"""Invariants of the table-driven Dṛggaṇita.

Part I against Part II (the validation map's "Dṛggaṇita Part I against
Part II"): every constant both parts state, compared as keyed, the Part I
dhruva's signed parts summed against the Part II dhruva the engine loads.
The II.43 complement applied once, and the node the output reports the
node the Moon's latitude uses (the Moon's latitude
is grahanamandana_1965 śl. 37–38's, the planets' not modelled). The precondition
of the Rsine table the Dṛk line adopts. No printed value enters
here: the data are compared with each other.
"""

from __future__ import annotations

import re
from fractions import Fraction
from functools import cache

import pytest

from jyotirganita.core.types import JDN, NOT_MODELLED, Nadika
from jyotirganita.data.datum import Records, context_for, load_fixture, load_records
from jyotirganita.methods.compose import REPO, MethodRun, build, load_method
from jyotirganita.regions.places import load_place
from jyotirganita.siddhantic.mean import DEGREES_PER_REVOLUTION
from jyotirganita.siddhantic.tabular import ARC_UNITS, TableModel
from jyotirganita.siddhantic.text import TextData

TEXT = "drgganita"
#: one rāśi in degrees, the twelfth of a revolution
DEGREES_PER_SIGN = Fraction(DEGREES_PER_REVOLUTION, 12)
UNITS = {**ARC_UNITS, "signs": DEGREES_PER_SIGN}
ELEMENTS = ("sun", "moon", "moon_apogee", "node", "mars", "mercury", "jupiter", "venus", "saturn")
PLANETS = ("sun", "mars", "mercury", "jupiter", "venus", "saturn")
PARTS = ("rasi", "bhaga", "lipta", "vilipta")
#: the Part II rates that differ from Part I's, each recorded with its provisional note, the
#: owner's to adjudicate
DISAGREEING = ("node.drift",)
#: every 7919th day from the Kali epoch over some five thousand years
STEP, COUNT = 7919, 230


@cache
def records() -> Records:
    return load_records(REPO, context_for(REPO))


def data() -> TextData:
    return TextData(TEXT, records().data)


@cache
def run() -> MethodRun:
    r = load_method(TEXT, REPO, records=records())
    observer = load_place(REPO, "meridians", "drgganita_samarekha", records().data)
    return build(r, observer)


def days() -> list[JDN]:
    first = run().runs_from
    return [first.plus_days(i * STEP) for i in range(COUNT)]


def _arc(d: TextData, suffix: str) -> Fraction:
    return d.fraction(suffix) * UNITS[str(d.record(suffix).raw["unit"])]


# --- Part I against Part II -------------------------------------------------------------


@pytest.mark.parametrize("element", ELEMENTS)
@pytest.mark.parametrize("name", ("guna", "hara", "drift"))
def test_part_one_and_part_two_state_the_same_rate(element: str, name: str) -> None:
    """A disagreement is recorded, provisional, on the loaded Part II datum."""
    d = data()
    one, two = d.record(f"part1.{element}.{name}"), d.record(f"part2.{element}.{name}")
    if (one.value, one.raw["unit"]) == (two.value, two.raw["unit"]):
        assert f"{element}.{name}" not in DISAGREEING, two.key
        return
    assert f"{element}.{name}" in DISAGREEING and two.raw.get("provisional"), (one.key, two.key)
    assert f"provisional:{two.key}" in run().day(days()[1]).flags


@pytest.mark.parametrize("element", ELEMENTS)
def test_part_one_s_signed_dhruva_parts_sum_to_part_two_s_dhruva(element: str) -> None:
    d = data()
    parts = [p for p in PARTS if d.has(f"part1.{element}.dhruva.{p}")]
    assert parts, element
    one = sum((_arc(d, f"part1.{element}.dhruva.{p}") for p in parts), Fraction(0))
    assert one == _arc(d, f"part2.{element}.dhruva")


@pytest.mark.parametrize("planet", PLANETS)
def test_part_one_s_mandocca_degrees_are_part_two_s_within_the_sign(planet: str) -> None:
    """Part I names the sign in words (``.mandocca.rasi``, a statement); the degrees compare."""
    d = data()
    two = _arc(d, f"part2.{planet}.mandocca")
    assert two % DEGREES_PER_SIGN == _arc(d, f"part1.{planet}.mandocca.bhaga")
    assert d.record(f"part1.{planet}.mandocca.rasi").raw["form"] == "text"


def test_the_engine_loads_part_two() -> None:
    model = run().resolved.model
    assert isinstance(model, TableModel)
    used = set(model.data.used)
    assert not {k for k in used if k.startswith(f"texts.{TEXT}.part1.")} - {
        f"texts.{TEXT}.part1.ahargana.n1"  # the Śaka–Kali difference only Part I states
    }
    for element in ELEMENTS:
        for name in ("guna", "hara", "drift", "dhruva"):
            assert f"texts.{TEXT}.part2.{element}.{name}" in used


