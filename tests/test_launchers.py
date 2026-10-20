# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""The double-click launchers exist, are executable (POSIX) and have the right line endings."""
import os
import stat
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_launchers():
    for name in ("Install-Linux.sh", "Install-Mac.command", "Install-Windows.bat"):
        p = os.path.join(ROOT, name)
        assert os.path.isfile(p), name
        data = open(p, "rb").read()
        assert b"install.py" in data, name
        if name.endswith(".bat"):
            assert data.count(b"\r\n") == data.count(b"\n"), "bat must use CRLF"
        else:
            assert b"\r\n" not in data, name + " must use LF"
            assert data.startswith(b"#!/bin/sh"), name
            if os.name == "posix":
                assert os.stat(p).st_mode & stat.S_IXUSR, name + " not executable"


def test_toolbar_icon_svg_is_safe():
    """Cura's icon loader injects fill="..." into the <svg> tag: the file must not have one already."""
    import re
    import xml.etree.ElementTree as ET
    p = os.path.join(ROOT, "SharkSupport", "icons", "shark_tool.svg")
    data = open(p, "rb").read()
    tag = re.search(rb"<svg [^>]*>", data).group(0)
    assert b"fill=" not in tag, "fill attribute on <svg>"
    ET.fromstring(data.replace(b"<svg ", b'<svg fill="#123456" '))   # still valid XML after Cura's edit


if __name__ == "__main__":
    fails = 0
    for n, fn in list(globals().items()):
        if n.startswith("test_"):
            try:
                fn()
                print("PASS", n)
            except AssertionError as ex:
                fails += 1
                print("FAIL", n, ex)
    print("RESULT:", "PASS" if not fails else "FAIL")
    sys.exit(1 if fails else 0)
