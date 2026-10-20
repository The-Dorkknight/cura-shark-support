# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Geometry tests for shark_core (run: python3 -m pytest tests  or  python3 tests/test_core.py)."""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "SharkSupport"))
import shark_core as sc  # noqa: E402


def _rotz(v, deg):
    a = math.radians(deg)
    R = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    return v @ R.T


def _clear_of_part(part_v, part_f, fins_v, gap):
    """Every fin vertex is at least `gap` below the part directly above it."""
    ray = sc.UpRaycaster(*sc.weld(part_v, part_f))
    worst = math.inf
    for p in fins_v:
        z, _ = ray.cast(p[0], p[1])
        if z < math.inf:
            worst = min(worst, z - p[2])
    return worst >= gap - 1e-6, worst


def _piece_volumes(v, f):
    uf = sc._UnionFind(len(v))
    for a, b, c in f:
        uf.union(int(a), int(b)); uf.union(int(a), int(c))
    roots = np.array([uf.find(int(a)) for a in f[:, 0]])
    return [sc.mesh_volume(v, f[roots == r]) for r in np.unique(roots)]


def test_every_piece_faces_outward():
    v, f = sc.tilted_box(tilt_deg=45)          # fins on both sides of the edge -> both mirror cases
    V, F, _ = sc.make_fins(v, f, sc.FinSettings())
    vols = _piece_volumes(V, F)
    assert len(vols) > 10 and min(vols) > 0, min(vols)


def test_ribbon_is_closed_and_outward():
    cols = np.array([[0, 1, 0.5, 3], [2, 1, 0.5, 4], [5, 1, 0.6, 2]], dtype=float)
    v, f = sc.ribbon_mesh(cols)
    assert sc.is_closed(f)
    assert sc.mesh_volume(v, f) > 0


def test_box_volume():
    v, f = sc.box_mesh(0, 2, 0, 3, 0, 4)
    assert sc.is_closed(f)
    assert abs(sc.mesh_volume(v, f) - 24.0) < 1e-9


def test_tilted_box_faces():
    v, f = sc.tilted_box(tilt_deg=35)
    ff = sc.find_flat_faces(*sc.weld(v, f), sc.FinSettings())
    assert len(ff) == 1
    assert abs(ff[0].angle - 55.0) < 0.01
    assert abs(ff[0].area - 150 * 40) < 1


def test_default_fins_on_test_box():
    st = sc.FinSettings()
    v, f = sc.tilted_box(tilt_deg=35)
    V, F, rep = sc.make_fins(v, f, st)
    assert rep.fins == 5, rep.summary()
    assert rep.crossbars == 5
    assert rep.teeth >= 15
    assert sc.mesh_volume(V, F) > 0
    # every piece is outward-facing: volume equals the sum of positive piece volumes
    ok, worst = _clear_of_part(v, f, V, -st.anchor_overlap)
    assert ok, f"fin pokes into the part by {-worst:.3f} mm"
    # the anchor teeth really reach into the part
    assert worst < -st.anchor_overlap + 0.01, worst
    # with anchors off, every tip stays contact_gap under the part
    V0, _, _ = sc.make_fins(v, f, sc.FinSettings(anchor_teeth=0))
    ok0, worst0 = _clear_of_part(v, f, V0, st.contact_gap)
    assert ok0 and worst0 < st.contact_gap + 0.01, worst0
    assert V[:, 2].min() == 0.0


def test_first_tooth_at_low_end():
    st = sc.FinSettings()
    teeth = sc._tooth_breakpoints(10.0, 40.0, st)
    assert abs(teeth[0][0] - 10.0) < 1e-9                    # first ramp starts at the fin's low end
    assert 40.0 - teeth[-1][3] <= st.tooth_pitch / 2 + 1e-9  # and a tooth sits at the tall end
    gaps = [b[1] - a[1] for a, b in zip(teeth, teeth[1:])]
    assert max(gaps) <= st.tooth_pitch + 1e-9


