"""The constants firewall.

Each test builds a throw-away package tree with its own ``data/`` and plants
one module in it. The stub datum is a planted test value, not a reading of
any source; it loads through the datum loader (records_kit).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from records_kit import DROP, Sample, datum

from jyotirganita.data.firewall import check_package
from jyotirganita.data.yamlio import dump_canonical, loads_exact

REPO = Path(__file__).resolve().parents[2]

STUB_ENGINE_PARAMETERS = """\
parameters:
  - key: test.step
    kind: scan_step
    value: "0.0625"
    unit: day
    justification: planted for the firewall test
    used_by: []
"""


def _stub_datum(value: str, status: str = "read") -> str:
    """Planted data: stub.constant (printed ``value``) and stub.negative."""
    if status == "gap":
        items: list[dict[str, object]] = [
            {
                "key": "stub.constant",
                "status": "gap",
                "reason": "planted gap",
                "searched": "nothing",
                "effect": "none",
            }
        ]
        return dump_canonical(items)
    printed = loads_exact(f"v: {value}\n")["v"]
    return dump_canonical(
        [
            datum(
                "stub.constant",
                value=printed,
                form="fraction",
                unit="none",
                status=status,
                second_read=DROP,
            ),
            datum(
                "stub.negative",
                value="-1/8",
                form="fraction",
                unit="none",
                status="read",
                second_read=DROP,
            ),
        ]
    )


def _package(
    tmp_path: Path,
    module: str,
    source: str,
    *,
    datum: str | None = None,
    allow: str = "entries: []\n",
) -> Path:
    Sample(tmp_path)  # sources.yaml, ISSUES.md and DECISIONS.md of a planted repository
    root = tmp_path / "jyotirganita"
    data = root / "data"
    (data / "texts" / "stub").mkdir(parents=True)
    (data / "firewall_allow.yaml").write_text(allow, encoding="utf-8")
    (data / "engine_parameters.yaml").write_text(STUB_ENGINE_PARAMETERS, encoding="utf-8")
    if datum is not None:
        (data / "texts" / "stub" / "elements.yaml").write_text(datum, encoding="utf-8")
    target = root / module
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(source), encoding="utf-8")
    return root


def _rules(root: Path) -> list[str]:
    return [f.rule for f in check_package(root)]


def test_planted_literal_fails(tmp_path: Path) -> None:
    root = _package(tmp_path, "core/planted.py", "X = 0.0057183\n")
    findings = check_package(root)
    assert [f.rule for f in findings] == ["literal"]
    assert "0.0057183" in findings[0].message


@pytest.mark.parametrize("printed", ["0.0057183", '"0.0057183"', '"57183/10000000"'])
def test_datum_tag_with_equal_value_passes(tmp_path: Path, printed: str) -> None:
    root = _package(
        tmp_path,
        "core/planted.py",
        "X = 0.0057183  # datum: stub.constant\n",
        datum=_stub_datum(printed),
    )
    assert _rules(root) == []


def test_datum_tag_with_different_value_fails(tmp_path: Path) -> None:
    root = _package(
        tmp_path,
        "core/planted.py",
        "X = 0.0057183  # datum: stub.constant\n",
        datum=_stub_datum("0.0057184"),
    )
    findings = check_package(root)
    assert [f.rule for f in findings] == ["tag-value"]


def test_datum_tag_naming_a_gap_fails(tmp_path: Path) -> None:
    root = _package(
        tmp_path,
        "core/planted.py",
        "X = 0.0057183  # datum: stub.constant\n",
        datum=_stub_datum("", status="gap"),
    )
    findings = check_package(root)
    assert [f.rule for f in findings] == ["tag"] and "gap" in findings[0].message


def test_datum_tag_naming_a_missing_key_fails(tmp_path: Path) -> None:
    root = _package(tmp_path, "core/planted.py", "X = 0.0057183  # datum: no.such.key\n")
    findings = check_package(root)
    assert [f.rule for f in findings] == ["tag"] and "does not load" in findings[0].message


def test_signed_literal_is_compared_with_its_sign(tmp_path: Path) -> None:
    ok = _package(
        tmp_path / "a",
        "core/planted.py",
        "X = -0.125  # datum: stub.negative\n",
        datum=_stub_datum("0.5"),
    )
    assert _rules(ok) == []
    bad = _package(
        tmp_path / "b",
        "core/planted.py",
        "X = 0.125  # datum: stub.negative\n",
        datum=_stub_datum("0.5"),
    )
    assert _rules(bad) == ["tag-value"]


def test_numeric_string_literal_is_caught(tmp_path: Path) -> None:
    root = _package(
        tmp_path,
        "core/planted.py",
        """\
        from fractions import Fraction
        X = Fraction("0.0057183")
        """,
    )
    assert _rules(root) == ["literal"]


def test_engine_parameter_tag(tmp_path: Path) -> None:
    ok = _package(tmp_path / "a", "modern/m.py", "STEP = 0.0625  # engine-parameter: test.step\n")
    assert _rules(ok) == []
    bad = _package(tmp_path / "b", "modern/m.py", "STEP = 0.125  # engine-parameter: test.step\n")
    assert _rules(bad) == ["tag-value"]


def test_derived_tag_without_a_record_fails(tmp_path: Path) -> None:
    root = _package(tmp_path, "search/s.py", "BOUND = 13  # derived: search.bound.moon\n")
    assert _rules(root) == ["tag"]


def test_stale_tag_fails(tmp_path: Path) -> None:
    root = _package(
        tmp_path, "core/planted.py", "X = len([])  # datum: stub.constant\n", datum=_stub_datum("1")
    )
    assert _rules(root) == ["tag"]


def test_tag_on_a_closed_set_literal_is_asserted(tmp_path: Path) -> None:
    same = _package(
        tmp_path / "a",
        "core/planted.py",
        "X = 60  # datum: stub.constant\n",
        datum=_stub_datum("60"),
    )
    assert _rules(same) == []
    differs = _package(
        tmp_path / "b",
        "core/planted.py",
        "X = 60  # datum: stub.constant\n",
        datum=_stub_datum("1"),
    )
    assert _rules(differs) == ["tag-value"]
    missing = _package(tmp_path / "c", "core/planted.py", "X = 60  # datum: no.such.key\n")
    assert _rules(missing) == ["tag"]


def test_closed_set_passes_and_others_fail(tmp_path: Path) -> None:
    ok = _package(tmp_path / "a", "core/c.py", "A = (0, 1, -1, 0.5, 60, 360, 86400, 1_000)\n")
    assert _rules(ok) == []
    bad = _package(tmp_path / "b", "core/c.py", "A = (61, 0.25, 1j)\n")
    assert _rules(bad) == ["literal", "literal", "literal"]


@pytest.mark.parametrize(
    ("module", "source"),
    [
        ("siddhantic/engine.py", "import math\n"),
        ("calendar/elements.py", "import math\n"),
        ("calendar/elements.py", "from math import floor\n"),
        ("search/stages.py", "import numpy as np\n"),
        ("siddhantic/x.py", "from decimal import Decimal\n"),
        ("core/exact.py", "import importlib\nm = importlib.import_module('decimal')\n"),
        ("siddhantic/y.py", "m = __import__('cmath')\n"),
    ],
)
def test_import_ban(tmp_path: Path, module: str, source: str) -> None:
    root = _package(tmp_path, module, source)
    assert _rules(root) == ["import-ban"]


@pytest.mark.parametrize("module", ["modern/frames.py", "core/types.py", "io/record.py"])
def test_import_ban_scope(tmp_path: Path, module: str) -> None:
    root = _package(tmp_path, module, "import math\n")
    assert _rules(root) == []


def test_module_scoped_allow_entry(tmp_path: Path) -> None:
    allow = textwrap.dedent(
        """\
        entries:
          - value: 1461
            module: core/calendar.py
            reason: planted for the test
        """
    )
    derived_in_docstring = '"""Days in four Julian years: 1461 = 4 × 365 + 1."""\nN = 1461\n'
    ok = _package(tmp_path / "a", "core/calendar.py", derived_in_docstring, allow=allow)
    assert _rules(ok) == []
    no_docstring = _package(tmp_path / "b", "core/calendar.py", "N = 1461\n", allow=allow)
    assert _rules(no_docstring) == ["literal"]
    elsewhere = _package(tmp_path / "c", "core/other.py", derived_in_docstring, allow=allow)
    assert _rules(elsewhere) == ["literal"]


def test_this_repository_passes() -> None:
    assert check_package(REPO / "jyotirganita") == []
