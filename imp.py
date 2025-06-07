"""Compatibility shim for deprecated imp module on Python >=3.12."""
import importlib.util
import types

PY_SOURCE = 1
PY_COMPILED = 2
C_EXTENSION = 3
PY_RESOURCE = 4
PKG_DIRECTORY = 5
C_BUILTIN = 6
PY_FROZEN = 7
PKG_SUFFIXES: list[str] = []
PY_SUFFIXES: list[str] = [".py"]


def new_module(name: str) -> types.ModuleType:
    return types.ModuleType(name)


def load_module(name: str):
    spec = importlib.util.find_spec(name)
    if spec is None or spec.loader is None:
        raise ImportError(name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
