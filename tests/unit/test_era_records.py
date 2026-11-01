"""The committed era records against their own witnesses.

Consistency checks between printed statements of different sources, made
with the calendar code; the engine's output is not the evidence: every expected value is a printed
value of the records.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from jyotirganita.core.calendar import (
    Weekday,
    jdn_from_gregorian,
    jdn_from_julian,
    parse_printed_date,
    weekday,
)
from jyotirganita.core.eras import Era
from jyotirganita.core.types import JDN, GregorianDate, JulianDate
from jyotirganita.data.datum import Record, Records, context_for, load_records
from jyotirganita.data.eras import EraFile, load_eras

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def records() -> Records:
    return load_records(REPO)


@pytest.fixture(scope="module")
def eras() -> dict[str, EraFile]:
    return load_eras(REPO / "jyotirganita" / "data", context_for(REPO), REPO)


def era(eras: dict[str, EraFile], era_id: str) -> Era:
    return eras[era_id].era


def rows(rec: Record) -> list[dict[str, object]]:
    """A table datum's rows, by column."""
    assert isinstance(rec.value, tuple)
    return [dict(zip(rec.raw["columns"], r, strict=True)) for r in rec.value]


def row(rec: Record) -> dict[str, object]:
    """The one row of a one-row table datum, by column."""
    (only,) = rows(rec)
    return only


def text(records: Records, key: str) -> str:
    """A text datum's printed statement."""
    v = records.data[key].value
    assert isinstance(v, str)
    return v


def julian(text: str) -> JDN:
    return jdn_from_julian(parse_printed_date(text, JulianDate))


def test_the_three_records_load(eras: dict[str, EraFile]) -> None:
    assert set(eras) == {"kali", "saka", "kollam"}


# --- Kali ------------------------------------------------------------------------------


def test_kali_epoch_is_the_date_every_witness_prints(
    eras: dict[str, EraFile], records: Records
) -> None:
    epoch = era(eras, "kali").epoch
    assert "old style" in text(records, "eras.kali.epoch.calendar.sewell_dikshit_1896")
    for key in (
        "eras.kali.epoch.date.aryabhatiya_1976",
        "eras.kali.epoch.date.aryabhatiya_1976_intro",
    ):
        # the printed Friday is checked by the parser in the Julian reading
        assert julian(text(records, key)) == epoch
    assert "Friday" in text(records, "eras.kali.epoch.day_start.vakyakarana_1962")
    assert "Friday, 18th February" in text(records, "eras.kali.epoch.day_start.sewell_dikshit_1896")
    assert epoch is not None and weekday(epoch) is Weekday.FRIDAY


def test_aryabhatiya_1976_friday_holds_only_in_the_julian_reading(records: Records) -> None:
    printed = text(records, "eras.kali.epoch.date.aryabhatiya_1976")
    with pytest.raises(ValueError, match="weekday"):
        parse_printed_date(printed, GregorianDate)


def test_kali_witnesses_are_linked_by_verified_by(records: Records) -> None:
    rec = records.data["eras.kali.epoch.date.pillai_1911_chronology"]
    sources = {records.data[k].source for k in rec.verified_by if k in records.data}
    assert {"aryabhatiya_1976", "vakyakarana_1962", "sewell_dikshit_1896"} <= sources


def test_calendar_reform_committee_1955_kali_row_is_the_midnight_epoch_a_day_earlier(
    eras: dict[str, EraFile], records: Records
) -> None:
    r = row(records.data["eras.kali.epoch.calendar_reform_committee_1955"])
    assert isinstance(r["date"], str)
    day = julian(r["date"])
    assert day.value == r["julian_day"]
    epoch = era(eras, "kali").epoch
    assert epoch is not None and epoch.days_since(day) == 1


# --- Śaka ------------------------------------------------------------------------------


