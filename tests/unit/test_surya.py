"""Unit tests of the Sūrya-siddhānta engine (``siddhantic/surya.py``).

Each rule on synthetic numbers chosen for the arithmetic, never taken from
the text (the printed examples are the authority tests
under ``tests/authority/``), and each refusal: a latitude that is not a
place, a day before ``runs_from``, a preset without an observer, a hybrid
sunrise without its quantum, an unknown body or intraday model, a latitude
away from sunrise. The versed sines, the equations of the
daily motion, the ascensional difference, the precession's halves, a
Kerala place by route (b) and each time correction applied once.
"""

from __future__ import annotations

import dataclasses
from fractions import Fraction
from functools import cache

import pytest

from jyotirganita.core.types import JDN, NOT_MODELLED, Nadika, SiddhanticCivilInstant
from jyotirganita.data.datum import Records, context_for, load_records
from jyotirganita.methods.compose import REPO, ResolvedMethod, build, load_method
from jyotirganita.methods.presets import PresetError, open_preset
from jyotirganita.regions.places import load_place
from jyotirganita.siddhantic.engine import BeforeRunsFrom, Observer
from jyotirganita.siddhantic.surya import (
    Epicycles,
    SineTable,
    SuryaEngine,
    SuryaModel,
    SuryaRefusal,
    ascensional_difference_surya,
    corrected_epicycle,
    manda_equation,
    manda_motion_equation,
    mean_remainder,
    palabha,
    sighra_equation,
    sighra_motion_equation,
)

#: a synthetic table: step 10′, sines 4, 7, 9, 10 (radius 10, quadrant 40′)
TABLE = SineTable(10, (4, 7, 9, 10))
#: its versed sines: the radius less the sine of the complement, 1, 3, 6, 10
VTABLE = SineTable(10, (4, 7, 9, 10), (1, 3, 6, 10))
CIRCLE = 360
RESOLUTION = Fraction(1, 1000)


@cache
def records() -> Records:
    return load_records(REPO, context_for(REPO))


@cache
def resolved() -> ResolvedMethod:
    return load_method("suryasiddhanta", REPO, records=records())


def own_place() -> Observer:
    return load_place(REPO, "meridians", "suryasiddhanta_lanka", records().data)


# --- the sine table (ii.31–33) ------------------------------------------------------------


@pytest.mark.parametrize("step, sines", [(0, (1,)), (-1, (1,)), (10, ())])
def test_a_sine_table_needs_a_positive_step_and_a_sine(step: int, sines: tuple[int, ...]) -> None:
    with pytest.raises(SuryaRefusal, match="positive step"):
        SineTable(step, sines)


def test_radius_and_quadrant() -> None:
    assert TABLE.radius == 10 and TABLE.quadrant == 40


@pytest.mark.parametrize("arc, sine", [(0, 0), (10, 4), (20, 7), (40, 10), (5, 2), (25, 8)])
def test_rsine_takes_the_tabular_sine_and_interpolates_between(arc: int, sine: int) -> None:
    assert TABLE.rsine(arc) == sine


def test_rsine_interpolates_a_fraction_of_a_step() -> None:
    assert TABLE.rsine(Fraction(13)) == 4 + Fraction(3 * (7 - 4), 10)  # 4 + 3 × (7 − 4) ÷ 10


@pytest.mark.parametrize("arc", [-1, 41])
def test_rsine_refuses_an_arc_outside_the_quadrant(arc: int) -> None:
    with pytest.raises(SuryaRefusal, match="outside the quadrant"):
        TABLE.rsine(arc)


@pytest.mark.parametrize("arc", [0, 3, 10, 13, Fraction(47, 3), 20, 33, 40])
def test_arc_inverts_rsine(arc: Fraction | int) -> None:
    assert TABLE.arc(TABLE.rsine(arc)) == arc


@pytest.mark.parametrize("sine", [-1, 11])
def test_arc_refuses_a_sine_outside_the_radius(sine: int) -> None:
    with pytest.raises(SuryaRefusal, match="outside"):
        TABLE.arc(sine)


def test_signed_rsine_is_negative_in_the_half_orbit_from_libra() -> None:
    # a quadrant of 40′ is a synthetic table: its signed sine takes degrees, so test with
    # the table scaled to a whole quadrant of 90° (step 1350′ = 22.5°)
    t = SineTable(1350, (2, 4, 5, 6))
    assert t.signed_rsine(Fraction(45)) == 4
    assert t.signed_rsine(Fraction(135)) == 4
    assert t.signed_rsine(Fraction(225)) == -4
    assert t.signed_rsine(Fraction(315)) == -4
    assert t.signed_rsine(Fraction(0)) == 0


