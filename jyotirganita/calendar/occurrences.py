"""Element streams over the engine.

An :class:`ElementSource` gives, for one civil day, what the calendar
layer reads (:class:`SourceDay`): the day's length to the next day's
start, its sunrise, sunset and midnight after its start where the engine
states them, each element's index at the day's start
(``calendar/elements.py``), its first ending after the start by the
method's procedure, and the time one span of the element takes at the
day's motion. :func:`day_occurrences` cuts the day into the element's
occurrences (``calendar/assignment.py``): the successive endings are
``e₁ + (k − 1) × nāḍikās per span``, a linear chord,
and the last occurrence runs past the day's end, or past the chord's end
(``SourceDay.chord_end``) where the day is longer than the chord.

:class:`SiddhanticSource` serves a siddhantic method run
(``methods/compose.py``): the civil day starts at the text's sunrise, the
endings are the method's proportional parts (laghubhaskariya_1963 II.25–28; the yoga's on
the fallback datum) and the rāśi's the same rule on the
Sun's arc and gati (the saṅkrānti); midnight is not stated. The modern source is
``modern/source.py``: its endings
are roots, every one in the day (``SourceDay.ending_list``).

The karaṇa names are the profile's: ``regions/base.py`` resolves them from
the profile's ``karana_cycle`` datum (sewell_dikshit_1896 Table VIII for Kerala).

Integers and fractions only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from jyotirganita.calendar import elements
from jyotirganita.calendar.assignment import Occurrence
from jyotirganita.core.calendar import Weekday
from jyotirganita.core.memo import DayMemo
from jyotirganita.core.types import JDN, AngleUnit, ExactArc, Nadika
from jyotirganita.siddhantic.endings import proportional_parts

if TYPE_CHECKING:
    from jyotirganita.methods.compose import MethodRun

__all__ = [
    "ElementSource",
    "SiddhanticSource",
    "SourceDay",
    "day_occurrences",
    "sankranti_in_day",
    "tithi_name_index",
]

#: the tithis of a pakṣa (thirty to the synodic month)
TITHIS_PER_PAKSA = 15


@dataclass(frozen=True, slots=True)
class SourceDay:
    """One civil day as the calendar layer reads it; times in nāḍikās after its start.

    ``sunrise_after_midnight`` is the sunrise after local mean midnight
    where the engine states it; ``weekday`` the method's
    own (laghubhaskariya_1963 I.8 under the siddhantic engine); ``ahargana`` the method's
    day count where it has one. ``ending_list``, where the engine finds
    every ending as a root (the modern engine, ``modern/source.py``), holds
    each element's endings in the day and the first after it; the
    occurrences are then cut at those, not on the chord. ``chord_end`` is
    the end of the chord's domain where the endings are on a chord (the
    text's nāḍīs to the day): an ending at or past it
    belongs to the next day even when the day is longer.
    """

    jdn: JDN
    length: Nadika
    sunrise: Nadika | None
    sunset: Nadika | None
    midnight: Nadika | None
    labels: Mapping[str, int]
    endings: Mapping[str, Nadika]
    per_span: Mapping[str, Nadika]
    flags: tuple[str, ...]
    standard: str
    sunrise_after_midnight: Nadika | None
    weekday: Weekday
    ahargana: int | None
    ending_list: Mapping[str, tuple[Nadika, ...]] | None = None
    chord_end: Nadika | None = None


class ElementSource(Protocol):
    """The element stream of one method and observer, day by day."""

    @property
    def id(self) -> str:
        """The method the stream computes."""
        ...

    @property
    def runs_from(self) -> JDN:
        """The first civil day the method serves."""
        ...

    def day(self, jdn: JDN) -> SourceDay:
        """The civil day ``jdn``."""
        ...


class SiddhanticSource:
    """A siddhantic method run as an :class:`ElementSource` (module docstring)."""

    def __init__(self, run: MethodRun) -> None:
        self.run = run
        self._memo: DayMemo[int, SourceDay] = DayMemo()

    @property
    def id(self) -> str:
        return self.run.resolved.method.id

    @property
    def runs_from(self) -> JDN:
        return self.run.runs_from

    def day(self, jdn: JDN) -> SourceDay:
        hit = self._memo.get(jdn.value)
        if hit is not None:
            return hit
        run, eng = self.run, self.run.engine
        r = run.day(jdn)
        nadis = run.resolved.model.units.nadis_per_day
        sun = ExactArc(r.true["sun"], AngleUnit.DEGREE)
        moon = ExactArc(r.true["moon"], AngleUnit.DEGREE)
        gs = ExactArc(eng.gati("sun", jdn), AngleUnit.DEGREE)
        gm = ExactArc(eng.gati("moon", jdn), AngleUnit.DEGREE)
        labels: dict[str, int] = {}
        per_span: dict[str, Nadika] = {}
        endings = dict(r.endings)
        for e, el in elements.ELEMENTS.items():
            labels[e] = elements.index(el, sun, moon)
            mot = elements.motion(el, gs, gm).value
            per_span[e] = proportional_parts(elements.span(el, sun).value, mot, nadis)
            if e not in endings:
                endings[e] = proportional_parts(elements.remaining(el, sun, moon).value, mot, nadis)
        sunset = None if r.sunset is None else r.sunset - r.sunrise
        out = SourceDay(
            jdn,
            r.day_length_nadika,
            Nadika(0),
            sunset,
            None,
            labels,
            endings,
            per_span,
            r.flags,
            r.standard,
            r.sunrise,
            r.weekday,
            r.ahargana.day,
            chord_end=Nadika(nadis),
        )
        self._memo[jdn.value] = out
        return out


def day_occurrences(day: SourceDay, element: str) -> tuple[Occurrence, ...]:
    """The element's occurrences in the civil day, the last running past its end."""
    count = elements.ELEMENTS[element].count
    index = day.labels[element]
    start: Nadika | None = None
    out: list[Occurrence] = []
    if day.ending_list is not None and element in day.ending_list:
        for end in day.ending_list[element]:
            if not end < day.length:
                out.append(Occurrence(index, start, None, end))
                return tuple(out)
            out.append(Occurrence(index, start, end, end))
            start, index = end, index % count + 1
        raise ValueError(f"{element}: the ending list stops inside the day")
    end, step = day.endings[element], day.per_span[element]
    if not step > Nadika(0):
        raise ValueError(f"{element}: a span of {step.value} nāḍikās does not advance")
    cut = day.length
    if day.chord_end is not None and day.chord_end < cut:
        cut = day.chord_end
    while end < cut:
        out.append(Occurrence(index, start, end, end))
        start, end, index = end, end + step, index % count + 1
    out.append(Occurrence(index, start, None, end))
    return tuple(out)


