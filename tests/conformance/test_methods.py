"""The conformance items over every siddhantic registry entry.

Each method runs under its registry entry, not a preset, at the place
``meridians.lanka``; the table-driven Dṛggaṇita at its own provisional
place ``meridians.drgganita_samarekha``; the Sūrya-siddhānta at
``meridians.suryasiddhanta_lanka``, its own meridian at the equator. The
items: the engine protocol on a sampled year; ``runs_from`` refused the day
before with its name and run on the day itself; the
``before_composition:<id>`` flag on every day before ``composed`` and on
none after, and ``before_epoch:<layer>`` for a layer; nothing refused on
any flag; every procedure name resolves, every registered procedure is used
and has an authority test or a declared ``no printed example`` or a pending
package; ``base``/``layers`` composition; the hybrid sunrise
under a test-only provider.

The day's rules: the sunrise, ending-time,
``computation_instant``, ``carry`` (every statement saying what it acts
on, at what motion, on which bodies) and ``intraday`` data present and
resolved for every method; the seam rule on a seeded year at a
Kerala observer (none where the gati is the sunrise difference, and a
seam flagged in both days' records where it is not); every transition
inside a day at the proportional-parts ending under ``linear_gati``;
the record's sunrise, sunset and ``day_length_nadika`` leaves with the
standard ``text_local:<text>``; the Kerala place table, each place with
its route or its gap; the ``full_evaluation`` diagnostic flagged.

The day's items run over the methods whose sunrise and carry are keyed:
the table-driven Dṛggaṇita among them (the Dṛk line's
rules, goladipika_1916 v. 195–209 and grahanamandana_1965, on the Rsine table of grahanamandana_1965
śl. 25A–B; its Kerala places by route (b)),
and the Sūrya-siddhānta (suryasiddhanta_burgess_1860 i.60–61, ii.46–68, iii.10,
xiv.18–19; its Kerala places by route (b) through Whitney's identification
of the prime meridian). No slot names the deferral datum any longer. The
Sūrya-siddhānta's gati is its equation of the daily motion (ii.47–51), not
the sunrise difference, so its seams are checked to come in pairs.
"""

from __future__ import annotations

import random
import shutil
from fractions import Fraction
from functools import cache
from pathlib import Path

import pytest

from jyotirganita.calendar import elements
from jyotirganita.core.calendar import jdn_from_gregorian, weekday
from jyotirganita.core.engine import Engine
from jyotirganita.core.types import (
    JDN,
    NOT_MODELLED,
    Ahargana,
    AngleUnit,
    ExactArc,
    GregorianDate,
    Nadika,
    NotModelled,
    SiddhanticCivilInstant,
)
from jyotirganita.data.datum import Record, Records, context_for, load_records
from jyotirganita.data.engine_parameters import seed
from jyotirganita.data.eras import EraFile, load_eras
from jyotirganita.data.yamlio import dump_canonical, load_exact
from jyotirganita.methods.compose import (
    ENDING_ELEMENTS,
    REPO,
    MethodRun,
    ResolvedMethod,
    build,
    load_method,
)
from jyotirganita.methods.registry import load_registry
from jyotirganita.regions.places import PlaceError, load_place, place_flag, place_ids
from jyotirganita.siddhantic.endings import SeamRefusal
from jyotirganita.siddhantic.engine import (
    CARRY_SLOTS,
    FULL_EVALUATION,
    BeforeRunsFrom,
    EngineRefusal,
    Observer,
)
from jyotirganita.siddhantic.procedures import REGISTRY, SLOTS, resolve
from jyotirganita.siddhantic.surya import CARA_GAP, SuryaEngine, SuryaModel
from jyotirganita.siddhantic.surya import CARRY as SURYA_CARRY
from jyotirganita.siddhantic.surya import FALLBACK_SLOTS as SURYA_FALLBACK
from jyotirganita.siddhantic.tabular import CARRY as TABLE_CARRY
from jyotirganita.siddhantic.tabular import TableEngine, TableModel

REGION, PLACE = "meridians", "lanka"
#: the sampled year of the protocol item: Gregorian 1963, the year of laghubhaskariya_1963's example
SAMPLE_YEAR = 1963
DAYS_IN_SAMPLE = 365


@cache
def records() -> Records:
    return load_records(REPO, context_for(REPO))


