"""The longitude step of the derived UT chain against the Central Station.

``derived_ut`` puts local mean midnight of a civil day at a place on UT1
from the place's longitude east of Greenwich
(:func:`~jyotirganita.core.types.ut1_from_text_local`). calendar_reform_committee_1955
(item 33, printed p. 14) and rashtriya_panchanga_1959 (the Explanation, printed pp. xv–xvi)
print a place's longitude beside the statement that its local mean time
is the standard time, and print that time's offset from Universal Time.
So local mean midnight at the place, put on UT1 from the printed
longitude, must lie the printed offset before the day's Greenwich mean
midnight, on the previous UT day (local time ahead of UT).

What this pins and what it does not (the fixtures' notes): at the Central Station the
local mean time is the standard time by definition, so the
local-to-standard difference there is zero; these fixtures pin the
sign, the degrees-to-time scale and the day boundary of the longitude
step, and no nonzero local-to-standard difference at a Kerala place is
printed in calendar_reform_committee_1955 or rashtriya_panchanga_1959.

Every input is the fixture's printed value or a datum loaded by key; no
place is added to ``places.yaml`` (the observer is the printed longitude
alone). Tolerance: the print quantum of the comparison (each test's
reason). The fixtures are editor_computed.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from fractions import Fraction
from functools import cache
from typing import Any

from authority_kit import REPO, printed

from jyotirganita.core.types import (
    JDN,
    UT1,
    Nadika,
    SiddhanticCivilInstant,
    jd_at_midnight,
    ut1_from_text_local,
)
from jyotirganita.data.datum import context_for, load_records

calendar_reform_committee_1955 = (
    "authority/calendar/calendar_reform_committee_1955_central_station_lmt"
)
rashtriya_panchanga_1959 = "authority/calendar/rashtriya_panchanga_1959_central_station_lmt"
rashtriya_panchanga_1959_OFFSET = "time_standards.ist.definition.rashtriya_panchanga_1959"
#: any civil day: the step does not depend on the day (a regression file's first day)
DAY = JDN(2434972)
HOURS_PER_DAY = 24  # the definition of the hour
MINUTES_PER_HOUR = 60  # the definition of the minute
SECONDS_PER_MINUTE = 60  # the definition of the second

type Record = Callable[..., None]


@cache
def _records() -> Any:
    return load_records(REPO, context_for(REPO))


def _jd(t: UT1) -> Fraction:
    return Fraction(t.jd_whole) + Fraction(t.jd_fraction)


def _local_midnight(longitude_east: Fraction) -> UT1:
    """Local mean midnight of DAY at the place: no sunrise offset, no nāḍikās after it."""
    instant = SiddhanticCivilInstant(DAY, Nadika(0), "text_local:central_station")
    return ut1_from_text_local(instant, Nadika(0), longitude_east)


def _ahead_hours(longitude_east: Fraction) -> Fraction:
    """Hours by which the place's local mean time is ahead of UT1, from the chain."""
    return (jd_at_midnight(DAY) - _jd(_local_midnight(longitude_east))) * HOURS_PER_DAY


def _ut_day(t: UT1) -> int:
    """The JDN of the UT civil day an instant falls on (a day runs from midnight)."""
    day = JDN(int(_jd(t) - jd_at_midnight(JDN(0))))
    return day.value


def test_calendar_reform_committee_1955_offset_from_the_printed_longitude(
    record_comparison: Record,
) -> None:
    fx = printed(calendar_reform_committee_1955)
    longitude = fx["input.longitude_east_whole"] + fx["input.longitude_east_fraction"]
    offset = fx["output.offset_hours_whole"] + fx["output.offset_hours_fraction"]
    computed = _ahead_hours(longitude)
    # the offset is the standard's definition (the station's local mean time), so the computed
    # offset can differ from it only by the place's quantum: half a degree, two minutes of time
    # (fixture precision); the offset's own half hour would admit a 29-minute error
    quantum = Fraction(2, MINUTES_PER_HOUR)
    record_comparison(
        fixture=calendar_reform_committee_1955,
        value="output.offset_statement",
        computed=computed,
        tolerance=quantum,
        tolerance_reason="the place's print quantum: half a degree, two minutes of time",
    )
    assert abs(computed - offset) <= quantum
    assert computed > 0  # ahead of UT: east of Greenwich
    assert _ut_day(_local_midnight(longitude)) == DAY.value - 1


def test_rashtriya_panchanga_1959_offset_from_the_printed_longitude(
    record_comparison: Record,
) -> None:
    fx = printed(rashtriya_panchanga_1959)
    statement = str(_records().data[rashtriya_panchanga_1959_OFFSET].value)
    m = re.search(r"(\d+)h (\d+)m ahead", statement)
    assert m is not None, statement
    offset = int(m.group(1)) + Fraction(int(m.group(2)), MINUTES_PER_HOUR)
    computed = _ahead_hours(fx["input.longitude_east"])
    # as for calendar_reform_committee_1955: the place's quantum, one minute of arc, four seconds of
    # time (fixture
    # precision), not the offset's minute
    quantum = Fraction(4, MINUTES_PER_HOUR * SECONDS_PER_MINUTE)
    record_comparison(
        fixture=rashtriya_panchanga_1959,
        value="input.place_statement",
        computed=computed,
        tolerance=quantum,
        tolerance_reason="the place's print quantum: one minute of arc, four seconds of time",
    )
    assert abs(computed - offset) <= quantum
    assert _ut_day(_local_midnight(fx["input.longitude_east"])) == DAY.value - 1
