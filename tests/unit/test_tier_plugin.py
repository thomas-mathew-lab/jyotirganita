"""The test plugin of tests/conftest.py: tiers by marker, no run-time skip, the summary.

Each case runs an inner pytest in a subprocess with a copy of the plugin,
so that the inner run's state never touches this run's.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CONFTEST = (Path(__file__).resolve().parents[1] / "conftest.py").read_text(encoding="utf-8")
INI = "[pytest]\nmarkers =\n    de441: tier\n    extras: tier\naddopts = -p no:cacheprovider\n"


def _tree(pytester: pytest.Pytester, tests: str) -> None:
    pytester.makefile(".ini", pytest=INI)
    (pytester.path / "tests").mkdir()
    (pytester.path / "tests" / "conftest.py").write_text(
        CONFTEST.replace('pytest_plugins = ["pytester"]\n', ""), encoding="utf-8"
    )
    (pytester.path / "tests" / "test_inner.py").write_text(tests, encoding="utf-8")


TIERED = """\
import pytest

def test_plain():
    pass

@pytest.mark.de441
def test_needs_de441():
    pass

@pytest.mark.extras
def test_needs_extras():
    pass
"""


def test_ci_tier_deselects_marked_tests(pytester: pytest.Pytester) -> None:
    _tree(pytester, TIERED)
    result = pytester.runpytest_subprocess("tests")
    result.assert_outcomes(passed=1, deselected=2)


def test_named_tier_runs_only_its_tests(pytester: pytest.Pytester) -> None:
    _tree(pytester, TIERED)
    result = pytester.runpytest_subprocess("tests", "--tier", "de441")
    result.assert_outcomes(passed=1, deselected=2)


@pytest.mark.parametrize(
    "body",
    [
        "import pytest\ndef test_x():\n    pytest.skip('fixture file missing')\n",
        "import pytest\n@pytest.mark.skipif(True, reason='no kernel')\ndef test_x():\n    pass\n",
        "import pytest\n@pytest.mark.xfail(reason='known')\ndef test_x():\n    assert False\n",
    ],
)
def test_run_time_skip_and_xfail_fail(pytester: pytest.Pytester, body: str) -> None:
    _tree(pytester, body)
    result = pytester.runpytest_subprocess("tests")
    # a skipif mark skips at setup, which pytest then counts as an error
    outcomes = result.parseoutcomes()
    assert outcomes.get("failed", 0) + outcomes.get("errors", 0) == 1
    assert "skipped" not in outcomes and "xfailed" not in outcomes
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*run-time skip or xfail is forbidden*"])


@pytest.mark.parametrize(
    "body",
    [
        "import pytest\npytest.importorskip('no_such_module_xyz')\ndef test_x():\n    pass\n",
        "import pytest\npytest.skip('no kernel', allow_module_level=True)\n"
        "def test_x():\n    pass\n",
    ],
)
def test_collection_skip_fails(pytester: pytest.Pytester, body: str) -> None:
    _tree(pytester, body)
    # a passing module beside it must not turn the run green
    pytester.makepyfile(**{"tests/test_other": "def test_y():\n    pass\n"})
    result = pytester.runpytest_subprocess("tests")
    outcomes = result.parseoutcomes()
    assert "skipped" not in outcomes
    assert outcomes.get("errors", 0) == 1
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*skip at collection*is forbidden*"])


def test_two_tier_markers_are_refused(pytester: pytest.Pytester) -> None:
    _tree(
        pytester,
        "import pytest\n@pytest.mark.de441\n@pytest.mark.extras\ndef test_x():\n    pass\n",
    )
    result = pytester.runpytest_subprocess("tests")
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*more than one tier marker*"])


def test_summary_merges_per_tier(pytester: pytest.Pytester) -> None:
    _tree(pytester, TIERED)
    summary = pytester.path / "reports" / "test_summary.json"
    summary.parent.mkdir()
    keep = {
        "result": "passed",
        "data_hash": "sha256:x",
        "data_files": [],
        "commit": "c",
        "date": "d",
    }
    summary.write_text(json.dumps({"schema": 1, "tiers": {"de441": keep}}), encoding="utf-8")
    result = pytester.runpytest_subprocess("tests", "--write-summary")
    result.assert_outcomes(passed=1, deselected=2)
    doc = json.loads(summary.read_text(encoding="utf-8"))
    assert doc["tiers"]["de441"] == keep
    ci = doc["tiers"]["ci"]
    assert ci["result"] == "passed" and ci["data_hash"].startswith("sha256:")


def test_summary_refuses_a_partial_run(pytester: pytest.Pytester) -> None:
    _tree(pytester, TIERED)
    result = pytester.runpytest_subprocess("tests", "--write-summary", "-k", "plain")
    assert result.ret != 0
