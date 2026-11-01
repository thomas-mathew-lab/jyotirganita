"""Ending times and positions inside the civil day.

Each rule is a registered procedure (:mod:`jyotirganita.siddhantic.procedures`).
Arcs and motions are in degrees (a motion per day), instants in nāḍikās
after the day's sunrise.

- ``gati.sunrise_difference`` (laghubhaskariya_1963 II.15(ii); mahabhaskariya_1960 IV.18 the second
  witness): the true daily motion is the difference of the true
  longitudes computed for two consecutive sunrises, tomorrow's less
  today's (:func:`sunrise_difference`), reduced into (−180°, 180°].
- ``ending.proportional_parts`` (laghubhaskariya_1963 II.25–28; mahabhaskariya_1960 IV.31–34): the
  portion
  of the element still to be traversed, multiplied by 60 and divided by
  the motion, is the time to elapse after sunrise (:func:`proportional_parts`).
  For the yoga no text states a rule (laghubhaskariya_1963 II.29 is the vyatīpāta); its
  ending is the same rule on the sum of the longitudes and of the gatis,
  resting on ``texts.aryabhatiya.procedures.proportional_parts.yoga_note.laghubhaskariya_1963``
  (``basis: fallback_no_stated_rule``).
- ``intraday.linear_gati`` (laghubhaskariya_1963 II.25–26(i), the same rule): a position
  at *n* nāḍikās after sunrise is the sunrise position plus *n*/60 of the
  day's gati, on [0, 60) (:func:`chord`); the sliver from 60 nāḍikās to
  the next sunrise belongs to the seam rule (:func:`seam`).
- ``rounding.ending_truncate_at_asu`` (mahabhaskariya_1960 IV.31–32): the
  ending is stated in ghaṭīs, vighaṭīs and asus by successive division,
  each quotient kept (:func:`truncate_at_asu`). The exact ending is what
  the engine computes; the rounding gives the text's printed form.
- Diagnostics, not a text's procedure (registered ``reserved``):
  ``diagnostic.root_bisection``, the exact-root ending by bisection in
  exact arithmetic to the engine parameter ``siddhantic.root_resolution``
  (:func:`root_bisection`), paired with ``diagnostic.full_evaluation``,
  the text's full procedure at a fractional day (the engine).
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction

from jyotirganita.core.types import Nadika

__all__ = [
    "SeamRefusal",
    "chord",
    "proportional_parts",
    "root_bisection",
    "seam",
    "sunrise_difference",
    "truncate_at_asu",
]

DEGREES_PER_REVOLUTION = 360
DEGREES_PER_HALF_ORBIT = 180


class SeamRefusal(ValueError):
    """An instant at or beyond 60 nāḍikās after sunrise: the next day's chord answers it."""


def sunrise_difference(today: Fraction, tomorrow: Fraction) -> Fraction:
    """The gati: tomorrow's sunrise longitude less today's, in (−180°, 180°] (laghubhaskariya_1963
    II.15(ii))."""
    g = (tomorrow - today) % DEGREES_PER_REVOLUTION
    return g - DEGREES_PER_REVOLUTION if g > DEGREES_PER_HALF_ORBIT else g


def proportional_parts(remaining: Fraction, motion: Fraction, nadis_per_day: int) -> Nadika:
    """The ending: ``nadis_per_day`` × remaining arc ÷ motion nāḍikās after sunrise
    (laghubhaskariya_1963 II.25–28).

    A motion that is not positive has no ending (the element does not
    advance): a hard error, never a guess.
    """
    if motion <= 0:
        raise ValueError(f"the element's motion is {motion}°/day: no ending by proportional parts")
    return Nadika(nadis_per_day * remaining / motion)


def chord(at_sunrise: Fraction, gati: Fraction, n: Nadika, nadis_per_day: int) -> Fraction:
    """The position *n* nāḍikās after sunrise on the day's chord.

    The chord's domain is [0, 60) nāḍikās; an instant outside it is refused.
    """
    if not 0 <= n.value < nadis_per_day:
        raise SeamRefusal(
            f"{n.value} nāḍikās after sunrise is outside the day's chord [0, {nadis_per_day}): "
            "the seam rule gives it to the next day's computation"
        )
    return (at_sunrise + gati * n.value / nadis_per_day) % DEGREES_PER_REVOLUTION


def seam(at_chord_end: int, at_next_sunrise: int) -> bool:
    """Whether an element in force at the chord's end differs from the next sunrise's."""
    return at_chord_end != at_next_sunrise


def truncate_at_asu(n: Nadika, vighatis_per_ghati: int, asus_per_vighati: int) -> list[int]:
    """``[ghaṭī, vighaṭī, asu]`` by successive division, each quotient kept (mahabhaskariya_1960
    IV.31–32)."""
    if n.value < 0:
        raise ValueError("an ending after sunrise is not negative")
    g, r = divmod(n.value, 1)
    v, r = divmod(r * vighatis_per_ghati, 1)
    a = int(r * asus_per_vighati)
    return [int(g), int(v), a]


def root_bisection(
    crossed: Callable[[Fraction], bool], lo: Fraction, hi: Fraction, resolution: Fraction
) -> Fraction:
    """The least instant in (lo, hi] at which ``crossed`` holds, to ``resolution`` (exact).

    ``crossed(lo)`` must be false and ``crossed(hi)`` true, and ``crossed``
    must turn true once in the bracket and stay true (a predicate that turns
    back finds some crossing, not the first); the result is the upper end
    of the final bracket, so it is never before the crossing. The ends are
    taken as fractions, so an integer bracket stays exact.
    """
    lo, hi, resolution = Fraction(lo), Fraction(hi), Fraction(resolution)
    if resolution <= 0 or hi <= lo:
        raise ValueError("bisection needs lo < hi and a positive resolution")
    if crossed(lo) or not crossed(hi):
        raise ValueError("bisection needs crossed(lo) false and crossed(hi) true")
    while hi - lo > resolution:
        mid = (lo + hi) / 2
        if crossed(mid):
            hi = mid
        else:
            lo = mid
    return hi
