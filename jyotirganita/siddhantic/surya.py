"""The Sūrya-siddhānta: rates from creation, the varying epicycle, the four processes.

suryasiddhanta_burgess_1860 (Burgess–Whitney) is the edition the elements are keyed from,
suryasiddhanta_hall_1859 (the
Sanskrit text with Raṅganātha's commentary) the witness. Every step is a
registered procedure (:mod:`jyotirganita.siddhantic.procedures`) whose datum
in ``data/texts/suryasiddhanta/procedures.yaml`` states it; nothing here
names a value.

**The count** (``ahargana.civil_days_since_creation``; i.48–51, i.53): the
sum of days is the civil days elapsed since the end of creation, at
midnight on the meridian of Laṅkā. The text places the end of the Kṛta of
the current mahāyuga at a stated number of years after creation (i.45–47,
``kalpa.elapsed_to_krta_end``); the Tretā and the Dvāpara follow, each its
stated share of the mahāyuga (i.17, ``yuga.quarters.*``), and the Kali
epoch is their end. The years to the Kali epoch become civil days by the
mahāyuga's own ratio (``yuga.civil_days`` to ``mahayuga.solar_years``),
and the Kali epoch is the era record's day: the civil day *d* has
the count ``N + (d − e)`` at the midnight that begins it, *N* the days to
the Kali epoch and *e* the era record's epoch. ``runs_from`` is *e*: no
page states a civil day the count from creation reaches before it.

**The mean** (``mean.revolutions_from_creation``; i.53–54): the sum of days
times an element's revolutions, divided by the civil days, gives the
revolutions and the part of a revolution; the revolutions are a
mahāyuga's (i.29–34) for the planets, the śīghroccas of Mercury and Venus,
the Moon's apsis and node, and a kalpa's (i.41–44) for the apsides and
nodes of the Sun and the five planets, whose civil days are the
mahāyuga's times the yugas of a kalpa (``kalpa.multiplier``). A node's
place is the result subtracted from a whole circle (i.54). Mercury and
Venus take the Sun's mean as their own (i.29, ``revolutions.shared_with_sun``).

**The carry** (``carry.epoch_advance_mean``; i.67): the mean daily motion
times the nāḍīs from midnight, divided by sixty, added after midnight.
The rest:

- the deśāntara (``carry.desantara_corrected_circumference``; i.60–61,
  i.63–65): every mean element moved at mean motion by the observer's
  offset east of the prime meridian, a sixtieth of a day for each nāḍī
  (the yojanas of i.65 over the corrected circumference of i.60: the
  scale cancels), subtracted east;
- the sunrise (``sunrise.surya_quarter_day_less_cara``; xiv.18–19,
  ii.61–63): half the night after the observer's midnight, a quarter of
  the day and night less the ascensional difference while the declination
  is north; the sunset twice the half-day later
  (``half_day.quarter_day_plus_cara``); the quarter is of the record's
  civil day, the text's 21600 respirations (the "corresponding day and
  night" of ii.59 needs rising times not keyed here: the half-day datum's
  ``provisional``);
- the cara's carry (``carry.cara_sunrise_mean_elements``, composed by
  ruling (h)): the places at that sunrise are the means carried to it at
  mean motion by i.67, before the equations; no verse applies the cara to
  a place (``procedures.cara.application``), and every day whose cara is
  not nil carries that gap's ``provisional`` flag;
- the bhujāntara (``carry.bhujantara_true_place``; ii.46): the true place
  moved by its true daily motion times the Sun's result from the
  base-sine over the minutes of a circle, in the direction of the Sun's
  equation. It corrects the place, not the time: each correction is
  applied once (the test of ruling (h)).

**The ascensional difference** (``ascensional_difference.palabha_versine``;
ii.60–62, iii.17b): the Sun's true longitude (deśāntara and bhujāntara
applied, before the cara) corrected by the precession (iii.9–10,
``declination_argument.ayana_corrected_true_longitude``) gives the
declination (ii.28, ii.58: ``declination.rsine_obliquity``); the
day-radius is the radius less the versed sine of the declination; the
earth-sine the sine of declination times the place's equinoctial shadow
over the gnomon (the shadow from the latitude by iii.17b); the sine of
the ascensional difference the earth-sine times the radius over the
day-radius, its arc the respirations. Reported longitudes are not
corrected by the precession.

**The daily motion** (``gati.equation_of_motion``; ii.47–51): the mean
daily motion (the Moon's less its apsis's) times the difference of the
tabular sines at the anomaly's base-sine, over the step, times the
corrected epicycle of the apsis over a circle, additive in the half-orbit
from Cancer; for a planet then the conjunction's motion less that, times
the last hypotenuse less the radius, over the hypotenuse. It is the
motion of the bhujāntara, of the chord inside the day and of the endings
(ii.64–66, ``ending.proportional_parts``).

**The true place** (ii.29–45): the anomaly (kendra) is the apsis or the
conjunction less the planet (ii.29); its quadrant gives the base-sine and
the perpendicular-sine (ii.30); the epicycle varies with the base-sine
between its values at the ends of the even and odd quadrants (ii.38); the
equation of the apsis is the arc of base-sine × epicycle ÷ 360 (ii.39), that
of the conjunction the arc of the base-result × radius ÷ the variable
hypotenuse (ii.40–42); each is additive while the anomaly lies in the
half-orbit from Aries (ii.45). The Sun and the Moon take the equation of
the apsis alone; the five planets the four processes of ii.43–44.

**Latitude** (``latitude.node_hypotenuse``; ii.56–57): the node of
Mars, Jupiter and Saturn takes the planet's equation of the conjunction,
that of Mercury and Venus the third process's equation of the apsis
reversed; the sine of the planet (Mercury and Venus: their conjunction)
less the node, times the extreme latitude (i.68–70), divided by the last
hypotenuse (the Moon: by the radius), is the latitude.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction

from jyotirganita.core.engine import Capabilities, CivilDayFrame
from jyotirganita.core.exact import Rounding, round_to
from jyotirganita.core.memo import DayMemo
from jyotirganita.core.types import (
    JDN,
    NOT_MODELLED,
    Ahargana,
    AngleUnit,
    ExactArc,
    Nadika,
    NotModelled,
    SiddhanticCivilInstant,
    SiderealLongitude,
    TropicalLongitude,
    TrueOfDate,
)
from jyotirganita.data.datum import Record
from jyotirganita.siddhantic.endings import chord
from jyotirganita.siddhantic.engine import (
    BeforeRunsFrom,
    EngineRefusal,
    NoSunriseAtPlace,
    Observer,
    SunriseProvider,
    hybrid_nadikas,
)
from jyotirganita.siddhantic.epicycle import bhuja_koti, karna
from jyotirganita.siddhantic.procedures import resolve
from jyotirganita.siddhantic.sunrise import TimeUnits, half_day, rsine_declination
from jyotirganita.siddhantic.tabular import DayUnits
from jyotirganita.siddhantic.text import TextData

__all__ = [
    "Elements",
    "SineTable",
    "SuryaEngine",
    "SuryaModel",
    "SuryaRefusal",
    "SuryaTerms",
    "ascensional_difference_surya",
    "corrected_epicycle",
    "manda_equation",
    "manda_motion_equation",
    "mean_remainder",
    "sighra_equation",
    "sighra_motion_equation",
]

DEGREES_PER_REVOLUTION = 360
DEGREES_PER_HALF_ORBIT = 180
DEGREES_PER_QUADRANT = 90
MINUTES_PER_DEGREE = 60
NADIKAS_PER_DAY = 60  # the record's nāḍikās in a civil day
QUARTERS_PER_DAY = 4
#: the observer's mean sunrise on the text's meridian at the equator, after midnight
SUNRISE_AFTER_MIDNIGHT = Fraction(1, QUARTERS_PER_DAY)
FULL_EVALUATION = "diagnostic.full_evaluation"
LINEAR_GATI = "intraday.linear_gati"

#: the procedure each slot must name for this engine
SUPPORTED: Mapping[str, str] = {
    "time_base": "ahargana.civil_days_since_creation",
    "weekday": "weekday.remainder_from_sunday",
    "mean_longitude": "mean.revolutions_from_creation",
    "computation_instant": "computation_instant.lanka_midnight",
    "carry.epoch_advance": "carry.epoch_advance_mean",
    "rsine": "trig.sine_table_linear",
    "arc": "trig.arc_from_sine_table",
    "bhuja_koti": "epicycle.bhuja_koti",
    "pulsation": "epicycle.base_sine_variation",
    "manda": "epicycle.manda_arc",
    "sighra": "epicycle.sighra_variable_hypotenuse",
    "order.luminaries": "order.manda_only",
    "order.planets": "order.four_processes",
    "latitude": "latitude.node_hypotenuse",
    "sunrise": "sunrise.surya_quarter_day_less_cara",
    "carry.desantara": "carry.desantara_corrected_circumference",
    "carry.bhujantara": "carry.bhujantara_true_place",
    "carry.cara": "carry.cara_sunrise_mean_elements",
    "declination": "declination.rsine_obliquity",
    "declination.argument": "declination_argument.ayana_corrected_true_longitude",
    "ascensional_difference": "ascensional_difference.palabha_versine",
    "half_day": "half_day.quarter_day_plus_cara",
    "gati": "gati.equation_of_motion",
    "proportional_parts": "ending.proportional_parts",
    "intraday": LINEAR_GATI,
}
#: the carry slots and the action each states (acts_on, motion, applies_to)
ALL_ELEMENTS = ("all_elements",)
CARRY: Mapping[str, tuple[str, str, tuple[str, ...] | None]] = {
    "carry.epoch_advance": ("mean_before_equation", "mean", ALL_ELEMENTS),
    "carry.desantara": ("mean_before_equation", "mean", ALL_ELEMENTS),
    "carry.cara": ("mean_before_equation", "mean", ALL_ELEMENTS),
    "carry.bhujantara": ("true_after_equation", "true", None),  # every body (checked in build)
}
#: the slot whose rule is the engine's composition, no verse's (basis fallback_no_stated_rule)
FALLBACK_SLOTS = ("carry.cara",)
#: the gap a day with a cara carries (ruling (h)): no verse applies the cara to a place
CARA_GAP = "procedures.cara.application"
OBLIQUITY = "obliquity"
GNOMON = "gnomon.palabha_from_latitude.iii17b.n1.suryasiddhanta_burgess_1860"
GATI_DIVISOR = "procedures.gati.rule.ii48.n1.suryasiddhanta_burgess_1860"
#: iii.9: the libration's revolutions in an Age; iii.10: the multiplier and divisor
AYANA = (
    "procedures.declination.argument.iii9.n1.suryasiddhanta_burgess_1860",
    "procedures.declination.argument.iii10.n1.suryasiddhanta_burgess_1860",
    "procedures.declination.argument.iii10.n2.suryasiddhanta_burgess_1860",
)

_YUGA_REVOLUTIONS = re.compile(r"^([a-z_]+)\.revolutions$")
_KALPA_REVOLUTIONS = re.compile(r"^([a-z]+)\.(apsis|node)\.revolutions_per_kalpa$")
_RSINE = re.compile(r"^trig\.rsine\.e(\d\d)$")
_RVERSINE = re.compile(r"^trig\.rversine\.e(\d\d)$")


def _floor(x: Fraction) -> int:
    """The floor of an exact number (no ``math`` under ``siddhantic/``)."""
    return x.numerator // x.denominator


class SuryaRefusal(EngineRefusal):
    """A request this engine refuses with a hard error."""


class SuryaNoSunrise(SuryaRefusal, NoSunriseAtPlace):
    """A day whose Sun the text's rule does not raise at the observer's latitude."""


# --- trigonometry (ii.31–33) ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SineTable:
    """The tabular sines at a fixed step, in minutes (ii.15–22, ii.31–33).

    ``rsines`` the tabulated values in order (the first at one step); the
    radius is the last sine, the sine of a quadrant (suryasiddhanta_hall_1859's radius computation,
    fixture ``ranganatha_radius``). ``rversines`` the versed sines of ii.22–27
    in the same order (the day-radius of ii.60; empty where none is loaded).
    """

    step: int
    rsines: tuple[int, ...]
    rversines: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.step <= 0 or not self.rsines:
            raise SuryaRefusal("a sine table has a positive step and at least one sine")
        if self.rversines and len(self.rversines) != len(self.rsines):
            raise SuryaRefusal("the versed sines are tabulated at the sines' steps")
        # the sines rise, or the inverse is not one
        if not all(a < b for a, b in zip((0, *self.rsines[:-1]), self.rsines, strict=True)):
            raise SuryaRefusal("the tabular sines do not rise")

    @property
    def radius(self) -> int:
        """The sine of a quadrant: the last tabular sine."""
        return self.rsines[-1]

    @property
    def quadrant(self) -> int:
        """A quadrant in minutes: the step times the number of sines."""
        return self.step * len(self.rsines)

    def rsine(self, arc: Fraction | int) -> Fraction:
        """The sine of ``arc`` minutes, ``0 ≤ arc ≤`` a quadrant (ii.31–32).

        The minutes divided by the step give the number of the preceding
        tabular sine; the remainder times the difference of the preceding
        and the following, divided by the step, is added to the preceding.
        """
        return self._interpolate(self.rsines, Fraction(arc))

    def rversine(self, arc: Fraction | int) -> Fraction:
        """The versed sine of ``arc`` minutes by the same rule (ii.32: "so also" for them)."""
        if not self.rversines:
            raise SuryaRefusal("no versed sines are loaded")
        return self._interpolate(self.rversines, Fraction(arc))

    def difference(self, arc: Fraction | int) -> int:
        """The difference of the tabular sines whose step holds ``arc`` minutes (ii.48).

        The sine at the step's end less the sine at its start; an arc on a
        step's boundary takes the step it opens (the quadrant's end the last).
        """
        a = Fraction(arc)
        if not 0 <= a <= self.quadrant:
            raise SuryaRefusal(f"arc {a}′ is outside the quadrant [0, {self.quadrant}′]")
        n = min(_floor(a / self.step), len(self.rsines) - 1)
        return self.rsines[n] - (self.rsines[n - 1] if n else 0)

    def _interpolate(self, table: Sequence[int], a: Fraction) -> Fraction:
        if not 0 <= a <= self.quadrant:
            raise SuryaRefusal(f"arc {a}′ is outside the quadrant [0, {self.quadrant}′]")
        q, r = divmod(a, self.step)
        n = int(q)
        preceding = Fraction(table[n - 1]) if n else Fraction(0)
        if not r:
            return preceding
        return preceding + r * (table[n] - preceding) / self.step

    def arc(self, sine: Fraction | int) -> Fraction:
        """The arc in minutes whose sine is ``sine``, ``0 ≤ sine ≤`` the radius (ii.33).

        The next less tabular sine is subtracted; the remainder times the
        step, divided by the difference between the next less and the next
        greater tabular sines, is added to the step times the serial number
        of the next less.
        """
        s = Fraction(sine)
        if not 0 <= s <= self.radius:
            raise SuryaRefusal(f"sine {s} is outside [0, {self.radius}]")
        n = 0
        while n < len(self.rsines) and self.rsines[n] <= s:
            n += 1
        less = Fraction(self.rsines[n - 1]) if n else Fraction(0)
        out = Fraction(n * self.step)
        if s > less:
            out += (s - less) * self.step / (self.rsines[n] - less)
        return out

    def signed_rsine(self, degrees: Fraction) -> Fraction:
        """The sine of an arc of any size: of its bhujā, positive in the half-orbit from Aries."""
        k = degrees % DEGREES_PER_REVOLUTION
        _, _, bhuja, _ = bhuja_koti(k)
        s = self.rsine(bhuja * MINUTES_PER_DEGREE)
        return s if k < DEGREES_PER_HALF_ORBIT else -s


# --- the epicycle and the equations (ii.29–45) ----------------------------------------------


@dataclass(frozen=True, slots=True)
class Epicycles:
    """A body's epicycle at the ends of the even and the odd quadrants, in degrees."""

    even: Fraction
    odd: Fraction


