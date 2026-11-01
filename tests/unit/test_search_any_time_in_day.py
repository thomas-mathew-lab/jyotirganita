"""The search's ``any_time_in_day`` match follows the engine's own motion through the day.

A position constraint matched ``any_time_in_day`` holds when the body's
place at some instant of the civil day, as the API's ``positions``
returns it, lies in a required span; the next day's start belongs to
the next day (review finding C1, ``CHANGELOG.md``; ``docs/search.md``).

**The oracle** (``linear_gati``, every shipped siddhantic preset) is the
intraday model's own definition, worked here in plain
arithmetic without the search's sweep: the place *n* nāḍikās after
sunrise is the sunrise place plus *n*/60 of the day's gati, over the
chord's domain [0, min(*L*, 60)), *L* the day's computed length. A
boundary *b* ahead of the place in the direction of motion is crossed at
*t* = 60·(*b* − λ)/*g* nāḍikās, and the body enters the next span when
*t* falls in that domain. Each crossing time is checked against the
engine's ``positions`` just before and just after it, and the spans the
search reports for the day must be exactly the oracle's.

The window is the one the review reproduced C1 on (1,500 days from JDN
2086382 under ``suryasiddhanta_kerala``, where the gati is the text's
true daily motion at sunrise, not the sunrise difference); the test
reads its first 300 days and asserts that the old reading (the arc from
this sunrise's place to the next sunrise's) differs from the oracle on
some of them, so that it can fail on the fault it guards. Parahita, whose
gati is the sunrise difference, is checked the same way over a shorter
window. ``full_evaluation`` and the modern engine have no chord: their
sweep is checked against the places sampled densely through the day.

No printed value enters here; nothing is typed from memory.
"""

from __future__ import annotations

from collections.abc import Iterator
from fractions import Fraction
from typing import Any

import pytest
from search_kit import config, query

from jyotirganita.core.types import JDN, AngleUnit, FloatDays, Nadika
from jyotirganita.io.record import Sweep, sampled_sweep, signed
from jyotirganita.search.evaluate import Evaluator, span_index, swept
from jyotirganita.search.query import Constraint, compile_query

CIRCLE = Fraction(360)
#: the review's C1 window (findings table, group C)
C1_FIRST = 2086382
#: an instant this close to a crossing lies on the expected side of it (nāḍikās)
EPSILON = Fraction(1, 10**9)
ELEMENTS = {"planet_rasi": 12, "planet_nakshatra": 27, "moon_rasi": 12, "sun_rasi": 12}
#: the Sun and the Moon by their own rāśi elements
BODY_OF = {"moon_rasi": "moon", "sun_rasi": "sun"}


def _deg(arc: Any) -> Fraction:
    return Fraction(arc.to(AngleUnit.DEGREE).value)


def _constraints(cfg: Any, first: int, last: int) -> tuple[Evaluator, list[Constraint]]:
    """One ``any_time_in_day`` constraint per body and position element, for the evidence."""
    planets = ("mercury", "venus", "mars", "jupiter", "saturn", "rahu", "ketu")
    docs: list[dict[str, Any]] = [
        {"element": e, "body": b, "value": 1, "position": True, "match": "any_time_in_day"}
        for b in planets
        for e in ("planet_rasi", "planet_nakshatra")
    ]
    docs += [{"element": e, "value": 1, "match": "any_time_in_day"} for e in BODY_OF]
    q = compile_query(query(docs, first, last), cfg)
    return Evaluator(cfg, q), list(q.constraints)


def _body(c: Constraint) -> str:
    return c.body or BODY_OF[c.element]


def _chord(cfg: Any, body: str, jdn: JDN) -> tuple[Fraction, Fraction, Fraction]:
    """The sunrise place, the gati and the chord's span of ``body`` on ``jdn``, from the engine."""
    eng = cfg.engine
    if body == "ketu":
        lam, g, span = _chord(cfg, "rahu", jdn)
        return (lam + CIRCLE / 2) % CIRCLE, g, span
    inst = eng.instant(jdn, Nadika(0))
    if body == "rahu":
        lam, g = _deg(eng.node(inst).arc), eng.node_gati(jdn)
    else:
        lam, g = _deg(eng.sidereal_longitude(body, inst).arc), _deg(eng.daily_motion(body, jdn))
    nadis = Fraction(eng.model.units.nadis_per_day)
    span = min(cfg.calendar.source.day(jdn).length.value, nadis)
    return lam % CIRCLE, g, span


