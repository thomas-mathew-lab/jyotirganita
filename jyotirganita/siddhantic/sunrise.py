"""The scheme-native sunrise of an Āryabhaṭan text.

Every rule is a registered procedure (:mod:`jyotirganita.siddhantic.procedures`)
whose datum in ``data/texts/<text>/procedures.yaml`` states it. Rsines are
in minutes of arc (the table's units), longitudes in degrees, the
ascensional difference in asus (prāṇas): the minutes of arc of its arc
(laghubhaskariya_1963 II.19–20), 21600 to a day (the time units of the text's data:
nāḍīs per day × vināḍīs per nāḍī × prāṇas per vināḍī).

- ``declination.rsine_obliquity`` (laghubhaskariya_1963 II.16; mahabhaskariya_1960 III.6–7 the
  second
  witness): Rsin δ = Rsin ε × Rsin(bhujā of λ) ÷ R, the Rsine of the
  greatest declination being the table's Rsine of the text's obliquity
  (the text prints it as 1397); north while λ lies in the half-orbit
  from Aries (:func:`rsine_declination`).
- ``declination_argument.svaniraksa_true_longitude`` (mahabhaskariya_1960 IV.25): λ is the Sun's
  longitude corrected
  for the deśāntara, the
  bāhuphala and the bhujāntara, the text's own sidereal longitude with no
  ayana correction (the engine, :mod:`jyotirganita.siddhantic.engine`).
- ``ascensional_difference.earthsine`` (laghubhaskariya_1963 II.17–18; mahabhaskariya_1960 III.6–7):
  the
  day-radius is the root of R² − Rsin²δ (:func:`day_radius`, truncated at
  the engine parameter ``siddhantic.day_radius_root_resolution``: the
  text states no precision for the root); the earthsine is
  Rsin φ × Rsin δ ÷ Rcos φ (:func:`earthsine`; with the equinoctial
  shadow and the gnomon in place of Rsin φ and Rcos φ, laghubhaskariya_1963 III.2–3 makes
  them proportional); the Rsine of the ascensional difference is the
  earthsine × R ÷ the day-radius, reduced to arc by the table
  (:func:`ascensional_difference`). Signed: positive when the day is
  longer than the night (the Sun north of the equator, the place north).
- ``half_day.quarter_day_plus_cara`` (mahabhaskariya_1960 IV.28; laghubhaskariya_1963 II.21 the
  second
  witness): half the day is a quarter of the day and night increased by
  the ascensional difference (:func:`half_day`).
- ``sunrise.mean_meridian_plus_carry`` (laghubhaskariya_1963 II.4(ii) with its note,
  II.19–20): the text's mean sunrise is 15 nāḍikās after
  local mean midnight; the bhujāntara moves it by the Sun's
  bhujāphala ÷ 21600 of a day (later when the bhujāphala is additive),
  the cara by the ascensional difference ÷ 21600 of a day (earlier when
  the day is the longer) (:func:`sunrise_after_midnight`). The sunset is
  the sunrise plus the day (:func:`sunset_after_midnight`).

All arithmetic is exact except the day-radius's root, which is the exact
root truncated at its resolution (as the śīghrakarṇa's).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Protocol

from jyotirganita.core.types import Nadika
from jyotirganita.siddhantic.epicycle import bhuja_koti, karna
from jyotirganita.siddhantic.tables import RsineTable

__all__ = [
    "NoSunrise",
    "Sines",
    "SunriseTimes",
    "TimeUnits",
    "ascensional_difference",
    "day_radius",
    "earthsine",
    "half_day",
    "mean_sunrise",
    "rsine_declination",
    "signed_rsine",
    "sunrise_after_midnight",
    "sunset_after_midnight",
]

MINUTES_PER_DEGREE = 60
DEGREES_PER_HALF_ORBIT = 180
DEGREES_PER_REVOLUTION = 360
QUARTERS_PER_DAY = 4


@dataclass(frozen=True, slots=True)
class TimeUnits:
    """The text's time units: nāḍīs in a day, asus (prāṇas) in a nāḍī."""

    nadis_per_day: int
    asus_per_nadi: int

    @property
    def asus_per_day(self) -> int:
        """Asus in a day and night (21600 for the Āryabhaṭan texts)."""
        return self.nadis_per_day * self.asus_per_nadi


def signed_rsine(table: RsineTable, degrees: Fraction) -> Fraction:
    """The Rsine of an arc of −90° to 90°, with its sign."""
    s = table.rsine(abs(degrees) * MINUTES_PER_DEGREE)
    return -s if degrees < 0 else s


class Sines(Protocol):
    """A table that gives the Rsine of an arc in minutes and states its radius."""

    @property
    def radius(self) -> int: ...

    def rsine(self, arc: Fraction | int) -> Fraction: ...