def corrected_epicycle(e: Epicycles, base_sine: Fraction, radius: int) -> Fraction:
    """The corrected epicycle at ``base_sine`` (ii.38).

    The base-sine times the difference of the odd and even epicycles,
    divided by the radius, applied to the even epicycle: additive when the
    even is less than the odd, subtractive when greater.
    """
    change = base_sine * abs(e.odd - e.even) / radius
    return e.even + change if e.even < e.odd else e.even - change


@dataclass(frozen=True, slots=True)
class Equation:
    """One equation: its signed value in degrees, and the variable hypotenuse (śīghra)."""

    degrees: Fraction
    hypotenuse: Fraction | None = None


def manda_equation(e: Epicycles, kendra: Fraction, table: SineTable, circle: int) -> Equation:
    """The equation of the apsis at ``kendra`` (apsis less planet, degrees) (ii.29–30, 38–39, 45).

    The base-sine times the corrected epicycle divided by the degrees of a
    circle; its arc is the equation in minutes; additive while the anomaly
    lies in the half-orbit from Aries.
    """
    k = kendra % DEGREES_PER_REVOLUTION
    _, _, bhuja, _ = bhuja_koti(k)
    base = table.rsine(bhuja * MINUTES_PER_DEGREE)
    epicycle = corrected_epicycle(e, base, table.radius)
    minutes = table.arc(base * epicycle / circle)
    degrees = minutes / MINUTES_PER_DEGREE
    return Equation(degrees if k < DEGREES_PER_HALF_ORBIT else -degrees)


