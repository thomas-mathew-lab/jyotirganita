"""Run-time behaviour of core/types.py: mixing is a TypeError, not a result.

mypy rejects the same mixes statically (test_mypy_mixing.py); these tests
cover code that reaches the types without static checking.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import pytest

from jyotirganita.core import types as t
from jyotirganita.core.types import AngleUnit

DEG = AngleUnit.DEGREE
NUT = t.NutationIdentity("iau2000b", "a")
NUT_OTHER = t.NutationIdentity("iau2000b", "b")


def _any(x: object) -> Any:
    """Hide a value's type from mypy so that the run-time check is exercised."""
    return x


def test_exact_arc_arithmetic_is_exact() -> None:
    a = t.ExactArc(Fraction(1, 3), DEG)
    assert (a + a).value == Fraction(2, 3)
    assert (a * Fraction(3, 2)).value == Fraction(1, 2)
    assert (2 * a).value == Fraction(2, 3)
    assert (a / 2).value == Fraction(1, 6)
    assert a.to(AngleUnit.REVOLUTION).value == Fraction(1, 1080)
    assert t.ExactArc(Fraction(1, 2), AngleUnit.REVOLUTION).to(DEG).value == 180


@pytest.mark.parametrize("bad", [0.5, True, "1"])
def test_exact_arc_refuses_non_exact_scalars(bad: object) -> None:
    a = t.ExactArc(1, DEG)
    with pytest.raises(TypeError):
        a * _any(bad)
    with pytest.raises(TypeError):
        t.ExactArc(_any(bad), DEG)


def test_float_arc_refuses_fraction() -> None:
    with pytest.raises(TypeError):
        t.FloatArc(1.0, DEG) * _any(Fraction(1, 2))
    with pytest.raises(TypeError):
        t.FloatArc(_any(Fraction(1, 2)), DEG)


def test_families_do_not_mix_at_run_time() -> None:
    e, f = t.ExactArc(1, DEG), t.FloatArc(1.0, DEG)
    with pytest.raises(TypeError):
        e + _any(f)
    with pytest.raises(TypeError):
        f + _any(e)
    with pytest.raises(TypeError):
        _ = e < _any(f)
    assert e != _any(f)


def test_units_do_not_mix_silently() -> None:
    with pytest.raises(TypeError):
        t.ExactArc(1, DEG) + t.ExactArc(1, AngleUnit.REVOLUTION)


def test_longitudes_normalise() -> None:
    lon = t.SiderealLongitude(t.ExactArc(370, DEG), "text:test")
    assert lon.arc.value == 10
    neg = t.SiderealLongitude(t.ExactArc(-10, DEG), "text:test")
    assert neg.arc.value == 350
    assert (lon - neg).value == -340


def test_sidereal_frames_do_not_mix() -> None:
    a = t.SiderealLongitude(t.ExactArc(1, DEG), "text:one")
    b = t.SiderealLongitude(t.ExactArc(1, DEG), "text:two")
    with pytest.raises(TypeError):
        a - b
    with pytest.raises(TypeError):
        t.SiderealLongitude(t.ExactArc(1, DEG), "no-kind")


def test_kinds_and_nutation_identities() -> None:
    with pytest.raises(TypeError):
        t.TropicalLongitude(t.FloatArc(1.0, DEG), t.TrueOfDate, None)
    with pytest.raises(TypeError):
        t.TropicalLongitude(t.FloatArc(1.0, DEG), t.MeanOfDate, NUT)
    with pytest.raises(TypeError):
        t.TropicalLongitude(t.FloatArc(1.0, DEG), _any(int), None)
    with pytest.raises(TypeError):
        t.MeanOfDate()


def test_sidereal_from_tropical() -> None:
    lon = t.TropicalLongitude(t.FloatArc(30.0, DEG), t.TrueOfDate, NUT)
    ay = t.Ayanamsa(t.FloatArc(24.0, DEG), t.TrueOfDate, NUT, "test")
    sid = t.sidereal_from_tropical(lon, ay)
    assert sid.arc.value == 6.0 and sid.frame == "ayanamsa:test"


def test_sidereal_from_tropical_refuses_mixed_nutation_instances() -> None:
    lon = t.TropicalLongitude(t.FloatArc(30.0, DEG), t.TrueOfDate, NUT)
    ay = t.Ayanamsa(t.FloatArc(24.0, DEG), t.TrueOfDate, NUT_OTHER, "test")
    with pytest.raises(TypeError):
        t.sidereal_from_tropical(lon, ay)