SIDDHANTIC = sorted(
    m.id
    for m in load_registry(
        REPO / "jyotirganita" / "methods" / "registry.yaml", context_for(REPO).sources
    ).values()
    if m.engine == "siddhantic"
)


@cache
def resolved(method_id: str) -> ResolvedMethod:
    return load_method(method_id, REPO, records=records())


#: the place a method's conformance items run at, where it is not Laṅkā
OWN_PLACE = {
    "drgganita": ("meridians", "drgganita_samarekha"),
    "suryasiddhanta": ("meridians", "suryasiddhanta_lanka"),
    # the same text, slots and meridian place as its base
    "suryasiddhanta_paramesvara_recension": ("meridians", "suryasiddhanta_lanka"),
}


def place_of(method_id: str) -> tuple[str, str]:
    return OWN_PLACE.get(method_id, (REGION, PLACE))


def observer(method_id: str) -> Observer:
    return load_place(REPO, *place_of(method_id), records().data)


def surya(method_id: str) -> bool:
    """The Sūrya-siddhānta and its recension."""
    return isinstance(resolved(method_id).model, SuryaModel)


def table_driven(method_id: str) -> bool:
    """The table-driven Dṛggaṇita: its day's rules are the Dṛk line's."""
    return isinstance(resolved(method_id).model, TableModel)


@cache
def run(method_id: str) -> MethodRun:
    return build(resolved(method_id), observer(method_id))


