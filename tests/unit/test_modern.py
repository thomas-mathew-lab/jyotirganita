"""Unit tests of the modern engine: refusals, the root finder, eclipses.

**Refusals**: a date past
the IERS cut-off; a date outside a model's stated range (ΔT, precession,
kernel); a search window across a model's boundary; a kernel without a
registry entry, of the wrong size or with the wrong hash; a preset
without an observer; a time standard outside its dates of force. Each
refusal names what refused.

**The root finder** (``modern/roots.py``): sign changes of a function
with known zeros are found to the tolerance, on the absolute grid (the
same instants whatever the window's start), and a bracket that does not
close is an error. **Golden-section search** (``modern/eclipses.py``) the
same for a minimum.

**Eclipses** (``modern/eclipses.py``; provisional, no published canon
compared yet): over the oppositions and conjunctions of a span of years, every
eclipse found is self-consistent (contacts nested and ordered around the
greatest instant, each contact a root of its defining condition,
magnitudes and contact sets agreeing, the provisional flag on every
result). No eclipse date or magnitude is typed here.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from functools import cache
from itertools import pairwise
from math import pi, sin

import pytest
from modern_kit import (
    REPO,
    data,
    default_engine,
    engine,
    ephemeris,
    parameters,
    records,
    time_standards,
)

from jyotirganita.core.calendar import jdn_from_gregorian
from jyotirganita.core.types import TT, FloatDays, GregorianDate, ModernCivilInstant
from jyotirganita.data.time_standards import OutOfForce
from jyotirganita.methods.presets import PresetError, open_modern_preset
from jyotirganita.modern.deltat import make_model
from jyotirganita.modern.eclipses import ECLIPSE_FLAG, LunarEclipse, golden_minimum, window
from jyotirganita.modern.engine import ModernEngine
from jyotirganita.modern.kernels import Ephemeris, KernelError, load_registry
from jyotirganita.modern.precession import make_precession
from jyotirganita.modern.roots import RootError, RootFinder
from jyotirganita.modern.timescales import OutOfRange, TimeScales

#: a test-only grid of one day for finding syzygies (the engine's grids are engine parameters)
SYZYGY_STEP = 1.0
#: a period and phase for the root finder's test function (test-only numbers, exact zeros)
PERIOD, PHASE = 0.37, 0.11


def _tt(date: GregorianDate) -> TT:
    return TT(jdn_from_gregorian(date).value, 0.0)


# --- refusals ------------------------------------------------------------------------------


def test_a_date_past_the_iers_cutoff_is_refused_naming_it() -> None:
    eng = default_engine()
    _, hi = eng.delta_t.range_tt()
    assert hi is not None
    with pytest.raises(OutOfRange, match="cut-off"):
        eng.check(hi + FloatDays(1))
    with pytest.raises(OutOfRange, match="cut-off"):
        eng.ut1_of(hi + FloatDays(1))
    eng.check(hi + FloatDays(-1))


def test_a_date_outside_a_model_s_range_is_refused_naming_the_model() -> None:
    d = data()
    scales = TimeScales(d)
    smh = make_model("smh2016", scales, d)
    _, hi = smh.range_tt()
    assert hi is not None
    with pytest.raises(OutOfRange, match="smh2016"):
        smh.delta_t(hi + FloatDays(1))
    em = make_model("em2006", scales, d)
    lo, _ = em.range_tt()
    assert lo is not None
    with pytest.raises(OutOfRange, match="em2006"):
        em.delta_t(lo + FloatDays(-1))
    vondrak = make_precession("vondrak2011", d, scales)
    _, top = vondrak.range_tt()
    assert top is not None
    with pytest.raises(OutOfRange, match="vondrak2011"):
        vondrak.check(top + FloatDays(1))
    eng = default_engine()
    span_from = eng.ephemeris.entry.span_from_jd
    assert span_from is not None
    with pytest.raises(OutOfRange, match="kernel de440"):
        eng.check(TT(int(span_from) - 1, 0.0))


def test_a_search_window_across_a_model_boundary_is_refused() -> None:
    eng = default_engine()
    _, hi = eng.delta_t.range_tt()
    assert hi is not None
    start, end = window(hi, 1.0)
    with pytest.raises(OutOfRange, match="cut-off"):
        eng.eclipses().lunar(start, end)
    with pytest.raises(OutOfRange, match="cut-off"):
        eng.eclipses().solar(start, end)
    run = open_modern_preset(REPO, "modern_iers", "kerala/kozhikode", records=records())[1]
    with pytest.raises(OutOfRange, match="ΔT model iers"):
        run.source.day(run.runs_to.plus_days(1))


def test_a_kernel_without_an_entry_or_with_a_wrong_size_or_hash_is_refused() -> None:
    with pytest.raises(KernelError, match="no entry"):
        Ephemeris.open("de999")
    reg = load_registry()
    good = reg["de440"]
    assert good.bytes is not None and good.sha256 is not None
    wrong_size = {"de440": dataclasses.replace(good, bytes=good.bytes + 1)}
    with pytest.raises(KernelError, match="bytes"):
        Ephemeris.open("de440", registry=wrong_size)
    wrong_hash = {"de440": dataclasses.replace(good, sha256="0" * len(good.sha256))}
    with pytest.raises(KernelError, match="differs"):
        Ephemeris.open("de440", registry=wrong_hash)
    unrecorded = {"de440": dataclasses.replace(good, sha256=None)}
    with pytest.raises(KernelError, match="no hash"):
        Ephemeris.open("de440", registry=unrecorded)


def test_a_preset_without_an_observer_is_refused() -> None:
    with pytest.raises(PresetError, match="names the observer"):
        open_modern_preset(REPO, "modern_iers", None, records=records())


def test_a_time_standard_outside_its_dates_of_force_is_refused() -> None:
    eng = engine("modern_smh", time_standard="ist")
    day = jdn_from_gregorian(GregorianDate(1900, 1, 1))
    with pytest.raises(OutOfForce, match="ist"):
        eng.tt_of_civil(ModernCivilInstant(day, 0.0, "ist"))


def test_an_engine_on_another_kernel_than_its_configuration_is_refused() -> None:
    cfg = default_engine().config
    with pytest.raises(KernelError, match="not de441"):
        ModernEngine(
            dataclasses.replace(cfg, kernel="de441"),
            default_engine().observer,
            data=data(),
            time_standards=time_standards(),
            parameters=parameters(),
            ephemeris=ephemeris("de440"),
        )


# --- the root finder -----------------------------------------------------------------------


def _finder(step: float = 0.05) -> RootFinder:
    r = default_engine().element_roots
    return RootFinder(step, r.tolerance, r.cap)


def _sine(t: TT) -> float:
    x = (t.jd_whole - 2451545) + t.jd_fraction
    return sin(2 * pi * (x - PHASE) / PERIOD)


def test_crossings_are_found_to_the_tolerance_with_their_directions() -> None:
    f = _finder()
    start = TT(2451545, 0.0)
    found = f.crossings(_sine, start, TT(2451547, 0.0))
    zeros = [PHASE + k * PERIOD / 2 for k in range(-1, 12)]
    zeros = [z for z in zeros if 0 <= z < 2]
    assert len(found) == len(zeros)
    for (t, sign), z in zip(found, zeros, strict=True):
        x = (t.jd_whole - 2451545) + t.jd_fraction
        assert abs(x - z) <= f.tolerance
        assert sign == (1 if round((z - PHASE) / (PERIOD / 2)) % 2 == 0 else -1)


def test_crossings_lie_on_the_absolute_grid_whatever_the_window_start() -> None:
    f = _finder()
    a = f.crossings(_sine, TT(2451545, 0.0), TT(2451547, 0.0))
    b = f.crossings(_sine, TT(2451545, 0.013), TT(2451547, 0.0))
    common = [t for t, _ in a if TT(2451545, 0.013) < t]
    assert common == [t for t, _ in b][-len(common) :]


def test_a_bracket_that_does_not_close_is_an_error() -> None:
    r = default_engine().element_roots
    tight = RootFinder(0.05, r.tolerance, 1)
    with pytest.raises(RootError, match="did not close"):
        tight.crossings(_sine, TT(2451545, 0.0), TT(2451546, 0.0))
    with pytest.raises(RootError, match="no crossing"):
        _finder().crossing_after(lambda t: -1.0, TT(2451545, 0.0), 0.5, 1.0)
    with pytest.raises(ValueError, match="ends after it starts"):
        _finder().crossings(_sine, TT(2451546, 0.0), TT(2451545, 0.0))


def test_golden_section_finds_a_minimum_and_refuses_an_open_bracket() -> None:
    r = default_engine().element_roots
    centre = TT(2451545, 0.3)

    def bowl(t: TT) -> float:
        x = (t.jd_whole - centre.jd_whole) + (t.jd_fraction - centre.jd_fraction)
        return x * x

    got = golden_minimum(bowl, TT(2451545, 0.0), TT(2451546, 0.0), r.tolerance, r.cap)
    assert abs((got.jd_whole - centre.jd_whole) + got.jd_fraction - centre.jd_fraction) <= (
        r.tolerance
    )
    with pytest.raises(RootError, match="golden"):
        golden_minimum(bowl, TT(2451545, 0.0), TT(2451546, 0.0), r.tolerance, 1)


# --- eclipses ------------------------------------------------------------------------------


def _syzygies(eng: ModernEngine, start: TT, end: TT, target: float) -> list[TT]:
    """The instants the Moon − Sun elongation reaches ``target`` degrees, rising."""

    def g(t: TT) -> float:
        moon = eng.place("moon", t).direction
        sun = eng.place("sun", t).direction
        lm, _, _ = eng.frame.true_ecliptic(moon, eng.scales.centuries(t))
        ls, _, _ = eng.frame.true_ecliptic(sun, eng.scales.centuries(t))
        x = (lm - ls) * 180 / pi - target
        return (x + 180) % 360 - 180

    finder = RootFinder(SYZYGY_STEP, eng.element_roots.tolerance, eng.element_roots.cap)
    return [t for t, sign in finder.crossings(g, start, end) if sign > 0]


@cache
def lunar_eclipses() -> list[LunarEclipse]:
    eng = default_engine()
    ecl = eng.eclipses()
    out = []
    for t in _syzygies(eng, _tt(GregorianDate(2019, 1, 1)), _tt(GregorianDate(2021, 1, 1)), 180):
        found = ecl.lunar(*window(t, 0.5))
        if found is not None:
            out.append(found)
    return out


def _lunar_condition(eng: ModernEngine, which: str) -> Callable[[TT], float]:
    ecl = eng.eclipses()
    col, sign = {"penumbral": (3, 1), "partial": (2, 1), "total": (2, -1)}[which]

    def f(t: TT) -> float:
        st = ecl._lunar_state(t)
        return st[0] - (st[col] + sign * st[1])

    return f


def test_lunar_eclipses_are_self_consistent() -> None:
    eng = default_engine()
    found = lunar_eclipses()
    assert found, "no lunar eclipse over two years of oppositions: the search is broken"
    minute = 1 / 1440
    for e in found:
        assert e.flags == (ECLIPSE_FLAG,)
        assert e.penumbral is not None and e.penumbral_magnitude > 0
        assert (e.partial is not None) == (e.umbral_magnitude > 0)
        assert (e.total is not None) == (e.umbral_magnitude > 1)
        spans = [s for s in (e.penumbral, e.partial, e.total) if s is not None]
        for outer, inner in pairwise(spans):
            assert outer[0] < inner[0] and inner[1] < outer[1]
        for (a, b), which in zip(spans, ("penumbral", "partial", "total"), strict=False):
            assert a < e.greatest < b
            f = _lunar_condition(eng, which)
            assert f(a + FloatDays(-minute)) > 0 > f(a + FloatDays(minute))
            assert f(b + FloatDays(-minute)) < 0 < f(b + FloatDays(minute))


def test_local_solar_eclipses_are_self_consistent() -> None:
    eng = default_engine()
    ecl = eng.eclipses()
    found = []
    for t in _syzygies(eng, _tt(GregorianDate(2010, 1, 1)), _tt(GregorianDate(2020, 1, 1)), 0):
        e = ecl.solar(*window(t, 0.5))
        if e is not None:
            found.append(e)
    assert found, "no solar eclipse at the observer over ten years: the search is broken"
    for e in found:
        assert e.flags == (ECLIPSE_FLAG,)
        assert e.outer[0] < e.greatest < e.outer[1]
        assert e.magnitude > 0
        assert (e.inner is not None) == (e.kind in ("total", "annular"))
        if e.inner is not None:
            assert e.outer[0] < e.inner[0] < e.greatest < e.inner[1] < e.outer[1]
