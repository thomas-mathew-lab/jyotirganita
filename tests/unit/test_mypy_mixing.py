"""The type families and kinds cannot be mixed.

Each ``fail_*.py`` case under ``mypy_cases/`` must fail mypy strict on the
line marked ``# expect-error: <code>`` and nowhere else; ``pass_control.py``
uses the same API correctly and must check clean, so that a failure is the
marked line's and not an import or setup error.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from mypy import api

CASES = Path(__file__).parent / "mypy_cases"
_MARK = re.compile(r"#\s*expect-error:\s*([a-z-]+)")
_ERROR = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+): error: .*\[(?P<code>[a-z-]+)\]$")

FAIL_CASES = sorted(p.name for p in CASES.glob("fail_*.py"))


@pytest.fixture(scope="module")
def mypy_errors(tmp_path_factory: pytest.TempPathFactory) -> dict[str, set[tuple[int, str]]]:
    cache = tmp_path_factory.mktemp("mypy-cache")
    files = [str(p) for p in sorted(CASES.glob("*.py"))]
    stdout, stderr, _status = api.run(
        ["--strict", "--no-error-summary", "--cache-dir", str(cache), *files]
    )
    assert stderr == "", stderr
    found: dict[str, set[tuple[int, str]]] = {}
    for line in stdout.splitlines():
        m = _ERROR.match(line.strip())
        assert m is not None, f"unparsed mypy output: {line}"
        found.setdefault(Path(m["path"]).name, set()).add((int(m["line"]), m["code"]))
    return found


def _expected(name: str) -> set[tuple[int, str]]:
    marks = set()
    for i, text in enumerate((CASES / name).read_text(encoding="utf-8").splitlines(), start=1):
        m = _MARK.search(text)
        if m:
            marks.add((i, m[1]))
    return marks


def test_the_four_acceptance_cases_exist() -> None:
    assert {
        "fail_tropical_plus_sidereal.py",
        "fail_ayanamsa_mean_for_true.py",
        "fail_exact_plus_float.py",
        "fail_exact_times_half.py",
    } <= set(FAIL_CASES)


def test_control_checks_clean(mypy_errors: dict[str, set[tuple[int, str]]]) -> None:
    assert mypy_errors.get("pass_control.py", set()) == set()
    assert mypy_errors.get("_setup.py", set()) == set()


@pytest.mark.parametrize("name", FAIL_CASES)
def test_case_fails_on_its_marked_line_only(
    name: str, mypy_errors: dict[str, set[tuple[int, str]]]
) -> None:
    expected = _expected(name)
    assert expected, f"{name} has no expect-error mark"
    assert mypy_errors.get(name, set()) == expected
