"""The Āryabhaṭīya's day count and yuga constants against the printed examples.

Every example here is ``editor_computed`` (Shukla's solutions in laghubhaskariya_1963 and
mahabhaskariya_1960, the editors' in aryabhatiya_1976): integers in the text's units, so each is
reproduced exactly. Inputs and constants are the loader's values (the
fixture's printed inputs, the text's data); nothing is typed into a test.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from authority_kit import epoch, printed, records, text_value

from jyotirganita.core.calendar import jdn_from_gregorian, parse_printed_date
from jyotirganita.core.calendar import weekday as weekday_of_jdn
from jyotirganita.core.types import GregorianDate
from jyotirganita.siddhantic.ahargana import (
    DAYS_PER_WEEK,
    LunarReckoning,
    ahargana_of_day,
    lunar_reckoning,
    weekday_of_ahargana,
)
from jyotirganita.siddhantic.mean import mean_daily_motion

Record = Callable[..., None]
EXACT = "integers in the text's units: exact"
T = "texts.aryabhatiya."
GREG = "authority/aryabhatiya/laghubhaskariya_1963_ahargana_gregorian_example"
laghubhaskariya_1963_YUGA = "authority/aryabhatiya/laghubhaskariya_1963_yuga_counts"
aryabhatiya_1976_YUGA = "authority/aryabhatiya/aryabhatiya_1976_kalakriya5_yuga_counts"
aryabhatiya_1976_K10 = "authority/aryabhatiya/aryabhatiya_1976_kalakriya10_days"
aryabhatiya_1976_G5 = "authority/aryabhatiya/aryabhatiya_1976_gitika5_days_before_kali"
DAILY = "authority/aryabhatiya/laghubhaskariya_1963_sankaranarayana_daily_motions"


def datum(suffix: str) -> Any:
    """The loader's value of ``texts.aryabhatiya.<suffix>``."""
    return text_value("aryabhatiya", suffix)


def civil_days() -> int:
    """Civil days of a yuga: Earth's rotations less the Sun's revolutions (civil_days.rule)."""
    return int(datum("earth.rotations")) - int(datum("sun.revolutions"))


def reckoning() -> LunarReckoning:
    p = "procedures.ahargana."
    return LunarReckoning(
        datum(p + "saka_to_kali_years"),
        datum(p + "months_per_year"),
        datum(p + "intercalary_months_per_yuga"),
        datum(p + "solar_months_per_yuga"),
        datum(p + "days_per_month"),
        datum(p + "omitted_days_per_yuga"),
        datum(p + "lunar_days_per_yuga"),
    )


# --- laghubhaskariya_1963 I.4–8: the ahargaṇa of January 1, 1963 (Shukla's example) ---------------

STEPS = {
    "output.step1_kali_years": "kali_years",
    "output.step2_solar_months": "solar_months",
    "output.step3_intercalary_months": "intercalary_months",
    "output.step4_lunar_months": "lunar_months",
    "output.step5_tithis": "tithis",
    "output.step6_omitted_days": "omitted_days",
    "output.ahargana": "ahargana",
}


