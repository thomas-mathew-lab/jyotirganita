"""The command line's ``search`` (``jyotirganita/io/cli.py``).

A query file in, JSON Lines out, staged and ``--brute`` alike; every
refusal on standard error as ``<field>: <message>`` with exit status 2
and nothing written (a ``--set`` key, which is ``--set``'s; a ``--procedure``
override; an unknown preset; a missing or malformed query file); an
``--intraday`` override flags every candidate ``diagnostic:<model>``
and switches planet pruning off. No printed value enters here.
"""

from __future__ import annotations

import io
import json
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml
from search_kit import REPO

from jyotirganita.io.cli import EXIT_REFUSED, main

FIRST, LAST = 2167030, 2167040
QUERY: dict[str, Any] = {
    "reading_profile": "kerala_default",
    "window": {"from": {"jdn": FIRST}, "to": {"jdn": LAST}},
    "constraints": [
        {"element": "weekday", "value": "Wednesday"},
        {"element": "planet_rasi", "body": "jupiter", "value": "Makara", "mode": "report"},
    ],
    "near_miss": {"max_misses": 1},
}
BASE = [
    "search",
    "--preset",
    "parahita_kerala",
    "--observer",
    "kerala/kozhikode",
    "--repo",
    str(REPO),
]


def _file(tmp_path: Path, doc: Any, name: str = "q.yaml") -> Path:
    p = tmp_path / name
    p.write_text(
        yaml.safe_dump(doc) if name.endswith(".yaml") else json.dumps(doc), encoding="utf-8"
    )
    return p


def _run(args: list[str]) -> tuple[int, list[dict[str, Any]]]:
    out = io.BytesIO()
    code = main(args, out=out)
    return code, [json.loads(x) for x in out.getvalue().decode("ascii").splitlines()]


def test_search_writes_json_lines(tmp_path: Path) -> None:
    q = _file(tmp_path, QUERY)
    code, lines = _run([*BASE, "--query", str(q)])
    assert code == 0 and lines
    assert [d["dates"]["jdn"] for d in lines] == sorted(d["dates"]["jdn"] for d in lines)
    assert {d["class"] for d in lines} <= {"match", "near_miss"}
    code, brute = _run([*BASE, "--query", str(q), "--brute"])
    assert code == 0
    strip = [{k: v for k, v in d.items() if k != "provenance"} for d in lines]
    assert strip == [{k: v for k, v in d.items() if k != "provenance"} for d in brute]
    assert lines[0]["provenance"]["search"]["path"] == "staged"
    assert brute[0]["provenance"]["search"]["path"] == "brute"


def test_json_query_and_file_output(tmp_path: Path) -> None:
    q = _file(tmp_path, QUERY, "q.json")
    target = tmp_path / "out.jsonl"
    assert main([*BASE, "--query", str(q), "--jsonl", str(target)]) == 0
    raw = target.read_bytes()
    assert raw.endswith(b"\n") and b"\r" not in raw
    _, lines = _run([*BASE, "--query", str(q)])
    assert raw.decode("ascii").splitlines() == [
        json.dumps(d, separators=(",", ":"), ensure_ascii=True) for d in lines
    ]


@pytest.mark.parametrize(
    ("extra", "field"),
    [
        (["--set", "gati=x"], "set"),
        (["--set", "noequals"], "set"),
        (["--procedure", "gati=x"], "procedure"),
        (["--intraday", "no_such_model"], "intraday"),
        (["--month-rule", "no_such_rule"], "month_rule"),
    ],
    ids=["set_key", "set_malformed", "procedure", "intraday", "month_rule"],
)
def test_refusals_exit_2_and_write_nothing(
    tmp_path: Path, extra: list[str], field: str, capsys: pytest.CaptureFixture[str]
) -> None:
    q = _file(tmp_path, QUERY)
    code, lines = _run([*BASE, "--query", str(q), *extra])
    assert code == EXIT_REFUSED and lines == []
    assert f"jyotirganita search: {field}: " in capsys.readouterr().err


def test_unknown_preset_and_query_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    q = _file(tmp_path, QUERY)
    code, _ = _run(["search", "--preset", "no_such", "--query", str(q), "--repo", str(REPO)])
    assert code == EXIT_REFUSED and "preset: " in capsys.readouterr().err
    code, _ = _run([*BASE, "--query", str(tmp_path / "missing.yaml")])
    assert code == EXIT_REFUSED and "query: " in capsys.readouterr().err
    bad = tmp_path / "q.txt"
    bad.write_text("x", encoding="utf-8")
    code, _ = _run([*BASE, "--query", str(bad)])
    assert code == EXIT_REFUSED
    malformed = _file(
        tmp_path, {**QUERY, "constraints": [{"element": "weekday", "value": "Wednesdy"}]}
    )
    code, _ = _run([*BASE, "--query", str(malformed)])
    assert code == EXIT_REFUSED and "nearest ids" in capsys.readouterr().err


@pytest.mark.parametrize(
    "constraint",
    [
        {"element": "weekday", "value": "Wednesdy"},
        {"element": "nakshatra", "value": 28},
        {"element": "day_of_month", "value": 40},
        {"element": "tithi", "value": 3, "match": "at_time"},
    ],
    ids=["misspelled_name", "index_out_of_range", "day_of_month", "at_time_without_nadika"],
)
def test_malformed_query_refused_before_the_preset_opens(
    tmp_path: Path,
    constraint: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Review N7: the vocabulary is checked before the configuration (a kernel) is opened."""

    def never(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("the preset was opened for a malformed query")

    monkeypatch.setattr("jyotirganita.io.cli.open_search", never)
    q = _file(tmp_path, {**QUERY, "constraints": [constraint]})
    modern = ["search", "--preset", "modern_iers", "--observer", "kerala/kozhikode"]
    code, lines = _run([*modern, "--repo", str(REPO), "--query", str(q)])
    assert code == EXIT_REFUSED and lines == []
    assert "constraints[0]" in capsys.readouterr().err


def test_intraday_override_is_diagnostic(tmp_path: Path) -> None:
    doc = {
        **QUERY,
        "constraints": [QUERY["constraints"][0], {**QUERY["constraints"][1], "mode": "require"}],
    }
    q = _file(tmp_path, doc)
    code, lines = _run([*BASE, "--query", str(q), "--intraday", "full_evaluation"])
    assert code == 0 and lines
    assert all("diagnostic:diagnostic.full_evaluation" in d["flags"] for d in lines)
    assert lines[0]["provenance"]["search"]["planet_pruning"].startswith("off:")


def test_console_script_is_declared() -> None:
    meta = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert meta["project"]["scripts"]["jyotirganita"] == "jyotirganita.io.cli:main"
