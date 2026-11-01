"""Fixes found by code review, each pinned by a test that failed before the fix.

Engine output only, as change detectors of the route; no
printed value enters here. The days named are the
reviews' probe days.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import pairwise
from typing import Any

import pytest
from modern_kit import default_engine, records
from record_kit import GEOMETRIC, REPO
from search_kit import config as search_config
from search_kit import window_doc

from jyotirganita import api
from jyotirganita.calendar import elements
from jyotirganita.calendar.months import (
    MeanSun,
    MonthNotFound,
    MonthStream,
    NearestEntryMonthStream,
)
from jyotirganita.calendar.occurrences import SourceDay, day_occurrences
from jyotirganita.config import open_config
from jyotirganita.core.calendar import Weekday
from jyotirganita.core.eras import Sun
from jyotirganita.core.types import JDN, Nadika
from jyotirganita.errors import Refusal
from jyotirganita.search.evaluate import Evaluator
from jyotirganita.search.query import compile_query

KOZHIKODE = "kerala/kozhikode"
THRISSUR = "kerala/thrissur"
NADIS = 60


def _day(jdn: int, labels: dict[str, int], **over: Any) -> SourceDay:
    """A synthetic civil day of 60 nāḍikās, sunrise at its start."""
    kw: dict[str, Any] = {
        "jdn": JDN(jdn),
        "length": Nadika(NADIS),
        "sunrise": Nadika(0),
        "sunset": Nadika(NADIS // 2),
        "midnight": None,
        "labels": labels,
        "endings": dict.fromkeys(labels, Nadika(NADIS // 2)),
        "per_span": dict.fromkeys(labels, Nadika(NADIS)),
        "flags": (),
        "standard": "test",
        "sunrise_after_midnight": None,
        "weekday": Weekday(0),
        "ahargana": None,
    }
    kw.update(over)
    return SourceDay(**kw)


# --- an ending past the chord's 60 nāḍikās belongs to the next day ---------------------------


def test_an_ending_past_the_chord_runs_past_the_day() -> None:
    """The sliver from 60 nāḍikās to a longer day's end is the next day's."""
    long_day = Nadika(NADIS) + Nadika(Fraction(1, 50))
    sd = _day(
        0,
        {"tithi": 3},
        length=long_day,
        endings={"tithi": Nadika(NADIS) + Nadika(Fraction(1, 100))},
        chord_end=Nadika(NADIS),
    )
    occ = day_occurrences(sd, "tithi")
    assert len(occ) == 1 and occ[0].index == 3 and occ[0].end is None


def test_the_reviewed_day_has_no_ending_in_the_sliver() -> None:
    """parahita_kerala at Kozhikode, JDN 2420774 (day 60.0133 nāḍikās)."""
    cfg = open_config(REPO, "parahita_kerala", KOZHIKODE, records=records())
    jdn = JDN(2420774)
    sd = cfg.calendar.source.day(jdn)
    assert sd.length > Nadika(NADIS)
    for e in elements.ELEMENTS:
        if e == elements.RASI.id:
            continue
        for o in day_occurrences(sd, e)[:-1]:
            assert o.end is not None and o.end < Nadika(NADIS), (e, o)
    nxt = cfg.calendar.source.day(jdn.plus_days(1))
    for e in ("tithi", "karana"):
        assert day_occurrences(sd, e)[-1].index == day_occurrences(nxt, e)[0].index


# --- the search timeline keeps a change between two days -------------------------------------


def test_the_timeline_keeps_a_seam_between_days() -> None:
    """suryasiddhanta_kerala at Thrissur, JDN 2415296: the tithi changes between sunrises."""
    cfg = search_config("suryasiddhanta_kerala", THRISSUR)
    probe = compile_query(
        {
            "reading_profile": "kerala_default",
            "window": window_doc(2415296, 2415297),
            "constraints": [{"element": "weekday", "value": 1}],
        },
        cfg,
    )
    ev = Evaluator(cfg, probe)
    today, nxt = JDN(2415296), JDN(2415297)
    last = ev.view(today).occurrences("tithi")[-1].index
    first = ev.view(nxt).occurrences("tithi")[0].index
    assert last != first, "the seam day no longer has a seam"
    tl = ev.timeline("tithi", nxt, 1, 1)
    assert tl.index_at(Fraction(1, 1000)) == first
    times = [t for t, _ in tl.transitions]
    assert all(a <= b for a, b in pairwise(times))


# --- the geometric sunrise serves its first year ---------------------------------------------


def test_the_geometric_sunrise_serves_its_first_year() -> None:
    """parahita_kerala at Kozhikode under modern_geometric:modern_smh.

    Every day up to about 476 days after ``runs_from`` was refused for a
    kernel instant two years earlier; now only the days before the first
    month the geometric range serves are refused, by name.
    """
    cfg = open_config(
        REPO, "parahita_kerala", KOZHIKODE, records=records(), **{"procedure.sunrise": GEOMETRIC}
    )
    rec = api.day(cfg, cfg.runs_from.plus_days(60))
    assert rec["masa"]["day"] >= 1
    with pytest.raises(Refusal) as info:
        api.day(cfg, cfg.runs_from)
    assert info.value.field == "date" and "no month start" in info.value.message


# --- a year start before a modern run's range is a named refusal -----------------------------


def test_a_year_start_before_the_modern_range_is_refused_by_name() -> None:
    """modern_smh at Kozhikode, 100 days after ``runs_from``: a bare ValueError escaped."""
    cfg = open_config(REPO, "modern_smh", KOZHIKODE, records=records())
    with pytest.raises(Refusal) as info:
        api.day(cfg, cfg.runs_from.plus_days(100))
    assert info.value.field == "date" and "before the run's range" in info.value.message


# --- the first month the run serves is served by the year count too --------------------------


def _turning_source(runs_from: int) -> Any:
    """The Sun enters rāśi m + 1 in civil day 30 m + 5, 30 nāḍikās after its start."""

    class Source:
        id = "test"

        @property
        def runs_from(self) -> JDN:
            return JDN(runs_from)

        def day(self, jdn: JDN) -> SourceDay:
            rasi = (jdn.value - 6) // 30 % 12 + 1
            return _day(jdn.value, {elements.RASI.id: rasi})

    return Source()


def test_the_first_served_entry_agrees_with_month_of() -> None:
    """An entry 11 days after ``runs_from`` opens a month ``month_of`` serves; the year count
    served it as before the run."""
    mean = MeanSun(1, 360, 0, JDN(0))  # Meṣa entries on days 360 k
    runs_from = 5 * 360 - 11
    stream = NearestEntryMonthStream(_turning_source(runs_from), mean, "following_day", {})
    month = stream.month_of(JDN(5 * 360 + 6))
    assert (month.rasi, month.first_day) == (1, JDN(5 * 360 + 6))
    got = stream.nth_start_after("sankranti.mesha", Sun.TRUE, JDN(4 * 360), 1)
    assert got == JDN(5 * 360 + 6)
    with pytest.raises(MonthNotFound):
        stream.nth_start_after("sankranti.mesha", Sun.TRUE, JDN(3 * 360), 1)


# --- month-rule parameters and the cached own start ------------------------------------------


@pytest.mark.parametrize(
    ("rule", "params"),
    [
        ("aparahna_parts", {"parts": Fraction(0), "within": Fraction(0)}),
        ("aparahna_parts", {"parts": Fraction(5), "within": Fraction(6)}),
        ("fixed_tropical_offset", {"offset": Fraction(0), "days_after": Fraction(3, 2)}),
    ],
)
def test_month_rule_parameters_are_checked(rule: str, params: dict[str, Fraction]) -> None:
    mean = MeanSun(1, 360, 0, JDN(0))
    with pytest.raises(ValueError, match=rule):
        MonthStream(_turning_source(0), mean, rule, params)


def test_moved_own_start_checks_the_sun_on_a_cached_answer() -> None:
    mean = MeanSun(1, 360, 0, JDN(0))
    stream = MonthStream(_turning_source(0), mean, "following_day", {})
    stream.moved_own_start("sankranti.mesha", Sun.TRUE, JDN(360 * 3 + 6))
    with pytest.raises(ValueError, match="sun: true"):
        stream.moved_own_start("sankranti.mesha", Sun.MEAN, JDN(360 * 3 + 6))


# --- the Sūrya-siddhānta's bhujāntara is on the place, not in the sunrise --------------------


@pytest.mark.parametrize(
    "preset", ["suryasiddhanta_kerala", "suryasiddhanta_paramesvara_recension_kerala"]
)
def test_surya_siddhanta_refuses_text_bhujantara_and_serves_a_modern_equation(
    preset: str,
) -> None:
    """``text_bhujantara`` added nothing although no equation is in the SS sunrise."""
    cfg = open_config(REPO, preset, THRISSUR, records=records())
    day = JDN(2447996)  # 1990, inside smh2016's table
    with pytest.raises(Refusal) as info:
        api.day(cfg, day, derived_ut="apparent:text_bhujantara")
    assert info.value.field == "derived_ut" and "true place" in info.value.message
    # the same clock reading in apparent time is the mean one less the equation
    # E = apparent − mean, in days (a sign or a unit);
    # 200 days later, where E is some 1.6e-2 days in size
    for jdn in (day, JDN(day.value + 200)):
        mean = api.day(cfg, jdn, derived_ut="mean")["derived_ut"]
        app = api.day(cfg, jdn, derived_ut="apparent:modern:modern_smh")["derived_ut"]
        e = app["equation_of_time"]["apparent_minus_mean_days"]
        assert e != 0
        assert app["value"] - mean["value"] == pytest.approx(-e, abs=1e-9)


# --- a saṅkrānti result carries the month rule's flag ----------------------------------------


def test_sankranti_results_carry_the_month_rule_flag() -> None:
    """parahita_kerala at Kozhikode, January–February 1900: ``assigned_day1`` is the
    provisional month rule's, and the result says so as a day record does."""
    # the flag's form is the profile's (regions/base.py docstring), not the helper's
    # output; the alternative rule names its own
    for sets, flag in (
        ({}, "provisional:regions.kerala.month_rule"),
        ({"conventions.month_rule": "following_day"}, "provisional:following_day"),
    ):
        cfg = open_config(REPO, "parahita_kerala", KOZHIKODE, records=records(), **sets)
        assert cfg.calendar.month_rule_flags() == (flag,)
        got = list(api.sankrantis(cfg, (JDN(2415020), JDN(2415070))))
        assert len(got) == 2
        for s in got:
            assert flag in s["flags"]
            assert flag in api.day(cfg, JDN(s["assigned_day1"]))["flags"]


