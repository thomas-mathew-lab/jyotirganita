"""Unit tests of the calendar layer: time standards, encodings, assignment, months, eras.

The calendar_reform_committee_1955 and rashtriya_panchanga_1959 statements a test compares with are
datums of the
profile and the time-standard records (``status`` as the ledger gives
it); the test reads them through the loader and never types their values.
"""

from __future__ import annotations

import dataclasses
import re
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace

import pytest

from jyotirganita.calendar.assignment import (
    DayPoints,
    NotModelledRule,
    Occurrence,
    assign,
    ksaya_vrddhi,
    label_at,
)
from jyotirganita.calendar.day import Calendar
from jyotirganita.calendar.encodings import clock, encode_ending, sexagesimal
from jyotirganita.calendar.months import (
    MONTH_RULES,
    RASI_IDS,
    SEARCH_DAYS,
    MeanSun,
    MeanYearStream,
    MonthRuleNotModelled,
    MonthStream,
    Sankranti,
    rule_rasi,
)
from jyotirganita.calendar.occurrences import tithi_name_index
from jyotirganita.core.calendar import jdn_from_gregorian, jdn_from_julian, parse_printed_date
from jyotirganita.core.eras import NotInRange, Sun, era_year
from jyotirganita.core.types import (
    JDN,
    UTC,
    GregorianDate,
    JulianDate,
    ModernCivilInstant,
    Nadika,
    civil_from_utc,
    utc_from_civil,
)
from jyotirganita.data.datum import DatumError, Record, context_for, load_records
from jyotirganita.data.eras import load_eras
from jyotirganita.data.time_standards import (
    OutOfForce,
    TimeStandard,
    load_time_standards,
    offset_days,
)
from jyotirganita.regions.base import ProfileError, load_profile, profile_ids

REPO = Path(__file__).resolve().parents[2]
CTX = context_for(REPO)


@pytest.fixture(scope="module")
def standards() -> dict[str, TimeStandard]:
    return dict(load_time_standards(REPO, CTX))


@pytest.fixture(scope="module")
def data() -> dict[str, Record]:
    return dict(load_records(REPO, CTX).data)


# --- time standards -----------------------------------------------------------------------


def _hm_offset(text: str) -> Fraction:
    m = re.search(r"(\d+)h (\d+)m", text)
    assert m is not None, text
    return offset_days(f"+{m[1]}:{m[2]}")


def test_ist_is_rashtriya_panchanga_1959_offset_on_rashtriya_panchanga_1959_day(
    standards: dict[str, TimeStandard], data: dict[str, Record]
) -> None:
    ist = standards["ist"]
    day = jdn_from_gregorian(GregorianDate(1959, 3, 22))
    stated = _hm_offset(str(data["time_standards.ist.definition.rashtriya_panchanga_1959"].value))
    assert ist.offset_on(day) == stated


def test_ist_agrees_with_calendar_reform_committee_1955_statement(
    standards: dict[str, TimeStandard], data: dict[str, Record]
) -> None:
    # calendar_reform_committee_1955: 5−30 A.M. IST is 0h UT
    text = str(data["time_standards.ist.definition.calendar_reform_committee_1955"].value)
    m = re.search(r"(\d+)−(\d+) A\. M\. I\. S\. T\.", text)
    assert m is not None
    day = jdn_from_gregorian(GregorianDate(1955, 1, 1))
    assert standards["ist"].offset_on(day) == offset_days(f"+{m[1]}:{m[2]}")


def test_war_time_and_refusal_outside_the_periods(standards: dict[str, TimeStandard]) -> None:
    ist = standards["ist"]
    periods = ist.periods
    war = [p for p in periods if p.war_time]
    assert war and all(p.offset > periods[0].offset for p in war)
    first = periods[0].start
    assert first is not None
    with pytest.raises(OutOfForce):
        ist.offset_on(first.plus_days(-1))
    for a, b in pairwise(periods):
        assert b.start is not None and a.end == b.start
        assert ist.offset_on(b.start) == b.offset
        assert ist.offset_on(b.start.plus_days(-1)) == a.offset


def test_madras_time_and_lmt(standards: dict[str, TimeStandard]) -> None:
    madras = standards["madras_time"]
    assert madras.citation.startswith("tzdata_asia_kolkata:")
    lmt = standards["lmt"]
    day = jdn_from_gregorian(GregorianDate(1900, 1, 1))
    with pytest.raises(ValueError, match="longitude"):
        lmt.offset_on(day)
    assert lmt.offset_on(day, Fraction(90)) == Fraction(1, 4)


