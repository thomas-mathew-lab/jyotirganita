"""The step-scan tool (``tools/step_scan.py``).

The scan's arithmetic on a few days against the engine it scans; the
bound's rounding (up to the next arcsecond, never below the maximum); the
ranges a method's record covers; the refusal of chunks that do not tile
the range or that were scanned under other hashes than the record's. The scan's records themselves
are checked by
``tests/unit/test_derived.py``. No printed value enters here.
"""

from __future__ import annotations

import itertools
import json
from fractions import Fraction
from pathlib import Path

import pytest
from modern_kit import records
from step_scan_kit import step_scan

from jyotirganita.core.types import JDN, AngleUnit, Nadika
from jyotirganita.data import engine_parameters

REPO = Path(__file__).resolve().parents[2]
ARCSECOND = Fraction(1, 3600)


def _signed(x: Fraction) -> Fraction:
    r = x % 360
    return r - 360 if r > 180 else r


def test_scan_days_is_the_largest_step_and_motion() -> None:
    tool = step_scan()
    engine = tool.siddhantic_run(REPO, "parahita", records()).engine
    first, last = 2167030, 2167034
    got = tool.scan_days(engine, first, last)
    for body in tool.BODIES:
        lons = []
        for j in range(first, last + 2):
            inst = engine.instant(JDN(j), Nadika(0))
            arc = engine.node(inst) if body == tool.NODE else engine.sidereal_longitude(body, inst)
            lons.append(Fraction(arc.arc.to(AngleUnit.DEGREE).value))
        steps = [abs(_signed(b - a)) for a, b in itertools.pairwise(lons)]
        assert Fraction(got[body]["step"]) == max(steps)
        assert got[body]["step_day"] == first + steps.index(max(steps))
        if body == tool.NODE:
            assert got[body]["motion"] == tool.NOT_SERVED
            continue
        motions = [
            abs(Fraction(engine.daily_motion(body, JDN(j)).to(AngleUnit.DEGREE).value))
            for j in range(first, last + 1)
        ]
        assert Fraction(got[body]["motion"]) == max(motions)


@pytest.mark.parametrize("v", [Fraction(1, 7), Fraction(3, 3600), Fraction(123456789, 10**9)])
def test_bound_rounds_up_to_the_arcsecond(v: Fraction) -> None:
    b = Fraction(step_scan()._bound_text(v))
    assert b >= v and b - v < ARCSECOND
    assert (b / ARCSECOND).denominator == 1


@pytest.mark.parametrize("v", [0.123456789, 1.0, 13.2])
def test_modern_bound_rounds_up(v: float) -> None:
    b = Fraction(step_scan()._bound_text(v))
    assert b >= Fraction(v) and b - Fraction(v) < 2 * ARCSECOND


def test_segments_cover_floor_to_horizon_cut_to_the_run() -> None:
    tool = step_scan()
    params = engine_parameters.load()
    floor = params["search.floor"].value.numerator
    horizon = params["search.horizon"].value.numerator
    run = tool.siddhantic_run(REPO, "parahita", records())
    (seg,) = tool.segments(REPO, "parahita", records())
    assert (seg.first, seg.last, seg.preset) == (max(floor, run.runs_from.value), horizon, None)
    modern = tool.segments(REPO, tool.MODERN, records())
    assert [s.preset for s in modern] == list(tool.MODERN_SEGMENTS)
    for a, b in itertools.pairwise(modern):
        assert b.first == a.last + 1


def test_chunks_tile_a_segment() -> None:
    tool = step_scan()
    seg = tool.Segment(100, 1000, None)
    cs = list(tool.chunks([seg], 300))
    assert cs[0].first == 100 and cs[-1].last == 1000
    assert all(b.first == a.last + 1 for a, b in itertools.pairwise(cs))


def test_chunks_that_do_not_tile_are_refused(tmp_path: Path) -> None:
    tool = step_scan()
    (seg,) = tool.segments(REPO, "parahita", records())
    d = tmp_path / "parahita"
    d.mkdir()
    for first, last in [(seg.first, seg.first + 9), (seg.first + 20, seg.last)]:
        body = {"step": "1/1", "step_day": first, "motion": "1/1", "motion_day": first}
        doc = {
            "method": "parahita",
            "first": first,
            "last": last,
            "preset": None,
            "bodies": dict.fromkeys(tool.BODIES, body),
        }
        (d / f"chunk_{first}_{last}.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SystemExit, match="do not tile"):
        tool.build_records(REPO, "parahita", tmp_path, records(), "2026-10-15")


def test_a_chunk_carries_the_run_hashes_and_a_stale_one_is_refused(tmp_path: Path) -> None:
    tool = step_scan()
    (seg,) = tool.segments(REPO, "parahita", records())
    short = tool.Segment(seg.first, seg.first + 1, None)
    tool.run_chunk(str(REPO), str(tmp_path), "parahita", short)
    doc = json.loads(tool._chunk_path(tmp_path, "parahita", short).read_text(encoding="utf-8"))
    procs, prov = tool._procedures(REPO, "parahita", records())
    assert doc["parameters_sha256"] == prov["parameters_sha256"]
    assert doc["procedures_sha256"] == tool.procedures_digest(procs)
    # the rest of the range as stand-in chunks with the right hashes; then one hash wrong
    rest = {k: doc[k] for k in ("parameters_sha256", "procedures_sha256")}
    body = {"step": "1/1", "step_day": seg.first, "motion": "1/1", "motion_day": seg.first}
    filler = {
        "method": "parahita",
        "first": short.last + 1,
        "last": seg.last,
        "preset": None,
        "bodies": dict.fromkeys(tool.BODIES, body),
        **rest,
    }
    fpath = tmp_path / "parahita" / f"chunk_{short.last + 1}_{seg.last}.json"
    fpath.write_text(json.dumps(filler), encoding="utf-8")
    assert tool.build_records(REPO, "parahita", tmp_path, records(), "2026-10-16")
    filler["procedures_sha256"] = "sha256:" + "0" * 64
    fpath.write_text(json.dumps(filler), encoding="utf-8")
    with pytest.raises(SystemExit, match="other hashes"):
        tool.build_records(REPO, "parahita", tmp_path, records(), "2026-10-16")