# --- input checks at the data boundary -------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "1 January AD 2000 BC",  # A.D. and B.C. both
        "1 January 0 BC",  # no year zero in print
        "1 January AD 0",
        "Saturdaygarbage, 1 January 2000",  # not a weekday name
        "S, 1 January 2000",  # ambiguous initial
    ],
)
def test_a_malformed_printed_date_is_refused(text: str) -> None:
    from jyotirganita.core.calendar import parse_printed_date
    from jyotirganita.core.types import GregorianDate

    with pytest.raises(ValueError):
        parse_printed_date(text, GregorianDate)


def test_a_printed_weekday_abbreviation_still_parses() -> None:
    from jyotirganita.core.calendar import parse_printed_date
    from jyotirganita.core.types import GregorianDate

    assert parse_printed_date("Sat, 1 January 2000", GregorianDate) == GregorianDate(2000, 1, 1)


def test_a_misspelt_counting_is_refused() -> None:
    from jyotirganita.core.eras import first_day_of_year

    with pytest.raises(ValueError, match="counting"):
        first_day_of_year(None, 1, "x", "elasped", None)  # type: ignore[arg-type]


@pytest.mark.parametrize("text", ["1/1\n", "1٠/1"])
def test_canonical_fractions_are_strict(text: str) -> None:
    from jyotirganita.core.exact import from_canonical

    with pytest.raises(ValueError):
        from_canonical(text)


def test_root_bisection_stays_exact_on_an_integer_bracket() -> None:
    """An int bracket went to floats and stopped shrinking; each look is
    counted, so a regression fails instead of hanging."""
    from jyotirganita.siddhantic.endings import root_bisection

    looks = 0

    def crossed(x: Fraction) -> bool:
        nonlocal looks
        looks += 1
        assert looks <= 200, "the bisection does not shrink its bracket"
        return x >= Fraction(1, 3)

    got = root_bisection(crossed, 0, 1, Fraction(1, 10**25))  # type: ignore[arg-type]
    assert isinstance(got, Fraction) and Fraction(0) <= got - Fraction(1, 3) <= Fraction(1, 10**25)


