# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Side view of one real fin from the test box, with the parts labelled.

python3 tools/draw_profile.py docs/images/fin-profile.png
Everything drawn comes from shark_core output (no hand-drawn shapes). Needs matplotlib.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "SharkSupport"))
import shark_core as sc  # noqa: E402


def main(out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    st = sc.FinSettings()
    v, f = sc.tilted_box(tilt_deg=35)
    V, F, rep = sc.make_fins(v, f, st)
    # the box's long axis is X; the fins run along Y. Take the middle fin (x near 75)
    xs = V[:, 0]
    mid = np.abs(xs - 75.0) < 1.3
    fin = V[mid]
    # keep only the ribbon's centre-line top points: the outline in the (y, z) plane
    ys, zs = fin[:, 1], fin[:, 2]

    fig, ax = plt.subplots(figsize=(9, 4.6), dpi=140)
    # part underside: the 35 degree base line from the standing edge
    yy = np.linspace(0, 40 * np.cos(np.radians(35)), 50)
    ax.fill_between(yy, yy * np.tan(np.radians(35)), yy * np.tan(np.radians(35)) + 6, color="#9aa4b1", alpha=0.55, lw=0)
    ax.plot(yy, yy * np.tan(np.radians(35)), color="#4b5563", lw=1.4)
    ax.text(-1.5, 3.4, "part: base face, 55\u00b0 overhang", color="#1f2937", fontsize=9, rotation=35)

    # split the output into pieces (fin ribbon, crossbar box, brim pads) using shared vertices
    tri = V[F]
    sel = np.all(np.abs(tri[:, :, 0] - 75.0) < 12.0, axis=1)   # middle fin, its crossbar and pads
    parent = list(range(len(V)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b, c in F[sel]:
        for x in (b, c):
            ra, rb = find(int(a)), find(int(x))
            if ra != rb:
                parent[rb] = ra
    roots = np.array([find(int(a)) for a in F[sel][:, 0]])
    from matplotlib.collections import PolyCollection
    from matplotlib.patches import Rectangle
    bars = []
    for r in np.unique(roots):
        pt = tri[sel][roots == r]
        zmax = pt[:, :, 2].max()
        y0, y1 = pt[:, :, 1].min(), pt[:, :, 1].max()
        if zmax <= st.brim_thickness + 1e-6:          # brim pad: one layer, drawn thicker so it shows
            ax.add_patch(Rectangle((y0, -0.15), y1 - y0, 0.6, color="#7c2d12"))
        elif len(np.unique(pt.reshape(-1, 3), axis=0)) <= 8:   # crossbar box
            ax.add_patch(Rectangle((y0, 0), y1 - y0, zmax, facecolor="#b45309", edgecolor="#7c2d12", lw=0.8, zorder=3))
            bars.append((y0 + y1) / 2)
        else:
            ax.add_collection(PolyCollection(pt[:, :, 1:3], facecolors="#f28c28", edgecolors="none", alpha=0.95))
    ax.plot([ys.min() - 1, ys.max() + 1], [0, 0], color="#111827", lw=1.2)
    ax.text(ys.max() + 6, -2.4, "build plate", fontsize=9, color="#111827")

    def note(xy, txt, xytext):
        ax.annotate(txt, xy=xy, xytext=xytext, fontsize=9, color="#111827",
                    arrowprops=dict(arrowstyle="-", color="#6b7280", lw=0.8))

    top_y = ys[zs == zs.max()][0]
    tip_y = ys[zs >= zs.max() - 1e-6]
    mid_y = ys.min() + (top_y - ys.min()) * 0.7
    note((mid_y, zs[np.argsort(np.abs(ys - mid_y))[:8]].max()), "other tips stop %.2f mm under the part" % st.contact_gap, (mid_y - 22, zs.max() + 7))
    y_first = ys.min() + st.tooth_ramp + st.tooth_tip / 2
    note((y_first, zs[np.abs(ys - y_first) < 0.4].max()), "first %d teeth touch the part (%.1f mm into it)" % (st.anchor_teeth, st.anchor_overlap), (ys.min() - 15, zs.max() + 3))
    half = st.tooth_ramp + st.tooth_tip / 2
    y_val = ys.min() + 2 * half + (st.tooth_pitch - 2 * half) / 2 + 3 * st.tooth_pitch
    note((y_val, zs[np.argsort(np.abs(ys - y_val))[:8]].max()), "valleys %.0f mm under the part" % st.relief, (y_val - 6, zs.max() * 0.85))
    note((ys.max(), zs.max() * 0.4), "straight back, down from the tip", (ys.max() + 2, zs.max() * 0.55))
    note((tip_y.mean(), zs.max()), "blunt %.0f mm tip, top %.0f %% left free" % (st.tip_length, st.top_cut * 100), (tip_y.mean() + 4, zs.max() + 4))
    bar_y = bars[0] if bars else tip_y.mean()
    note((bar_y, 2.5), "crossbar foot under the tip, %.0f mm high" % st.crossbar_height, (bar_y - 2, -4.6))
    note((ys.min() + 1.5, 0.3), "%.0f mm brim pad, one layer (drawn thicker)" % st.brim_width, (ys.min() - 14, -4.6))
    ax.set_xlim(ys.min() - 16, ys.max() + 24)
    ax.set_ylim(-6, zs.max() + 11)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("One fin, side view (real output for the 35° test box)", fontsize=11)
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    print("wrote", out, rep.summary())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "fin-profile.png")
