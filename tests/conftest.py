"""Load the plugin directory as a package so relative imports resolve."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = "intents_pay_plugin"


def load_plugin():
    if PKG in sys.modules:
        return sys.modules[PKG]
    spec = importlib.util.spec_from_file_location(
        PKG,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = PKG
    module.__path__ = [str(ROOT)]
    sys.modules[PKG] = module
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


load_plugin()
