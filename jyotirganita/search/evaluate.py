"""The day view and the evaluation of a query on one civil day.

**The day view** (:class:`DayView`) of one civil day is the calendar
leaves of :meth:`Calendar.day` plus the record's ``planets`` block:
``planets: {body: {sidereal_longitude, latitude | not_modelled,
daily_motion, retrograde}}`` for the Sun, the Moon, Mercury, Venus, Mars,
Jupiter, Saturn, Rāhu and Ketu, ``planets.<body>: not_modelled`` for a
body the method does not serve. It is built from the engine protocol
only (``core/engine.py``): ``sidereal_longitude(body, instant(jdn,
Nadika(0)))`` at the civil day's start (the frame's sunrise, the
method's computation instant as the engine realises it), ``daily_motion``
(the gati under a siddhantic method, the arc between consecutive day
starts under ``modern_de``), ``latitude`` where served, ``retrograde`` as
the sign of the daily motion. Rāhu is the engine's ascending node
(``node``), Ketu the descending node, the ascending node plus half a
circle; the nodes' daily motion is the signed arc between consecutive
day starts. The leaf is built in one place, ``io/record.py``
(:class:`~jyotirganita.io.record.Positions`), which the evaluator and the
day records share.

**Fixed mathematics**: the rāśi of a longitude λ is
⌊λ/30°⌋ + 1 and its nakṣatra ⌊27λ/360°⌋ + 1. Under a siddhantic run every
value is exact (``Fraction``); under ``modern_de`` the longitudes are the
engine's floats, converted exactly to fractions for comparison and
written back as the same floats (``numeric: float``).

**Matching**. An occurrence element matched
``assigned`` holds when the day's label under the preset's assignment
rule is a required index; ``any_occurrence`` when a required index is in
force at some instant of the civil day; ``at_time`` when it is in force
the stated nāḍikās after sunrise. A position element matched
``at_sunrise`` holds when the body's place at the day's start lies in a
required span; ``any_time_in_day`` when its place at some instant of the
civil day, on the engine's own motion through it (the places the API's
``positions`` returns, :meth:`Positions.sweep`), lies in a required span;
the next day's start belongs to the next day. ``position: mean`` reads the
siddhantic engine's mean longitude (``DayResult.mean``). ``retrograde``,
where a constraint states it, must also agree.

**Margins**: an occurrence element, the signed nāḍikās
from the reference instant (the assignment instant, the stated time, or
the civil day's bounds for ``any_occurrence``) to the nearest instant at
which it holds; a position element, the signed degrees from the body's
place to the nearest boundary of a required span and the days at its
daily motion; ``weekday``, ``day_of_month``, ``masa``, ``era_year`` and
``era_day``, the signed integer difference to the nearest required value
in days, months or years; any other element, the signed days to the
nearest day on which it holds, searched to ``search.margin_horizon``
days either side and reported beyond it as ``null``. Positive is later.

No ``math``, ``numpy`` or ``decimal`` import.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cached_property
from itertools import pairwise
from typing import Any

from jyotirganita.calendar import elements
from jyotirganita.calendar.assignment import Occurrence
from jyotirganita.calendar.day import NOT_IN_PRESET
from jyotirganita.calendar.months import MonthOf
from jyotirganita.calendar.occurrences import SourceDay, day_occurrences, sankranti_in_day
from jyotirganita.core.eras import NotInRange, era_year
from jyotirganita.core.types import JDN, Nadika
from jyotirganita.data import engine_parameters
from jyotirganita.io.record import BODIES, NODES, Positions, Sweep, parsed_leaves, signed
from jyotirganita.search.config import SearchConfig
from jyotirganita.search.query import Constraint, Query
from jyotirganita.search.results import Candidate

__all__ = ["BODIES", "NODES", "DayView", "Evaluator", "Outcome", "Timeline", "signed"]

CIRCLE = Fraction(360)
HALF = Fraction(180)
SIGNS = elements.RASI.count
NAKSHATRAS = elements.NAKSATRA.count
NADIKAS = 60
DAYS_PER_WEEK = 7
HALF_WEEK = 3
HALF_YEAR_SIGNS = 6
#: day views kept in memory (a near-miss margin revisits the days around a candidate);
#: structural: a cache of a pure function of the day
VIEW_CACHE = 1000
#: days of the element timeline built first around a day, then widened fourfold
TIMELINE_START = 2
TIMELINE_GROWTH = 4
#: the full moon ends tithi 15, the new moon tithi 30
FULL_MOON_TITHI, NEW_MOON_TITHI = 15, 30
ECLIPSE_FLAG = "provisional:eclipse"
#: the span count of each position element's indices
SPANS: Mapping[str, int] = {
    "planet_rasi": SIGNS,
    "planet_nakshatra": NAKSHATRAS,
    "moon_rasi": SIGNS,
    "sun_rasi": SIGNS,
    "ayana": SIGNS,
}
BODY_OF: Mapping[str, str] = {"moon_rasi": "moon", "sun_rasi": "sun", "ayana": "sun"}


def span_index(lam: Fraction, count: int) -> int:
    """The 1-based span of ``count`` equal spans to the circle that ``lam`` lies in."""
    return int((lam % CIRCLE) * count // CIRCLE) + 1


def swept(lam: Fraction, sweep: Sweep, count: int) -> tuple[int, ...]:
    """The spans the body's place lies in at some instant of the day, in its direction of motion.

    ``lam`` is the place at the day's start and ``sweep`` the arc it covers
    (:meth:`Positions.sweep`): every span from the one holding ``lam +
    sweep.lo`` to the one holding ``lam + sweep.hi``, less the span that
    begins exactly at an upper end reached only at the day's end.
    """
    width = CIRCLE / count
    lo, hi = lam + sweep.lo, lam + sweep.hi
    first, last = int(lo // width), int(hi // width)
    if sweep.hi_open and last > first and hi % width == 0:
        last -= 1
    out = tuple(k % count + 1 for k in range(first, last + 1))
    return out[::-1] if sweep.end < 0 else out


def to_spans(lam: Fraction, values: frozenset[int], count: int) -> Fraction:
    """Signed degrees from ``lam`` to the nearest boundary of a span in ``values`` (0 inside)."""
    if span_index(lam, count) in values:
        return Fraction(0)
    width = CIRCLE / count
    best: Fraction | None = None
    for v in values:
        ahead = ((v - 1) * width - lam) % CIRCLE
        behind = -((lam - v * width) % CIRCLE)
        for d in (ahead, behind):
            if best is None or abs(d) < abs(best) or (abs(d) == abs(best) and d > best):
                best = d
    assert best is not None
    return best


def _nearest_int(n: int, ranges: Sequence[tuple[int, int]]) -> int:
    best: int | None = None
    for lo, hi in ranges:
        d = 0 if lo <= n <= hi else (lo - n if n < lo else hi - n)
        if best is None or abs(d) < abs(best) or (abs(d) == abs(best) and d > best):
            best = d
    assert best is not None
    return best


def _cyclic(actual: int, values: frozenset[int], count: int) -> int:
    """The signed shortest difference from ``actual`` to a value of a cycle of ``count``."""
    half = count // 2
    best: int | None = None
    for v in values:
        d = (v - actual + half) % count - half
        if best is None or abs(d) < abs(best) or (abs(d) == abs(best) and d > best):
            best = d
    assert best is not None
    return best


@dataclass(frozen=True, slots=True)
class Outcome:
    """A constraint on one day: whether it holds, its evidence, and its margin when it fails."""

    matched: bool
    evidence: Mapping[str, Any]
    margin: Mapping[str, Any] | None


class Timeline:
    """An element's indices along consecutive civil days, times in nāḍikās after day ``jdn``.

    ``first`` is the index in force at the start of the first day covered;
    ``transitions`` the instants at which the index changes, with the index
    after each.
    """

    def __init__(
        self,
        first: int,
        transitions: Sequence[tuple[Fraction, int]],
        reach: tuple[Fraction | None, Fraction | None] = (None, None),
    ) -> None:
        self.first = first
        self.transitions = tuple(transitions)
        # the instants the timeline covers, before and after; None where the served
        # range ends it, so that nothing lies beyond to be found
        self.reach = reach

    def index_at(self, t: Fraction) -> int:
        idx = self.first
        for tt, i in self.transitions:
            if t < tt:
                break
            idx = i
        return idx

    def holding(
        self, values: frozenset[int], a: Fraction, b: Fraction
    ) -> list[tuple[Fraction, Fraction]]:
        """The parts of [a, b) during which a value of ``values`` is in force."""
        out: list[tuple[Fraction, Fraction]] = []
        cur, start = self.index_at(a), a
        for tt, i in self.transitions:
            if tt <= a:
                continue
            if tt >= b:
                break
            if cur in values:
                out.append((start, tt))
            cur, start = i, tt
        if cur in values:
            out.append((start, b))
        return out

    def nearest(self, values: frozenset[int], a: Fraction, b: Fraction) -> Fraction | None:
        """Signed nāḍikās from [a, b] to the nearest instant a value holds (0 if it holds in it)."""
        if self.holding(values, a, b) if b > a else self.index_at(a) in values:
            return Fraction(0)
        after: Fraction | None = None
        for tt, i in self.transitions:
            # a value that begins at b itself holds in [a, b] (else it would fall between
            # holding()'s [a, b) and this search)
            if tt >= b and i in values:
                after = tt - b
                break
        before: Fraction | None = None
        prev_index = self.first
        for tt, i in self.transitions:
            if tt > a:
                break
            if prev_index in values:
                before = tt - a  # the occurrence ended at tt, before a (≤ 0)
            prev_index = i
        options = [x for x in (after, before) if x is not None]
        if not options:
            return None
        return min(options, key=lambda x: (abs(x), -x))

    def around(self, t: Fraction) -> tuple[Fraction | None, Fraction | None]:
        """The transitions before (≤) and after (>) ``t``, ``None`` beyond the timeline."""
        before = after = None
        for tt, _ in self.transitions:
            if tt <= t:
                before = tt
            elif after is None:
                after = tt
        return before, after


class DayView:
    """One civil day's leaves, computed when first asked for (module docstring)."""

    def __init__(self, ev: Evaluator, jdn: JDN) -> None:
        self.ev = ev
        self.jdn = jdn

    @cached_property
    def sd(self) -> SourceDay:
        return self.ev.source.day(self.jdn)

    @cached_property
    def cal(self) -> Mapping[str, Any]:
        return self.ev.calendar.day(self.jdn)

    @cached_property
    def month(self) -> MonthOf | None:
        months = self.ev.calendar.months
        return None if months is None else months.month_of(self.jdn)

    def occurrences(self, element: str) -> tuple[Occurrence, ...]:
        return day_occurrences(self.sd, element)

    def assigned(self, element: str) -> int:
        return self.ev.calendar.assigned(self.sd, element)

    @cached_property
    def weekday(self) -> int:
        """The weekday, ``names.yaml``'s vara index (1 = Sunday), as the calendar writes it."""
        return (self.sd.weekday.value + 1) % DAYS_PER_WEEK + 1

    @cached_property
    def sunrise(self) -> Fraction:
        """Sunrise in nāḍikās after the civil day's start."""
        s = self.sd.sunrise
        return Fraction(0) if s is None else s.value

    @cached_property
    def length(self) -> Fraction:
        return self.sd.length.value

    @cached_property
    def planets(self) -> dict[str, Any]:
        return self.ev.planets(self.jdn)

    def record(self) -> dict[str, Any]:
        """The calendar leaves with their exact strings parsed, and the planets block."""
        out = {k: parsed_leaves(k, v) for k, v in self.cal.items()}
        out["planets"] = self.planets
        return out