def _first_day_with_years(r: MethodRun, years: int) -> JDN:
    """The first civil day whose completed Kali years at sunrise are at least ``years``."""
    lo, hi = r.runs_from, r.runs_from.plus_days(366 * (years + 2))
    while lo.days_since(JDN(0)) < hi.days_since(JDN(0)):
        mid = lo.plus_days(hi.days_since(lo) // 2)
        if r.engine.day(mid).completed_years >= years:
            hi = mid
        else:
            lo = mid.plus_days(1)
    return lo


def _threshold(method_id: str, flag: str) -> int:
    r = resolved(method_id)
    (c,) = [c for c in r.components if c.flag == flag]
    return c.year.kali_threshold(r.model.saka_to_kali_years, r.ce_to_kali_years)


def _sample_days() -> list[JDN]:
    first = jdn_from_gregorian(GregorianDate(SAMPLE_YEAR, 1, 1))
    return [first.plus_days(i) for i in range(DAYS_IN_SAMPLE)]


# --- the engine protocol on a sampled year ------------------------------------------------


@pytest.mark.parametrize("method_id", SIDDHANTIC)
def test_the_engine_protocol_on_a_sampled_year(method_id: str) -> None:
    eng: Engine[ExactArc, SiddhanticCivilInstant] = run(method_id).engine
    assert eng.time_base is Ahargana
    caps = eng.capabilities
    assert caps.bodies and caps.node
    assert "tropical_longitude" in caps.not_modelled
    # the Sūrya-siddhānta states a latitude for the Moon and the planets (ii.56–57); the
    # Dṛk line for the Moon (grahanamandana_1965 śl. 37), its planets' rules needing what no table
    # gives
    text = resolved(method_id).method.text
    with_latitude = "latitude" not in caps.not_modelled
    assert with_latitude is (text in ("suryasiddhanta", "drgganita"))
    if with_latitude:
        assert "latitude.sun" in caps.not_modelled
    if text == "drgganita":
        assert [b for b in caps.bodies if f"latitude.{b}" not in caps.not_modelled] == ["moon"]
    for key in ("sunset", "daily_motion", "intraday"):
        assert key not in caps.not_modelled
    frame_id = f"text:{resolved(method_id).method.text}"
    previous = None
    for jdn in _sample_days():
        frame = eng.civil_day(jdn)
        assert frame.jdn == jdn
        assert frame.start == frame.sunrise == eng.instant(jdn, Nadika(0))
        assert frame.end == eng.instant(jdn.plus_days(1), Nadika(0))
        assert isinstance(frame.sunset, SiddhanticCivilInstant) and frame.sunset.jdn == jdn
        assert isinstance(frame.day_length_nadika, Nadika)
        for body in caps.bodies:
            lon = eng.sidereal_longitude(body, frame.start)
            assert isinstance(lon.arc, ExactArc) and lon.frame == frame_id
            assert eng.tropical_longitude(body, frame.start) is NOT_MODELLED
            lat = eng.latitude(body, frame.start)
            if with_latitude and f"latitude.{body}" not in caps.not_modelled:
                assert isinstance(lat, ExactArc) and lat.unit is AngleUnit.DEGREE
            else:
                assert lat is NOT_MODELLED
            assert isinstance(eng.daily_motion(body, jdn), ExactArc)
        node = eng.node(frame.start)
        assert not isinstance(node, NotModelled) and node.frame == frame_id
        day = run(method_id).day(jdn)
        if previous is not None:
            assert day.ahargana.day == previous.ahargana.day + 1
            assert day.weekday.value == (previous.weekday.value + 1) % 7
        previous = day


@pytest.mark.parametrize("method_id", SIDDHANTIC)
def test_positions_inside_the_day_are_on_the_chord_and_the_sliver_is_refused(
    method_id: str,
) -> None:
    eng = run(method_id).engine
    jdn = _sample_days()[0]
    nadis = resolved(method_id).model.units.nadis_per_day
    sunrise = eng.day(jdn).true["moon"]
    half = Nadika(Fraction(nadis, 2))
    at = eng.sidereal_longitude("moon", eng.instant(jdn, half)).arc.value
    assert at == (sunrise + eng.gati("moon", jdn) / 2) % 360
    with pytest.raises(SeamRefusal, match="seam rule"):
        eng.sidereal_longitude("moon", eng.instant(jdn, Nadika(nadis)))


# --- runs_from -----------------------------------------------------------------------


@pytest.mark.parametrize("method_id", SIDDHANTIC)
def test_the_day_before_runs_from_is_refused_naming_it(method_id: str) -> None:
    r = run(method_id)
    before = r.runs_from.plus_days(-1)
    with pytest.raises(BeforeRunsFrom, match=rf"before runs_from \(JDN {r.runs_from.value}\)"):
        r.day(before)
    with pytest.raises(BeforeRunsFrom, match="runs_from"):
        r.engine.civil_day(before)


@pytest.mark.parametrize("method_id", SIDDHANTIC)
def test_runs_from_itself_runs(method_id: str) -> None:
    r = run(method_id)
    day = r.day(r.runs_from)
    assert day.ahargana.day == 0 and day.completed_kali_years == 0
    assert day.provenance["runs_from"] == r.runs_from.value


def test_runs_from_is_the_kali_epoch_of_the_era_record() -> None:
    eras = {e.era.id: e for e in _eras().values()}
    for method_id in SIDDHANTIC:
        assert resolved(method_id).era == "kali"
        assert run(method_id).runs_from == eras["kali"].era.epoch


def _eras() -> dict[str, EraFile]:
    return dict(load_eras(REPO / "jyotirganita" / "data", context_for(REPO), REPO))


# --- flags before composed and before a layer's epoch; nothing refused ----------------


@pytest.mark.parametrize("method_id", SIDDHANTIC)
def test_before_composition_flags_every_day_before_composed_and_none_after(
    method_id: str,
) -> None:
    flag = f"before_composition:{method_id}"
    r = run(method_id)
    first = _first_day_with_years(r, _threshold(method_id, flag))
    for jdn in (r.runs_from, r.runs_from.plus_days(1), first.plus_days(-1)):
        assert flag in r.day(jdn).flags
    for jdn in (first, first.plus_days(1), _sample_days()[0]):
        assert flag not in r.day(jdn).flags


def test_parahita_flags_before_the_layer_epoch_and_before_its_definition() -> None:
    r = run("parahita")
    epoch = _first_day_with_years(r, _threshold("parahita", "before_epoch:sakabda_samskara"))
    defined = _first_day_with_years(
        r, _threshold("parahita", "before_composition:sakabda_samskara")
    )
    assert epoch.days_since(defined) < 0  # Śaka 444 precedes Kali 3785
    before_epoch = r.day(epoch.plus_days(-1))
    assert {
        "before_epoch:sakabda_samskara",
        "before_composition:sakabda_samskara",
        "before_composition:parahita",
    } <= set(before_epoch.flags)
    assert before_epoch.layer_counts["sakabda_samskara"] < 0
    between = r.day(epoch)
    assert "before_epoch:sakabda_samskara" not in between.flags
    assert "before_composition:sakabda_samskara" in between.flags
    assert between.layer_counts["sakabda_samskara"] == 0
    after = r.day(defined)
    assert not {f for f in after.flags if f.startswith(("before_epoch:", "before_composition:"))}


@pytest.mark.parametrize("method_id", SIDDHANTIC)
def test_nothing_is_refused_on_a_flag(method_id: str) -> None:
    r = run(method_id)
    step = 36525 * 3  # every third century from runs_from to beyond 2100
    end = jdn_from_gregorian(GregorianDate(2101, 1, 1))
    jdn = r.runs_from
    while jdn.days_since(end) < 0:
        day = r.day(jdn)
        assert day.flags == tuple(sorted(day.flags))
        jdn = jdn.plus_days(step)


@pytest.mark.parametrize("method_id", SIDDHANTIC)
def test_every_record_carries_its_status_flag_and_its_place(method_id: str) -> None:
    day = run(method_id).day(_sample_days()[0])
    region, place = place_of(method_id)
    # Laṅkā is no longer provisional; the samarekhā place is
    assert (place_flag(region, place) in day.flags) is (method_id in OWN_PLACE)
    # the flag follows the status the ledger computes
    status = load_registry(
        REPO / "jyotirganita" / "methods" / "registry.yaml", context_for(REPO).sources
    )[method_id].status
    assert ("provisional_method" in day.flags) is (status == "provisional")
    assert day.provenance["observer"] == f"{region}.{place}"
    assert day.provenance["observer_route"] == "text_units"


# --- procedures ------------------------------------------------------------------------


def _procedure_data() -> list[Record]:
    return [r for r in records().data.values() if "procedure" in r.raw]


def test_every_procedure_name_resolves_in_its_slot() -> None:
    for method_id in SIDDHANTIC:
        for slot, rec in resolved(method_id).procedures.items():
            assert slot in SLOTS
            if rec.kind != "gap":
                assert resolve(str(rec.raw["procedure"]), slot).name == rec.raw["procedure"]
    for rec in _procedure_data():
        resolve(str(rec.raw["procedure"]))


def test_every_registered_procedure_is_used_or_reserved() -> None:
    used = {str(r.raw["procedure"]) for r in _procedure_data()}
    for name, p in REGISTRY.items():
        assert name in used or p.reserved, f"{name}: neither used nor reserved"


def test_every_registered_procedure_has_a_test_a_declaration_or_a_pending_package() -> None:
    by_name: dict[str, list[Record]] = {}
    for rec in _procedure_data():
        by_name.setdefault(str(rec.raw["procedure"]), []).append(rec)
    for name, recs in by_name.items():
        for rec in recs:
            tested = any(v.startswith("authority/") for v in rec.verified_by)
            declared = rec.raw.get("no_printed_example") is not None
            pending = str(rec.raw.get("provisional", "")).startswith("pending")
            assert tested or declared or pending, f"{rec.key} ({name})"
            if declared:
                assert f"provisional:{rec.key}" in rec.flags


def test_an_unknown_slot_or_procedure_is_refused() -> None:
    from jyotirganita.siddhantic.procedures import UnknownProcedure

    with pytest.raises(UnknownProcedure, match="not in the registry"):
        resolve("no.such_procedure")
    with pytest.raises(UnknownProcedure, match="registered for"):
        resolve("epicycle.manda_bhujaphala", "sighra")


# --- base and layers ---------------------------------------------------------------------


def test_a_layered_method_is_its_base_with_its_layers() -> None:
    base, layered = resolved("aryabhatiya"), resolved("parahita")
    assert layered.method.base == "aryabhatiya" and layered.method.layers == ("sakabda_samskara",)
    assert [x.id for x in layered.layers] == ["sakabda_samskara"] and base.layers == ()
    for slot, rec in base.procedures.items():
        assert layered.procedures[slot] is rec
    assert {"layer.step", "layer.count_reckoning", "layer.negative_count"} <= set(
        layered.procedures
    )
    assert layered.runs_from == base.runs_from


REPLACING = [m for m in SIDDHANTIC if resolved(m).method.replaces]


@pytest.mark.parametrize("method_id", REPLACING)
def test_a_replacing_method_is_its_base_with_the_named_data(method_id: str) -> None:
    # replaces: every slot resolves to the base's datum; the
    # composed data read each replacement in place of the datum it replaces
    r = resolved(method_id)
    base = resolved(str(r.method.base))
    assert r.procedures.keys() == base.procedures.keys()
    for slot, rec in base.procedures.items():
        assert r.procedures[slot] is rec, slot
    for old, new in r.method.replaces.items():
        assert new in r.data.used and old not in r.data.used
        assert old in base.data.used and new not in base.data.used
    assert r.runs_from == base.runs_from and r.layers == ()


def test_a_replacing_method_is_registered() -> None:
    assert REPLACING == ["suryasiddhanta_paramesvara_recension"]


def test_the_layer_moves_the_positions_after_its_epoch() -> None:
    jdn = _sample_days()[0]
    a, p = run("aryabhatiya").day(jdn), run("parahita").day(jdn)
    assert p.layer_counts["sakabda_samskara"] > 0
    assert a.mean["sun"] == p.mean["sun"]  # the layer states no rate for the Sun
    assert a.mean["moon"] != p.mean["moon"]


# --- the hybrid sunrise ---------------------------------


class _TestSunrise:
    """A test-only provider: sunrise a fixed fraction of the day after mean midnight."""

    id = "test.fixed_quarter_day"

    def sunrise_fraction(self, jdn: JDN, observer: Observer) -> float:
        return 0.25

    def sunset_fraction(self, jdn: JDN, observer: Observer) -> float | None:
        return 0.75


SUNRISE_KEY = "texts.aryabhatiya.procedures.civil_day.definition"


def _repo_with_a_sunrise_gap(tmp: Path) -> Path:
    # the registers are absent from a copy without them, whose records read the shipped
    # ids instead
    for rel in ("jyotirganita", "tests/authority", "ISSUES.md", "DECISIONS.md"):
        src, dst = REPO / rel, tmp / rel
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "ephemerides"))
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    path = tmp / "jyotirganita/data/texts/aryabhatiya/procedures.yaml"
    doc = load_exact(path)
    i = next(i for i, d in enumerate(doc) if d["key"] == SUNRISE_KEY)
    doc[i] = {
        "key": SUNRISE_KEY,
        "status": "gap",
        "reason": "planted for the hybrid test (tests/conformance/test_methods.py)",
        "searched": "planted",
        "effect": "the hybrid sunrise is required",
    }
    path.write_text(dump_canonical(doc), encoding="utf-8")
    return tmp


