"""Internal redundancies of the modern engine.

- **The nutation toggle** leaves star-fixed sidereal longitudes unchanged:
  on the true equinox both the body's longitude and the ayanāṃśa carry the
  same Δψ, on the mean equinox neither does, so the sidereal longitude is
  the same (``iae_lahiri`` and ``citra_180``); and under ``citra_180`` it is
  the same whichever nutation theory the frame uses.
- **Latitude node ≡ output node**. The modern latitude is the apparent
  ecliptic latitude, which uses no node; what binds the latitude to the
  node is the osculating identity: the Moon's geometric position lies in
  the osculating orbit plane, so its ecliptic latitude β and longitude λ
  satisfy tan β = tan i · sin(λ − Ω) with the Ω that ``node: osculating``
  outputs. Under either node the protocol's ``node`` is the one function
  (:meth:`ModernEngine.node_at`) at the instant's TT.
- **F10**: on every day of the IERS series, the UT1 − UTC a modern-era ΔT
  model implies, TT − UTC − ΔT, stays within the envelope of the observed
  series (the largest |UT1 − UTC| it holds; no bound is typed here). The
  ``iers`` model meets it by construction; ``smh2016`` and ``em2006`` do
  not, and the test pins that documented finding: both models stay as
  published and their mismatch since 1972 is recorded.
- **Pairing**: a longitude and an ayanāṃśa from
  different nutation instances, and a mean value against a true one, are
  refused; ``iae_lahiri``'s mean value is its printed polynomial whatever
  the frame's precession theory.
"""

from __future__ import annotations

import random
from fractions import Fraction
from functools import cache
from typing import Any

import numpy as np
import pytest
from modern_kit import data, default_engine, engine

from jyotirganita.core.types import (
    JDN,
    TT,
    UTC,
    AngleUnit,
    FloatArc,
    MeanOfDate,
    TropicalLongitude,
    TrueOfDate,
    sidereal_from_tropical,
    sidereal_from_tropical_mean,
)
from jyotirganita.data.engine_parameters import seed
from jyotirganita.modern.angles import r1
from jyotirganita.modern.deltat import IersDeltaT, make_model
from jyotirganita.modern.engine import ModernEngine
from jyotirganita.modern.timescales import OutOfRange, TimeScales

DAYS = 6
BODIES = ("sun", "moon", "mars")
#: float rounding of a longitude in degrees (a few units in the last place of 360)
ANGLE_ROUNDING_DEG = 1e-9
#: float rounding of a ratio of order one
RATIO_ROUNDING = 1e-9
#: the models that do not meet F10 on the IERS era
F10_EXCEEDS = {"smh2016", "em2006"}


@cache
def days() -> list[TT]:
    """Seeded instants inside DE440 and the IERS series (1972-2026)."""
    rng = random.Random(seed("seeds.modern_sample"))
    lo, hi = 2441318, 2461290  # JD 1972-01-02 and 2026-09-07, inside the series
    return [TT(rng.randrange(lo, hi), rng.random()) for _ in range(DAYS)]


def _deg(x: FloatArc) -> float:
    return x.to(AngleUnit.DEGREE).value % 360