def sighra_equation(
    e: Epicycles, kendra: Fraction, table: SineTable, circle: int, resolution: Fraction
) -> Equation:
    """The equation of the conjunction at ``kendra`` (conjunction less planet) (ii.38–42, 45).

    The perpendicular-result is added to the radius while the anomaly lies
    in the half-orbit from Capricorn, subtracted in that from Cancer; the
    variable hypotenuse is the root of that squared plus the base-result
    squared (truncated at ``resolution``, the engine parameter
    ``siddhantic.karna_root_resolution``: no precision is stated); the arc
    of base-result × radius ÷ hypotenuse is the equation in minutes,
    additive while the anomaly lies in the half-orbit from Aries.
    """
    k = kendra % DEGREES_PER_REVOLUTION
    quadrant, _, bhuja, koti = bhuja_koti(k)
    base = table.rsine(bhuja * MINUTES_PER_DEGREE)
    perpendicular = table.rsine(koti * MINUTES_PER_DEGREE)
    epicycle = corrected_epicycle(e, base, table.radius)
    base_result = base * epicycle / circle
    perp_result = perpendicular * epicycle / circle
    # quadrants 4 and 1 lie in the half-orbit beginning with Capricorn
    side = table.radius + perp_result if quadrant in (1, 4) else table.radius - perp_result
    square = side * side + base_result * base_result
    h = karna(square, resolution)
    if square and not h:
        # a root truncated to nothing hides the equation
        raise SuryaRefusal(f"śīghra hypotenuse: the root of {square} truncates to 0")
    minutes = table.arc(base_result * table.radius / h) if h else Fraction(0)
    degrees = minutes / MINUTES_PER_DEGREE
    return Equation(degrees if k < DEGREES_PER_HALF_ORBIT else -degrees, h)


# --- the daily motion (ii.47–51) and the ascensional difference (ii.58–62) --------------------


def manda_motion_equation(
    e: Epicycles, kendra: Fraction, table: SineTable, circle: int, motion: Fraction
) -> Fraction:
    """The equation of a daily motion for the apsis, in degrees a day (ii.48–49).

    ``motion`` the daily motion it is calculated from (the Moon's less its
    apsis's, ii.47), ``kendra`` the anomaly (apsis less planet). The motion
    times the difference of the tabular sines at the anomaly's base-sine,
    divided by the step, times the corrected epicycle (ii.38), divided by
    the degrees of a circle; additive while the anomaly lies in the
    half-orbit beginning with Cancer, subtractive in that from Capricorn.
    """
    k = kendra % DEGREES_PER_REVOLUTION
    _, _, bhuja, _ = bhuja_koti(k)
    minutes = bhuja * MINUTES_PER_DEGREE
    epicycle = corrected_epicycle(e, table.rsine(minutes), table.radius)
    eq = motion * table.difference(minutes) / table.step * epicycle / circle
    return eq if DEGREES_PER_QUADRANT <= k < DEGREES_PER_QUADRANT * 3 else -eq


def sighra_motion_equation(
    conjunction_motion: Fraction, manda_gati: Fraction, hypotenuse: Fraction, radius: int
) -> Fraction:
    """The equation of a daily motion for the conjunction, in degrees a day (ii.50–51).

    The conjunction's daily motion less the motion corrected for the apsis,
    times the last hypotenuse less the radius, divided by the hypotenuse:
    additive while the hypotenuse is the greater, subtractive while the
    less; a subtraction greater than the motion leaves it retrograde (the
    sign of the sum).
    """
    if hypotenuse <= 0:
        raise SuryaRefusal("the variable hypotenuse is not positive")
    return (conjunction_motion - manda_gati) * (hypotenuse - radius) / hypotenuse


