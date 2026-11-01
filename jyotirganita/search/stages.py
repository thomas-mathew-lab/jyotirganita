"""The staged path: conservative pruning, cheap stages first.

:func:`staged` returns the candidates :func:`~jyotirganita.search.brute.brute`
returns, by discarding days that cannot be candidates before the full
evaluation. Each stage tests the ``require`` constraints of its kind on
the days still alive and counts, per day, the constraints *shown* to
fail; a day is dropped when that count exceeds the query's
``max_misses`` (zero without ``near_miss``). The survivors go through
:meth:`Evaluator.evaluate`, which assigns the class and the margins. A
stage may keep a day the full evaluation rejects; it never shows a
constraint to fail that holds. The stages, in order:

1. **era** — ``era_year`` from the year boundaries, found by bisecting
   the same :func:`~jyotirganita.core.eras.era_year` the evaluation calls
   (the year is a non-decreasing step function of the day, so a span
   whose two ends share a year is that year throughout); ``era_day`` by
   arithmetic from the day count at the window's first day (the count
   advances by one a civil day; checked at the last day, and evaluated
   per day if it does not).
2. **solar** — ``masa`` and ``day_of_month`` from the month starts of the
   preset's month stream (:meth:`MonthStream.start`, the function
   :meth:`MonthStream.month_of` takes its first days from); ``sun_rasi``,
   ``ayana`` and ``sankranti_day`` from the saṅkrānti days of the same
   stream (:meth:`MonthStream.sankranti`). A day within
   :data:`GUARD_DAYS` of a month start or a saṅkrānti day is kept
   whatever its month or rāśi, since there the stream's day and the
   evaluation's reading of it (the Sun's place at the day's start, an
   ending found by proportional parts) can differ. Without a month stream
   (a text-only preset) these constraints are evaluated per day on the
   survivors of the planet stage.
3. **weekday** — arithmetic from the weekday of the window's first day
   (checked at the last day, as for ``era_day``).
4. **planets** — ``planet_rasi`` and ``planet_nakshatra`` from positions
   sampled every ``step_days`` days, with the guard band of the body's
   step bound: the derived record ``derived.search.step_bound.<method>.<body>``
   (``data/derived.py``) times ``search.safety_factor``. With *B* that
   product, every sunrise-to-sunrise step and every day's motion is at
   most *B*, so the body's place on day *d* lies within |*d* − *s*|·*B*
   of its place on a sampled day *s*; a day is kept when the place on
   each of the two samples around it lies within that distance of a
   required span (one *B* more for ``any_time_in_day``, whose places
   through the day lie within the day's motion of its start).
   ``step_days`` is the largest whole number
   with ``step_days``·*B* below the span (a rāśi or a nakṣatra). The
   stage runs only when the record serves the run: its method, the
   procedures and intraday model it was scanned under (``linear_gati``,
   or the modern presets it followed), the digest of the files the run
   loads, the record's hash ``current``, and no override that moves a
   planet (a convention, the output selection or the clock does not:
   ``BOUND_NEUTRAL``). Otherwise the
   planet constraints are evaluated per day on the survivors, and the
   provenance says why. A window beyond the record's scanned range is
   refused when the stage would run (the brute path has no such limit).
5. **lunar** — ``tithi``, ``nakshatra``, ``yoga``, ``karana`` and
   ``moon_rasi`` evaluated per day on the survivors (the Moon is never
   pruned by step).
6. **last** — ``overlap``, ``at_time``, ``eclipse``, and any constraint
   no earlier stage tested, evaluated per day.

The per-day tests of stages 5 and 6 are :meth:`Evaluator.holds`, the
test the full evaluation makes. Each candidate's provenance carries the
pruning summary: per stage the constraints it tested and the days in and
out, the derived records used and the planet stage's state.

No ``math``, ``numpy`` or ``decimal`` import.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from jyotirganita.calendar import elements
from jyotirganita.calendar.months import SEARCH_DAYS, MonthStream
from jyotirganita.core.eras import NotInRange, era_year
from jyotirganita.core.types import JDN
from jyotirganita.data import engine_parameters
from jyotirganita.data.derived import DerivedRecord, hash_status, load_derived, step_bound_key
from jyotirganita.search.brute import search_provenance
from jyotirganita.search.config import SearchConfig
from jyotirganita.search.errors import SearchError
from jyotirganita.search.evaluate import (
    CIRCLE,
    DAYS_PER_WEEK,
    NODES,
    SIGNS,
    SPANS,
    Evaluator,
    to_spans,
)
from jyotirganita.search.query import Constraint, Query
from jyotirganita.search.results import Candidate
from jyotirganita.siddhantic.engine import LINEAR_GATI

__all__ = ["GUARD_DAYS", "planet_plan", "staged"]

#: days either side of a month start or a saṅkrānti day kept whatever the stream says;
#: structural: a kept day goes on to the exact evaluation
GUARD_DAYS = 1
#: days beyond the window over which month starts and saṅkrāntis are enumerated;
#: structural: wider than a month, a wider pad adds months that touch no day (§F)
MONTH_PAD = 60
MODERN_INTRADAY = "modern.at_instant"
#: the modern components a step record fixes (tools/step_scan.py MODERN_PROCEDURES)
MODERN_PROCEDURES = ("kernel", "precession", "nutation", "ayanamsa", "observer_frame", "node")
PLANET_ELEMENTS = ("planet_rasi", "planet_nakshatra")
SUN_ELEMENTS = ("sun_rasi", "ayana", "sankranti_day")
MONTH_ELEMENTS = ("masa", "day_of_month")
LUNAR_ELEMENTS = (*elements.ELEMENTS, "moon_rasi")

Maybe = Callable[[int], bool]
IntOf = Callable[[int], int]
#: a run test: the day, the run's first day, the run's rāśi
RunOk = Callable[[int, int, int], bool]


def _record_body(body: str) -> str:
    return "node" if body in NODES else body


def _next_rasi(r: int) -> int:
    return r % SIGNS + 1


# --- the planet stage's eligibility --------------------------------------------------------


@dataclass(frozen=True)
class PlanetPlan:
    """Whether the planet stage runs, on which records, and why not when it does not."""

    records: Mapping[str, DerivedRecord]
    reason: str | None

    @property
    def runs(self) -> bool:
        return self.reason is None


def _procedures_of(config: SearchConfig) -> dict[str, Any]:
    if config.kind == "modern":
        prov = config.run.provenance
        return {k: prov[k] for k in MODERN_PROCEDURES}
    return {
        slot: str(rec.raw.get("procedure", rec.kind))
        for slot, rec in sorted(config.run.resolved.procedures.items())
    }


def _serves(config: SearchConfig, rec: DerivedRecord) -> str | None:
    """Why ``rec`` does not serve the run, or ``None`` when it does (module docstring, stage 4)."""
    status = hash_status(config.repo, rec)
    if status != "current":
        return f"{rec.key} is {status}"
    if rec.parameters_sha256 != config.run.provenance["parameters_sha256"]:
        return f"{rec.key} was scanned on other files (parameters_sha256 differs)"
    procs = _procedures_of(config)
    if config.kind == "modern":
        if rec.intraday != MODERN_INTRADAY or config.preset.id not in rec.procedures.get(
            "presets", ()
        ):
            return f"{rec.key} was not scanned under the preset {config.preset.id}"
        theirs = {k: rec.procedures.get(k) for k in MODERN_PROCEDURES}
    else:
        if rec.intraday != LINEAR_GATI:
            return f"{rec.key} was scanned under {rec.intraday}"
        theirs = dict(rec.procedures)
    if theirs != procs:
        return f"{rec.key} was scanned under other procedures"
    return None


#: overrides that leave a planet's daily positions as the step bound was scanned: the
#: conventions (month rule, era year starts), the output selection and the clock
BOUND_NEUTRAL = ("conventions.", "output.", "time_standard")


def planet_plan(config: SearchConfig, query: Query) -> PlanetPlan:
    """The planet stage's records, or the reason it does not run (module docstring, stage 4)."""
    bodies = sorted(
        {_record_body(c.body) for c in query.required if c.element in PLANET_ELEMENTS and c.body}
    )
    if not bodies:
        return PlanetPlan({}, "no require constraint on a planet")
    moving = sorted(k for k in config.overrides if not k.startswith(BOUND_NEUTRAL))
    if moving:
        return PlanetPlan({}, f"the run overrides {moving}")
    if config.kind != "modern" and config.intraday != LINEAR_GATI:
        return PlanetPlan({}, f"the run's intraday model is {config.intraday}, not {LINEAR_GATI}")
    derived = load_derived(config.repo)
    out: dict[str, DerivedRecord] = {}
    for body in bodies:
        rec = derived.get(step_bound_key(config.method_id, body))
        if rec is None:
            return PlanetPlan({}, f"no derived record {step_bound_key(config.method_id, body)}")
        why = _serves(config, rec)
        if why is not None:
            return PlanetPlan({}, why)
        out[body] = rec
    return PlanetPlan(out, None)


