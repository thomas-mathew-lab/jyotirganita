"""Mean positions from yuga revolutions.

Procedure ``mean.yuga_rate_successive_division``, laghubhaskariya_1963 I.15–17(i)
(``texts.aryabhatiya.procedures.mean_longitude.rule``; mahabhaskariya_1960 I the second
witness): the revolutions of an element in a yuga times the ahargaṇa,
divided by the civil days of a yuga, give the revolutions performed; the
successive remainders times 12, 30 and 60, divided by the same divisor,
give the signs, degrees and minutes "and so on", "up to seconds of arc"
(``...mean_longitude.precision``, procedure ``rounding.truncate_at_vikala``).
Successive division keeps each quotient and carries the remainder, so the
longitude is the exact one truncated at the vikalā; :func:`mean_longitude`
returns both the truncated value the rule produces and the exact residue
the mahabhaskariya_1960 problems work with.

The epoch additives of the Moon's apogee and node (laghubhaskariya_1963 I.17(ii–iv),
procedure ``mean.moon_apogee_node_additive``): three signs added to the
apogee; six signs added to the node and the result subtracted from a
circle, the node moving westward.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from jyotirganita.core.exact import Rounding, round_to

__all__ = [
    "MeanLongitude",
    "mean_daily_motion",
    "mean_longitude",
    "node_from_mean",
]

DEGREES_PER_REVOLUTION = 360
DEGREES_PER_SIGN = 30
ARCSECONDS_PER_DEGREE = 3600


@dataclass(frozen=True, slots=True)
class MeanLongitude:
    """A mean longitude by successive division.

    ``revolutions`` completed, ``degrees`` the longitude truncated at the
    vikalā (``[0, 360)``), and ``exact`` the untruncated longitude in degrees.
    """

    revolutions: int
    degrees: Fraction
    exact: Fraction


def mean_longitude(
    revolutions_per_yuga: int, civil_days_per_yuga: int, ahargana: int | Fraction
) -> MeanLongitude:
    """The mean longitude at the sunrise ``ahargana`` days after the epoch (laghubhaskariya_1963
    I.15–17)."""
    q, r = divmod(revolutions_per_yuga * ahargana, civil_days_per_yuga)
    exact = Fraction(r * DEGREES_PER_REVOLUTION, civil_days_per_yuga)
    truncated = round_to(exact, Fraction(1, ARCSECONDS_PER_DEGREE), Rounding.TRUNCATE)
    return MeanLongitude(q, truncated, exact)


def mean_daily_motion(revolutions_per_yuga: int, civil_days_per_yuga: int) -> Fraction:
    """The mean daily motion in degrees per civil day: revolutions × 360 ÷ civil days."""
    return Fraction(revolutions_per_yuga * DEGREES_PER_REVOLUTION, civil_days_per_yuga)


def node_from_mean(mean_degrees: Fraction, additive_signs: int) -> Fraction:
    """The node's longitude: add the additive signs and subtract from a circle (laghubhaskariya_1963
    I.17)."""
    return (-(mean_degrees + additive_signs * DEGREES_PER_SIGN)) % DEGREES_PER_REVOLUTION
