"""The conformance items of profiles, era and time-standard records, presets.

The items: regional
profiles, era records and time-standard records load; every name has an
id and a list of accepted Latin spellings; a fictitious second profile
with its own era loads and produces calendar leaves with no change under
``jyotirganita/``; every preset of §9's table that the registry can serve
exists, is complete once an observer is given and rejected without one,
names its time standard, and no preset file exists outside the table; a
convention set that pins its observer rejects a call naming another
(a test-only set until a ``crc`` set is keyed); the ``text_only`` set emits
exactly its leaves; the effective composition date is printed per preset
by the ledger, a day before it carries the latest component's flag and
nothing refuses on it; every ``provisional`` convention, rule or name
table carries its reason and its flag; ``fixed_tropical_offset`` and
``at_midnight`` run through a test-only engine and refuse under the siddhantic one.
"""

from __future__ import annotations

import shutil
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from jyotirganita.calendar.assignment import DayPoints, NotModelledRule, assign
from jyotirganita.calendar.day import (
    NOT_IN_PRESET,
    OCCURRENCE_ELEMENTS,
    TEXT_ONLY,
    Calendar,
    conventions_of,
)
from jyotirganita.calendar.months import MeanSun, MonthRuleNotModelled, MonthStream
from jyotirganita.calendar.occurrences import SourceDay, day_occurrences
from jyotirganita.core.calendar import Weekday
from jyotirganita.core.types import (
    JDN,
    AngleUnit,
    FloatArc,
    ModernCivilInstant,
    Nadika,
    NutationIdentity,
    TropicalLongitude,
    TrueOfDate,
)
from jyotirganita.data.datum import Records, context_for, load_records
from jyotirganita.data.eras import EraFile, load_eras
from jyotirganita.data.time_standards import load_time_standards
from jyotirganita.data.yamlio import dump_canonical, load_exact
from jyotirganita.methods.compose import REPO, build, load_method
from jyotirganita.methods.presets import (
    PRESET_TABLE,
    PresetError,
    effective_composition,
    load_preset,
    open_preset,
    parse_preset,
    preset_ids,
    resolve,
)
from jyotirganita.methods.registry import load_registry
from jyotirganita.regions.base import load_profile, profile_ids
from jyotirganita.regions.places import load_place

OBSERVER = "kerala/kozhikode"
#: a preset whose method serves no Kerala place yet runs at its own observer, and without a
#: sunset under the profile's selectable month rule (drgganita_1963 I.ii.7 defers the sunrise and
#: the carry; tools/regression.py RUNS)
OWN_RUN: dict[str, tuple[str, str | None]] = {
    "drgganita_kerala": ("meridians/drgganita_samarekha", "following_day"),
    # the text's meridian on the equator
    "suryasiddhanta_text": ("meridians/suryasiddhanta_lanka", None),
    "suryasiddhanta_paramesvara_recension_text": ("meridians/suryasiddhanta_lanka", None),
}


@cache
def records() -> Records:
    return load_records(REPO, context_for(REPO))


@cache
def eras() -> dict[str, EraFile]:
    return load_eras(REPO / "jyotirganita" / "data", context_for(REPO), REPO)


def _registry_methods() -> dict[str, Any]:
    ctx = context_for(REPO)
    return dict(load_registry(REPO / "jyotirganita" / "methods" / "registry.yaml", ctx.sources))


# --- profiles, era records, time standards ---------------------------------------------------


@pytest.mark.parametrize("region", profile_ids(REPO))
def test_every_profile_loads_with_ids_and_spellings(region: str) -> None:
    p = load_profile(REPO, region, records().data, eras())
    for cls, count in p.counts.items():
        names = [p.name(cls, i) for c, i in p.names if c == cls]
        assert len(names) == count
        assert len({n.id for n in names}) == count
        assert all(n.forms["latin"] for n in names), cls
    for spec in p.eras:
        assert spec.era in eras()


def test_era_and_time_standard_records_load() -> None:
    assert {"kali", "saka", "kollam"} <= set(eras())
    assert {"lmt", "madras_time", "ist"} <= set(load_time_standards(REPO, context_for(REPO)))


def test_every_provisional_part_carries_its_reason_and_its_flag() -> None:
    p = load_profile(REPO, "kerala", records().data, eras())
    assert p.provisional and all(r.strip() for r in p.provisional.values())
    _, _, cal = open_preset(REPO, "parahita_kerala", OBSERVER, records=records())
    day = cal.day(cal.source.runs_from.plus_days(1_850_000))
    assert p.month_rule.flag in day["flags"]
    scripts = Calendar(cal.run, conventions_of(p), eras(), scripts=("malayalam",))
    leaves = scripts.day(cal.source.runs_from.plus_days(1_850_000))
    assert p.name_flags["malayalam"] in leaves["flags"]


# --- the fictitious second profile -----------------------------------------------------------

FICT = "fictia"


def _copy_repo(tmp: Path) -> Path:
    # the registers are absent from a copy without them, whose records read the shipped
    # ids instead
    for rel in ("jyotirganita", "tests/authority", "ISSUES.md", "DECISIONS.md"):
        src, dst = REPO / rel, tmp / rel
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "ephemerides"))
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return tmp


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_canonical(doc), encoding="utf-8")