@pytest.fixture(scope="module")
def gap_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _repo_with_a_sunrise_gap(tmp_path_factory.mktemp("sunrise_gap"))


def test_a_sunrise_gap_needs_the_declared_geometric_alternative(gap_repo: Path) -> None:
    r = load_method("aryabhatiya", gap_repo)
    obs = load_place(gap_repo, REGION, PLACE, r.records.data)
    with pytest.raises(EngineRefusal, match="sunrise datum is a gap"):
        build(r, obs)


@pytest.mark.parametrize("method_id", SIDDHANTIC)
def test_the_hybrid_sunrise_flags_every_record(method_id: str, gap_repo: Path) -> None:
    r = load_method(method_id, gap_repo)
    obs = load_place(gap_repo, *place_of(method_id), r.records.data)
    hybrid = build(r, obs, sunrise_provider=_TestSunrise())
    quantum = hybrid.provenance["sunrise"]["siddhantic.hybrid_sunrise_quantum"]
    assert hybrid.provenance["sunrise"]["provider"] == _TestSunrise.id
    assert Fraction(quantum) == r.parameters["siddhantic.hybrid_sunrise_quantum"]
    text = run(method_id).day(_sample_days()[0])
    for jdn in (hybrid.runs_from, *_sample_days()[:3]):
        day = hybrid.day(jdn)
        assert "hybrid_sunrise:modern_geometric" in day.flags
        assert hybrid.engine.civil_day(jdn).sunrise_after_local_midnight == Nadika(15)
        # the provider's sunset, three quarters of the day, passes through quantised
        sunset = hybrid.engine.day(jdn).sunset
        assert sunset == Nadika(45)
    # sunrise a quarter day after mean midnight is the text's mean sunrise: no carry
    if table_driven(method_id):
        # the table text's record carries its means to its own sunrise (goladipika_1916 v. 195):
        # the hybrid's are the means at the computation instant, uncarried. The
        # comparison reaches the engine's own private TableEngine._means_at (no
        # public accessor): it is the engine's uncarried mean that is compared, so
        # a rename of that helper must move here too
        eng = run(method_id).engine
        assert isinstance(eng, TableEngine)
        uncarried = eng._means_at(_sample_days()[0], Fraction(0))
        assert hybrid.day(_sample_days()[0]).mean == uncarried != text.mean
    else:
        assert hybrid.day(_sample_days()[0]).mean == text.mean


