"""The engine-parameter loader refuses malformed entries."""

from __future__ import annotations

import textwrap
from fractions import Fraction
from pathlib import Path

import pytest

from jyotirganita.data import engine_parameters as ep

GOOD = """\
parameters:
  - key: seeds.one
    kind: seed
    value: 7
    unit: none
    justification: planted
    used_by: []
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "engine_parameters.yaml"
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return p


def test_shipped_file_loads() -> None:
    params = ep.load()
    assert "seeds.signoff_sample" in params
    assert params["seeds.signoff_sample"].kind == "seed"


def test_seed_lookup(tmp_path: Path) -> None:
    assert ep.seed("seeds.one", _write(tmp_path, GOOD)) == 7
    with pytest.raises(ep.EngineParameterError, match=r"seeds\.two"):
        ep.seed("seeds.two", _write(tmp_path, GOOD))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("    unit: none\n", ""), "missing field"),
        (("    used_by: []\n", "    used_by: []\n    extra: 1\n"), "unknown field"),
        (("value: 7", "value: 0.5"), "not a float"),
        (("kind: seed", "kind: guess"), "kind"),
        (("value: 7", "value: -1"), "non-negative integer"),
        (("justification: planted", 'justification: " "'), "justification"),
    ],
)
def test_malformed_entries_are_refused(
    tmp_path: Path, change: tuple[str, str], message: str
) -> None:
    text = GOOD.replace(*change)
    with pytest.raises(ep.EngineParameterError, match=message):
        ep.load(_write(tmp_path, text))


FACTOR = """\
parameters:
  - key: search.f
    kind: factor
    value: "5/4"
    unit: none
    justification: planted
    used_by: []
"""


def test_factor_kind(tmp_path: Path) -> None:
    assert ep.load(_write(tmp_path, FACTOR))["search.f"].value == Fraction(5, 4)
    for bad in ('"1"', '"3/4"'):
        with pytest.raises(ep.EngineParameterError, match="above one"):
            ep.load(_write(tmp_path, FACTOR.replace('"5/4"', bad)))


def test_shipped_search_parameters() -> None:
    params = ep.load()
    assert params["search.safety_factor"].kind == "factor"
    assert params["search.floor"].kind == params["search.horizon"].kind == "horizon"
    assert params["search.floor"].value < params["search.horizon"].value
    assert ep.seed("seeds.search_windows") != ep.seed("seeds.search_sample")


def test_duplicate_key_is_refused(tmp_path: Path) -> None:
    text = GOOD + GOOD.split("\n", 1)[1]
    with pytest.raises(ep.EngineParameterError, match="used twice"):
        ep.load(_write(tmp_path, text))
