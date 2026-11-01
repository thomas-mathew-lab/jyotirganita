"""Unit tests of the table-driven engine (``siddhantic/tabular.py``).

Each rule on synthetic numbers (no printed value enters: the Dṛggaṇita
prints no worked example), and each refusal. The
interpolation is checked against Newton's forward formula on a quadratic,
which II.44–45's rule reproduces exactly when its divisors satisfy
d²·q = 2h² (h the step in kalās); the divisors here are chosen for that,
not taken from the text.

No place south of the equator or west of the text's meridian runs under the
table engine here. The sign paths it shares with the Āryabhaṭan engine are
tested there: the earthsine and the cara (``siddhantic/sunrise.py``) change
sign with the Sun in ``tests/unit/test_day_rules.py``
(``test_the_cara_vanishes_at_the_equator_and_changes_sign_with_the_sun``),
and the deśāntara, which ``TableEngine._desantara_days`` takes with the
Āryabhaṭan engine's sign (east positive, subtracted), in
``tests/unit/test_siddhantic.py``
(``test_an_observer_east_of_the_meridian_takes_the_desantara``).
"""

from __future__ import annotations

import dataclasses
from fractions import Fraction
from functools import cache

import pytest

from jyotirganita.data.datum import Record, Records, context_for, load_records
from jyotirganita.methods.compose import (
    DAY_RADIUS_RESOLUTION,
    REPO,
    ResolvedMethod,
    build,
    load_method,
)
from jyotirganita.regions.places import load_place
from jyotirganita.siddhantic.engine import EngineRefusal
from jyotirganita.siddhantic.tables import RsineTable, recursion_difference, rsines_by_recursion
from jyotirganita.siddhantic.tabular import (
    KARKYADI,
    MANDA,
    MRGADI,
    JyaTable,
    RationalRate,
    TableModel,
    TableRefusal,
    bhuja,
    mean_longitude_rational,
)

STEP = Fraction(6)
H = STEP * 60  # the step in kalās
ARC_DIVISOR = Fraction(12)
DIFF_DIVISOR = 2 * H * H / (ARC_DIVISOR * ARC_DIVISOR)


def _quadratic(x: Fraction) -> Fraction:
    return Fraction(3, 7) * x + Fraction(1, 50) * x * x


def _table(entries: tuple[Fraction, ...]) -> JyaTable:
    return JyaTable("t", entries, STEP, ARC_DIVISOR, DIFF_DIVISOR, "t.last_step")


@cache
def records() -> Records:
    return load_records(REPO, context_for(REPO))


@cache
def resolved() -> ResolvedMethod:
    return load_method("drgganita", REPO, records=records())


def model() -> TableModel:
    m = resolved().model
    assert isinstance(m, TableModel)
    return m


# --- the mean ------------------------------------------------------------------------------


def test_the_mean_drops_whole_revolutions_and_adds_the_signed_drift_and_dhruva() -> None:
    rate = RationalRate("x", 3, 7, Fraction(1, 100), Fraction(-2))
    assert mean_longitude_rational(rate, Fraction(7)) == Fraction(7, 100) - 2
    days = Fraction(10)
    revs = Fraction(30, 7)
    expected = (revs - 4) * 360 + Fraction(10, 100) - 2
    assert mean_longitude_rational(rate, days) == expected


# --- the bhujā -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kendra", "arc"), [(30, 30), (90, 90), (120, 60), (180, 0), (200, 20), (300, 60), (390, 30)]
)
def test_the_bhuja_is_the_arc_gone_or_to_go_in_the_quadrant(kendra: int, arc: int) -> None:
    assert bhuja(Fraction(kendra)) == arc


# --- the table and II.44–45 ----------------------------------------------------------------


def test_a_table_returns_its_entries_at_the_steps() -> None:
    entries = tuple(_quadratic(STEP * i) for i in range(1, 16))
    t = _table(entries)
    assert t.value(Fraction(0)) == 0
    for i, e in enumerate(entries, start=1):
        assert t.value(STEP * i) == e


@pytest.mark.parametrize("x", [Fraction(1), Fraction(37, 3), Fraction(45), Fraction(899, 10)])
def test_the_second_difference_rule_is_newton_s_on_a_quadratic(x: Fraction) -> None:
    """Exact inside every step; in the last, by the engine's fallback (no stated rule).

    The last step has no next difference: the engine takes the preceding
    pair's (``texts.drgganita.procedures.interpolation.last_step``, basis
    ``fallback_no_stated_rule``), which on a quadratic is the same.
    """
    t = _table(tuple(_quadratic(STEP * i) for i in range(1, 16)))
    assert t.value(x) == _quadratic(x) - _quadratic(Fraction(0))