# --- the epicycle and the equations (ii.38–45) --------------------------------------------


@pytest.mark.parametrize("even, odd", [(32, 31), (31, 32)])
def test_the_corrected_epicycle_runs_from_the_even_to_the_odd_value(even: int, odd: int) -> None:
    e = Epicycles(Fraction(even), Fraction(odd))
    assert corrected_epicycle(e, Fraction(0), 10) == even
    assert corrected_epicycle(e, Fraction(10), 10) == odd
    assert corrected_epicycle(e, Fraction(5), 10) == Fraction(even + odd, 2)


QUARTER = SineTable(1350, (2, 4, 5, 6))  # radius 6, quadrant 90°
EPI = Epicycles(Fraction(360), Fraction(360))  # base-result equals the base-sine


@pytest.mark.parametrize("kendra, sign", [(30, 1), (150, 1), (210, -1), (330, -1)])
def test_the_equation_of_the_apsis_is_additive_in_the_half_orbit_from_aries(
    kendra: int, sign: int
) -> None:
    eq = manda_equation(EPI, Fraction(kendra), QUARTER, CIRCLE).degrees
    assert (eq > 0 if sign > 0 else eq < 0) and eq.denominator


def test_the_equation_of_the_apsis_is_the_arc_of_the_base_result() -> None:
    # kendra 45°: base-sine 4; base-result 4 × 360 ÷ 360 = 4; its arc 45° → 45 × 60′
    eq = manda_equation(EPI, Fraction(45), QUARTER, CIRCLE)
    assert eq.degrees == QUARTER.arc(4) / 60 and eq.hypotenuse is None


def test_the_equation_of_the_conjunction_vanishes_at_the_conjunction() -> None:
    eq = sighra_equation(
        Epicycles(Fraction(36), Fraction(36)), Fraction(0), QUARTER, 360, RESOLUTION
    )
    assert eq.degrees == 0
    assert eq.hypotenuse == QUARTER.radius + QUARTER.radius * Fraction(36, 360)


@pytest.mark.parametrize("kendra, side", [(45, 1), (135, -1), (225, -1), (315, 1)])
def test_the_perpendicular_result_is_added_in_the_half_orbit_from_capricorn(
    kendra: int, side: int
) -> None:
    e = Epicycles(Fraction(36), Fraction(36))
    eq = sighra_equation(e, Fraction(kendra), QUARTER, CIRCLE, RESOLUTION)
    base = perp = QUARTER.rsine(45 * 60) * Fraction(36, 360)
    expected_square = (QUARTER.radius + side * perp) ** 2 + base**2
    assert eq.hypotenuse is not None
    assert eq.hypotenuse**2 <= expected_square < (eq.hypotenuse + RESOLUTION) ** 2
    assert (eq.degrees > 0) is (kendra < 180)


def test_the_mean_is_the_remainder_of_the_revolutions() -> None:
    assert mean_remainder(3, 4, Fraction(2)) == Fraction(1, 2) * 360  # 6/4: 1 and a half
    assert mean_remainder(3, 4, Fraction(4)) == 0
    assert mean_remainder(1, 3, Fraction(1)) == 120


# --- the engine's refusals ----------------------------------------------------------------


def test_the_engine_is_the_surya_engine_on_its_own_meridian() -> None:
    run = build(resolved(), own_place())
    assert isinstance(resolved().model, SuryaModel)
    assert isinstance(run.engine, SuryaEngine)


def test_a_kerala_place_runs_through_the_identification_of_the_prime_meridian() -> None:
    obs = load_place(REPO, "kerala", "kozhikode", records().data)
    run = build(resolved(), obs)
    day = run.engine.day(run.runs_from.plus_days(1_800_000))
    assert (
        "provisional:texts.suryasiddhanta.meridian.identification.suryasiddhanta_burgess_1860"
        in day.flags
    )
    assert day.sunset is not None and day.terms is not None and day.terms.cara_asus != 0
    assert "provisional:texts.suryasiddhanta.procedures.cara.application" in day.flags


def test_a_day_without_a_cara_carries_no_cara_gap() -> None:
    run = build(resolved(), own_place())
    day = run.engine.day(run.runs_from.plus_days(1_800_000))
    assert day.terms is not None and day.terms.cara_asus == 0
    assert not [f for f in day.flags if f.endswith("cara.application")]


@pytest.mark.parametrize("latitude", [90, -90, 91])
def test_a_latitude_that_is_not_a_place_is_refused(latitude: int) -> None:
    moved = dataclasses.replace(own_place(), latitude_degrees=Fraction(latitude))
    with pytest.raises(SuryaRefusal, match="is not a place"):
        build(resolved(), moved)