def test_a_period_that_disagrees_with_its_table_line_is_refused(tmp_path: Path) -> None:
    import shutil

    for rel in ("jyotirganita",):
        shutil.copytree(
            REPO / rel, tmp_path / rel, ignore=shutil.ignore_patterns("__pycache__", "ephemerides")
        )
    path = tmp_path / "jyotirganita/data/time_standards/ist.yaml"
    text = path.read_text(encoding="utf-8").replace("to: 1941-10-01", "to: 1941-10-02", 1)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(DatumError):
        load_time_standards(tmp_path, context_for(tmp_path))


def test_civil_and_utc_round_trip() -> None:
    offset = offset_days("+05:30")
    day = jdn_from_gregorian(GregorianDate(1959, 3, 22))
    inst = ModernCivilInstant(day, 0.25, "ist")
    back = civil_from_utc(utc_from_civil(inst, offset), offset, "ist")
    assert back == inst


def test_a_utc_fraction_past_the_day_is_carried() -> None:
    """utc_from_civil's sum can leave [0, 1); the two-part form carries it."""
    assert UTC(2436650, 1.25) == UTC(2436651, 0.25)
    assert UTC(2436650, -0.25) == UTC(2436649, 0.75)
    offset = offset_days("+05:30")
    day = jdn_from_gregorian(GregorianDate(1959, 3, 22))
    late = ModernCivilInstant(day, 0.9, "ist")  # 0.9 + 1/2 − offset > 1
    t = utc_from_civil(late, offset)
    assert 0 <= t.jd_fraction < 1 and t.jd_whole == day.value
    assert utc_from_civil(ModernCivilInstant(day, 0.25, "ist"), offset) < t
    back = civil_from_utc(t, offset, "ist")
    # the carry costs the float its last bits: equal to well under a microsecond
    assert back.jdn == late.jdn and abs(back.local_fraction - late.local_fraction) < 1e-12


# --- encodings ------------------------------------------------------------------------------


def test_encodings() -> None:
    n, length = Nadika(Fraction(53, 10)), Nadika(Fraction(601, 10))
    assert (
        encode_ending(n, unit="nadika", direction="elapsed", reference="sunrise", day_length=length)
        == n.value
    )
    assert (
        encode_ending(
            n, unit="nadika", direction="remaining", reference="sunrise", day_length=length
        )
        == (length - n).value
    )
    assert (
        encode_ending(
            n, unit="ghatika_variable", direction="elapsed", reference="sunrise", day_length=length
        )
        == n.value * 60 / length.value
    )
    rise = Nadika(15)
    assert (
        encode_ending(
            n,
            unit="hours",
            direction="elapsed",
            reference="midnight",
            day_length=length,
            sunrise_after_midnight=rise,
        )
        == (n + rise).value * 24 / 60
    )
    with pytest.raises(ValueError, match="midnight reference"):
        encode_ending(n, unit="hours", direction="elapsed", reference="midnight", day_length=length)
    assert sexagesimal(Fraction(53, 10)) == (5, Fraction(18))
    assert clock(Fraction(12)) == (12, Fraction(0), "p.m.")
    assert clock(Fraction(0)) == (12, Fraction(0), "a.m.")


# --- assignment and kṣaya/vṛddhi ---------------------------------------------------------


def _occ(*cuts: int, first: int = 4) -> tuple[Occurrence, ...]:
    out, start, index = [], None, first
    for c in cuts:
        out.append(Occurrence(index, start, Nadika(c), Nadika(c)))
        start, index = Nadika(c), index + 1
    out.append(Occurrence(index, start, None, Nadika(99)))
    return tuple(out)


def test_assignment_rules_on_constructed_days() -> None:
    occ = _occ(10, 40)  # 4 for 10 nāḍikās, 5 for 30, 6 for 20
    points = DayPoints(Nadika(60), Nadika(0), Nadika(45))
    assert assign("at_sunrise", occ, points) == 4
    assert assign("udaya_vyapini", occ, points) == 4
    assert assign("at_midnight", occ, points) == 6
    assert assign("predominant", occ, points) == 5
    assert assign("at_custom_time", occ, DayPoints(Nadika(60), Nadika(0), None, Nadika(10))) == 5
    assert label_at(occ, Nadika(10)) == 5  # an ending belongs to the next occurrence
    tie = _occ(30)
    assert assign("predominant", tie, points) == 4  # the earlier wins a tie
    with pytest.raises(NotModelledRule, match="modern engine"):
        assign("at_midnight", occ, DayPoints(Nadika(60), Nadika(0)))
    with pytest.raises(KeyError):
        assign("at_noon", occ, points)