def _check_range(plan: PlanetPlan, query: Query) -> None:
    for rec in plan.records.values():
        if query.first.value < rec.from_jdn or query.last.value > rec.to_jdn:
            raise SearchError(
                "window",
                f"JDN {query.first.value}–{query.last.value} leaves the range the step bound "
                f"{rec.key} was scanned over (JDN {rec.from_jdn}–{rec.to_jdn}); the staged "
                "search prunes on it and refuses the window; the brute path has no such limit",
            )


# --- the day set ------------------------------------------------------------------------------


@dataclass
class _Days:
    """The window's days with each day's count of require constraints shown to fail."""

    first: int
    misses: list[int]
    allowance: int
    summary: list[dict[str, Any]] = field(default_factory=list)

    def alive(self) -> list[int]:
        return [self.first + i for i, m in enumerate(self.misses) if m <= self.allowance]

    def stage(
        self, name: str, tests: Sequence[tuple[Constraint, Maybe]], note: Mapping[str, Any]
    ) -> None:
        if not tests:
            return
        alive = self.alive()
        for j in alive:
            i = j - self.first
            for _, maybe in tests:
                if not maybe(j):
                    self.misses[i] += 1
                    if self.misses[i] > self.allowance:
                        break
        entry: dict[str, Any] = {
            "stage": name,
            "constraints": [c.index for c, _ in tests],
            "days_in": len(alive),
            "days_out": len(self.alive()),
        }
        entry.update(note)
        self.summary.append(entry)