def test_text_replacements_do_not_depend_on_order() -> None:
    from types import SimpleNamespace

    from jyotirganita.siddhantic.text import MissingDatum, TextData

    def rec(k: str, v: int) -> Any:
        return SimpleNamespace(key=f"texts.t.{k}", value=v, kind="value", raw={"procedure": "p"})

    records = {r.key: r for r in (rec("a", 1), rec("b", 2), rec("c", 3))}
    with pytest.raises(MissingDatum, match="itself replaced"):
        TextData("t", records, {"texts.t.a": "texts.t.b", "texts.t.b": "texts.t.c"})
    data = TextData("t", records, {"texts.t.a": "texts.t.c"})
    assert data.integer("a") == 3
    assert sorted(r.key for r in data.records_with("procedure")) == ["texts.t.b", "texts.t.c"]


# --- crash paths and the eclipse contacts ----------------------------------------------------


def test_a_fraction_an_ulp_below_midnight_carries_to_the_next_day() -> None:
    """f - floor(f) rounds to 1.0 for f a few ulp below 0."""
    from jyotirganita.core.types import UT1, UTC, civil_from_utc, mean_time_from_ut1

    just_below = 0.25 - 2.0**-54  # with a quarter-day offset, the local fraction is −2⁻⁵⁴
    a = civil_from_utc(UTC(2451545, just_below), Fraction(1, 4), "test")
    b = mean_time_from_ut1(UT1(2451545, just_below), Fraction(1, 4), "test")
    for got in (a, b):
        assert got.jdn == JDN(2451546) and got.local_fraction == 0.0
    t = UTC(2451545, -(2.0**-60))
    assert (t.jd_whole, t.jd_fraction) == (2451545, 0.0)


def test_the_entry_walk_does_not_stall_on_a_grid_point() -> None:
    """A step of 1/24 day is not a binary fraction; the walk re-derived its index."""
    from jyotirganita.core.types import TT
    from jyotirganita.modern.roots import RootFinder

    root = TT(2451545, 0.9)

    def g(t: TT) -> float:
        return (t.jd_whole - root.jd_whole) + (t.jd_fraction - root.jd_fraction)

    finder = RootFinder(1 / 24, 1e-9, 100)
    got = finder.crossing_after(g, TT(2451545, 0.0), 0.0, 2.0)
    assert abs(g(got)) <= 1e-9


def test_the_month_locator_survives_a_start_just_past_mesa() -> None:
    """A quarter point within ~2.6 days after a Meṣa entry left g ≥ 0 after one shift."""
    from types import SimpleNamespace

    from jyotirganita.core.types import TT, FloatDays
    from jyotirganita.modern.source import mean_locator

    year = 365.25  # a uniform Sun: a test fixture, not a datum
    entry = TT(2451545, 0.0)

    def sidereal_at(body: str, t: TT) -> Any:
        days = (t.jd_whole - entry.jd_whole) + (t.jd_fraction - entry.jd_fraction)
        return SimpleNamespace(arc=SimpleNamespace(value=(days * 360 / year) % 360))

    lo = entry + FloatDays(1 - 4 * year)  # the quarter point lies one day after the entry
    hi = lo + FloatDays(16 * year)
    fake = SimpleNamespace(
        range_tt=lambda: (lo, hi),
        element_roots=default_engine().element_roots,
        sidereal_at=sidereal_at,
    )
    sun = mean_locator(fake)  # type: ignore[arg-type]
    assert sun.revolutions > 0


def test_the_cli_reports_an_engine_fault_as_internal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A RootError reached the user as a traceback."""
    from jyotirganita.io import cli
    from jyotirganita.modern.roots import RootError

    def boom(args: Any, out: Any) -> int:
        raise RootError("no crossing within 1 days")

    monkeypatch.setitem(cli.COMMANDS, "day", boom)
    status = cli.main(["day", "--preset", "parahita_kerala", "--date", "jdn:2435023"])
    assert status == cli.EXIT_INTERNAL
    assert "internal: RootError: no crossing" in capsys.readouterr().err


def test_search_output_is_written_part_and_rename(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """search --jsonl opened its target directly; a refusal part way truncated it."""
    import json

    from jyotirganita.io import cli

    target = tmp_path / "out.jsonl"
    target.write_text("earlier\n")
    q = tmp_path / "q.json"
    q.write_text(
        json.dumps(
            {
                "reading_profile": "kerala_default",
                "window": window_doc(2435023, 2435024),
                "constraints": [{"element": "weekday", "value": 1}],
            }
        )
    )
    argv = ["search", "--preset", "parahita_kerala", "--observer", KOZHIKODE, "--query", str(q)]
    argv += ["--jsonl", str(target)]
    real = cli.write_jsonl  # type: ignore[attr-defined]

    def part_way(candidates: Any, out: Any) -> int:
        out.write(b"partial")
        raise Refusal("window.to", "refused part way")

    monkeypatch.setattr(cli, "write_jsonl", part_way)
    assert cli.main(argv) == cli.EXIT_REFUSED
    assert target.read_text() == "earlier\n"
    monkeypatch.setattr(cli, "write_jsonl", real)
    assert cli.main(argv) == 0
    assert target.read_text() != "earlier\n"
    assert not list(tmp_path.glob(".*.part"))


def test_seconds_that_round_to_midnight_are_refused_by_name() -> None:
    """23:59:59.9999999999999 rounded to a local fraction of 1.0."""
    from jyotirganita.io.dates import DateSyntaxError, parse_cli_instant

    with pytest.raises(DateSyntaxError, match="next day's midnight"):
        parse_cli_instant("gregorian:2022-08-17T23:59:59.9999999999999/ist", "modern", "ist")


def test_an_umbral_eclipse_is_seen_from_its_umbral_contacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The total lunar eclipse of 2022-11-08 at Kozhikode: visibility reads the umbral
    contacts, not the penumbral ones."""
    cfg = search_config("modern_iers", KOZHIKODE)
    day = 2459892
    probe = compile_query(
        {
            "reading_profile": "kerala_default",
            "window": window_doc(day, day),
            "constraints": [{"element": "weekday", "value": 1}],
        },
        cfg,
    )
    ev = Evaluator(cfg, probe)
    seen: list[Any] = []
    real = Evaluator._visible

    def spy(self: Evaluator, body: str, greatest: Any, contacts: Any) -> bool:
        seen.append(contacts)
        return real(self, body, greatest, contacts)

    monkeypatch.setattr(Evaluator, "_visible", spy)
    found = ev.eclipses(JDN(day))
    assert [e["kind"] for e in found] == ["lunar"] and found[0]["type"] == "total"
    g = found[0]["_greatest"]
    le = ev.engine.eclipses().lunar(g + _days(-1), g + _days(1))
    assert le is not None and seen[-1] == le.partial != le.penumbral


