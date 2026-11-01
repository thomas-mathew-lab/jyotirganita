"""JDN from and to Julian and Gregorian dates; weekday from JDN.

Astronomical year numbering throughout: year 0 is 1 B.C., year −3101 is
3102 B.C. Every date is a :class:`~jyotirganita.core.types.JulianDate` or a
:class:`~jyotirganita.core.types.GregorianDate`; no function here takes a
bare year, month and day, and there is no switch date: which calendar a
date is in is the caller's tag, never inferred from the year.

**The rules, and the constants derived from them.** Both calendars have
twelve months of 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30 and 31 days
in a common year, so a common year has 365 days, and a leap year adds a
29th day to February.

- Julian leap rule: every year divisible by 4 is a leap year. The Julian
  cycle is therefore 4 years of 4 × 365 + 1 = 1461 days.
- Gregorian leap rule: a year divisible by 4 is a leap year, except a
  year divisible by 100 that is not divisible by 400. The Gregorian cycle
  is therefore 400 years of 400 × 365 + 97 = 146097 days.

These are the calendars' own rules. They are tested against printed
conversions, not taken from them: the Julian leap days in Sewell and
Dikshit's Table I (fixtures ``authority/calendar/sewell_dikshit_1896_table1_p130`` and
``sewell_dikshit_1896_table1_p214``), the century years that are not leap years in the
Gregorian calendar (``sewell_dikshit_1896_table1_p216``, ``sewell_dikshit_1896_table1_p222``, whose
footnotes say so).

**The epoch offsets of the Julian-day conversion**:

- JDN 0 is the Julian date 1 January 4713 B.C., astronomical year −4712
  (the origin of the Julian day as bag_2003_julian_days p. 30 states it, datum
  ``eras.kali.julian_period.bag_2003_julian_days``; tested by
  ``authority/calendar/bag_2003_julian_days_ex1`` and ``bag_2003_julian_days_table1``;
  sewell_dikshit_1896 Art. 16
  prints a Tuesday for that day). So JDN of a Julian
  date is its count of days from Julian −4712-01-01.
- The Gregorian calendar is aligned to the Julian by the reform of 1582:
  the Gregorian date 15 October 1582 is the day after the Julian date
  4 October 1582 (bag_2003_julian_days Table 1's legend and its rows 1500 (J) and
  1500 (G), ``authority/calendar/bag_2003_julian_days_table1``; the change of style of
  1752 in Britain, ``authority/calendar/pillai_1911_chronology_s236``, is a test of the same
  alignment). That alignment is the only use of the year 1582 here; it is
  not a switch date.

**Weekday.** JDN 0 was a Monday, so the weekday of a day is its JDN modulo
7 counted from Monday (bag_2003_julian_days p. 30; ``authority/calendar/bag_2003_julian_days_ex1``;
tested against every printed weekday of the fixtures).

The fixtures cited here are the authority fixtures under
``tests/authority/calendar/``; the module is allow-listed for its literals
in ``data/firewall_allow.yaml`` on the derivations above, never tagged as
data.
"""

from __future__ import annotations

import re
from enum import Enum

from jyotirganita.core.types import JDN, GregorianDate, JulianDate

__all__ = [
    "CalendarDate",
    "Weekday",
    "check_day_of_month",
    "days_in_month",
    "gregorian_from_jdn",
    "gregorian_from_julian",
    "is_leap",
    "jdn_from_gregorian",
    "jdn_from_julian",
    "julian_from_gregorian",
    "julian_from_jdn",
    "parse_printed_date",
    "weekday",
]

type CalendarDate = JulianDate | GregorianDate
"""A tagged date of either calendar."""

_COMMON_MONTHS: tuple[int, ...] = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
_COMMON_YEAR = sum(_COMMON_MONTHS)
_FEBRUARY = 2
_JULIAN_LEAP_EVERY = 4
_GREGORIAN_CENTURY = 100
_GREGORIAN_LEAP_CENTURY = _JULIAN_LEAP_EVERY * _GREGORIAN_CENTURY


class Weekday(Enum):
    """The days of the week; the value is the JDN remainder modulo 7 (module docstring)."""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


