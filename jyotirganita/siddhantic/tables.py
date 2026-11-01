"""The Rsine table and its interpolation.

A text's Rsine table is a datum: the Āryabhaṭīya's 24 Rsine-differences of
Gītikā 12 (``texts.aryabhatiya.trig.rsine_differences.d01`` … ``d24``),
tabulated at intervals of ``interval`` minutes of arc
(``texts.aryabhatiya.procedures.rsine.interval_minutes``). The radius is
the sum of the differences (the Rsine of a quadrant); it is derived, not
keyed.

The rules, as laghubhaskariya_1963 II.2(ii)–3(i) and mahabhaskariya_1960 IV.3–4(i) state them:

- **Rsine** of an arc (in minutes): divide by the interval; take the sum of
  as many differences as the quotient; multiply the remainder by the next
  ("current") difference, divide by the interval and add
  (:meth:`RsineTable.rsine`, procedure ``trig.rsine_table_linear``);
- **Rversed-sine**: the same rule on the table reversed (mahabhaskariya_1960 IV.3–4,
  Shukla's note p. 108: "the same table reversed becomes the table of
  Rversed-sine-differences"; :meth:`RsineTable.rversine`);
- **arc from a Rsine** (mahabhaskariya_1960 VIII.6): subtract the differences in order as
  far as possible, multiply their number by the interval, multiply the
  residue by the interval, divide by the current difference and add
  (:meth:`RsineTable.arc`, procedure ``trig.arc_table_linear``).

Everything is exact: the division by the interval or by a difference is a
``Fraction``; the texts state no rounding inside the rule, and none is made.

A table may also be given by its Rsines (:meth:`RsineTable.of_sines`): the
Dṛk line's, grahanamandana_1965 śl. 25A–B
(``texts.drgganita.trig.rsine_table.quoted.grahanamandana_1965.e01``
… ``e24``), whose interval is the quadrant divided by the count of its
entries. **The tabular Rsines by computation** (golasara_1970 III.13b–14a, procedure
``trig.rsine_recursion_backward``; :func:`rsines_by_recursion`): from the
radius and the Rsine below it, each Rsine times ``multiplier`` (twice) the
last difference divided by the radius, plus the difference that gave it, is
the difference to the Rsine before it. Run on the editor's inputs it is a
cross-check of a table, never a table the engine runs on.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

MINUTES_PER_DEGREE = 60
DEGREES_PER_QUADRANT = 90

__all__ = ["RsineTable", "recursion_difference", "rsines_by_recursion"]


@dataclass(frozen=True, slots=True)
class RsineTable:
    """A table of Rsine-differences at a fixed interval (arcs and Rsines in minutes)."""

    interval: int
    differences: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.interval <= 0 or not self.differences:
            raise ValueError("a Rsine table has a positive interval and at least one difference")
        if any(d <= 0 for d in self.differences):
            raise ValueError("Rsine-differences are positive")

    @classmethod
    def of(cls, interval: int, differences: Sequence[int]) -> RsineTable:
        """The table of ``differences`` at ``interval`` minutes."""
        return cls(interval, tuple(differences))

    @classmethod
    def of_sines(cls, sines: Sequence[int]) -> RsineTable:
        """The table whose Rsines at each step of a quadrant are ``sines`` (the last the radius).

        The interval is the quadrant in minutes divided by the count of the
        Rsines; a count that does not divide it is refused.
        """
        if not sines:
            raise ValueError("a Rsine table has at least one Rsine")
        interval, rest = divmod(DEGREES_PER_QUADRANT * MINUTES_PER_DEGREE, len(sines))
        if rest:
            raise ValueError(f"{len(sines)} Rsines do not divide a quadrant into whole minutes")
        return cls(interval, tuple(b - a for a, b in zip((0, *sines[:-1]), sines, strict=True)))

    @property
    def radius(self) -> int:
        """The Rsine of a quadrant: the sum of the differences."""
        return sum(self.differences)

    @property
    def quadrant(self) -> int:
        """A quadrant in minutes of arc: the interval times the number of differences."""
        return self.interval * len(self.differences)

    def _check_arc(self, arc: Fraction) -> None:
        if not 0 <= arc <= self.quadrant:
            raise ValueError(f"arc {arc}′ is outside the quadrant [0, {self.quadrant}′]")

    def _interpolate(self, table: Sequence[int], arc: Fraction) -> Fraction:
        self._check_arc(arc)
        q, r = divmod(arc, self.interval)
        whole = int(q)
        total = Fraction(sum(table[:whole]))
        if r:
            total += r * table[whole] / self.interval
        return total

    def rsine(self, arc: Fraction | int) -> Fraction:
        """The Rsine of ``arc`` minutes, ``0 ≤ arc ≤`` a quadrant (laghubhaskariya_1963
        II.2(ii)–3(i))."""
        return self._interpolate(self.differences, Fraction(arc))

    def rversine(self, arc: Fraction | int) -> Fraction:
        """The Rversed-sine of ``arc`` minutes, by the reversed table (mahabhaskariya_1960
        IV.3–4)."""
        return self._interpolate(self.differences[::-1], Fraction(arc))

    def arc(self, rsine: Fraction | int) -> Fraction:
        """The arc in minutes whose Rsine is ``rsine``, ``0 ≤ rsine ≤`` radius (mahabhaskariya_1960
        VIII.6)."""
        s = Fraction(rsine)
        if not 0 <= s <= self.radius:
            raise ValueError(f"Rsine {s} is outside [0, {self.radius}]")
        k = 0
        while k < len(self.differences) and s >= self.differences[k]:
            s -= self.differences[k]
            k += 1
        out = Fraction(k * self.interval)
        if s:
            out += s * self.interval / self.differences[k]
        return out


def recursion_difference(
    rsine: Fraction,
    last_difference: Fraction,
    radius: Fraction,
    difference: Fraction,
    multiplier: int,
) -> Fraction:
    """The difference to the Rsine before ``rsine`` (golasara_1970 III.13b–14a).

    ``rsine`` × ``multiplier`` × ``last_difference`` ÷ ``radius`` plus
    ``difference``, the difference by which ``rsine`` was found.
    """
    return rsine * multiplier * last_difference / radius + difference


def rsines_by_recursion(
    radius: Fraction, below_radius: Fraction, count: int, multiplier: int
) -> tuple[Fraction, ...]:
    """The ``count`` Rsines of a quadrant by golasara_1970 III.13b–14a, the first first.

    ``below_radius`` is the Rsine before the radius (the editor's note: the
    Rcosine of the first Rsine); the last difference is the radius less it.
    Exact; no rounding is stated.
    """
    if count < 2:
        raise ValueError("the recursion starts from the radius and the Rsine below it")
    last = Fraction(radius) - below_radius
    sines = [Fraction(radius), Fraction(below_radius)]
    difference = last
    while len(sines) < count:
        difference = recursion_difference(sines[-1], last, radius, difference, multiplier)
        sines.append(sines[-1] - difference)
    return tuple(reversed(sines))
