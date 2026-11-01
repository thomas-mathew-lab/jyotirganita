"""The conformance items of the inverse search.

The items: the forward–
inverse round trip under every shipped preset, so every registered
method (a day drawn by ``seeds.search_windows`` gives its own elements,
``moon_rasi`` among them; fed back as a query they return that day as a
``match``, under ``kerala_default`` and under ``strict_sunrise``, staged
and brute alike); the name vocabulary generated from ``names.yaml``
(every id and listed Latin spelling resolves to its index, case
ignored; anything else is refused naming the nearest ids); a
``near_miss`` query's two classes reported apart in the JSON Lines
output. Staged equals brute on twenty windows per method is
``tests/invariants/test_search_invariants.py``. No printed value enters
here; the search has no authority tests yet.
"""

from __future__ import annotations

import io
import json
import random
from collections.abc import Mapping
from functools import cache
from typing import Any

import pytest
from search_kit import REPO, config, own_elements, query, served_span

from jyotirganita.core.types import JDN
from jyotirganita.data.engine_parameters import seed
from jyotirganita.methods.presets import load_preset, preset_ids
from jyotirganita.methods.registry import load_registry
from jyotirganita.search import SearchError, search
from jyotirganita.search.evaluate import Evaluator
from jyotirganita.search.query import compile_query
from jyotirganita.search.results import comparable, write_jsonl

SHIPPED = preset_ids(REPO)
#: presets whose runs need the DE441 kernel
DE441 = ("modern_antiquity",)
PRESETS = [pytest.param(p, marks=pytest.mark.de441) if p in DE441 else p for p in SHIPPED]
HALF_WINDOW = 3


@cache
def _days() -> dict[str, float]:
    rng = random.Random(seed("seeds.search_windows"))
    return {p: rng.random() for p in SHIPPED}


def _day(preset: str) -> int:
    lo, hi = served_span(config(preset))
    return lo + int(_days()[preset] * (hi - lo))


def test_every_registered_method_has_a_shipped_preset() -> None:
    from jyotirganita.data.datum import context_for

    reg = load_registry(
        REPO / "jyotirganita" / "methods" / "registry.yaml", context_for(REPO).sources
    )
    assert set(reg) <= {str(load_preset(REPO, p).method) for p in SHIPPED}


def _strict(cfg: Any, day: int, own: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The day's own elements read as ``strict_sunrise`` does: occurrence elements assigned."""
    probe = compile_query(query([{"element": "weekday", "value": 1}], day, day), cfg)
    rec = Evaluator(cfg, probe).view(JDN(day)).record()
    out = []
    for c in own:
        e = c["element"]
        if e in ("tithi", "nakshatra", "yoga", "karana"):
            row = next(r for r in rec[e] if r["assigned"])
            out.append({"element": e, "value": row["index"]})
        elif "match" in c:
            out.append({**c, "match": "at_sunrise"})
        else:
            out.append(c)
    return out


@pytest.mark.parametrize("profile", ["kerala_default", "strict_sunrise"])
@pytest.mark.parametrize("preset", PRESETS)
def test_round_trip(preset: str, profile: str) -> None:
    cfg = config(preset)
    day = _day(preset)
    own = own_elements(cfg, day)
    assert any(c["element"] == "moon_rasi" for c in own)
    if profile == "strict_sunrise":
        own = _strict(cfg, day, own)
    q = query(own, day - HALF_WINDOW, day + HALF_WINDOW)
    q["reading_profile"] = profile
    staged = list(search(cfg, q))
    assert [comparable(c) for c in staged] == [comparable(c) for c in search(cfg, q, brute=True)]
    found = {c.jdn: c for c in staged}
    assert day in found and found[day].cls == "match", (preset, day)
    for c in found[day].constraints:
        assert c["matched"], (preset, day, c["element"])


@pytest.mark.parametrize("match", ["at_sunrise", "any_time_in_day"])
@pytest.mark.parametrize("preset", PRESETS)
def test_moon_rasi_served(preset: str, match: str) -> None:
    cfg = config(preset)
    day = _day(preset)
    q = query([{"element": "moon_rasi", "value": "Mesha", "match": match}], day, day + 30)
    got = list(search(cfg, q))
    assert got and all(c.cls == "match" for c in got)


@cache
def _vocabulary() -> Any:
    return config("parahita_kerala").reading_profile("kerala_default").vocabulary


def _names() -> list[tuple[str, int, str, tuple[str, ...]]]:
    from jyotirganita.regions.base import load_profile

    cfg = config("parahita_kerala")
    prof = load_profile(REPO, "kerala", cfg.records.data, cfg.eras)
    return [
        (cls, index, name.id, tuple(name.forms.get("latin", ())))
        for (cls, index), name in sorted(prof.names.items())
    ]


def test_vocabulary_is_generated_from_names_yaml() -> None:
    voc = _vocabulary()
    names = _names()
    assert names
    for cls, index, ident, latin in names:
        for spelling in (ident, *latin):
            for variant in (spelling, spelling.upper(), spelling.lower()):
                assert voc.index(cls, variant, "f") == index, (cls, variant)
    assert set(voc.classes()) == {cls for cls, *_ in names}
    expected = {s.casefold() for _, _, i, latin in names for s in (i, *latin)}
    assert {k for cls in voc.classes() for k in voc.spellings(cls)} == expected


def test_vocabulary_refusal_names_the_nearest_ids() -> None:
    cls, _, ident, _ = _names()[0]
    with pytest.raises(SearchError) as info:
        _vocabulary().index(cls, ident + "zz", "constraints[0].value")
    assert info.value.field == "constraints[0].value"
    assert "nearest ids" in info.value.message and ident in info.value.message


def test_near_miss_classes_reported_apart() -> None:
    cfg = config("parahita_kerala")
    day = _day("parahita_kerala")
    own = {c["element"]: c for c in own_elements(cfg, day)}
    cs = [own["weekday"], own["nakshatra"], own["masa"]]
    q = query(cs, day - 30, day + 30, near_miss={"max_misses": 1})
    buf = io.BytesIO()
    n = write_jsonl(search(cfg, q), buf)
    lines = [json.loads(x) for x in buf.getvalue().decode("ascii").splitlines()]
    assert len(lines) == n and n > 0
    assert {d["class"] for d in lines} == {"match", "near_miss"}
    assert [d["dates"]["jdn"] for d in lines] == sorted(d["dates"]["jdn"] for d in lines)
    for d in lines:
        if d["class"] == "match":
            assert "misses" not in d and all(c["matched"] for c in d["constraints"])
        else:
            assert len(d["misses"]) == 1
            assert sum(not c["matched"] for c in d["constraints"]) == 1
    assert isinstance(lines[0]["provenance"]["search"], Mapping)
