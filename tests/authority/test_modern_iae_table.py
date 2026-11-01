"""indian_astronomical_ephemeris's "True Ayanamsa" table against the method's own definition.

The table (fixture ``authority/modern/iae_2022_true_ayanamsa``; indian_astronomical_ephemeris PDF
p. 428) is the IAE's own tabulation of the definition it states (the mean
polynomial, PDF p. 387, plus the nutation in longitude, the table's foot).
``tools/iae_comparison.py`` computes every row; this test compares them
block by block, one printed value per test, so that the ledger counts the
fixture. The tolerance is half the table's
print quantum plus half the print quantum of the polynomial's constant
term, which the computation takes rounded (the tool's docstring;
the report records the three rows beyond 0.05″ and that
attribution, an inference). A comparison internal to the method's own
source.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from authority_kit import printed, records

Recorder = Callable[..., None]

REPO = Path(__file__).resolve().parents[2]
FIXTURE = "authority/modern/iae_2022_true_ayanamsa"


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "iae_comparison", REPO / "tools" / "iae_comparison.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["iae_comparison"] = mod
    spec.loader.exec_module(mod)
    return mod


tool = _tool()


@cache
def rows() -> list[Any]:
    return list(tool.rows(REPO))


def _block(block: int) -> list[tuple[Any, Any]]:
    """The printed rows of ``output.block<n>`` paired with their computed rows, in order."""
    start = sum(len(printed(FIXTURE)[f"output.block{b}"]) for b in range(1, block))
    cells = list(printed(FIXTURE)[f"output.block{block}"])
    return list(zip(cells, rows()[start : start + len(cells)], strict=True))


@pytest.mark.parametrize("block", range(1, tool.BLOCKS + 1))
def test_the_true_ayanamsa_block_reproduces(block: int, record_comparison: Recorder) -> None:
    half_table, half_c0 = tool.tolerance(records().data)
    pairs = _block(block)
    record_comparison(
        fixture=FIXTURE,
        value=f"output.block{block}",
        computed=[
            [cells[0], cells[1], r.degrees, r.arcminutes, f"{r.computed:.4f}"] for cells, r in pairs
        ],
        tolerance=half_table + half_c0,
        tolerance_reason=(
            "half the table's print quantum (0.1″) plus half that of the polynomial's "
            "constant term (0.01″), which the computation takes rounded; rows beyond 0.05″ "
            "are listed in reports/iae_true_ayanamsa.md (an inference)"
        ),
    )
    for cells, r in pairs:
        assert (int(cells[2]), int(cells[3])) == (r.degrees, r.arcminutes)
    worst = max(abs(r.difference) for _, r in pairs)
    assert worst <= half_table + half_c0