def _ceil_div(a: int, b: int) -> int:
    return -((-a) // b)


def _is_leap_julian(y: int) -> bool:
    return y % _JULIAN_LEAP_EVERY == 0


def _is_leap_gregorian(y: int) -> bool:
    return y % _JULIAN_LEAP_EVERY == 0 and (
        y % _GREGORIAN_CENTURY != 0 or y % _GREGORIAN_LEAP_CENTURY == 0
    )


def _leap_years_before_julian(y: int) -> int:
    """Leap years in [0, y), negative for y < 0 (year 0 is a leap year)."""
    return _ceil_div(y, _JULIAN_LEAP_EVERY)


def _leap_years_before_gregorian(y: int) -> int:
    return (
        _ceil_div(y, _JULIAN_LEAP_EVERY)
        - _ceil_div(y, _GREGORIAN_CENTURY)
        + _ceil_div(y, _GREGORIAN_LEAP_CENTURY)
    )


def is_leap(date: CalendarDate) -> bool:
    """Whether the year of ``date`` is a leap year of ``date``'s own calendar."""
    if isinstance(date, JulianDate):
        return _is_leap_julian(date.y)
    if isinstance(date, GregorianDate):
        return _is_leap_gregorian(date.y)
    raise TypeError(f"a tagged date is a JulianDate or a GregorianDate, not {type(date).__name__}")


def _month_lengths(leap: bool) -> tuple[int, ...]:
    if not leap:
        return _COMMON_MONTHS
    return tuple(n + 1 if i == _FEBRUARY - 1 else n for i, n in enumerate(_COMMON_MONTHS))


def days_in_month(date: CalendarDate) -> int:
    """The number of days in the month of ``date``, in ``date``'s own calendar."""
    return _month_lengths(is_leap(date))[date.m - 1]


def check_day_of_month(date: CalendarDate) -> None:
    """Refuse a day beyond the length of its month in the date's own calendar."""
    n = days_in_month(date)
    if date.d > n:
        name = type(date).__name__
        raise ValueError(f"{name}({date.y}, {date.m}, {date.d}): month {date.m} has {n} days")


def _ordinal(date: CalendarDate) -> int:
    """Days from 1 January of year 0 of ``date``'s own calendar to ``date``."""
    check_day_of_month(date)
    if isinstance(date, JulianDate):
        leap_before = _leap_years_before_julian(date.y)
    else:
        leap_before = _leap_years_before_gregorian(date.y)
    before_month = sum(_month_lengths(is_leap(date))[: date.m - 1])
    return _COMMON_YEAR * date.y + leap_before + before_month + date.d - 1


def jdn_from_julian(date: JulianDate) -> JDN:
    """The JDN of a Julian date: its days from Julian −4712-01-01 (JDN 0)."""
    if not isinstance(date, JulianDate):
        raise TypeError(f"jdn_from_julian takes a JulianDate, not {type(date).__name__}")
    return JDN(_ordinal(date) - _ordinal(_JDN_ORIGIN))


def jdn_from_gregorian(date: GregorianDate) -> JDN:
    """The JDN of a Gregorian date, aligned by the reform of 1582 (module docstring)."""
    if not isinstance(date, GregorianDate):
        raise TypeError(f"jdn_from_gregorian takes a GregorianDate, not {type(date).__name__}")
    first = jdn_from_julian(_REFORM_LAST_JULIAN).plus_days(1)
    return first.plus_days(_ordinal(date) - _ordinal(_REFORM_FIRST_GREGORIAN))


def _from_ordinal(ordinal: int, julian: bool) -> tuple[int, int, int]:
    """Year, month and day of a day ``ordinal`` days after 1 January of year 0."""
    cycle_years = _JULIAN_LEAP_EVERY if julian else _GREGORIAN_LEAP_CENTURY
    before = _leap_years_before_julian if julian else _leap_years_before_gregorian
    leap_of = _is_leap_julian if julian else _is_leap_gregorian

    def start(y: int) -> int:
        return _COMMON_YEAR * y + before(y)

    y = ordinal * cycle_years // start(cycle_years)
    while start(y) > ordinal:
        y -= 1
    while start(y + 1) <= ordinal:
        y += 1
    rest = ordinal - start(y)
    m = 1
    for n in _month_lengths(leap_of(y)):
        if rest < n:
            break
        rest -= n
        m += 1
    return y, m, rest + 1


def julian_from_jdn(jdn: JDN) -> JulianDate:
    """The Julian date of a JDN."""
    if not isinstance(jdn, JDN):
        raise TypeError(f"julian_from_jdn takes a JDN, not {type(jdn).__name__}")
    y, m, d = _from_ordinal(jdn.value + _ordinal(_JDN_ORIGIN), julian=True)
    return JulianDate(y, m, d)


def gregorian_from_jdn(jdn: JDN) -> GregorianDate:
    """The (proleptic) Gregorian date of a JDN."""
    if not isinstance(jdn, JDN):
        raise TypeError(f"gregorian_from_jdn takes a JDN, not {type(jdn).__name__}")
    first = jdn_from_julian(_REFORM_LAST_JULIAN).plus_days(1)
    ordinal = _ordinal(_REFORM_FIRST_GREGORIAN) + jdn.days_since(first)
    y, m, d = _from_ordinal(ordinal, julian=False)
    return GregorianDate(y, m, d)


def gregorian_from_julian(date: JulianDate) -> GregorianDate:
    """The Gregorian date of the same day as a Julian date (through its JDN)."""
    return gregorian_from_jdn(jdn_from_julian(date))


def julian_from_gregorian(date: GregorianDate) -> JulianDate:
    """The Julian date of the same day as a Gregorian date (through its JDN)."""
    return julian_from_jdn(jdn_from_gregorian(date))


def weekday(jdn: JDN) -> Weekday:
    """The weekday of a civil day: its JDN modulo 7, counted from Monday."""
    if not isinstance(jdn, JDN):
        raise TypeError(f"weekday takes a JDN, not {type(jdn).__name__}")
    return Weekday(jdn.value % len(Weekday))


# --- printed dates ------------------------------------------------------------------

_MONTH_NAMES = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
_PRINTED = re.compile(
    r"^(?:(?P<ce>C\.?\s?E\.?)\s+)?"
    r"(?:(?P<wd>[A-Za-z]+),?\s+)?"
    r"(?:(?P<d1>\d+)(?:st|nd|rd|th)?\s+(?P<m1>[A-Za-z]+)\.?"
    r"|(?P<m2>[A-Za-z]+)\.?,?\s+(?P<d2>\d+)(?:st|nd|rd|th)?),?\s+"
    r"(?:(?P<era0>A\.?\s?D\.?)\s*)?(?P<y>\d+)\s*(?P<era>B\.?\s?C\.?|A\.?\s?D\.?)?$"
)


def _month_of(name: str) -> int:
    n = name.lower().rstrip(".")
    hits = [i + 1 for i, full in enumerate(_MONTH_NAMES) if full.startswith(n) and len(n) >= 3]
    if len(hits) != 1:
        raise ValueError(f"{name!r} is not a month name")
    return hits[0]


def parse_printed_date[D: (JulianDate, GregorianDate)](text: str, calendar: type[D]) -> D:
    """A printed date (``Friday, February 18, 3102 B.C.``, ``CE 25 July 824``) as ``calendar``.

    The calendar is the caller's: the source's own statement of it, cited
    beside the datum; the text never decides it. A year
    marked B.C. is converted to astronomical numbering (*n* B.C. is
    1 − *n*); an unmarked year is A.D., as is one led by "CE". A weekday
    name, when printed, must be the weekday of the date (else ``ValueError``).
    """
    m = _PRINTED.match(text.strip())
    if m is None:
        raise ValueError(f"{text!r} is not a printed date of the forms this parser knows")
    day = int(m["d1"] or m["d2"])
    month = _month_of(m["m1"] or m["m2"])
    year = int(m["y"])
    if year < 1:  # a printed A.D. or B.C. year has no zero
        raise ValueError(f"{text!r}: a printed year is 1 or more")
    if m["era"] is not None and m["era"].upper().startswith("B"):
        if m["ce"] is not None or m["era0"] is not None:
            raise ValueError(f"{text!r} marks its year both A.D. or CE and B.C.")
        year = 1 - year
    date = calendar(year, month, day)
    check_day_of_month(date)
    if m["wd"] is not None:
        jdn = jdn_from_julian(date) if isinstance(date, JulianDate) else jdn_from_gregorian(date)
        printed = m["wd"].lower()
        actual = weekday(jdn).name.lower()
        # a weekday name or its abbreviation of three letters or more, nothing else
        if len(printed) < 3 or not actual.startswith(printed):
            raise ValueError(f"{text!r}: the printed weekday is not the date's ({actual})")
    return date


# The epoch offsets (module docstring).
_JDN_ORIGIN = JulianDate(-4712, 1, 1)
_REFORM_LAST_JULIAN = JulianDate(1582, 10, 4)
_REFORM_FIRST_GREGORIAN = GregorianDate(1582, 10, 15)
