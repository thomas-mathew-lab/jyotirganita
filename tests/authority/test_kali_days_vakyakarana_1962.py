"""Kali-day round trips against vakyakarana_1962 Examples 1 and 2.

vakyakarana_1962 counts the Kali days with the epoch's own day as the first ("the first
(Kali) day being a Friday", ``eras.kali.year_start.true.vakyakarana_1962``), so the day
that ends at Kali count *n* is ``n - 1`` civil days after the epoch day. The
examples are the editors' (``editor_computed``): their whole Kali days and
their sexagesimal subtraction are exact in the text's units.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from authority_kit import REPO, eras, printed

from jyotirganita.core.calendar import weekday
from jyotirganita.core.eras import Era, day_from_epoch_days, days_from_epoch
from jyotirganita.core.types import JDN
from jyotirganita.data.datum import context_for, load_records

Record = Callable[..., None]
EX1 = "authority/kali/vakyakarana_1962_ex1"
EX2 = "authority/kali/vakyakarana_1962_ex2"
EXACT = "whole Kali days and week-days: exact"


def ending_at(kali: Era, count: int) -> JDN:
    """The civil day that ends at Kali count ``count`` (vakyakarana_1962: the epoch's day is day
    1)."""
    day = day_from_epoch_days(kali, count - 1)
    assert isinstance(day, JDN)
    return day


def test_ex1_kali_year_from_the_saka_year(record_comparison: Record) -> None:
    fx = printed(EX1)
    offset = (
        load_records(REPO, context_for(REPO)).data["eras.saka.kali_offset.vakyakarana_1962"].value
    )
    computed = fx["input.saka_year"] + offset
    record_comparison(
        fixture=EX1,
        value="output.kali_year",
        computed=computed,
        tolerance=0,
        tolerance_reason="whole years (Kali elapsed = Śaka elapsed + 3179, vakyakarana_1962 I.2)",
    )
    assert computed == fx["output.kali_year"]


def test_ex1_the_day_ending_the_count_is_a_sunday(record_comparison: Record) -> None:
    fx = printed(EX1)
    computed = weekday(ending_at(eras()["kali"], fx["output.kali_days_end_of_day"])).name.title()
    record_comparison(
        fixture=EX1,
        value="output.weekday_gone",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == fx["output.weekday_gone"]


def test_ex1_new_years_day_is_a_monday(record_comparison: Record) -> None:
    fx = printed(EX1)
    new_year = ending_at(eras()["kali"], fx["output.kali_days_end_of_day"]).plus_days(1)
    computed = weekday(new_year).name.title()
    record_comparison(
        fixture=EX1,
        value="output.new_year_day",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == fx["output.new_year_day"]


@pytest.mark.parametrize("value", ["output.kali_days_end_of_day", "output.kali_days_kanya"])
def test_ex1_kali_counts_round_trip(value: str, record_comparison: Record) -> None:
    fx = printed(EX1)
    kali = eras()["kali"]
    back = days_from_epoch(kali, ending_at(kali, fx[value]))
    assert isinstance(back, int)
    computed = back + 1
    record_comparison(
        fixture=EX1,
        value=value,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (Kali count to civil day and back)",
    )
    assert computed == fx[value]


def test_ex1_the_kanya_day_counts_from_new_years_day(record_comparison: Record) -> None:
    fx = printed(EX1)
    kali = eras()["kali"]
    new_year = ending_at(kali, fx["output.kali_days_end_of_day"]).plus_days(1)
    kanya_24 = ending_at(kali, fx["output.kali_days_kanya"])
    computed = kanya_24.days_since(new_year) + 1
    record_comparison(
        fixture=EX1,
        value="output.kali_days_kanya",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (the days of the year to the end of Siṃha, then 24 of Kanyā)",
    )
    assert computed == fx["output.days_to_end_simha"] + fx["input.kanya_days"]


def test_ex2_days_elapsed_since_the_mesha_sankramana(record_comparison: Record) -> None:
    fx = printed(EX2)
    computed = fx["input.kali_days"] - fx["input.mesha_kali_days"]
    record_comparison(
        fixture=EX2,
        value="output.elapsed",
        computed=computed,
        tolerance=0,
        tolerance_reason="exact sexagesimal subtraction in days, nāḍikās and vināḍikās",
    )
    assert computed == fx["output.elapsed"]


def test_ex2_continues_ex1(record_comparison: Record) -> None:
    ex1, ex2 = printed(EX1), printed(EX2)
    computed = [ex2["input.kali_days"], ex2["input.mesha_kali_days"]]
    record_comparison(
        fixture=EX2,
        value="input.kali_days",
        computed=computed,
        tolerance=0,
        tolerance_reason="Example 2's Kali days are Example 1's results, as printed",
    )
    assert computed == [ex1["output.kali_days_kanya"], ex1["output.true_year_start"]]
