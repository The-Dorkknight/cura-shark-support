# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
#
# TEST-ONLY plugin. Not installed by the installer. It drives Shark Support inside a
# running Cura (used in development under Xvfb): sets up a printer if none exists,
# loads the test box, selects it, adds fins, opens the dialog, runs the self-check,
# tries support-mesh mode and removal, and writes "HARNESS:" lines to cura.log.
# Set SHARK_HARNESS_STL to the STL to load.


def getMetaData():
    return {}


def register(app):
    from . import Harness
    return {"extension": Harness.Harness()}