# --- stage 1: era -------------------------------------------------------------------------------


def _steps(f: Callable[[int], Any], first: int, last: int) -> list[tuple[int, Any]]:
    """The (first day, value) runs of the non-decreasing step function ``f`` on [first, last]."""
    out: list[tuple[int, Any]] = [(first, f(first))]
    stack = [(first, out[0][1], last, f(last))]
    found: list[tuple[int, Any]] = []
    while stack:
        lo, flo, hi, fhi = stack.pop()
        if flo == fhi:
            continue
        if hi - lo == 1:
            found.append((hi, fhi))
            continue
        mid = (lo + hi) // 2
        fm = f(mid)
        stack.append((lo, flo, mid, fm))
        stack.append((mid, fm, hi, fhi))
    out.extend(sorted(found))
    return out


def _lookup(runs: Sequence[tuple[int, Any]]) -> Callable[[int], Any]:
    starts = [s for s, _ in runs]
    return lambda j: runs[bisect_right(starts, j) - 1][1]


def _era_year_test(ev: Evaluator, c: Constraint, query: Query) -> Maybe:
    assert c.era is not None and c.year_start is not None
    record = ev.calendar.eras[c.era].era
    stream = ev.calendar.year_stream(c.era, c.year_start)

    def year(j: int) -> int | None:
        y = era_year(record, JDN(j), c.year_start or "", stream)
        return None if isinstance(y, NotInRange) else y.year

    at = _lookup(_steps(year, query.first.value, query.last.value))

    def maybe(j: int) -> bool:
        y = at(j)
        return y is not None and c.holds_number(y)

    return maybe