@pytest.mark.parametrize("value", sorted(STEPS))
def test_laghubhaskariya_1963_lunar_reckoning_step(value: str, record_comparison: Record) -> None:
    fx = printed(GREG)
    steps = lunar_reckoning(
        reckoning(),
        fx["input.saka_year_elapsed"],
        fx["input.months_elapsed"],
        fx["input.tithis_elapsed"],
    )
    computed = getattr(steps, STEPS[value])
    record_comparison(
        fixture=GREG, value=value, computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == fx[value]


def test_laghubhaskariya_1963_weekday_remainder(record_comparison: Record) -> None:
    fx = printed(GREG)
    computed = fx["output.ahargana"] % DAYS_PER_WEEK
    record_comparison(
        fixture=GREG,
        value="output.weekday_remainder",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == fx["output.weekday_remainder"]


def test_laghubhaskariya_1963_weekday_counted_from_friday(record_comparison: Record) -> None:
    fx = printed(GREG)
    first = weekday_of_jdn(epoch("kali"))  # the epoch's own day (laghubhaskariya_1963 I.8: Friday)
    computed = weekday_of_ahargana(fx["output.ahargana"], first).name.title()
    record_comparison(
        fixture=GREG, value="output.weekday", computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == fx["output.weekday"] == fx["input.weekday"]


def test_laghubhaskariya_1963_time_base_from_the_gregorian_date(record_comparison: Record) -> None:
    """The time base: the ahargaṇa is the civil days since the Kali epoch day (count_note)."""
    fx = printed(GREG)
    day = jdn_from_gregorian(parse_printed_date(fx["input.date"], GregorianDate))
    computed = ahargana_of_day("aryabhatiya", epoch("kali"), day).day
    record_comparison(
        fixture=GREG,
        value="output.ahargana",
        computed=computed,
        tolerance=0,
        tolerance_reason="whole civil days from the Kali epoch day (JDN arithmetic): exact",
    )
    assert computed == fx["output.ahargana"]


# --- yuga counts (laghubhaskariya_1963 I.4–8 notes; aryabhatiya_1976 Kālakriyā 5)
# --------------------------------


def _yuga_counts() -> dict[str, int]:
    sun, moon = int(datum("sun.revolutions")), int(datum("moon.revolutions"))
    lunar_months = moon - sun
    months, days = int(datum("time_units.months_per_year")), int(datum("time_units.days_per_month"))
    return {
        "solar_years": sun,
        "lunar_months": lunar_months,
        "solar_months": sun * months,
        "intercalary_months": lunar_months - sun * months,
        "lunar_days": lunar_months * days,
        "civil_days": civil_days(),
        "omitted_lunar_days": lunar_months * days - civil_days(),
        "sidereal_days": int(datum("earth.rotations")),
    }


@pytest.mark.parametrize(
    ("fixture", "value"),
    [
        (laghubhaskariya_1963_YUGA, "output.lunar_months"),
        (laghubhaskariya_1963_YUGA, "output.solar_months"),
        (laghubhaskariya_1963_YUGA, "output.intercalary_months"),
        (laghubhaskariya_1963_YUGA, "output.lunar_days"),
        (laghubhaskariya_1963_YUGA, "output.civil_days"),
        (laghubhaskariya_1963_YUGA, "output.omitted_lunar_days"),
        (aryabhatiya_1976_YUGA, "output.solar_years"),
        (aryabhatiya_1976_YUGA, "output.lunar_months"),
        (aryabhatiya_1976_YUGA, "output.civil_days"),
        (aryabhatiya_1976_YUGA, "output.sidereal_days"),
    ],
)
def test_yuga_count(fixture: str, value: str, record_comparison: Record) -> None:
    computed = _yuga_counts()[value.removeprefix("output.")]
    record_comparison(
        fixture=fixture, value=value, computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == printed(fixture)[value]


# --- aryabhatiya_1976 Kālakriyā 10: the days of 3600 Kali years ----------------------------------


@pytest.mark.parametrize("value", ["output.numerator", "output.divisor", "output.days"])
def test_aryabhatiya_1976_kalakriya10(value: str, record_comparison: Record) -> None:
    from fractions import Fraction

    fx = printed(aryabhatiya_1976_K10)
    years, sun = fx["input.kali_years_elapsed"], int(datum("sun.revolutions"))
    computed = {
        "output.numerator": civil_days(),
        "output.divisor": Fraction(sun, years),
        "output.days": Fraction(years * civil_days(), sun),
    }[value]
    record_comparison(
        fixture=aryabhatiya_1976_K10,
        value=value,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == fx[value]


# --- aryabhatiya_1976 Gītikā 5: the years and days from the kalpa's start to Kali ----------------


def _gitika5() -> dict[str, Any]:
    from fractions import Fraction

    yuga = int(datum("sun.revolutions"))
    per_manu = int(datum("kalpa.yugas_per_manu"))
    manu_yugas = int(datum("kali.manus_elapsed")) * per_manu
    to_yuga_yugas = manu_yugas + int(datum("kali.yugas_elapsed"))
    quarter = Fraction(int(datum("kali.quarter_yugas_elapsed")), 4)
    to_kali = to_yuga_yugas + quarter
    days_to_kali = to_kali * civil_days()
    kali_weekday = weekday_of_jdn(epoch("kali"))
    order = list(type(kali_weekday))
    kalpa_start = order[(order.index(kali_weekday) - int(days_to_kali)) % len(order)]
    return {
        "input.yuga_years": yuga,
        "output.to_yuga.years": to_yuga_yugas * yuga,
        "output.to_yuga.days": to_yuga_yugas * civil_days(),
        "output.to_kali.years": to_kali * yuga,
        "output.to_kali.days": days_to_kali,
        "check.kalpa.yugas": int(datum("kalpa.manus")) * per_manu,
        "check.kalpa.years": int(datum("kalpa.manus")) * per_manu * yuga,
        "check.to_kali.manu_yugas": manu_yugas,
        "check.to_kali.yuga_years": yuga,
        "check.to_kali.years": to_kali * yuga,
        "check.to_kali.days": days_to_kali,
        "output.kalpa_start.weekday": kalpa_start.name.title(),
    }


GITIKA5 = [
    "input.yuga_years",
    "output.to_yuga.years",
    "output.to_yuga.days",
    "output.to_kali.years",
    "output.to_kali.days",
    "check.kalpa.yugas",
    "check.kalpa.years",
    "check.to_kali.manu_yugas",
    "check.to_kali.yuga_years",
    "check.to_kali.years",
    "check.to_kali.days",
    "output.kalpa_start.weekday",
]


@pytest.mark.parametrize("value", GITIKA5)
def test_aryabhatiya_1976_gitika5(value: str, record_comparison: Record) -> None:
    computed = _gitika5()[value]
    record_comparison(
        fixture=aryabhatiya_1976_G5,
        value=value,
        computed=computed,
        tolerance=0,
        tolerance_reason="whole years, days and week-days from the text's yuga counts: exact",
    )
    assert computed == printed(aryabhatiya_1976_G5)[value]


# --- the mean daily motions of Śaṅkaranārāyaṇa (text_computed, laghubhaskariya_1963)
# -----------------

DAILY_ELEMENTS = [
    "sun",
    "moon",
    "moon_apogee",
    "moon_node",
    "mars",
    "mercury_sighrocca",
    "jupiter",
    "venus_sighrocca",
    "saturn",
]


@pytest.mark.parametrize("element", DAILY_ELEMENTS)
def test_mean_daily_motion_to_the_printed_place(element: str, record_comparison: Record) -> None:
    """Revolutions × 360 ÷ civil days, to the place printed (seconds; minutes for Saturn).

    The commentator's figures are the exact motion rounded to the nearest
    unit of the last place printed: truncation would give 13° 10′ 34″ for
    the Moon (printed 35″), 6′ 40″ for its apogee (41″), 3′ 10″ for its
    node (11″) and 1° 36′ 7″ for Venus's śīghrocca (8″). The rounding is
    read off this example only; nothing in the engine uses it (the gati is
    keyed with the day's rules).
    """
    from fractions import Fraction

    from jyotirganita.core.exact import Rounding, round_to

    fx = printed(DAILY)
    name = f"output.{element}"
    rev = abs(int(datum(f"{element}.revolutions")))
    raw = records().fixtures[DAILY]
    parts = next(v for v in raw.values if v.key.endswith("#" + name)).raw["value"]
    place = Fraction(1, 60 ** (len(parts) - 1))
    computed = round_to(mean_daily_motion(rev, civil_days()), place, Rounding.HALF_UP)
    record_comparison(
        fixture=DAILY,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason="exact motion rounded to the printed place (text_computed: exact)",
    )
    assert computed == fx[name]