def _days(n: int) -> Any:
    from jyotirganita.core.types import FloatDays

    return FloatDays(n)


# --- the core: layers and carries ------------------------------------------------------------


def test_a_true_motion_carry_before_the_cara_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """_pre_cara passed a gati of 0: a true-motion carry there gave the mean-sunrise value
    silently. No shipped text has one; the carry is altered here, on this test's
    engine only."""
    from dataclasses import replace

    from jyotirganita.core.memo import DayMemo
    from jyotirganita.siddhantic.engine import EngineRefusal

    eng = open_config(REPO, "parahita_kerala", KOZHIKODE, records=records()).run.engine
    altered = {
        b: [
            replace(c, acts_on="true_after_equation", motion="true")
            if c.slot == "carry.bhujantara"
            else c
            for c in cs
        ]
        for b, cs in eng._carries.items()
    }
    monkeypatch.setattr(eng, "_carries", altered)
    monkeypatch.setattr(eng, "_pre", DayMemo())
    with pytest.raises(EngineRefusal, match="before the cara"):
        eng._pre_cara(JDN(2435023))


# --- assembly and time scales ----------------------------------------------------------------


def test_a_missing_kernel_for_the_equation_of_time_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """b4 opened the modern equation of time to the SS methods; an unfetched kernel then
    escaped as a bare KernelError."""
    import jyotirganita.methods.presets as presets
    from jyotirganita.modern.kernels import KernelError

    def unfetched(*a: Any, **k: Any) -> Any:
        raise KernelError("kernel 'de441' is not fetched")

    monkeypatch.setattr(presets, "modern_run", unfetched)
    cfg = open_config(REPO, "suryasiddhanta_kerala", THRISSUR, records=records())
    with pytest.raises(Refusal) as info:
        api.day(cfg, JDN(2447996), derived_ut="apparent:modern:modern_antiquity")
    assert info.value.field == "derived_ut" and "not fetched" in info.value.message


@pytest.mark.parametrize("seconds", ["1/0", "1e400"])
def test_a_constant_delta_t_that_is_not_a_number_is_refused(seconds: str) -> None:
    """constant:1/0 raised ZeroDivisionError, constant:1e400 OverflowError."""
    cfg = open_config(REPO, "parahita_kerala", KOZHIKODE, records=records())
    with pytest.raises(Refusal) as info:
        api.day(cfg, JDN(2435023), derived_ut="mean", derived_tt=f"constant:{seconds}")
    assert info.value.field == "derived_tt"


def test_a_float_arc_an_ulp_below_zero_stays_below_the_circle() -> None:
    """-x % 360.0 is 360.0 for tiny x: a tithi 31 of 30; 0 put it on the far
    side of the new moon, a tithi 1."""
    from jyotirganita.core.types import AngleUnit, FloatArc

    circle = FloatArc(360.0, AngleUnit.DEGREE)
    reduced = FloatArc(-1e-17, AngleUnit.DEGREE).mod_arc(circle).value
    assert 0.0 < reduced < 360.0
    sun = FloatArc(100.0, AngleUnit.DEGREE)
    moon = FloatArc(100.0 - 1.4e-14, AngleUnit.DEGREE)
    assert elements.index(elements.TITHI, sun, moon) == 30
    assert elements.index(elements.KARANA, sun, moon) == 60


def test_a_negative_sexagesimal_coordinate_keeps_its_sign() -> None:
    """[-10, 30] read as −9.5° (no shipped datum is negative)."""
    from types import SimpleNamespace

    from jyotirganita.regions.places import _degrees

    rec: Any = SimpleNamespace(key="k", value=[-10, 30])
    assert _degrees(rec, "test") == Fraction(-21, 2)
    rec = SimpleNamespace(key="k", value=[10, 30, 36])
    assert _degrees(rec, "test") == Fraction(10) + Fraction(30, 60) + Fraction(36, 3600)


@pytest.mark.parametrize("value", [[True, 30], [10, 30, 36, 42], [10, "30"], [10, 30.5]])
def test_a_sexagesimal_coordinate_of_the_wrong_shape_is_refused(value: list[object]) -> None:
    """[True, 30] read as 1.5°, four parts were summed."""
    from types import SimpleNamespace

    from jyotirganita.regions.places import PlaceError, _degrees

    rec: Any = SimpleNamespace(key="k", value=value)
    with pytest.raises(PlaceError, match="is not \\[deg"):
        _degrees(rec, "test")


