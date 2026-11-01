"""The modern engine as the calendar layer's element stream.

:class:`ModernSource` gives, for one civil day, the
:class:`~jyotirganita.calendar.occurrences.SourceDay` the calendar layer
reads, from a :class:`~jyotirganita.modern.engine.ModernEngine`:

- the day runs from its start (the convention set's: sunrise or local
  midnight on the run's time standard, ``ModernEngine.day_bounds``) to the
  next day's start; sunrise, sunset and the local midnight are stated;
- each element's index at the day's start is the fixed mathematics
  of ``calendar/elements.py`` on the apparent sidereal longitudes;
- each **ending** is the instant the element's arc reaches the end of its
  span, found as a root (``modern/roots.py``, ``modern.root.*``): the
  procedure ``root``, not a chord. Every ending in the
  day is found, and the first after it, so the day's occurrences are the
  roots themselves (``SourceDay.ending_list``);
- ``per_span`` is the time one span takes at the day's mean motion of the
  arc, start to end, for a reader that wants it; the occurrences do not
  use it.

Times are the TT durations from the day's start, in nāḍikās (60 to the
day), except the sunrise after midnight, which is the reading of the
run's civil clock at sunrise (``ModernEngine.civil_of_tt``), so that a
leap second between midnight and sunrise (05:29:60 IST) does not put it
a second late. The record's sunset is that sunrise plus the TT duration
to the sunset, each quantised: no leap second falls between sunrise and
sunset at a Kerala place. All are quantised to ``modern.calendar_quantum``
half to even so that a
record is the same on every platform except at an exact half-quantum tie
(the siddhantic hybrid's convention, ``siddhantic.hybrid_sunrise_quantum``).

The search for an ending starts from the day's mean motion of the arc and
runs at most twice the time that motion needs to cover the span; a longer
search is an error.

:func:`mean_locator` gives the month stream (``calendar/months.py``) the
integer "mean Sun" it uses to find the *k*-th sidereal entry into a rāśi:
under the modern engine there is no text's mean Sun, so the locator is
calibrated on the engine's own Meṣa entries (two, about half the run's
range apart) and serves the search only. A year start counted from the
mean Sun (``sun: mean``) is not served by a modern run.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction
from math import floor

from jyotirganita.calendar import elements
from jyotirganita.calendar.months import MeanSun
from jyotirganita.calendar.occurrences import SourceDay
from jyotirganita.core.calendar import weekday
from jyotirganita.core.exact import Rounding, round_to
from jyotirganita.core.memo import DayMemo
from jyotirganita.core.types import JDN, TT, FloatArc, FloatDays, Nadika
from jyotirganita.data.engine_parameters import EngineParameter
from jyotirganita.modern.engine import ModernEngine
from jyotirganita.modern.kernels import KernelError
from jyotirganita.modern.roots import RootError
from jyotirganita.modern.timescales import OutOfRange

__all__ = ["ModernSource", "mean_locator"]

NADIKAS_PER_DAY = 60
DEGREES_PER_REVOLUTION = 360
_HALF = DEGREES_PER_REVOLUTION // 2
_SCALE = 1000
#: the bodies an element's arc reads
_NEEDS: dict[elements.Of, tuple[str, ...]] = {
    elements.Of.ELONGATION: ("sun", "moon"),
    elements.Of.MOON: ("moon",),
    elements.Of.SUM: ("sun", "moon"),
    elements.Of.SUN: ("sun",),
}


def _wrap(deg: float) -> float:
    """An arc in degrees reduced into [−180°, 180°)."""
    return (deg + _HALF) % DEGREES_PER_REVOLUTION - _HALF


class ModernSource:
    """A modern run as an :class:`~jyotirganita.calendar.occurrences.ElementSource`."""

    def __init__(
        self,
        engine: ModernEngine,
        method_id: str,
        quantum: EngineParameter,
        flags: tuple[str, ...] = (),
    ) -> None:
        if quantum.key != "modern.calendar_quantum" or quantum.unit != "day":
            raise ValueError("the modern source's quantum is modern.calendar_quantum, in days")
        self.engine = engine
        self._id = method_id
        self.quantum = quantum.value
        self.flags = tuple(sorted(set(flags) | set(engine.observer.flags)))
        self._first, self.runs_to = engine.served_days()
        self._memo: DayMemo[int, SourceDay] = DayMemo()
        self._pos: dict[tuple[int, float], dict[str, FloatArc]] = {}

    @property
    def id(self) -> str:
        return self._id

    @property
    def runs_from(self) -> JDN:
        return self._first

    # --- positions and arcs -------------------------------------------------------

    def _positions(self, tt: TT) -> dict[str, FloatArc]:
        key = (tt.jd_whole, tt.jd_fraction)
        hit = self._pos.get(key)
        if hit is None:
            hit = {b: self.engine.sidereal_at(b, tt).arc for b in ("sun", "moon")}
            if len(self._pos) > DEGREES_PER_REVOLUTION:
                self._pos.clear()
            self._pos[key] = hit
        return hit

    def _arc_fn(self, el: elements.Element, boundary: float) -> Callable[[TT], float]:
        needs = _NEEDS[el.of]
        eng = self.engine

        def g(t: TT) -> float:
            pos = {b: eng.sidereal_at(b, t).arc for b in needs}
            sun = pos.get("sun", pos.get("moon"))
            moon = pos.get("moon", pos.get("sun"))
            assert sun is not None and moon is not None
            return _wrap(elements.arc(el, sun, moon).value - boundary)

        return g

    def _nadika(self, d: FloatDays) -> Nadika:
        q = round_to(Fraction(d.value), self.quantum, Rounding.HALF_EVEN)
        return Nadika(q * NADIKAS_PER_DAY)

    def _clock(self, tt: TT, jdn: JDN) -> Nadika:
        """The civil clock's reading at ``tt`` on day ``jdn``, in nāḍikās after midnight."""
        return self._nadika(FloatDays(self.engine.civil_of_tt(tt, jdn).local_fraction))

    # --- the day --------------------------------------------------------------------

    def _check_served(self, jdn: JDN) -> None:
        before = jdn.days_since(self._first) < 0
        if before or self.runs_to.days_since(jdn) < 0:
            lo, hi = self.engine.bounding_components()
            raise OutOfRange(
                f"JDN {jdn.value} is outside the run's range (JDN {self._first.value}–"
                f"{self.runs_to.value}), which {lo if before else hi} bounds at that end "
                f"({self.engine.range_text()})"
            )

    def day(self, jdn: JDN) -> SourceDay:
        hit = self._memo.get(jdn.value)
        if hit is not None:
            return hit
        self._check_served(jdn)
        eng = self.engine
        start, sunrise, sunset, m0 = eng.day_bounds(jdn)
        end, _, _, m1 = eng.day_bounds(jdn.plus_days(1))
        length_days = (end - start).value
        p0, p1 = self._positions(start), self._positions(end)
        labels: dict[str, int] = {}
        endings: dict[str, Nadika] = {}
        ending_list: dict[str, tuple[Nadika, ...]] = {}
        per_span: dict[str, Nadika] = {}
        for e, el in elements.ELEMENTS.items():
            idx = elements.index(el, p0["sun"], p0["moon"])
            labels[e] = idx
            a0 = elements.arc(el, p0["sun"], p0["moon"]).value
            a1 = elements.arc(el, p1["sun"], p1["moon"]).value
            rate = ((a1 - a0) % DEGREES_PER_REVOLUTION) / length_days
            span = DEGREES_PER_REVOLUTION / el.count
            per_span[e] = self._nadika(FloatDays(span / rate))
            found: list[Nadika] = []
            after, boundary = start, span * idx
            while True:
                remaining = (boundary - elements.arc(el, *self._at(after)).value) % (
                    DEGREES_PER_REVOLUTION
                )
                estimate = remaining / rate
                try:
                    t = eng.element_roots.crossing_after(
                        self._arc_fn(el, boundary % DEGREES_PER_REVOLUTION),
                        after,
                        estimate,
                        2 * span / rate + 1,
                    )
                except RootError as exc:
                    raise RootError(f"{e} ending after JDN {jdn.value}'s start: {exc}") from exc
                n = self._nadika(t - start)
                found.append(n)
                if not (t - start).value < length_days:
                    break
                after, boundary = t, boundary + span
            endings[e] = found[0]
            ending_list[e] = tuple(found)
        out = SourceDay(
            jdn,
            self._nadika(end - start),
            self._nadika(sunrise - start),
            None if sunset is None else self._nadika(sunset - start),
            self._nadika(m0 - start) if not m0 < start else self._nadika(m1 - start),
            labels,
            endings,
            per_span,
            self.flags,
            eng.standard.id,
            # the clock's reading, not the TT elapsed since midnight: a leap second
            # between them would otherwise put the sunrise a second late
            self._clock(sunrise, jdn),
            weekday(jdn),
            None,
            ending_list,
        )
        self._memo[jdn.value] = out
        return out

    def _at(self, tt: TT) -> tuple[FloatArc, FloatArc]:
        p = self._positions(tt)
        return p["sun"], p["moon"]