class Evaluator:
    """Evaluates a compiled query on civil days of one configuration (module docstring)."""

    def __init__(self, config: SearchConfig, query: Query) -> None:
        self.config = config
        self.query = query
        self.calendar = config.calendar
        self.source = config.calendar.source
        self.engine = config.engine
        self.exact = config.numeric == "exact"
        self.positions = Positions(config)
        self.bodies = self.positions.bodies
        params = engine_parameters.load()
        self.horizon = int(params["search.margin_horizon"].value)
        self._views: OrderedDict[int, DayView] = OrderedDict()
        self._eclipses: dict[tuple[str, int], list[dict[str, Any]]] = {}
        static: set[str] = set(config.diagnostic)
        for c in query.constraints:
            static.update(c.flags())
            if c.element == "eclipse":
                static.add(ECLIPSE_FLAG)
        self.static_flags = frozenset(static)
        self.provenance: dict[str, Any] = {}

    # --- served range --------------------------------------------------------------------

    def served(self, jdn: JDN) -> bool:
        if jdn.days_since(self.config.runs_from) < 0:
            return False
        rt = self.config.runs_to
        return rt is None or rt.days_since(jdn) >= 0

    def view(self, jdn: JDN) -> DayView:
        hit = self._views.get(jdn.value)
        if hit is not None:
            self._views.move_to_end(jdn.value)
            return hit
        v = DayView(self, jdn)
        self._views[jdn.value] = v
        if len(self._views) > VIEW_CACHE:
            self._views.popitem(last=False)
        return v

    # --- positions -----------------------------------------------------------------------

    def _out(self, x: Fraction | None) -> Any:
        return self.positions.out(x)

    def lon(self, body: str, jdn: JDN, position: object = True) -> Fraction:
        """The body's sidereal longitude at the start of civil day ``jdn`` (``io/record.py``)."""
        return self.positions.lon(body, jdn, position)

    def motion(self, body: str, jdn: JDN, position: object = True) -> Fraction | None:
        """The body's daily motion on ``jdn`` (``io/record.py``)."""
        return self.positions.motion(body, jdn, position)

    def planets(self, jdn: JDN) -> dict[str, Any]:
        """The record's planets block for civil day ``jdn`` (``io/record.py``)."""
        return self.positions.planets(jdn)

    # --- element timelines ---------------------------------------------------------------

    def timeline(self, element: str, jdn: JDN, back: int, fwd: int) -> Timeline:
        """The element's indices from ``back`` days before ``jdn`` to ``fwd`` days after it."""
        first_day = jdn.plus_days(-back)
        while not self.served(first_day):
            if first_day.value >= jdn.value:
                # the walk would run on unbounded past the served range; every caller asks
                # about a served day
                raise ValueError(f"JDN {jdn.value} is not a served day")
            first_day = first_day.plus_days(1)
        clipped = first_day.value != jdn.value - back
        offset = Fraction(0)
        d = first_day
        while d.value < jdn.value:
            offset -= self.view(d).length
            d = d.plus_days(1)
        transitions: list[tuple[Fraction, int]] = []
        first_index: int | None = None
        last_index: int | None = None
        d, off = first_day, offset
        while d.value <= jdn.value + fwd and self.served(d):
            v = self.view(d)
            occ = v.occurrences(element)
            if first_index is None:
                first_index = occ[0].index
            elif occ[0].index != last_index:
                # a change between the day's last occurrence and the next day's first
                # (a seam): it is placed at the day's start
                transitions.append((off, occ[0].index))
            last_index = occ[-1].index
            for o, nxt in pairwise(occ):
                assert o.end is not None
                transitions.append((off + o.end.value, nxt.index))
            off += v.length
            d = d.plus_days(1)
        assert first_index is not None
        ended = d.value <= jdn.value + fwd  # the served range ended the walk
        return Timeline(
            first_index, transitions, (None if clipped else offset, None if ended else off)
        )

    def nearest_instant(
        self, element: str, jdn: JDN, values: frozenset[int], a: Fraction, b: Fraction
    ) -> Fraction | None:
        span = TIMELINE_START
        while True:
            span = min(span, self.horizon)
            tl = self.timeline(element, jdn, span, span)
            got = tl.nearest(values, a, b)
            if span >= self.horizon:
                return got
            if got is not None:
                # an instant found on one side is the nearest only if the timeline reaches
                # as far on the other
                lo, hi = tl.reach
                if (lo is None or a - abs(got) >= lo) and (hi is None or b + abs(got) <= hi):
                    return got
            span *= TIMELINE_GROWTH

    def transitions_around(
        self, element: str, jdn: JDN, t: Fraction
    ) -> tuple[Fraction | None, Fraction | None]:
        span = TIMELINE_START
        while True:
            span = min(span, self.horizon)
            before, after = self.timeline(element, jdn, span, span).around(t)
            if (before is not None and after is not None) or span >= self.horizon:
                return before, after
            span *= TIMELINE_GROWTH

    def nearest_day(self, c: Constraint, jdn: JDN) -> int | None:
        """Signed days to the nearest civil day on which ``c`` holds, within the horizon."""
        for k in range(1, self.horizon + 1):
            for d in (jdn.plus_days(k), jdn.plus_days(-k)):
                if not self.served(d) or not self.served(d.plus_days(1)):
                    continue
                try:
                    if self.holds(c, self.view(d)):
                        return d.days_since(jdn)
                except ValueError:  # a stream that cannot be searched there
                    continue
        return None

    def _day_margin(self, c: Constraint, jdn: JDN) -> dict[str, Any]:
        n = self.nearest_day(c, jdn)
        out: dict[str, Any] = {"unit": "day", "value": n}
        if n is None:
            out["beyond"] = self.horizon
        return out

    # --- the constraints ------------------------------------------------------------------

    def holds(self, c: Constraint, v: DayView) -> bool:
        """Whether ``c`` holds on ``v`` (the cheap path; the same test :meth:`outcome` makes)."""
        return self._eval(c, v, full=False).matched

    def outcome(self, c: Constraint, v: DayView) -> Outcome:
        return self._eval(c, v, full=True)

    def _eval(self, c: Constraint, v: DayView, *, full: bool) -> Outcome:
        e = c.element
        if e == "era_year":
            return self._era_year(c, v, full)
        if e == "era_day":
            return self._era_day(c, v, full)
        if e == "masa":
            return self._masa(c, v, full)
        if e == "day_of_month":
            return self._day_of_month(c, v, full)
        if e == "sankranti_day":
            return self._sankranti_day(c, v, full)
        if e == "weekday":
            return self._weekday(c, v, full)
        if e in SPANS:
            return self._position(c, v, full)
        if e in elements.ELEMENTS:
            return self._occurrence(c, v, full)
        if e == "eclipse":
            return self._eclipse(c, v, full)
        if e == "overlap":
            return self._overlap(c, v, full)
        if e == "at_time":
            return self._at_time(c, v, full)
        raise AssertionError(e)  # pragma: no cover - compile_query's vocabulary

    def _era_year(self, c: Constraint, v: DayView, full: bool) -> Outcome:
        assert c.era is not None and c.year_start is not None
        record = self.calendar.eras[c.era].era
        y = era_year(record, v.jdn, c.year_start, self.calendar.year_stream(c.era, c.year_start))
        if isinstance(y, NotInRange):
            return Outcome(
                False, {"era": c.era, "year": "not_in_range"}, {"unit": "year", "value": None}
            )
        ok = c.holds_number(y.year)
        if not full:
            return Outcome(ok, {}, None)
        others: dict[str, Any] = {}
        for option in sorted(record.year_starts or {}):
            if option == c.year_start:
                continue
            try:
                oy = era_year(record, v.jdn, option, self.calendar.year_stream(c.era, option))
                others[option] = "not_in_range" if isinstance(oy, NotInRange) else oy.year
            except ValueError:
                others[option] = "not_served"
        ev = {
            "era": c.era,
            "year_start": c.year_start,
            "year": y.year,
            "year_first_day": y.first_day.value,
            "other_year_starts": others,
        }
        return Outcome(
            ok, ev, None if ok else {"unit": "year", "value": _nearest_int(y.year, c.ranges)}
        )

    def count(self, v: DayView) -> int:
        """The day count ``era_day`` is matched against: the ahargaṇa, or the JDN less the epoch."""
        leaf = self.calendar.binding.day_count
        if leaf == "ahargana":
            n = v.sd.ahargana
            assert n is not None
            return n
        epoch = self.calendar.eras[self.calendar.time_base_era].era.epoch
        assert epoch is not None
        return v.jdn.days_since(epoch)

    def _era_day(self, c: Constraint, v: DayView, full: bool) -> Outcome:
        n = self.count(v)
        ok = c.holds_number(n)
        if not full:
            return Outcome(ok, {}, None)
        ef = self.calendar.eras[self.calendar.time_base_era]
        ev = {
            "era": c.era,
            "leaf": self.calendar.binding.day_count,
            "count": n,
            "epoch": {
                "record": ef.path,
                "jdn": None if ef.era.epoch is None else ef.era.epoch.value,
            },
        }
        return Outcome(ok, ev, None if ok else {"unit": "day", "value": _nearest_int(n, c.ranges)})

    def _masa(self, c: Constraint, v: DayView, full: bool) -> Outcome:
        m = v.month
        assert m is not None
        ok = m.rasi in c.values
        if not full:
            return Outcome(ok, {}, None)
        ev = {"rasi_index": m.rasi, "first_day": m.first_day.value, "day": m.day_of_month}
        return Outcome(
            ok, ev, None if ok else {"unit": "month", "value": _cyclic(m.rasi, c.values, SIGNS)}
        )

    def _day_of_month(self, c: Constraint, v: DayView, full: bool) -> Outcome:
        m = v.month
        assert m is not None
        ok = c.holds_number(m.day_of_month)
        if not full:
            return Outcome(ok, {}, None)
        ev = {"day": m.day_of_month, "rasi_index": m.rasi, "first_day": m.first_day.value}
        margin = None if ok else {"unit": "day", "value": _nearest_int(m.day_of_month, c.ranges)}
        return Outcome(ok, ev, margin)

    def _sankranti(self, v: DayView) -> tuple[int, Fraction] | None:
        s = sankranti_in_day(self.source, v.jdn)
        return None if s is None else (s[0], s[1].value)

    def _sankranti_day(self, c: Constraint, v: DayView, full: bool) -> Outcome:
        s = self._sankranti(v)
        ok = s is not None and s[0] in c.values
        if not full:
            return Outcome(ok, {}, None)
        ev: dict[str, Any] = (
            {"sankranti": None}
            if s is None
            else {
                "rasi_index": s[0],
                "instant_nadika": s[1],
            }
        )
        return Outcome(ok, ev, None if ok else self._day_margin(c, v.jdn))

    def _weekday(self, c: Constraint, v: DayView, full: bool) -> Outcome:
        w = v.weekday
        ok = w in c.values
        if not full:
            return Outcome(ok, {}, None)
        margin = None if ok else {"unit": "day", "value": _cyclic(w, c.values, DAYS_PER_WEEK)}
        return Outcome(ok, {"index": w}, margin)

    def _position(self, c: Constraint, v: DayView, full: bool) -> Outcome:
        body = c.body or BODY_OF[c.element]
        position: object = True if c.position is None else c.position
        count = SPANS[c.element]
        lam = self.lon(body, v.jdn, position)
        if c.match == "at_sunrise":
            spans: tuple[int, ...] = (span_index(lam, count),)
            sweep = Sweep.chord(Fraction(0))
        else:
            sweep = self.positions.sweep(body, v.jdn, position)
            spans = swept(lam, sweep, count)
        in_span = any(s in c.values for s in spans)
        mot = self.motion(body, v.jdn, position) if (c.retrograde is not None or full) else None
        retro_ok = True
        if c.retrograde is not None:
            retro_ok = mot is not None and (mot < 0) == c.retrograde
        ok = in_span and retro_ok
        if not full:
            return Outcome(ok, {}, None)
        width = CIRCLE / count
        inside = lam % width
        to_edge = min(inside, width - inside)
        ev: dict[str, Any] = {
            "body": body,
            "position": "true" if position is True else str(position),
            "longitude": self._out(lam),
            "index": span_index(lam, count),
            "daily_motion": None if mot is None else self._out(mot),
            "retrograde": None if mot is None else mot < 0,
            "to_boundary": {
                "degrees": self._out(to_edge),
                "days": None if not mot else self._out(abs(to_edge / mot)),
            },
        }
        if c.match == "any_time_in_day":
            ev["step"] = self._out(sweep.end)
            ev["indices"] = list(spans)
        if ok:
            return Outcome(True, ev, None)
        if not in_span:
            lo_end = lam + sweep.lo
            hi_end = lam + sweep.hi
            ahead = to_spans(hi_end % CIRCLE, c.values, count)
            behind = to_spans(lo_end % CIRCLE, c.values, count)
            # ahead is 0 where a required span begins at an upper end the day does not reach
            deg = ahead if ahead >= 0 else behind
            if ahead >= 0 and behind < 0:
                deg = min((ahead, behind), key=lambda x: (abs(x), -x))
            days = None if not mot else deg / mot
            return Outcome(
                False, ev, {"unit": "degree", "value": self._out(deg), "days": self._out(days)}
            )
        return Outcome(False, ev, self._day_margin(c, v.jdn))

    def _reference(self, c: Constraint, v: DayView) -> tuple[Fraction, Fraction]:
        """The interval an occurrence constraint is read over, in nāḍikās after the day's start."""
        if c.match == "at_time":
            assert c.nadika is not None
            t = v.sunrise + c.nadika
            return t, t
        if c.match == "assigned":
            if self.calendar.conventions.assignment in ("at_sunrise", "udaya_vyapini"):
                return v.sunrise, v.sunrise
            return Fraction(0), v.length
        return Fraction(0), v.length

    def _occurrence(self, c: Constraint, v: DayView, full: bool) -> Outcome:
        e = c.element
        occ = v.occurrences(e)
        if c.match == "assigned":
            idx = v.assigned(e)
            ok = idx in c.values
        elif c.match == "at_time":
            a, _ = self._reference(c, v)
            if not a < v.length:
                ok, idx = False, -1
            else:
                idx = next(o.index for o in occ if o.end is None or a < o.end.value)
                ok = idx in c.values
        else:
            idx = -1
            ok = any(o.index in c.values for o in occ)
        if not full:
            return Outcome(ok, {}, None)
        assigned = v.assigned(e)
        rows = []
        first = True
        for o in occ:
            rows.append(
                {
                    "index": o.index,
                    "start": None if o.start is None else o.start.value,
                    "end": None if o.end is None else o.end.value,
                    "assigned": first and o.index == assigned,
                }
            )
            if o.index == assigned:
                first = False
        a, b = self._reference(c, v)
        ev: dict[str, Any] = {"match": c.match, "occurrences": rows}
        if c.match != "any_occurrence":
            ev["reference_nadika"] = a
            ev["index"] = idx
            if ok:
                before, after = self.transitions_around(e, v.jdn, a)
                ev["since_transition_nadika"] = None if before is None else a - before
                ev["to_transition_nadika"] = None if after is None else after - a
        if ok:
            return Outcome(True, ev, None)
        n = self.nearest_instant(e, v.jdn, c.values, a, b)
        margin: dict[str, Any] = {"unit": "nadika", "value": n}
        if n is None:
            margin["beyond"] = self.horizon
        return Outcome(False, ev, margin)

    # --- eclipses (modern only) ------------------------------------------------------------

    def _syzygies(self, jdn: JDN) -> list[tuple[str, Fraction]]:
        """The syzygies in civil day ``jdn``: (``lunar`` | ``solar``, nāḍikās after its start)."""
        out: list[tuple[str, Fraction]] = []
        occ = self.view(jdn).occurrences("tithi")
        for o in occ:
            if o.end is None:
                continue
            if o.index == FULL_MOON_TITHI:
                out.append(("lunar", o.end.value))
            elif o.index == NEW_MOON_TITHI:
                out.append(("solar", o.end.value))
        return out

    def eclipses(self, jdn: JDN) -> list[dict[str, Any]]:
        """The eclipses whose greatest instant falls in civil day ``jdn`` (provisional)."""
        out: list[dict[str, Any]] = []
        eng = self.engine
        start = eng.day_bounds(jdn)[0]
        end = eng.day_bounds(jdn.plus_days(1))[0]
        for d in (jdn.plus_days(-1), jdn, jdn.plus_days(1)):
            if not self.served(d) or not self.served(d.plus_days(1)):
                continue
            for kind, t in self._syzygies(d):
                key = (kind, d.value)
                hit = self._eclipses.get(key)
                if hit is None:
                    hit = self._eclipse_at(kind, d, t)
                    self._eclipses[key] = hit
                for e in hit:
                    g = e["_greatest"]
                    if not g < start and g < end:
                        out.append(e)
        return out

    def _eclipse_at(self, kind: str, day: JDN, t: Fraction) -> list[dict[str, Any]]:
        eng = self.engine
        provider = eng.eclipses()
        lo = eng.tt_of_civil(eng.instant(day.plus_days(-1), Nadika(t)))
        hi = eng.tt_of_civil(eng.instant(day.plus_days(1), Nadika(t)))
        body = "moon" if kind == "lunar" else "sun"
        if kind == "lunar":
            le = provider.lunar(lo, hi)
            if le is None:
                return []
            greatest = le.greatest
            # an umbral eclipse is seen from its umbral contacts: a Moon that rises in
            # the penumbral phase after the umbral one has ended sees nothing
            contacts = le.partial if le.partial is not None else le.penumbral
            magnitude = le.umbral_magnitude if le.partial is not None else le.penumbral_magnitude
            sub = "total" if le.total is not None else ("partial" if le.partial else "penumbral")
        else:
            se = provider.solar(lo, hi)
            if se is None:
                return []
            greatest, contacts, magnitude, sub = se.greatest, se.outer, se.magnitude, se.kind
        visible = self._visible(body, greatest, contacts)
        civil = eng.civil_of_tt(greatest, day)
        return [
            {
                "_greatest": greatest,
                "kind": kind,
                "type": sub,
                "magnitude": magnitude,
                "greatest": {"jdn": civil.jdn.value, "local_fraction": civil.local_fraction},
                "visible_at_observer": visible,
            }
        ]

    def _visible(self, body: str, greatest: Any, contacts: Any) -> bool:
        rs = self.engine.riseset
        if contacts is not None and rs.events(body, contacts[0], contacts[1]):
            return True
        alt, threshold = rs.altitude(body, greatest)
        return bool(alt > threshold)

    def _eclipse(self, c: Constraint, v: DayView, full: bool) -> Outcome:
        found = [
            e
            for e in self.eclipses(v.jdn)
            if (c.eclipse == "any" or e["kind"] == c.eclipse)
            and (c.visible is None or e["visible_at_observer"] == c.visible)
        ]
        ok = bool(found)
        if not full:
            return Outcome(ok, {}, None)
        listed = [
            {k: x for k, x in e.items() if not k.startswith("_")} for e in self.eclipses(v.jdn)
        ]
        ev = {"eclipses": listed}
        return Outcome(ok, ev, None if ok else self._day_margin(c, v.jdn))

    # --- overlap and at_time ---------------------------------------------------------------

    def _overlap(self, c: Constraint, v: DayView, full: bool) -> Outcome:
        cons = self.query.constraints
        common: list[tuple[Fraction, Fraction]] = [(Fraction(0), v.length)]
        tl = {}
        for i in c.of:
            ref = cons[i]
            tl[ref.element] = self.timeline(ref.element, v.jdn, 0, 0)
            parts = tl[ref.element].holding(ref.values, Fraction(0), v.length)
            common = [
                (max(a, x), min(b, y)) for a, b in common for x, y in parts if max(a, x) < min(b, y)
            ]
        ok = bool(common)
        if not full:
            return Outcome(ok, {}, None)
        ev = {
            "elements": [cons[i].element for i in c.of],
            "common": [[a, b] for a, b in common],
        }
        return Outcome(ok, ev, None if ok else self._day_margin(c, v.jdn))

    def _at_time(self, c: Constraint, v: DayView, full: bool) -> Outcome:
        assert c.nadika is not None
        t = v.sunrise + c.nadika
        cons = self.query.constraints
        indices: dict[str, int | None] = {}
        ok = t < v.length
        for i in c.of:
            ref = cons[i]
            idx = self.timeline(ref.element, v.jdn, 0, 0).index_at(t) if t < v.length else None
            indices[ref.element] = idx
            ok = ok and idx in ref.values
        if not full:
            return Outcome(ok, {}, None)
        ev = {"at_nadika": t, "indices": indices}
        return Outcome(ok, ev, None if ok else self._day_margin(c, v.jdn))

    # --- one day --------------------------------------------------------------------------

    def fails(self, jdn: JDN) -> int | None:
        """The count of ``require`` constraints failing on ``jdn``, stopping past the allowance."""
        v = self.view(jdn)
        n = 0
        for c in self.query.required:
            if not self.holds(c, v):
                n += 1
                if n > self.query.max_misses:
                    return None
        return n

    def evaluate(self, jdn: JDN) -> Candidate | None:
        """The candidate ``jdn`` is, or ``None`` (more require constraints fail than allowed)."""
        if self.fails(jdn) is None:
            return None
        v = self.view(jdn)
        outcomes = [self.outcome(c, v) for c in self.query.constraints]
        misses = [
            (c, o)
            for c, o in zip(self.query.constraints, outcomes, strict=True)
            if c.require and not o.matched
        ]
        if len(misses) > self.query.max_misses:  # pragma: no cover - fails() agrees
            return None
        rec = v.record()
        flags = set(rec["flags"]) | self.static_flags
        for c, o in zip(self.query.constraints, outcomes, strict=True):
            if o.matched and self._boundary(c, o):
                flags.add("boundary_sensitive")
        entries = []
        for c, o in zip(self.query.constraints, outcomes, strict=True):
            entry: dict[str, Any] = {
                "index": c.index,
                "element": c.element,
                "mode": c.mode,
            }
            if c.match is not None:
                entry["match"] = c.match
            entry.update(
                {
                    "given": dict(c.given),
                    "matched": o.matched,
                    "evidence": dict(o.evidence),
                    "margin": o.margin,
                }
            )
            entries.append(entry)
        return Candidate(
            "match" if not misses else "near_miss",
            self.config.method_id,
            self.config.numeric,
            rec["dates"],
            self._fields(rec),
            tuple(entries),
            tuple({"index": c.index, "element": c.element, "margin": o.margin} for c, o in misses),
            tuple(sorted(flags)),
            self.provenance,
        )

    def _boundary(self, c: Constraint, o: Outcome) -> bool:
        entry = c.entry
        if entry is None or entry.threshold is None:
            return False
        limit = self.config.records.data[entry.threshold].value
        assert isinstance(limit, int | Fraction)
        ev = o.evidence
        if entry.threshold_unit == "nadika":
            got = [ev.get("to_transition_nadika"), ev.get("since_transition_nadika")]
        elif entry.threshold_unit == "degree":
            got = [(ev.get("to_boundary") or {}).get("degrees")]
        else:
            got = [(ev.get("to_boundary") or {}).get("days")]
        return any(g is not None and Fraction(g) <= limit for g in got)

    def _fields(self, rec: Mapping[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {
            k: rec[k] for k in ("weekday", "eras", "sunrise", "sunset", "day_length_nadika")
        }
        planets: dict[str, Any] = {}
        for c in self.query.constraints:
            e = c.element
            if e in ("masa", "day_of_month"):
                out["masa"] = rec["masa"]
            elif e == "sankranti_day":
                out["sankranti"] = rec["sankranti"]
            elif e in elements.ELEMENTS:
                out[e] = rec[e]
            elif e in ("overlap", "at_time"):
                for i in c.of:
                    el = self.query.constraints[i].element
                    out[el] = rec[el]
            elif e in SPANS:
                body = c.body or BODY_OF[e]
                planets[body] = rec["planets"][body]
        if planets:
            out["planets"] = planets
        if out.get("masa") == NOT_IN_PRESET:  # pragma: no cover - compile_query refuses
            out.pop("masa")
        return out


def window_days(first: JDN, last: JDN) -> Callable[[], range]:
    """The JDN values of a window, first to last inclusive."""
    return lambda: range(first.value, last.value + 1)