def test_weekday_of_the_runs_from_day_is_the_text_s_first() -> None:
    r = run("aryabhatiya")
    assert r.day(r.runs_from).weekday == weekday(r.runs_from)


# --- the day: sunrise, carry, endings, intraday ----------------

#: the methods whose sunrise, carry and ending data are keyed: every siddhantic method
KEYED_DAY = SIDDHANTIC
#: the methods whose gati is the sunrise difference: no seam
SUNRISE_DIFFERENCE = [
    m
    for m in KEYED_DAY
    if resolved(m).procedures["gati"].raw["procedure"] == "gati.sunrise_difference"
]
KERALA = "kerala"
KERALA_OBSERVER = "kozhikode"
DAY_SLOTS = (
    "sunrise",
    "computation_instant",
    *CARRY_SLOTS,
    "declination",
    "declination.argument",
    "ascensional_difference",
    "half_day",
    "gati",
    "proportional_parts",
    "intraday",
    "ending_rounding",
)


@cache
def seeded_year() -> int:
    """The year of the day's items, drawn from 1900–2099 by ``seeds.conformance_year``."""
    return random.Random(seed("seeds.conformance_year")).randrange(1900, 2100)


def _year_days(year: int) -> list[JDN]:
    first = jdn_from_gregorian(GregorianDate(year, 1, 1))
    last = jdn_from_gregorian(GregorianDate(year + 1, 1, 1))
    return [first.plus_days(i) for i in range(last.days_since(first))]