def test_an_unmapped_weekday_rule_or_era_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bare KeyErrors in method assembly."""
    import jyotirganita.methods.compose as compose

    monkeypatch.setattr(compose, "WEEKDAY_FIRST", {})
    with pytest.raises(Refusal, match="weekday rule"):
        open_config(REPO, "parahita_kerala", KOZHIKODE, records=records())
    monkeypatch.undo()
    era = {k: "no_such_era" for k in compose.TIME_BASE_ERA}
    monkeypatch.setattr(compose, "TIME_BASE_ERA", era)
    with pytest.raises(Refusal, match="not loaded"):
        open_config(REPO, "parahita_kerala", KOZHIKODE, records=records())


# --- methods, presets and places -------------------------------------------------------------


@pytest.mark.parametrize("methods", ["null", "7"])
def test_a_malformed_methods_list_is_a_registry_error(tmp_path: Any, methods: str) -> None:
    """methods: null raised a TypeError before the schema check."""
    from jyotirganita.data.datum import context_for
    from jyotirganita.methods.registry import RegistryError, load_registry

    path = tmp_path / "registry.yaml"
    path.write_text(f"methods: {methods}\n")
    with pytest.raises(RegistryError):
        load_registry(path, context_for(REPO).sources)


def test_a_layer_rate_that_is_a_gap_is_refused() -> None:
    """A gap rate was skipped, leaving its element uncorrected silently."""
    from dataclasses import replace
    from types import SimpleNamespace

    from jyotirganita.methods.compose import _layer
    from jyotirganita.siddhantic.engine import EngineRefusal
    from jyotirganita.siddhantic.text import TextData

    key = "texts.aryabhatiya.sakabda_samskara.rates.moon"
    gapped = dict(records().data)
    gapped[key] = replace(gapped[key], kind="gap")
    fake: Any = SimpleNamespace(data=gapped)  # _layer reads the records' data only
    with pytest.raises(EngineRefusal, match="a layer rate is a gap"):
        _layer(TextData("aryabhatiya", gapped), "sakabda_samskara", fake)


def _preset_doc(preset_id: str) -> Any:
    from jyotirganita.data.yamlio import load_exact

    return load_exact(REPO / "jyotirganita" / "methods" / "presets" / f"{preset_id}.yaml")


def test_a_parsed_modern_preset_does_not_share_its_document() -> None:
    """Changing the document after parsing changed the parsed preset."""
    from jyotirganita.methods.presets import parse_preset

    doc = _preset_doc("modern_iers")
    p = parse_preset(doc, "test", REPO)
    assert p.modern is not None
    before = dict(p.modern["delta_t"])
    doc["modern"]["delta_t"]["seconds"] = "3600"
    assert p.modern["delta_t"] == before


def test_preset_lists_and_numbers_are_checked() -> None:
    """A string output list became its characters; a null pin made the observer optional;
    "1/0" escaped as ZeroDivisionError; a coefficient string became digits."""
    from jyotirganita.methods.presets import PresetError, modern_config, parse_preset

    doc = _preset_doc("parahita_kerala")
    doc["output"]["elements"] = "tithi"
    with pytest.raises(PresetError, match=r"output\.elements is a list"):
        parse_preset(doc, "test", REPO)
    doc = _preset_doc("parahita_kerala")
    doc["observer"] = {"pinned": None}
    with pytest.raises(PresetError, match=r"observer\.pinned"):
        parse_preset(doc, "test", REPO)
    cfg = open_config(REPO, "modern_iers", KOZHIKODE, records=records())
    doc = _preset_doc("modern_iers")
    doc["modern"]["delta_t"] = {**doc["modern"]["delta_t"], "id": "constant", "seconds": "1/0"}
    p = parse_preset(doc, "test", REPO)
    with pytest.raises(PresetError, match="not a number"):
        modern_config(p, cfg.conventions, records())
    doc = _preset_doc("modern_iers")
    doc["modern"]["ayanamsa"] = {**doc["modern"]["ayanamsa"], "coefficients": "123"}
    p = parse_preset(doc, "test", REPO)
    with pytest.raises(PresetError, match="coefficients is a list"):
        modern_config(p, cfg.conventions, records())


def test_a_non_finite_angle_is_refused() -> None:
    """An infinite angle became a NaN longitude."""
    from jyotirganita.core.types import AngleUnit, FloatArc

    for bad in (float("inf"), float("nan"), -float("inf")):
        with pytest.raises(ValueError, match="finite"):
            FloatArc(bad, AngleUnit.DEGREE)


def test_the_tropical_to_sidereal_conversions_check_their_arguments() -> None:
    """An Ayanamsa passed as the longitude gave a plausible 0°."""
    from jyotirganita.core.types import (
        AngleUnit,
        Ayanamsa,
        FloatArc,
        MeanOfDate,
        sidereal_from_tropical_mean,
    )

    a = Ayanamsa(FloatArc(20.0, AngleUnit.DEGREE), MeanOfDate, None, "test")
    with pytest.raises(TypeError, match="TropicalLongitude"):
        sidereal_from_tropical_mean(a, a)  # type: ignore[arg-type]


def test_a_tabled_coordinate_gets_the_user_route_s_checks() -> None:
    """[10, 60] read as 11° and an empty list as an IndexError."""
    from types import SimpleNamespace

    from jyotirganita.regions.places import PlaceError, _degrees

    for bad in ([10, 60], [10, 30, 60], [10, -1], []):
        rec: Any = SimpleNamespace(key="k", value=bad)
        with pytest.raises(PlaceError, match="not \\[deg, min"):
            _degrees(rec, "test")


def test_a_set_key_with_a_trailing_newline_is_refused() -> None:
    """``$`` matched before a final newline, so "procedure.sunrise\\n" passed."""
    from jyotirganita.config import check_set_keys

    check_set_keys({"procedure.sunrise": "x"})
    for key in ("procedure.sunrise\n", "conventions.era.kollam.year_start\n"):
        with pytest.raises(Refusal, match="is not a --set key"):
            check_set_keys({key: "x"})


@pytest.mark.parametrize("key", ["records", "repo", "preset_id", "observer"])
def test_a_set_key_named_like_a_parameter_is_refused_by_name(key: str) -> None:
    """open_search(sets={"records": ...}) raised a TypeError before any check."""
    from jyotirganita.search.config import open_search

    with pytest.raises(Refusal) as info:
        open_search(REPO, "parahita_kerala", KOZHIKODE, sets={key: "x"}, records=records())
    assert info.value.field == "set"
    if key != "records":  # the API's own keyword
        with pytest.raises(Refusal) as info:
            open_config(REPO, "parahita_kerala", KOZHIKODE, records=records(), **{key: "x"})
        assert info.value.field == "set"


def test_name_indices_must_run_from_one_to_the_count() -> None:
    """Indices 1…29 and 31 passed a count of 30."""
    from jyotirganita.data.datum import NAMES_FILE
    from jyotirganita.data.yamlio import load_exact
    from jyotirganita.regions.base import ProfileError, _names

    doc = load_exact(REPO / "jyotirganita" / "regions" / "kerala" / NAMES_FILE)
    _names(doc, records().data, "test")
    cls = doc["names"][0]["class"]
    last = max(n["index"] for n in doc["names"] if n["class"] == cls)
    for n in doc["names"]:
        if n["class"] == cls and n["index"] == last:
            n["index"] = last + 1
    with pytest.raises(ProfileError, match="its indices are not"):
        _names(doc, records().data, "test")


# --- the modern engine -----------------------------------------------------------------------


def test_a_kernel_chain_that_misses_the_barycentre_or_cycles_is_refused() -> None:
    """A chain C → T was read as barycentric; a cycle looped forever."""
    from jyotirganita.modern.kernels import KernelError, check_chains

    check_chains("k", {399: 3, 301: 3, 3: 0, 10: 0})
    with pytest.raises(KernelError, match="ends at 5"):
        check_chains("k", {399: 5})
    with pytest.raises(KernelError, match="cycle"):
        check_chains("k", {1: 2, 2: 1})


def test_opening_a_kernel_checks_its_chains(monkeypatch: pytest.MonkeyPatch) -> None:
    """The test above pins the helper; this one its call at open."""
    import jyotirganita.modern.kernels as kernels

    seen: list[tuple[str, dict[int, int]]] = []
    monkeypatch.setattr(kernels, "check_chains", lambda k, p: seen.append((k, dict(p))))
    kernels.Ephemeris.open("de440")
    assert [k for k, _ in seen] == ["de440"] and seen[0][1][399] == 3


def test_a_kernel_span_with_one_end_is_refused(tmp_path: Any) -> None:
    """An entry with a hash and from_jd but no to_jd loaded as recorded."""
    from jyotirganita.modern.kernels import REGISTRY_PATH, KernelError, load_registry

    text = REGISTRY_PATH.read_text(encoding="utf-8")
    bad = text.replace(
        "span: {from_jd: '2287184.5', to_jd: '2688976.5'}", "span: {from_jd: '2287184.5'}"
    )
    assert bad != text
    path = tmp_path / "kernels.yaml"
    path.write_text(bad, encoding="utf-8")
    with pytest.raises(KernelError, match="one end only"):
        load_registry(path)


def test_a_non_finite_printed_coefficient_is_refused() -> None:
    """The strings NaN, Infinity and 1e309 passed the float fallback."""
    from jyotirganita.modern.tables import TableError, number

    assert number("1.5e3") == 1500.0
    for bad in ("NaN", "Infinity", "-inf", "1e309"):
        with pytest.raises(TableError, match="finite"):
            number(bad)


def test_the_golden_section_search_checks_its_window_and_its_last_step() -> None:
    """A reversed window "converged" at once; a bracket closed by the last permitted step
    was refused."""
    from jyotirganita.core.types import TT
    from jyotirganita.modern.eclipses import golden_minimum, window

    def flat(t: TT) -> float:
        return 0.0

    with pytest.raises(ValueError, match="not before its end"):
        golden_minimum(flat, TT(2451546, 0.0), TT(2451545, 0.0), 0.7, 5)
    got = golden_minimum(flat, TT(2451545, 0.0), TT(2451546, 0.0), 0.7, 1)
    assert got.jd_whole == 2451545
    with pytest.raises(ValueError, match="half-width"):
        window(TT(2451545, 0.0), -1.0)


def test_a_central_solar_eclipse_has_the_ratio_of_the_diameters() -> None:
    """A centred annular eclipse gave (s☉ + s☾)/(2 s☉), not s☾/s☉."""
    from jyotirganita.core.types import TT

    eng = default_engine()
    ecl = eng.eclipses()
    centre = TT(2451545, 0.25)

    def state(t: TT) -> tuple[float, float, float]:
        x = (t.jd_whole - centre.jd_whole) + (t.jd_fraction - centre.jd_fraction)
        return abs(x) * 0.01, 0.005, 0.004

    ecl._solar_state = state  # type: ignore[method-assign]
    e = ecl.solar(TT(2451544, 0.25), TT(2451546, 0.25))
    assert e is not None and e.kind == "annular"
    assert abs(e.magnitude - 0.8) < 1e-6


def test_an_internal_tangency_is_partial() -> None:
    """With ``<=`` a greatest eclipse just touching the central phase sought contacts that
    the separation never crosses: a RootError."""
    from jyotirganita.core.types import TT

    eng = default_engine()
    ecl = eng.eclipses()
    centre = TT(2451545, 0.25)

    def state(t: TT) -> tuple[float, float, float]:
        x = (t.jd_whole - centre.jd_whole) + (t.jd_fraction - centre.jd_fraction)
        return abs(0.005 - 0.004) + 0.01 * x * x, 0.005, 0.004

    ecl._solar_state = state  # type: ignore[method-assign]
    e = ecl.solar(TT(2451544, 0.25), TT(2451546, 0.25))
    assert e is not None and e.kind == "partial" and e.inner is None
    assert abs(e.magnitude - 0.8) < 1e-6


def test_one_light_time_evaluation_is_refused() -> None:
    """With one evaluation the place was taken at reception, unretarded."""
    from dataclasses import replace

    from modern_kit import parameters

    from jyotirganita.modern.apparent import Apparent

    eng = default_engine()
    one = replace(parameters()["modern.light_time_iterations"], value=Fraction(1))
    with pytest.raises(ValueError, match="at least 2"):
        Apparent(eng.ephemeris, eng.scales, records().data, one)


def test_the_iers_cut_off_lies_in_its_series() -> None:
    """A cut-off past the series' last day was extrapolated flat."""
    from pathlib import Path

    from jyotirganita.modern.deltat import IersDeltaT
    from jyotirganita.modern.timescales import OutOfRange

    class Table(dict[str, Any]):
        path = Path("iers_eop_c04.yaml")

    eng = default_engine()
    bad = Table(first_mjd=0, last_mjd=1, cutoff_mjd=3, ut1_minus_utc=["0", "0"])
    with pytest.raises(OutOfRange, match="cut-off"):
        IersDeltaT(eng.scales, bad)  # type: ignore[arg-type]