def test_ksaya_and_vrddhi_from_consecutive_labels() -> None:
    assert ksaya_vrddhi("tithi", 30, 3, 4, 5) == ()
    assert ksaya_vrddhi("tithi", 30, 4, 4, 5) == ("vriddhi:tithi.4",)
    assert ksaya_vrddhi("tithi", 30, 3, 4, 6) == ("kshaya:tithi.5",)
    assert ksaya_vrddhi("tithi", 30, 29, 30, 2) == ("kshaya:tithi.1",)  # across the month
    assert ksaya_vrddhi("tithi", 30, None, 4, None) == ()


def test_tithi_names() -> None:
    assert tithi_name_index(15) == (15, "shukla")
    assert tithi_name_index(16) == (1, "krishna")
    assert tithi_name_index(30) == (30, "krishna")


# --- months and the mean year ---------------------------------------------------------------


def test_rule_vocabulary_covers_every_era_record() -> None:
    eras = load_eras(REPO / "jyotirganita" / "data", CTX, REPO)
    for ef in eras.values():
        for ys in (ef.era.year_starts or {}).values():
            assert 1 <= rule_rasi(ys.rule) <= len(RASI_IDS)
    with pytest.raises(ValueError):
        rule_rasi("sankranti.nowhere")
    assert set(MONTH_RULES) == {
        "aparahna_parts",
        "fixed_tropical_offset",
        "following_day",
        "sunset",
    }


def test_mean_year_matches_completed_years_of_a_constructed_yuga() -> None:
    epoch = JDN(1000)
    mean = MeanSun(4, 1461, 0, epoch)  # four revolutions in 1461 days
    stream = MeanYearStream(mean)
    for a in range(0, 1461 * 3, 37):
        day = epoch.plus_days(a)
        assert stream.starts_between("sankranti.mesha", Sun.MEAN, epoch, day) == 4 * a // 1461
    first = stream.nth_start_after("sankranti.mesha", Sun.MEAN, epoch, 1)
    assert first.days_since(epoch) == 366  # the first day at whose start a revolution is complete
    with pytest.raises(ValueError):
        stream.starts_between("sankranti.mesha", Sun.TRUE, epoch, first)


def test_fixed_tropical_offset_refuses_a_siddhantic_engine() -> None:
    from jyotirganita.core.types import NOT_MODELLED

    class _Siddhantic:
        def instant(self, jdn: JDN, after: Nadika) -> object:
            return (jdn, after)

        def tropical_longitude(self, body: str, instant: object) -> object:
            return NOT_MODELLED

    class _Stream:
        engine = _Siddhantic()

        def bisect(self, entered, near):  # type: ignore[no-untyped-def]
            return entered(near)

    rule = MONTH_RULES["fixed_tropical_offset"]
    with pytest.raises(MonthRuleNotModelled, match="tropical longitude"):
        rule.fn(_Stream(), 1, JDN(0), {"offset": Fraction(0), "days_after": Fraction(0)})  # type: ignore[arg-type]


# --- profiles and the year-start statements -------------------------------------------------


def test_kerala_profile_loads_with_its_flags(data: dict[str, Record]) -> None:
    assert profile_ids(REPO) == ["kerala"]
    eras = load_eras(REPO / "jyotirganita" / "data", CTX, REPO)
    p = load_profile(REPO, "kerala", data, eras)
    assert p.month_rule.flag == "provisional:regions.kerala.month_rule"
    assert all(reason for reason in p.provisional.values())
    assert p.era_option("kollam") == "simha"
    assert p.era_option("kollam", "kanya") == "kanya"
    with pytest.raises(ProfileError):
        p.era_option("kollam", "mesha")
    with pytest.raises(ProfileError):
        p.name("tithi", 16)  # a kṛṣṇa tithi is named by its śukla twin (tithi_name_index)


KARANA_CYCLE = "calendar.karana_cycle.sewell_dikshit_1896"