@dataclass(frozen=True, slots=True)
class CaraTerms:
    """The day-radius, the earth-sine and the signed ascensional difference in respirations."""

    day_radius: Fraction
    earthsine: Fraction
    cara_asus: Fraction  # positive while the day is the longer


def palabha(table: SineTable, latitude_degrees: Fraction, gnomon: int) -> Fraction:
    """The equinoctial shadow: Rsin latitude × the gnomon ÷ Rsin co-latitude (iii.17b)."""
    phi = abs(latitude_degrees)
    if phi >= DEGREES_PER_QUADRANT:
        raise SuryaRefusal(f"latitude {latitude_degrees}° is not a place")
    s = table.rsine(phi * MINUTES_PER_DEGREE) * gnomon
    shadow = s / table.rsine((DEGREES_PER_QUADRANT - phi) * MINUTES_PER_DEGREE)
    return -shadow if latitude_degrees < 0 else shadow


def ascensional_difference_surya(
    table: SineTable, rsin_declination: Fraction, shadow: Fraction, gnomon: int
) -> CaraTerms:
    """The ascensional difference from the signed sine of declination (ii.60–62).

    The day-radius is the radius less the versed sine of the declination
    (ii.60); the earth-sine the sine of declination times the equinoctial
    shadow, divided by the gnomon (ii.61); the sine of the ascensional
    difference the earth-sine times the radius divided by the day-radius,
    its arc in minutes the respirations (ii.61–62).
    """
    declination_arc = table.arc(abs(rsin_declination))
    radius = table.radius - table.rversine(declination_arc)
    if radius <= 0:
        raise SuryaRefusal("the day-radius is not positive")
    earth = rsin_declination * shadow / gnomon
    rsin_cara = abs(earth) * table.radius / radius
    if rsin_cara > table.radius:
        raise SuryaNoSunrise(
            "no sunrise: the sine of the ascensional difference exceeds the radius"
        )
    c = table.arc(rsin_cara)
    return CaraTerms(radius, earth, -c if earth < 0 else c)


# --- the mean (i.48–54) ----------------------------------------------------------------------


def mean_remainder(revolutions: int, civil_days: int, days: Fraction) -> Fraction:
    """The part of a revolution in degrees after ``days`` of the count (i.53).

    ``days`` times ``revolutions`` divided by ``civil_days`` (the civil days
    of the period the revolutions are stated for); the whole revolutions
    dropped.
    """
    x = Fraction(revolutions) * days / civil_days
    return (x - _floor(x)) * DEGREES_PER_REVOLUTION


@dataclass(frozen=True, slots=True)
class Elements:
    """The rates of every element: revolutions and the civil days they take."""

    revolutions: Mapping[str, int]
    civil_days: Mapping[str, int]
    nodes: frozenset[str]

    def mean(self, element: str, days: Fraction) -> Fraction:
        """The element's place after ``days`` of the count, a node's subtracted from a circle."""
        r = mean_remainder(self.revolutions[element], self.civil_days[element], days)
        return (-r) % DEGREES_PER_REVOLUTION if element in self.nodes else r

    def motion(self, element: str) -> Fraction:
        """The element's mean daily motion in degrees (negative for a node)."""
        m = Fraction(self.revolutions[element] * DEGREES_PER_REVOLUTION, self.civil_days[element])
        return -m if element in self.nodes else m


@dataclass(frozen=True, slots=True)
class Body:
    """A body: its mean element, its apsis element, its conjunction element, its epicycles."""

    body: str
    mean: str
    apsis: str
    conjunction: str | None
    manda: Epicycles
    sighra: Epicycles | None
    node: str | None  # the node element of its latitude
    extreme_latitude: Fraction | None  # minutes
    order: str  # "order.luminaries" | "order.planets"