@cache
def kerala_run(method_id: str) -> MethodRun:
    return build(resolved(method_id), load_place(REPO, KERALA, KERALA_OBSERVER, records().data))


@pytest.mark.parametrize("method_id", KEYED_DAY)
def test_sunrise_carry_ending_and_intraday_data_are_present_and_resolved(method_id: str) -> None:
    procs = resolved(method_id).procedures
    for slot in DAY_SLOTS:
        rec = procs[slot]
        if rec.kind == "gap":
            # the sunrise resolves only with the hybrid alternative in force; an ending
            # rounding no text states leaves the endings exact
            assert slot in ("sunrise", "ending_rounding"), slot
            continue
        assert resolve(str(rec.raw["procedure"]), slot)
        assert not str(rec.raw.get("provisional", "")).startswith("pending")
    if table_driven(method_id):
        # the Dṛk line: each carry on every mean element at mean motion (goladipika_1916 v. 196–207)
        for slot in CARRY_SLOTS:
            raw = procs[slot].raw
            assert (raw["acts_on"], raw["motion"], tuple(raw["applies_to"])) == TABLE_CARRY
        return
    if surya(method_id):
        # ruling (h): the deśāntara and the cara move the means' time at mean motion,
        # the bhujāntara the true place of every body
        model = resolved(method_id).model
        assert isinstance(model, SuryaModel)
        for slot, (acts_on, motion, applies_to) in SURYA_CARRY.items():
            raw = procs[slot].raw
            assert (raw["acts_on"], raw["motion"]) == (acts_on, motion), slot
            assert sorted(raw["applies_to"]) == sorted(applies_to or model.planets), slot
        for slot in SURYA_FALLBACK:  # the composition no verse states
            assert procs[slot].raw["basis"] == "fallback_no_stated_rule"
        return
    model = resolved(method_id).text_model
    for c in model.carries:
        assert c.acts_on and c.motion and (c.applies_to or c.acts_on == "sunrise_instant_only")
    for slot in CARRY_SLOTS[1:]:
        covered = [b for c in model.carries if c.slot == slot for b in c.applies_to]
        assert sorted(covered) == sorted(model.planets)


@pytest.mark.parametrize("method_id", SUNRISE_DIFFERENCE)
def test_no_seam_where_the_gati_is_the_sunrise_difference(method_id: str) -> None:
    r = kerala_run(method_id)
    for jdn in _year_days(seeded_year()):
        assert not [f for f in r.day(jdn).flags if f.startswith("seam:")], jdn


