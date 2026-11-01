"""Invariants of the siddhantic engine.

The zero-layer identity (a layered method with its layers zeroed is its
base, exactly), the weekday of the day count against the calendar's, the
day count's continuity, the additivity of the mean motion and the
linearity of a layer in its count. No printed value enters here: the
printed examples are the authority tests under ``tests/authority/aryabhatiya/``.
"""

from __future__ import annotations

from fractions import Fraction
from functools import cache

import pytest

from jyotirganita.core.calendar import weekday
from jyotirganita.core.types import JDN
from jyotirganita.data.datum import Records, context_for, load_records
from jyotirganita.methods.compose import REPO, MethodRun, build, load_method
from jyotirganita.regions.places import load_place
from jyotirganita.siddhantic.mean import DEGREES_PER_REVOLUTION, mean_longitude

#: every 9973rd day from the Kali epoch over some six thousand years
STEP, COUNT = 9973, 220


@cache
def records() -> Records:
    return load_records(REPO, context_for(REPO))


@cache
def run(method_id: str, *, zero_layers: bool = False) -> MethodRun:
    r = load_method(method_id, REPO, records=records())
    observer = load_place(REPO, "meridians", "lanka", records().data)
    return build(r, observer, zero_layers=zero_layers)


def days() -> list[JDN]:
    first = run("aryabhatiya").runs_from
    return [first.plus_days(i * STEP) for i in range(COUNT)]


def test_the_zero_layer_identity() -> None:
    base, zeroed = run("aryabhatiya"), run("parahita", zero_layers=True)
    for jdn in days():
        b, z = base.day(jdn), zeroed.day(jdn)
        assert (z.mean, z.true, z.node) == (b.mean, b.true, b.node), jdn
        assert z.ahargana == b.ahargana and z.weekday == b.weekday
    assert zeroed.provenance["zero_layers"] is True


def test_the_layers_alone_separate_the_methods() -> None:
    later = days()[-1]
    assert run("parahita").day(later).mean != run("aryabhatiya").day(later).mean


@pytest.mark.parametrize("method_id", ["aryabhatiya", "parahita"])
def test_the_weekday_of_the_count_is_the_calendar_weekday(method_id: str) -> None:
    r = run(method_id)
    for jdn in days():
        assert r.day(jdn).weekday == weekday(jdn), jdn


def test_the_count_starts_on_the_epoch_and_advances_a_day_a_day() -> None:
    r = run("aryabhatiya")
    for jdn in days():
        a, b = r.day(jdn), r.day(jdn.plus_days(1))
        assert a.ahargana.day == jdn.days_since(r.runs_from)
        assert b.ahargana.day == a.ahargana.day + 1


def test_mean_motion_is_additive() -> None:
    m = run("aryabhatiya").resolved.text_model
    for rev in m.revolutions.values():
        for a, b in ((1, 1), (365, 4000), (STEP, 1_000_003)):
            sa = mean_longitude(rev, m.civil_days, a).exact
            sb = mean_longitude(rev, m.civil_days, b).exact
            sab = mean_longitude(rev, m.civil_days, a + b).exact
            assert sab == (sa + sb) % DEGREES_PER_REVOLUTION


def test_a_layer_is_linear_in_its_count() -> None:
    (layer,) = run("parahita").resolved.layers
    for element in layer.rates:
        for n, k in ((1, 1), (-3, 7), (1440, 345)):
            c = layer.correction(element, n + k)
            assert c == layer.correction(element, n) + layer.correction(element, k)
        assert layer.correction(element, 0) == Fraction(0)