def mean_locator(engine: ModernEngine) -> MeanSun:
    """The integer locator of the Sun's sidereal entries for the month stream (module docstring).

    Two Meṣa entries of the run's own Sun are found: the first after a
    quarter of the run's range, ``E₀``, and the one about half the range
    later, ``E₁``; the locator is ``N`` revolutions in the whole days from
    ``E₀`` to ``E₁``, counted from the civil day of ``E₀``.
    """
    lo, hi = engine.range_tt()
    span_days = (hi - lo).value
    roots = engine.element_roots
    rasi = elements.RASI

    def g(t: TT) -> float:
        return _wrap(engine.sidereal_at("sun", t).arc.value)

    def entry_after(t: TT, estimate: float) -> TT:
        # g < 0 while the Sun is in the half circle before Meṣa
        return roots.crossing_after(g, t, estimate, DEGREES_PER_REVOLUTION)

    def first_entry(t: TT) -> TT:
        # half a year moves the Sun a little less than half a circle: a start just past
        # a Meṣa entry needs a second shift to reach the half before Meṣa
        while not g(t) < 0:
            t = t + FloatDays(_HALF)
        rate = _wrap(g(t + FloatDays(1)) - g(t))
        return entry_after(t, -g(t) / rate)

    e0 = first_entry(lo + FloatDays(span_days / 4))
    lead = FloatDays(DEGREES_PER_REVOLUTION / rasi.count)  # a sign's worth of days before
    e1 = entry_after(e0 + (FloatDays(DEGREES_PER_REVOLUTION) - lead), lead.value)
    year = (e1 - e0).value
    n = floor(span_days / 2 / year)
    if n < 1:
        raise KernelError(
            "the run's range (the kernel's span within the ΔT model's) is shorter than two "
            "years: no month locator"
        )
    en = entry_after(e0 + (FloatDays(n * year) - lead), lead.value)
    # the revolutions and days scaled by a thousand, so that the rate keeps the root's precision
    days = round((en - e0).value * _SCALE)
    epoch = floor(e0.jd_whole + e0.jd_fraction + Fraction(1, 2))
    return MeanSun(n * _SCALE, days, 0, JDN(epoch))
