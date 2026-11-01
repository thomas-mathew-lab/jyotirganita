"""Invariants of the calendar arithmetic.

JDN round trips in both calendars, day-to-day continuity of dates and
weekdays (across any boundary, the reform alignment included), and the
leap rules' periodicity. No printed value enters here: the printed
conversions are the authority tests under ``tests/authority/calendar/``.
"""

from __future__ import annotations

import itertools

import pytest

from jyotirganita.core.calendar import (
    Weekday,
    days_in_month,
    gregorian_from_jdn,
    gregorian_from_julian,
    is_leap,
    jdn_from_gregorian,
    jdn_from_julian,
    julian_from_gregorian,
    julian_from_jdn,
    weekday,
)
from jyotirganita.core.types import JDN, GregorianDate, JulianDate

# Every 991st day over about eleven thousand years either side of the era.
SPAN = range(-1_000_000, 4_000_000, 991)


def _next_day(d: JulianDate | GregorianDate) -> JulianDate | GregorianDate:
    cls = type(d)
    if d.d < days_in_month(d):
        return cls(d.y, d.m, d.d + 1)
    if d.m < 12:
        return cls(d.y, d.m + 1, 1)
    return cls(d.y + 1, 1, 1)


def test_jdn_round_trips_in_the_julian_calendar() -> None:
    for n in SPAN:
        assert jdn_from_julian(julian_from_jdn(JDN(n))) == JDN(n)


def test_jdn_round_trips_in_the_gregorian_calendar() -> None:
    for n in SPAN:
        assert jdn_from_gregorian(gregorian_from_jdn(JDN(n))) == JDN(n)


def test_julian_gregorian_round_trip() -> None:
    for n in SPAN:
        j = julian_from_jdn(JDN(n))
        assert julian_from_gregorian(gregorian_from_julian(j)) == j


@pytest.mark.parametrize("start", [-1_000_000, 0, 1_721_000, 2_299_000, 2_361_000, 2_415_000])
def test_consecutive_days_are_consecutive_dates_and_weekdays(start: int) -> None:
    order = list(Weekday)
    for n in range(start, start + 3000):
        a, b = JDN(n), JDN(n + 1)
        assert julian_from_jdn(b) == _next_day(julian_from_jdn(a))
        assert gregorian_from_jdn(b) == _next_day(gregorian_from_jdn(a))
        assert order.index(weekday(b)) == (order.index(weekday(a)) + 1) % len(order)


def test_weekday_is_the_days_weekday_in_either_calendar() -> None:
    for n in SPAN:
        j = julian_from_jdn(JDN(n))
        assert weekday(jdn_from_gregorian(gregorian_from_julian(j))) == weekday(JDN(n))


def test_leap_day_exists_exactly_in_leap_years() -> None:
    for y in range(-4800, 2500):
        for cls in (JulianDate, GregorianDate):
            leap = is_leap(cls(y, 1, 1))
            if leap:
                cls(y, 2, 29)
            else:
                with pytest.raises(ValueError):
                    cls(y, 2, 29)


def test_julian_leap_years_are_every_fourth_year() -> None:
    leaps = [y for y in range(-20, 21) if is_leap(JulianDate(y, 1, 1))]
    assert all((b - a) == 4 for a, b in itertools.pairwise(leaps))
    assert 0 in leaps  # astronomical year 0 (1 B.C.) is a Julian leap year


def test_calendar_cycles_are_periodic() -> None:
    def julian_span(y: int) -> int:
        return jdn_from_julian(JulianDate(y + 4, 1, 1)).days_since(
            jdn_from_julian(JulianDate(y, 1, 1))
        )

    def gregorian_span(y: int) -> int:
        return jdn_from_gregorian(GregorianDate(y + 400, 1, 1)).days_since(
            jdn_from_gregorian(GregorianDate(y, 1, 1))
        )

    assert len({julian_span(y) for y in range(-5000, 3000, 7)}) == 1
    assert len({gregorian_span(y) for y in range(-5000, 3000, 37)}) == 1


def test_calendars_drift_apart_only_at_gregorian_common_century_years() -> None:
    def gap(y: int) -> int:
        return jdn_from_gregorian(GregorianDate(y, 3, 1)).days_since(
            jdn_from_julian(JulianDate(y, 3, 1))
        )

    for y in range(-1000, 2500):
        if gap(y + 1) != gap(y):
            century = y + 1
            assert century % 100 == 0 and century % 400 != 0
            assert gap(y + 1) == gap(y) - 1  # the Julian 29 February the Gregorian drops