def _linear(
    ev: Evaluator, query: Query, of: Callable[[Any], int], cycle: int | None
) -> IntOf | None:
    """``j ↦ of(day j)`` by arithmetic from the window's first day, or ``None`` if it is not."""
    first, last = query.first, query.last
    v0 = of(ev.view(first))
    n = last.days_since(first)
    expect = v0 + n if cycle is None else (v0 - 1 + n) % cycle + 1
    if of(ev.view(last)) != expect:
        return None
    start = first.value

    def at(j: int) -> int:
        return v0 + (j - start) if cycle is None else (v0 - 1 + (j - start)) % cycle + 1

    return at


def _number_test(c: Constraint, f: IntOf) -> Maybe:
    return lambda j: c.holds_number(f(j))


def _cycle_test(c: Constraint, f: IntOf) -> Maybe:
    return lambda j: f(j) in c.values


def _rasi_ok(c: Constraint) -> RunOk:
    return lambda j, s, r: r in c.values


def _day_ok(c: Constraint) -> RunOk:
    return lambda j, s, r: c.holds_number(j - s + 1)


def _today_or_next(label: Maybe) -> Maybe:
    return lambda j: label(j) or label(j + 1)


def _era_tests(
    ev: Evaluator, query: Query, cs: Sequence[Constraint]
) -> list[tuple[Constraint, Maybe]]:
    out: list[tuple[Constraint, Maybe]] = []
    count: IntOf | None = None
    for c in cs:
        if c.element == "era_year":
            out.append((c, _era_year_test(ev, c, query)))
        else:
            count = count or _linear(ev, query, ev.count, None)
            if count is None:
                out.append((c, _exact(ev, c)))
            else:
                out.append((c, _number_test(c, count)))
    return out


def _exact(ev: Evaluator, c: Constraint) -> Maybe:
    return lambda j: ev.holds(c, ev.view(JDN(j)))


# --- stage 2: solar -----------------------------------------------------------------------------


def _entries(ms: MonthStream, rasi: int, query: Query, runs_from: JDN) -> list[int]:
    lo = ms.mean.entries(rasi, query.first.plus_days(-MONTH_PAD))
    hi = ms.mean.entries(rasi, query.last.plus_days(MONTH_PAD))
    return [
        k
        for k in range(lo, hi + 1)
        if ms.mean.entry_day(rasi, k).days_since(runs_from) > SEARCH_DAYS
    ]


def _month_starts(
    ms: MonthStream, rasis: Sequence[int], query: Query, runs_from: JDN
) -> list[tuple[int, int]]:
    """The (first day, rāśi) of the months of ``rasis`` around the window, in day order."""
    return sorted(
        (ms.start(r, k).value, r) for r in rasis for k in _entries(ms, r, query, runs_from)
    )


def _sankrantis(
    ms: MonthStream, rasis: Sequence[int], query: Query, runs_from: JDN
) -> list[tuple[int, int]]:
    """The (civil day, rāśi entered) of the saṅkrāntis of ``rasis`` around the window."""
    out = set()
    for r in rasis:
        for k in _entries(ms, r, query, runs_from):
            out.add((ms.sankranti(r, ms.mean.entry_day(r, k)).day.value, r))
    return sorted(out)