def rsine_declination(table: Sines, rsin_obliquity: Fraction, longitude: Fraction) -> Fraction:
    """The signed Rsine of the Sun's declination at ``longitude`` degrees (laghubhaskariya_1963
    II.16).

    The Sūrya-siddhānta's ii.28 states the same rule (its sine table,
    :class:`jyotirganita.siddhantic.surya.SineTable`).
    """
    _, _, bhuja, _ = bhuja_koti(longitude)
    s = rsin_obliquity * table.rsine(bhuja * MINUTES_PER_DEGREE) / table.radius
    return s if longitude % DEGREES_PER_REVOLUTION < DEGREES_PER_HALF_ORBIT else -s


def day_radius(table: RsineTable, rsin_declination: Fraction, resolution: Fraction) -> Fraction:
    """The day-radius: the root of R² − Rsin²δ, truncated at ``resolution`` (laghubhaskariya_1963
    II.17)."""
    r = table.radius
    return karna(r * r - rsin_declination * rsin_declination, resolution)


def earthsine(
    rsin_latitude: Fraction, rcos_latitude: Fraction, rsin_declination: Fraction
) -> Fraction:
    """The earthsine: Rsin φ × Rsin δ ÷ Rcos φ (laghubhaskariya_1963 II.18).

    The equinoctial midday shadow and the gnomon may stand for Rsin φ and
    Rcos φ: laghubhaskariya_1963 III.2–3 makes the two pairs proportional.
    """
    if rcos_latitude <= 0:
        raise ValueError("the Rsine of the colatitude must be positive (a place off the poles)")
    return rsin_latitude * rsin_declination / rcos_latitude


class NoSunrise(ValueError):
    """The day's Sun does not rise at the place: the ascensional difference exceeds the radius."""


def ascensional_difference(
    table: RsineTable, earthsine_value: Fraction, day_radius_value: Fraction
) -> Fraction:
    """The signed ascensional difference in asus: arc of earthsine × R ÷ day-radius
    (laghubhaskariya_1963 II.18)."""
    if day_radius_value <= 0:
        raise ValueError("the day-radius must be positive")
    rsin_cara = abs(earthsine_value) * table.radius / day_radius_value
    if rsin_cara > table.radius:
        raise NoSunrise("no sunrise: the Rsine of the ascensional difference exceeds the radius")
    c = table.arc(rsin_cara)
    return -c if earthsine_value < 0 else c


def half_day(cara_asus: Fraction, units: TimeUnits) -> Nadika:
    """Half the day in nāḍīs: a quarter of the day and night plus the cara (mahabhaskariya_1960
    IV.28)."""
    return Nadika(Fraction(units.nadis_per_day, QUARTERS_PER_DAY) + cara_asus / units.asus_per_nadi)


@dataclass(frozen=True, slots=True)
class SunriseTimes:
    """A day's bhujāntara and cara as fractions of a day, and its sunrise and sunset."""

    bhujantara_days: Fraction  # later when positive
    cara_days: Fraction  # later when positive (negative while the day is the longer)
    sunrise: Nadika  # after local mean midnight
    sunset: Nadika  # after local mean midnight


def mean_sunrise(units: TimeUnits) -> Nadika:
    """The mean sunrise after local mean midnight: a quarter of the text's day.

    6h local mean time, the quarter day the half-day
    rule starts from (mahabhaskariya_1960 IV.28, ``half_day.quarter_day_plus_cara``), in the
    text's nāḍīs (``time_units.nadis_per_day``), not a held literal.
    """
    return Nadika(Fraction(units.nadis_per_day, QUARTERS_PER_DAY))


def sunrise_after_midnight(
    bhujaphala_minutes: Fraction, cara_asus: Fraction, units: TimeUnits
) -> SunriseTimes:
    """The text's sunrise and sunset after local mean midnight (laghubhaskariya_1963 II.4(ii),
    II.19–21).

    ``bhujaphala_minutes`` is the Sun's signed bhujāphala (positive when
    additive); ``cara_asus`` the signed ascensional difference.
    """
    b = bhujaphala_minutes / units.asus_per_day  # minutes of arc are asus of time
    c = -cara_asus / units.asus_per_day
    sunrise = mean_sunrise(units) + Nadika((b + c) * units.nadis_per_day)
    return SunriseTimes(b, c, sunrise, sunset_after_midnight(sunrise, cara_asus, units))


def sunset_after_midnight(sunrise: Nadika, cara_asus: Fraction, units: TimeUnits) -> Nadika:
    """The sunset: the sunrise plus twice the half-day (mahabhaskariya_1960 IV.28;
    laghubhaskariya_1963 II.21)."""
    h = half_day(cara_asus, units)
    return sunrise + h + h
