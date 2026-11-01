"""Invariants of the Sūrya-siddhānta engine.

Cycle closure of every mean element over its own civil days (i.53); the
order of ii.43–44 as the procedure data state it (the luminaries one
process, the five planets four, each step taken once from the place the
step before gave); the node the latitude uses is the node the output
reports; the epoch advance (i.67) moves the mean from midnight to the
sunrise by the motion times the nāḍīs over the nāḍīs of a day. At Laṅkā (the text's meridian, on the
equator) the
ascensional difference vanishes and the sunrise is the quarter day; at a
Kerala place the sunrise is the quarter day moved by the cara (ii.60–63,
xiv.18), the sunset its mirror about noon, and the day the longer while
the Sun's declination is north. No printed
value enters: the data are compared with each other and with the engine's
own day. The Āryabhaṭan and Dṛggaṇita regression files stay unchanged
(``tests/regression/``).
"""

from __future__ import annotations

from fractions import Fraction
from functools import cache

import pytest

from jyotirganita.core.types import JDN
from jyotirganita.data.datum import Records, context_for, load_records
from jyotirganita.methods.compose import REPO, MethodRun, build, load_method
from jyotirganita.regions.places import load_place
from jyotirganita.siddhantic.mean import DEGREES_PER_REVOLUTION
from jyotirganita.siddhantic.surya import SuryaDay, SuryaEngine, SuryaModel

TEXT = "suryasiddhanta"
#: every 7919th day from the Kali epoch over some five thousand years
STEP, COUNT = 7919, 230


@cache
def records() -> Records:
    return load_records(REPO, context_for(REPO))


@cache
def run() -> MethodRun:
    r = load_method(TEXT, REPO, records=records())
    return build(r, load_place(REPO, "meridians", "suryasiddhanta_lanka", records().data))


def model() -> SuryaModel:
    m = run().resolved.model
    assert isinstance(m, SuryaModel)
    return m


def engine() -> SuryaEngine:
    e = run().engine
    assert isinstance(e, SuryaEngine)
    return e


@cache
def kerala() -> MethodRun:
    r = load_method(TEXT, REPO, records=records())
    return build(r, load_place(REPO, "kerala", "kozhikode", records().data))


def days() -> list[JDN]:
    return [run().runs_from.plus_days(STEP * i) for i in range(COUNT)]


def day(jdn: JDN) -> SuryaDay:
    return engine().day(jdn)


def test_every_mean_element_closes_its_cycle() -> None:
    e = model().elements
    for element, civil in e.civil_days.items():
        assert e.mean(element, Fraction(0)) == 0, element
        for d in (Fraction(1), Fraction(7919, 3), Fraction(model().days_to_epoch)):
            assert e.mean(element, d + civil) == e.mean(element, d), element


def test_a_node_moves_backward_and_every_other_element_forward() -> None:
    e = model().elements
    for element in e.revolutions:
        assert (e.motion(element) < 0) is (element in e.nodes), element


def test_the_order_is_the_procedure_data_s() -> None:
    procs = run().resolved.procedures
    luminaries = set(procs["order.luminaries"].raw["applies_to"])
    planets = set(procs["order.planets"].raw["applies_to"])
    m = model()
    assert {b for b, p in m.planets.items() if p.order == "order.luminaries"} == luminaries
    assert {b for b, p in m.planets.items() if p.order == "order.planets"} == planets
    assert luminaries.isdisjoint(planets) and luminaries | planets == set(m.planets)


@pytest.mark.parametrize("jdn", days()[::23])
def test_each_process_is_taken_once_from_the_place_before(jdn: JDN) -> None:
    m, mean = model(), day(jdn).mean
    for body, p in m.planets.items():
        steps = m.processes(p, mean)
        place = mean[p.mean]
        if p.order == "order.luminaries":
            assert steps == (place + m.manda(p, mean, place).degrees,), body
            continue
        p1, p2, p3, p4 = steps
        assert p1 == place + m.sighra(p, mean, place).degrees / 2, body
        assert p2 == p1 + m.manda(p, mean, p1).degrees / 2, body
        assert p3 == place + m.manda(p, mean, p2).degrees, body
        assert p4 == p3 + m.sighra(p, mean, p3).degrees, body
        # the bhujāntara once, on the true place (ii.46)
        bhujantara = m.gati(p, mean) * m.bhujaphala_minutes(mean) / m.circle_minutes
        assert day(jdn).true[body] == (p4 + bhujantara) % DEGREES_PER_REVOLUTION, body


@pytest.mark.parametrize("jdn", days()[::23])
def test_the_latitude_s_node_is_the_output_node(jdn: JDN) -> None:
    m, d = model(), day(jdn)
    moon = m.planets["moon"]
    assert moon.node == m.node_element
    assert d.node == d.mean[m.node_element]
    for body, p in m.planets.items():
        if p.node is not None:
            assert p.node in d.mean, body


@pytest.mark.parametrize("jdn", days()[::23])
def test_the_epoch_advance_carries_the_mean_to_the_sunrise(jdn: JDN) -> None:
    m, d = model(), day(jdn)
    nadis = Fraction(m.units.nadis_per_day)
    assert d.creation_count == m.days_to_epoch + jdn.days_since(run().runs_from)
    for element in m.elements.revolutions:
        at_midnight = m.elements.mean(element, Fraction(d.creation_count))
        advance = m.elements.motion(element) * d.sunrise.value / nadis
        assert d.mean[element] == (at_midnight + advance) % DEGREES_PER_REVOLUTION, element


def test_the_count_and_the_weekday_advance_by_one_a_day() -> None:
    r = run()
    previous = None
    for jdn in days()[:40]:
        for k in (0, 1):
            today = r.day(jdn.plus_days(k))
            if previous is not None and k == 1:
                assert today.ahargana.day == previous.ahargana.day + 1
                assert today.weekday.value == (previous.weekday.value + 1) % 7
            previous = today


# --- the sunrise ----------------------------------------------------------------


@pytest.mark.parametrize("jdn", days()[::23])
def test_at_lanka_the_sunrise_is_the_quarter_day(jdn: JDN) -> None:
    nadis = Fraction(model().units.nadis_per_day)
    d = day(jdn)
    assert d.terms is not None
    assert d.terms.cara_days == 0
    assert (d.sunrise.value, d.sunset) == (nadis / 4, d.terms.sunset)
    assert d.terms.sunset.value == 3 * nadis / 4


@pytest.mark.parametrize("jdn", days()[::23])
def test_at_a_kerala_place_the_cara_moves_sunrise_and_sunset_about_noon(jdn: JDN) -> None:
    nadis = Fraction(model().units.nadis_per_day)
    e = kerala().engine
    assert isinstance(e, SuryaEngine)
    d = e.day(jdn)
    assert d.terms is not None and d.sunset is not None
    assert d.sunrise.value == nadis * (Fraction(1, 4) + d.terms.cara_days)
    assert d.sunrise.value + d.sunset.value == nadis
    # north latitude: a north declination makes the day the longer, the sunrise earlier
    assert (d.terms.cara_days < 0) == (d.terms.rsin_declination > 0)