def _runs_test(marks: Sequence[tuple[int, int]], ok: RunOk, lag: int) -> Maybe:
    """A test on the run of ``marks`` a day falls in, keeping days near a mark.

    A day *j* falls in the run of the last mark at or before *j* − ``lag``
    (``lag`` 0 for a month, which begins on its first day; 1 for a
    saṅkrānti, after which the next day starts in the new rāśi);
    ``ok(j, mark, rasi)`` decides it. A day before the first mark, or
    within :data:`GUARD_DAYS` of the start of a run, is kept.
    """
    days = [d + lag for d, _ in marks]

    def maybe(j: int) -> bool:
        i = bisect_right(days, j) - 1
        near = [days[x] for x in (i, i + 1) if 0 <= x < len(days)]
        if any(abs(j - d) <= GUARD_DAYS for d in near):
            return True
        if i < 0:
            return True
        return ok(j, days[i], marks[i][1])

    return maybe


def _solar_tests(
    ev: Evaluator, query: Query, cs: Sequence[Constraint]
) -> tuple[list[tuple[Constraint, Maybe]], list[Constraint], dict[str, Any]]:
    """The solar stage's tests, the constraints left to per-day evaluation, and a note."""
    ms = ev.calendar.months
    if ms is None:
        return [], list(cs), {"not_pruned": "the preset has no month stream"}
    runs_from = ev.config.runs_from
    tests: list[tuple[Constraint, Maybe]] = []
    left: list[Constraint] = []
    try:
        month_rasis: set[int] = set()
        for c in cs:
            if c.element == "day_of_month":
                month_rasis.update(range(1, SIGNS + 1))
            elif c.element == "masa":
                month_rasis.update(c.values)
                month_rasis.update(_next_rasi(r) for r in c.values)
        starts = _month_starts(ms, sorted(month_rasis), query, runs_from) if month_rasis else []
        sun_rasis: set[int] = set()
        for c in cs:
            if c.element in ("sun_rasi", "ayana"):
                sun_rasis.update(c.values)
                sun_rasis.update(_next_rasi(r) for r in c.values)
            elif c.element == "sankranti_day":
                sun_rasis.update(c.values)
        sank = _sankrantis(ms, sorted(sun_rasis), query, runs_from) if sun_rasis else []
    except ValueError as e:  # a stream that cannot be searched near the window
        return [], list(cs), {"not_pruned": f"the month stream: {e}"}
    for c in cs:
        if c.element == "masa":
            tests.append((c, _runs_test(starts, _rasi_ok(c), 0)))
        elif c.element == "day_of_month":
            tests.append((c, _runs_test(starts, _day_ok(c), 0)))
        elif c.element == "sankranti_day":
            tests.append((c, _near_test([d for d, r in sank if r in c.values])))
        elif c.match == "at_sunrise":
            tests.append((c, _runs_test(sank, _rasi_ok(c), 1)))
        elif c.match == "any_time_in_day":
            # the day's places run toward the next day's: the rāśi of day j or of day j + 1
            # (where the chord ends in another rāśi than the next sunrise's, day j lies
            # within GUARD_DAYS of the stream's saṅkrānti and is kept)
            tests.append((c, _today_or_next(_runs_test(sank, _rasi_ok(c), 1))))
        else:  # pragma: no cover - the profiles' match modes
            left.append(c)
    return tests, left, {}


def _near_test(days: Sequence[int]) -> Maybe:
    """Keep a day within :data:`GUARD_DAYS` of one of ``days`` (sorted)."""

    def maybe(j: int) -> bool:
        i = bisect_right(days, j)
        return any(abs(j - d) <= GUARD_DAYS for d in days[max(i - 1, 0) : i + 1])

    return maybe


# --- stage 4: planets ---------------------------------------------------------------------------


