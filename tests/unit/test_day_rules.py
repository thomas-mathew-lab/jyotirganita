"""The day rules' mechanics: elements, sunrise and endings.

Planted values only: these tests check the arithmetic and the refusals;
the printed examples are in ``tests/authority/test_aryabhatiya_sunrise.py``.
"""

from __future__ import annotations

from fractions import Fraction as F

import pytest

from jyotirganita.calendar import elements as el
from jyotirganita.core.types import AngleUnit, ExactArc, Nadika
from jyotirganita.methods.compose import REPO, load_method
from jyotirganita.siddhantic.endings import (
    SeamRefusal,
    chord,
    proportional_parts,
    root_bisection,
    seam,
    sunrise_difference,
    truncate_at_asu,
)
from jyotirganita.siddhantic.sunrise import (
    TimeUnits,
    ascensional_difference,
    day_radius,
    earthsine,
    half_day,
    rsine_declination,
    signed_rsine,
    sunrise_after_midnight,
)
from jyotirganita.siddhantic.tables import RsineTable

UNITS = TimeUnits(60, 360)  # planted: 60 nāḍīs, 360 asus to the nāḍī


def deg(x: F | int) -> ExactArc:
    return ExactArc(F(x), AngleUnit.DEGREE)


# --- elements ---------------------------------------------------------------------------


def test_element_arcs_indices_and_remainders() -> None:
    sun, moon = deg(350), deg(20)  # Δ = 30°, sum = 10°
    assert el.arc(el.TITHI, sun, moon).value == 30
    assert el.index(el.TITHI, sun, moon) == 3  # 30° opens the third tithi
    assert el.remaining(el.TITHI, sun, moon).value == 6
    assert el.index(el.KARANA, sun, moon) == 6
    assert el.index(el.NAKSATRA, sun, moon) == 2  # 20° of 13°20′ spans
    assert el.remaining(el.NAKSATRA, sun, moon).value == F(20, 3)
    assert el.index(el.YOGA, sun, moon) == 1
    assert el.index(el.RASI, sun, moon) == 12
    assert el.span(el.NAKSATRA, sun).value == F(40, 3)


def test_element_motions() -> None:
    s, m = deg(1), deg(13)
    assert [el.motion(e, s, m).value for e in (el.TITHI, el.NAKSATRA, el.YOGA, el.RASI)] == [
        12,
        13,
        14,
        1,
    ]


# --- sunrise ----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def table() -> RsineTable:
    return load_method("aryabhatiya", REPO).text_model.table


def test_declination_is_north_in_the_half_orbit_from_aries(table: RsineTable) -> None:
    eps = table.rsine(24 * 60)
    assert rsine_declination(table, eps, F(90)) == eps
    assert rsine_declination(table, eps, F(270)) == -eps
    assert rsine_declination(table, eps, F(0)) == 0
    assert rsine_declination(table, eps, F(150)) == rsine_declination(table, eps, F(30))
    assert rsine_declination(table, eps, F(210)) == -rsine_declination(table, eps, F(30))
    assert signed_rsine(table, F(-30)) == -table.rsine(30 * 60)


def test_the_cara_vanishes_at_the_equator_and_changes_sign_with_the_sun(table: RsineTable) -> None:
    eps = table.rsine(24 * 60)
    d = day_radius(table, eps, F(1, 3600))
    assert d * d <= table.radius**2 - eps * eps < (d + F(1, 3600)) ** 2
    north = earthsine(table.rsine(10 * 60), table.rsine(80 * 60), eps)
    assert earthsine(F(0), F(table.radius), eps) == 0
    c = ascensional_difference(table, north, d)
    assert c > 0 and ascensional_difference(table, -north, d) == -c
    with pytest.raises(ValueError, match="colatitude must be positive"):
        earthsine(F(table.radius), F(0), eps)
    with pytest.raises(ValueError, match="day-radius must be positive"):
        ascensional_difference(table, north, F(0))
    with pytest.raises(ValueError, match="no sunrise"):
        ascensional_difference(table, F(table.radius), F(1))


def test_sunrise_and_sunset_from_the_carries() -> None:
    t = sunrise_after_midnight(F(0), F(0), UNITS)
    assert (t.sunrise.value, t.sunset.value) == (F(15), F(45))
    # +216′ of bhujāphala delays sunrise 216/21600 day; a cara of 360 asus, a nāḍī earlier
    t = sunrise_after_midnight(F(216), F(360), UNITS)
    assert t.bhujantara_days == F(1, 100) and t.cara_days == -F(1, 60)
    assert t.sunrise.value == 15 + F(60, 100) - 1
    assert t.sunset.value - t.sunrise.value == 2 * half_day(F(360), UNITS).value == 32


# --- endings ----------------------------------------------------------------------------


def test_the_gati_is_reduced_into_the_half_circle() -> None:
    assert sunrise_difference(F(359), F(12)) == 13
    assert sunrise_difference(F(10), F(9)) == -1
    assert sunrise_difference(F(0), F(180)) == 180


def test_proportional_parts_and_their_refusal() -> None:
    assert proportional_parts(F(6), F(12), 60).value == 30
    with pytest.raises(ValueError, match="no ending by proportional parts"):
        proportional_parts(F(6), F(0), 60)


def test_the_chord_and_the_sliver() -> None:
    assert chord(F(350), F(20), Nadika(F(30)), 60) == 0
    assert chord(F(10), F(12), Nadika(F(0)), 60) == 10
    for n in (F(60), F(-1, 10)):
        with pytest.raises(SeamRefusal, match="outside the day's chord"):
            chord(F(10), F(12), Nadika(n), 60)
    assert seam(4, 5) and not seam(5, 5)


def test_an_ending_truncated_at_the_asu() -> None:
    # 12 ghaṭīs 34 vighaṭīs and 5.9 asus of 6 to the vighaṭī → [12, 34, 5]
    n = Nadika(12 + F(34, 60) + F(59, 10) / 360)
    assert truncate_at_asu(n, 60, 6) == [12, 34, 5]
    assert truncate_at_asu(Nadika(F(0)), 60, 6) == [0, 0, 0]
    with pytest.raises(ValueError, match="not negative"):
        truncate_at_asu(Nadika(F(-1)), 60, 6)


def test_root_bisection_is_never_before_the_crossing() -> None:
    root = F(37, 3)
    r = root_bisection(lambda x: x >= root, F(0), F(120), F(1, 3600))
    assert root <= r <= root + F(1, 3600)
    with pytest.raises(ValueError, match="crossed\\(lo\\) false"):
        root_bisection(lambda x: True, F(0), F(1), F(1, 10))
    with pytest.raises(ValueError, match="lo < hi"):
        root_bisection(lambda x: x > 0, F(1), F(1), F(1, 10))