def test_saka_epoch_is_calendar_reform_committee_1955_printed_julian_day(
    eras: dict[str, EraFile], records: Records
) -> None:
    r = row(records.data["eras.saka.epoch.calendar_reform_committee_1955"])
    epoch = era(eras, "saka").epoch
    assert epoch is not None and epoch.value == r["julian_day"]
    # the same printed date read as Gregorian is another day
    assert isinstance(r["date"], str)
    greg = jdn_from_gregorian(parse_printed_date(r["date"], GregorianDate))
    assert greg != epoch


def test_saka_epoch_is_pillai_1911_chronology_solar_year_of_kali_3179(records: Records) -> None:
    pillai_1911_chronology = row(records.data["eras.saka.epoch.pillai_1911_chronology"])
    calendar_reform_committee_1955 = row(
        records.data["eras.saka.epoch.calendar_reform_committee_1955"]
    )
    assert (
        pillai_1911_chronology["kaliyuga"]
        == records.data["eras.saka.kali_offset.vakyakarana_1962"].value
    )
    # pillai_1911_chronology prints the day and the month's initial ('15M') and the A.D. year apart
    assert isinstance(calendar_reform_committee_1955["date"], str) and isinstance(
        pillai_1911_chronology["month_day"], str
    )
    day, month, year = calendar_reform_committee_1955["date"].replace(",", "").split()[:3]
    assert pillai_1911_chronology["month_day"] == f"{day}{month[0]}"
    assert pillai_1911_chronology["ad"] == int(year)


def test_saka_and_kali_offsets_agree(records: Records) -> None:
    offset = records.data["eras.saka.kali_offset.vakyakarana_1962"].value
    assert str(offset) in text(records, "eras.saka.kali_offset.vakyakarana_1962_verse")


# --- Kollam ----------------------------------------------------------------------------


def test_kollam_year_pair_and_zero_year_agree(records: Records) -> None:
    pair = text(records, "eras.kollam.year_pair.sewell_dikshit_1896")
    m = re.fullmatch(r"A\.D\. (\d+)—\d+ being called Kollam (\d+)\.", pair)
    assert m is not None
    ad, kollam = int(m[1]), int(m[2])
    zero = {
        r["zero_year"]
        for r in rows(records.data["eras.kollam.range.calendar_reform_committee_1955"])
    }
    assert zero == {ad - kollam}
    for key in ("eras.kollam.epoch.gislen", "eras.kollam.epoch.sarma_b"):
        assert parse_printed_date(text(records, key), JulianDate).y == ad - kollam


def test_kollam_options_and_contradictions(eras: dict[str, EraFile], records: Records) -> None:
    k = era(eras, "kollam")
    assert k.year_starts is not None and k.epoch is not None
    assert set(k.year_starts) == {"simha", "kanya"}
    assert k.year_starts["kanya"].epoch.days_since(k.epoch) > 0
    flagged = {
        r.key
        for r in records.data.values()
        if r.key.startswith("eras.kollam.") and "contradiction" in r.raw
    }
    assert flagged == {
        "eras.kollam.epoch.sarma_a",
        "eras.kollam.epoch.sarma_a.sarma_2009_facets",
        "eras.kollam.epoch.sarma_c",
        "eras.kollam.epoch.menon",
        "eras.kollam.epoch.kanya.sarma",
        "eras.kollam.epoch.kanya.sarma_93",
    }
    for key in flagged:
        assert f"provisional:{key}" in records.data[key].flags


def test_every_year_datum_states_its_convention(eras: dict[str, EraFile]) -> None:
    for ef in eras.values():
        counting = ef.data[load_counting_key(ef)]
        assert counting.raw.get("convention") in {"stated", "inferred_from_pair", "unstated"}


def load_counting_key(ef: EraFile) -> str:
    from jyotirganita.data.yamlio import load_exact

    doc = load_exact(REPO / ef.path)
    assert isinstance(doc, dict)
    return str(doc["counting"]["datum"])