def test_a_seam_is_flagged_in_both_days_records() -> None:
    """With a gati that is not the sunrise difference (the mean motion), seams appear in pairs.

    The path is forced by replacing the engine's gati with the mean motion
    (a stand-in, no text's rule): a check of the seam mechanics only, not
    evidence about any printed case.
    """
    r = build(resolved("aryabhatiya"), load_place(REPO, KERALA, KERALA_OBSERVER, records().data))
    model = r.resolved.text_model
    mean_motion = {
        b: Fraction(model.revolutions[p.mean] * 360, model.civil_days)
        for b, p in model.planets.items()
    }
    r.engine.gati = lambda body, jdn: mean_motion[body]  # type: ignore[method-assign]
    assert _seams_in_pairs(r, _year_days(seeded_year())[:60]) > 0


def _seams_in_pairs(r: MethodRun, days: list[JDN]) -> int:
    """The seam flags on ``days``, each found on the day before or after as well."""
    seams = {d.value: set(f for f in r.day(d).flags if f.startswith("seam:")) for d in days}
    found = 0
    for d in days[:-1]:
        after = r.seams(d.plus_days(1))
        for flag in seams[d.value]:
            found += 1
            prev = r.seams(d.plus_days(-1)) if d != days[0] else set()
            assert flag in after or flag in prev
    return found


@pytest.mark.parametrize("method_id", [m for m in KEYED_DAY if surya(m)])
def test_the_equation_of_motion_gati_flags_its_seams_in_both_days_records(
    method_id: str,
) -> None:
    """The Sūrya-siddhānta's own gati (ii.47–51) is not the sunrise difference: seams occur.

    Over the seeded year: the recension's seams are fewer, none in its first 60 days.
    """
    assert _seams_in_pairs(kerala_run(method_id), _year_days(seeded_year())) > 0


@pytest.mark.parametrize("method_id", KEYED_DAY)
def test_every_transition_inside_a_day_is_the_proportional_parts_ending(method_id: str) -> None:
    r = kerala_run(method_id)
    eng = r.engine
    nadis = r.resolved.model.units.nadis_per_day
    checked = 0
    for jdn in _year_days(seeded_year())[:40]:
        ends = r.day(jdn).endings
        for name in ENDING_ELEMENTS:
            n = ends[name]
            if not 0 < n.value < nadis:
                continue
            el = elements.ELEMENTS[name]
            at = eng.instant(jdn, n)
            sun, moon = (eng.sidereal_longitude(b, at).arc for b in ("sun", "moon"))
            start = eng.sidereal_longitude("sun", eng.instant(jdn, Nadika(0))).arc
            mstart = eng.sidereal_longitude("moon", eng.instant(jdn, Nadika(0))).arc
            assert elements.remaining(el, sun, moon) == elements.span(el, sun)
            assert (
                elements.index(el, sun, moon) % el.count
                == (elements.index(el, start, mstart) % el.count + 1) % el.count
            )
            checked += 1
    assert checked > 0


@pytest.mark.parametrize("method_id", KEYED_DAY)
def test_the_record_s_sunrise_sunset_and_day_length_leaves(method_id: str) -> None:
    r = kerala_run(method_id)
    days = _year_days(seeded_year())
    text = resolved(method_id).method.text
    for jdn in days[:31]:
        d = r.day(jdn)
        assert d.standard == f"text_local:{text}"
        assert d.sunset is not None and d.sunset.value > d.sunrise.value
        nxt = r.day(jdn.plus_days(1))
        assert d.day_length_nadika == Nadika(60) + nxt.sunrise - d.sunrise
        assert set(d.endings) == set(ENDING_ELEMENTS)
        assert all(isinstance(v, Nadika) and v.value > 0 for v in d.endings.values())
    # at the equator the cara vanishes: the day is half the day and night
    eq = run(method_id).day(days[0])
    assert eq.sunset is not None and eq.sunset - eq.sunrise == Nadika(30)


def test_the_kerala_place_table_states_a_route_or_a_gap_for_every_place() -> None:
    routes: dict[str, str] = {}
    for pid in place_ids(REPO, KERALA):
        try:
            routes[pid] = load_place(REPO, KERALA, pid, records().data).route
        except PlaceError as e:
            assert "no route serves this place" in str(e)
            routes[pid] = "gap"
    assert routes == {
        "kozhikode": "modern_converted",
        "thiruvananthapuram": "modern_converted",
        "thrissur": "modern_converted",
        "thalassery": "gap",
        "kochi": "gap",
    }
    for method_id in KEYED_DAY:
        for pid, route in routes.items():
            if route != "gap":
                obs = load_place(REPO, KERALA, pid, records().data)
                assert build(resolved(method_id), obs).day(_sample_days()[0]).sunset is not None


