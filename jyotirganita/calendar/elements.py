"""The element definitions (fixed mathematics).

With sidereal longitudes λ☾, λ☉ and Δ = λ☾ − λ☉ mod 360°:

- tithi = ⌊Δ/12°⌋ + 1 (30 to a circle of elongation);
- karaṇa = ⌊Δ/6°⌋ + 1 (60 to a circle; the name cycle is the regional profile's);
- nakṣatra = ⌊λ☾/(360°/27)⌋ + 1;
- yoga = ⌊((λ☾ + λ☉) mod 360°)/(360°/27)⌋ + 1;
- rāśi = ⌊λ☉/30°⌋ + 1.

Each element is an arc of the circle cut into equal spans; :func:`index`
is the 1-based span the arc lies in and :func:`remaining` the arc left to
the span's end, in (0, span]. :func:`motion` is the motion of the
element's arc as the proportional parts use it:
the Moon's less the Sun's for tithi and karaṇa, the Moon's alone for
nakṣatra, the sum for yoga, the Sun's for the rāśi.

Generic over the numeric family (``ExactArc`` or ``FloatArc``); under the
siddhantic family the floors are exact. Integers and fractions only: no
``math``, ``numpy`` or ``decimal`` import. The calendar layer
calls it and adds nothing to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from jyotirganita.core.types import AngleUnit, ExactArc, FloatArc

__all__ = ["ELEMENTS", "Element", "Of", "arc", "index", "motion", "remaining", "span"]

DEGREES_PER_REVOLUTION = 360


class Of(Enum):
    """What an element's arc is measured on."""

    ELONGATION = "elongation"  # Moon − Sun
    MOON = "moon"
    SUM = "sum"  # Moon + Sun
    SUN = "sun"


@dataclass(frozen=True, slots=True)
class Element:
    """An element: its id, the number of equal spans to a circle and the arc it is measured on."""

    id: str
    count: int
    of: Of


TITHI = Element("tithi", 30, Of.ELONGATION)
KARANA = Element("karana", 60, Of.ELONGATION)
NAKSATRA = Element("nakshatra", 27, Of.MOON)
YOGA = Element("yoga", 27, Of.SUM)
RASI = Element("rasi", 12, Of.SUN)

#: the day's elements, by id
ELEMENTS: dict[str, Element] = {e.id: e for e in (TITHI, KARANA, NAKSATRA, YOGA, RASI)}


def _circle[A: (ExactArc, FloatArc)](like: A) -> A:
    return type(like).of_int(DEGREES_PER_REVOLUTION, AngleUnit.DEGREE)


def _reduce[A: (ExactArc, FloatArc)](a: A) -> A:
    return a.to(AngleUnit.DEGREE).mod_arc(_circle(a))


def arc[A: (ExactArc, FloatArc)](e: Element, sun: A, moon: A) -> A:
    """The element's arc in [0°, 360°): Δ, λ☾, λ☾ + λ☉ or λ☉."""
    if e.of is Of.ELONGATION:
        return _reduce(moon - sun)
    if e.of is Of.MOON:
        return _reduce(moon)
    if e.of is Of.SUM:
        return _reduce(moon + sun)
    return _reduce(sun)


def span[A: (ExactArc, FloatArc)](e: Element, like: A) -> A:
    """One span of the element: 360° divided by its count."""
    return _circle(like) / e.count


def index[A: (ExactArc, FloatArc)](e: Element, sun: A, moon: A) -> int:
    """The element's 1-based index: the floor of its arc over one span, plus one."""
    return arc(e, sun, moon).scaled(e.count).floordiv_arc(_circle(sun)) + 1


def remaining[A: (ExactArc, FloatArc)](e: Element, sun: A, moon: A) -> A:
    """The arc left to the end of the current span, in (0, span]."""
    return span(e, sun).scaled(index(e, sun, moon)) - arc(e, sun, moon)


def motion[A: (ExactArc, FloatArc)](e: Element, sun_motion: A, moon_motion: A) -> A:
    """The daily motion of the element's arc."""
    if e.of is Of.ELONGATION:
        return moon_motion - sun_motion
    if e.of is Of.MOON:
        return moon_motion
    if e.of is Of.SUM:
        return moon_motion + sun_motion
    return sun_motion
