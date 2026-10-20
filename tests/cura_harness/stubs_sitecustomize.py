# TEST ONLY: stand-ins for Cura's C++ modules so Cura can start from source without them (no slicing).
# Put this file on PYTHONPATH as sitecustomize.py.
# Test-only stubs for Cura's native C++ modules, so the GUI and plugins can load in a sandbox.
import sys, types, importlib.abc, importlib.machinery
NAMES = {"pyUvula", "pyArcus", "pynest2d", "pySavitar", "pyDulcificum", "pyclipper_stub", "Charon", "charon"}
class _Any(type):
    def __getattr__(cls, n): return _anything(n)
def _anything(name):
    return _Any(name, (object,), {"__init__": lambda self, *a, **k: None,
                                  "__getattr__": lambda self, n: _anything(n),
                                  "__call__": lambda self, *a, **k: None})
class _Mod(types.ModuleType):
    def __getattr__(self, n):
        if n.startswith("__"): raise AttributeError(n)
        return _anything(n)
class _Finder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] in NAMES:
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
    def create_module(self, spec): 
        m = _Mod(spec.name); m.__path__ = []; return m
    def exec_module(self, m): pass
sys.meta_path.insert(0, _Finder())
