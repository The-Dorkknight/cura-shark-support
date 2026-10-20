# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Side view of the extrusions in a thin slice of a G-code file, to see fins vs part.

python3 tools/gcode_side_view.py file.gcode out.png --x 117 --width 2 [--title ...]
Plots every extruding move whose X lies within [x - width/2, x + width/2], as Y against Z.
Handles absolute or relative E (M82/M83) and G92 resets. Needs matplotlib for the picture.
"""
import argparse
import re


def moves(path):
    x = y = z = e = 0.0
    rel_e = False
    num = re.compile(r"([XYZEF])(-?\d*\.?\d+)")
    with open(path, errors="replace") as fh:
        for line in fh:
            line = line.split(";", 1)[0].strip()
            if not line:
                continue
            if line.startswith("M83"):
                rel_e = True
            elif line.startswith("M82"):
                rel_e = False
            elif line.startswith("G92"):
                for k, v in num.findall(line):
                    if k == "E":
                        e = float(v)
            elif line.startswith(("G0", "G1")):
                d = dict((k, float(v)) for k, v in num.findall(line))
                nx, ny, nz = d.get("X", x), d.get("Y", y), d.get("Z", z)
                extr = False
                if "E" in d:
                    ne = d["E"] if not rel_e else e + d["E"]
                    extr = ne > e + 1e-6 and (nx != x or ny != y)
                    e = ne
                yield x, y, z, nx, ny, nz, extr
                x, y, z = nx, ny, nz


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("gcode")
    ap.add_argument("out")
    ap.add_argument("--x", type=float, required=True)
    ap.add_argument("--width", type=float, default=2.0)
    ap.add_argument("--title", default="")
    a = ap.parse_args(argv)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    lo, hi = a.x - a.width / 2, a.x + a.width / 2
    segs = []
    for x0, y0, z0, x1, y1, z1, ex in moves(a.gcode):
        if not ex or max(x0, x1) < lo or min(x0, x1) > hi:
            continue
        if abs(x1 - x0) < 1e-9:
            segs.append([(y0, z1), (y1, z1)])
            continue
        # clip the move to the slab so long lines across the part show as short dashes
        t0 = max(0.0, min(1.0, (lo - x0) / (x1 - x0)))
        t1 = max(0.0, min(1.0, (hi - x0) / (x1 - x0)))
        ya, yb = y0 + (y1 - y0) * t0, y0 + (y1 - y0) * t1
        if abs(yb - ya) < 0.05:
            yb = ya + 0.05
        segs.append([(ya, z1), (yb, z1)])
    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=140)
    ax.add_collection(LineCollection(segs, colors="#1f2937", linewidths=0.6))
    ax.autoscale()
    ax.set_aspect("equal")
    ax.set_xlabel("Y (mm)")
    ax.set_ylabel("Z (mm)")
    ax.set_title(a.title or "Extrusions with X in [%.1f, %.1f]" % (lo, hi), fontsize=10)
    fig.tight_layout()
    fig.savefig(a.out, facecolor="white")
    print("wrote", a.out, len(segs), "segments")


if __name__ == "__main__":
    main()
