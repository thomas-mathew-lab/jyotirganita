"""Ending encodings.

An element's ending is computed as nāḍikās after the civil day's start
(the text's sunrise under every siddhantic method). An almanac prints it
in one of these encodings, each a registered option of the profile's
``encodings.ending`` and pinned by a printed example:

- **unit** ``nadika``: the fixed nāḍikā (nāzhika), a sixtieth of the civil
  day; ``ghatika_variable``: a sixtieth of the day's
  own length from sunrise to the next sunrise; ``hours``: twenty-four to
  the civil day, sixty minutes to the hour;
- **direction** ``elapsed``: from the reference to the ending;
  ``remaining``: from the ending to the end of the civil day (the next
  day's reference), the complement within the day;
- **reference** ``sunrise``, or ``midnight``: local mean midnight, the
  day's sunrise after midnight added.

:func:`sexagesimal` splits a value into its whole units and sixtieths
(ghaṭikās and palas, hours and minutes) without rounding; an almanac's
rounding is its own datum and is applied by the caller. :func:`clock`
gives a clock reading from hours after midnight.

Integers and fractions only.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Literal

from jyotirganita.core.types import Nadika

__all__ = ["DIRECTIONS", "REFERENCES", "UNITS", "clock", "encode_ending", "sexagesimal"]

type Unit = Literal["nadika", "ghatika_variable", "hours"]
type Direction = Literal["elapsed", "remaining"]
type Reference = Literal["sunrise", "midnight"]

UNITS: tuple[Unit, ...] = ("nadika", "ghatika_variable", "hours")
DIRECTIONS: tuple[Direction, ...] = ("elapsed", "remaining")
REFERENCES: tuple[Reference, ...] = ("sunrise", "midnight")

NADIKAS_PER_DAY = 60
HOURS_PER_DAY = 24
SIXTY = 60
HALF_DAY_HOURS = 12


def encode_ending(
    ending: Nadika,
    *,
    unit: Unit,
    direction: Direction,
    reference: Reference,
    day_length: Nadika,
    sunrise_after_midnight: Nadika | None = None,
) -> Fraction:
    """The ending, given in nāḍikās after the day's sunrise, in the named encoding (exact)."""
    if not isinstance(ending, Nadika) or not isinstance(day_length, Nadika):
        raise TypeError("an ending and a day length are Nadika")
    if reference == "midnight":
        if sunrise_after_midnight is None:
            raise ValueError("a midnight reference needs the day's sunrise after midnight")
        start = sunrise_after_midnight
    elif reference == "sunrise":
        start = Nadika(0)
    else:
        raise ValueError(f"no reference {reference!r} ({REFERENCES})")
    if direction == "elapsed":
        n = start + ending
    elif direction == "remaining":
        n = day_length - ending
    else:
        raise ValueError(f"no direction {direction!r} ({DIRECTIONS})")
    if unit == "nadika":
        return n.value
    if unit == "ghatika_variable":
        return n.value * NADIKAS_PER_DAY / day_length.value
    if unit == "hours":
        return n.value * HOURS_PER_DAY / NADIKAS_PER_DAY
    raise ValueError(f"no unit {unit!r} ({UNITS})")


def sexagesimal(value: Fraction) -> tuple[int, Fraction]:
    """``value`` (≥ 0) as whole units and the remaining sixtieths, unrounded."""
    if value < 0:
        raise ValueError("a printed ending is not negative")
    whole = value.numerator // value.denominator
    return whole, (value - whole) * SIXTY


def clock(hours_after_midnight: Fraction) -> tuple[int, Fraction, str]:
    """A twelve-hour clock reading: hour (1–12), minutes, ``a.m.`` or ``p.m.``."""
    h = hours_after_midnight % HOURS_PER_DAY
    half = "a.m." if h < HALF_DAY_HOURS else "p.m."
    whole, minutes = sexagesimal(h)
    hour = whole % HALF_DAY_HOURS or HALF_DAY_HOURS
    return hour, minutes, half
