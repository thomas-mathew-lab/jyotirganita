"""Invariants of the inverse search.

**Staged equals brute.** Under every method the CI tier serves (one
preset each, ``search_kit.METHOD_PRESETS``), on twenty windows of
:data:`LENGTH` days drawn by ``seeds.search_windows``, each queried with
``near_miss`` absent and with ``max_misses: 1``, the staged path returns
exactly the candidates of the brute path, both classes, compared without
their provenance; each staged run prunes on planets (its step record
loads and describes the run).

**Multi-year windows.** The twenty windows are shorter than the planet
stage's sampling step for Jupiter and Saturn, so one window of
:data:`YEARS_LENGTH` days per method (:data:`SLOW_METHODS`) runs
a query of the day's own Jupiter rāśi (``at_sunrise``), Saturn rāśi
(``any_time_in_day``) and weekday, with and without ``near_miss``, staged
against brute.

**Bound-neutral overrides.** The planet stage keeps pruning under an
override of a key in ``search/stages.py`` ``BOUND_NEUTRAL`` (the
conventions, the output selection, the clock), since none moves a body;
under one override of each such key (:data:`NEUTRAL_RUNS`) a query of
the day's own Jupiter rāśi and weekday returns, staged, exactly the brute
path's candidates, with the planet stage on (the condition
on ``BOUND_NEUTRAL``).

**Round trip.** In each window a day drawn by the same seed gives its own
elements (``search_kit.own_elements``); a query of one element from each
group (era, solar, weekday, planet, lunar) as ``require`` and three more
as ``report`` returns that day as a ``match``; with one ``require``
element miswritten and ``max_misses: 1`` it returns the day as a
``near_miss`` naming that element, and with ``near_miss`` absent it does
not return it. Where the miswritten element is ``era_year``, the
slipped year lies outside the years the window spans, so the query is
refused naming that constraint's value. Every window is
evaluated by both paths, so the round trip holds on each.

No printed value enters here; none of this is evidence for a method.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from functools import cache
from typing import Any

import pytest
from modern_kit import records
from search_kit import (
    GROUPS,
    METHOD_PRESETS,
    OBSERVER,
    REPO,
    config,
    group_of,
    miswrite,
    own_elements,
    query,
    window_at,
)

from jyotirganita.data.engine_parameters import seed
from jyotirganita.search import SearchError, open_search, search
from jyotirganita.search.results import comparable
from jyotirganita.search.stages import BOUND_NEUTRAL

WINDOWS = 20
LENGTH = 35
REPORTED = 3
#: three years of civil days
YEARS_LENGTH = 3 * 365 + 1
SLOW_METHODS = ("parahita", "drgganita")
#: one override of each bound-neutral --set key, each differing from its preset's value
NEUTRAL_RUNS: tuple[tuple[str, dict[str, str]], ...] = (
    ("parahita", {"conventions.month_rule": "following_day"}),
    ("parahita", {"conventions.era.kollam.year_start": "kanya"}),
    ("parahita", {"output.elements": "tithi,nakshatra"}),
    ("parahita", {"output.scripts": "latin,malayalam"}),
    ("modern_de", {"time_standard": "lmt"}),
)


@cache
def draws() -> dict[str, list[dict[str, Any]]]:
    """Every window's draws, made before any is evaluated, in a fixed order."""
    rng = random.Random(seed("seeds.search_windows"))
    return {
        method: [
            {
                "window": rng.random(),
                "day": rng.random(),
                "pick": {g: rng.random() for g in GROUPS},
                "report": rng.random(),
                "slip": rng.random(),
            }
            for _ in range(WINDOWS)
        ]
        for method in METHOD_PRESETS
    }


def _pick(items: Sequence[Any], u: float) -> Any:
    return items[int(u * len(items))]


def _query_of(
    own: Sequence[Mapping[str, Any]], d: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], int]:
    """The require constraints (one per group) and reported ones; the index of the slip."""
    required = []
    for g in GROUPS:
        options = [c for c in own if group_of(c) == g]
        required.append({**_pick(options, d["pick"][g]), "mode": "require"})
    rest = [
        c for c in own if c not in [{k: v for k, v in r.items() if k != "mode"} for r in required]
    ]
    rest = [c for c in rest if c["element"] != "sankranti_day"]
    start = int(d["report"] * len(rest))
    reported = [{**c, "mode": "report"} for c in (rest[start:] + rest[:start])[:REPORTED]]
    slip = int(d["slip"] * len(required))
    return required + reported, slip


def _both(method: str, d: Mapping[str, Any]) -> list[Any]:
    """Staged equals brute on one window, without and with ``near_miss``; the round trip."""
    cfg = config(METHOD_PRESETS[method])
    first, last = window_at(cfg, d["window"], LENGTH)
    day = first + int(d["day"] * LENGTH)
    constraints, slip = _query_of(own_elements(cfg, day), d)
    where = f"{method} JDN {first}-{last} day {day}"
    plain = query(constraints, first, last)
    exact = list(search(cfg, plain))
    assert [comparable(c) for c in exact] == [
        comparable(c) for c in search(cfg, plain, brute=True)
    ], where
    found = {c.jdn: c for c in exact}
    assert day in found and found[day].cls == "match", where
    assert found[day].provenance["search"]["planet_pruning"] == "on", where
    slipped = list(constraints)
    slipped[slip] = miswrite(constraints[slip])
    near = query(slipped, first, last, near_miss={"max_misses": 1})
    if slipped[slip]["element"] == "era_year":
        # a year no day of the window carries is refused, not a near miss
        with pytest.raises(SearchError) as info:
            search(cfg, near)
        assert info.value.field == f"constraints[{slip}].value", where
        return exact
    loose = list(search(cfg, near))
    assert [comparable(c) for c in loose] == [
        comparable(c) for c in search(cfg, near, brute=True)
    ], where
    found = {c.jdn: c for c in loose}
    assert day in found and found[day].cls == "near_miss", where
    assert [m["index"] for m in found[day].misses] == [slip], where
    assert day not in {c.jdn for c in search(cfg, query(slipped, first, last))}, where
    return exact