def test_the_karana_cycle_is_resolved_from_its_table_datum(data: dict[str, Record]) -> None:
    """The sixty names come from sewell_dikshit_1896 Table VIII's datum, flagged while read."""
    eras = load_eras(REPO / "jyotirganita" / "data", CTX, REPO)
    p = load_profile(REPO, "kerala", data, eras)
    table = data[KARANA_CYCLE].value
    assert isinstance(table, tuple)
    assert len(p.karana_cycle) == 2 * len(table)
    assert set(p.karana_cycle) == set(range(1, p.counts["karana"] + 1))
    for row, pair in zip(
        table, zip(p.karana_cycle[::2], p.karana_cycle[1::2], strict=True), strict=True
    ):
        for cell, index in zip(row[1:], pair, strict=True):
            if isinstance(cell, int):
                assert index == cell
            else:
                assert cell in p.name("karana", index).forms["latin"]
    if data[KARANA_CYCLE].status == "double_read":
        assert p.karana_flag is None
    else:
        assert p.karana_flag == f"provisional:{KARANA_CYCLE}"
        assert p.provisional[p.karana_flag]


@pytest.mark.parametrize(
    "change",
    ["a name no karaṇa carries", "a karaṇa number the profile lacks", "a row short"],
)
def test_a_karana_table_that_does_not_resolve_is_refused(
    change: str, data: dict[str, Record]
) -> None:
    eras = load_eras(REPO / "jyotirganita" / "data", CTX, REPO)
    rec = data[KARANA_CYCLE]
    assert isinstance(rec.value, tuple)
    rows = [list(r) for r in rec.value]
    if change == "a name no karaṇa carries":
        rows[0][1] = "Nonesuch"
    elif change == "a karaṇa number the profile lacks":
        rows[1][1] = 12
    else:
        rows.pop()
    planted = {**data, KARANA_CYCLE: dataclasses.replace(rec, value=tuple(map(tuple, rows)))}
    with pytest.raises(ProfileError):
        load_profile(REPO, "kerala", planted, eras)


def test_a_day_that_names_a_karana_carries_the_cycle_flag(kerala_calendar: Calendar) -> None:
    profile = kerala_calendar.conventions.profile
    assert profile is not None
    day = kerala_calendar.day(kerala_calendar.source.runs_from.plus_days(1000))
    assert day["karana"]
    if profile.karana_flag is not None:
        assert profile.karana_flag in day["flags"]


@pytest.fixture(scope="module")
def kerala_calendar() -> Calendar:
    from jyotirganita.methods.presets import open_preset

    _, _run, cal = open_preset(REPO, "parahita_kerala", "kerala/kozhikode")
    return cal


@pytest.mark.parametrize(
    ("option", "key"),
    [
        ("simha", "regions.kerala.conventions.kollam_year_start.calendar_reform_committee_1955_30"),
        ("kanya", "regions.kerala.conventions.kollam_year_start.calendar_reform_committee_1955_32"),
    ],
)
def test_kollam_year_start_options_against_calendar_reform_committee_1955_almanac_replies(
    option: str, key: str, data: dict[str, Record], kerala_calendar: Calendar
) -> None:
    """calendar_reform_committee_1955's replies (30) and (32): the first day of a Kollam year under
    each option.

    A comparison of parahita under the aparāhna rule at Kozhikode with the
    almanacs' practice as calendar_reform_committee_1955 reports it; a disagreement after a change
    is a finding to record, not a value to adjust.
    """
    text = str(data[key].value)
    m = re.fullmatch(r".*?(\d+) begins on (\d+)\w\w (\w+), (\d+)", text)
    assert m is not None, text
    year = int(m[1])
    printed_day = jdn_from_gregorian(parse_printed_date(f"{m[2]} {m[3]} {m[4]}", GregorianDate))
    cal = kerala_calendar
    era = cal.eras["kollam"].era
    assert cal.months is not None
    y = era_year(era, printed_day, option, cal.months)
    assert not isinstance(y, NotInRange)
    assert (y.year, y.first_day) == (year, printed_day)


