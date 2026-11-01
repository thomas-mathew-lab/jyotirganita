"""The step-scan tool loaded as a module for the tests (``tools/step_scan.py``)."""

from __future__ import annotations

import importlib.util
import sys
from functools import cache
from pathlib import Path
from types import ModuleType

TOOL = Path(__file__).resolve().parents[1] / "tools" / "step_scan.py"


@cache
def step_scan() -> ModuleType:
    spec = importlib.util.spec_from_file_location("step_scan", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["step_scan"] = module
    spec.loader.exec_module(module)
    return module
