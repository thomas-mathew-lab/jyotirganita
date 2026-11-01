"""Invariants of Parameśvara's recension against its base.

``suryasiddhanta_paramesvara_recension`` is ``suryasiddhanta`` with two
data read in place of the base's (``replaces``). Three invariants: (a) the composed data
set equals the base's in every key except the two replaced ones; (b) on
those two it holds the suryasiddhanta_paramesvara_1957 data, loaded by key; (c) on a seeded sample
of
days every mean element but the Moon's apogee and node agrees exactly
between the two methods, and those two differ. No value is typed: the
data are compared with each other and the engines with each other.
"""

from __future__ import annotations

import random
from functools import cache

import pytest

from jyotirganita.core.types import JDN
from jyotirganita.data.datum import Records, context_for, load_records
from jyotirganita.data.engine_parameters import seed
from jyotirganita.methods.compose import REPO, MethodRun, ResolvedMethod, build, load_method
from jyotirganita.regions.places import load_place
from jyotirganita.siddhantic.surya import SuryaModel

BASE = "suryasiddhanta"
NEW = "suryasiddhanta_paramesvara_recension"
#: the sample: this many days drawn from the first five thousand years of the Kali count
SAMPLE, SPAN = 40, 5000 * 366


@cache
def records() -> Records:
    return load_records(REPO, context_for(REPO))


@cache
def resolved(method: str) -> ResolvedMethod:
    return load_method(method, REPO, records=records())


@cache
def run(method: str) -> MethodRun:
    return build(
        resolved(method), load_place(REPO, "meridians", "suryasiddhanta_lanka", records().data)
    )


def model(method: str) -> SuryaModel:
    m = resolved(method).model
    assert isinstance(m, SuryaModel)
    return m


def replaced() -> dict[str, str]:
    return dict(resolved(NEW).method.replaces)


def _elements(key: str) -> str:
    """The element a revolution datum states (``texts.suryasiddhanta.<element>.revolutions``)."""
    return key.removeprefix("texts.suryasiddhanta.").removesuffix(".revolutions")


def sample() -> list[JDN]:
    rng = random.Random(seed("seeds.conformance_year"))
    start = run(BASE).runs_from
    return sorted(
        {start.plus_days(rng.randrange(SPAN)) for _ in range(SAMPLE)}, key=lambda j: j.value
    )


def test_the_composed_data_differ_from_the_base_s_in_the_two_replaced_keys_only() -> None:
    new, base = resolved(NEW).data, resolved(BASE).data
    keys = set(base.held) | set(new.held)
    differing = {k for k in keys if new.held.get(k) is not base.held.get(k)}
    assert differing == set(replaced())
    assert len(differing) == 2


def test_the_replaced_keys_hold_the_suryasiddhanta_paramesvara_1957_data_loaded_by_key() -> None:
    new = resolved(NEW).data
    revolutions = model(NEW).elements.revolutions
    for old, repl in replaced().items():
        assert new.held[old] is records().data[repl]
        assert revolutions[_elements(old)] == records().data[repl].value


def test_every_element_but_the_moon_s_apogee_and_node_agrees_on_a_seeded_sample() -> None:
    moved = {_elements(k) for k in replaced()}
    assert moved == {"moon_apogee", "moon_node"}
    days = sample()
    assert len(days) > SAMPLE // 2
    seen_differ = dict.fromkeys(moved, False)
    for jdn in days:
        a, b = run(BASE).engine.day(jdn), run(NEW).engine.day(jdn)
        assert a.mean.keys() == b.mean.keys()
        for element in a.mean:
            if element in moved:
                seen_differ[element] |= a.mean[element] != b.mean[element]
            else:
                assert a.mean[element] == b.mean[element], (jdn, element)
    assert all(seen_differ.values()), seen_differ


@pytest.mark.parametrize("method", [BASE, NEW])
def test_each_method_reads_its_own_pair_and_not_the_other_s(method: str) -> None:
    used = set(resolved(method).data.used)
    old, new = set(replaced()), set(replaced().values())
    assert (used & old, used & new) == ((old, set()) if method == BASE else (set(), new))


def test_every_slot_is_the_base_s_procedure() -> None:
    """``replaces`` changes no procedure."""
    base, new = resolved(BASE).procedures, resolved(NEW).procedures
    assert {k: v.key for k, v in new.items()} == {k: v.key for k, v in base.items()}


def test_the_sunrise_is_the_base_s_at_a_kerala_place() -> None:
    """The sunrise rests on the Sun alone, which the two methods share."""
    place = load_place(REPO, "kerala", "kozhikode", records().data)
    a, b = (build(resolved(m), place).engine for m in (BASE, NEW))
    for jdn in sample()[:10]:
        da, db = a.day(jdn), b.day(jdn)
        assert (da.sunrise, da.sunset) == (db.sunrise, db.sunset), jdn
