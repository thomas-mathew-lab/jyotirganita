"""The Sūrya-siddhānta's counts of years and days, the weekday and the lords.

The ages' totals and the years to the end of the Kṛta (i.15–23, i.45–47)
against Raṅganātha's text-computed chains (suryasiddhanta_hall_1859) and Whitney's tables
(suryasiddhanta_burgess_1860); the sum of days by the lunar-date rule (i.48–51,
``ahargana.lunar_reckoning``) against Whitney's two computations and Bag's
three (bag_2001); the engine's count from creation and from the Kali
epoch (``ahargana.civil_days_since_creation``) against the sums Whitney
and Bag print; the weekday (i.51–52) against Whitney, Bag and
Parameśvara (suryasiddhanta_paramesvara_1957, text-computed). Every example but
suryasiddhanta_paramesvara_1957's and suryasiddhanta_hall_1859's is
``editor_computed``; all are integers, compared exactly. Where an
editor's figure is not reproduced the test says so, names the cause it
asserts, and cites the issue.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction
from functools import cache

import pytest
from authority_kit import printed
from surya_kit import EXACT, FX, METHODS, day, integer, model, reckoning, run, value

from jyotirganita.core.calendar import Weekday, jdn_from_gregorian, weekday
from jyotirganita.core.types import JDN, GregorianDate
from jyotirganita.siddhantic.ahargana import DAYS_PER_WEEK, LunarReckoning, lunar_reckoning

Record = Callable[..., None]
YUGA = FX + "whitney_yuga_days"
ELAPSED = FX + "whitney_elapsed_to_kali"
suryasiddhanta_hall_1859_ELAPSED = FX + "ranganatha_elapsed_to_krta_end"
suryasiddhanta_hall_1859_TOTALS = FX + "ranganatha_yuga_kalpa_totals"
W1860 = FX + "whitney_ahargana_example"
SOLAR = FX + "whitney_eclipse_solar_ahargana"
LUNAR = FX + "whitney_eclipse_lunar_ahargana"
BAG = FX + "bag_epoch_ahargana"
BAG_JD = FX + "bag_kali_jd"
LORDS = FX + "whitney_weekday_lords"
TRETA = FX + "paramesvara_treta_ahargana"
JAN_1_1860 = GregorianDate(1860, 1, 1)


def yuga_years() -> int:
    return integer("mahayuga.solar_years")


def quarter_years(share: str) -> Fraction:
    """A quarter-age in years: its share of the tenth parts of the age (i.17)."""
    return Fraction(
        integer(f"yuga.quarters.share.{share}") * value("yuga.quarters.part") * yuga_years()
    )


# --- Whitney's table of the age's days and months (i.34–40) -------------------------


@cache
def _yuga_days() -> dict[str, Fraction]:
    """The table's two columns from the text's numbers: the age, and Whitney's lesser part."""
    fx = printed(YUGA)
    part = Fraction(fx["input.sidereal_solar_years.part_1080000"], yuga_years())
    sun, moon = integer("sun.revolutions"), integer("moon.revolutions")
    civil = integer("asterisms.revolutions") - sun  # i.34: the sidereal days
    solar = yuga_years() * integer("time.year.months")
    synodic = moon - sun
    lunar_days = synodic * integer("time.month.days")
    age = {
        "civil_days": Fraction(civil),
        "solar_months": Fraction(solar),
        "synodic_months": Fraction(synodic),
        "intercalary_months": Fraction(synodic - solar),
        "lunar_days": Fraction(lunar_days),
        "omitted_lunar_days": Fraction(lunar_days - civil),
    }
    out = {f"output.{k}.age_4320000": v for k, v in age.items()}
    out |= {f"output.{k}.part_1080000": v * part for k, v in age.items()}
    return out


