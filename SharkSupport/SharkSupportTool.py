# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
#
# Shark Support for UltiMaker Cura - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
#
# The shark-fin button in Cura's left toolbar (under move, scale, rotate, mirror, ...).
# Its panel: Pick face / Auto / Remove all / Settings. In pick mode a left click on the
# selected model's underside adds fins under that one flat face.
from typing import List, Optional

from UM.Application import Application
from UM.Event import Event, MouseEvent
from UM.Logger import Logger
from UM.Message import Message
from UM.Scene.Selection import Selection
from UM.Tool import Tool

from .SharkActions import SharkActions


class SharkSupportTool(Tool):
    instances: List["SharkSupportTool"] = []

    def __init__(self) -> None:
        super().__init__()
        self.actions = SharkActions.instance()
        self._pick_mode = False
        self._picking_pass = None
        self._hint: Optional[Message] = None
        self.setExposedProperties("PickMode", "Status", "Version")
        self.actions.statusChanged.connect(self._onStatusChanged)
        SharkSupportTool.instances.append(self)

    def setPluginId(self, plugin_id: str) -> None:
        super().setPluginId(plugin_id)
        self.actions.setPluginId(plugin_id)

    # ---------------------------------------------------------------- properties for the panel
    def getPickMode(self) -> bool:
        return self._pick_mode

    def setPickMode(self, value) -> None:
        value = bool(value)
        if value == self._pick_mode:
            return
        self._pick_mode = value
        if value:
            self._hint = Message("Click the underside face you want supported. Click it again after changing "
                                 "settings to redo it. Press Pick face again to stop.",
                                 title="Shark Support: pick a face", lifetime=0, dismissable=True)
            self._hint.show()
        elif self._hint is not None:
            self._hint.hide()
            self._hint = None
        self.propertyChanged.emit()

    def getStatus(self) -> str:
        return self.actions.status

    def getVersion(self) -> str:
        return self.actions.version

    def _onStatusChanged(self) -> None:
        self.propertyChanged.emit()

    # ---------------------------------------------------------------- panel actions
    def autoFins(self) -> None:
        self.setPickMode(False)
        self.actions.addFinsToSelection()

    def removeFins(self) -> None:
        self.actions.removeAllFins()

    def openSettings(self) -> None:
        self.actions.showDialog()

    # ---------------------------------------------------------------- rendering passes (Cura 5.11+)
    def getRequiredExtraRenderingPasses(self) -> list:
        return ["picking_selected"]

    def _pickedPosition(self, event):
        """World position under the mouse, on a selected object. Works on old and new Cura."""
        renderer = Application.getInstance().getRenderer()
        pp = renderer.getRenderPass("picking_selected")
        if pp is not None:
            return pp.getPickedPosition(event.x, event.y)
        # Cura 5.0-5.x without the shared pass: render one on demand, like Cura's own support blocker did
        from cura.PickingPass import PickingPass
        camera = self._controller.getScene().getActiveCamera()
        pp = PickingPass(camera.getViewportWidth(), camera.getViewportHeight())
        pp.render()
        return pp.getPickedPosition(event.x, event.y)

    @staticmethod
    def _selectedAncestor(node):
        n = node
        while n is not None:
            if Selection.isSelected(n):
                return True
            n = n.getParent()
        return False

    def event(self, event) -> bool:
        super().event(event)
        if event.type == Event.ToolDeactivateEvent:
            self.setPickMode(False)
            return False
        if not self._pick_mode:
            return False
        if event.type != Event.MousePressEvent or MouseEvent.LeftButton not in event.buttons:
            return False
        if not self._controller.getToolsEnabled():
            return False
        if self._selection_pass is None:
            self._selection_pass = Application.getInstance().getRenderer().getRenderPass("selection")
        if self._selection_pass is None:
            return False
        node = self._controller.getScene().findObject(self._selection_pass.getIdAtPosition(event.x, event.y))
        if node is None or self.actions._isFinNode(node):
            return False
        if not self._selectedAncestor(node):
            return False          # let Cura select it first; the next click picks the face
        try:
            pos = self._pickedPosition(event)
        except Exception:  # noqa: BLE001
            Logger.logException("w", "Shark Support: could not read the clicked position")
            return False
        if pos is None:
            return False
        self.actions.addFinsAtPoint(node, pos)
        return True