#: the identification datum read in place of the Dṛggaṇita's own meridian datum,
#: the gap it stands in for, and the gap the Rsine table fills
DRK_IDENTIFICATION = "texts.drgganita.samarekha.identification.grahanamandana_1965"
DRK_MERIDIAN_GAP = "texts.drgganita.samarekha.modern_longitude"
DRK_RSINE_GAP = "texts.drgganita.trig.rsine_table"


def test_the_drgganita_at_a_kerala_place_is_provisional_on_its_route_and_its_table() -> None:
    """Route (b) through the editor's identification, on grahanamandana_1965's table."""
    r = kerala_run("drgganita")
    assert isinstance(r.engine, TableEngine)
    day = r.day(_sample_days()[0])
    assert f"provisional:{DRK_IDENTIFICATION}" in day.flags
    assert f"provisional:{DRK_RSINE_GAP}" in day.flags
    route = day.provenance["observer_route_data"]
    assert route[:2] == [DRK_IDENTIFICATION, DRK_MERIDIAN_GAP]
    # the meridian datum read (laghubhaskariya_1963)
    assert route[2].startswith("texts.aryabhatiya.")
    # hashed with the place, outside data_files: the scan at the samarekhā serves it
    meridian = records().data[route[2]].path
    assert meridian in day.provenance["observer_route_files"]
    assert meridian not in day.provenance["data_files"]
    # the place's other text runs on its own meridian datum: no identification
    other = kerala_run("aryabhatiya").day(_sample_days()[0])
    assert f"provisional:{DRK_IDENTIFICATION}" not in other.flags
    assert "observer_route_data" not in other.provenance


@pytest.mark.parametrize("method_id", SIDDHANTIC)
def test_the_full_evaluation_diagnostic_is_flagged(method_id: str) -> None:
    obs = load_place(REPO, KERALA, KERALA_OBSERVER, records().data)
    diag = build(resolved(method_id), obs, intraday=FULL_EVALUATION)
    jdn = _sample_days()[0]
    day = diag.day(jdn)
    assert f"diagnostic:{FULL_EVALUATION}" in day.flags
    plain = kerala_run(method_id)
    assert day.true == plain.day(jdn).true  # the same at sunrise
    lon = diag.engine.sidereal_longitude("moon", diag.engine.instant(jdn, Nadika(10)))
    assert lon.arc.unit is AngleUnit.DEGREE


# --- the Sūrya-siddhānta's sunrise, carry and endings ------------------

DEFERRAL_PROCEDURE = "deferred.pending_keying"
#: Whitney's identification of the prime meridian (suryasiddhanta_burgess_1860 i.62 note) read in
#: place of the
#: modern longitude no verse states, and the gap it stands in for (route (b))
SURYA_IDENTIFICATION = "texts.suryasiddhanta.meridian.identification.suryasiddhanta_burgess_1860"
SURYA_MERIDIAN_GAP = "texts.suryasiddhanta.meridian.modern_longitude"


def test_no_slot_names_the_deferral_and_every_method_has_its_day_keyed() -> None:
    assert KEYED_DAY == SIDDHANTIC
    for method_id in SIDDHANTIC:
        procs = resolved(method_id).procedures
        assert not [s for s in DAY_SLOTS if procs[s].raw.get("procedure") == DEFERRAL_PROCEDURE]


@pytest.mark.parametrize("method_id", [m for m in SIDDHANTIC if surya(m)])
def test_the_surya_siddhanta_at_a_kerala_place_is_provisional_on_its_identification(
    method_id: str,
) -> None:
    r = kerala_run(method_id)
    assert isinstance(r.engine, SuryaEngine)
    day = r.day(_sample_days()[0])
    assert f"provisional:{SURYA_IDENTIFICATION}" in day.flags
    route = day.provenance["observer_route_data"]
    assert route[:2] == [SURYA_IDENTIFICATION, SURYA_MERIDIAN_GAP]
    # off the equator the cara is applied by the engine's composition (ruling (h))
    assert f"provisional:texts.suryasiddhanta.{CARA_GAP}" in day.flags
    # at its own meridian on the equator: no identification and no cara
    own = run(method_id).day(_sample_days()[0])
    assert f"provisional:{SURYA_IDENTIFICATION}" not in own.flags
    assert not [f for f in own.flags if f.endswith(CARA_GAP)]
