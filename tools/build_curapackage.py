#!/usr/bin/env python3
# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Build dist/SharkSupport-<version>.curapackage (drag it onto the Cura window to install)."""
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import package_info as pi  # noqa: E402


def build(out_dir=None) -> str:
    out_dir = out_dir or os.path.join(pi.ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "%s-%s-wip.curapackage" % (pi.PLUGIN_ID, pi.plugin_version()))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("package.json", json.dumps(pi.package_json(), indent=4))
        lic = os.path.join(pi.ROOT, "LICENSE.md")
        if os.path.exists(lic):
            z.write(lic, "LICENSE")
        for rel, ap in pi.plugin_files():
            z.write(ap, "files/plugins/%s/%s" % (pi.PLUGIN_ID, rel))
    return path


if __name__ == "__main__":
    print("wrote", build(sys.argv[1] if len(sys.argv) > 1 else None))