def _crossings(lam: Fraction, g: Fraction, span: Fraction, count: int) -> Iterator[Fraction]:
    """The crossing times (nāḍikās after sunrise) of the span boundaries inside the chord."""
    if g == 0:
        return
    width = CIRCLE / count
    k = lam // width
    b = (k + 1) * width if g > 0 else k * width
    while True:
        t = 60 * (b - lam) / g
        if not t < span:
            return
        yield t
        b += width if g > 0 else -width


def _oracle(lam: Fraction, g: Fraction, span: Fraction, count: int) -> list[int]:
    """The spans of the chord's places, in the direction of motion (module docstring)."""
    out = [span_index(lam, count)]
    for t in _crossings(lam, g, span, count):
        # past a crossing at t the place is in the span the motion enters
        out.append(span_index(lam + g * (t + EPSILON) / 60, count))
    return out


def _positions_place(ev: Evaluator, body: str, jdn: JDN, t: Fraction) -> Fraction:
    """The body's place ``t`` nāḍikās after sunrise by the engine call ``positions`` makes.

    The API's ``positions`` itself refuses an instant off sunrise under the
    Sūrya-siddhānta, whose latitude is served at sunrise only (review
    finding C5), so its longitude call is made here directly.
    """
    eng = ev.engine
    inst = eng.instant(jdn, Nadika(t))
    if body == "ketu":
        return (_deg(eng.node(inst).arc) + CIRCLE / 2) % CIRCLE
    arc = eng.node(inst) if body == "rahu" else eng.sidereal_longitude(body, inst)
    return _deg(arc.arc) % CIRCLE


def _check_chord_window(preset: str, first: int, days: int) -> int:
    """Assert the search's spans are the oracle's; return the days the old reading differs."""
    cfg = config(preset)
    ev, cs = _constraints(cfg, first, first + days - 1)
    old_differs = 0
    for d in range(first, first + days):
        jdn = JDN(d)
        view = ev.view(jdn)
        for c in cs:
            body = _body(c)
            count = ELEMENTS[c.element]
            lam, g, span = _chord(cfg, body, jdn)
            want = _oracle(lam, g, span, count)
            for t in _crossings(lam, g, span, count):
                # the crossing time is the engine's: positions gives the chord's place on
                # either side of it, in two different spans
                sides = [x for x in (t - EPSILON, t + EPSILON) if x >= 0]
                places = [_positions_place(ev, body, jdn, x) for x in sides]
                assert places == [(lam + g * x / 60) % CIRCLE for x in sides], (d, body, t)
                if len(places) == 2:
                    assert span_index(places[0], count) != span_index(places[1], count)
            got = ev.outcome(c, view)
            assert got.evidence["indices"] == want, (preset, d, body, count)
            assert got.matched == (1 in want), (preset, d, body, count)
            # the old reading: the arc from this sunrise's place to the next sunrise's
            nxt, _, _ = _chord(cfg, body, jdn.plus_days(1))
            old = swept(lam, Sweep(*_closed(signed(nxt - lam))), count)
            old_differs += set(old) != set(want)
    return old_differs


def _closed(step: Fraction) -> tuple[Fraction, Fraction, Fraction, bool]:
    return min(step, Fraction(0)), max(step, Fraction(0)), step, False


def test_suryasiddhanta_matches_the_chord_and_positions() -> None:
    differs = _check_chord_window("suryasiddhanta_kerala", C1_FIRST, 300)
    # the window holds days the sunrise-to-sunrise arc got wrong: the test sees C1
    assert differs > 0


def test_parahita_matches_the_chord_and_positions() -> None:
    _check_chord_window("parahita_kerala", C1_FIRST, 60)


