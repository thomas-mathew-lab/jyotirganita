"""The calendar module's API: tagged dates only, printed dates, the date syntax.

The dates here are planted
test inputs; printed conversions are the authority tests.
"""

from __future__ import annotations

import inspect
from types import ModuleType
from typing import Any

import pytest

import jyotirganita.core.calendar as cal
import jyotirganita.core.eras as eras
import jyotirganita.data.eras as data_eras
import jyotirganita.io.dates as dates
from jyotirganita.core.types import JDN, GregorianDate, JulianDate
from jyotirganita.io.dates import (
    DateSyntaxError,
    date_record,
    jdn_of,
    parse_cli_date,
    parse_json_date,
)


def _any(x: object) -> Any:
    return x


# --- no bare (y, m, d) ------------------------------------------------------------------

API_MODULES = (cal, eras, data_eras, dates)


def _public_callables(mod: ModuleType) -> list[tuple[str, Any]]:
    out = []
    for name in mod.__all__:
        obj = getattr(mod, name)
        if inspect.isfunction(obj):
            out.append((f"{mod.__name__}.{name}", obj))
        elif inspect.isclass(obj):
            for meth_name, meth in vars(obj).items():
                if inspect.isfunction(meth) and not meth_name.startswith("_"):
                    out.append((f"{mod.__name__}.{name}.{meth_name}", meth))
    return out


def _bare_date_offenders(callables: list[tuple[str, Any]]) -> list[str]:
    offenders = []
    for qual, fn in callables:
        params = inspect.signature(fn).parameters.values()
        hints = {p.name: str(p.annotation) for p in params if p.name not in ("self", "cls")}
        ints = [p for p, h in hints.items() if h == "int"]
        tuples = [p for p, h in hints.items() if h.startswith("tuple[")]
        datey = {"y", "m", "d", "year", "month", "day"} & set(hints)
        if len(ints) >= 3 or tuples or (datey and len(ints) >= 2):
            offenders.append(qual)
    return offenders


def test_no_function_accepts_a_bare_year_month_day() -> None:
    """A date crosses the API only as a tagged type."""
    callables = [c for mod in API_MODULES for c in _public_callables(mod)]
    assert len(callables) > 20
    assert _bare_date_offenders(callables) == []


def test_the_bare_date_check_finds_a_bare_date() -> None:
    def bare(y: int, m: int, d: int) -> None: ...

    def as_tuple(date: tuple[int, int, int]) -> None: ...

    def tagged(date: JulianDate) -> None: ...

    found = _bare_date_offenders([("bare", bare), ("as_tuple", as_tuple), ("tagged", tagged)])
    assert found == ["bare", "as_tuple"]


@pytest.mark.parametrize(
    "fn", [cal.jdn_from_julian, cal.jdn_from_gregorian, cal.is_leap, cal.days_in_month]
)
def test_converters_refuse_an_untagged_tuple(fn: Any) -> None:
    with pytest.raises((TypeError, AttributeError)):
        fn(_any((2000, 1, 1)))


def test_converters_refuse_the_other_calendar() -> None:
    with pytest.raises(TypeError):
        cal.jdn_from_julian(_any(GregorianDate(2000, 1, 1)))
    with pytest.raises(TypeError):
        cal.jdn_from_gregorian(_any(JulianDate(2000, 1, 1)))
    with pytest.raises(TypeError):
        cal.weekday(_any(2451545))


# --- day of month -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls,y,m,d",
    [
        (GregorianDate, 1900, 2, 29),
        (GregorianDate, 2001, 2, 29),
        (JulianDate, 1901, 2, 29),
        (JulianDate, 2000, 4, 31),
        (GregorianDate, 2000, 6, 31),
    ],
)
def test_days_beyond_the_month_are_refused(cls: Any, y: int, m: int, d: int) -> None:
    with pytest.raises(ValueError, match="has"):
        cls(y, m, d)


def test_leap_days_of_each_calendar() -> None:
    JulianDate(1900, 2, 29)
    GregorianDate(2000, 2, 29)
    JulianDate(-4, 2, 29)


