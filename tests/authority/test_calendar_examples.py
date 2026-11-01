"""Calendar conversions against printed worked examples and tables.

Every expected value is a printed value of a fixture under
``tests/authority/calendar/``; every date is read in the calendar its
source states (the fixture's ``calendar.statement`` values). Whole days are reproduced exactly: no
tolerance.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import pytest
from authority_kit import Printed, eras, printed

from jyotirganita.core.calendar import (
    Weekday,
    jdn_from_gregorian,
    jdn_from_julian,
    julian_from_jdn,
    parse_printed_date,
    weekday,
)
from jyotirganita.core.eras import NOT_IN_RANGE, day_from_epoch_days, days_from_epoch
from jyotirganita.core.types import JDN, GregorianDate, JulianDate

Record = Callable[..., None]
EXACT = "whole days and week-days: the text's own arithmetic reproduces exactly"


def julian(text: str) -> JDN:
    return jdn_from_julian(parse_printed_date(text, JulianDate))


def gregorian(text: str) -> JDN:
    return jdn_from_gregorian(parse_printed_date(text, GregorianDate))


# --- pillai_1911_chronology (Indian Chronology): §233, §235, §236, §240
# --------------------------------------


def test_pillai_1911_chronology_s233_of_15_july_1910(record_comparison: Record) -> None:
    fx = printed("authority/calendar/pillai_1911_chronology_s233")
    assert "New Style" in fx["calendar.statement"] or "Old Style" in fx["calendar.statement"]
    computed = weekday(gregorian(fx["input.date"])).name.title()
    record_comparison(
        fixture=fx.id,
        value="output.weekday",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == fx["output.weekday"]


def test_pillai_1911_chronology_s235_kali_epoch_is_a_friday(record_comparison: Record) -> None:
    fx = printed("authority/calendar/pillai_1911_chronology_s235")
    computed = weekday(julian(fx["input.date"])).name.title()
    record_comparison(
        fixture=fx.id,
        value="output.weekday",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == fx["output.weekday"]


def test_pillai_1911_chronology_s236_first_new_style_day_follows_the_last_old_style_day(
    record_comparison: Record,
) -> None:
    fx = printed("authority/calendar/pillai_1911_chronology_s236")
    # each printed date carries its week-day, which the parser checks in its own style
    last_old = julian(fx["input.last_old_style"])
    first_new = gregorian(fx["output.first_new_style"])
    computed = first_new.days_since(last_old)
    record_comparison(
        fixture=fx.id,
        value="output.first_new_style",
        computed=computed,
        tolerance=0,
        tolerance_reason="the first New Style day is the civil day after the last Old Style day",
    )
    assert computed == 1


def test_pillai_1911_chronology_s240_as_emended(record_comparison: Record) -> None:
    fx = printed("authority/calendar/pillai_1911_chronology_s240")
    computed = weekday(gregorian(fx["input.date"])).name.title()
    record_comparison(
        fixture=fx.id,
        value="output.weekday",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + "; compared with the emendation, the print says Sunday",
    )
    assert computed == fx["output.weekday"]


# --- bag_2003_julian_days (Kali ahargaṇa and Julian day): Examples 1 and 2, Table 1
# -------------------


def test_bag_2003_julian_days_ex1_julian_day(record_comparison: Record) -> None:
    fx = printed("authority/calendar/bag_2003_julian_days_ex1")
    computed = gregorian(fx["input.date"]).value
    record_comparison(
        fixture=fx.id, value="output.jd", computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == fx["output.jd"]


def test_bag_2003_julian_days_ex1_kali_ahargana(record_comparison: Record) -> None:
    fx = printed("authority/calendar/bag_2003_julian_days_ex1")
    computed = days_from_epoch(eras()["kali"], gregorian(fx["input.date"]))
    record_comparison(
        fixture=fx.id, value="output.ka", computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == fx["output.ka"]


def test_bag_2003_julian_days_ex1_weekday_from_the_julian_day(record_comparison: Record) -> None:
    fx = printed("authority/calendar/bag_2003_julian_days_ex1")
    # the paper counts JD's remainder from Monday, as Weekday's values do
    computed = weekday(gregorian(fx["input.date"])).value
    record_comparison(
        fixture=fx.id,
        value="output.jd_remainder",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == fx["output.jd_remainder"]


def test_bag_2003_julian_days_ex1_weekday_from_the_kali_count(record_comparison: Record) -> None:
    fx = printed("authority/calendar/bag_2003_julian_days_ex1")
    # the paper counts KA's remainder from Friday, the Kali epoch's week-day
    day = weekday(gregorian(fx["input.date"]))
    computed = (day.value - Weekday.FRIDAY.value) % len(Weekday)
    record_comparison(
        fixture=fx.id,
        value="output.ka_remainder",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == fx["output.ka_remainder"]


def test_bag_2003_julian_days_ex2_kali_count_to_julian_day(record_comparison: Record) -> None:
    fx = printed("authority/calendar/bag_2003_julian_days_ex2")
    day = day_from_epoch_days(eras()["kali"], fx["input.ka"])
    assert isinstance(day, JDN)
    record_comparison(
        fixture=fx.id,
        value="output.jd",
        computed=day.value,
        tolerance=0,
        tolerance_reason=EXACT + "; compared with the emendation, the print says 2022616",
    )
    assert day.value == fx["output.jd"]


def test_bag_2003_julian_days_ex2_julian_day_to_christian_date(record_comparison: Record) -> None:
    fx = printed("authority/calendar/bag_2003_julian_days_ex2")
    computed = julian_from_jdn(JDN(fx["output.jd"]))
    record_comparison(
        fixture=fx.id,
        value="output.date",
        computed=str(computed),
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == parse_printed_date(fx["output.date"], JulianDate)


def _table1_year_start(row: dict[str, Any]) -> JDN:
    """The paper's Table 1 constant for a year, by its Example 1 rule.

    Example 1: JD of 10 July 2001 = Table 1 (2000) + Table 2 (one year, 365)
    + Table 3 (10 July, 191), so Table 1 (Y) is the JD of 1 January Y + 1
    less 365 and less one day. Each row is read in its own mark's calendar.
    """
    year = row["year"] + 1
    first = (
        jdn_from_julian(JulianDate(year, 1, 1))
        if row["calendar"] == "J"
        else jdn_from_gregorian(GregorianDate(year, 1, 1))
    )
    return first.plus_days(-366)


def test_bag_2003_julian_days_table1_constants_follow_example_1(record_comparison: Record) -> None:
    fx = printed("authority/calendar/bag_2003_julian_days_table1")
    rows = fx.rows("table")
    computed = [_table1_year_start(r).value for r in rows]
    record_comparison(
        fixture=fx.id, value="table", computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == [r["jd"] for r in rows]


def test_bag_2003_julian_days_table1_kali_counts(record_comparison: Record) -> None:
    fx = printed("authority/calendar/bag_2003_julian_days_table1")
    kali = eras()["kali"]
    assert kali.epoch is not None
    rows = fx.rows("table")
    computed = [JDN(r["jd"]).days_since(kali.epoch) for r in rows]
    record_comparison(
        fixture=fx.id, value="table", computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == [r["ka"] for r in rows]
    # the era's own count agrees in its range and gives not_in_range before it
    for r, n in zip(rows, computed, strict=True):
        expected = n if n >= 0 else NOT_IN_RANGE
        assert days_from_epoch(kali, JDN(r["jd"])) == expected


def test_bag_2003_julian_days_table1_reform_alignment(record_comparison: Record) -> None:
    fx = printed("authority/calendar/bag_2003_julian_days_table1")
    assert "1582" in fx["calendar.statement"]
    # the rows printed for one year in both calendars (1500 (J) and 1500 (G))
    by_year: dict[int, dict[str, int]] = {}
    for r in fx.rows("table"):
        by_year.setdefault(r["year"], {})[r["calendar"]] = r["jd"]
    both = [y for y, cals in by_year.items() if set(cals) == {"J", "G"}]
    assert both
    computed = [
        jdn_from_julian(JulianDate(y + 1, 1, 1)).days_since(
            jdn_from_gregorian(GregorianDate(y + 1, 1, 1))
        )
        for y in both
    ]
    record_comparison(
        fixture=fx.id, value="table", computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == [by_year[y]["J"] - by_year[y]["G"] for y in both]


# --- sewell_dikshit_1896 Table I: the A.D. date and week-day of each year's Meṣa saṅkrānti
# ------------------

_CELL = re.compile(r"^(?P<d>\d+) (?P<m>[A-Za-z]+\.?) \((?P<doy>\d+)\)$")
_YEAR = re.compile(r"^\*?(?P<y>\d+)")


def _last_old_style_year(fx: Printed) -> int:
    """The A.D. year of the change of style, from the fixture's printed statement.

    The footnote of sewell_dikshit_1896 p. 53 (each fixture's calendar.statement) puts New Style
    into the Tables from September of that year, so a Meṣa saṅkrānti (March or
    April) is New Style from the next A.D. year on.
    """
    m = re.search(r"from Sept\. A\.D\. (?P<y>\d+)", fx["calendar.statement"])
    assert m is not None, fx["calendar.statement"]
    return int(m["y"])


def _table1_cell(cell: str, year: int, old_style_to: int) -> tuple[JDN, int]:
    """A col. 13 or col. 19 cell ('18 Mar. (77)') in its year's style, and its printed day count."""
    m = _CELL.match(cell)
    assert m is not None, cell
    text = f"{m['d']} {m['m']} {year}"
    day = gregorian(text) if year > old_style_to else julian(text)
    return day, int(m["doy"])


def _day_of_year(day: JDN, year: int, old_style_to: int) -> int:
    first = (
        jdn_from_gregorian(GregorianDate(year, 1, 1))
        if year > old_style_to
        else jdn_from_julian(JulianDate(year, 1, 1))
    )
    return day.days_since(first) + 1


def _sat0(day: JDN) -> int:
    """sewell_dikshit_1896's week-day numeral: 0 for Saturday (the printed pairs '0 Sat.', '6
    Fri.')."""
    return (weekday(day).value - Weekday.SATURDAY.value) % len(Weekday)


def _ad_year(cell: str) -> int:
    """The first A.D. year of a col. 5 span ('*400-401', '1800§- 1')."""
    m = _YEAR.match(cell)
    assert m is not None, cell
    return int(m["y"])


def _sewell_dikshit_1896_rows(
    fx: Printed, date_col: str, n_col: str, name_col: str
) -> list[dict[str, Any]]:
    years = {r["c1"]: r["c5"] for r in fx.rows("years")}
    # every col. 13 row has its col. 5 row (the fixtures key the same rows of both)
    missing = [r["c1"] for r in fx.rows("mesha") if r["c1"] not in years]
    assert not missing, (fx.id, missing)
    out = []
    for r in fx.rows("mesha"):
        out.append(
            {
                "year": _ad_year(years[r["c1"]]),
                "cell": r[date_col],
                "n": r[n_col],
                "name": r[name_col],
            }
        )
    return out


sewell_dikshit_1896_FIXTURES = [
    "sewell_dikshit_1896_table1_p130",
    "sewell_dikshit_1896_table1_p166",
    "sewell_dikshit_1896_table1_p204",
    "sewell_dikshit_1896_table1_p214",
    "sewell_dikshit_1896_table1_p216",
    "sewell_dikshit_1896_table1_p222",
]


@pytest.mark.parametrize("name", sewell_dikshit_1896_FIXTURES)
def test_sewell_dikshit_1896_table1_mesha_dates(name: str, record_comparison: Record) -> None:
    fx = printed(f"authority/calendar/{name}")
    assert "New Style" in fx["calendar.statement"]
    old_style_to = _last_old_style_year(fx)
    computed: list[list[Any]] = []
    expected: list[list[Any]] = []
    for r in _sewell_dikshit_1896_rows(fx, "c13", "c14_n", "c14_day"):
        day, doy = _table1_cell(r["cell"], r["year"], old_style_to)
        name_ok = weekday(day).name.lower().startswith(r["name"].lower())
        computed.append([_day_of_year(day, r["year"], old_style_to), _sat0(day), name_ok])
        expected.append([doy, r["n"], True])
    record_comparison(
        fixture=fx.id,
        value="mesha",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (per row: day of the year, week-day numeral, name agrees)",
    )
    assert computed == expected


def test_sewell_dikshit_1896_table1_p130_caitra_dates(record_comparison: Record) -> None:
    fx = printed("authority/calendar/sewell_dikshit_1896_table1_p130")
    old_style_to = _last_old_style_year(fx)
    computed: list[list[Any]] = []
    expected: list[list[Any]] = []
    for r in _sewell_dikshit_1896_rows(fx, "c19", "c20_n", "c20_day"):
        day, doy = _table1_cell(r["cell"], r["year"], old_style_to)
        name_ok = weekday(day).name.lower().startswith(r["name"].lower())
        computed.append([_day_of_year(day, r["year"], old_style_to), _sat0(day), name_ok])
        expected.append([doy, r["n"], True])
    record_comparison(
        fixture=fx.id,
        value="mesha",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (cols. 19–20 per row: day of the year, numeral, name agrees)",
    )
    assert computed == expected


def test_sewell_dikshit_1896_table1_new_style_mark_is_the_first_new_style_row(
    record_comparison: Record,
) -> None:
    fx = printed("authority/calendar/sewell_dikshit_1896_table1_p214")
    assert "New Style" in fx["calendar.statement_new_style"]
    years = {r["c1"]: r["c5"] for r in fx.rows("years")}
    rows = fx.rows("mesha")
    marked = [r["c1"] for r in rows if r["mark"] == "×"]
    old_style_to = _last_old_style_year(fx)
    first_new = [r["c1"] for r in rows if _ad_year(years[r["c1"]]) > old_style_to][:1]
    record_comparison(
        fixture=fx.id,
        value="mesha",
        computed=first_new,
        tolerance=0,
        tolerance_reason="the row the 'New Style' footnote marks is the first of A.D. 1753",
    )
    assert first_new == marked


@pytest.mark.parametrize(
    "name", ["sewell_dikshit_1896_table1_p216", "sewell_dikshit_1896_table1_p222"]
)
def test_sewell_dikshit_1896_table1_gregorian_century_year_is_common(
    name: str, record_comparison: Record
) -> None:
    fx = printed(f"authority/calendar/{name}")
    m = re.search(r"\d{4}", fx["leap_statement"])
    assert m is not None and "not" in fx["leap_statement"]
    century = int(m[0])
    computed = jdn_from_gregorian(GregorianDate(century, 3, 1)).days_since(
        jdn_from_gregorian(GregorianDate(century, 2, 1))
    )
    record_comparison(
        fixture=fx.id,
        value="leap_statement",
        computed=computed,
        tolerance=0,
        tolerance_reason="the footnote's common year: February has 28 days in the Gregorian count",
    )
    assert computed == 28