def test_only_first_two_teeth_touch():
    st = sc.FinSettings()
    v, f = sc.tilted_box()
    b = sc.FinBuilder(v, f, st)
    V, F, rep = b.build()
    ray = sc.UpRaycaster(*sc.weld(v, f))
    # per fin (fins are spaced along X on this box), the touching points lie in the first 2 tooth spans
    for xc in np.unique(np.round(V[V[:, 2] > 1.0][:, 0] / 10.0)) * 10.0:
        sel = (np.abs(V[:, 0] - xc) < 3) & (V[:, 2] > 1.0)
        P = V[sel]
        depth = np.array([ray.cast(p[0], p[1])[0] - p[2] for p in P])
        touching = P[depth < 0]
        if not len(touching):
            continue
        y_low = P[:, 1].min()
        span = 2 * st.tooth_pitch
        assert (touching[:, 1] - y_low).max() <= span + 0.01, (touching[:, 1] - y_low).max()


def test_teeth_doubled():
    v, f = sc.tilted_box()
    _, _, r3 = sc.make_fins(v, f, sc.FinSettings())
    _, _, r6 = sc.make_fins(v, f, sc.FinSettings(tooth_pitch=6.0))
    assert r3.teeth >= 2 * r6.teeth - 5, (r3.teeth, r6.teeth)


def test_cut_blunt_vertical_is_default_and_cheapest():
    v, f = sc.tilted_box()
    kw = dict(brim=False, crossbar=False)
    vols = {}
    for back in ("vertical", "slope", "ellipse"):
        V, F, _ = sc.make_fins(v, f, sc.FinSettings(back_curve=back, **kw))
        vols[back] = sc.mesh_volume(V, F)
    V, F, _ = sc.make_fins(v, f, sc.FinSettings(**kw))
    assert abs(sc.mesh_volume(V, F) - vols["vertical"]) < 1e-6        # vertical is the default
    assert vols["vertical"] < vols["slope"] < vols["ellipse"] * 1.25
    # and cheaper than the 0.1.x fin that ran to the top with a sharp tip
    V0, F0, _ = sc.make_fins(v, f, sc.FinSettings(top_cut=0, tip_length=0, **kw))
    assert vols["vertical"] < sc.mesh_volume(V0, F0)


def test_top_left_free_and_blunt_tip():
    st = sc.FinSettings(brim=False, crossbar=False)
    v, f = sc.tilted_box()
    V0, _, _ = sc.make_fins(v, f, sc.FinSettings(top_cut=0, tip_length=0, brim=False, crossbar=False))
    V, F, _ = sc.make_fins(v, f, st)
    zmax0, zmax = V0[:, 2].max(), V[:, 2].max()
    assert zmax <= (1 - st.top_cut) * zmax0, (zmax, zmax0)
    assert zmax >= (1 - st.top_cut) * zmax0 - 1.5, (zmax, zmax0)
    # every fin has a flat top at least tip_length long (no tiny top layers)
    xs = np.sort(np.unique(np.round(V[:, 0], 3)))
    groups = np.split(xs, np.where(np.diff(xs) > 5)[0] + 1)
    assert len(groups) == 5
    for g in groups:
        P = V[(V[:, 0] >= g[0] - 1e-6) & (V[:, 0] <= g[-1] + 1e-6)]
        top = P[P[:, 2] >= P[:, 2].max() - 1e-6]
        assert top[:, 1].max() - top[:, 1].min() >= st.tip_length - st.sample_step - 1e-6


def test_pick_face_on_the_underside():
    v, f = sc.tilted_box()
    b = sc.FinBuilder(v, f)
    n, _ = sc.face_normals_areas(b.v, b.f)
    under = b.v[b.f[int(np.argmin(n[:, 2]))]].mean(axis=0)
    V, F, rep = sc.make_fins_at(v, f, under)
    assert rep.fins == 5 and len(rep.face_keys) == 1
    # the same face picked anywhere on it gives the same key
    other = b.v[b.f[[i for i in range(len(b.f)) if np.allclose(n[i], n[int(np.argmin(n[:, 2]))])][-1]]].mean(axis=0)
    assert sc.make_fins_at(v, f, other)[2].face_keys == rep.face_keys


