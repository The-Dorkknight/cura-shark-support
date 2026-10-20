# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
#
# Shark Support - geometry core (WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN)
#
# Pure numpy, no Cura imports, so the same code runs inside Cura, in the
# command-line tool and in the tests. All coordinates here are Z-up in mm
# with the build plate at z = 0 (Cura's scene is Y-up; the plugin converts).
#
# What it does, in short:
#   1. find flat, downward-facing faces whose overhang angle is in a band
#   2. for each such face, work out its downhill direction
#   3. lay out thin vertical fins along that direction, spaced across the face
#   4. raycast up from the bed to get the exact underside height along each fin
#   5. build each fin as a closed "ribbon" mesh: tapered thickness, a relief gap
#      under the part, small teeth that reach up to just below the part, a
#      curved back edge, a crossbar foot and a one-layer brim pad
"""Shark-fin support geometry (numpy only)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import numpy as np

__version__ = "0.2.1-wip"


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

@dataclass
class FinSettings:
    """Every tunable number, in mm or degrees.

    Overhang angle follows Cura's convention: 0 = vertical wall,
    90 = flat ceiling.
    """
    min_angle: float = 20.0          # faces flatter than vertical by at least this ...
    max_angle: float = 70.0          # ... and steeper than a flat ceiling by this
    min_face_area: float = 300.0     # mm^2, ignore small faces
    min_reach: float = 15.0          # mm, face's horizontal depth along the slope
    coplanar_tolerance: float = 3.0  # degrees, triangles merged into one face

    spacing: float = 30.0            # mm between fins across the face
    edge_margin: float = 4.0         # mm, keep fins this far in from the face's side edges
    min_fin_height: float = 4.0      # mm, fins start where the face is this high
    min_fin_length: float = 8.0      # mm, drop shorter fins
    sample_step: float = 0.5         # mm, profile resolution

    thick_base: float = 2.4          # mm, fin thickness at the bed
    thick_top: float = 1.2           # mm, fin thickness at the top edge
    relief: float = 1.0              # mm, gap between fin top edge and part (between teeth)

    tooth_pitch: float = 3.0         # mm between tooth tips
    tooth_tip: float = 0.6           # mm, flat length of each tip
    tooth_ramp: float = 1.0          # mm, length of each tooth flank
    contact_gap: float = 0.15        # mm, tips stop this far below the part
    anchor_teeth: int = 2            # the first N teeth from the low end really touch the part ...
    anchor_overlap: float = 0.1      # ... reaching this far into it, so they bond slightly

    top_cut: float = 0.15            # leave this fraction of the fin's height unsupported at the top
                                     # (the part is held by the lower 85 %); 0 = run to the top
    tip_length: float = 5.0          # mm, flat blunt tip: no layer of the fin gets shorter than this
    back_curve: str = "vertical"     # "vertical": straight down from the blunt tip (default, least plastic),
                                     # "slope": straight back leaning out to the bed (wider base),
                                     # "ellipse" (round back) or "concave" (shark look)
    back_lean: float = 20.0          # degrees from vertical for the "slope" back
    rake: float = 0.35               # curved back edge length as fraction of tallest height
    rake_max: float = 25.0           # mm
    rake_min: float = 3.0            # mm

    crossbar: bool = True
    crossbar_fraction: float = 0.25  # crossbar length as fraction of fin footprint length
    crossbar_min_length: float = 10.0
    crossbar_height: float = 4.0
    crossbar_thickness: float = 2.0
    second_crossbar_over: float = 100.0  # mm footprint length that earns a middle crossbar

    brim: bool = True
    brim_width: float = 4.0
    brim_thickness: float = 0.2      # set to your first layer height (the Cura plugin does this for you)
    brim_clearance: float = 1.0      # mm, pad stays where the part is at least this high

    max_fins: int = 200              # safety cap

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "FinSettings":
        s = cls()
        for k, v in (d or {}).items():
            if hasattr(s, k):
                cur = getattr(s, k)
                try:
                    if isinstance(cur, bool):
                        v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
                    elif isinstance(cur, int):
                        v = int(float(v))
                    elif isinstance(cur, float):
                        v = float(v)
                    else:
                        v = str(v)
                except (TypeError, ValueError):
                    continue
                setattr(s, k, v)
        return s


@dataclass
class FinReport:
    faces_found: int = 0
    faces_used: int = 0
    face_keys: List[Tuple[float, float, float, float]] = field(default_factory=list)
    fins: int = 0
    crossbars: int = 0
    teeth: int = 0
    notes: List[str] = field(default_factory=list)

    def summary(self) -> str:
        s = (f"{self.fins} fin(s) under {self.faces_used} of {self.faces_found} "
             f"candidate face(s), {self.teeth} teeth, {self.crossbars} crossbar(s)")
        return s


# --------------------------------------------------------------------------
# Mesh helpers
# --------------------------------------------------------------------------

def weld(vertices: np.ndarray, faces: Optional[np.ndarray], tol: float = 1e-4) -> Tuple[np.ndarray, np.ndarray]:
    """Merge duplicate vertices so faces share indices (Cura meshes are often a triangle soup)."""
    v = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    if faces is None:
        f = np.arange(len(v)).reshape(-1, 3)
    else:
        f = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    key = np.round(v / tol).astype(np.int64)
    _, first, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inverse = inverse.reshape(-1)
    nv = v[first]
    nf = inverse[f]
    # drop degenerate triangles
    ok = (nf[:, 0] != nf[:, 1]) & (nf[:, 1] != nf[:, 2]) & (nf[:, 0] != nf[:, 2])
    return nv, nf[ok]


def face_normals_areas(v: np.ndarray, f: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    cr = np.cross(b - a, c - a)
    ln = np.linalg.norm(cr, axis=1)
    n = np.zeros_like(cr)
    good = ln > 1e-12
    n[good] = cr[good] / ln[good, None]
    return n, 0.5 * ln


def overhang_angle_deg(normals: np.ndarray) -> np.ndarray:
    """0 = vertical wall, 90 = flat ceiling; negative for upward-facing."""
    return np.degrees(np.arcsin(np.clip(-normals[:, 2], -1.0, 1.0)))


class _UnionFind:
    def __init__(self, n: int):
        self.p = np.arange(n)

    def find(self, i: int) -> int:
        p = self.p
        while p[i] != i:
            p[i] = p[p[i]]
            i = p[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


@dataclass
class FlatFace:
    face_ids: np.ndarray       # triangle indices
    normal: np.ndarray         # unit, pointing down
    area: float
    angle: float               # overhang angle, degrees
    downhill: np.ndarray       # unit horizontal vector (x, y, 0) pointing down the slope
    across: np.ndarray         # unit horizontal vector perpendicular to downhill
    reach: float               # horizontal extent along downhill


def face_groups(v: np.ndarray, f: np.ndarray, s: FinSettings, use_limits: bool = True) -> List[FlatFace]:
    """Group coplanar, edge-connected downward triangles into flat faces.

    use_limits=True keeps only faces inside the angle band and above the size limits (automatic mode);
    False keeps every downward face that is not a flat ceiling (for faces the user picked by hand).
    """
    n, area = face_normals_areas(v, f)
    ang = overhang_angle_deg(n)
    if use_limits:
        cand = np.where((ang >= s.min_angle) & (ang <= s.max_angle) & (area > 1e-9))[0]
    else:
        cand = np.where((ang > 0.5) & (ang < 89.5) & (area > 1e-9))[0]
    if len(cand) == 0:
        return []
    uf = _UnionFind(len(cand))
    cos_tol = math.cos(math.radians(s.coplanar_tolerance))
    edge_owner: Dict[Tuple[int, int], int] = {}
    for k, ti in enumerate(cand):
        tri = f[ti]
        for e in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            key = (int(min(e)), int(max(e)))
            other = edge_owner.get(key)
            if other is None:
                edge_owner[key] = k
            else:
                if float(np.dot(n[cand[other]], n[ti])) >= cos_tol:
                    uf.union(other, k)
    groups: Dict[int, List[int]] = {}
    for k in range(len(cand)):
        groups.setdefault(uf.find(k), []).append(int(cand[k]))

    out: List[FlatFace] = []
    for ids in groups.values():
        ids_a = np.array(ids, dtype=np.int64)
        a = float(area[ids_a].sum())
        if use_limits and a < s.min_face_area:
            continue
        nn = (n[ids_a] * area[ids_a, None]).sum(axis=0)
        nn /= max(np.linalg.norm(nn), 1e-12)
        g = np.array([0.0, 0.0, -1.0])
        d = g - np.dot(g, nn) * nn          # steepest descent within the plane
        dh = np.array([d[0], d[1], 0.0])
        ln = np.linalg.norm(dh)
        if ln < 1e-6:
            continue                           # a flat ceiling has no downhill
        dh /= ln
        ac = np.array([-dh[1], dh[0], 0.0])
        pts = v[np.unique(f[ids_a].reshape(-1))]
        u = pts @ dh
        reach = float(u.max() - u.min())
        if use_limits and reach < s.min_reach:
            continue
        out.append(FlatFace(ids_a, nn, a, float(math.degrees(math.asin(min(1.0, -nn[2])))), dh, ac, reach))
    out.sort(key=lambda ff: -ff.area)
    return out


def find_flat_faces(v: np.ndarray, f: np.ndarray, s: FinSettings) -> List[FlatFace]:
    """Faces that get fins in automatic mode."""
    return face_groups(v, f, s, use_limits=True)


def triangle_at_point(v: np.ndarray, f: np.ndarray, point, tol: float = 1.0) -> int:
    """Index of the triangle that contains the point (within tol mm of its plane), or -1."""
    p = np.asarray(point, dtype=np.float64)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-12
    n = np.where(ok[:, None], n / np.where(ok, ln, 1.0)[:, None], 0.0)
    dist = np.abs(np.einsum("ij,ij->i", p - a, n))
    q = p - np.einsum("ij,i->ij", n, np.einsum("ij,ij->i", p - a, n))    # projected onto each plane
    v0, v1, v2 = b - a, c - a, q - a
    d00 = np.einsum("ij,ij->i", v0, v0)
    d01 = np.einsum("ij,ij->i", v0, v1)
    d11 = np.einsum("ij,ij->i", v1, v1)
    d20 = np.einsum("ij,ij->i", v2, v0)
    d21 = np.einsum("ij,ij->i", v2, v1)
    den = d00 * d11 - d01 * d01
    den = np.where(np.abs(den) > 1e-18, den, np.inf)
    l1 = (d11 * d20 - d01 * d21) / den
    l2 = (d00 * d21 - d01 * d20) / den
    eps = 0.02
    inside = ok & (l1 >= -eps) & (l2 >= -eps) & (l1 + l2 <= 1 + eps) & (dist <= tol)
    if not inside.any():
        return -1
    cand = np.where(inside)[0]
    return int(cand[np.argmin(dist[cand])])


class UpRaycaster:
    """Vertical rays from below. Returns the lowest point of the part above (x, y).

    For a closed mesh the first surface hit from below always faces down, so
    only downward-facing triangles are indexed. A uniform XY grid keeps it fast
    enough for low-end machines.
    """

    def __init__(self, v: np.ndarray, f: np.ndarray):
        n, _ = face_normals_areas(v, f)
        keep = np.where(n[:, 2] < -1e-9)[0]
        self.ids = keep
        tri = v[f[keep]]                       # (T, 3, 3)
        self.tri = tri
        self.n = n[keep]
        lo = tri[:, :, :2].min(axis=1)
        hi = tri[:, :, :2].max(axis=1)
        self.lo, self.hi = lo, hi
        if len(keep) == 0:
            self.cell = 1.0
            self.origin = np.zeros(2)
            self.grid: Dict[Tuple[int, int], np.ndarray] = {}
            return
        span = np.maximum(hi.max(axis=0) - lo.min(axis=0), 1e-3)
        cell = max(1.0, math.sqrt(span[0] * span[1] / max(len(keep), 1)) * 2.0)
        self.cell = cell
        self.origin = lo.min(axis=0)
        g: Dict[Tuple[int, int], List[int]] = {}
        i0 = np.floor((lo - self.origin) / cell).astype(int)
        i1 = np.floor((hi - self.origin) / cell).astype(int)
        for k in range(len(keep)):
            for ix in range(i0[k, 0], i1[k, 0] + 1):
                for iy in range(i0[k, 1], i1[k, 1] + 1):
                    g.setdefault((ix, iy), []).append(k)
        self.grid = {key: np.array(val, dtype=np.int64) for key, val in g.items()}

    def cast(self, x: float, y: float) -> Tuple[float, int]:
        """(z of lowest hit, triangle index in the original mesh) or (inf, -1)."""
        if not self.grid:
            return math.inf, -1
        key = (int(math.floor((x - self.origin[0]) / self.cell)),
               int(math.floor((y - self.origin[1]) / self.cell)))
        cand = self.grid.get(key)
        if cand is None:
            return math.inf, -1
        t = self.tri[cand]
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        v0 = b[:, :2] - a[:, :2]
        v1 = c[:, :2] - a[:, :2]
        v2 = np.array([x, y]) - a[:, :2]
        den = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
        ok = np.abs(den) > 1e-12
        if not ok.any():
            return math.inf, -1
        den = np.where(ok, den, 1.0)
        l1 = (v2[:, 0] * v1[:, 1] - v1[:, 0] * v2[:, 1]) / den
        l2 = (v0[:, 0] * v2[:, 1] - v2[:, 0] * v0[:, 1]) / den
        l0 = 1.0 - l1 - l2
        eps = -1e-7
        inside = ok & (l0 >= eps) & (l1 >= eps) & (l2 >= eps)
        if not inside.any():
            return math.inf, -1
        z = l0 * a[:, 2] + l1 * b[:, 2] + l2 * c[:, 2]
        z = np.where(inside, z, np.inf)
        k = int(np.argmin(z))
        return float(z[k]), int(self.ids[cand[k]])


# --------------------------------------------------------------------------
# Mesh building
# --------------------------------------------------------------------------

class MeshAccumulator:
    def __init__(self):
        self.verts: List[np.ndarray] = []
        self.faces: List[np.ndarray] = []
        self.count = 0

    def add(self, v: np.ndarray, f: np.ndarray) -> None:
        self.verts.append(np.asarray(v, dtype=np.float64))
        self.faces.append(np.asarray(f, dtype=np.int64) + self.count)
        self.count += len(v)

    def build(self) -> Tuple[np.ndarray, np.ndarray]:
        if not self.verts:
            return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)
        return np.vstack(self.verts), np.vstack(self.faces)


def _quads_to_tris(quads: List[Tuple[int, int, int, int]]) -> np.ndarray:
    out = []
    for a, b, c, d in quads:          # quads are listed clockwise seen from outside
        out.append((a, c, b))
        out.append((a, d, c))
    return np.array(out, dtype=np.int64)


def ribbon_mesh(cols: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Closed mesh from columns.

    cols: (N, 4) rows of (s, half_bottom, half_top, top_z), s increasing.
    Local frame: x = s, y = sideways offset, z = height; bottom at z = 0.
    Each column has 4 vertices: 0 bottom-left, 1 bottom-right, 2 top-right, 3 top-left.
    Winding gives outward normals (checked by the tests).
    """
    N = len(cols)
    V = np.zeros((N * 4, 3))
    for i, (s, hb, ht, tz) in enumerate(cols):
        V[4 * i + 0] = (s, -hb, 0.0)
        V[4 * i + 1] = (s, hb, 0.0)
        V[4 * i + 2] = (s, ht, tz)
        V[4 * i + 3] = (s, -ht, tz)
    q: List[Tuple[int, int, int, int]] = []
    for i in range(N - 1):
        a, b = 4 * i, 4 * (i + 1)
        q.append((a + 0, b + 0, b + 1, a + 1))   # bottom (normal -z)
        q.append((a + 1, b + 1, b + 2, a + 2))   # right side (+y)
        q.append((a + 2, b + 2, b + 3, a + 3))   # top (+z)
        q.append((a + 3, b + 3, b + 0, a + 0))   # left side (-y)
    q.append((0, 1, 2, 3))                       # start cap (-x)
    e = 4 * (N - 1)
    q.append((e + 0, e + 3, e + 2, e + 1))       # end cap (+x)
    return V, _quads_to_tris(q)