def test_a_cio_step_that_is_not_positive_is_refused() -> None:
    """A step of 0 divided by zero."""
    from dataclasses import replace

    from modern_kit import parameters

    from jyotirganita.modern.frames import Frame

    eng = default_engine()
    for value in (Fraction(0), Fraction(1, 10**400)):  # the second's float is 0
        step = replace(parameters()["modern.cio_locator_step"], value=value)
        with pytest.raises(ValueError, match="positive"):
            Frame(eng.precession, eng.nutation, eng.scales, step)


# --- the search's timelines and margins ------------------------------------------------------


def test_a_value_beginning_at_the_reference_end_is_at_zero() -> None:
    """A transition at b fell between holding()'s [a, b) and the search after b."""
    from jyotirganita.search.evaluate import Timeline

    tl = Timeline(1, [(Fraction(60), 2)])
    assert tl.nearest(frozenset({2}), Fraction(0), Fraction(60)) == 0


def _stub_evaluator(full: list[tuple[Fraction, int]], first: int) -> Any:
    """An evaluator whose timelines cut ``full`` to ``back`` days before and ``fwd`` after."""
    from types import SimpleNamespace

    from jyotirganita.search.evaluate import Timeline

    def timeline(element: str, jdn: JDN, back: int, fwd: int) -> Timeline:
        lo, hi = Fraction(-60 * back), Fraction(60 * (fwd + 1))
        start = first
        for tt, i in full:
            if tt <= lo:
                start = i
        inside = [(tt, i) for tt, i in full if lo < tt < hi]
        return Timeline(start, inside, (lo, hi))

    return SimpleNamespace(horizon=400, timeline=timeline)


