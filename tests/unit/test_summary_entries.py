"""A fixture's fields reach reports/test_summary.json unchanged.

An inner pytest runs a planted authority test in a planted repository
with a copy of the plugin; the summary it writes is compared with the
planted fixture file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from records_kit import Sample, datum, fixture

CONFTEST = (Path(__file__).resolve().parents[1] / "conftest.py").read_text(encoding="utf-8")
INI = "[pytest]\nmarkers =\n    de441: tier\n    extras: tier\naddopts = -p no:cacheprovider\n"

AUTHORITY_TEST = """\
from fractions import Fraction

def test_example(record_comparison):
    computed = [3, 12, 7]
    record_comparison(
        fixture="authority/sample/ex_one",
        value="output.longitude",
        computed=computed,
        tolerance=0,
        tolerance_reason="text_computed: exact in the text's units",
    )
    assert computed == [3, 12, 7]

def test_failing(record_comparison):
    record_comparison(
        fixture="authority/sample/ex_one",
        value="input.days",
        computed=Fraction(1001, 1),
        tolerance=0,
        tolerance_reason="exact",
    )
    assert 1001 == 1000
"""


def _tree(pytester: pytest.Pytester, tests: dict[str, str]) -> Sample:
    s = Sample(pytester.path)
    pytester.makefile(".ini", pytest=INI)
    (pytester.path / "tests").mkdir(exist_ok=True)
    (pytester.path / "tests" / "conftest.py").write_text(
        CONFTEST.replace('pytest_plugins = ["pytester"]\n', ""), encoding="utf-8"
    )
    for rel, body in tests.items():
        p = pytester.path / "tests" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return s


def _run(pytester: pytest.Pytester, *args: str) -> pytest.RunResult:
    # pytester puts the working directory on PYTHONPATH; the planted tree's
    # jyotirganita/ there would shadow the package, so run from tests/
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(pytester.path / "tests")
        return pytester.runpytest_subprocess(".", *args)


def _summary(pytester: pytest.Pytester) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(
        (pytester.path / "reports" / "test_summary.json").read_text(encoding="utf-8")
    )
    return doc


def test_fixture_fields_reach_the_summary_unchanged(pytester: pytest.Pytester) -> None:
    s = _tree(pytester, {"authority/test_sample.py": AUTHORITY_TEST})
    s.data([datum()])
    fx = fixture(datum_keys=["texts.sample.revolutions"])
    s.fixture(fx)
    result = _run(pytester, "--write-summary")
    result.assert_outcomes(passed=1, failed=1)
    entries = _summary(pytester)["entries"]["ci"]
    ok = entries["tests/authority/test_sample.py::test_example"]
    out = fx["values"][1]
    assert ok == {
        "fixture": fx["id"],
        "source": fx["source"],
        "edition_page": fx["edition_page"],
        "pdf_page": fx["pdf_page"],
        "class": fx["class"],
        "methods": fx["methods"],
        "datum_keys": fx["datum_keys"],
        "fixture_status": "double_read",
        "value": out["name"],
        "printed": out["value"],
        "kind": "authority",
        "computed": ["3/1", "12/1", "7/1"],
        "tolerance": "0/1",
        "tolerance_reason": "text_computed: exact in the text's units",
        "result": "passed",
    }
    bad = entries["tests/authority/test_sample.py::test_failing"]
    assert bad["result"] == "failed" and bad["printed"] == 1000 and bad["computed"] == "1001/1"


def test_an_unrecorded_authority_test_fails(pytester: pytest.Pytester) -> None:
    _tree(pytester, {"authority/test_bare.py": "def test_bare():\n    assert True\n"})
    result = _run(pytester)
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*records its comparison with record_comparison*"])


def test_entries_merge_per_tier(pytester: pytest.Pytester) -> None:
    s = _tree(pytester, {"authority/test_sample.py": AUTHORITY_TEST.split("def test_failing")[0]})
    s.fixture(fixture())
    path = pytester.path / "reports" / "test_summary.json"
    path.parent.mkdir()
    other = {
        "result": "passed",
        "data_files": [],
        "data_hash": "sha256:" + "0" * 64,
        "commit": "a" * 40,
        "date": "2026-10-01",
    }
    path.write_text(
        json.dumps({"schema": 1, "tiers": {"de441": other}, "entries": {"de441": {"x::y": {}}}}),
        encoding="utf-8",
    )
    _run(pytester, "--write-summary").assert_outcomes(passed=1)
    doc = _summary(pytester)
    assert doc["tiers"]["de441"] == other and doc["entries"]["de441"] == {"x::y": {}}
    assert list(doc["entries"]["ci"]) == ["tests/authority/test_sample.py::test_example"]