def box_mesh(x0, x1, y0, y1, z0, z1) -> Tuple[np.ndarray, np.ndarray]:
    cols = np.array([[x0, (y1 - y0) / 2, (y1 - y0) / 2, z1 - z0],
                     [x1, (y1 - y0) / 2, (y1 - y0) / 2, z1 - z0]])
    V, F = ribbon_mesh(cols)
    V[:, 1] += (y0 + y1) / 2
    V[:, 2] += z0
    return V, F


def mesh_volume(v: np.ndarray, f: np.ndarray) -> float:
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def is_closed(f: np.ndarray) -> bool:
    edges = np.sort(np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    _, cnt = np.unique(edges, axis=0, return_counts=True)
    return bool(np.all(cnt == 2))


# --------------------------------------------------------------------------
# Fin layout
# --------------------------------------------------------------------------

def _longest_true_run(mask: np.ndarray) -> Optional[Tuple[int, int]]:
    best = None
    start = None
    for i, m in enumerate(list(mask) + [False]):
        if m and start is None:
            start = i
        elif not m and start is not None:
            if best is None or (i - start) > (best[1] - best[0]):
                best = (start, i)
            start = None
    return best


def _tooth_breakpoints(s0: float, s1: float, st: FinSettings) -> List[Tuple[float, float, float, float]]:
    """Teeth as (ramp_start, tip_start, tip_end, ramp_end) inside [s0, s1].

    The first tooth starts right at the low end of the fin, so the part is held from
    the first millimetres of the fin. Teeth then follow every tooth_pitch, and a last
    tooth sits at the tall end (where the face ends) unless one is already close to it.
    """
    teeth = []
    half = st.tooth_tip / 2 + st.tooth_ramp
    if st.tooth_pitch <= 0 or s1 - s0 < 2 * half:
        return teeth
    centres = []
    c = s0 + half
    while c <= s1 - half + 1e-9:
        centres.append(c)
        c += st.tooth_pitch
    last = s1 - half
    if last - centres[-1] > st.tooth_pitch * 0.5:
        centres.append(last)
    for c in centres:
        teeth.append((c - half, c - st.tooth_tip / 2, c + st.tooth_tip / 2, c + half))
    return teeth


class FinBuilder:
    def __init__(self, vertices: np.ndarray, faces: Optional[np.ndarray], settings: Optional[FinSettings] = None):
        self.s = settings or FinSettings()
        self.v, self.f = weld(vertices, faces)
        self.ray = UpRaycaster(self.v, self.f)
        self.report = FinReport()

    # world point from fin-local (s along e, w across, z) ------------------
    @staticmethod
    def _to_world(V: np.ndarray, e: np.ndarray, c: np.ndarray, t: float) -> np.ndarray:
        out = np.empty_like(V)
        out[:, 0] = V[:, 0] * e[0] + (V[:, 1] + t) * c[0]
        out[:, 1] = V[:, 0] * e[1] + (V[:, 1] + t) * c[1]
        out[:, 2] = V[:, 2]
        return out

    @staticmethod
    def _faces_for(F: np.ndarray, e: np.ndarray, c: np.ndarray) -> np.ndarray:
        # (s, w) -> (e, c) is a mirror when e x c points down; flip winding then
        return F[:, ::-1] if (e[0] * c[1] - e[1] * c[0]) < 0 else F

    def _hit(self, e, c, t, s, w=0.0) -> Tuple[float, int]:
        x = s * e[0] + (t + w) * c[0]
        y = s * e[1] + (t + w) * c[1]
        return self.ray.cast(x, y)

    def _clearance(self, e, c, t, s0, s1, w0, w1, n=4) -> float:
        """Lowest part height over a rectangle in fin-local coordinates (inf if open)."""
        lo = math.inf
        for s in np.linspace(s0, s1, max(2, n)):
            for w in np.linspace(w0, w1, max(2, n)):
                z, _ = self._hit(e, c, t, s, w)
                lo = min(lo, z)
        return lo

    def build(self, faces: Optional[List[FlatFace]] = None) -> Tuple[np.ndarray, np.ndarray, FinReport]:
        st = self.s
        if faces is None:
            faces = find_flat_faces(self.v, self.f, st)
        self.report.faces_found = len(faces)
        acc = MeshAccumulator()
        for ff in faces:
            if self.report.fins >= st.max_fins:
                self.report.notes.append(f"stopped at the {st.max_fins}-fin safety cap")
                break
            made = self._fins_for_face(ff, acc)
            if made:
                self.report.faces_used += 1
                self.report.face_keys.append(self.key_for(ff))
        V, F = acc.build()
        if not len(F) and not self.report.notes:
            self.report.notes.append("no fins made: no flat downward face matched the angle, area and reach limits")
        return V, F, self.report

    def key_for(self, ff: FlatFace) -> Tuple[float, float, float, float]:
        """Rounded plane of a face (normal and offset), to recognise the same face again."""
        p = self.v[self.f[ff.face_ids[0], 0]]
        return (round(float(ff.normal[0]), 2), round(float(ff.normal[1]), 2), round(float(ff.normal[2]), 2),
                round(float(np.dot(ff.normal, p)), 0))

    def face_at(self, point, tol: float = 1.0):
        """The flat downward face under a picked point: (FlatFace, None) or (None, reason)."""
        ti = triangle_at_point(self.v, self.f, point, tol)
        if ti < 0:
            return None, "the click was not on this model's surface"
        n, _ = face_normals_areas(self.v, self.f[ti:ti + 1])
        ang = float(overhang_angle_deg(n)[0])
        if ang <= 0.5:
            return None, "that face does not face downwards (overhang %.0f\u00b0): pick the underside" % ang
        if ang >= 89.5:
            return None, "that face is a flat ceiling: fins need a sloping face"
        for ff in face_groups(self.v, self.f, self.s, use_limits=False):
            if ti in set(int(i) for i in ff.face_ids):
                return ff, None
        return None, "could not group the picked face"

    def build_at(self, point, tol: float = 1.0) -> Tuple[np.ndarray, np.ndarray, FinReport]:
        ff, why = self.face_at(point, tol)
        if ff is None:
            self.report.notes.append(why)
            return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64), self.report
        V, F, rep = self.build([ff])
        if not len(F):
            rep.notes = ["the face is too small or too low for a fin (overhang %.0f\u00b0, %.0f mm along the slope); "
                         "try a lower Start height" % (ff.angle, ff.reach)]
        return V, F, rep

    def _fins_for_face(self, ff: FlatFace, acc: MeshAccumulator) -> int:
        st = self.s
        region = set(int(i) for i in ff.face_ids)
        pts = self.v[np.unique(self.f[ff.face_ids].reshape(-1))]
        h, c = ff.downhill, ff.across
        u_all = pts @ h
        t_all = pts @ c
        tmin, tmax = float(t_all.min()), float(t_all.max())
        width = tmax - tmin - 2 * st.edge_margin
        if width <= 0:
            ts = [(tmin + tmax) / 2]
        else:
            nf = int(width // max(st.spacing, 1.0)) + 1
            if nf == 1:
                ts = [(tmin + tmax) / 2]
            else:
                ts = list(np.linspace(tmin + st.edge_margin, tmax - st.edge_margin, nf))
        umin, umax = float(u_all.min()) - 1.0, float(u_all.max()) + 1.0
        made = 0
        for t in ts:
            if self.report.fins >= st.max_fins:
                break
            if self._one_fin(h, c, t, umin, umax, region, acc):
                made += 1
        return made

    def _one_fin(self, h, c, t, umin, umax, region, acc) -> bool:
        st = self.s
        step = max(0.1, st.sample_step)
        us = np.arange(umin, umax + step / 2, step)
        zs = np.empty(len(us))
        fid = np.empty(len(us), dtype=np.int64)
        for i, u in enumerate(us):
            zs[i], fid[i] = self._hit(h, c, t, u)
        mask = np.array([int(k) in region for k in fid]) & (zs >= st.min_fin_height)
        run = _longest_true_run(mask)
        if run is None:
            return False
        i0, i1 = run
        if (i1 - i0) * step < st.min_fin_length:
            return False
        u_run, z_run = us[i0:i1], zs[i0:i1]
        # orient so s grows toward the tall end
        if z_run[-1] >= z_run[0]:
            e = h.copy()
            s_run = u_run
        else:
            e = -h
            s_run = -u_run[::-1]
            z_run = z_run[::-1]
        s0, s1 = float(s_run[0]), float(s_run[-1])

        def surf(sq: float) -> float:
            return float(np.interp(sq, s_run, z_run))

        # where the fin stops following the part: top_cut of its height is left to bridge on its own
        z_face = z_run - st.relief
        z_cut = (1.0 - max(0.0, min(0.9, st.top_cut))) * float(z_face.max())
        if z_cut <= 0.5:
            return False
        k_cut = int(np.argmax(z_face >= z_cut - 1e-9))
        if k_cut == 0:
            s_cut = s0
        else:
            za, zb = z_face[k_cut - 1], z_face[k_cut]
            q = (z_cut - za) / max(zb - za, 1e-9)
            s_cut = float(s_run[k_cut - 1] + q * (s_run[k_cut] - s_run[k_cut - 1]))

        # profile sample positions along the part: grid + tooth breakpoints, up to the cut
        teeth = _tooth_breakpoints(s0, s_cut, st)
        sset = set(np.round(s_run[s_run < s_cut], 6).tolist())
        sset.add(round(s_cut, 6))
        for tb in teeth:
            for x in tb:
                sset.add(round(float(x), 6))
        s_prof = np.array(sorted(x for x in sset if x <= s_cut + 1e-9))
        top = np.array([min(surf(x) - st.relief, z_cut) for x in s_prof])
        for k, (r0, p0, p1, r1) in enumerate(teeth):
            reach = st.anchor_overlap if k < st.anchor_teeth else -st.contact_gap
            for i, x in enumerate(s_prof):
                if r0 <= x <= r1:
                    if x < p0:
                        fr = (x - r0) / max(p0 - r0, 1e-9)
                    elif x > p1:
                        fr = (r1 - x) / max(r1 - p1, 1e-9)
                    else:
                        fr = 1.0
                    full = surf(x) + reach
                    top[i] = max(top[i], top[i] + fr * (full - top[i]))
        top = np.minimum(top, z_cut)          # nothing pokes above the blunt top (no tiny top layers)

        # blunt tip: flat at z_cut for tip_length, then the back edge
        s_back, z_back = [], []

        def push(sx: float, zz: float) -> bool:
            hz, _ = self._hit(e, c, t, sx)
            zz = min(zz, hz - st.relief)
            if zz < 0.6:
                return False
            s_back.append(sx)
            z_back.append(zz)
            return True

        s_tip = s_cut + max(0.0, st.tip_length)
        n_tip = max(1, int(round((s_tip - s_cut) / step)))
        for k in range(1, n_tip + 1):
            if not push(s_cut + (s_tip - s_cut) * k / n_tip, z_cut):
                break
        H_end = z_back[-1] if z_back else float(top[-1])
        s_from = s_back[-1] if s_back else s_cut
        if st.back_curve == "slope":
            run_len = H_end * math.tan(math.radians(max(0.0, min(80.0, st.back_lean))))
            nback = max(2, int(run_len / step))
            for k in range(1, nback + 1):
                q = k / nback
                if not push(s_from + q * run_len, max(H_end * (1.0 - q), 0.6)):
                    break
        elif st.back_curve in ("ellipse", "concave"):
            R = float(np.clip(st.rake * H_end, st.rake_min, st.rake_max))
            nback = max(4, int(R / step))
            for k in range(1, nback + 1):
                q = k / nback
                if st.back_curve == "concave":
                    zz = H_end * (1.0 - q) ** 2
                else:
                    zz = H_end * math.sqrt(max(0.0, 1.0 - q * q))
                if not push(s_from + q * R, max(zz, 0.6)):
                    break
        # "vertical" (or "triangle" from 0.1.x): nothing more, the fin ends straight down under the tip
        s_all = np.concatenate([s_prof, np.array(s_back)]) if s_back else s_prof
        z_all = np.concatenate([top, np.array(z_back)]) if z_back else top
        s_end = float(s_all[-1])
        s_tip_end = s_tip if s_back else s_cut

        hb = st.thick_base / 2
        Hmax = max(float(z_all.max()), 1e-6)
        thick = st.thick_base - (st.thick_base - st.thick_top) * np.clip(z_all / Hmax, 0, 1)
        cols = np.column_stack([s_all, np.full(len(s_all), hb), thick / 2, z_all])
        V, F = ribbon_mesh(cols)
        acc.add(self._to_world(V, e, c, t), self._faces_for(F, e, c))
        self.report.fins += 1
        self.report.teeth += len(teeth)

        footprint = s_end - s0
        bars: List[Tuple[float, float]] = []   # (s centre, half length)
        if st.crossbar:
            L = max(st.crossbar_min_length, st.crossbar_fraction * footprint)
            centres = [min((s_cut + s_tip_end) / 2, s_end - st.crossbar_thickness / 2)]   # under the tip
            if footprint > st.second_crossbar_over:
                centres.append((s0 + s_cut) / 2)
            for sc in centres:
                ct = st.crossbar_thickness / 2
                clear = self._clearance(e, c, t, sc - ct, sc + ct, -L / 2, L / 2)
                hgt = min(st.crossbar_height, clear - st.relief)
                if hgt < 1.5:
                    continue
                bv, bf = box_mesh(sc - ct, sc + ct, -L / 2, L / 2, 0.0, hgt)
                acc.add(self._to_world(bv, e, c, t), self._faces_for(bf, e, c))
                bars.append((sc, L / 2))
                self.report.crossbars += 1

        if st.brim and st.brim_width > 0 and st.brim_thickness > 0:
            bw = st.brim_width
            need = st.brim_thickness + st.brim_clearance
            # trim the pad's low end until the part is high enough above it
            p0 = s0 - bw
            while p0 < s0 and self._clearance(e, c, t, p0, p0, -hb - bw, hb + bw, n=3) < need:
                p0 += step
            pv, pf = box_mesh(p0, s_end + bw, -hb - bw, hb + bw, 0.0, st.brim_thickness)
            acc.add(self._to_world(pv, e, c, t), self._faces_for(pf, e, c))
            for sc, half in bars:
                ct = st.crossbar_thickness / 2
                if self._clearance(e, c, t, sc - ct - bw, sc + ct + bw, -half - bw, half + bw) >= need:
                    pv, pf = box_mesh(sc - ct - bw, sc + ct + bw, -half - bw, half + bw, 0.0, st.brim_thickness)
                    acc.add(self._to_world(pv, e, c, t), self._faces_for(pf, e, c))
        return True


def make_fins(vertices: np.ndarray, faces: Optional[np.ndarray] = None,
              settings: Optional[FinSettings] = None) -> Tuple[np.ndarray, np.ndarray, FinReport]:
    """Main entry point (automatic mode). vertices (N,3) Z-up mm; faces (M,3) or None for a triangle soup."""
    return FinBuilder(vertices, faces, settings).build()


def make_fins_at(vertices: np.ndarray, faces: Optional[np.ndarray], point,
                 settings: Optional[FinSettings] = None, tol: float = 1.0) -> Tuple[np.ndarray, np.ndarray, FinReport]:
    """Fins under the one flat face that contains `point` (a picked spot on the part, Z-up mm)."""
    return FinBuilder(vertices, faces, settings).build_at(point, tol)


# --------------------------------------------------------------------------
# STL input/output (no extra dependencies)
# --------------------------------------------------------------------------

def read_stl(path: str) -> np.ndarray:
    """Return an (M*3, 3) triangle soup."""
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) >= 84:
        n = int.from_bytes(data[80:84], "little")
        if 84 + n * 50 == len(data):
            rec = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]),
                                count=n, offset=84)
            return rec["v"].reshape(-1, 3).astype(np.float64)
    pts = []
    for line in data.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if line.startswith("vertex"):
            parts = line.split()
            pts.append([float(parts[1]), float(parts[2]), float(parts[3])])
    if not pts or len(pts) % 3:
        raise ValueError(f"{path}: not a readable STL")
    return np.array(pts, dtype=np.float64)


