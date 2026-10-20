# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""One place for the package metadata used by the installer and the .curapackage builder."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_ID = "SharkSupport"
PLUGIN_DIR = os.path.join(ROOT, PLUGIN_ID)


def plugin_version() -> str:
    with open(os.path.join(PLUGIN_DIR, "plugin.json"), encoding="utf-8") as fh:
        return json.load(fh)["version"]


def package_json() -> dict:
    """What Cura reads from a .curapackage (and keeps in packages.json once installed)."""
    with open(os.path.join(PLUGIN_DIR, "plugin.json"), encoding="utf-8") as fh:
        pj = json.load(fh)
    return {
        "package_id": PLUGIN_ID,
        "package_type": "plugin",
        "display_name": pj["name"],
        "description": pj["description"],
        "package_version": pj["version"],
        "sdk_version": 8,
        "sdk_version_semver": "8.0.0",
        "website": "https://github.com/The-Dorkknight/cura-shark-support",
        "author": {
            "author_id": "The-Dorkknight",
            "display_name": "Matthew Armstrong",
            "email": "The-Dorkknight@users.noreply.github.com",
            "website": "https://github.com/The-Dorkknight",
        },
        "tags": ["support", "supports", "overhang"],
    }


def plugin_files():
    """(relative path, absolute path) of every file that belongs in the plugin folder."""
    out = []
    for base, dirs, files in os.walk(PLUGIN_DIR):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                continue
            ap = os.path.join(base, f)
            out.append((os.path.relpath(ap, PLUGIN_DIR).replace(os.sep, "/"), ap))
    return sorted(out)
