"""Derived records: the loader's refusals, the hash check, the sample-year re-scan.

The step bounds in
``jyotirganita/data/derived/search_step_bounds.yaml`` are derived by
``tools/step_scan.py``. This test fails when a record's hash no longer
matches the files its method loads (the method's data changed without a
re-scan), when a record no longer describes the run it bounds (its
procedures or digest), and when a re-scan of one year per method, drawn
by ``seeds.search_sample`` within the record's range, finds a sunrise
step or a day's motion above the stored bound. The loader's refusals are
tested on altered copies of the committed records. No printed value
enters here.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml
from modern_kit import records
from step_scan_kit import step_scan

from jyotirganita.data.derived import DerivedError, DerivedRecord, hash_status, load_derived
from jyotirganita.data.engine_parameters import seed

REPO = Path(__file__).resolve().parents[2]
YEAR = 365


@cache
def committed() -> dict[str, DerivedRecord]:
    return load_derived(REPO)


def _methods() -> list[str]:
    return list(step_scan().scan_methods(REPO))


def test_every_method_and_body_has_a_record() -> None:
    tool = step_scan()
    keys = set(committed())
    want = {f"derived.search.step_bound.{m}.{b}" for m in _methods() for b in tool.BODIES}
    assert want == keys


@pytest.mark.parametrize("key", sorted(committed()))
def test_hash_is_current(key: str) -> None:
    assert hash_status(REPO, committed()[key]) == "current", key


@pytest.mark.parametrize("method", _methods())
def test_record_describes_the_run(method: str) -> None:
    procs, prov = step_scan()._procedures(REPO, method, records())
    mine = [rec for rec in committed().values() if rec.method == method]
    assert mine, method
    for rec in mine:
        if rec.method == method:
            assert dict(rec.procedures) == procs, rec.key
            assert rec.parameters_sha256 == prov["parameters_sha256"], rec.key
            assert dict(rec.data_files) == dict(prov["data_files"]), rec.key


@cache
def _sample_years() -> dict[str, int]:
    rng = random.Random(seed("seeds.search_sample"))
    out = {}
    for method in _methods():
        # a method without a record draws nothing, so the others keep their years and the
        # missing one fails test_record_describes_the_run and the assertion below, by name
        rec = next((r for r in committed().values() if r.method == method), None)
        if rec is not None:
            out[method] = rng.randint(rec.from_jdn, rec.to_jdn - YEAR)
    return out


@pytest.mark.parametrize("method", _methods())
def test_sample_year_rescan_stays_under_the_bound(method: str) -> None:
    tool = step_scan()
    assert method in _sample_years(), f"{method}: no committed step-bound record"
    first = _sample_years()[method]
    last = first + YEAR - 1
    segs = [s for s in tool.segments(REPO, method, records()) if s.first <= first <= s.last]
    (seg,) = segs
    last = min(last, seg.last)
    got = tool.scan_days(tool._engine(REPO, method, seg.preset), first, last)
    for body, r in got.items():
        rec = committed()[f"derived.search.step_bound.{method}.{body}"]
        assert Fraction(r["step"]) <= rec.value, (rec.key, r["step_day"])
        if r["motion"] != tool.NOT_SERVED:
            assert Fraction(r["motion"]) <= rec.value, (rec.key, r["motion_day"])


# --- the loader's refusals ----------------------------------------------------------------


def _raw() -> list[dict[str, Any]]:
    path = REPO / "jyotirganita" / "data" / "derived" / "search_step_bounds.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(doc, list)
    return doc


def _load(tmp_path: Path, doc: Any) -> dict[str, DerivedRecord]:
    (tmp_path / "bounds.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return load_derived(REPO, root=tmp_path)


def test_copy_loads(tmp_path: Path) -> None:
    assert set(_load(tmp_path, _raw())) == set(committed())


def _altered(
    change: Mapping[str, Any] | None = None, drop: str | None = None
) -> list[dict[str, Any]]:
    doc = _raw()
    first = dict(doc[0])
    if drop is not None:
        first.pop(drop)
    first.update(change or {})
    return [first, *doc[1:]]


@pytest.mark.parametrize(
    ("doc_of", "word"),
    [
        (lambda: _altered(drop="parameters_sha256"), "parameters_sha256"),
        (lambda: _altered({"extra": 1}), "extra"),
        (lambda: _altered({"value": "about 2"}), "value"),
        (lambda: _altered({"value": "1/0"}), "value"),
        (lambda: _altered({"unit": "degree"}), "unit"),
        (lambda: [*_raw(), _raw()[0]], "twice"),
        (
            lambda: _altered({"body": "saturn" if _raw()[0]["body"] != "saturn" else "mars"}),
            "another",
        ),
        (lambda: _altered({"value": "0"}), "exceeds"),
    ],
    ids=[
        "missing_field",
        "unknown_field",
        "not_a_number",
        "zero_denominator",
        "unit",
        "twice",
        "key_body",
        "below_maximum",
    ],
)
def test_refusals(tmp_path: Path, doc_of: Any, word: str) -> None:
    with pytest.raises(DerivedError, match=word):
        _load(tmp_path, doc_of())


def test_unregistered_method_refused(tmp_path: Path) -> None:
    first = _raw()[0]
    key = f"derived.search.step_bound.no_such_method.{first['body']}"
    with pytest.raises(DerivedError, match="registry"):
        _load(tmp_path, _altered({"key": key, "method": "no_such_method"}))


def test_stale_hash_is_reported(tmp_path: Path) -> None:
    rec = next(iter(committed().values()))
    files = dict(rec.data_files)
    name = sorted(files)[0]
    files[name] = "0" * 64
    from jyotirganita.provenance.hashing import files_digest

    changed = DerivedRecord(
        **{
            **{f: getattr(rec, f) for f in rec.__dataclass_fields__},
            "data_files": files,
            "parameters_sha256": files_digest(files.items()),
        }
    )
    assert hash_status(REPO, changed) == f"stale: {name} changed"
    wrong = DerivedRecord(
        **{
            **{f: getattr(rec, f) for f in rec.__dataclass_fields__},
            "parameters_sha256": "sha256:" + "0" * 64,
        }
    )
    assert hash_status(REPO, wrong).startswith("stale: parameters_sha256")
