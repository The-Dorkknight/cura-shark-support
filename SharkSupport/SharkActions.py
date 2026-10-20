# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
#
# Shark Support for UltiMaker Cura - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
#
# Everything the menu (SharkSupportExtension), the toolbar tool (SharkSupportTool) and the settings
# dialog share: settings, making fins (automatic or for one picked face), removing them, self-check.
import json
import os
import tempfile
import time
import traceback
from typing import List, Optional, Tuple

import numpy

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from UM.Logger import Logger
from UM.Message import Message
from UM.Math.Vector import Vector
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Operations.GroupedOperation import GroupedOperation
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from UM.Operations.TranslateOperation import TranslateOperation
from UM.PluginRegistry import PluginRegistry
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.Scene.Selection import Selection
from UM.Settings.SettingInstance import SettingInstance

from cura.CuraApplication import CuraApplication
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from cura.Scene.CuraSceneNode import CuraSceneNode
from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator

from . import shark_core

VERSION = shark_core.__version__
BUILD_DATE = "2026-10-19 21:40"
FIN_NODE_PREFIX = "Shark fins"
PREF_SETTINGS = "sharksupport/settings_v3"   # v3 (0.2.0): blunt cut tip, straight back
PREF_OPTIONS = "sharksupport/options"
PREF_WELCOMED = "sharksupport/welcomed_" + VERSION

# options that are not geometry (kept apart from FinSettings)
DEFAULT_OPTIONS = {
    "as_support_mesh": False,       # False: solid little part (default). True: Cura support mesh
    "brim_from_first_layer": True,  # brim pad thickness = the profile's first layer height
    "disable_model_support": True,  # turn normal support off for the model the fins are made for
}

# what the dialog shows: (key, label, unit, tooltip)
DIALOG_FIELDS = [
    ("min_angle", "Overhang angle from", "deg", "Faces at least this far from vertical get fins (Cura's 0 = wall, 90 = ceiling)."),
    ("max_angle", "Overhang angle to", "deg", "... and at most this far."),
    ("min_face_area", "Smallest face", "mm2", "Faces smaller than this are left alone."),
    ("min_reach", "Shortest slope", "mm", "Faces that reach less than this along the slope are left alone."),
    ("spacing", "Fin spacing", "mm", "Distance between fins across the face."),
    ("edge_margin", "Side margin", "mm", "Keep fins this far in from the face's side edges."),
    ("min_fin_height", "Start height", "mm", "Fins start where the face is this high above the bed."),
    ("thick_base", "Thickness at bed", "mm", "Fin thickness at the bottom."),
    ("thick_top", "Thickness at top", "mm", "Fin thickness at the top edge."),
    ("relief", "Gap between teeth", "mm", "How far below the part the fin edge sits between teeth."),
    ("tooth_pitch", "Tooth spacing", "mm", "Distance between tooth tips."),
    ("tooth_tip", "Tooth tip length", "mm", "Flat length of each tip."),
    ("contact_gap", "Tip gap", "mm", "All other tips stop this far below the part."),
    ("anchor_teeth", "Anchor teeth", "count", "The first teeth from the fin's low end that really touch the part (0 = none)."),
    ("anchor_overlap", "Anchor overlap", "mm", "How far the anchor teeth reach into the part, so they bond slightly."),
    ("top_cut_pct", "Top left free", "%", "The fin stops this far below the top of the face; the part bridges the rest."),
    ("tip_length", "Blunt tip length", "mm", "The fin's flat top: no layer of the fin is shorter than this."),
    ("back_lean", "Back lean", "deg", "Only with 'Lean the back out': angle of the back edge from vertical."),
    ("crossbar_fraction", "Crossbar length", "x fin", "Crossbar length as a fraction of the fin's footprint length."),
    ("crossbar_height", "Crossbar height", "mm", "Height of the crossbar foot."),
    ("brim_width", "Brim width", "mm", "Width of the one-layer pad around each fin and crossbar."),
    ("brim_thickness", "Brim thickness", "mm", "Used when 'brim = first layer height' is off."),
]
DIALOG_BOOLS = [
    ("crossbar", "Crossbar foot"),
    ("brim", "Brim pad"),
    ("slope_back", "Lean the back out to the bed (wider base, more plastic)"),
    ("brim_from_first_layer", "Brim thickness = first layer height"),
    ("disable_model_support", "Turn off normal support for the model"),
    ("as_support_mesh", "Print fins as a Cura support mesh (experimental, uses your support density)"),
]


