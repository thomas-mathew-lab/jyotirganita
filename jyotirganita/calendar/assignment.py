"""Assignment rules and kṣaya/vṛddhi flags.

A civil day is cut by an element's endings into occurrences
(:class:`Occurrence`, built by ``calendar/occurrences.py``): the element in
force at the day's start, then each successor, the last running past the
day's end. An **assignment rule** chooses the one label that names the
day; each is a registered function (:data:`ASSIGNMENT_RULES`) with its
citation:

- ``at_sunrise``: the element in force at the start of the civil day, which
  begins at sunrise (sewell_dikshit_1896 Art. 31: "the tithi current at sunrise of the
  solar day gives its name and numeral to that day";
  ``regions.kerala.conventions.assignment.at_sunrise.sewell_dikshit_1896``);
- ``udaya_vyapini``: the element in force at the day's sunrise, wherever
  the civil day begins (the same as ``at_sunrise`` under a sunrise civil
  day; it differs under a midnight civil day, modern engine);
- ``at_midnight``: the element in force at local midnight (modern engine
  only: the siddhantic frame states no midnight and the
  rule raises :class:`NotModelledRule`);
- ``predominant``: the element in force over the longest part of the
  civil day (an earlier occurrence wins a tie);
- ``at_custom_time``: the element in force at a caller-named time after
  the day's start.

**Kṣaya and vṛddhi** (sewell_dikshit_1896 Art. 32: "A tithi on which the sun does not rise
is expunged", "a tithi on which the sun rises twice is repeated";
``regions.kerala.conventions.ksaya.sewell_dikshit_1896``, ``.vrddhi.sewell_dikshit_1896``) are read
from
consecutive assigned labels only (:func:`ksaya_vrddhi`): a label skipped
between day *d* and day *d* + 1 is ``kshaya:<element>.<index>`` on day
*d*; a label equal to the previous day's is ``vriddhi:<element>.<index>``
on day *d*. A day's flags depend on days *d* − 1, *d* and *d* + 1 alone,
so they do not depend on the range a caller asks for.

Integers and fractions only.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from jyotirganita.core.types import Nadika

__all__ = [
    "ASSIGNMENT_RULES",
    "AssignmentRule",
    "DayPoints",
    "NotModelledRule",
    "Occurrence",
    "assign",
    "ksaya_vrddhi",
    "label_at",
]


class NotModelledRule(ValueError):
    """A rule that needs an instant the engine's civil-day frame does not state."""


@dataclass(frozen=True, slots=True)
class Occurrence:
    """One element in force during a civil day.

    ``index`` is the element's 1-based index; ``start`` and ``end`` are
    nāḍikās after the civil day's start, ``None`` where the occurrence began
    before the day or ends after it; ``ends_after_start`` is its ending
    after the day's start as the method computes it (the record's
    ``ends_nadika_after_sunrise``, which may exceed the day's length).
    """

    index: int
    start: Nadika | None
    end: Nadika | None
    ends_after_start: Nadika


@dataclass(frozen=True, slots=True)
class DayPoints:
    """The instants of a civil day the rules read, in nāḍikās after its start."""

    length: Nadika
    sunrise: Nadika | None
    midnight: Nadika | None = None
    custom: Nadika | None = None


def label_at(occurrences: Sequence[Occurrence], t: Nadika) -> int:
    """The index of the occurrence in force ``t`` after the day's start (``0 ≤ t < length``)."""
    for o in occurrences:
        if o.end is None or t < o.end:
            return o.index
    raise ValueError(f"no occurrence covers {t}")  # pragma: no cover - the last is open


def _at_sunrise(occ: Sequence[Occurrence], points: DayPoints) -> int:
    return occ[0].index


def _udaya_vyapini(occ: Sequence[Occurrence], points: DayPoints) -> int:
    if points.sunrise is None:
        raise NotModelledRule("udaya_vyapini needs the day's sunrise")
    return label_at(occ, points.sunrise)


def _at_midnight(occ: Sequence[Occurrence], points: DayPoints) -> int:
    if points.midnight is None:
        raise NotModelledRule(
            "at_midnight is served by the modern engine only: the "
            "siddhantic civil-day frame states no midnight"
        )
    return label_at(occ, points.midnight)


def _predominant(occ: Sequence[Occurrence], points: DayPoints) -> int:
    best, longest = occ[0].index, Nadika(0) - Nadika(1)
    for o in occ:
        lo = Nadika(0) if o.start is None else o.start
        hi = points.length if o.end is None else o.end
        if longest < hi - lo:
            best, longest = o.index, hi - lo
    return best


def _at_custom_time(occ: Sequence[Occurrence], points: DayPoints) -> int:
    if points.custom is None:
        raise ValueError("at_custom_time needs the caller's time after the day's start")
    return label_at(occ, points.custom)


@dataclass(frozen=True, slots=True)
class AssignmentRule:
    """A registered assignment rule: its function and citation."""

    name: str
    fn: Callable[[Sequence[Occurrence], DayPoints], int]
    citation: str


ASSIGNMENT_RULES: Mapping[str, AssignmentRule] = {
    r.name: r
    for r in (
        AssignmentRule(
            "at_sunrise",
            _at_sunrise,
            "sewell_dikshit_1896 Art. 31 "
            "(regions.kerala.conventions.assignment.at_sunrise.sewell_dikshit_1896)",
        ),
        AssignmentRule(
            "udaya_vyapini",
            _udaya_vyapini,
            "the element prevailing at sunrise, under any civil-day start",
        ),
        AssignmentRule("at_midnight", _at_midnight, "modern engine only"),
        AssignmentRule(
            "predominant",
            _predominant,
            "the element in force over the longest part of the day",
        ),
        AssignmentRule(
            "at_custom_time",
            _at_custom_time,
            "the element in force at a caller-named time",
        ),
    )
}


def assign(rule: str, occurrences: Sequence[Occurrence], points: DayPoints) -> int:
    """The label ``rule`` assigns to the day."""
    r = ASSIGNMENT_RULES.get(rule)
    if r is None:
        raise KeyError(f"no assignment rule {rule!r} ({sorted(ASSIGNMENT_RULES)})")
    return r.fn(occurrences, points)


def ksaya_vrddhi(
    element: str, count: int, previous: int | None, today: int, following: int | None
) -> tuple[str, ...]:
    """The kṣaya and vṛddhi flags of a day from its own and its neighbours' labels."""
    flags: list[str] = []
    if previous is not None and previous == today:
        flags.append(f"vriddhi:{element}.{today}")
    if following is not None:
        step = (following - today) % count
        for k in range(1, step):
            flags.append(f"kshaya:{element}.{(today - 1 + k) % count + 1}")
    return tuple(flags)