def test_the_correction_is_subtracted_where_the_next_difference_is_greater() -> None:
    t = _table(tuple(_quadratic(STEP * i) for i in range(1, 16)))
    x = STEP / 2
    linear = t.entries[0] / 2
    assert t.value(x) < linear  # the differences grow: the term is negative


def test_a_bhuja_outside_the_table_is_refused() -> None:
    t = _table(tuple(Fraction(i) for i in range(1, 16)))
    with pytest.raises(TableRefusal, match="outside the table"):
        t.value(STEP * 15 + 1)
    with pytest.raises(TableRefusal, match="outside the table"):
        t.value(Fraction(-1))


# --- the kendra's sign and the śīghra branches (II.19, II.25) -------------------------------


def _constant(c: int) -> JyaTable:
    return _table(tuple(Fraction(c) for _ in range(15)))


def _with_tables(body: str, manda: int, mrgadi: int, karkyadi: int) -> TableModel:
    tables = dict(model().tables)
    tables[(body, MANDA)] = _constant(manda)
    tables[(body, MRGADI)] = _constant(mrgadi)
    tables[(body, KARKYADI)] = _constant(karkyadi)
    return dataclasses.replace(model(), tables=tables)


@pytest.mark.parametrize(
    ("kendra", "manda", "sighra"),
    [(30, -1, -2), (120, -1, -3), (200, 1, 3), (300, 1, 2)],
)
def test_the_sign_follows_the_kendra_and_the_sighra_branch_its_half(
    kendra: int, manda: int, sighra: int
) -> None:
    m = _with_tables("mars", 1, 2, 3)
    assert m.phala("mars", MANDA, Fraction(kendra)) == manda
    assert m.phala("mars", "sighra", Fraction(kendra)) == sighra


def test_a_missing_table_is_refused() -> None:
    tables = {k: v for k, v in model().tables.items() if k != ("mars", KARKYADI)}
    m = dataclasses.replace(model(), tables=tables)
    with pytest.raises(TableRefusal, match="no sighra_karkyadi table for mars"):
        m.phala("mars", "sighra", Fraction(120))


# --- the orders (II.20–24, II.43a) --------------------------------------------------------


def _means() -> dict[str, Fraction]:
    return {e: Fraction(37 * i + 11) for i, e in enumerate(sorted(model().rates))}


def _zero_tables(m: TableModel, body: str, kind: str) -> TableModel:
    tables = dict(m.tables)
    tables[(body, kind)] = _constant(0)
    return dataclasses.replace(m, tables=tables)


def test_the_luminaries_take_the_manda_correction_alone() -> None:
    m = model()
    mean = _means()
    for body in ("sun", "moon"):
        p = m.planets[body]
        assert p.order == "order.luminaries"
        ucca = mean[p.mandocca] if p.mandocca else p.apogee
        assert ucca is not None
        assert m.true(p, mean) == mean[p.mean] + m.phala(body, MANDA, mean[p.mean] - ucca)


@pytest.mark.parametrize("body", ["mars", "jupiter", "saturn"])
def test_a_superior_planet_without_manda_is_its_mean_and_the_whole_sighra(body: str) -> None:
    """With the manda nil, II.20 reduces to the whole śīghra on the mean (P3 is the mean)."""
    m = _zero_tables(model(), body, MANDA)
    p, mean = m.planets[body], _means()
    assert p.order == "order.superior" and p.sighrocca == "sun"
    p0 = mean[p.mean]
    assert m.true(p, mean) == p0 + m.phala(body, "sighra", p0 - mean["sun"])


@pytest.mark.parametrize("body", ["mercury", "venus"])
def test_an_inferior_planet_without_sighra_is_its_mean_and_the_whole_manda(body: str) -> None:
    """With the śīghra nil, II.22 reduces to the whole manda on the mean (the Sun's mean)."""
    m = model()
    for kind in (MRGADI, KARKYADI):
        m = _zero_tables(m, body, kind)
    p, mean = m.planets[body], _means()
    assert p.order == "order.inferior" and p.mean == "sun" and p.sighrocca == body
    assert p.apogee is not None
    p0 = mean["sun"]
    assert m.true(p, mean) == p0 + m.phala(body, MANDA, p0 - p.apogee)