# --- the II.43 complement and the node ---------------------------------------------


def test_the_complement_is_applied_once() -> None:
    eng = run().engine
    node_element = run().resolved.model.node_element
    for jdn in days():
        day = eng.day(jdn)
        assert (day.node + day.mean[node_element]) % DEGREES_PER_REVOLUTION == 0
        assert eng.node(eng.instant(jdn, Nadika(0))).arc.value == day.node
        # applied twice would return the mean Rāhu itself
        assert day.node != day.mean[node_element] or day.node in (0, 180)


def test_the_node_reported_is_the_node_the_moon_s_latitude_uses() -> None:
    """grahanamandana_1965 śl. 37–38 on the record's node: north in the six signs from Meṣa, at most
    the Great Sine of a quadrant (the radius) times the verse's ratio, in minutes."""
    r = run()
    eng = r.engine
    model = r.resolved.model
    assert isinstance(model, TableModel)
    multiplier, divisor = model.moon_latitude
    bound = Fraction(model.table.radius * multiplier, divisor) / 60
    for jdn in days()[:40]:
        rec = r.day(jdn)
        assert rec.node == eng.day(jdn).node
        at = eng.instant(jdn, Nadika(0))
        lat = eng.latitude("moon", at)
        assert not isinstance(lat, type(NOT_MODELLED))
        arg = (eng.day(jdn).true["moon"] - rec.node) % DEGREES_PER_REVOLUTION
        assert (lat.value > 0) is (0 < arg < 180) and abs(lat.value) <= bound
        for body in eng.capabilities.bodies:
            if body != "moon":
                assert eng.latitude(body, at) is NOT_MODELLED
                assert f"latitude.{body}" in eng.capabilities.not_modelled
    assert "latitude" not in eng.capabilities.not_modelled


def test_the_moon_s_greatest_latitude_is_golasara_1970_s_within_its_quantum() -> None:
    """grahanamandana_1965 śl. 37's multiplier and divisor on the table's radius against
    golasara_1970 I.7a's
    Moon, which states its maximum in tens of minutes: within half of ten minutes."""
    model = run().resolved.model
    assert isinstance(model, TableModel)
    multiplier, divisor = model.moon_latitude
    rule = Fraction(model.table.radius * multiplier, divisor)
    stated = str(records().data[f"texts.{TEXT}.latitude.maxima.statement.golasara_1970"].value)
    match = re.search(r"\(Moon\) (\d+) \(x (\d+)=(\d+)'\)", stated)
    assert match is not None, stated
    tens, quantum, minutes = (int(g) for g in match.groups())
    assert tens * quantum == minutes
    assert abs(rule - minutes) <= Fraction(quantum, 2)


# --- the Rsine table: the precondition of its adoption ------------------------------------


def test_the_table_s_last_rsine_is_the_radius_and_its_count_the_rules() -> None:
    """grahanamandana_1965 śl. 25A–B serves the Dṛk line only while its last Rsine is the radius the
    rules assume and its count theirs: against grahanamandana_1965's footnote to śl. 16b–17a and
    golasara_1970's example (``golasara_1970_iii_13_rsine_recursion``), data against data."""
    model = run().resolved.model
    assert isinstance(model, TableModel)
    note = str(
        records().data[f"texts.{TEXT}.trig.great_sine.editor_note.grahanamandana_1965"].value
    )
    match = re.search(r"=(\d+)\.?$", note)
    assert match is not None, note
    fx = load_fixture(
        REPO / "tests/authority/drgganita/golasara_1970_iii_13_rsine_recursion.yaml",
        context_for(REPO),
        repo=REPO,
    )
    printed = {v.key.split("#", 1)[1]: v.value for v in fx.values}
    assert model.table.radius == int(match.group(1)) == printed["input.radius"]
    assert len(model.table.differences) == printed["input.sines_in_quadrant"]
    assert model.table.differences[0] == printed["input.first_sine"]


# --- II.44–45's divisors ------------------------------------------------------------------


def test_the_interpolation_divisors_satisfy_the_rule_s_own_arithmetic() -> None:
    """d²·q = 2h², h the tables' step in kalās.

    With it the II.44–45 rule, the product of the kalās gone and to go each
    divided by d, times the difference of the differences, divided by q, is
    Newton's second-order term over a step of h: an internal redundancy of
    the source between three data, whatever the spelling
    of the divisor's word.
    """
    d = data()
    h = _arc(d, "table.step") / ARC_UNITS["arcminutes"]
    arc = d.fraction("procedures.interpolation.divisor_arc")
    diff = d.fraction("procedures.interpolation.divisor_diff")
    assert arc * arc * diff == 2 * h * h