def sankranti_in_day(source: ElementSource, jdn: JDN) -> tuple[int, Nadika] | None:
    """The rāśi the Sun enters in civil day ``jdn`` and the time of entry, or ``None``.

    The day is the one the month stream takes (``calendar/months.py``,
    ``MonthStream.sankranti``): the Sun enters in day *n* when its rāśi
    at the sunrise of *n* + 1 is not its rāśi at the sunrise of *n*. The
    time is day *n*'s own estimate of the sign's end, in nāḍikās after
    its start; near a sunrise the two routes can disagree by seconds, so
    the estimate may fall just past the day's length, and it is reported
    as computed. Day *n* + 1 is
    read, a look ahead like a month's.
    """
    rasi = elements.RASI.id
    day = source.day(jdn)
    if source.day(jdn.plus_days(1)).labels[rasi] == day.labels[rasi]:
        return None
    return day.labels[rasi] % elements.RASI.count + 1, day.endings[rasi]


def tithi_name_index(t: int) -> tuple[int, str]:
    """The name (``names.yaml`` tithi index) and pakṣa of tithi ``t`` (1–30) of the month.

    Tithis 1–15 are the śukla pakṣa (15 the full moon); 16–29 the kṛṣṇa
    pakṣa, named as ``t`` − 15; 30 the new moon, its own name.
    """
    count = elements.TITHI.count
    if not 1 <= t <= count:
        raise ValueError(f"a tithi of the month is 1–{count}, not {t}")
    if t <= TITHIS_PER_PAKSA:
        return t, "shukla"
    if t == count:
        return count, "krishna"
    return t - TITHIS_PER_PAKSA, "krishna"