def test_a_margin_looks_as_far_back_as_it_found_ahead() -> None:
    """With the value ending at −121 and beginning again at +179, the first window (two
    days each side) saw only +179 and returned it."""
    ev = _stub_evaluator([(Fraction(-121), 1), (Fraction(179), 5)], 5)
    got = Evaluator.nearest_instant(ev, "tithi", JDN(100), frozenset({5}), Fraction(0), Fraction(0))
    assert got == -121


def test_a_timeline_from_beyond_the_served_range_is_refused() -> None:
    """timeline(JDN 11) with days 0–10 served walked on forever."""
    from types import SimpleNamespace

    ev: Any = SimpleNamespace(served=lambda d: 0 <= d.value <= 10)
    with pytest.raises(ValueError, match="not a served day"):
        Evaluator.timeline(ev, "tithi", JDN(11), 0, 0)


# --- the search's compiler and stages --------------------------------------------------------


def test_a_window_from_a_day_without_a_record_is_refused_up_front() -> None:
    """A window from runs_from compiled, then the search failed part-way with MonthNotFound
    (the first days lie before the run's first month)."""
    from search_kit import query as query_doc

    from jyotirganita.search import search

    cfg = search_config("parahita_kerala")
    rf = cfg.runs_from.value
    doc = query_doc([{"element": "weekday", "value": 1}], rf, rf + 40)
    with pytest.raises(Refusal) as info:
        search(cfg, doc)
    assert info.value.field == "window.from"
    assert list(search(cfg, query_doc([{"element": "weekday", "value": 1}], rf + 60, rf + 80)))


def test_a_compiled_query_is_checked_against_the_configuration_it_runs_under() -> None:
    """A Query compiled under one run passed every check under another."""
    from search_kit import query as query_doc

    from jyotirganita.search import search

    cfg = search_config("parahita_kerala")
    q = compile_query(query_doc([{"element": "weekday", "value": 1}], 600000, 600010), cfg)
    with pytest.raises(Refusal) as info:
        search(search_config("modern_iers"), q)
    assert info.value.field == "window.from"


def test_an_integral_float_is_an_integer_and_the_document_is_copied() -> None:
    """JSON Schema takes 1.0 as an integer, the compiler did not; a compiled
    query shared the caller's mappings."""
    from search_kit import query as query_doc

    from jyotirganita.search.query import canonical_sha256

    cfg = search_config("parahita_kerala")
    doc = query_doc(
        [{"element": "tithi", "value": 1.0}, {"element": "weekday", "value": 2}], 600000, 600010
    )
    q = compile_query(doc, cfg)
    assert q.constraints[0].values == frozenset({1})
    doc["constraints"][1]["value"] = 3
    assert q.doc["constraints"][1]["value"] == 2
    assert q.sha256 == canonical_sha256(q.doc)


def test_a_key_given_twice_in_a_query_file_is_refused(tmp_path: Any) -> None:
    """The last of two `constraints:` sections won silently."""
    from jyotirganita.search.query import read_query

    y = tmp_path / "q.yaml"
    y.write_text("constraints: []\nconstraints: []\n", encoding="utf-8")
    j = tmp_path / "q.json"
    j.write_text('{"constraints": [], "constraints": []}', encoding="utf-8")
    for path in (y, j):
        with pytest.raises(Refusal, match="appears twice"):
            read_query(path)


def test_a_standalone_at_time_is_checked_before_the_run_is_opened() -> None:
    """The preflight checked a time only under a match mode."""
    from search_kit import query as query_doc

    from jyotirganita.search.query import check_vocabulary

    cfg = search_config("parahita_kerala")
    doc = query_doc(
        [
            {"element": "tithi", "value": 1},
            {"element": "at_time", "of": ["tithi"], "nadika": "120/2"},
        ],
        600000,
        600010,
    )
    with pytest.raises(Refusal) as info:
        check_vocabulary(doc, cfg.reading_profile("kerala_default"))
    assert info.value.field == "constraints[1].nadika"


def test_a_position_selector_of_one_is_refused() -> None:
    """``1 in (True, "mean")`` held, so ``position: 1`` loaded."""
    from jyotirganita.data.yamlio import load_exact
    from jyotirganita.search.profiles import CITATION_FILE, _entry

    doc = load_exact(REPO / "jyotirganita/search/reading_profiles/kerala_default.yaml")
    item = next(e for e in doc["entries"] if e["element"] == "planet_rasi")
    allowed = (CITATION_FILE, "jyotirganita/regions/kerala/conventions.yaml")
    _entry(dict(item), "kerala_default", records(), allowed, "t")
    for bad in ({"position": 1}, {"position_by_body": {"jupiter": 1}}):
        with pytest.raises(Refusal, match="position"):
            _entry({**item, **bad}, "kerala_default", records(), allowed, "t")


# --- eras, freshness and witnesses -----------------------------------------------------------