def _record_windows(record_property: Any, method: str, picks: Sequence[float], length: int) -> None:
    """The windows, seed and classes, for reports/search_invariants.md (no compared values)."""
    cfg = config(METHOD_PRESETS[method])
    record_property("windows", [list(window_at(cfg, u, length)) for u in picks])
    record_property("seed", "seeds.search_windows")
    record_property("classes", ["match", "near_miss"])


@pytest.mark.parametrize("method", list(METHOD_PRESETS))
def test_staged_equals_brute_and_round_trip(method: str, record_property: Any) -> None:
    _record_windows(record_property, method, [d["window"] for d in draws()[method]], LENGTH)
    for d in draws()[method]:
        _both(method, d)


@pytest.mark.parametrize("method", SLOW_METHODS)
def test_multi_year_window_with_slow_planets(method: str, record_property: Any) -> None:
    cfg = config(METHOD_PRESETS[method])
    d = draws()[method][1]
    _record_windows(record_property, method, [d["window"]], YEARS_LENGTH)
    first, last = window_at(cfg, d["window"], YEARS_LENGTH)
    day = first + int(d["day"] * YEARS_LENGTH)
    own = own_elements(cfg, day)
    rasi = {c["body"]: c for c in own if c["element"] == "planet_rasi"}
    weekday = next(c for c in own if c["element"] == "weekday")
    constraints = [
        {**rasi["jupiter"], "match": "at_sunrise"},
        {**rasi["saturn"], "match": "any_time_in_day"},
        weekday,
    ]
    where = f"{method} JDN {first}-{last} day {day}"
    for doc in (
        query(constraints, first, last),
        query(
            [miswrite(constraints[0]), *constraints[1:]], first, last, near_miss={"max_misses": 1}
        ),
    ):
        staged = list(search(cfg, doc))
        assert [comparable(c) for c in staged] == [
            comparable(c) for c in search(cfg, doc, brute=True)
        ], where
        found = {c.jdn: c for c in staged}
        assert day in found, where
        assert found[day].provenance["search"]["planet_pruning"] == "on", where
        assert found[day].cls == ("near_miss" if "near_miss" in doc else "match"), where


def test_classes_never_merge() -> None:
    """A full match stays ``match`` under ``max_misses: 1``; a near miss is never a match."""
    method = "parahita"
    cfg = config(METHOD_PRESETS[method])
    d = draws()[method][0]
    first, last = window_at(cfg, d["window"], LENGTH)
    day = first + int(d["day"] * LENGTH)
    constraints, _ = _query_of(own_elements(cfg, day), d)
    exact = list(search(cfg, query(constraints, first, last)))
    loose = list(search(cfg, query(constraints, first, last, near_miss={"max_misses": 1})))
    assert {c.jdn for c in exact} == {c.jdn for c in loose if c.cls == "match"}
    assert all(c.cls == "match" for c in exact)
    assert all(not c.misses for c in loose if c.cls == "match")
    assert all(len(c.misses) == 1 for c in loose if c.cls == "near_miss")


def test_every_bound_neutral_prefix_has_a_run() -> None:
    keys = [k for _, sets in NEUTRAL_RUNS for k in sets]
    assert all(any(k.startswith(p) for k in keys) for p in BOUND_NEUTRAL)
    assert all(k.startswith(BOUND_NEUTRAL) for k in keys)


@pytest.mark.parametrize(("method", "sets"), NEUTRAL_RUNS, ids=lambda v: str(v))
def test_staged_equals_brute_under_a_bound_neutral_override(
    method: str, sets: dict[str, str]
) -> None:
    cfg = open_search(REPO, METHOD_PRESETS[method], OBSERVER, sets=sets, records=records())
    assert cfg.overrides == sets
    d = draws()[method][2]
    first, last = window_at(cfg, d["window"], LENGTH)
    day = first + int(d["day"] * LENGTH)
    own = own_elements(cfg, day)
    rasi = next(c for c in own if c["element"] == "planet_rasi" and c["body"] == "jupiter")
    weekday = next(c for c in own if c["element"] == "weekday")
    doc = query([{**rasi, "match": "at_sunrise"}, weekday], first, last)
    where = f"{method} {sets} JDN {first}-{last} day {day}"
    staged = list(search(cfg, doc))
    assert [comparable(c) for c in staged] == [
        comparable(c) for c in search(cfg, doc, brute=True)
    ], where
    found = {c.jdn: c for c in staged}
    assert day in found and found[day].cls == "match", where
    assert found[day].provenance["search"]["planet_pruning"] == "on", where