def _fictitious(tmp: Path) -> Path:
    repo = _copy_repo(tmp)
    kerala = repo / "jyotirganita" / "regions" / "kerala"
    names = load_exact(kerala / "names.yaml")
    names["region"] = FICT
    names["notes"] = (
        "A fictitious profile (tests/conformance): Kerala's Latin names, no data of its own."
    )
    for n in names["names"]:
        n["forms"] = {"latin": n["forms"]["latin"]}
    names["data"] = []
    conv = load_exact(kerala / "conventions.yaml")
    conv["region"] = FICT
    conv["eras"] = [{"era": "fict"}]
    conv["data"] = []
    places = load_exact(kerala / "places.yaml")
    places["region"] = FICT
    places["places"] = [dict(places["places"][0], id="somewhere", name="Somewhere")]
    era = load_exact(repo / "jyotirganita" / "data" / "eras" / "saka.yaml")
    text = dump_canonical(era).replace("eras.saka.", "eras.fict.").replace("era: saka", "era: fict")
    region = repo / "jyotirganita" / "regions" / FICT
    _write(region / "names.yaml", names)
    _write(region / "conventions.yaml", conv)
    _write(region / "places.yaml", places)
    (repo / "jyotirganita" / "data" / "eras" / "fict.yaml").write_text(text, encoding="utf-8")
    return repo


def _code(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in (root / "jyotirganita").rglob("*.py")
        if "__pycache__" not in p.parts
    }


def test_a_fictitious_second_profile_with_its_own_era_runs_unchanged(tmp_path: Path) -> None:
    repo = _fictitious(tmp_path)
    assert _code(repo) == _code(REPO)
    ctx = context_for(repo)
    recs = load_records(repo, ctx)
    era_files = load_eras(repo / "jyotirganita" / "data", ctx, repo)
    assert FICT in profile_ids(repo)
    profile = load_profile(repo, FICT, recs.data, era_files)
    run = build(
        load_method("parahita", repo, records=recs), load_place(repo, FICT, "somewhere", recs.data)
    )
    cal = Calendar(run, conventions_of(profile), era_files)
    day = cal.day(run.runs_from.plus_days(1_850_000))
    assert set(day["eras"]) == {"fict"}
    assert day["eras"]["fict"]["year"] > 0
    assert day["masa"]["name"] in {n.id for (c, _), n in profile.names.items() if c == "masa"}


# --- presets ----------------------------------------------------------------------------------


def _shipped() -> list[str]:
    return preset_ids(REPO)


def _shipped_siddhantic() -> list[str]:
    """The siddhantic presets (a modern preset has no composition date)."""
    return [p for p in _shipped() if load_preset(REPO, p).engine == "siddhantic"]


def test_no_preset_exists_outside_the_design_table() -> None:
    assert set(_shipped()) <= set(PRESET_TABLE)


def test_every_siddhantic_method_has_its_preset() -> None:
    methods = _registry_methods()
    named = {load_preset(REPO, p).method for p in _shipped()}
    assert {m for m, e in methods.items() if e.engine == "siddhantic"} <= named


@pytest.mark.parametrize("preset_id", _shipped())
def test_a_preset_is_complete_with_an_observer_and_rejected_without(preset_id: str) -> None:
    p = load_preset(REPO, preset_id)
    with pytest.raises(PresetError, match="names the observer"):
        resolve(p, None)
    r = resolve(p, OBSERVER)
    assert len(r.config_hash) == 64
    if p.engine == "siddhantic":
        assert r.config["time_standard"] == f"text_local:{p.text}"
    else:
        assert r.config["time_standard"] in load_time_standards(REPO, context_for(REPO))
    assert set(r.config) == {*p.as_config(), "observer"}
    assert "docs/verification.md" in p.header["range"]
    assert r.config_hash != resolve(p, "kerala/thiruvananthapuram").config_hash


def test_an_incomplete_or_unknown_preset_is_rejected() -> None:
    doc = load_exact(REPO / "jyotirganita/methods/presets/parahita_kerala.yaml")
    for field in ("time_standard", "variants", "observer"):
        broken = {k: v for k, v in doc.items() if k != field}
        with pytest.raises(PresetError, match="missing"):
            parse_preset(broken, "test", REPO)
    with pytest.raises(PresetError, match="preset table"):
        parse_preset(dict(doc, preset="parahita_tamil"), "test", REPO)
    with pytest.raises(PresetError, match="text_local"):
        parse_preset(dict(doc, time_standard="ist"), "test", REPO)


def test_a_set_that_pins_its_observer_rejects_another() -> None:
    doc = load_exact(REPO / "jyotirganita/methods/presets/parahita_kerala.yaml")
    pinned = parse_preset(dict(doc, observer={"pinned": OBSERVER}), "test-only set", REPO)
    assert resolve(pinned, None).observer == OBSERVER
    assert resolve(pinned, OBSERVER).observer == OBSERVER
    with pytest.raises(PresetError, match="pin the observer"):
        resolve(pinned, "kerala/thiruvananthapuram")


