"""Epicycle corrections with the Āryabhaṭan pulsating epicycle.

Every rule here is a registered procedure (:mod:`jyotirganita.siddhantic.procedures`)
whose datum in the text's ``procedures.yaml`` states it and cites the page.
Arcs and Rsines are in minutes, longitudes and kendras in degrees; all
arithmetic is exact except the root of the śīghrakarṇa (below).

- ``epicycle.bhuja_koti`` (laghubhaskariya_1963 II.1–2(i), ``...bhuja_koti.rule``): three
  signs make a quadrant; in an odd quadrant the arc traversed is the bhujā
  and the arc to be traversed the koṭi, in an even quadrant the reverse
  (:func:`bhuja_koti`). The decomposition of a kendra into the parts lying
  in successive quadrants (mahabhaskariya_1960 IV, Shukla's note; fixture
  ``authority/aryabhatiya/mahabhaskariya_1960_ch4_anomaly_quadrant_example``) is
  :func:`quadrant_parts`.
- ``epicycle.pulsating`` (laghubhaskariya_1963 II.31–32, ``...quadrant_convention.rule``;
  mahabhaskariya_1960
  IV.38–39(i) the second witness): the epicycles stated for the beginnings
  of the odd and even quadrants are corrected for the part of the kendra
  in the current quadrant, by its Rsine in an odd quadrant and its
  Rversed-sine in an even one, times the difference of the two epicycles,
  divided by the radius; the result is added to the epicycle at the
  beginning of the current quadrant if that is the smaller, subtracted if
  the greater (:func:`corrected_epicycle`). An element with one stated
  epicycle (the Sun's, the Moon's) keeps it.
- ``epicycle.manda_bhujaphala`` (laghubhaskariya_1963 II.3(ii)–4(i), ``...manda.bhujaphala_rule``):
  the Rsine of the bhujā times the epicycle divided by the divisor
  (``...manda.epicycle_divisor``); subtractive while the kendra lies in the
  half-orbit beginning with Aries, additive in that beginning with Libra
  (``...manda.sign_rule``) (:func:`manda_correction`). For the Sun and the
  Moon the bhujāphala is applied as it is (laghubhaskariya_1963 II.4(i), II.23–24); for the
  planets it is "reduced to arc" (laghubhaskariya_1963 II.33–37(i)) with ``arc=True``.
- ``epicycle.sighra`` (laghubhaskariya_1963 II.33–37(i)): the śīghrakendra is the śīghrocca
  less the planet; its bāhuphala and koṭiphala as above; the śīghrakarṇa is
  the root of the square of the radius plus or minus the koṭiphala (plus in
  the first and fourth quadrants, ``...application_order.sighrakarna_sign``)
  and the square of the bāhuphala; the bāhuphala times the radius divided
  by the karṇa, reduced to arc, is the correction, additive while the
  śīghrakendra lies in the half-orbit beginning with Aries
  (:func:`sighra_correction`). The texts state no rule for the root's
  precision: the karṇa is the exact root truncated at the engine parameter
  ``siddhantic.karna_root_resolution``, the one place this
  engine leaves the rationals.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from jyotirganita.siddhantic.tables import RsineTable

__all__ = [
    "Epicycle",
    "bhuja_koti",
    "corrected_epicycle",
    "karna",
    "manda_correction",
    "quadrant_parts",
    "sighra_correction",
]

DEGREES_PER_QUADRANT = 90
DEGREES_PER_HALF_ORBIT = 180
DEGREES_PER_REVOLUTION = 360
MINUTES_PER_DEGREE = 60


@dataclass(frozen=True, slots=True)
class Epicycle:
    """The epicycles at the beginnings of the odd and even quadrants (equal: no pulsation)."""

    odd: Fraction
    even: Fraction


def _reduce(degrees: Fraction) -> Fraction:
    return degrees % DEGREES_PER_REVOLUTION


def quadrant_parts(kendra: Fraction) -> list[tuple[str, Fraction]]:
    """The parts of ``kendra`` (degrees) in successive quadrants: Rsine in odd, Rversine in even."""
    k = _reduce(kendra)
    out: list[tuple[str, Fraction]] = []
    quadrant = 0
    while k > 0:
        part = min(k, Fraction(DEGREES_PER_QUADRANT))
        out.append(("rsine" if quadrant % 2 == 0 else "rversine", part))
        k -= part
        quadrant += 1
    return out


def bhuja_koti(kendra: Fraction) -> tuple[int, Fraction, Fraction, Fraction]:
    """``(quadrant 1–4, part traversed, bhujā, koṭi)`` of ``kendra`` in degrees
    (laghubhaskariya_1963 II.1–2)."""
    k = _reduce(kendra)
    index, traversed = divmod(k, DEGREES_PER_QUADRANT)
    quadrant = int(index) + 1
    to_go = DEGREES_PER_QUADRANT - traversed
    if quadrant % 2 == 1:
        return quadrant, traversed, traversed, to_go
    return quadrant, traversed, to_go, traversed


def corrected_epicycle(e: Epicycle, kendra: Fraction, table: RsineTable) -> Fraction:
    """The pulsating epicycle at ``kendra`` (laghubhaskariya_1963 II.31–32)."""
    if e.odd == e.even:
        return e.odd
    quadrant, traversed, _, _ = bhuja_koti(kendra)
    odd = quadrant % 2 == 1
    begin, other = (e.odd, e.even) if odd else (e.even, e.odd)
    minutes = traversed * MINUTES_PER_DEGREE
    factor = table.rsine(minutes) if odd else table.rversine(minutes)
    change = factor * abs(e.odd - e.even) / table.radius
    return begin + change if begin < other else begin - change


def manda_correction(
    e: Epicycle,
    kendra: Fraction,
    table: RsineTable,
    divisor: int,
    *,
    arc: bool,
) -> Fraction:
    """The signed manda correction in degrees at ``kendra`` (laghubhaskariya_1963 II.3(ii)–4(i),
    II.33–37)."""
    epicycle = corrected_epicycle(e, kendra, table)
    _, _, bhuja, _ = bhuja_koti(kendra)
    phala = table.rsine(bhuja * MINUTES_PER_DEGREE) * epicycle / divisor
    if arc:
        phala = table.arc(phala)
    degrees = phala / MINUTES_PER_DEGREE
    return -degrees if _reduce(kendra) < DEGREES_PER_HALF_ORBIT else degrees


def _integer_root(n: int) -> int:
    """The greatest integer whose square does not exceed ``n`` (Newton's iteration on integers)."""
    if n < 2:
        return n
    x = 1 << ((n.bit_length() + 1) // 2)
    while True:
        y = (x + n // x) // 2
        if y >= x:
            return x
        x = y


def karna(square: Fraction, resolution: Fraction) -> Fraction:
    """The root of ``square`` truncated at ``resolution``: an integer square root, exact."""
    if square < 0 or resolution <= 0:
        raise ValueError("karna takes a non-negative square and a positive resolution")
    scaled = square / (resolution * resolution)
    return _integer_root(scaled.numerator // scaled.denominator) * resolution


def sighra_correction(
    e: Epicycle,
    kendra: Fraction,
    table: RsineTable,
    divisor: int,
    resolution: Fraction,
) -> Fraction:
    """The signed śīghra correction in degrees at the śīghrakendra ``kendra`` (laghubhaskariya_1963
    II.33–37)."""
    epicycle = corrected_epicycle(e, kendra, table)
    quadrant, _, bhuja, koti = bhuja_koti(kendra)
    bahu = table.rsine(bhuja * MINUTES_PER_DEGREE) * epicycle / divisor
    kotiphala = table.rsine(koti * MINUTES_PER_DEGREE) * epicycle / divisor
    radius = table.radius
    base = radius + kotiphala if quadrant in (1, 4) else radius - kotiphala
    square = base * base + bahu * bahu
    h = karna(square, resolution)
    if square and not h:
        # a root truncated to nothing hides the correction
        raise ValueError(f"śīghrakarṇa: the root of {square} truncates to 0 at {resolution}")
    phala = table.arc(bahu * radius / h) if h else Fraction(0)
    degrees = phala / MINUTES_PER_DEGREE
    return degrees if _reduce(kendra) < DEGREES_PER_HALF_ORBIT else -degrees