@dataclass(slots=True)
class SuryaModel:
    """The Sūrya-siddhānta's numbers, read once from its data."""

    text: str
    data: TextData
    procedures: Mapping[str, Record]
    elements: Elements
    table: SineTable
    planets: Mapping[str, Body]
    days_to_epoch: int
    circle: int
    signs_per_circle: int
    karna_resolution: Fraction
    units: DayUnits
    node_element: str
    time: TimeUnits
    rsin_obliquity: Fraction
    gnomon: int
    circle_minutes: int
    ayana_rate: tuple[int, int]  # the libration's revolutions in an Age, the Age's civil days
    ayana_factor: Fraction  # iii.10: the multiplier over the divisor
    saka_to_kali_years: int | None = None
    flags: tuple[str, ...] = field(default=())

    @property
    def revolutions(self) -> Mapping[str, int]:
        """Each element's revolutions in its own period."""
        return self.elements.revolutions

    def mean_sun_signs_at_epoch_sunrise(self) -> Fraction:
        """The mean Sun in signs at the mean sunrise of the Kali epoch's day (a search aid).

        The count's place at the Kali midnight carried a quarter day (i.67); the calendar's mean
        year starts count from it.
        """
        sun = self.planets["sun"].mean
        days = self.days_to_epoch + SUNRISE_AFTER_MIDNIGHT
        return self.elements.mean(sun, days) * self.signs_per_circle / DEGREES_PER_REVOLUTION

    @classmethod
    def build(
        cls, data: TextData, procedures: Mapping[str, Record], karna_resolution: Fraction
    ) -> SuryaModel:
        """Read the model; ``procedures`` maps each slot to its datum (the registry's)."""
        for slot, expected in SUPPORTED.items():
            rec = _named(data, procedures, slot)
            if rec.raw["procedure"] != expected:
                raise SuryaRefusal(
                    f"{rec.key}: procedure {rec.raw['procedure']} for {slot!r} is not one "
                    f"this engine runs ({expected})"
                )
        for slot in FALLBACK_SLOTS:
            rec = procedures[slot]
            if rec.raw.get("basis") != "fallback_no_stated_rule":
                raise SuryaRefusal(f"{rec.key}: {slot} is the engine's composition, no stated rule")
        suffixes = sorted(k.removeprefix(data.prefix) for k in data._records)
        yuga_days = data.integer("yuga.civil_days")
        kalpa_days = yuga_days * data.integer("kalpa.multiplier")
        revolutions: dict[str, int] = {}
        periods: dict[str, int] = {}
        nodes: set[str] = set()
        for s in suffixes:
            m = _YUGA_REVOLUTIONS.match(s)
            if m and m.group(1) != "asterisms" and data.has(s):
                revolutions[m.group(1)] = data.integer(s)
                periods[m.group(1)] = yuga_days
            k = _KALPA_REVOLUTIONS.match(s)
            if k and data.has(s):
                element = f"{k.group(1)}_{k.group(2)}"
                revolutions[element] = data.integer(s)
                periods[element] = kalpa_days
                if k.group(2) == "node":
                    nodes.add(element)
        data.record("revolutions.shared_with_sun")
        data.record("procedures.mean_longitude.apsides_nodes")  # i.54: nodes retrograde
        nodes.add("moon_node")
        elements = Elements(revolutions, periods, frozenset(nodes))
        circle = data.integer("circle.revolution.signs") * data.integer("circle.sign.degrees")
        sign_minutes = data.integer("circle.sign.degrees") * data.integer("circle.degree.minutes")
        step = data.fraction("trig.step") * sign_minutes
        if step.denominator != 1:
            raise SuryaRefusal(f"{data.key('trig.step')}: the step is not whole minutes")
        table = SineTable(
            int(step), _entries(data, suffixes, _RSINE), _entries(data, suffixes, _RVERSINE)
        )
        if len(table.rsines) != data.integer("trig.rsine.count"):
            raise SuryaRefusal(f"{data.key('trig.rsine.count')}: the table's length differs")
        if data.integer(GATI_DIVISOR) != table.step:
            raise SuryaRefusal(f"{data.key(GATI_DIVISOR)}: ii.48 divides by the table's step")
        planets = _bodies(data, procedures, elements)
        for slot, (acts_on, motion, applies) in CARRY.items():
            rec = procedures[slot]
            got = (rec.raw.get("acts_on"), rec.raw.get("motion"), rec.raw.get("applies_to"))
            want = (acts_on, motion, list(applies) if applies is not None else sorted(planets))
            if (got[0], got[1], sorted(got[2] or ())) != (want[0], want[1], sorted(want[2])):
                raise SuryaRefusal(f"{rec.key}: {slot} states {want}, not {got}")
        nadis = data.integer("time.day.nadis")
        if nadis != NADIKAS_PER_DAY:
            raise SuryaRefusal(f"{data.key('time.day.nadis')}: the day is the record's sixty")
        time = TimeUnits(
            nadis, data.integer("time.nadi.vinadis") * data.integer("time.vinadi.pranas")
        )
        data.record("declination.rule")  # ii.28: the rule the obliquity serves
        revs, mult, div = (data.integer(k) for k in AYANA)
        return cls(
            data.text,
            data,
            procedures,
            elements,
            table,
            planets,
            _days_to_kali(data, yuga_days),
            circle,
            data.integer("circle.revolution.signs"),
            karna_resolution,
            DayUnits(NADIKAS_PER_DAY),
            "moon_node",
            time,
            Fraction(data.integer(OBLIQUITY)),
            data.integer(GNOMON),
            circle * data.integer("circle.degree.minutes"),
            (revs, yuga_days),
            Fraction(mult, div),
        )

    # --- the four processes (ii.43–44) -----------------------------------------------

    def manda(self, p: Body, mean: Mapping[str, Fraction], place: Fraction) -> Equation:
        """The equation of the apsis for a body at ``place``."""
        return manda_equation(p.manda, mean[p.apsis] - place, self.table, self.circle)

    def sighra(self, p: Body, mean: Mapping[str, Fraction], place: Fraction) -> Equation:
        """The equation of the conjunction for a body at ``place``."""
        assert p.sighra is not None and p.conjunction is not None
        return sighra_equation(
            p.sighra, mean[p.conjunction] - place, self.table, self.circle, self.karna_resolution
        )

    def processes(self, p: Body, mean: Mapping[str, Fraction]) -> tuple[Fraction, ...]:
        """The places after each process; the last is the true place (not reduced)."""
        m = mean[p.mean]
        if p.order == "order.luminaries":
            return (m + self.manda(p, mean, m).degrees,)
        # ii.44: half the equation of the conjunction on the mean; half that of the
        # apsis (from that place) on that; the whole equation of the apsis (from that
        # place) on the mean; the whole equation of the conjunction (from that) on that
        p1 = m + self.sighra(p, mean, m).degrees / 2
        p2 = p1 + self.manda(p, mean, p1).degrees / 2
        p3 = m + self.manda(p, mean, p2).degrees
        p4 = p3 + self.sighra(p, mean, p3).degrees
        return (p1, p2, p3, p4)

    def true(self, p: Body, mean: Mapping[str, Fraction]) -> Fraction:
        """The body's true place (not reduced)."""
        return self.processes(p, mean)[-1]

    def bhujaphala_minutes(self, mean: Mapping[str, Fraction]) -> Fraction:
        """The Sun's result from the base-sine in minutes, signed as applied (ii.39, ii.46)."""
        sun = self.planets["sun"]
        return self.manda(sun, mean, mean[sun.mean]).degrees * MINUTES_PER_DEGREE

    def gati(self, p: Body, mean: Mapping[str, Fraction]) -> Fraction:
        """The body's true daily motion in degrees a day (ii.47–51).

        The Sun and the Moon take the equation for the apsis alone, the
        Moon's from its motion less its apsis's (ii.47); a planet's for the
        apsis from the place the third process takes its anomaly from, then
        the equation for the conjunction from the last hypotenuse (ii.50–51).
        """
        e = self.elements
        motion = e.motion(p.mean)
        if p.order == "order.luminaries":
            # ii.47: the Moon's daily motion less its apsis's; the Sun's apsis is fixed in it
            own = motion - e.motion(p.apsis) if p.body == "moon" else motion
            kendra = mean[p.apsis] - mean[p.mean]
            return motion + manda_motion_equation(p.manda, kendra, self.table, self.circle, own)
        assert p.conjunction is not None
        steps = self.processes(p, mean)
        kendra = mean[p.apsis] - steps[1]
        manda_gati = motion + manda_motion_equation(
            p.manda, kendra, self.table, self.circle, motion
        )
        last = self.sighra(p, mean, steps[2])
        assert last.hypotenuse is not None
        return manda_gati + sighra_motion_equation(
            e.motion(p.conjunction), manda_gati, last.hypotenuse, self.table.radius
        )

    def ayana(self, days: Fraction) -> Fraction:
        """The precession in degrees after ``days`` of the count (iii.9–10).

        The bhujā of the part of a revolution of the libration, times the
        multiplier and divided by the divisor iii.10 states. The sign is not
        stated as read: additive while the part lies in the half-revolution
        from 180° (suryasiddhanta_burgess_1860's worked example, fixture
        ``whitney_precession_example``),
        subtractive in the other
        (``procedures.declination.argument.iii10.suryasiddhanta_burgess_1860``,
        its ``provisional``; ruling (i)).
        """
        revs, civil_days = self.ayana_rate
        part = mean_remainder(revs, civil_days, days)
        _, _, bhuja, _ = bhuja_koti(part)
        degrees = bhuja * self.ayana_factor
        return degrees if part >= DEGREES_PER_HALF_ORBIT else -degrees

    def latitude(self, p: Body, mean: Mapping[str, Fraction]) -> Fraction:
        """The body's latitude in minutes, north positive (ii.56–57, i.68–70)."""
        if p.node is None or p.extreme_latitude is None:
            raise SuryaRefusal(f"{self.text}: no latitude rule for {p.body}")
        node = mean[p.node]
        if p.order == "order.luminaries":
            place = self.true(p, mean)
            divisor = Fraction(self.table.radius)
        else:
            steps = self.processes(p, mean)
            p3 = steps[2]
            last = self.sighra(p, mean, p3)
            assert last.hypotenuse is not None and p.conjunction is not None
            divisor = last.hypotenuse
            if p.mean == p.body:
                # ii.56: Mars, Jupiter, Saturn: the equation of the conjunction, as to the planet
                node += last.degrees
                place = steps[-1]
            else:
                # ii.56: Mercury, Venus: the third process's equation of the apsis, reversed;
                # ii.57: the arc from the conjunction
                node -= self.manda(p, mean, steps[1]).degrees
                place = mean[p.conjunction]
        return self.table.signed_rsine(place - node) * p.extreme_latitude / divisor