# --- printed dates ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("18 February 3102 B.C.", JulianDate(-3101, 2, 18)),
        ("February 18, 3102 B.C.", JulianDate(-3101, 2, 18)),
        ("February, 18, 3102 B.C.", JulianDate(-3101, 2, 18)),
        ("15 March, 78 A.D.", JulianDate(78, 3, 15)),
        ("Aug. 15, 824 AD", JulianDate(824, 8, 15)),
        ("2 September, A.D. 1752", JulianDate(1752, 9, 2)),
        ("1st January A.D. 1910", JulianDate(1910, 1, 1)),
        ("15th July 1910", JulianDate(1910, 7, 15)),
        ("July 15th, 1910", JulianDate(1910, 7, 15)),
        ("15x July 1910", None),
        ("A.D. 1752", None),
        ("1 B.C. ", None),
        ("Jan. 1, 1 B.C.", JulianDate(0, 1, 1)),
        ("CE 25 July 824", JulianDate(824, 7, 25)),
        ("C.E. 25 July 824", JulianDate(824, 7, 25)),
        ("CE Monday, 25 July 824", JulianDate(824, 7, 25)),
        ("CE 25 July 824 B.C.", None),
    ],
)
def test_parse_printed_date(text: str, expected: JulianDate | None) -> None:
    if expected is None:
        with pytest.raises(ValueError):
            cal.parse_printed_date(text, JulianDate)
    else:
        assert cal.parse_printed_date(text, JulianDate) == expected


def test_printed_weekday_is_checked() -> None:
    d = JulianDate(1000, 3, 1)
    name = cal.weekday(cal.jdn_from_julian(d)).name.capitalize()
    assert cal.parse_printed_date(f"{name}, March 1, 1000 A.D.", JulianDate) == d
    other = next(w for w in cal.Weekday if w.name.capitalize() != name).name.capitalize()
    with pytest.raises(ValueError, match="weekday"):
        cal.parse_printed_date(f"{other}, March 1, 1000 A.D.", JulianDate)


def test_parse_printed_date_reads_the_callers_calendar() -> None:
    assert cal.parse_printed_date("1 March 1900", GregorianDate) == GregorianDate(1900, 3, 1)
    with pytest.raises(ValueError):
        cal.parse_printed_date("29 February 1900", GregorianDate)
    assert cal.parse_printed_date("29 February 1900", JulianDate) == JulianDate(1900, 2, 29)


# --- CLI and JSON syntax ------------------------------------------------------------------


def test_cli_dates() -> None:
    assert parse_cli_date("julian:1000-03-15") == JulianDate(1000, 3, 15)
    assert parse_cli_date("gregorian:1868-01-01") == GregorianDate(1868, 1, 1)
    assert parse_cli_date("jdn:12345") == JDN(12345)
    assert parse_cli_date("jdn:-5") == JDN(-5)


def test_cli_accepts_negative_years() -> None:
    assert parse_cli_date("julian:-3101-02-18") == JulianDate(-3101, 2, 18)
    assert parse_cli_date("gregorian:-44-03-15") == GregorianDate(-44, 3, 15)


@pytest.mark.parametrize(
    "text",
    [
        "1000-03-15",
        "-3101-02-18",
        "15/03/1000",
        "julian:1000-3",
        "islamic:1000-03-15",
        "julian 1000-03-15",
        "jdn:",
        "julian:1000-13-01",
        "gregorian:1900-02-29",
    ],
)
def test_cli_rejects_untagged_or_malformed_dates(text: str) -> None:
    with pytest.raises(DateSyntaxError):
        parse_cli_date(text)


def test_json_dates() -> None:
    assert parse_json_date({"julian": {"y": -3101, "m": 2, "d": 18}}) == JulianDate(-3101, 2, 18)
    assert parse_json_date({"gregorian": {"y": 1868, "m": 1, "d": 1}}) == GregorianDate(1868, 1, 1)
    assert parse_json_date({"jdn": 7}) == JDN(7)


@pytest.mark.parametrize(
    "obj",
    [
        {"y": 1000, "m": 3, "d": 15},
        {"date": "1000-03-15"},
        "julian:1000-03-15",
        [1000, 3, 15],
        {"julian": {"y": 1000, "m": 3}},
        {"julian": {"y": 1000, "m": 3, "d": 15}, "jdn": 1},
        {"jdn": "12"},
        {"jdn": True},
        {"gregorian": {"y": 1900, "m": 2, "d": 29}},
    ],
)
def test_json_rejects_untagged_or_malformed_dates(obj: object) -> None:
    with pytest.raises(DateSyntaxError):
        parse_json_date(obj)


def test_date_record_carries_the_jdn_and_both_calendars() -> None:
    for text in ("julian:1000-03-15", "gregorian:1868-01-01", "julian:-3101-02-18"):
        d = parse_cli_date(text)
        rec = date_record(jdn_of(d))
        assert set(rec) == {"jdn", "julian", "gregorian"}
        assert parse_json_date({"julian": rec["julian"]}) == cal.julian_from_jdn(jdn_of(d))
        assert jdn_of(parse_json_date({"gregorian": rec["gregorian"]})) == jdn_of(d)
        assert jdn_of(parse_json_date({"jdn": rec["jdn"]})) == jdn_of(d)