@pytest.mark.parametrize(
    ("option", "key"),
    [("simha", "eras.kollam.epoch.gislen"), ("kanya", "eras.kollam.epoch.sarma_b")],
)
def test_kollam_epochs_are_the_first_days_of_year_zero(
    option: str, key: str, data: dict[str, Record], kerala_calendar: Calendar
) -> None:
    """Each Kollam epoch as printed is the first day of the year 0.

    Gislén's Chingam 1 and Sarma's August 25, read as Kanni 1, against
    parahita's year starts of 824 at Kozhikode under the aparāhna rule: the
    printed day is the method's own year start, the day before it is outside
    the option's count, and the year turns 1 at the next year start. A
    comparison; a disagreement after a change is a finding to record, not a
    value to adjust.
    """
    cal = kerala_calendar
    era = cal.eras["kollam"].era
    assert cal.months is not None and era.year_starts is not None
    printed = jdn_from_julian(parse_printed_date(str(data[key].value), JulianDate))
    ys = era.year_starts[option]
    assert ys.epoch == printed
    assert cal.months.nth_start_after(ys.rule, ys.sun, printed.plus_days(-60), 1) == printed
    assert isinstance(era_year(era, printed.plus_days(-1), option, cal.months), NotInRange)
    first = era_year(era, printed, option, cal.months)
    assert not isinstance(first, NotInRange)
    assert (first.year, first.first_day) == (0, printed)
    turn = cal.months.nth_start_after(ys.rule, ys.sun, printed, 1)
    last = era_year(era, turn.plus_days(-1), option, cal.months)
    after = era_year(era, turn, option, cal.months)
    assert not isinstance(last, NotInRange) and not isinstance(after, NotInRange)
    assert (last.year, last.first_day) == (0, printed)
    assert (after.year, after.first_day) == (1, turn)


#: the Kerala presets whose month stream counts from a text's mean Sun (calendar/day.py)
KERALA_MEAN_SUN_PRESETS = (
    "parahita_kerala",
    "aryabhatiya_kerala",
    "suryasiddhanta_kerala",
    "suryasiddhanta_paramesvara_recension_kerala",
)


@pytest.fixture(scope="module")
def kerala_runs() -> dict[str, Calendar]:
    from jyotirganita.methods.presets import open_preset

    records = load_records(REPO, CTX)
    return {
        p: open_preset(REPO, p, "kerala/kozhikode", records=records)[2]
        for p in KERALA_MEAN_SUN_PRESETS
    }


@pytest.mark.parametrize("rule", ["aparahna_parts", "following_day", "sunset"])
@pytest.mark.parametrize("preset", KERALA_MEAN_SUN_PRESETS)
def test_kali_less_saka_is_vakyakarana_1962_offset_under_every_month_rule(
    preset: str, rule: str, data: dict[str, Record], kerala_runs: dict[str, Calendar]
) -> None:
    """vakyakarana_1962's Kali = Śaka + 3179 holds for the true-Sun years under both month rules.

    Before 1.0.0 the ``following_day`` rule moved the
    Śaka epoch's own Meṣa start (the epoch is the day of its saṅkrānti) to
    the next day and counted it as a year, one too many. Both eras start
    their years at the same true Meṣa start, so their difference is the
    printed offset on every day; and the Śaka year is 0 from the epoch to
    the day before the next Meṣa start. The offset is read through the
    loader (eras.saka.kali_offset.vakyakarana_1962), never typed.
    """
    base = kerala_runs[preset]
    cal = Calendar(base.run, base.conventions, base.eras, month_rule=rule)
    assert cal.months is not None
    offset = data["eras.saka.kali_offset.vakyakarana_1962"].value
    kali, saka = cal.eras["kali"].era, cal.eras["saka"].era
    days = [jdn_from_gregorian(GregorianDate(1900, 1, 1)).plus_days(29 * i) for i in range(14)]
    for d in days:
        k, s = era_year(kali, d, "true", cal.months), era_year(saka, d, "mesha", cal.months)
        assert not isinstance(k, NotInRange) and not isinstance(s, NotInRange)
        assert (k.year - s.year, k.first_day) == (offset, s.first_day), d
    ys = saka.year_starts["mesha"] if saka.year_starts else None
    assert ys is not None
    moved = 1 if rule == "following_day" else 0  # this epoch's saṅkrānti is early in its day
    assert cal.months.moved_own_start(ys.rule, ys.sun, ys.epoch) == moved
    turn = cal.months.nth_start_after(ys.rule, ys.sun, ys.epoch, 1 + moved)
    for d, year in ((ys.epoch.plus_days(2), 0), (turn.plus_days(-1), 0), (turn, 1)):
        y = era_year(saka, d, "mesha", cal.months)
        assert not isinstance(y, NotInRange) and y.year == year, (d, year)