class SharkActions(QObject):
    """One shared instance: SharkActions.instance()."""
    settingsChanged = pyqtSignal()
    statusChanged = pyqtSignal()
    _instance = None

    @classmethod
    def instance(cls) -> "SharkActions":
        if cls._instance is None:
            cls._instance = SharkActions()
        return cls._instance

    def __init__(self, parent=None) -> None:
        QObject.__init__(self, parent)
        self._app = CuraApplication.getInstance()
        self._dialog = None
        self._plugin_id = "SharkSupport"
        self._status = "Select a model, then pick a face or press Auto."
        prefs = self._app.getPreferences()
        prefs.addPreference(PREF_SETTINGS, "{}")
        prefs.addPreference(PREF_OPTIONS, "{}")
        prefs.addPreference(PREF_WELCOMED, False)
        self._app.engineCreatedSignal.connect(self._onEngineCreated)
        Logger.log("i", "Shark Support %s (built %s) loaded", VERSION, BUILD_DATE)

    def setPluginId(self, plugin_id: str) -> None:
        self._plugin_id = plugin_id

    def pluginDir(self) -> str:
        return PluginRegistry.getInstance().getPluginPath(self._plugin_id) or os.path.dirname(os.path.abspath(__file__))

    # ------------------------------------------------------------ settings
    def _settings(self) -> shark_core.FinSettings:
        try:
            d = json.loads(self._app.getPreferences().getValue(PREF_SETTINGS) or "{}")
        except (ValueError, TypeError):
            d = {}
        return shark_core.FinSettings.from_dict(d)

    def _saveSettings(self, s: shark_core.FinSettings) -> None:
        self._app.getPreferences().setValue(PREF_SETTINGS, json.dumps(s.to_dict()))

    def _options(self) -> dict:
        o = dict(DEFAULT_OPTIONS)
        try:
            o.update(json.loads(self._app.getPreferences().getValue(PREF_OPTIONS) or "{}"))
        except (ValueError, TypeError):
            pass
        return o

    def _saveOptions(self, o: dict) -> None:
        self._app.getPreferences().setValue(PREF_OPTIONS, json.dumps(o))

    # ------------------------------------------------------------ QML bridge
    @pyqtProperty(str, constant=True)
    def version(self) -> str:
        return VERSION

    @pyqtProperty(str, constant=True)
    def buildDate(self) -> str:
        return BUILD_DATE

    @pyqtProperty(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    def _setStatus(self, text: str) -> None:
        self._status = text
        self.statusChanged.emit()

    @pyqtProperty("QVariantList", constant=True)
    def fields(self):
        return [{"key": k, "label": l, "unit": u, "tip": t} for k, l, u, t in DIALOG_FIELDS]

    @pyqtProperty("QVariantList", constant=True)
    def switches(self):
        return [{"key": k, "label": l} for k, l in DIALOG_BOOLS]

    @pyqtSlot(str, result=str)
    def getValue(self, key: str) -> str:
        s = self._settings()
        if key == "slope_back":
            return "true" if s.back_curve == "slope" else "false"
        if key == "top_cut_pct":
            return ("%.1f" % (s.top_cut * 100)).rstrip("0").rstrip(".")
        if key in DEFAULT_OPTIONS:
            return "true" if self._options().get(key) else "false"
        v = getattr(s, key, "")
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, float):
            return ("%.3f" % v).rstrip("0").rstrip(".")
        return str(v)

    @pyqtSlot(str, str)
    def setValue(self, key: str, value: str) -> None:
        if key in DEFAULT_OPTIONS:
            o = self._options()
            o[key] = str(value).lower() == "true"
            self._saveOptions(o)
            return
        s = self._settings()
        if key == "slope_back":
            s.back_curve = "slope" if str(value).lower() == "true" else "vertical"
        elif key == "top_cut_pct":
            try:
                s.top_cut = max(0.0, min(90.0, float(value))) / 100.0
            except ValueError:
                return
        else:
            s = shark_core.FinSettings.from_dict(dict(s.to_dict(), **{key: value}))
        self._saveSettings(s)

    @pyqtSlot()
    def resetDefaults(self) -> None:
        self._saveSettings(shark_core.FinSettings())
        self._saveOptions(dict(DEFAULT_OPTIONS))
        self.settingsChanged.emit()
        self._setStatus("Settings back to defaults.")

    @pyqtSlot()
    def addFins(self) -> None:
        self.addFinsToSelection()

    @pyqtSlot()
    def startPicking(self) -> None:
        """Dialog button: switch to the toolbar tool in face-picking mode."""
        tool = PluginRegistry.getInstance().getPluginObject(self._plugin_id)
        try:
            self._app.getController().setActiveTool(self._plugin_id)
            from .SharkSupportTool import SharkSupportTool
            for t in SharkSupportTool.instances:
                t.setPickMode(True)
        except Exception:  # noqa: BLE001
            Logger.logException("w", "Shark Support: could not start face picking")

    @pyqtSlot()
    def removeFins(self) -> None:
        self.removeAllFins()

    # ------------------------------------------------------------ menu actions
    def showDialog(self) -> None:
        if self._dialog is None:
            plugin_dir = self.pluginDir()
            path = os.path.join(plugin_dir, "qml", "SharkSupportDialog.qml")
            self._dialog = self._app.createQmlComponent(path, {"manager": self})
            if self._dialog is None:
                Logger.log("e", "Shark Support: could not create the settings dialog from %s", path)
                self._message("The settings dialog failed to open. Your settings still work from the menu; "
                              "please report this with cura.log.", Message.MessageType.ERROR)
                return
        self.settingsChanged.emit()
        self._dialog.show()

    def showAbout(self) -> None:
        self._message(
            f"Shark Support {VERSION} (built {BUILD_DATE})\n"
            "Copyright Matthew Armstrong (https://github.com/The-Dorkknight)\n"
            "Source-available under the PolyForm Noncommercial License 1.0.0. No warranty.\n"
            "WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN.",
            Message.MessageType.NEUTRAL, title="About Shark Support")

    def _onEngineCreated(self) -> None:
        # Logged again here because Cura's file logger may not be running yet when plugins load.
        # The installer looks for this line in cura.log and for the marker file below.
        Logger.log("i", "Shark Support %s (built %s) loaded", VERSION, BUILD_DATE)
        try:
            marker = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shark_loaded")
            with open(marker, "w") as fh:
                fh.write("%s %s %f\n" % (VERSION, BUILD_DATE, time.time()))
        except OSError:
            pass
        prefs = self._app.getPreferences()
        if not prefs.getValue(PREF_WELCOMED):
            prefs.setValue(PREF_WELCOMED, True)
            self._message("Shark Support is installed. Select a model, then click the shark-fin button in the left "
                          "toolbar (under move, scale and rotate): pick a face, or press Auto.",
                          Message.MessageType.POSITIVE, title="Shark Support " + VERSION)

    def _message(self, text: str, kind=Message.MessageType.NEUTRAL, title: str = "Shark Support") -> None:
        Message(text, title=title, message_type=kind, lifetime=20).show()

    # ------------------------------------------------------------ geometry in/out
    @staticmethod
    def _isFinNode(node) -> bool:
        return isinstance(node, CuraSceneNode) and (node.getName() or "").startswith(FIN_NODE_PREFIX)

    def _selectedMeshes(self) -> List[CuraSceneNode]:
        out = []
        for sel in Selection.getAllSelectedObjects():
            for node in DepthFirstIterator(sel):
                if not isinstance(node, CuraSceneNode) or self._isFinNode(node):
                    continue
                if node.getMeshData() is None or not node.callDecoration("isSliceable"):
                    continue
                if node.callDecoration("isNonPrintingMesh"):
                    continue
                if node not in out:
                    out.append(node)
        return out

    @staticmethod
    def _worldSoupZup(nodes) -> numpy.ndarray:
        """All triangles of the nodes, printer frame (Z up, mm)."""
        parts = []
        for node in nodes:
            md = node.getMeshData().getTransformed(node.getWorldTransformation())
            v = numpy.asarray(md.getVertices(), dtype=numpy.float64)
            idx = md.getIndices()
            tri = v[numpy.asarray(idx).reshape(-1)] if idx is not None else v
            parts.append(tri)
        soup = numpy.vstack(parts)
        # Cura scene: x right, y up, z towards the front. Printer: x, y = -z, z = y
        return numpy.column_stack([soup[:, 0], -soup[:, 2], soup[:, 1]])

    @staticmethod
    def _sceneFromZup(v: numpy.ndarray) -> numpy.ndarray:
        return numpy.column_stack([v[:, 0], v[:, 2], -v[:, 1]])

    def _firstLayer(self) -> Optional[float]:
        stack = self._app.getGlobalContainerStack()
        if stack is None:
            return None
        try:
            return float(stack.getProperty("layer_height_0", "value"))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _setNodeSetting(node, key: str, value) -> bool:
        stack = node.callDecoration("getStack")
        if stack is None:
            return False
        settings = stack.getTop()
        definition = stack.getSettingDefinition(key)
        if definition is None:
            Logger.log("w", "Shark Support: this Cura has no setting %s", key)
            return False
        if settings.getInstance(key) is None:
            inst = SettingInstance(definition, settings)
            inst.setProperty("value", value)
            inst.resetState()
            settings.addInstance(inst)
        else:
            settings.setProperty(key, "value", value)
        # Cura's per-object decorator caches flags such as "is support mesh" (used for drawing and
        # the build-volume checks) and only refreshes them when it hears about a change.
        try:
            for dec in node.getDecorators():
                if hasattr(dec, "_onSettingChanged"):
                    dec._onSettingChanged(key, "value")
        except Exception:  # noqa: BLE001
            Logger.logException("w", "Shark Support: could not refresh flags after setting %s", key)
        return True

    def _buildFinNode(self, V: numpy.ndarray, F: numpy.ndarray, name: str, as_support: bool,
                      model_id: str = "", face_key=None) -> CuraSceneNode:
        sv = self._sceneFromZup(V)
        lo, hi = sv.min(axis=0), sv.max(axis=0)
        centre = numpy.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2])
        mb = MeshBuilder()
        mb.setVertices((sv - centre).astype(numpy.float32))
        mb.setIndices(F.astype(numpy.int32))
        mb.calculateNormals()
        node = CuraSceneNode()
        node.setName(name)
        node._shark_model = model_id          # which model these fins belong to
        node._shark_face = face_key           # None = automatic (all faces)
        node.setSelectable(True)
        node.setCalculateBoundingBox(True)
        node.setMeshData(mb.build())
        node.calculateBoundingBoxMesh()
        plate = self._app.getMultiBuildPlateModel().activeBuildPlate
        node.addDecorator(BuildPlateDecorator(plate))
        node.addDecorator(SliceableObjectDecorator())
        node.setPosition(Vector(float(centre[0]), float(centre[1]), float(centre[2])))
        if as_support:
            self._setNodeSetting(node, "support_mesh", True)
            self._setNodeSetting(node, "support_mesh_drop_down", False)
        else:
            self._setNodeSetting(node, "infill_sparse_density", 100)
            self._setNodeSetting(node, "support_enable", False)
            self._setNodeSetting(node, "meshfix_union_all", True)
        return node, Vector(float(centre[0]), float(centre[1]), float(centre[2]))

    # ------------------------------------------------------------ actions
    def _prepared_settings(self):
        s = self._settings()
        opts = self._options()
        if opts.get("brim_from_first_layer"):
            fl = self._firstLayer()
            if fl:
                s.brim_thickness = fl
        return s, opts

    def _finNodes(self, model_id: Optional[str] = None, face_key=None, any_face: bool = True):
        root = self._app.getController().getScene().getRoot()
        out = []
        for n in DepthFirstIterator(root):
            if not self._isFinNode(n):
                continue
            if model_id is not None and getattr(n, "_shark_model", None) != model_id:
                continue
            if not any_face and getattr(n, "_shark_face", None) != face_key:
                continue
            out.append(n)
        return out

    def _place(self, V, F, rep, nodes, label: str, model_id: str, face_key, replace) -> None:
        opts = self._options()
        fin_node, pos = self._buildFinNode(V, F, "%s (%s)" % (FIN_NODE_PREFIX, label), bool(opts.get("as_support_mesh")),
                                           model_id, face_key)
        op = GroupedOperation()
        for old in replace:
            op.addOperation(RemoveSceneNodeOperation(old))
        op.addOperation(AddSceneNodeOperation(fin_node, self._app.getController().getScene().getRoot()))
        op.addOperation(TranslateOperation(fin_node, pos, set_position=True))
        op.push()
        changed = []
        if opts.get("disable_model_support"):
            for n in nodes:
                if self._setNodeSetting(n, "support_enable", False):
                    changed.append(n.getName())
        self._app.getController().getScene().sceneChanged.emit(fin_node)
        extra = ""
        if replace:
            extra += "\nReplaced the fins that were there before."
        if changed:
            extra += "\nNormal support is now off for: %s (per-model setting; you can change it back)." % ", ".join(changed)
        if self._app.getPreferences().getValue("physics/automatic_push_free"):
            extra += ("\nWarning: 'Ensure models are kept apart' is on in Preferences; it will push the fins "
                      "away from the model. Turn it off.")
        msg = rep.summary() + "." + extra + "\nIf you move or rotate the model, remove the fins and add them again."
        self._setStatus(rep.summary())
        self._message(msg, Message.MessageType.POSITIVE, title="Shark fins added")

    def addFinsToSelection(self) -> None:
        """Automatic: fins under every matching face of each selected model (replaces their old fins)."""
        try:
            self._addFinsAuto()
        except Exception as ex:  # noqa: BLE001 - never take Cura down
            Logger.logException("e", "Shark Support: adding fins failed")
            self._setStatus("Failed: " + str(ex))
            self._message("Adding fins failed: %s\nDetails are in cura.log." % ex, Message.MessageType.ERROR)

    def _addFinsAuto(self) -> None:
        nodes = self._selectedMeshes()
        if not nodes:
            self._setStatus("Nothing selected: click your model first.")
            self._message("Select the model first, then press Auto.", Message.MessageType.WARNING)
            return
        s, _ = self._prepared_settings()
        made_any = False
        for node in nodes:
            t0 = time.time()
            soup = self._worldSoupZup([node])
            V, F, rep = shark_core.make_fins(soup, None, s)
            Logger.log("i", "Shark Support: auto %s: %s in %.2f s (%d triangles)", node.getName(), rep.summary(),
                       time.time() - t0, len(soup) // 3)
            if not len(F):
                why = "; ".join(rep.notes) or "nothing matched"
                self._setStatus("No fins: " + why)
                self._message("No fins were made for %s: %s.\nTry picking the face by hand, widening the overhang "
                              "angle range or lowering 'Shortest slope' in the settings." % (node.getName(), why),
                              Message.MessageType.WARNING)
                continue
            made_any = True
            self._place(V, F, rep, [node], node.getName(), node.getId(), None, self._finNodes(node.getId()))
        return made_any

    def addFinsAtPoint(self, node, scene_point) -> bool:
        """Fins under the one flat face of `node` that contains the picked point (scene coordinates)."""
        try:
            if node is None or node.getMeshData() is None:
                return False
            s, _ = self._prepared_settings()
            soup = self._worldSoupZup([node])
            p = numpy.array([scene_point.x, -scene_point.z, scene_point.y], dtype=numpy.float64)
            size = float(numpy.linalg.norm(soup.max(axis=0) - soup.min(axis=0)))
            b = shark_core.FinBuilder(soup, None, s)
            V, F, rep = b.build_at(p, tol=max(1.0, 0.01 * size))
            if not len(F):
                why = "; ".join(rep.notes) or "nothing matched"
                self._setStatus("No fins: " + why)
                self._message("No fins for that face: %s." % why, Message.MessageType.WARNING, title="Shark Support")
                return False
            key = rep.face_keys[0] if rep.face_keys else None
            self._place(V, F, rep, [node], "%s, face" % node.getName(), node.getId(), key,
                        self._finNodes(node.getId(), key, any_face=False) + self._finNodes(node.getId(), None, any_face=False))
            return True
        except Exception as ex:  # noqa: BLE001
            Logger.logException("e", "Shark Support: picking a face failed")
            self._setStatus("Failed: " + str(ex))
            self._message("Adding fins failed: %s\nDetails are in cura.log." % ex, Message.MessageType.ERROR)
            return False

    def removeAllFins(self) -> None:
        fins = self._finNodes()
        if not fins:
            self._setStatus("No fins in the scene.")
            return
        op = GroupedOperation()
        for n in fins:
            op.addOperation(RemoveSceneNodeOperation(n))
        op.push()
        self._setStatus("Removed %d fin object(s)." % len(fins))

    # ------------------------------------------------------------ self-check
    def runSelfCheck(self) -> None:
        lines = ["Shark Support self-check %s (built %s)" % (VERSION, BUILD_DATE)]
        ok_all = True

        def check(name, fn):
            nonlocal ok_all
            try:
                res = fn()
                good = res is not False
                lines.append(("PASS " if good else "FAIL ") + name + ("" if res in (None, True, False) else " - %s" % res))
                ok_all &= good
            except Exception as ex:  # noqa: BLE001
                ok_all = False
                lines.append("FAIL %s - %r" % (name, ex))
                Logger.logException("e", "Shark Support self-check: %s", name)

        holder = {}

        def geometry():
            v, f = shark_core.tilted_box(tilt_deg=35)
            V, F, rep = shark_core.make_fins(v, f, shark_core.FinSettings())
            holder["V"], holder["F"] = V, F
            assert rep.fins == 5, rep.summary()
            return rep.summary()

        def picking():
            v, f = shark_core.tilted_box(tilt_deg=35)
            b = shark_core.FinBuilder(v, f, shark_core.FinSettings())
            n, _ = shark_core.face_normals_areas(b.v, b.f)
            under = b.v[b.f[int(numpy.argmin(n[:, 2]))]].mean(axis=0)
            V, F, rep = b.build_at(under)
            assert rep.fins == 5, rep.summary()
            top = b.v[b.f[int(numpy.argmax(n[:, 2]))]].mean(axis=0)
            _, _, rep2 = shark_core.FinBuilder(v, f).build_at(top)
            assert rep2.fins == 0 and rep2.notes, "a top face was accepted"
            return "underside picked, top face refused"

        def clearance():
            v, f = shark_core.tilted_box(tilt_deg=35)
            ray = shark_core.UpRaycaster(*shark_core.weld(v, f))
            worst = min(ray.cast(p[0], p[1])[0] - p[2] for p in holder["V"])
            st = shark_core.FinSettings()
            assert worst >= -st.anchor_overlap - 1e-6, worst
            return "anchor teeth reach %.3f mm into the part, nothing deeper" % -worst

        def node():
            n, _ = self._buildFinNode(holder["V"], holder["F"], FIN_NODE_PREFIX + " (self-check)", False)
            md = n.getMeshData()
            assert md is not None and md.getVertexCount() > 0
            stack = n.callDecoration("getStack")
            assert stack is not None
            assert stack.getTop().getProperty("infill_sparse_density", "value") == 100
            return "%d vertices, per-object settings applied" % md.getVertexCount()

        def support_node():
            n, _ = self._buildFinNode(holder["V"], holder["F"], FIN_NODE_PREFIX + " (self-check)", True)
            assert n.callDecoration("isSupportMesh"), "support_mesh flag not set"

        def first_layer():
            fl = self._firstLayer()
            return "first layer height %s" % fl

        def plugin_files():
            d = self.pluginDir()
            for rel in ("qml/SharkSupportDialog.qml", "qml/SharkSupportTool.qml", "icons/shark_tool.svg"):
                assert os.path.isfile(os.path.join(d, rel)), rel

        def toolbar():
            tools = self._app.getController().getAllTools()
            assert self._plugin_id in tools, "tool not registered"
            return "toolbar button registered"

        check("fin geometry on the 35 degree test box", geometry)
        check("fins reach no deeper than the anchor teeth", clearance)
        check("picking a face", picking)
        check("Cura scene node (solid fins)", node)
        check("Cura scene node (support mesh mode)", support_node)
        check("read printer profile", first_layer)
        check("plugin files present", plugin_files)
        check("toolbar tool", toolbar)
        lines.append("RESULT: " + ("PASS" if ok_all else "FAIL"))
        text = "\n".join(lines)
        for ln in lines:
            Logger.log("i", "Shark Support self-check: %s", ln)
        path = os.path.join(tempfile.gettempdir(), "shark_support_selfcheck.txt")
        try:
            with open(path, "w") as fh:
                fh.write(text + "\n")
            text += "\nSaved to " + path
        except OSError:
            pass
        self._message(text, Message.MessageType.POSITIVE if ok_all else Message.MessageType.ERROR,
                      title="Shark Support self-check")