def test_each_time_correction_is_applied_once() -> None:
    """Ruling (h): deśāntara and cara move the means' time, the bhujāntara the place.

    The means are those of the count's midnight carried at mean motion by
    the deśāntara, the quarter day and the cara together, and by nothing
    else; the true place is the equations on those means plus the
    bhujāntara once; the sunrise instant holds the cara and not the
    bhujāntara (ii.46 corrects the place, not the time).
    """
    obs = dataclasses.replace(
        load_place(REPO, "kerala", "kozhikode", records().data), meridian_offset_ghatis=Fraction(3)
    )
    eng = build(resolved(), obs).engine
    assert isinstance(eng, SuryaEngine)
    m = eng.model
    jdn = eng.runs_from.plus_days(1_800_000)
    day = eng.day(jdn)
    t = day.terms
    assert t is not None and t.cara_days != 0 and t.bhujaphala_minutes != 0
    quarter = Fraction(1, 4)
    assert t.shift_days == -Fraction(3, 60) + quarter + t.cara_days
    assert day.mean == eng._means_at(jdn, t.shift_days)
    count = Fraction(m.days_to_epoch + jdn.days_since(eng.epoch))
    for e in ("sun", "moon", "moon_node"):
        at_midnight = m.elements.mean(e, count)
        assert day.mean[e] == (at_midnight + m.elements.motion(e) * t.shift_days) % 360
    for b, p in m.planets.items():
        once = m.true(p, day.mean) + m.gati(p, day.mean) * m.bhujaphala_minutes(day.mean) / 21600
        assert day.true[b] == once % 360
    assert day.sunrise == Nadika((quarter + t.cara_days) * 60)
    assert day.sunset == day.sunrise + Nadika(30) + Nadika(2 * t.cara_asus / 360)


# --- the versed sines, the daily motion, the cara (ii.47–62, iii.9–10) -------


def test_the_versed_sine_interpolates_by_the_same_rule() -> None:
    assert VTABLE.rversine(10) == 1 and VTABLE.rversine(40) == 10
    assert VTABLE.rversine(15) == 1 + Fraction(5 * (3 - 1), 10)
    with pytest.raises(SuryaRefusal, match="no versed sines"):
        TABLE.rversine(10)
    with pytest.raises(SuryaRefusal, match="at the sines' steps"):
        SineTable(10, (4, 7, 9, 10), (1, 3))


@pytest.mark.parametrize("arc, diff", [(0, 4), (5, 4), (10, 3), (15, 3), (35, 1), (40, 1)])
def test_the_difference_of_tabular_sines_is_that_of_the_step_holding_the_arc(
    arc: int, diff: int
) -> None:
    assert TABLE.difference(arc) == diff


def test_the_equation_of_the_daily_motion_for_the_apsis() -> None:
    e = Epicycles(Fraction(36), Fraction(36))
    k = Fraction(1, 4)  # 15′ of anomaly: the second step, difference 3
    motion = Fraction(100)
    # motion × difference ÷ step × epicycle ÷ circle = 100 × 3 ÷ 10 × 36 ÷ 360 = 3
    assert manda_motion_equation(e, k, TABLE, CIRCLE, motion) == -3  # half from Capricorn
    assert manda_motion_equation(e, 180 + k, TABLE, CIRCLE, motion) == 3  # half from Cancer
    assert manda_motion_equation(e, 180 - k, TABLE, CIRCLE, motion) == 3  # half from Cancer
    assert manda_motion_equation(e, 360 - k, TABLE, CIRCLE, motion) == -3  # half from Capricorn


def test_the_equation_of_the_daily_motion_for_the_conjunction() -> None:
    # (conjunction's motion − motion) × (hypotenuse − radius) ÷ hypotenuse
    assert sighra_motion_equation(Fraction(10), Fraction(4), Fraction(12), 10) == 1
    assert sighra_motion_equation(Fraction(10), Fraction(4), Fraction(8), 10) == Fraction(-3, 2)
    with pytest.raises(SuryaRefusal, match="not positive"):
        sighra_motion_equation(Fraction(10), Fraction(4), Fraction(0), 10)


def test_the_ascensional_difference_from_the_versed_sine_day_radius() -> None:
    # day-radius 10 − vers(arc of 4 = 10′) = 9; earth-sine 4 × 6 ÷ 12 = 2;
    # sine of the cara 2 × 10 ÷ 9 = 20/9, its arc (20/9) × 10 ÷ 4 = 50/9
    c = ascensional_difference_surya(VTABLE, Fraction(4), Fraction(6), 12)
    assert (c.day_radius, c.earthsine, c.cara_asus) == (Fraction(9), Fraction(2), Fraction(50, 9))
    south = ascensional_difference_surya(VTABLE, Fraction(-4), Fraction(6), 12)
    assert south.cara_asus == -Fraction(50, 9)
    with pytest.raises(SuryaRefusal, match="no sunrise"):
        ascensional_difference_surya(VTABLE, Fraction(4), Fraction(60), 12)