def _named(data: TextData, procedures: Mapping[str, Record], slot: str) -> Record:
    rec = procedures.get(slot)
    if rec is None:
        raise SuryaRefusal(f"{data.text}: no procedure datum for slot {slot!r}")
    name = rec.raw.get("procedure")
    if not isinstance(name, str):
        raise SuryaRefusal(f"{rec.key}: the datum names no procedure")
    resolve(name, slot)
    data.mark_used(rec)
    return rec


def _entries(data: TextData, suffixes: Sequence[str], pattern: re.Pattern[str]) -> tuple[int, ...]:
    found: dict[int, int] = {}
    for s in suffixes:
        m = pattern.match(s)
        if m:
            found[int(m.group(1))] = data.integer(s)
    if sorted(found) != list(range(1, len(found) + 1)):
        raise SuryaRefusal(f"{data.text}: tabular entries not numbered 1…{len(found)}")
    return tuple(found[i] for i in sorted(found))


def _days_to_kali(data: TextData, yuga_days: int) -> int:
    """The civil days from the end of creation to the Kali epoch (i.17, i.45–47; reading 4)."""
    shares = data.integer("yuga.quarters.share.treta") + data.integer("yuga.quarters.share.dvapara")
    years = data.integer("kalpa.elapsed_to_krta_end") + shares * data.fraction(
        "yuga.quarters.part"
    ) * data.integer("mahayuga.solar_years")
    days = years * yuga_days / data.integer("mahayuga.solar_years")
    if days.denominator != 1:
        raise SuryaRefusal("the civil days to the Kali epoch are not whole (i.45–47, i.17)")
    return int(days)


def _epicycles(data: TextData, body: str, kind: str) -> Epicycles | None:
    even_key = f"epicycles.{body}.{kind}.even"
    if not data.has(even_key):
        return None
    even = data.fraction(even_key)
    odd_key = f"epicycles.{body}.{kind}.odd"
    if data.has(odd_key):
        return Epicycles(even, data.fraction(odd_key))
    # ii.34: the Sun's and the Moon's at the odd quadrants are less by stated minutes
    reduction = data.fraction(f"epicycles.{_pair(body)}.{kind}.odd_reduction")
    return Epicycles(even, even - reduction / MINUTES_PER_DEGREE)


def _pair(body: str) -> str:
    if body in ("sun", "moon"):
        return "sun_moon"
    raise SuryaRefusal(f"epicycles.{body}: no odd-quadrant epicycle and no stated reduction")


def _bodies(
    data: TextData, procedures: Mapping[str, Record], elements: Elements
) -> dict[str, Body]:
    orders = {
        slot: frozenset(str(b) for b in procedures[slot].raw.get("applies_to", ()))
        for slot in ("order.luminaries", "order.planets")
    }
    multiplier = data.integer("latitude.multiplier")
    out: dict[str, Body] = {}
    for slot, bodies in orders.items():
        for body in sorted(bodies):
            if body in out:
                raise SuryaRefusal(f"{procedures[slot].key}: {body} is in two orders")
            manda = _epicycles(data, body, "manda")
            if manda is None:
                raise SuryaRefusal(f"{data.key(body)}: no epicycle of the apsis")
            lat = f"{body}.latitude_max"
            extreme = Fraction(data.integer(lat) * multiplier) if data.has(lat) else None
            if slot == "order.luminaries":
                apogee = f"{body}_apogee"
                apsis = apogee if apogee in elements.revolutions else f"{body}_apsis"
                node = f"{body}_node" if f"{body}_node" in elements.revolutions else None
                out[body] = Body(body, body, apsis, None, manda, None, node, extreme, slot)
                continue
            sighra = _epicycles(data, body, "sighra")
            if sighra is None:
                raise SuryaRefusal(f"{data.key(body)}: no epicycle of the conjunction")
            own = f"{body}_sighrocca"
            if own in elements.revolutions:
                # i.29: the mean of Mercury and Venus is the Sun's; their own is the conjunction
                mean, conjunction = "sun", own
            else:
                mean, conjunction = body, "sun"
            apsis, node = f"{body}_apsis", f"{body}_node"
            out[body] = Body(body, mean, apsis, conjunction, manda, sighra, node, extreme, slot)
    for p in out.values():
        for element in (p.mean, p.apsis, p.conjunction, p.node):
            if element is not None and element not in elements.revolutions:
                raise SuryaRefusal(f"{data.text}: {p.body} needs {element}, which has no rate")
    return dict(sorted(out.items()))


@dataclass(frozen=True, slots=True)
class SuryaTerms:
    """A day's sunrise terms (ii.46, ii.58–63, iii.9–10).

    ``bhujaphala_minutes`` the Sun's result from the base-sine and
    ``ayana_degrees`` the precession, both at the observer's mean sunrise;
    ``rsin_declination`` from the Sun before the cara corrected by the
    precession; ``cara`` the day-radius, earth-sine and ascensional
    difference; ``cara_days`` the sunrise's move by it (later when
    positive); ``shift_days`` the time from the count's midnight on the
    prime meridian to the sunrise, at which the means are taken (the
    deśāntara, the quarter day and the cara).
    """

    bhujaphala_minutes: Fraction
    ayana_degrees: Fraction
    rsin_declination: Fraction
    cara: CaraTerms
    cara_days: Fraction
    sunrise: Nadika
    sunset: Nadika
    shift_days: Fraction

    @property
    def cara_asus(self) -> Fraction:
        """The signed ascensional difference in respirations (positive: the day the longer)."""
        return self.cara.cara_asus


@dataclass(frozen=True, slots=True)
class SuryaDay:
    """One civil day's positions at the text's sunrise, with the flags raised.

    The fields of :class:`jyotirganita.siddhantic.engine.DayPositions`;
    ``ahargana`` is the civil days since the Kali epoch (the era record's
    day, runs_from); ``creation_count`` is the text's own sum of days from
    the end of creation at the midnight that begins the day (i.48–51);
    ``mean`` the means at the sunrise (the deśāntara and the cara applied),
    ``true`` the true places there with the bhujāntara; under the hybrid
    alternative ``terms`` is ``None`` and ``sunset`` the provider's.
    """

    jdn: JDN
    ahargana: Ahargana
    creation_count: int
    completed_years: int
    layer_counts: Mapping[str, int]  # empty: no layer
    mean: Mapping[str, Fraction]
    true: Mapping[str, Fraction]
    node: Fraction
    flags: tuple[str, ...]
    sunrise: Nadika
    sunset: Nadika | None
    terms: SuryaTerms | None = None