# --- refusals of the model and the engine ------------------------------------------------


def _with_procedure(slot: str, **raw: object) -> dict[str, Record]:
    procs = dict(resolved().procedures)
    rec = procs[slot]
    procs[slot] = dataclasses.replace(rec, raw={**rec.raw, **raw})
    return procs


def test_a_slot_naming_another_procedure_is_refused() -> None:
    procs = _with_procedure("time_base", procedure="ahargana.civil_days_since_kali_epoch")
    with pytest.raises(TableRefusal, match="is not one this engine runs"):
        TableModel.build(model().data, procs, resolved().parameters[DAY_RADIUS_RESOLUTION])


@pytest.mark.parametrize("slot", ["gati", "rsine", "arc", "interpolation.last_step"])
def test_a_fallback_slot_must_say_it_is_the_fallback(slot: str) -> None:
    procs = _with_procedure(slot, basis="stated")
    with pytest.raises(TableRefusal, match="fallback"):
        TableModel.build(model().data, procs, resolved().parameters[DAY_RADIUS_RESOLUTION])


@pytest.mark.parametrize("slot", ["carry.desantara", "carry.bhujantara", "carry.cara"])
def test_a_carry_runs_on_every_mean_element_at_mean_motion(slot: str) -> None:
    procs = _with_procedure(slot, motion="true")
    with pytest.raises(TableRefusal, match="every mean element at mean motion"):
        TableModel.build(model().data, procs, resolved().parameters[DAY_RADIUS_RESOLUTION])


def test_a_body_in_two_orders_is_refused() -> None:
    inferior = (*resolved().procedures["order.inferior"].raw["applies_to"], "mars")
    procs = _with_procedure("order.inferior", applies_to=list(inferior))
    with pytest.raises(TableRefusal, match="mars is in two orders"):
        TableModel.build(model().data, procs, resolved().parameters[DAY_RADIUS_RESOLUTION])


def test_the_complement_names_the_one_node_element() -> None:
    procs = _with_procedure("node_complement", applies_to=["node", "moon"])
    with pytest.raises(TableRefusal, match="applies_to names the one node element"):
        TableModel.build(model().data, procs, resolved().parameters[DAY_RADIUS_RESOLUTION])


def test_an_unknown_intraday_model_is_refused() -> None:
    obs = load_place(REPO, "meridians", "drgganita_samarekha", records().data)
    with pytest.raises(EngineRefusal, match="intraday model"):
        build(resolved(), obs, intraday="intraday.no_such")


def test_a_body_the_text_does_not_serve_is_refused() -> None:
    obs = load_place(REPO, "meridians", "drgganita_samarekha", records().data)
    run = build(resolved(), obs)
    eng = run.engine
    jdn = run.runs_from.plus_days(1000)
    with pytest.raises(TableRefusal, match="serves no body"):
        eng.sidereal_longitude("uranus", eng.civil_day(jdn).start)


# --- the Rsine table by its Rsines and the recursion ---------------------


def test_a_table_of_rsines_takes_its_interval_from_the_quadrant() -> None:
    t = RsineTable.of_sines([10, 19, 25])  # synthetic
    assert (t.interval, t.differences, t.radius) == (1800, (10, 9, 6), 25)
    with pytest.raises(ValueError, match="do not divide a quadrant"):
        RsineTable.of_sines([1] * 7)


def test_the_recursion_s_steps_are_its_differences() -> None:
    """``rsines_by_recursion`` takes each difference by ``recursion_difference`` (no rounding).

    Synthetic numbers (no printed value): the composition of the steps only.
    """
    radius, below, twice = Fraction(1000), Fraction(9985, 10), 2
    sines = rsines_by_recursion(radius, below, 5, twice)[::-1]
    assert sines[:2] == (radius, below)
    last = difference = radius - below
    for k in range(1, 4):
        difference = recursion_difference(sines[k], last, radius, difference, twice)
        assert sines[k + 1] == sines[k] - difference
    with pytest.raises(ValueError, match="starts from the radius"):
        rsines_by_recursion(radius, below, 1, twice)


@pytest.mark.parametrize("n", [0, 1])
def test_a_table_too_short_for_the_last_step_is_refused(n: int) -> None:
    """The last step's fallback reads the pair before it; one entry has none."""
    with pytest.raises(TableRefusal, match="entries"):
        _table(tuple(Fraction(i + 1) for i in range(n)))


