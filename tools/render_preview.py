# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Draw the part (grey) and its fins (orange) to a PNG, from real geometry.

Usage:  python3 tools/render_preview.py part.stl fins.stl out.png [--view 25 -60] [--side]
Needs matplotlib (only for these pictures; the plugin itself does not).
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "SharkSupport"))
import shark_core as sc  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("part")
    ap.add_argument("fins")
    ap.add_argument("out")
    ap.add_argument("--view", nargs=2, type=float, default=[22, -58])
    ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--title", default="")
    ap.add_argument("--part-alpha", type=float, default=0.35)
    a = ap.parse_args(argv)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    part = sc.read_stl(a.part).reshape(-1, 3, 3)
    fins = sc.read_stl(a.fins).reshape(-1, 3, 3)
    light = np.array([0.3, -0.5, 0.8])
    light /= np.linalg.norm(light)

    def shade(tris, rgb):
        n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        k = 0.45 + 0.55 * np.clip(n @ light, 0, 1)
        return np.clip(np.outer(k, rgb), 0, 1)

    fig = plt.figure(figsize=(8, 5.2), dpi=130)
    ax = fig.add_subplot(111, projection="3d")
    pc = Poly3DCollection(part, facecolors=shade(part, (0.62, 0.66, 0.72)), edgecolors="none", alpha=a.part_alpha)
    fc = Poly3DCollection(fins, facecolors=shade(fins, (0.95, 0.48, 0.12)), edgecolors=(0.35, 0.15, 0.0, 0.25), linewidths=0.15)
    ax.add_collection3d(fc)
    ax.add_collection3d(pc)
    allp = np.vstack([part.reshape(-1, 3), fins.reshape(-1, 3)])
    lo, hi = allp.min(0), allp.max(0)
    c = (lo + hi) / 2
    r = (hi - lo).max() / 2 / a.zoom
    ax.set_xlim(c[0] - r, c[0] + r)
    ax.set_ylim(c[1] - r, c[1] + r)
    ax.set_zlim(0, 2 * r * 0.6)
    ax.set_box_aspect((1, 1, 0.6))
    ax.view_init(*a.view)
    ax.set_axis_off()
    # build plate
    gx = np.array([lo[0] - 5, hi[0] + 5])
    gy = np.array([lo[1] - 5, hi[1] + 5])
    X, Y = np.meshgrid(gx, gy)
    ax.plot_surface(X, Y, np.zeros_like(X), color=(0.85, 0.87, 0.9), alpha=0.5, shade=False)
    if a.title:
        ax.set_title(a.title, fontsize=11)
    plt.subplots_adjust(0, 0, 1, 0.95)
    fig.savefig(a.out, dpi=130, facecolor="white")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
