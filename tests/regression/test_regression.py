"""The regression files are current (change detectors, not evidence).

A difference fails: the change is either a fault or a deliberate change
to computed output, which regenerates the file with ``tools/regression.py``
and names it, with a new version, in ``CHANGELOG.md``. The file of a preset on DE441 is checked
under the ``de441`` tier: CI does not fetch DE441.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from jyotirganita.methods.presets import preset_ids

REPO = Path(__file__).resolve().parents[2]


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("regression", REPO / "tools" / "regression.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["regression"] = mod
    spec.loader.exec_module(mod)
    return mod


regression = _tool()


def _params() -> list[object]:
    return [
        pytest.param(p, marks=pytest.mark.de441) if regression.kernel_of(REPO, p) == "de441" else p
        for p in preset_ids(REPO)
    ]


@pytest.mark.parametrize("preset_id", _params())
def test_the_regression_file_is_current(preset_id: str) -> None:
    path = regression.path_of(REPO, preset_id)
    assert path.is_file(), f"no regression file for {preset_id}: run tools/regression.py"
    assert path.read_text(encoding="ascii") == regression.render(REPO, preset_id)


def test_every_regression_file_says_it_is_a_change_detector() -> None:
    for path in sorted((REPO / "tests" / "regression").glob("*.jsonl")):
        first = path.read_text(encoding="ascii").split("\n", 1)[0]
        assert "CHANGE DETECTOR, NOT EVIDENCE" in first, path.name