def test_the_next_sunrise_belongs_to_the_next_day() -> None:
    w = Fraction(30)
    # forward to a boundary reached only at the day's end: the span beyond is not entered
    assert swept(Fraction(29), Sweep.chord(Fraction(1)), 12) == (1,)
    assert swept(Fraction(29), Sweep.chord(Fraction(1) + EPSILON), 12) == (1, 2)
    # backward to a boundary: the place at the boundary is in the upper span already
    assert swept(w + 1, Sweep.chord(Fraction(-1)), 12) == (2,)
    assert swept(w + 1, Sweep.chord(-1 - EPSILON), 12) == (2, 1)
    # across 0°
    assert swept(Fraction(359), Sweep.chord(Fraction(2)), 12) == (12, 1)
    # a boundary reached inside the day (not only at its end) is entered
    assert swept(Fraction(29), Sweep(Fraction(0), Fraction(1), Fraction(1, 2), False), 12) == (
        1,
        2,
    )


def test_a_station_inside_a_step_is_found() -> None:
    # a place that rises to 30.0005° a tenth of a day after the start and falls back
    # below 30° by the next sample (a quarter day): no sample lies in the second rāśi
    def at(t: Fraction) -> Fraction:
        return Fraction(299995, 10**4) + Fraction(1, 10) * t * (Fraction(1, 5) - t)

    span = Fraction(1)
    lam = at(Fraction(0))
    sw = sampled_sweep(lam, at, span, Fraction(1, 10**8))
    # the day ends lower than it starts, so the spans are listed falling
    assert swept(lam, sw, 12) == (2, 1)
    assert lam + sw.hi > 30
    # and the same path seen only at the samples would stay in the first
    samples = [at(span * i / 4) for i in range(5)]
    assert {span_index(x, 12) for x in samples} == {1}


def test_a_station_beyond_the_day_is_not_counted() -> None:
    # a place falling toward 30° that turns a tenth of a day after the day's end, just
    # below 30°: the day itself never leaves the second rāśi, though the step that
    # brackets the station reaches into the first
    def at(t: Fraction) -> Fraction:
        return 30 - Fraction(1, 10**4) + Fraction(1, 50) * (t - Fraction(11, 10)) ** 2

    span = Fraction(1)
    lam = at(Fraction(0))
    sw = sampled_sweep(lam, at, span, Fraction(1, 10**8))
    assert at(Fraction(11, 10)) < 30 < at(span)
    assert swept(lam, sw, 12) == (2,)


@pytest.mark.parametrize(
    ("preset", "intraday", "first", "days"),
    [("suryasiddhanta_kerala", "full_evaluation", C1_FIRST, 3), ("modern_iers", None, 2460000, 20)],
)
def test_sampled_sweep_covers_the_places_through_the_day(
    preset: str, intraday: str | None, first: int, days: int
) -> None:
    """Every place sampled densely through the day lies within the sweep."""
    cfg = config(preset, None, intraday)
    ev, _ = _constraints(cfg, first, first + days)
    pos, eng = ev.positions, cfg.engine
    for d in range(first, first + days):
        jdn = JDN(d)
        for body in ("moon", "mercury", "mars"):
            lam = pos.lon(body, jdn)
            sw = pos.sweep(body, jdn)
            if intraday:
                nadis = Fraction(eng.model.units.nadis_per_day)
                span = min(cfg.calendar.source.day(jdn).length.value, nadis)
                at = [eng.evaluate(jdn, Nadika(span * i / 60))[1][body] for i in range(1, 60)]
                tol = Fraction(0)
            else:
                start = eng.day_bounds(jdn)[0]
                length = (eng.day_bounds(jdn.plus_days(1))[0] - start).value
                at = [
                    _deg(eng.sidereal_at(body, start + FloatDays(length * i / 60)).arc)
                    for i in range(1, 60)
                ]
                # the day's start place is read through the civil instant, a round trip
                tol = Fraction(1, 10**9)
            offs = [signed(x - lam) for x in at]
            assert all(sw.lo - tol <= o <= sw.hi + tol for o in offs), (preset, d, body)