class SuryaEngine:
    """The engine protocol for the Sūrya-siddhānta and one observer (no layer).

    The observer's offset from the prime meridian and its latitude are
    carried by the text's rules (the module docstring); a place reaches the
    text by its route.
    """

    def __init__(
        self,
        model: SuryaModel,
        observer: Observer,
        epoch: JDN,
        *,
        sunrise_provider: SunriseProvider | None = None,
        hybrid_quantum: Fraction | None = None,
        intraday: str = LINEAR_GATI,
    ) -> None:
        if model.text not in observer.texts:
            raise SuryaRefusal(
                f"observer {observer.id} has no coordinates for {model.text} "
                "(the place's route names the texts it serves)"
            )
        if sunrise_provider is not None and hybrid_quantum is None:
            raise SuryaRefusal("a hybrid sunrise needs siddhantic.hybrid_sunrise_quantum")
        if intraday not in (LINEAR_GATI, FULL_EVALUATION):
            raise SuryaRefusal(f"intraday model {intraday!r}: {LINEAR_GATI} or {FULL_EVALUATION}")
        self.model = model
        self.observer = observer
        self.epoch = epoch
        self.sunrise_provider = sunrise_provider
        self.hybrid_quantum = hybrid_quantum
        self.intraday = intraday
        self.frame_id = f"text:{model.text}"
        self.standard = f"text_local:{model.text}"
        # iii.17b: the place's equinoctial shadow (refuses a latitude that is not a place)
        self._palabha = palabha(model.table, observer.latitude_degrees, model.gnomon)
        self._cara_flag = f"provisional:{model.data.key(CARA_GAP)}"
        data_flags = {f for r in model.data.used.values() for f in r.flags}
        hybrid = {"hybrid_sunrise:modern_geometric"} if sunrise_provider is not None else set()
        diagnostic = {f"diagnostic:{FULL_EVALUATION}"} if intraday == FULL_EVALUATION else set()
        self._flags = tuple(
            sorted(data_flags | set(observer.flags_for(model.text)) | hybrid | diagnostic)
        )
        self._memo: DayMemo[int, SuryaDay] = DayMemo()
        self._terms_memo: DayMemo[int, SuryaTerms] = DayMemo()

    # --- the protocol -----------------------------------------------------------

    @property
    def time_base(self) -> type:
        return Ahargana

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(
            bodies=tuple(self.model.planets),
            node=True,
            not_modelled={
                "latitude.sun": "the Sun has no latitude in the text (i.68–70 name the Moon "
                "and the five planets)",
                "tropical_longitude": "a siddhantic method has no tropical frame",
                "distance": "not modelled",
                "eclipses": "not modelled",
            },
        )

    def civil_day(self, jdn: JDN) -> CivilDayFrame[SiddhanticCivilInstant]:
        self._check_runs_from(jdn)
        day = self.day(jdn)
        sunrise = self.instant(jdn, Nadika(0))
        sunset: SiddhanticCivilInstant | NotModelled = NOT_MODELLED
        if day.sunset is not None:
            sunset = self.instant(jdn, day.sunset - day.sunrise)
        return CivilDayFrame(
            jdn=jdn,
            start=sunrise,
            end=self.instant(jdn.plus_days(1), Nadika(0)),
            sunrise=sunrise,
            sunset=sunset,
            sunrise_after_local_midnight=day.sunrise,
            meridian=f"{self.frame_id}+{self.observer.meridian_offset_ghatis}ghati",
            flags=day.flags,
            day_length_nadika=self.day_length(jdn),
        )

    def instant(self, jdn: JDN, after_start: Nadika) -> SiddhanticCivilInstant:
        return SiddhanticCivilInstant(jdn, after_start, self.standard)

    def sidereal_longitude(
        self, body: str, instant: SiddhanticCivilInstant
    ) -> SiderealLongitude[ExactArc]:
        if body not in self.model.planets:
            raise SuryaRefusal(f"{self.model.text} serves no body {body!r}")
        return self._longitude(self._position(body, instant))

    def tropical_longitude(
        self, body: str, instant: SiddhanticCivilInstant
    ) -> TropicalLongitude[TrueOfDate] | NotModelled:
        return NOT_MODELLED

    def daily_motion(self, body: str, day: JDN) -> ExactArc | NotModelled:
        if body not in self.model.planets:
            raise SuryaRefusal(f"{self.model.text} serves no body {body!r}")
        return ExactArc(self.gati(body, day), AngleUnit.DEGREE)

    def node(self, instant: SiddhanticCivilInstant) -> SiderealLongitude[ExactArc]:
        return self._longitude(self._position(None, instant))

    def latitude(self, body: str, instant: SiddhanticCivilInstant) -> ExactArc | NotModelled:
        """The latitude at the day's sunrise (ii.56–57), in degrees.

        The Sun's is not modelled, nor any body's at another instant of the
        day: the engine computes the latitude from the sunrise's mean places
        only, so a later instant gets ``not_modelled`` beside its longitude.
        """
        if body not in self.model.planets:
            raise SuryaRefusal(f"{self.model.text} serves no body {body!r}")
        p = self.model.planets[body]
        if p.node is None:
            return NOT_MODELLED
        if instant.standard != self.standard:  # as longitude does
            raise SuryaRefusal(f"instant of {instant.standard}, engine of {self.standard}")
        if instant.nadika_after_sunrise != Nadika(0):
            return NOT_MODELLED  # served at sunrise only (docstring)
        mean = self.day(instant.jdn).mean
        return ExactArc(self.model.latitude(p, mean) / MINUTES_PER_DEGREE, AngleUnit.DEGREE)

    # --- the day ------------------------------------------------------------------

    @property
    def runs_from(self) -> JDN:
        """The first civil day of the text's count on the era record."""
        return self.epoch

    @property
    def flags(self) -> tuple[str, ...]:
        """The flags every record of this engine carries (a day with a cara adds its gap's)."""
        return self._flags

    def _check_runs_from(self, jdn: JDN) -> None:
        if jdn.days_since(self.epoch) < 0:
            raise BeforeRunsFrom(
                f"JDN {jdn.value} is before runs_from (JDN {self.epoch.value}) of "
                f"{self.model.text}: the text's own count does not exist before it "
                ""
            )

    def _longitude(self, degrees: Fraction) -> SiderealLongitude[ExactArc]:
        return SiderealLongitude(ExactArc(degrees, AngleUnit.DEGREE), self.frame_id)

    def _position(self, body: str | None, instant: SiddhanticCivilInstant) -> Fraction:
        if instant.standard != self.standard:
            raise SuryaRefusal(f"instant of {instant.standard}, engine of {self.standard}")
        jdn, n = instant.jdn, instant.nadika_after_sunrise
        day = self.day(jdn)
        at_sunrise = day.node if body is None else day.true[body]
        if n == Nadika(0):
            return at_sunrise
        nadis = self.model.units.nadis_per_day
        if self.intraday == FULL_EVALUATION:
            if not 0 <= n.value < nadis:
                chord(at_sunrise, Fraction(0), n, nadis)  # the same refusal as the chord's
            node, true = self._evaluate(jdn, n.value / nadis)
            return node if body is None else true[body]
        gati = self.node_gati(jdn) if body is None else self.gati(body, jdn)
        return chord(at_sunrise, gati, n, nadis)

    def gati(self, body: str, jdn: JDN) -> Fraction:
        """The body's true daily motion at the day's sunrise (ii.47–51), in degrees a day."""
        return self.model.gati(self.model.planets[body], self.day(jdn).mean)

    def node_gati(self, jdn: JDN) -> Fraction:
        """The node's daily motion: its mean motion, retrograde (i.33, i.54)."""
        return self.model.elements.motion(self.model.node_element)

    def day_length(self, jdn: JDN) -> Nadika:
        """The interval from this sunrise to the next (``day_length_nadika``)."""
        nadis = Nadika(self.model.units.nadis_per_day)
        return nadis + self.day(jdn.plus_days(1)).sunrise - self.day(jdn).sunrise

    def _quarter(self) -> Fraction:
        """The observer's mean sunrise after its midnight, in days: a quarter day."""
        return SUNRISE_AFTER_MIDNIGHT

    def _desantara_days(self) -> Fraction:
        """The deśāntara as a time in days: the offset east in nāḍīs, subtracted (i.60–61, i.65)."""
        return -self.observer.meridian_offset_ghatis / self.model.units.nadis_per_day

    def _count(self, jdn: JDN) -> int:
        """The sum of days from creation at the prime meridian's midnight beginning ``jdn``."""
        return self.model.days_to_epoch + jdn.days_since(self.epoch)

    def _means_at(self, jdn: JDN, days: Fraction) -> dict[str, Fraction]:
        """Every mean element ``days`` after the count's midnight beginning ``jdn`` (i.53, i.67).

        At that midnight by the count, then carried at mean motion: the
        motion times the nāḍīs, divided by the nāḍīs of a day.
        """
        m = self.model
        count = Fraction(self._count(jdn))
        nadis = days * m.units.nadis_per_day
        mean: dict[str, Fraction] = {}
        for element in m.elements.revolutions:
            at_midnight = m.elements.mean(element, count)
            advance = m.elements.motion(element) * nadis / m.units.nadis_per_day
            mean[element] = (at_midnight + advance) % DEGREES_PER_REVOLUTION
        return mean

    def _bhujantara(self, p: Body, mean: Mapping[str, Fraction]) -> Fraction:
        """The bhujāntara of a body in degrees (ii.46)."""
        m = self.model
        return m.gati(p, mean) * m.bhujaphala_minutes(mean) / m.circle_minutes

    def _positions(
        self, mean: Mapping[str, Fraction], *, bhujantara: bool
    ) -> tuple[Fraction, dict[str, Fraction]]:
        m = self.model
        true: dict[str, Fraction] = {}
        for b, p in m.planets.items():
            t = m.true(p, mean)
            if bhujantara:
                t += self._bhujantara(p, mean)
            true[b] = t % DEGREES_PER_REVOLUTION
        return mean[m.node_element], true

    def _terms(self, jdn: JDN) -> SuryaTerms:
        """The day's sunrise terms from the Sun before the cara (ruling (h); iii.10)."""
        memo = self._terms_memo.get(jdn.value)
        if memo is not None:
            return memo
        m = self.model
        before = self._desantara_days() + self._quarter()
        mean = self._means_at(jdn, before)
        sun = m.planets["sun"]
        longitude = m.true(sun, mean) + self._bhujantara(sun, mean)
        ayana = m.ayana(self._count(jdn) + before)
        rsin_d = rsine_declination(
            m.table, m.rsin_obliquity, (longitude + ayana) % DEGREES_PER_REVOLUTION
        )
        cara = ascensional_difference_surya(m.table, rsin_d, self._palabha, m.gnomon)
        cara_days = -cara.cara_asus / m.time.asus_per_day
        nadis = m.units.nadis_per_day
        sunrise = Nadika((self._quarter() + cara_days) * nadis)
        h = half_day(cara.cara_asus, m.time)
        out = SuryaTerms(
            m.bhujaphala_minutes(mean),
            ayana,
            rsin_d,
            cara,
            cara_days,
            sunrise,
            sunrise + h + h,
            before + cara_days,
        )
        self._terms_memo[jdn.value] = out
        return out

    def _hybrid(self, jdn: JDN) -> tuple[Nadika, Fraction]:
        """A hybrid provider's sunrise, quantised, and the time of the means at it.

        The means are carried at mean motion from the count's midnight by the
        deśāntara and the provider's sunrise after the observer's midnight;
        the provider's instant stands for the text's bhujāntara and cara.
        """
        assert self.sunrise_provider is not None and self.hybrid_quantum is not None
        f = self.sunrise_provider.sunrise_fraction(jdn, self.observer)
        q = round_to(Fraction(f), self.hybrid_quantum, Rounding.HALF_EVEN)
        return Nadika(q * self.model.units.nadis_per_day), self._desantara_days() + q

    def _shift(self, jdn: JDN) -> Fraction:
        if self.sunrise_provider is not None:
            return self._hybrid(jdn)[1]
        return self._terms(jdn).shift_days

    def day(self, jdn: JDN) -> SuryaDay:
        """Every body's mean and true place at the text's sunrise of civil day ``jdn``."""
        self._check_runs_from(jdn)
        memo = self._memo.get(jdn.value)
        if memo is not None:
            return memo
        m = self.model
        since_kali = jdn.days_since(self.epoch)
        sun = m.elements
        years = _floor(
            sun.revolutions["sun"] * (since_kali + self._quarter()) / sun.civil_days["sun"]
        )
        terms: SuryaTerms | None = None
        sunset: Nadika | None = None
        flags = self._flags
        if self.sunrise_provider is not None:
            sunrise, shift = self._hybrid(jdn)
            assert self.hybrid_quantum is not None
            sunset = hybrid_nadikas(
                self.sunrise_provider.sunset_fraction(jdn, self.observer),
                self.hybrid_quantum,
                self.model.units.nadis_per_day,
            )
        else:
            terms = self._terms(jdn)
            sunrise, sunset, shift = terms.sunrise, terms.sunset, terms.shift_days
            if terms.cara_asus:
                flags = tuple(sorted({*flags, self._cara_flag}))
        mean = self._means_at(jdn, shift)
        node, true = self._positions(mean, bhujantara=terms is not None)
        out = SuryaDay(
            jdn,
            Ahargana(m.text, since_kali, Fraction(0)),
            self._count(jdn),
            years,
            {},
            mean,
            true,
            node,
            flags,
            sunrise,
            sunset,
            terms,
        )
        self._memo[jdn.value] = out
        return out

    def _evaluate(self, jdn: JDN, extra_days: Fraction) -> tuple[Fraction, dict[str, Fraction]]:
        """The full evaluation at a fractional day (diagnostic).

        The means advanced at mean motion by ``extra_days`` beyond the day's
        sunrise; the bhujāntara from those means.
        """
        mean = self._means_at(jdn, self._shift(jdn) + extra_days)
        return self._positions(mean, bhujantara=self.sunrise_provider is None)

    def evaluate(self, jdn: JDN, n: Nadika) -> tuple[Fraction, dict[str, Fraction]]:
        """The full evaluation *n* nāḍikās after sunrise ``jdn`` (any *n*; diagnostic)."""
        self._check_runs_from(jdn)
        return self._evaluate(jdn, n.value / self.model.units.nadis_per_day)