@pytest.mark.parametrize("name", sorted(_yuga_days()))
def test_whitney_yuga_days(name: str, record_comparison: Record) -> None:
    computed = _yuga_days()[name]
    record_comparison(
        fixture=YUGA, value=name, computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == printed(YUGA)[name]


def test_the_age_s_stated_counts_agree_with_whitney_s_table(record_comparison: Record) -> None:
    # the text's own statements of i.37–40 against the table's differences (the lunar
    # months are stated only as a rule, i.35, and taken from the table's difference)
    computed = (
        integer("yuga.civil_days"),
        integer("yuga.solar_months"),
        integer("yuga.intercalary_months"),
        integer("yuga.lunar_days"),
        integer("yuga.omitted_days"),
    )
    fx = printed(YUGA)
    record_comparison(
        fixture=YUGA,
        value="output.omitted_lunar_days.age_4320000",
        computed=computed[-1],
        tolerance=0,
        tolerance_reason=EXACT + " (the six stated counts of i.37–40 against the table)",
    )
    assert computed == tuple(
        fx[f"output.{k}.age_4320000"]
        for k in (
            "civil_days",
            "solar_months",
            "intercalary_months",
            "lunar_days",
            "omitted_lunar_days",
        )
    )


# --- the years to the end of the Kṛta and to the Kali epoch (i.45–48) ---------------


@cache
def _suryasiddhanta_hall_1859_chain() -> dict[str, Fraction]:
    """Raṅganātha's chain (suryasiddhanta_hall_1859 p. 34) on the text's numbers; the counts stated
    only in
    words in the commentary (the seven twilights) are the commentary's inputs."""
    fx = printed(suryasiddhanta_hall_1859_ELAPSED)
    mahayuga = integer("time.divine_year.divine_days") * integer("mahayuga.divine_years")
    manu = mahayuga * integer("kalpa.manu.yugas")
    manus = manu * integer("kalpa.elapsed.manus")
    with_sandhis = manus + fx["input.sandhis_word"] * quarter_years("krta")
    with_yugas = with_sandhis + integer("kalpa.elapsed.yugas") * mahayuga
    kalpa_elapsed = with_yugas + quarter_years("krta")
    creation = integer("creation.years") * integer("time.divine_year.divine_days")
    return {
        "output.mahayuga": Fraction(mahayuga),
        "output.manu": Fraction(manu),
        "output.manus_total": Fraction(manus),
        "output.manus_with_sandhis": with_sandhis,
        "output.with_elapsed_yugas": with_yugas,
        "output.kalpa_elapsed": kalpa_elapsed,
        "output.elapsed_to_krta_end": kalpa_elapsed - creation,
    }


@pytest.mark.parametrize("name", sorted(_suryasiddhanta_hall_1859_chain()))
def test_ranganatha_years_to_the_end_of_the_krta(name: str, record_comparison: Record) -> None:
    computed = _suryasiddhanta_hall_1859_chain()[name]
    record_comparison(
        fixture=suryasiddhanta_hall_1859_ELAPSED,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == printed(suryasiddhanta_hall_1859_ELAPSED)[name]


def test_the_chain_ends_at_the_text_s_stated_years(record_comparison: Record) -> None:
    # i.47 states the years to the end of the Kṛta as one number (kalpa.elapsed_to_krta_end)
    computed = integer("kalpa.elapsed_to_krta_end")
    record_comparison(
        fixture=suryasiddhanta_hall_1859_ELAPSED,
        value="output.elapsed_to_krta_end",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (the text's stated figure, i.47)",
    )
    assert computed == printed(suryasiddhanta_hall_1859_ELAPSED)["output.elapsed_to_krta_end"]


@cache
def _suryasiddhanta_hall_1859_totals() -> dict[str, Fraction]:
    """suryasiddhanta_hall_1859 p. 15: the ages and their twilights in divine years; the Manu in
    years."""
    fx = printed(suryasiddhanta_hall_1859_TOTALS)
    divine = integer("mahayuga.divine_years")
    part, sandhi = value("yuga.quarters.part"), value("yuga.sandhi.part")
    out: dict[str, Fraction] = {}
    for q in ("krta", "treta", "dvapara", "kali"):
        whole = integer(f"yuga.quarters.share.{q}") * part * divine
        out[f"output.sandhi_part.{q}"] = whole * sandhi
        each = whole * sandhi / 2  # the twilight is shared, half before and half after
        out[f"output.sandhi_each.{q}"] = each
        out[f"output.{q}.adi_sandhi"] = each
        out[f"output.{q}.anta_sandhi"] = each
        out[f"output.{q}.mana"] = whole - 2 * each
    manu = yuga_years() * integer("kalpa.manu.yugas")
    out["output.manu_years"] = Fraction(manu)
    out["output.manu_with_sandhi_years"] = manu + Fraction(fx["input.krta_years"])
    out["output.mahayuga_years_words"] = Fraction(yuga_years())
    return out


@pytest.mark.parametrize("name", sorted(_suryasiddhanta_hall_1859_totals()))
def test_ranganatha_ages_and_twilights(name: str, record_comparison: Record) -> None:
    computed = _suryasiddhanta_hall_1859_totals()[name]
    record_comparison(
        fixture=suryasiddhanta_hall_1859_TOTALS,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT
        + " (i.15–19; the twilight halved before and after, suryasiddhanta_hall_1859 p. 15)",
    )
    assert computed == printed(suryasiddhanta_hall_1859_TOTALS)[name]


@cache
def _whitney_elapsed() -> dict[str, Fraction]:
    fx = printed(ELAPSED)
    to_krta = Fraction(integer("kalpa.elapsed_to_krta_end"))
    since = quarter_years("treta") + quarter_years("dvapara") + fx["input.of_iron_age"]
    return {
        "output.v47.elapsed_to_end_of_golden_age": to_krta,
        "output.creation_to_end_of_last_golden_age": to_krta,
        "output.sum_silver_brazen_iron": since,
        "output.total_creation_to_april_1859": to_krta + since,
    }


@pytest.mark.parametrize("name", sorted(_whitney_elapsed()))
def test_whitney_years_from_creation(name: str, record_comparison: Record) -> None:
    computed = _whitney_elapsed()[name]
    record_comparison(
        fixture=ELAPSED, value=name, computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == printed(ELAPSED)[name]


# --- the sum of days by the lunar-date rule (i.48–51) --------------------------------


@cache
def _whitney_1860() -> dict[str, int]:
    fx = printed(W1860)
    s = lunar_reckoning(
        reckoning(),
        fx["input.complete_years"],
        fx["input.months_elapsed_current_year"],
        fx["input.lunar_days_elapsed_current_month"],
    )
    return {
        "output.number_of_months": s.kali_years * reckoning().months_per_year,
        "output.whole_months_elapsed": s.solar_months,
        "output.proportion1.intercalary_months": s.intercalary_months,
        "output.whole_lunar_months": s.lunar_months,
        "output.number_of_lunar_days": s.lunar_months * reckoning().days_per_month,
        "output.whole_lunar_days_elapsed": s.tithis,
        "output.proportion2.omitted_lunar_days": s.omitted_days,
        "output.ahargana_to_target_date": s.ahargana,
    }


@pytest.mark.parametrize("name", sorted(_whitney_1860()))
def test_whitney_sum_of_days_1860(name: str, record_comparison: Record) -> None:
    computed = _whitney_1860()[name]
    record_comparison(
        fixture=W1860,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (both proportions' fractions dropped, as printed)",
    )
    assert computed == printed(W1860)[name]


@cache
def _whitney_1854() -> dict[str, int]:
    fx = printed(SOLAR)
    s = lunar_reckoning(
        reckoning(),
        fx["output.complete_years_to_march_1854"],
        fx["input.month_of_current_year"],
        fx["input.add_for_current_month"],
    )
    to_krta = integer("kalpa.elapsed_to_krta_end")
    return {
        "output.complete_years_to_march_1854": to_krta
        + int(quarter_years("treta") + quarter_years("dvapara"))
        + fx["input.kali_to_calivahana"]
        + fx["input.era_years_elapsed"],
        "output.solar_months": s.kali_years * reckoning().months_per_year,
        "output.whole_solar_months": s.solar_months,
        "output.proportion1.intercalary_months": s.intercalary_months,
        "output.lunar_months_elapsed": s.lunar_months,
        "output.lunar_days": s.lunar_months * reckoning().days_per_month,
        "output.whole_lunar_days": s.tithis,
        "output.proportion2.omitted_lunar_days": s.omitted_days,
        "output.ahargana_may_1854": s.ahargana,
    }


@pytest.mark.parametrize("name", sorted(_whitney_1854()))
def test_whitney_sum_of_days_1854(name: str, record_comparison: Record) -> None:
    computed = _whitney_1854()[name]
    record_comparison(
        fixture=SOLAR, value=name, computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == printed(SOLAR)[name]


@cache
def _bag(case: str, c: LunarReckoning | None = None) -> dict[str, int]:
    fx = printed(BAG)
    s = lunar_reckoning(c or reckoning(), fx[f"output.{case}.years"], 0, 0)
    return {
        f"output.{case}.saura_months": s.solar_months,
        f"output.{case}.intercalary_months": s.intercalary_months,
        f"output.{case}.months_sum": s.lunar_months,
        f"output.{case}.lunar_days": s.tithis,
        f"output.{case}.omitted_days": s.omitted_days,
        f"output.{case}.ahargana": s.ahargana,
        f"output.{case}.remainder": s.ahargana % DAYS_PER_WEEK,
    }


@cache
def _bag_years() -> dict[str, Fraction]:
    fx = printed(BAG)
    s2k = fx["input.t1.years_before_saka"]
    return {
        "output.i.years": integer("kalpa.elapsed_to_krta_end")
        + quarter_years("treta")
        + quarter_years("dvapara"),
        "output.ii.years": Fraction(s2k + fx["input.t2.saka_year"]),
        "output.iii.years": Fraction(s2k + fx["input.t3.saka_year"]),
    }


# Bag's two fixtures and Parameśvara's Tretā count name both methods.
# Bag's count arithmetic (his years, sums of days and case (ii) months)
# reads the base text's data directly, the base's by construction, and runs once;
# the tests that go through an engine run under each method and record which
# .


@pytest.mark.parametrize("name", sorted(_bag_years()))
def test_bag_years(name: str, record_comparison: Record) -> None:
    computed = _bag_years()[name]
    record_comparison(
        fixture=BAG, value=name, computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == printed(BAG)[name]


BAG_REPRODUCED = sorted([*_bag("iii"), "output.i.saura_months", "output.ii.saura_months"])


@pytest.mark.parametrize("name", BAG_REPRODUCED)
def test_bag_sum_of_days(name: str, record_comparison: Record) -> None:
    computed = {**_bag("i"), **_bag("ii"), **_bag("iii")}[name]
    record_comparison(
        fixture=BAG,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (fractions dropped)",
    )
    assert computed == printed(BAG)[name]


@pytest.mark.parametrize("method", METHODS)
def test_bag_i_is_not_the_text_s_count_to_the_kali_epoch(
    method: str, record_comparison: Record
) -> None:
    # NOT reproduced: the rule on the text's numbers gives the engine's
    # count to the Kali epoch. Bag's case (i) prints one intercalary month less than the
    # proportion's exact whole quotient, and omitted days that neither the text's divisor
    # nor the one he says he used gives; his later steps follow from his own figures
    fx = printed(BAG)
    c = reckoning()
    steps = _bag("i")
    computed = steps["output.i.ahargana"]
    record_comparison(
        fixture=BAG,
        value="output.i.ahargana",
        method=method,
        computed=computed,
        tolerance=0,
        tolerance_reason=(
            "NOT reproduced: the text's numbers give the engine's count to the "
            "Kali epoch; Bag's intercalary months and omitted days differ from the rule's"
        ),
    )
    assert computed == model(method).days_to_epoch != fx["output.i.ahargana"]
    exact = Fraction(fx["output.i.saura_months"] * c.intercalary_months_per_yuga)
    assert (exact / c.solar_months_per_yuga).denominator == 1
    assert steps["output.i.intercalary_months"] == fx["output.i.intercalary_months"] + 1
    months = fx["output.i.saura_months"] + fx["output.i.intercalary_months"]
    assert months == fx["output.i.months_sum"]
    assert months * c.days_per_month == fx["output.i.lunar_days"]
    used = fx["output.i.lunar_days"] * fx["input.omitted_days_used"] // c.lunar_days_per_yuga
    assert used == fx["output.i.omitted_days"] + 1
    assert fx["output.i.lunar_days"] - fx["output.i.omitted_days"] == fx["output.i.ahargana"]
    assert computed % DAYS_PER_WEEK == fx["output.i.remainder"]


def test_bag_ii_rounds_the_intercalary_months_up(record_comparison: Record) -> None:
    # NOT reproduced: Bag takes the intercalary months of case (ii) as
    # the next whole month where the rule drops the fraction (suryasiddhanta_burgess_1860 i.48–51;
    # Whitney's two
    # computations drop it); with his month the rest of his steps follow exactly
    fx = printed(BAG)
    steps = _bag("ii")
    computed = steps["output.ii.intercalary_months"]
    record_comparison(
        fixture=BAG,
        value="output.ii.intercalary_months",
        computed=computed,
        tolerance=0,
        tolerance_reason=(
            "NOT reproduced: the rule drops the fraction of the intercalary "
            "months; Bag's figure is one more, and his later steps follow from it"
        ),
    )
    assert computed + 1 == fx["output.ii.intercalary_months"]
    c = reckoning()
    months = fx["output.ii.saura_months"] + fx["output.ii.intercalary_months"]
    tithis = months * c.days_per_month
    omitted = tithis * c.omitted_days_per_yuga // c.lunar_days_per_yuga
    assert (months, tithis, omitted, tithis - omitted) == (
        fx["output.ii.months_sum"],
        fx["output.ii.lunar_days"],
        fx["output.ii.omitted_days"],
        fx["output.ii.ahargana"],
    )
    assert (tithis - omitted) % DAYS_PER_WEEK == fx["output.ii.remainder"]


# --- the engine's count (i.48–51 and i.45–47) ----------------------------------------


def test_the_engine_s_count_from_creation_on_1860_jan_1(record_comparison: Record) -> None:
    computed = day(jdn_from_gregorian(JAN_1_1860)).creation_count
    record_comparison(
        fixture=W1860,
        value="output.ahargana_to_target_date",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (the engine's count at Laṅkā's midnight beginning the day)",
    )
    assert computed == printed(W1860)["output.ahargana_to_target_date"]


def test_the_engine_s_count_from_the_iron_age_for_the_eclipse(record_comparison: Record) -> None:
    # suryasiddhanta_burgess_1860 p. 434: the lunar eclipse of 1860 Feb 6, the count from the Kali
    # epoch (i.56)
    computed = day(jdn_from_gregorian(GregorianDate(1860, 2, 6))).ahargana.day
    record_comparison(
        fixture=LUNAR,
        value="output.sum_of_days",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == printed(LUNAR)["output.sum_of_days"]


@cache
def _bag_jd(method: str = "suryasiddhanta") -> dict[str, int]:
    fx = printed(BAG_JD)
    epoch = run(method).runs_from
    return {
        "output.a.kali_jd_sunrise": epoch.value,
        "output.b.discussion.kali_jd": epoch.value,
        "output.a.vm_epoch_jd": epoch.plus_days(fx["input.b.vm_epoch_ka"]).value,
        "output.b.discussion.vm_epoch_jd": epoch.plus_days(fx["input.b.vm_epoch_ka"]).value,
        "output.a.bg_epoch_jd": epoch.plus_days(fx["input.b.bg_epoch_ka"]).value,
        "output.b.discussion.bg_epoch_jd": epoch.plus_days(fx["input.b.bg_epoch_ka"]).value,
        "output.a.bg_epoch_ka": day(JDN(fx["input.b.bg_epoch_jd"]), method).ahargana.day,
    }


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("name", sorted(_bag_jd()))
def test_bag_kali_julian_days(name: str, method: str, record_comparison: Record) -> None:
    computed = _bag_jd(method)[name]
    record_comparison(
        fixture=BAG_JD,
        value=name,
        method=method,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (the engine's Kali epoch, the record's JDN, plus the count)",
    )
    assert computed == printed(BAG_JD)[name]


# --- the weekday and the lords (i.51–52) ---------------------------------------------


def test_the_engine_s_weekday_on_1860_jan_1(record_comparison: Record) -> None:
    jdn = jdn_from_gregorian(JAN_1_1860)
    computed = run().day(jdn).weekday.name.capitalize()
    record_comparison(
        fixture=LORDS,
        value="output.weekday.name",
        computed=computed,
        tolerance=0,
        tolerance_reason="the weekday's name: exact",
    )
    assert computed == printed(LORDS)["output.weekday.name"]
    assert run().day(jdn).weekday == weekday(jdn)


@cache
def _lords() -> dict[str, int | str]:
    """Whitney's arithmetic of i.51–52 from the engine's count (the days counted from Sunday)."""
    fx = printed(LORDS)
    count = day(jdn_from_gregorian(JAN_1_1860)).creation_count
    day_order = {
        fx[f"input.succession.{b}.day"]: b.capitalize()
        for b in ("sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn")
    }
    q, r = divmod(count + 1, DAYS_PER_WEEK)
    month_days = integer("time.month.days")
    year_days = month_days * integer("time.year.months")
    months = count // month_days
    # a remainder of nought is counted as the seventh, the quotient one less
    # (suryasiddhanta_burgess_1860 p. 177)
    m_q, m_r = divmod(months * fx["input.month_lord.multiplier"], DAYS_PER_WEEK)
    m_r += 1
    if m_r > DAYS_PER_WEEK:
        m_q, m_r = m_q + 1, m_r - DAYS_PER_WEEK
    y_r = (count // year_days * fx["input.year_lord.multiplier"]) % DAYS_PER_WEEK + 1
    return {
        "output.weekday.quotient": q,
        "output.weekday.remainder": r,
        "output.month_lord.months_elapsed": months,
        "output.month_lord.product": months * fx["input.month_lord.multiplier"],
        "output.month_lord.quotient": m_q,
        "output.month_lord.remainder": m_r,
        "output.month_lord.name": day_order[m_r],
        "output.year_lord.remainder": y_r,
        "output.year_lord.name": day_order[y_r],
    }


@pytest.mark.parametrize("name", sorted(_lords()))
def test_whitney_lords_of_the_day_month_and_year(name: str, record_comparison: Record) -> None:
    computed = _lords()[name]
    record_comparison(
        fixture=LORDS,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (i.51–52 on the engine's count; a remainder 0 is the seventh)",
    )
    assert computed == printed(LORDS)[name]


@pytest.mark.parametrize("method", METHODS)
def test_the_kali_epoch_is_a_friday(method: str, record_comparison: Record) -> None:
    # Bag's remainder table: case (i)'s remainder 5 counted from Sunday is Friday
    epoch = run(method).runs_from
    computed = run(method).day(epoch).weekday
    record_comparison(
        fixture=BAG,
        value="output.i.remainder",
        method=method,
        computed=model(method).days_to_epoch % DAYS_PER_WEEK,
        tolerance=0,
        tolerance_reason=EXACT + " (the days to the Kali epoch mod 7, from Sunday)",
    )
    assert computed is Weekday.FRIDAY
    rows = {
        r["remainder"]: r["suryasiddhanta_epoch_r1"]
        for r in printed(BAG).rows("output.remainder_table")
    }
    assert rows[model(method).days_to_epoch % DAYS_PER_WEEK] == computed.name.capitalize()


@pytest.mark.parametrize("method", METHODS)
def test_paramesvara_treta_start_remainder(method: str, record_comparison: Record) -> None:
    # suryasiddhanta_paramesvara_1957 p. 17 (text_computed): the count to the start of the Tretā,
    # from Sunday, leaves 3
    days = model(method).days_to_epoch - (
        (quarter_years("treta") + quarter_years("dvapara"))
        * integer("yuga.civil_days")
        / yuga_years()
    )
    assert days.denominator == 1
    computed = int(days) % DAYS_PER_WEEK
    record_comparison(
        fixture=TRETA,
        value="output.remainder",
        method=method,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == printed(TRETA)["output.remainder"]
