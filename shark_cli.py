#!/usr/bin/env python3
# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
#
# WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
"""Shark Support command line: make fins for an STL without Cura.

    python3 shark_cli.py part.stl                    -> part_fins.stl
    python3 shark_cli.py part.stl -o fins.stl --spacing 25 --merged both.stl
    python3 shark_cli.py --make-test-box box.stl     -> the 35 degree test box

The STL must already be placed the way you will print it (Z up, on the bed).
Import the fins file into PrusaSlicer / OrcaSlicer / Cura as a second part
at the same position (in Cura, untick "Ensure models are kept apart" and do
not arrange) - or use the Cura plugin, which places them for you.
Needs Python 3.8+ and numpy.
"""
import argparse
import json
import os
import sys
from dataclasses import fields

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "SharkSupport"))
import numpy as np  # noqa: E402
import shark_core as sc  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Shark-fin supports for STL files (" + sc.__version__ + ")")
    ap.add_argument("stl", nargs="?", help="input STL, already oriented for printing")
    ap.add_argument("-o", "--out", help="fins STL to write (default <input>_fins.stl)")
    ap.add_argument("--merged", help="also write part + fins as one STL")
    ap.add_argument("--settings", help="JSON file with any FinSettings values")
    ap.add_argument("--make-test-box", metavar="STL", help="write the tilted test box and exit")
    ap.add_argument("--tilt", type=float, default=35.0, help="tilt for --make-test-box (degrees)")
    ap.add_argument("--version", action="version", version="Shark Support " + sc.__version__)
    for fld in fields(sc.FinSettings):
        if fld.type in ("float", "int", float, int):
            ap.add_argument("--" + fld.name.replace("_", "-"), dest="opt_" + fld.name,
                            type=float, default=None, help=f"(default {fld.default})")
    ap.add_argument("--no-brim", action="store_true")
    ap.add_argument("--no-crossbar", action="store_true")
    ap.add_argument("--back", choices=["vertical", "slope", "round", "concave", "triangle"], default=None,
                    help="back edge: vertical (default, least plastic), slope (leans out, wider base), "
                         "round, or concave shark look ('triangle' = vertical, from 0.1.x)")
    a = ap.parse_args(argv)

    if a.make_test_box:
        v, f = sc.tilted_box(tilt_deg=a.tilt)
        sc.write_stl(a.make_test_box, v, f, "tilted test box")
        print("wrote", a.make_test_box)
        return 0
    if not a.stl:
        ap.error("give an STL (or --make-test-box)")

    d = {}
    if a.settings:
        with open(a.settings) as fh:
            d.update(json.load(fh))
    for k, v in vars(a).items():
        if k.startswith("opt_") and v is not None:
            d[k[4:]] = v
    if a.no_brim:
        d["brim"] = False
    if a.no_crossbar:
        d["crossbar"] = False
    if a.back:
        d["back_curve"] = {"vertical": "vertical", "triangle": "vertical", "slope": "slope",
                           "round": "ellipse", "concave": "concave"}[a.back]
    st = sc.FinSettings.from_dict(d)

    soup = sc.read_stl(a.stl)
    V, F, rep = sc.make_fins(soup, None, st)
    print(rep.summary())
    for n in rep.notes:
        print("note:", n)
    if not len(F):
        return 2
    out = a.out or os.path.splitext(a.stl)[0] + "_fins.stl"
    sc.write_stl(out, V, F)
    print("wrote", out)
    if a.merged:
        pv, pf = sc.weld(soup, None)
        sc.write_stl(a.merged, np.vstack([pv, V]), np.vstack([pf, F + len(pv)]))
        print("wrote", a.merged)
    return 0


if __name__ == "__main__":
    sys.exit(main())