def write_stl(path: str, v: np.ndarray, f: np.ndarray, name: str = "shark-fins") -> None:
    tri = v[f].astype(np.float32)
    n, _ = face_normals_areas(v, f)
    header = (f"Shark Support {__version__} {name}".encode()[:80]).ljust(80, b" ")
    rec = np.zeros(len(f), dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    rec["n"] = n.astype(np.float32)
    rec["v"] = tri
    with open(path, "wb") as fh:
        fh.write(header)
        fh.write(np.uint32(len(f)).tobytes())
        fh.write(rec.tobytes())


def tilted_box(length=150.0, depth=40.0, height=25.0, tilt_deg=35.0) -> Tuple[np.ndarray, np.ndarray]:
    """Test model: a long box rotated about one long bottom edge, standing on that edge.

    With tilt_deg = 35 the base becomes a 55 degree overhang (Cura convention)
    and the adjacent side a 35 degree one. Returned Z-up, sitting on z = 0.
    """
    x = [0, length]
    corners = np.array([[xi, yi, zi] for xi in x for yi in (0, depth) for zi in (0, height)], dtype=float)
    # index = 4*ix + 2*iy + iz
    faces = np.array([
        [0, 4, 6], [0, 6, 2],   # z=0 base
        [1, 3, 7], [1, 7, 5],   # z=top
        [0, 1, 5], [0, 5, 4],   # y=0
        [2, 6, 7], [2, 7, 3],   # y=depth
        [0, 2, 3], [0, 3, 1],   # x=0
        [4, 5, 7], [4, 7, 6],   # x=length
    ])
    a = math.radians(tilt_deg)
    # rotate about the X axis through the edge y=0,z=0 so the base tips up
    R = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    v = corners @ R.T
    v[:, 2] -= v[:, 2].min()
    # make sure outward winding survived
    if mesh_volume(v, faces) < 0:
        faces = faces[:, ::-1]
    return v, faces
