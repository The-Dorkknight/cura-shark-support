# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
# TEST-ONLY driver, see __init__.py.
#
# Writes "HARNESS:" lines to the log. Two lines ask the outside script to act:
#   "HARNESS: shot <name>"        take a screenshot now
#   "HARNESS: click <x> <y>"      left-click at that window pixel (xdotool), a real mouse click
import os

import numpy
from PyQt6.QtCore import QObject, QTimer, QUrl

from UM.Event import MouseEvent
from UM.Extension import Extension
from UM.Logger import Logger
from UM.Math.Vector import Vector
from UM.PluginRegistry import PluginRegistry
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.Scene.Selection import Selection

from cura.CuraApplication import CuraApplication
from cura.Scene.CuraSceneNode import CuraSceneNode

STEP_MS = int(os.environ.get("SHARK_HARNESS_STEP_MS", "2500"))


def say(msg):
    Logger.log("i", "HARNESS: %s", msg)


class Harness(QObject, Extension):
    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        Extension.__init__(self)
        self._app = CuraApplication.getInstance()
        self._steps = [self.package, self.machine, self.load, self.activate_tool, self.aim, self.wait_click,
                       self.check_pick, self.shot_pick, self.pick_again, self.check_replace, self.auto,
                       self.check_auto, self.view, self.dialog, self.selfcheck, self.support_mode, self.remove,
                       self.done]
        self._model = None
        self._app.engineCreatedSignal.connect(self._start)  # bound method: Uranium signals hold weak refs

    def _start(self):
        QTimer.singleShot(STEP_MS * 2, self.next)

    def next(self):
        if not self._steps:
            return
        step = self._steps.pop(0)
        try:
            say("step " + step.__name__)
            step()
        except Exception as ex:  # noqa: BLE001
            Logger.logException("e", "HARNESS step failed")
            say("FAIL %s %r" % (step.__name__, ex))
        QTimer.singleShot(STEP_MS, self.next)

    def actions(self):
        return PluginRegistry.getInstance().getPluginObject("SharkSupport").actions

    def tool(self):
        return self._app.getController().getTool("SharkSupport")

    def nodes(self):
        root = self._app.getController().getScene().getRoot()
        return [n for n in DepthFirstIterator(root) if isinstance(n, CuraSceneNode) and n.getMeshData()]

    def fins(self):
        return [n for n in self.nodes() if n.getName().startswith("Shark fins")]

    def package(self):
        pm = self._app.getPackageManager()
        cp = os.environ.get("SHARK_HARNESS_CURAPACKAGE")
        if cp:
            pid = pm.installPackage(cp)
            say("scheduled curapackage install: %s" % pid)
            self._steps = [self.done]
            return
        say(("PASS" if pm.isPackageInstalled("SharkSupport") else "FAIL") +
            " Cura's package manager lists SharkSupport as installed")

    def machine(self):
        if self._app.getGlobalContainerStack() is None:
            self._app.getMachineManager().addMachine("elegoo_neptune_4")
        st = self._app.getGlobalContainerStack()
        say("printer %s" % (st.getName() if st else None))

    def load(self):
        stl = os.environ.get("SHARK_HARNESS_STL")
        self._app.readLocalFile(QUrl.fromLocalFile(stl), add_to_recent_files=False)
        say("loading %s" % stl)

    def activate_tool(self):
        w = self._app.getMainWindow()
        if w is not None:
            w.setGeometry(0, 0, 1600, 1000)
        self._model = [n for n in self.nodes() if not n.getName().startswith("Shark fins")][0]
        Selection.clear()
        Selection.add(self._model)
        cam = self._app.getController().getScene().getActiveCamera()
        cam.setPosition(Vector(-120, 40, -330))   # low and behind: looking at the tilted underside
        cam.lookAt(Vector(0, 12, 0))
        tools = self._app.getController().getAllTools()
        say(("PASS" if "SharkSupport" in tools else "FAIL") + " toolbar tool registered")
        self._app.getController().setActiveTool("SharkSupport")
        t = self._app.getController().getActiveTool()
        say(("PASS" if t is not None and t.getPluginId() == "SharkSupport" else "FAIL") + " toolbar tool active")

    def aim(self):
        """Find the window pixel of a point in the middle of the underside face, and ask for a real click."""
        a = self.actions()
        soup = a._worldSoupZup([self._model])
        import importlib; sc = importlib.import_module("SharkSupport.shark_core")
        b = sc.FinBuilder(soup, None)
        n, area = sc.face_normals_areas(b.v, b.f)
        i = int(numpy.argmin(n[:, 2] - 0.0 * area))
        ids = [k for k in range(len(b.f)) if numpy.allclose(n[k], n[i], atol=1e-3)]
        centre = b.v[b.f[ids]].reshape(-1, 3).mean(axis=0)            # printer frame, Z up
        p = Vector(float(centre[0]), float(centre[2]), float(-centre[1]))  # scene frame
        cam = self._app.getController().getScene().getActiveCamera()
        x, y = cam.project(p)
        win = self._app.getMainWindow()
        W, H = win.width(), win.height()
        sel = self._app.getRenderer().getRenderPass("selection")
        best = None
        for sy in (1, -1):
            nx, ny = x, sy * y
            if self._app.getController().getScene().findObject(sel.getIdAtPosition(nx, ny)) is self._model:
                best = (nx, ny)
                break
        if best is None:
            say("FAIL could not aim at the model (projected %.3f %.3f)" % (x, y))
            return
        px = int(round((best[0] + 1) / 2 * W))
        py = int(round((best[1] + 1) / 2 * H))
        self.tool().setPickMode(True)
        say("pick mode %s" % self.tool().getPickMode())
        say("click %d %d" % (px, py))

    def wait_click(self):
        say("waited for the click")

    def check_pick(self):
        f = self.fins()
        ok = len(f) == 1 and getattr(f[0], "_shark_face", None) is not None
        say(("PASS" if ok else "FAIL") + " a real mouse click on the underside made fins for that face (%d fin objects)" % len(f))
        if f:
            say("status: %s" % self.actions().status)

    def shot_pick(self):
        say("shot pick")

    def pick_again(self):
        say("click again")   # the outside script repeats the last click

    def check_replace(self):
        f = self.fins()
        say(("PASS" if len(f) == 1 else "FAIL") + " picking the same face again replaces its fins (%d)" % len(f))
        self.tool().setPickMode(False)

    def auto(self):
        self.tool().autoFins()

    def check_auto(self):
        f = self.fins()
        ok = len(f) == 1 and getattr(f[0], "_shark_face", 1) is None
        say(("PASS" if ok else "FAIL") + " Auto replaced the picked fins with automatic ones (%d)" % len(f))
        if f:
            fb, mb = f[0].getBoundingBox(), self._model.getBoundingBox()
            stack = f[0].callDecoration("getStack")
            say("fin infill %s support %s union %s" % (
                stack.getProperty("infill_sparse_density", "value"),
                stack.getProperty("support_enable", "value"),
                stack.getProperty("meshfix_union_all", "value")))
            inside = (fb.minimum.x >= mb.minimum.x - 6 and fb.maximum.x <= mb.maximum.x + 6 and fb.minimum.y >= -0.01)
            say(("PASS" if inside else "FAIL") + " fins sit under the model on the plate")

    def view(self):
        cam = self._app.getController().getScene().getActiveCamera()
        cam.setPosition(Vector(-260, 170, -330))
        cam.lookAt(Vector(0, 10, -5))
        say("shot scene")

    def dialog(self):
        self.actions().showDialog()
        say("shot dialog")

    def selfcheck(self):
        self.actions().runSelfCheck()

    def support_mode(self):
        a = self.actions()
        a.setValue("as_support_mesh", "true")
        Selection.clear()
        Selection.add(self._model)
        a.addFinsToSelection()
        f = self.fins()
        say(("PASS" if len(f) == 1 and f[0].isSupportMesh() else "FAIL") + " support-mesh mode")
        a.setValue("as_support_mesh", "false")

    def remove(self):
        self.tool().removeFins()
        say(("PASS" if not self.fins() else "FAIL") + " remove all fins")
        Selection.clear()
        Selection.add(self._model)
        self.actions().addFinsToSelection()

    def done(self):
        say("DONE")
