"""Invariants of the calendar layer.

Under ``parahita_kerala`` and ``modern_iers`` (the universal
invariants on ``modern_de``) at Kozhikode, over
a window drawn by the seed of ``data/engine_parameters.yaml``: the kṣaya
and vṛddhi flags do not depend on the range or the order in which days
are asked for; the weekday runs on by one each day; every day falls in
one solar month, the months run
in order and each begins on day 1; an era's year changes only on the first
day of its year-start month; a day's occurrences cover it without gap or
overlap. The constructed boundary cases of the assignment rules are unit
tests (``tests/unit/test_calendar_layer.py``). No printed value enters here.
"""

from __future__ import annotations

import random
from functools import cache
from itertools import pairwise
from typing import Any

import pytest

from jyotirganita.calendar import elements
from jyotirganita.calendar.day import OCCURRENCE_ELEMENTS, Calendar
from jyotirganita.core.types import JDN
from jyotirganita.data.engine_parameters import seed
from jyotirganita.methods.compose import REPO
from jyotirganita.methods.presets import load_preset, open_modern_preset, open_preset
from jyotirganita.modern.source import ModernSource

DAYS = 400
DAYS_PER_WEEK = 7
SIGNS = 12


PRESETS = ("parahita_kerala", "modern_iers")
OBSERVER = "kerala/kozhikode"


@cache
def calendar(preset: str) -> Calendar:
    if load_preset(REPO, preset).engine == "modern":
        _, _, cal = open_modern_preset(REPO, preset, OBSERVER)
    else:
        _, _, cal = open_preset(REPO, preset, OBSERVER)
    return cal


@cache
def window(preset: str) -> tuple[JDN, ...]:
    if load_preset(REPO, preset).engine == "modern":
        # a window inside the run's served days (the components' ranges)
        rng = random.Random(seed("seeds.modern_sample"))
        src = calendar(preset).source
        assert isinstance(src, ModernSource)
        span = src.runs_to.days_since(src.runs_from) - DAYS
        start = src.runs_from.plus_days(rng.randrange(0, span))
    else:
        rng = random.Random(seed("seeds.conformance_year"))
        # a day in the Kali years 4900–5200 (the 19th and 20th centuries' almanacs)
        start = calendar(preset).source.runs_from.plus_days(rng.randrange(1_789_700, 1_899_300))
    return tuple(start.plus_days(i) for i in range(DAYS))


@cache
def leaves(preset: str) -> tuple[dict[str, Any], ...]:
    return tuple(calendar(preset).day(d) for d in window(preset))


@pytest.mark.parametrize("preset", PRESETS)
def test_ksaya_and_vrddhi_flags_are_range_independent(preset: str) -> None:
    whole = {d["dates"]["jdn"]: d["flags"] for d in leaves(preset)}
    cal = calendar(preset)
    fresh = Calendar(cal.run, cal.conventions, cal.eras)
    for d in reversed(window(preset)[150:180]):
        assert fresh.day(d)["flags"] == whole[d.value]


@pytest.mark.parametrize("preset", PRESETS)
def test_ksaya_and_vrddhi_follow_the_assigned_labels(preset: str) -> None:
    days = leaves(preset)
    for e in OCCURRENCE_ELEMENTS:
        assigned = [next(o["index"] for o in d[e] if o["assigned"]) for d in days]
        for i in range(1, len(days) - 1):
            flags = days[i]["flags"]
            assert (assigned[i] == assigned[i - 1]) == (f"vriddhi:{e}.{assigned[i]}" in flags)
            has_ksaya = any(f.startswith(f"kshaya:{e}.") for f in flags)
            assert has_ksaya == (assigned[i + 1] not in (assigned[i], _next(e, assigned[i])))


def _next(element: str, index: int) -> int:
    return index % elements.ELEMENTS[element].count + 1


@pytest.mark.parametrize("preset", PRESETS)
def test_the_weekday_runs_on_by_one(preset: str) -> None:
    idx = [d["weekday"]["index"] for d in leaves(preset)]
    for a, b in pairwise(idx):
        assert b == a % DAYS_PER_WEEK + 1


@pytest.mark.parametrize("preset", PRESETS)
def test_months_run_in_order_and_begin_on_day_one(preset: str) -> None:
    masa = [d["masa"] for d in leaves(preset)]
    lengths: list[int] = []
    for a, b in pairwise(masa):
        if b["day"] == 1:
            assert b["rasi_index"] == a["rasi_index"] % SIGNS + 1
            lengths.append(a["day"])
        else:
            assert (b["rasi_index"], b["day"]) == (a["rasi_index"], a["day"] + 1)
    assert lengths and all(29 <= n <= 32 for n in lengths[1:])


@pytest.mark.parametrize("preset", PRESETS)
def test_an_era_year_changes_only_on_its_first_day(preset: str) -> None:
    days = leaves(preset)
    for era in ("kali", "saka", "kollam"):
        for a, b in pairwise(days):
            ya, yb = a["eras"][era], b["eras"][era]
            if yb["year"] != ya["year"]:
                assert yb["year"] == ya["year"] + 1
                assert yb["day"] == 1


@pytest.mark.parametrize("preset", PRESETS)
def test_occurrences_cover_the_day(preset: str) -> None:
    for d in leaves(preset):
        for e in OCCURRENCE_ELEMENTS:
            occ = d[e]
            assert occ[0]["start"] is None and occ[-1]["end"] is None
            for a, b in pairwise(occ):
                assert a["end"] == b["start"] and a["end"] is not None
            assert sum(o["assigned"] for o in occ) == 1