@pytest.mark.parametrize("turn", range(-SEARCH_DAYS + 1, SEARCH_DAYS + 1))
def test_month_bisection_ends_on_the_last_day_before_the_turn(turn: int) -> None:
    """The bisection returns the day before ``entered`` turns true, in a bounded number of looks.

    Each look is counted: a loop test that lets the bracket stop shrinking
    (a ``>`` written as ``>=``, say) fails here at once instead
    of running forever.
    """
    near = JDN(1000)
    looks = 0
    bound = 2 * SEARCH_DAYS + 2  # far above the log2 of the bracket a bisection needs

    def entered(d: JDN) -> bool:
        nonlocal looks
        looks += 1
        assert looks <= bound, "the bisection does not shrink its bracket"
        return d.days_since(near) >= turn

    stream = MonthStream.__new__(MonthStream)
    stream.source = SimpleNamespace(runs_from=JDN(0))
    assert stream.bisect(entered, near) == near.plus_days(turn - 1)


@pytest.mark.parametrize("preset", KERALA_MEAN_SUN_PRESETS)
def test_every_true_sun_epoch_is_a_year_start_day_of_its_rule(
    preset: str, kerala_runs: dict[str, Calendar]
) -> None:
    """The assumption ``moved_own_start`` rests on, checked for every era option.

    ``YearStartStream.moved_own_start`` takes each epoch
    to be a year-start day of its rule: the day of the rule's saṅkrānti or
    the day after it, or, for an epoch at ``runs_from``, a day whose sunrise
    already has the Sun in the rule's rāśi. An option whose epoch is not
    (a Caitrādi Śaka start, a lunar one) would break the count; this test
    fails before it ships (non-blocking item).
    """
    cal = kerala_runs[preset]
    assert cal.months is not None
    checked = 0
    for ef in cal.eras.values():
        for ys in (ef.era.year_starts or {}).values():
            if ys.sun is not Sun.TRUE:
                continue
            rasi = rule_rasi(ys.rule)
            if ys.epoch == cal.source.runs_from:
                assert cal.source.day(ys.epoch).labels["rasi"] == rasi, ys
            else:
                day = cal.months.sankranti(rasi, ys.epoch).day
                assert ys.epoch.days_since(day) in (0, 1), ys
            checked += 1
    assert checked >= len(cal.eras)


@pytest.mark.parametrize(
    ("after_start", "same_day"),
    [
        (Fraction(1, 10**6), True),
        (Fraction(30), True),
        (Fraction(32) - Fraction(1, 10**6), True),
        (Fraction(32), False),
        (Fraction(45), False),
        (Fraction(60) + Fraction(1, 100), False),
    ],
)
def test_sunset_rule_boundary(after_start: Fraction, same_day: bool) -> None:
    """sewell_dikshit_1896 Art. 28 (2) rule (a): an entry after sunrise and before sunset opens the
    month that
    day, one after sunset the next; an entry at sunset itself, which the rule does not name, is
    taken as not before it. An estimate past the day's length (the saṅkrānti marked by the
    label route seconds before the next sunrise) opens the next day's month.
    """
    day = JDN(5000)
    s = Sankranti(1, day, Nadika(after_start), Nadika(0), Nadika(Fraction(32)), Nadika(60))
    stream = SimpleNamespace(sankranti=lambda rasi, near: s)
    rule = MONTH_RULES["sunset"]
    got = rule.fn(stream, 1, day, {})  # type: ignore[arg-type]
    assert got == (day if same_day else day.plus_days(1))
    assert "sewell_dikshit_1896 Art. 28 rule (a)" in rule.citation


def test_sunset_rule_needs_a_sunset() -> None:
    day = JDN(5000)
    s = Sankranti(1, day, Nadika(Fraction(10)), Nadika(0), None, Nadika(60))
    stream = SimpleNamespace(sankranti=lambda rasi, near: s)
    with pytest.raises(MonthRuleNotModelled):
        MONTH_RULES["sunset"].fn(stream, 1, day, {})  # type: ignore[arg-type]


def test_sunset_rule_is_selectable_in_the_kerala_profile(
    kerala_calendar: Calendar, data: dict[str, Record]
) -> None:
    """The profile offers the rule with its statement and a provisional flag."""
    spec = kerala_calendar.conventions.month_rule
    assert spec is not None
    alt = spec.select("sunset")
    assert alt.datum == "regions.kerala.conventions.month_rule.sunset.statement.sewell_dikshit_1896"
    assert data[alt.datum].raw["status"] == "double_read"
    assert alt.flag == "provisional:sunset"
    cal = Calendar(
        kerala_calendar.run,
        kerala_calendar.conventions,
        kerala_calendar.eras,
        month_rule="sunset",
    )
    rec = cal.day(kerala_calendar.source.runs_from.plus_days(1000))
    assert "provisional:sunset" in rec["flags"]
