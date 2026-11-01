"""Test-tier selection, the run-time-skip ban and the test summary.

**Tiers.** ``--tier ci`` (the default) runs every test without a tier marker
and deselects those marked ``de441`` or ``extras``; ``--tier de441`` and
``--tier extras`` run only their own tier. Deselection is by marker at
collection; a test is never skipped at run time.

**No run-time skip.** A test that skips or xfails, and a module that skips
at collection (``pytest.importorskip``, a module-level ``pytest.skip``), is
reported as a failure
(a missing fixture is a failure, a requirement CI lacks
is a tier marker).

**Summary.** With ``--write-summary`` the run's tier record is merged into
``reports/test_summary.json``, replacing that tier's record only and keeping
every other tier's: result, the data files the tier's tests loaded under
``jyotirganita/data/`` with their SHA-256 and the hash of the set, the
commit, the date and the environment. A summary is written only for a full
run of the tier (no ``-k``, no ``-m``, no path arguments).

**Per-test entries.** Every test under ``tests/authority/``,
``tests/corpora/`` and ``tests/crosscheck/`` records its comparison through
the ``record_comparison`` fixture, and a test there that records none
fails. For an authority test the plugin copies the fixture's own fields
from its file (id, source, printed page, PDF page, class, methods, datum
keys and the printed value named), so they reach the summary unchanged;
the test gives the computed value, the tolerance and its reason. The
comparison result is the test's outcome. The entries are merged per tier
like the tier records, under ``entries``.

**Check entries.** Every test under ``tests/invariants/`` and
``tests/conformance/`` records one entry: its file, the methods or presets
it covers (its parameters that name a registered method or a preset, else
its file's subject) and its result, with any ``record_property`` fields it
set (the search invariants' windows and seed); no comparison values. They
are merged per tier under ``checks``, beside the authority entries.

**Mutation.** ``--mutate <key>`` perturbs one datum's parsed value in this
test process (``tests/mutate_kit.py`` states the rule), to measure which
data the suite notices when changed; ``--mutate-out <file>`` writes what the run
saw (how often the record was built, whether it was read, the result, the
first failing test). ``--mutate-probe <file>`` perturbs nothing and writes
the keys whose value the run read. Both refuse ``--write-summary``: such a
run is never a tier record.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from collections.abc import Generator
from datetime import UTC, datetime
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from jyotirganita.core.exact import to_canonical
from jyotirganita.provenance.hashing import file_sha256, files_digest
from jyotirganita.provenance.loads import loaded_data_files, reset_loaded

pytest_plugins = ["pytester"]

REPO = Path(__file__).resolve().parent.parent
SUMMARY = REPO / "reports" / "test_summary.json"
TIERS = ("ci", "de441", "extras")
TIER_MARKERS = ("de441", "extras")
RECORDED_DIRS = ("authority", "corpora", "crosscheck")
CHECK_DIRS = ("invariants", "conformance")
_CHECKS = pytest.StashKey[dict[str, dict[str, Any]]]()
_ENTRIES = pytest.StashKey[dict[str, dict[str, Any]]]()
_MUTATION = pytest.StashKey[Any]()
_FIRST_FAILURE = pytest.StashKey[str]()
_PROBE = pytest.StashKey[Any]()


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("jyotirganita")
    group.addoption("--tier", choices=TIERS, default="ci", help="test tier to run (default ci)")
    group.addoption(
        "--write-summary",
        action="store_true",
        help="merge this run's tier record into reports/test_summary.json",
    )
    group.addoption("--mutate", default=None, help="perturb this datum key (mutation coverage)")
    group.addoption("--mutate-out", default=None, help="write the mutated run's result here")
    group.addoption("--mutate-probe", default=None, help="write the data keys this run read")


def pytest_configure(config: pytest.Config) -> None:
    reset_loaded()
    key = config.getoption("--mutate")
    probe_out = config.getoption("--mutate-probe")
    if key is not None or probe_out is not None:
        if config.getoption("--write-summary"):
            raise pytest.UsageError("--mutate never writes a summary: a perturbed run is no tier")
        from mutate_kit import install, install_probe

        if key is not None:
            config.stash[_MUTATION] = install(key)  # inside the probe, which wraps it
        config.stash[_PROBE] = install_probe()
    if config.getoption("--write-summary"):
        partial = (
            config.getoption("keyword")
            or config.getoption("markexpr")
            or any(Path(a).resolve() != REPO / "tests" for a in config.args)
        )
        if partial:
            raise pytest.UsageError("--write-summary records a full tier run: no -k, -m or paths")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    tier = config.getoption("--tier")
    keep: list[pytest.Item] = []
    dropped: list[pytest.Item] = []
    for item in items:
        marks = [m for m in TIER_MARKERS if item.get_closest_marker(m) is not None]
        if len(marks) > 1:
            raise pytest.UsageError(f"{item.nodeid} carries more than one tier marker: {marks}")
        own = marks[0] if marks else "ci"
        (keep if own == tier else dropped).append(item)
    if dropped:
        config.hook.pytest_deselected(items=dropped)
    items[:] = keep


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    if report.failed and _FIRST_FAILURE not in item.config.stash:
        item.config.stash[_FIRST_FAILURE] = item.nodeid
    if report.when == "call" or (report.when == "setup" and not report.passed):
        _check_entry(item, report)
    if report.when == "call" and _recorded_dir(item) is not None:
        entry = item.config.stash.get(_ENTRIES, {}).get(item.nodeid)
        if entry is None and report.passed:
            report.outcome = "failed"
            report.longrepr = (
                f"{item.nodeid}: a test under authority/, corpora/ or crosscheck/ records its "
                "comparison with record_comparison"
            )
        elif entry is not None:
            entry["result"] = "passed" if report.passed else "failed"
    if report.skipped or hasattr(report, "wasxfail"):
        report.outcome = "failed"
        if hasattr(report, "wasxfail"):
            # pytest does not count a failed report carrying wasxfail as a failure
            del report.wasxfail
        report.longrepr = (
            f"{item.nodeid}: a run-time skip or xfail is forbidden; "
            "a missing fixture is a failure and a requirement CI lacks is a tier marker"
        )
    return report


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(
    collector: pytest.Collector,
) -> Generator[None, pytest.CollectReport, pytest.CollectReport]:
    # a module-level pytest.skip(allow_module_level=True) or importorskip skips at collection
    report = yield
    if report.skipped:
        report.outcome = "failed"
        report.longrepr = (
            f"{collector.nodeid}: a skip at collection (pytest.importorskip or a "
            "module-level pytest.skip) is forbidden; a missing "
            "requirement is a failure or a tier marker"
        )
    if report.failed and _FIRST_FAILURE not in collector.config.stash:
        # a module whose own check fails at import fails before any test runs: the first
        # failure is the file's, at collection
        collector.config.stash[_FIRST_FAILURE] = f"{report.nodeid} (collection)"
    return report


def _recorded_dir(item: pytest.Item) -> str | None:
    try:
        rel = Path(str(item.path)).resolve().relative_to(REPO / "tests")
    except ValueError:
        return None
    return rel.parts[0] if rel.parts and rel.parts[0] in RECORDED_DIRS else None


@cache
def _known_ids() -> frozenset[str]:
    """The registered method ids and the preset ids (what a check entry may cover)."""
    import yaml

    from jyotirganita.methods.presets import preset_ids

    reg = yaml.safe_load(
        (REPO / "jyotirganita" / "methods" / "registry.yaml").read_text(encoding="utf-8")
    )
    return frozenset(m["id"] for m in reg["methods"]) | frozenset(preset_ids(REPO))


def _covers(item: pytest.Item) -> list[str]:
    callspec = getattr(item, "callspec", None)
    params = callspec.params.values() if callspec is not None else ()
    known = _known_ids()
    named = sorted({v for v in params if isinstance(v, str) and v in known})
    if named:
        return named
    stem = Path(str(item.path)).stem.removeprefix("test_")
    for suffix in ("_invariants", "_presets"):
        stem = stem.removesuffix(suffix)
    hits = sorted((k for k in known if k in stem), key=len, reverse=True)
    return [hits[0]] if hits else [stem]


def _check_entry(item: pytest.Item, report: pytest.TestReport) -> None:
    try:
        rel = Path(str(item.path)).resolve().relative_to(REPO / "tests")
    except ValueError:
        return
    if not rel.parts or rel.parts[0] not in CHECK_DIRS:
        return
    checks = item.config.stash.setdefault(_CHECKS, {})
    if report.when == "call" or item.nodeid not in checks:
        checks[item.nodeid] = {
            "suite": rel.parts[0],
            "file": f"tests/{rel.as_posix()}",
            "covers": _covers(item),
            "result": "passed" if report.passed else "failed",
            **{str(k): v for k, v in item.user_properties},
        }


def _jsonable(x: object) -> object:
    """A computed value as JSON: exact numbers in the canonical ``num/den`` form."""
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, int | Fraction):
        return to_canonical(x)
    if isinstance(x, list | tuple):
        return [_jsonable(v) for v in x]
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    raise TypeError(f"a computed value is exact or text, not {type(x).__name__}")


def _fixture_entry(fixture_id: str, value: str) -> dict[str, Any]:
    from jyotirganita.data.datum import context_for, load_fixture

    path = REPO / "tests" / f"{fixture_id}.yaml"
    if not path.is_file():
        raise pytest.UsageError(
            f"no fixture file for {fixture_id} (a missing fixture is a failure)"
        )
    fx = load_fixture(path, context_for(REPO), repo=REPO)
    named = [v for v in fx.raw["values"] if v["name"] == value]
    if not named:
        raise pytest.UsageError(f"{fixture_id} has no printed value {value}")
    return {
        "fixture": fx.id,
        "source": fx.raw["source"],
        "edition_page": named[0].get("edition_page", fx.raw["edition_page"]),
        "pdf_page": named[0].get("pdf_page", fx.raw["pdf_page"]),
        "class": fx.cls,
        "methods": list(fx.methods),
        "datum_keys": list(fx.datum_keys),
        "fixture_status": fx.status,
        "value": value,
        "printed": named[0]["value"],
    }


@pytest.fixture
def record_comparison(request: pytest.FixtureRequest) -> Any:
    """Record this test's comparison for ``reports/test_summary.json``.

    Authority tests: ``record_comparison(fixture=<id>, value=<printed value
    name>, computed=..., tolerance=..., tolerance_reason=...)``, with
    ``method=<registry id>`` where the test runs the fixture under one of the
    methods it names (the ledger then credits that method only). Corpus and
    cross-check tests: ``record_comparison(id=..., source=..., methods=[...],
    datum_keys=[...], printed=..., computed=..., tolerance=...,
    tolerance_reason=...)``.
    """
    item = request.node
    kind = _recorded_dir(item)
    if kind is None:
        raise pytest.UsageError(
            "record_comparison serves tests under authority/, corpora/, crosscheck/"
        )
    entries = item.config.stash.setdefault(_ENTRIES, {})

    def record(**fields: Any) -> None:
        if item.nodeid in entries:
            raise pytest.UsageError(f"{item.nodeid} records one comparison; split the test")
        for need in ("computed", "tolerance", "tolerance_reason"):
            if need not in fields:
                raise pytest.UsageError(f"record_comparison needs {need}")
        if kind == "authority":
            allowed = {"fixture", "value", "method", "computed", "tolerance", "tolerance_reason"}
            extra = set(fields) - allowed
            if extra or "fixture" not in fields or "value" not in fields:
                raise pytest.UsageError(
                    "an authority test names fixture and value and nothing it could copy"
                )
            entry = _fixture_entry(fields["fixture"], fields["value"])
            if "method" in fields:
                if not isinstance(fields["method"], str):
                    raise pytest.UsageError("record_comparison's method is a registry id")
                entry["method"] = fields["method"]
        else:
            missing = {"id", "source", "methods", "datum_keys", "printed"} - set(fields)
            if missing:
                raise pytest.UsageError(f"record_comparison needs {sorted(missing)}")
            entry = {
                k: _jsonable(fields[k])
                for k in ("id", "source", "methods", "datum_keys", "printed")
            }
        entry.update(
            kind=kind,
            computed=_jsonable(fields["computed"]),
            tolerance=_jsonable(fields["tolerance"]),
            tolerance_reason=str(fields["tolerance_reason"]),
            result="pending",
        )
        entries[item.nodeid] = entry

    return record


def _git_head() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out.stdout.strip()


def _record(session: pytest.Session, exitstatus: int) -> dict[str, Any]:
    files = [
        {"path": p.relative_to(REPO).as_posix(), "sha256": file_sha256(p)}
        for p in loaded_data_files()
    ]
    return {
        "result": "passed" if exitstatus == 0 else "failed",
        "tests": session.testscollected,
        "failed": session.testsfailed,
        "data_files": files,
        "data_hash": files_digest((f["path"], f["sha256"]) for f in files),
        "commit": _git_head(),
        "date": datetime.now(UTC).date().isoformat(),
        "environment": {
            "python": platform.python_version(),
            "implementation": sys.implementation.name,
            "platform": platform.platform(),
        },
    }


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config
    out = config.getoption("--mutate-out")
    if out is not None:
        patch = config.stash.get(_MUTATION, None)
        result = {
            "key": config.getoption("--mutate"),
            "built": patch.built if patch is not None else 0,
            "read": config.getoption("--mutate") in config.stash[_PROBE].read,
            "outside": patch.outside if patch is not None else None,
            "exitstatus": int(exitstatus),
            "tests": session.testscollected,
            "failed": session.testsfailed,
            "first_failure": config.stash.get(_FIRST_FAILURE, None),
        }
        Path(out).write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
    probe_out = config.getoption("--mutate-probe")
    if probe_out is not None:
        probe = {"exitstatus": int(exitstatus), "read": sorted(config.stash[_PROBE].read)}
        Path(probe_out).write_text(json.dumps(probe, sort_keys=True) + "\n", encoding="utf-8")
    if not config.getoption("--write-summary"):
        return
    summary: dict[str, Any] = {"schema": 1, "tiers": {}}
    if SUMMARY.is_file():
        summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    tier = config.getoption("--tier")
    summary.setdefault("tiers", {})[tier] = _record(session, int(exitstatus))
    summary.setdefault("entries", {})[tier] = dict(sorted(config.stash.get(_ENTRIES, {}).items()))
    summary.setdefault("checks", {})[tier] = dict(sorted(config.stash.get(_CHECKS, {}).items()))
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(summary, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    with SUMMARY.open("wb") as fh:
        fh.write(text.encode("ascii"))