def _sep(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


@cache
def _pair(ayanamsa: str, aberration: bool | None) -> tuple[ModernEngine, ModernEngine]:
    kw: dict[str, Any] = {"ayanamsa": ayanamsa, "ayanamsa_aberration": aberration}
    return (engine(ayanamsa_equinox="true", **kw), engine(ayanamsa_equinox="mean", **kw))


@pytest.mark.parametrize(("ayanamsa", "aberration"), [("iae_lahiri", None), ("citra_180", False)])
def test_the_nutation_toggle_leaves_sidereal_longitudes_unchanged(
    ayanamsa: str, aberration: bool | None
) -> None:
    true_eng, mean_eng = _pair(ayanamsa, aberration)
    for t in days():
        for body in BODIES:
            a = _deg(true_eng.sidereal_at(body, t).arc)
            b = _deg(mean_eng.sidereal_at(body, t).arc)
            assert _sep(a, b) <= ANGLE_ROUNDING_DEG, (body, t)


def test_citra_180_does_not_depend_on_the_nutation_theory() -> None:
    kw: dict[str, Any] = {
        "ayanamsa": "citra_180",
        "ayanamsa_equinox": "true",
        "ayanamsa_aberration": False,
    }
    a_eng, b_eng = engine(nutation="iau2000a", **kw), engine(nutation="iau1980", **kw)
    for t in days():
        for body in BODIES:
            assert _sep(_deg(a_eng.sidereal_at(body, t).arc),
                        _deg(b_eng.sidereal_at(body, t).arc)) <= ANGLE_ROUNDING_DEG  # fmt: skip


@pytest.mark.parametrize("node", ["mean", "osculating"])
def test_the_protocol_node_is_the_output_node(node: str) -> None:
    eng = engine(node=node)
    for t in days()[:2]:
        instant = eng.civil_of_tt(t, JDN(int(t.jd_whole + t.jd_fraction + Fraction(1, 2))))
        a = eng.node(instant).arc.to(AngleUnit.DEGREE).value
        b = eng.node_at(eng.tt_of_civil(instant)).arc.to(AngleUnit.DEGREE).value
        assert a == b


def test_the_osculating_node_is_the_latitude_node() -> None:
    """tan β = tan i · sin(λ − Ω) for the Moon's geometric place, Ω the output node."""
    eng = engine(node="osculating", ayanamsa_equinox="true")
    for t in days():
        tc = eng.scales.centuries(t)
        nut, m = eng.frame.state(tc)
        rot = r1(eng.precession.mean_obliquity(tc) + nut.deps) @ m
        jd1, jd2 = eng.scales.tdb_parts(t)
        pm, vm = eng.ephemeris.barycentric("MOON", jd1, jd2)
        pe, ve = eng.ephemeris.barycentric("EARTH", jd1, jd2)
        r, v = rot @ (pm - pe), rot @ (vm - ve)
        lam, beta = np.arctan2(r[1], r[0]), np.arcsin(r[2] / np.linalg.norm(r))
        h = np.cross(r, v)
        inc = np.arccos(h[2] / np.linalg.norm(h))
        omega = _deg(eng.node_at(t).arc) + _deg(eng.ayanamsa.at(t, nut).arc)
        lhs = np.tan(beta)
        rhs = np.tan(inc) * np.sin(lam - np.radians(omega))
        assert abs(lhs - rhs) <= RATIO_ROUNDING, t


@pytest.mark.parametrize("model_id", ["iers", "smh2016", "em2006"])
def test_f10_ut1_minus_utc_within_the_observed_envelope(model_id: str) -> None:
    d = data()
    scales = TimeScales(d)
    iers = IersDeltaT(scales)
    envelope = max(abs(Fraction(v)) for _, v in iers.daily_ut1_minus_utc())
    model = make_model(model_id, scales, d)
    off = scales.leap.mjd_offset
    whole = int(off)
    worst = Fraction(0)
    served = 0
    for mjd in range(iers.first_mjd, iers.cutoff_mjd + 1):
        utc = UTC(whole, float(off - whole) + mjd)
        tt = scales.tt_from_utc(utc)
        try:
            dt = model.delta_t(tt)
        except OutOfRange:
            continue
        served += 1
        implied = scales.tt_minus_tai_s + scales.leap.tai_minus_utc(utc) - Fraction(dt)
        worst = max(worst, abs(implied))
    assert served > 0
    exceeds = worst > envelope + Fraction(1, 10**9)
    assert exceeds == (model_id in F10_EXCEEDS), (model_id, float(worst), float(envelope))


def test_a_longitude_and_an_ayanamsa_of_different_nutation_instances_are_refused() -> None:
    a = engine(nutation="iau2000a")
    b = engine(nutation="iau1980")
    t = days()[0]
    trop = a.tropical_at("sun", t)
    nut_b = b.frame.state(b.scales.centuries(t))[0]
    with pytest.raises(TypeError, match="nutation instances differ"):
        sidereal_from_tropical(trop, b.ayanamsa.at(t, nut_b))


def test_a_mean_and_a_true_value_are_never_paired() -> None:
    eng = default_engine()
    t = days()[0]
    nut = eng.frame.state(eng.scales.centuries(t))[0]
    true_aya = eng.ayanamsa.at(t, nut)
    mean_eng = engine(ayanamsa_equinox="mean")
    mean_aya = mean_eng.ayanamsa.at(t, None)
    arc = FloatArc(float(1), AngleUnit.DEGREE)
    with pytest.raises(TypeError):
        sidereal_from_tropical(TropicalLongitude(arc, TrueOfDate, nut.identity), mean_aya)
    with pytest.raises(TypeError):
        sidereal_from_tropical_mean(TropicalLongitude(arc, MeanOfDate, None), true_aya)
    citra = engine(ayanamsa="citra_180", ayanamsa_aberration=False)
    other = engine(nutation="iau1980").frame.state(eng.scales.centuries(t))[0]
    with pytest.raises(ValueError, match="own nutation"):
        citra.ayanamsa.at(t, other)


def test_the_iae_mean_value_is_its_polynomial_whatever_the_frame() -> None:
    kw: dict[str, Any] = {"ayanamsa_equinox": "mean"}
    for t in days():
        a = engine(precession="iau2006", **kw).ayanamsa.at(t, None).arc
        b = engine(precession="vondrak2011", **kw).ayanamsa.at(t, None).arc
        assert a.to(AngleUnit.DEGREE).value == b.to(AngleUnit.DEGREE).value