# --- guards from the 1.0.0 release review ---------------------------------


def _build_with(records: dict[str, Record]) -> TableModel:
    from jyotirganita.siddhantic.text import TextData

    return TableModel.build(
        TextData("drgganita", records),
        resolved().procedures,
        resolved().parameters[DAY_RADIUS_RESOLUTION],
    )


def test_rsine_entries_from_a_second_witness_are_refused() -> None:
    """A second witness's entry overwrote grahanamandana_1965's of the same number (item 4)."""
    recs = dict(model().data._records)
    old = "texts.drgganita.trig.rsine_table.quoted.grahanamandana_1965.e12"
    new = old.replace(".grahanamandana_1965.", ".another_witness.")
    recs[new] = dataclasses.replace(recs[old], key=new)
    with pytest.raises(TableRefusal, match="witnesses"):
        _build_with(recs)


def test_a_table_short_of_the_quadrant_is_refused() -> None:
    """A table missing its last entry built, and refused only at a bhujā near 90° (item 7)."""
    recs = dict(model().data._records)
    del recs["texts.drgganita.table.mars.manda.e15"]
    with pytest.raises(TableRefusal, match="do not span a quadrant"):
        _build_with(recs)


def test_an_unknown_kind_or_order_is_refused() -> None:
    """A misspelt kind became a śīghra correction; an unknown order the inferior one (item 9)."""
    m = model()
    with pytest.raises(TableRefusal, match="no correction kind"):
        m.phala("mars", "mnda", Fraction(60))
    odd = dataclasses.replace(m.planets["mars"], order="order.unknown")
    with pytest.raises(TableRefusal, match="no order"):
        m.true(odd, _means())


def test_a_diagnostic_offset_before_the_epoch_is_refused() -> None:
    """evaluate(epoch, −60 nāḍikās) reached the day before the epoch (item 8)."""
    from jyotirganita.core.types import Nadika
    from jyotirganita.siddhantic.engine import BeforeRunsFrom

    obs = load_place(REPO, "meridians", "drgganita_samarekha", records().data)
    run = build(resolved(), obs)
    eng = run.engine
    with pytest.raises(BeforeRunsFrom):
        eng.evaluate(eng.epoch, Nadika(-60))
    eng.evaluate(eng.epoch, Nadika(1))


def test_the_diagnostic_epoch_guard_uses_the_sunrises_own_shifts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard took consecutive sunrises as 60 nāḍikās apart."""
    from jyotirganita.core.types import JDN, Nadika
    from jyotirganita.siddhantic.engine import BeforeRunsFrom
    from jyotirganita.siddhantic.tabular import TableEngine

    obs = load_place(REPO, "meridians", "drgganita_samarekha", records().data)
    eng = build(resolved(), obs).engine
    assert isinstance(eng, TableEngine)
    nadis = eng.model.units.nadis_per_day
    at_epoch = eng._shift(eng.epoch)
    nxt = JDN(eng.epoch.value + 1)
    # the next sunrise 60.02 nāḍikās after the epoch's: −60.01 is 0.01 after the epoch's
    monkeypatch.setattr(
        eng, "_shift", lambda j: at_epoch + (Fraction(2, 100) / nadis if j == nxt else 0)
    )
    eng.evaluate(nxt, Nadika(Fraction(-6001, 100)))
    # the next sunrise 59.98 nāḍikās after: −59.99 is 0.01 before it
    monkeypatch.setattr(
        eng, "_shift", lambda j: at_epoch - (Fraction(2, 100) / nadis if j == nxt else 0)
    )
    with pytest.raises(BeforeRunsFrom):
        eng.evaluate(nxt, Nadika(Fraction(-5999, 100)))


# --- guards from the 1.0.0 release review ---------------------


def _with_raw(key: str, **raw: object) -> dict[str, Record]:
    recs = dict(model().data._records)
    recs[key] = dataclasses.replace(recs[key], raw={**recs[key].raw, **raw})
    return recs


def test_the_step_and_the_rates_name_their_units() -> None:
    """A changed unit on the step or a rate scaled the tables silently (item 3)."""
    with pytest.raises(TableRefusal, match="names its arc unit"):
        _build_with(_with_raw("texts.drgganita.table.step", unit="furlongs"))
    with pytest.raises(TableRefusal, match="is in revolutions"):
        _build_with(_with_raw("texts.drgganita.part2.mars.guna", unit="degrees"))
