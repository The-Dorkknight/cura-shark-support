# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
#
# Shark Support for UltiMaker Cura - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
#
# Menu: Extensions > Shark Support (the same actions as the toolbar button).
from PyQt6.QtCore import QObject

from UM.Extension import Extension

from .SharkActions import SharkActions


class SharkSupportExtension(QObject, Extension):
    def __init__(self, parent=None) -> None:
        QObject.__init__(self, parent)
        Extension.__init__(self)
        self.actions = SharkActions.instance()
        self.setMenuName("Shark Support")
        self.addMenuItem("Auto: fins under all matching faces of the selection", self.actions.addFinsToSelection)
        self.addMenuItem("Pick a face (opens the toolbar tool)", self.actions.startPicking)
        self.addMenuItem("Settings...", self.actions.showDialog)
        self.addMenuItem("Remove all fins", self.actions.removeAllFins)
        self.addMenuItem("Run self-check", self.actions.runSelfCheck)
        self.addMenuItem("About", self.actions.showAbout)

    def setPluginId(self, plugin_id: str) -> None:
        super().setPluginId(plugin_id)
        self.actions.setPluginId(plugin_id)