@pytest.mark.parametrize("preset_id", _shipped_siddhantic())
def test_composition_date_is_printed_flagged_and_refuses_nothing(preset_id: str) -> None:
    observer, month_rule = OWN_RUN.get(preset_id, (OBSERVER, None))
    _, run, cal = open_preset(REPO, preset_id, observer, records=records(), month_rule=month_rule)
    comp = effective_composition(run.resolved)
    on, before = cal.day(comp.first_day), cal.day(comp.first_day.plus_days(-1))
    flag = f"before_composition:{comp.component}"
    assert flag in before["flags"]
    assert not any(f.startswith("before_composition:") for f in on["flags"])


def test_text_only_emits_exactly_its_leaves() -> None:
    _, run, cal = open_preset(REPO, "aryabhatiya_text", OBSERVER, records=records())
    assert cal.conventions is TEXT_ONLY
    day = cal.day(run.runs_from.plus_days(1_850_000))
    assert set(day["eras"]) == {"kali"}
    assert day["eras"]["kali"]["sun"] == "mean" and "ahargana" in day["eras"]["kali"]
    assert isinstance(day["masa"]["rasi_index"], int)
    assert day["masa"]["name"] == day["masa"]["day"] == NOT_IN_PRESET
    assert isinstance(day["weekday"]["index"], int) and day["weekday"]["name"] == NOT_IN_PRESET
    for e in OCCURRENCE_ELEMENTS:
        for o in day[e]:
            name = o["name"]["name"] if e == "tithi" else o["name"]
            assert name == NOT_IN_PRESET
    assert not any(f.startswith("provisional:regions.") for f in day["flags"])


# --- fixed_tropical_offset and at_midnight through a test-only engine -----------------------


class _TestSource:
    """A source whose days the month stream never reads (the tropical rule reads the engine)."""

    id = "test"
    runs_from = JDN(0)

    def day(self, jdn: JDN) -> SourceDay:  # pragma: no cover - not reached
        raise AssertionError("the tropical rule reads the engine only")


class _TestEngine:
    """A tropical Sun moving one degree a day from 0° at JDN 2 400 000's day start (test only)."""

    zero = 2_400_000

    def instant(self, jdn: JDN, after_start: Nadika) -> ModernCivilInstant:
        return ModernCivilInstant(jdn, float(after_start.value / 60), "test")

    def tropical_longitude(
        self, body: str, instant: ModernCivilInstant
    ) -> TropicalLongitude[TrueOfDate]:
        days = instant.jdn.value - self.zero + instant.local_fraction
        nutation = NutationIdentity("test", "test-only")
        return TropicalLongitude(FloatArc(days % 360, AngleUnit.DEGREE), TrueOfDate, nutation)


def test_fixed_tropical_offset_runs_on_a_test_only_engine() -> None:
    # a mean Sun of one revolution in 360 days whose entries fall near the tropical ones
    mean = MeanSun(1, 360, 0, JDN(_TestEngine.zero + 23))
    stream = MonthStream(
        _TestSource(),
        mean,
        "fixed_tropical_offset",
        {"offset": Fraction(93, 4), "days_after": Fraction(1)},
        _TestEngine(),
    )
    # rāśi 2 begins when the longitude reaches 23°15′ + 30°, during day zero + 53;
    # the month begins the next day
    first = stream.start(2, 0)
    assert first.value == _TestEngine.zero + 53 + 1


def test_fixed_tropical_offset_refuses_under_the_siddhantic_engine() -> None:
    _, run, cal = open_preset(REPO, "parahita_kerala", OBSERVER, records=records())
    stream = MonthStream(
        cal.source,
        cal.mean,
        "fixed_tropical_offset",
        {"offset": Fraction(0), "days_after": Fraction(0)},
        run.engine,
    )
    with pytest.raises(MonthRuleNotModelled, match="tropical longitude"):
        stream.start(1, 5000)


def test_at_midnight_runs_where_a_midnight_is_stated_and_refuses_otherwise() -> None:
    labels = dict.fromkeys(("tithi", "nakshatra", "yoga", "karana", "rasi"), 1)
    common = dict(
        jdn=JDN(0),
        length=Nadika(60),
        sunrise=Nadika(0),
        sunset=Nadika(30),
        labels=labels,
        endings={e: Nadika(40) for e in labels},
        per_span={e: Nadika(70) for e in labels},
        flags=(),
        standard="test",
        sunrise_after_midnight=None,
        weekday=Weekday.MONDAY,
        ahargana=None,
    )
    modern = SourceDay(midnight=Nadika(45), **common)  # type: ignore[arg-type]
    occ = day_occurrences(modern, "tithi")
    assert (
        assign("at_midnight", occ, DayPoints(modern.length, modern.sunrise, modern.midnight)) == 2
    )
    siddhantic = SourceDay(midnight=None, **common)  # type: ignore[arg-type]
    with pytest.raises(NotModelledRule):
        assign("at_midnight", occ, DayPoints(siddhantic.length, siddhantic.sunrise, None))