def test_the_equinoctial_shadow_from_the_latitude() -> None:
    t = resolved().model.table
    assert isinstance(t, SineTable)
    phi = Fraction(10)
    want = t.rsine(phi * 60) * 12 / t.rsine((90 - phi) * 60)
    assert palabha(t, phi, 12) == want and palabha(t, -phi, 12) == -want
    assert palabha(t, Fraction(0), 12) == 0


def test_the_precession_is_added_in_the_half_from_180_and_subtracted_in_the_other() -> None:
    m = resolved().model
    assert isinstance(m, SuryaModel)
    revs, days = m.ayana_rate

    def at(part: int) -> Fraction:
        return Fraction(days, revs) * Fraction(part, 360)  # the days that give the part

    factor = m.ayana_factor
    assert m.ayana(at(200)) == 20 * factor
    assert m.ayana(at(300)) == 60 * factor
    assert m.ayana(at(100)) == -80 * factor
    assert m.ayana(at(0)) == 0


def test_a_day_before_runs_from_is_refused_naming_it() -> None:
    run = build(resolved(), own_place())
    before = run.runs_from.plus_days(-1)
    with pytest.raises(BeforeRunsFrom, match=f"JDN {before.value} is before runs_from"):
        run.engine.day(before)
    assert run.engine.day(run.runs_from).ahargana.day == 0


def test_a_preset_without_an_observer_is_refused() -> None:
    with pytest.raises(PresetError, match="the caller names the observer"):
        open_preset(REPO, "suryasiddhanta_text", None, records=records())


def test_a_hybrid_sunrise_needs_its_quantum() -> None:
    r = resolved()
    obs = own_place()

    class Provider:
        id = "test"

        def sunrise_fraction(self, jdn: JDN, observer: object) -> Fraction:
            return Fraction(1, 4)

    with pytest.raises(SuryaRefusal, match="hybrid_sunrise_quantum"):
        SuryaEngine(r.model, obs, r.epoch, sunrise_provider=Provider())  # type: ignore[arg-type]


def test_an_unknown_intraday_model_is_refused() -> None:
    r = resolved()
    with pytest.raises(SuryaRefusal, match="intraday model"):
        SuryaEngine(r.model, own_place(), r.epoch, intraday="intraday.unknown")  # type: ignore[arg-type]


def test_an_unknown_body_is_refused_and_a_latitude_away_from_sunrise_not_modelled() -> None:
    eng = build(resolved(), own_place()).engine
    assert isinstance(eng, SuryaEngine)
    jdn = eng.runs_from.plus_days(10)
    at = eng.instant(jdn, Nadika(0))
    with pytest.raises(SuryaRefusal, match="serves no body 'rahu'"):
        eng.sidereal_longitude("rahu", at)
    assert eng.latitude("mars", eng.instant(jdn, Nadika(1))) is NOT_MODELLED
    assert eng.latitude("mars", at) is not NOT_MODELLED
    with pytest.raises(SuryaRefusal, match="instant of"):
        eng.sidereal_longitude("sun", SiddhanticCivilInstant(jdn, Nadika(0), "text_local:other"))


# --- guards from the 1.0.0 release review ---------------------------------


def test_a_sine_table_that_does_not_rise_is_refused() -> None:
    """SineTable(…, (100, 90, 200)) built, and its inverse was no inverse (item 8)."""
    with pytest.raises(SuryaRefusal, match="do not rise"):
        SineTable(10, (4, 3, 9, 10))


def test_a_hypotenuse_truncated_to_nothing_is_refused() -> None:
    """A root truncated to 0 gave an equation of 0 (item 9)."""
    with pytest.raises(SuryaRefusal, match="truncates to 0"):
        sighra_equation(EPI, Fraction(45), QUARTER, CIRCLE, Fraction(1000))


def test_the_latitude_checks_the_instant_s_standard() -> None:
    """longitude refused a foreign standard; latitude served it (item 6)."""
    run = build(resolved(), own_place())
    jdn = run.runs_from.plus_days(1_900_000)
    foreign = SiddhanticCivilInstant(jdn, Nadika(0), "text_local:aryabhatiya")
    with pytest.raises(SuryaRefusal, match="instant of text_local:aryabhatiya"):
        run.engine.latitude("moon", foreign)