def _planet_test(
    ev: Evaluator, c: Constraint, rec: DerivedRecord, factor: Fraction, query: Query
) -> tuple[Maybe, dict[str, Any]]:
    assert c.body is not None
    position: object = True if c.position is None else c.position
    count = SPANS[c.element]
    width = CIRCLE / count
    bound = rec.value * factor
    step = max(1, int(-(-width // bound)) - 1)
    first, last = query.first.value, query.last.value
    samples = list(range(first, last + 1, step))
    if samples[-1] != last:
        samples.append(last)
    dist = {s: abs(to_spans(ev.lon(c.body, JDN(s), position), c.values, count)) for s in samples}
    extra = bound if c.match == "any_time_in_day" else Fraction(0)

    def maybe(j: int) -> bool:
        i = bisect_right(samples, j) - 1
        lo = samples[i]
        if lo == j:
            return dist[lo] <= extra
        hi = samples[i + 1]
        return dist[lo] <= (j - lo) * bound + extra and dist[hi] <= (hi - j) * bound + extra

    note = {
        "constraint": c.index,
        "body": c.body,
        "derived": rec.key,
        "bound_deg_per_day": f"{bound.numerator}/{bound.denominator}",
        "step_days": step,
        "samples": len(samples),
    }
    return maybe, note


# --- the staged path ----------------------------------------------------------------------------


def staged(config: SearchConfig, query: Query) -> Iterator[Candidate]:
    """The candidates of ``query`` by the staged path (module docstring).

    Every refusal (a window beyond a step bound's scanned range) is raised
    here, before the iterator is returned.
    """
    plan = planet_plan(config, query)
    if plan.runs:
        _check_range(plan, query)
    return _run(config, query, plan)


def _run(config: SearchConfig, query: Query, plan: PlanetPlan) -> Iterator[Candidate]:
    ev = Evaluator(config, query)
    n = query.last.days_since(query.first) + 1
    days = _Days(query.first.value, [0] * n, query.max_misses)
    req = query.required
    done: set[int] = set()

    def of(kinds: Sequence[str]) -> list[Constraint]:
        return [c for c in req if c.element in kinds and c.index not in done]

    era = of(("era_year", "era_day"))
    days.stage("era", _era_tests(ev, query, era), {})
    done.update(c.index for c in era)

    solar = of((*MONTH_ELEMENTS, *SUN_ELEMENTS))
    tests, _left, note = _solar_tests(ev, query, solar)  # what is left is tested in "last"
    days.stage("solar", tests, note)
    done.update(c.index for c, _ in tests)

    week = of(("weekday",))
    if week:
        wd = _linear(ev, query, lambda v: v.weekday, DAYS_PER_WEEK)
        wtests = [(c, _exact(ev, c) if wd is None else _cycle_test(c, wd)) for c in week]
        days.stage("weekday", wtests, {})
        done.update(c.index for c in week)

    planets = of(PLANET_ELEMENTS)
    if planets and plan.runs:
        factor = engine_parameters.load()["search.safety_factor"].value
        assert isinstance(factor, Fraction | int)
        ptests: list[tuple[Constraint, Maybe]] = []
        notes = []
        for c in planets:
            assert c.body is not None
            maybe, pn = _planet_test(
                ev, c, plan.records[_record_body(c.body)], Fraction(factor), query
            )
            ptests.append((c, maybe))
            notes.append(pn)
        days.stage("planets", ptests, {"bounds": notes})
        done.update(c.index for c in planets)

    lunar = of(LUNAR_ELEMENTS)
    days.stage("lunar", [(c, _exact(ev, c)) for c in lunar], {})
    done.update(c.index for c in lunar)

    rest = [c for c in req if c.index not in done]
    days.stage("last", [(c, _exact(ev, c)) for c in rest], {})

    survivors = days.alive()
    stages = [*days.summary, {"stage": "full_evaluation", "days_in": len(survivors)}]
    if not any(c.element in PLANET_ELEMENTS for c in query.constraints):
        pruning = None
    elif plan.runs:
        pruning = "on"
    else:
        pruning = f"off: {plan.reason}"
    ev.provenance = search_provenance(
        config,
        query,
        "staged",
        stages,
        derived=sorted(r.key for r in plan.records.values()) if plan.runs else (),
        planets=pruning,
    )
    for j in survivors:
        cand = ev.evaluate(JDN(j))
        if cand is not None:
            yield cand
