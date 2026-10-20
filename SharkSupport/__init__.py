# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
#
# Shark Support for UltiMaker Cura - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
#
# One plugin, two faces: a button in the left toolbar (tool) and Extensions > Shark Support (menu).
# The toolbar icon is an SVG with no fill attribute on its <svg> tag: Cura's icon loader adds its own
# fill there, and a second one makes the file invalid.


def getMetaData():
    return {
        "tool": {
            "name": "Shark Support",
            "description": "Shark-fin supports: pick a face to support, or Auto for all big tilted flat faces",
            "icon": "icons/shark_tool.svg",
            "tool_panel": "qml/SharkSupportTool.qml",
            "weight": 10,
        }
    }


def register(app):
    from . import SharkSupportExtension, SharkSupportTool
    return {
        "extension": SharkSupportExtension.SharkSupportExtension(),
        "tool": SharkSupportTool.SharkSupportTool(),
    }