def test_an_era_defined_twice_or_a_cycle_anchored_to_a_cycle_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """The later of two files replaced the earlier; a cycle anchored to a cycle passed
    ."""
    from types import SimpleNamespace

    import jyotirganita.data.eras as eras_mod
    from jyotirganita.data.datum import DatumError

    def ef(era_id: str, path: str, anchor: str | None = None) -> Any:
        cycle = None if anchor is None else SimpleNamespace(anchor_era=anchor)
        return SimpleNamespace(era=SimpleNamespace(id=era_id, cycle=cycle), path=path)

    def run(files: list[Any]) -> None:
        monkeypatch.setattr(eras_mod, "era_files", lambda root: files)
        monkeypatch.setattr(eras_mod, "load_era", lambda path, ctx, repo: path)
        ctx: Any = None
        eras_mod.load_eras(tmp_path, ctx)

    run([ef("a", "a.yaml"), ef("c", "c.yaml", "a")])
    with pytest.raises(DatumError, match="also defined in"):
        run([ef("a", "a.yaml"), ef("a", "b.yaml")])
    with pytest.raises(DatumError, match="itself a cycle"):
        run([ef("a", "a.yaml", "b"), ef("b", "b.yaml", "a")])


# --- group C of the 1.0.0 review findings ----------------------------------------------------


def _vondrak_frame() -> Any:
    from modern_kit import data, parameters

    from jyotirganita.modern.frames import Frame
    from jyotirganita.modern.nutation import make_nutation
    from jyotirganita.modern.precession import make_precession
    from jyotirganita.modern.timescales import TimeScales

    d = data()
    scales = TimeScales(d)
    prec = make_precession("vondrak2011", d, scales)
    return Frame(prec, make_nutation("iau2000a"), scales, parameters()["modern.cio_locator_step"])


def test_the_cio_locator_follows_the_exact_integral_far_from_j2000() -> None:
    """C3: s by TN36 eq. (5.8), not the series form (5.9), which drifts by arcseconds.

    Authority: TN36 chapter 5, eq. (5.8) on p. 6 (the integral itself). The
    expected value is an independent quadrature of that integral along the
    precession-only pole (composite Simpson on central differences, 2000
    panels), plus the frame's own nutation term −½[X Y − Xp Yp]; the
    tolerance is the grid's measured error at this date (under 0.01″,
    ``modern.cio_locator_step``). The series form misses by about 7″ here.
    """
    import numpy as np

    frame = _vondrak_frame()
    t = -27.0
    arcsec = 180 * 3600 / np.pi

    def pole(u: float) -> tuple[float, float, float]:
        row = frame.precession.bias_precession(u)[2]
        return float(row[0]), float(row[1]), float(row[2])

    def rates(u: float, e: float = 1e-4) -> tuple[float, float, float, float, float]:
        x, y, z = pole(u)
        (xa, ya, _), (xb, yb, _) = pole(u - e), pole(u + e)
        return x, y, z, (xb - xa) / (2 * e), (yb - ya) / (2 * e)

    def simpson(f: Any, n: int = 2000) -> float:
        us = np.linspace(0.0, t, n + 1)
        w = np.ones(n + 1)
        w[1:-1:2], w[2:-1:2] = 4, 2
        return float(sum(wi * f(float(u)) for wi, u in zip(w, us, strict=True))) * (t / n / 3)

    def eq58(u: float) -> float:
        x, y, z, dx, dy = rates(u)
        return (x * dy - y * dx) / (1 + z)

    def dxy(u: float) -> float:
        _, y, _, dx, _ = rates(u)
        return dx * y

    _, m = frame.state(t)
    x, y = float(m[2, 0]), float(m[2, 1])
    xp, yp, _ = pole(t)
    x0, y0, _ = pole(0.0)
    expected = -simpson(eq58) - (x * y - xp * yp) / 2
    # the series form (5.9) on the same poles, which the engine used before
    series = -(x * y - x0 * y0) / 2 + simpson(dxy)
    got = frame.cio_locator(t)
    assert abs(got - expected) * arcsec < 0.02
    assert abs(series - expected) * arcsec > 5  # the date tells the two forms apart


def test_modern_clock_times_hold_the_leap_second() -> None:
    """C2: on a leap-second day the sunrise is the clock's time, not the TT elapsed.

    Authority: the leap-second table the engine fetched (TAI − UTC steps
    from 36 s to 37 s at 2017-01-01 0h UTC, 05:30 IST). Between local
    midnight and sunrise on 1 Jan 2017 the TT elapsed is one second more
    than the clock shows; on the day before the two agree. The expected
    sunrise is the TT elapsed less the step, quantised to the second; the
    sunset adds the quantised TT duration from sunrise (no step between).
    """
    from jyotirganita.calendar.day import _hms
    from jyotirganita.core.types import FloatDays

    cfg = open_config(REPO, "modern_iers", "kerala/kozhikode")
    eng = cfg.engine
    src: Any = cfg.calendar.source  # a ModernSource; its quantiser is private
    for jdn, step in ((JDN(2457754), 0), (JDN(2457755), 1)):
        _, sunrise, sunset, m0 = eng.day_bounds(jdn)
        rec = api.day(cfg, jdn)
        clock = src._nadika(FloatDays((sunrise - m0).value - step / 86400))
        assert rec["sunrise"]["local"] == _hms(clock), jdn
        assert rec["sunset"]["local"] == _hms(clock + src._nadika(sunset - sunrise)), jdn


def test_a_record_fingerprints_the_calendar_files() -> None:
    """C6: the profile, names, places, era records and composition datum's file are hashed.

    They stay outside ``data_files``, so ``parameters_sha256``, on which the
    step scans are keyed, does not move.
    """
    from jyotirganita.provenance.hashing import file_sha256, files_digest

    cfg = open_config(REPO, "suryasiddhanta_kerala", "kerala/kozhikode", records=records())
    prov = api.day(cfg, JDN(2086382))["provenance"]
    files = prov["calendar_files"]
    for rel in (
        "jyotirganita/regions/kerala/conventions.yaml",
        "jyotirganita/regions/kerala/names.yaml",
        "jyotirganita/regions/kerala/places.yaml",
        "jyotirganita/data/eras/kollam.yaml",
        "jyotirganita/data/eras/saka.yaml",
        "jyotirganita/data/texts/suryasiddhanta/composed.yaml",
        "jyotirganita/methods/presets/suryasiddhanta_kerala.yaml",
    ):
        assert files[rel] == file_sha256(REPO / rel), rel
    assert prov["parameters_sha256"] == files_digest(prov["data_files"].items())
    assert "jyotirganita/data/texts/suryasiddhanta/composed.yaml" not in prov["data_files"]