def test_pick_refuses_top_and_misses():
    v, f = sc.tilted_box()
    b = sc.FinBuilder(v, f)
    n, _ = sc.face_normals_areas(b.v, b.f)
    top = b.v[b.f[int(np.argmax(n[:, 2]))]].mean(axis=0)
    _, F, rep = sc.make_fins_at(v, f, top)
    assert len(F) == 0 and "downwards" in rep.notes[0]
    _, F, rep = sc.make_fins_at(v, f, (500.0, 500.0, 500.0))
    assert len(F) == 0 and rep.notes


def test_pick_ignores_automatic_limits():
    v, f = sc.tilted_box()
    st = sc.FinSettings(min_face_area=1e9)            # auto would refuse every face
    assert sc.make_fins(v, f, st)[2].fins == 0
    b = sc.FinBuilder(v, f, st)
    n, _ = sc.face_normals_areas(b.v, b.f)
    under = b.v[b.f[int(np.argmin(n[:, 2]))]].mean(axis=0)
    assert sc.make_fins_at(v, f, under, st)[2].fins == 5


def test_brim_is_one_layer():
    st = sc.FinSettings(brim_thickness=0.24)
    v, f = sc.tilted_box()
    V, F, _ = sc.make_fins(v, f, st)
    zs = np.unique(np.round(V[:, 2], 6))
    assert 0.24 in zs


def test_no_brim_no_crossbar():
    st = sc.FinSettings(brim=False, crossbar=False)
    v, f = sc.tilted_box()
    V, F, rep = sc.make_fins(v, f, st)
    assert rep.crossbars == 0
    assert sc.is_closed(F)          # only ribbons left, each closed


def test_rotated_on_bed_and_triangle_soup():
    v, f = sc.tilted_box(tilt_deg=45)
    v = _rotz(v, 30) + np.array([20.0, -10.0, 0.0])
    soup = v[f].reshape(-1, 3)                  # like Cura's unindexed meshes
    V, F, rep = sc.make_fins(soup, None, sc.FinSettings())
    # at 45 degrees both faces beside the standing edge are overhangs: 5 fins each
    assert rep.faces_used == 2 and rep.fins == 10, rep.summary()
    ok, worst = _clear_of_part(v, f, V, -sc.FinSettings().anchor_overlap)
    assert ok, worst


def test_box_standing_on_a_corner():
    v, f = sc.tilted_box(tilt_deg=35)
    a = math.radians(12)
    R = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    v = v @ R.T
    v[:, 2] -= v[:, 2].min()
    V, F, rep = sc.make_fins(v, f, sc.FinSettings())
    assert rep.fins >= 5
    ok, worst = _clear_of_part(v, f, V, -sc.FinSettings().anchor_overlap)
    assert ok, worst
    assert min(_piece_volumes(V, F)) > 0


def test_flat_cube_gets_nothing():
    v, f = sc.box_mesh(0, 20, 0, 20, 0, 20)
    V, F, rep = sc.make_fins(v, f, sc.FinSettings())
    assert rep.fins == 0 and len(F) == 0
    assert rep.notes


def test_spacing_changes_count():
    v, f = sc.tilted_box(length=200)
    _, _, r1 = sc.make_fins(v, f, sc.FinSettings(spacing=20))
    _, _, r2 = sc.make_fins(v, f, sc.FinSettings(spacing=50))
    assert r1.fins > r2.fins >= 2


def test_long_fin_gets_middle_crossbar():
    v, f = sc.tilted_box(length=60, depth=160, height=20, tilt_deg=30)
    _, _, rep = sc.make_fins(v, f, sc.FinSettings(spacing=40))
    assert rep.crossbars > rep.fins


def test_settings_from_dict():
    s = sc.FinSettings.from_dict({"spacing": "25", "brim": "false", "max_fins": "12.0", "nope": 1})
    assert s.spacing == 25.0 and s.brim is False and s.max_fins == 12


def test_stl_roundtrip(tmp_path=None):
    import tempfile
    d = tmp_path or tempfile.mkdtemp()
    v, f = sc.tilted_box()
    p = os.path.join(str(d), "b.stl")
    sc.write_stl(p, v, f)
    soup = sc.read_stl(p)
    assert soup.shape == (len(f) * 3, 3)


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as ex:  # noqa: BLE001
                fails += 1
                print("FAIL", name, repr(ex))
    print("RESULT:", "PASS" if not fails else f"{fails} FAILED")
    sys.exit(1 if fails else 0)