def test_sidereal_from_tropical_refuses_mean_at_run_time() -> None:
    lon = t.TropicalLongitude(t.FloatArc(30.0, DEG), t.TrueOfDate, NUT)
    mean = t.Ayanamsa(t.FloatArc(24.0, DEG), t.MeanOfDate, None, "test")
    with pytest.raises(TypeError):
        t.sidereal_from_tropical(lon, _any(mean))


def test_durations() -> None:
    n = t.Nadika(Fraction(15))
    assert t.days_from_nadika(n) == t.Days(Fraction(1, 4))
    assert t.nadika_from_days(t.Days(1)) == t.Nadika(60)
    assert t.vinadika_from_nadika(t.Nadika(1)) == t.Vinadika(60)
    assert t.nadika_from_vinadika(t.Vinadika(30)) == t.Nadika(Fraction(1, 2))
    with pytest.raises(TypeError):
        n + _any(t.Days(1))
    with pytest.raises(TypeError):
        t.days_from_nadika(_any(t.Vinadika(1)))


def test_time_scales_do_not_mix() -> None:
    a, b = t.TT(2451545, 0.25), t.UT1(2451545, 0.25)
    with pytest.raises(TypeError):
        a - _any(b)
    later = a + t.FloatDays(1.0)
    assert (later - a) == t.FloatDays(1.0)
    assert t.TT(2451545, 1.5) == t.TT(2451546, 0.5)


def test_ahargana() -> None:
    a = t.Ahargana("one", 10, Fraction(3, 4))
    b = a.plus(t.Days(Fraction(1, 2)))
    assert (b.day, b.fraction) == (11, Fraction(1, 4))
    assert b.minus(a) == t.Days(Fraction(1, 2))
    with pytest.raises(TypeError):
        b.minus(t.Ahargana("two", 10, Fraction(0)))
    with pytest.raises(ValueError):
        t.Ahargana("one", 1, Fraction(1))


def test_dates_are_tagged_and_distinct() -> None:
    j, g = t.JulianDate(1000, 3, 15), t.GregorianDate(1000, 3, 15)
    assert j != _any(g)
    with pytest.raises(ValueError):
        t.JulianDate(1000, 13, 1)
    with pytest.raises(TypeError):
        t.GregorianDate(_any(1000.0), 1, 1)
    assert t.JDN(10).plus_days(5).days_since(t.JDN(10)) == 5


def test_civil_instants() -> None:
    s = t.SiddhanticCivilInstant(t.JDN(1), t.Nadika(5), "text_local:aryabhatiya")
    assert s.standard == "text_local:aryabhatiya"
    with pytest.raises(ValueError):
        t.SiddhanticCivilInstant(t.JDN(1), t.Nadika(5), "IST")
    with pytest.raises(TypeError):
        t.SiddhanticCivilInstant(t.JDN(1), _any(t.Days(5)), "text_local:x")
    m = t.ModernCivilInstant(t.JDN(1), 0.5, "IST")
    assert m.local_fraction == 0.5
    with pytest.raises(ValueError):
        t.ModernCivilInstant(t.JDN(1), 1.0, "IST")


def test_greenwich_mean_time_before_utc_is_ut1_both_ways() -> None:
    """ut1_from_gmt and its inverse gmt_from_ut1 carry the two parts unchanged; neither casts."""
    g = t.UTC(2415021, 0.25)
    u = t.ut1_from_gmt(g)
    assert isinstance(u, t.UT1) and (u.jd_whole, u.jd_fraction) == (2415021, 0.25)
    back = t.gmt_from_ut1(u)
    assert isinstance(back, t.UTC) and back == g
    with pytest.raises(TypeError):
        t.gmt_from_ut1(_any(g))
    with pytest.raises(TypeError):
        t.ut1_from_gmt(_any(u))


def test_jd_at_midnight_opens_the_day_whose_noon_is_the_jdn() -> None:
    # the midnight is the instant text-local midnight is placed at on Greenwich's meridian
    # (ut1_from_text_local, no sunrise offset, no nāḍikās), and the next day's is a day later
    day = t.JDN(2434972)
    at_greenwich = t.ut1_from_text_local(
        t.SiddhanticCivilInstant(day, t.Nadika(0), "text_local:x"), t.Nadika(0), Fraction(0)
    )
    assert Fraction(at_greenwich.jd_whole) + Fraction(at_greenwich.jd_fraction) == (
        t.jd_at_midnight(day)
    )
    assert t.jd_at_midnight(day.plus_days(1)) - t.jd_at_midnight(day) == 1
    assert t.jd_at_midnight(day) < day.value < t.jd_at_midnight(day.plus_days(1))
    with pytest.raises(TypeError):
        t.jd_at_midnight(_any(day.value))
