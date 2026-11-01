"""The conformance items of ``modern_de`` and its presets.

- every modern preset names ``observer_frame``, ``sunrise_event`` and
  ``node``, each with a datum that loads, and is complete once an observer
  is named (the shared item of ``test_profiles_presets.py`` covers the
  refusal without one);
- every model datum states its range (or ``range: unstated``) and keeps a
  stated accuracy apart from it; every model the engine builds states its
  range in words;
- each preset refuses a day outside its components' ranges, naming the
  component, and serves its first and last days;
- the engine protocol on a sampled year of ``modern_iers``, and no
  ``before_composition`` flag on a modern record (a modern run has no
  composition date);
- ``fixed_tropical_offset`` and ``at_midnight`` served by the real engine
  (beside the test-only engine of ``test_profiles_presets.py``);
- the 1868 month rule (reading 17): selected, it flags every record
  ``provisional:following_day``; the default is unchanged;
- the hybrid sunrise with the real provider
  (``modern/hybrid.py``) beside the test-only one of ``test_methods.py``,
  on days inside the modern engine's range.

The universal calendar invariants run on ``modern_iers`` in
``tests/invariants/test_calendar_layer_invariants.py``.
"""

from __future__ import annotations

import random
from fractions import Fraction
from functools import cache

import pytest

from jyotirganita.calendar.assignment import DayPoints, assign
from jyotirganita.calendar.day import Calendar
from jyotirganita.calendar.months import MonthStream
from jyotirganita.calendar.occurrences import day_occurrences
from jyotirganita.core.calendar import jdn_from_gregorian
from jyotirganita.core.types import (
    JDN,
    TT,
    AngleUnit,
    FloatArc,
    GregorianDate,
    ModernCivilInstant,
    Nadika,
    SiderealLongitude,
    TropicalLongitude,
)
from jyotirganita.data import engine_parameters
from jyotirganita.data.datum import Records, context_for, load_records
from jyotirganita.data.engine_parameters import seed
from jyotirganita.data.time_standards import load_time_standards
from jyotirganita.methods.compose import REPO, build, load_method
from jyotirganita.methods.presets import (
    PresetError,
    load_preset,
    open_modern_preset,
    preset_ids,
    resolve,
)
from jyotirganita.modern.engine import ModernConfig, ModernEngine
from jyotirganita.modern.hybrid import GeometricSunrise
from jyotirganita.modern.kernels import Ephemeris
from jyotirganita.modern.riseset import Event, ModernObserver
from jyotirganita.modern.run import ModernRun
from jyotirganita.modern.source import mean_locator
from jyotirganita.modern.timescales import OutOfRange
from jyotirganita.regions.places import load_modern_place, load_place

OBSERVER = "kerala/kozhikode"
REGION, PLACE = "kerala", "kozhikode"
DAYS_PER_YEAR = 365
DEGREES_PER_SIGN = 30


@cache
def records() -> Records:
    return load_records(REPO, context_for(REPO))


def _modern() -> list[str]:
    return [p for p in preset_ids(REPO) if load_preset(REPO, p).engine == "modern"]


def _kernel(preset_id: str) -> str:
    m = load_preset(REPO, preset_id).modern
    assert m is not None
    return str(m["kernel"])


def _params() -> list[object]:
    """The modern presets, one on DE441 under its tier (CI does not fetch DE441)."""
    return [
        pytest.param(p, marks=pytest.mark.de441) if _kernel(p) == "de441" else p for p in _modern()
    ]


@cache
def opened(preset_id: str) -> tuple[ModernRun, Calendar]:
    _, run, cal = open_modern_preset(REPO, preset_id, OBSERVER, records=records())
    return run, cal


# --- the preset files ------------------------------------------------------------------


@pytest.mark.parametrize("preset_id", _modern())
def test_a_modern_preset_names_frame_event_and_node_with_their_data(preset_id: str) -> None:
    p = load_preset(REPO, preset_id)
    assert p.modern is not None
    for field in ("observer_frame", "sunrise_event", "node"):
        datum = p.modern[field]["datum"]
        assert datum in records().data, (field, datum)
    assert p.modern["observer_frame"]["value"] == "geocentric"
    assert p.header["represents"] and p.header["hypothesis"]
    assert "docs/verification.md" in p.header["range"]
    with pytest.raises(PresetError, match="names the observer"):
        resolve(p, None)
    assert resolve(p, OBSERVER).observer == OBSERVER


def test_every_model_states_its_range_and_keeps_accuracy_apart() -> None:
    models = [r for r in records().data.values() if r.raw.get("kind") == "model"]
    assert models
    for r in models:
        rng = r.raw.get("range")
        assert rng == "unstated" or (isinstance(rng, dict) and {"from", "to"} <= set(rng)), r.key
        acc = r.raw.get("accuracy")
        if acc is not None:
            assert isinstance(acc, dict) and {"value", "interval"} <= set(acc), r.key
            assert acc != rng, r.key


@pytest.mark.parametrize("preset_id", _params())
def test_the_preset_serves_its_ends_and_refuses_beyond_naming_the_component(
    preset_id: str,
) -> None:
    run, _ = opened(preset_id)
    eng = run.engine
    names = (
        f"kernel {eng.ephemeris.entry.id}",
        f"ΔT model {eng.delta_t.id}",
        f"precession {eng.precession.id}",
    )
    assert run.source.day(run.runs_from).jdn == run.runs_from
    assert run.source.day(run.runs_to).jdn == run.runs_to
    for day in (run.runs_from.plus_days(-3), run.runs_to.plus_days(3)):
        with pytest.raises(OutOfRange) as err:
            run.source.day(day)
        assert any(n in str(err.value) for n in names), str(err.value)


# --- the engine protocol on a sampled year ------------------------------------------------


@cache
def sample_year() -> list[JDN]:
    """A Gregorian year inside ``modern_iers``'s range, drawn by ``seeds.modern_sample``."""
    run, _ = opened("modern_iers")
    rng = random.Random(seed("seeds.modern_sample"))
    first, last = run.runs_from, run.runs_to.plus_days(-DAYS_PER_YEAR)
    start = first.plus_days(rng.randrange(0, last.days_since(first)))
    return [start.plus_days(i) for i in range(DAYS_PER_YEAR)]


def test_the_engine_protocol_on_a_sampled_year() -> None:
    run, cal = opened("modern_iers")
    eng = run.engine
    assert eng.time_base is TT
    caps = eng.capabilities
    assert caps.bodies and caps.node
    assert set(caps.not_modelled) == {"eclipses"}
    frame_id = f"ayanamsa:{eng.ayanamsa.id}"
    for jdn in sample_year():
        frame = eng.civil_day(jdn)
        assert frame.jdn == jdn and frame.meridian == eng.standard.id
        assert frame.start == frame.sunrise == eng.instant(jdn, Nadika(0))
        assert frame.end == eng.civil_day(jdn.plus_days(1)).start
        assert isinstance(frame.sunset, ModernCivilInstant) and frame.sunset.jdn == jdn
        record = cal.day(jdn)
        assert not any(f.startswith("before_composition") for f in record["flags"])
        # modern_de is validated: no provisional_method flag
        assert ("provisional_method" in record["flags"]) is (run.method.status == "provisional")
    assert run.method.status == "validated"
    jdn = sample_year()[0]
    start = eng.civil_day(jdn).start
    for body in caps.bodies:
        lon = eng.sidereal_longitude(body, start)
        assert isinstance(lon, SiderealLongitude) and lon.frame == frame_id
        assert isinstance(eng.tropical_longitude(body, start), TropicalLongitude)
        assert isinstance(eng.latitude(body, start), FloatArc)
        assert isinstance(eng.daily_motion(body, jdn), FloatArc)
    assert eng.node(start).frame == frame_id


def test_at_midnight_is_served_by_the_real_engine() -> None:
    run, _ = opened("modern_iers")
    eng = run.engine
    for jdn in sample_year()[:5]:
        sd = run.source.day(jdn)
        assert sd.midnight is not None
        occ = day_occurrences(sd, "tithi")
        got = assign("at_midnight", occ, DayPoints(sd.length, sd.sunrise, sd.midnight))
        # the tithi in force at the day's local midnight, from the engine at that instant
        start, _, _, m0 = eng.day_bounds(jdn)
        midnight = m0 if start < m0 else eng.day_bounds(jdn.plus_days(1))[3]
        moon = eng.sidereal_at("moon", midnight).arc.to(AngleUnit.DEGREE).value
        sun = eng.sidereal_at("sun", midnight).arc.to(AngleUnit.DEGREE).value
        assert got == int(((moon - sun) % 360) // 12) + 1


def _offset(eng: ModernEngine) -> Fraction:
    """An offset of whole degrees near the sampled year's ayanāṃśa, so that each tropical
    target falls within the month stream's search around the sidereal locator's entry."""
    jdn = sample_year()[0]
    t = eng.day_bounds(jdn)[0]
    trop = eng.tropical_at("sun", t).arc.to(AngleUnit.DEGREE).value
    sid = eng.sidereal_at("sun", t).arc.to(AngleUnit.DEGREE).value
    return Fraction(round((trop - sid) % 360))


def test_fixed_tropical_offset_is_served_by_the_real_engine() -> None:
    run, _ = opened("modern_iers")
    eng = run.engine
    stream = MonthStream(
        run.source,
        mean_locator(eng),
        "fixed_tropical_offset",
        {"offset": _offset(eng), "days_after": Fraction(0)},
        eng,
    )
    for rasi in (1, 4, 7, 10):
        day = stream.start(rasi, 1)
        target = float(stream.parameters["offset"]) + DEGREES_PER_SIGN * (rasi - 1)

        def lon(d: JDN) -> float:
            v = eng.tropical_longitude("sun", eng.instant(d, Nadika(0))).arc
            return float(v.to(AngleUnit.DEGREE).value)

        # the Sun reaches the target during the returned day: short of it at the day's
        # start, past it at the next day's (the rule's days_after is zero)
        assert (lon(day) - target) % 360 > 360 - DEGREES_PER_SIGN
        assert (lon(day.plus_days(1)) - target) % 360 < DEGREES_PER_SIGN


def test_the_1868_month_rule_flags_its_records_and_the_default_is_unchanged() -> None:
    _, _, cal = open_modern_preset(
        REPO, "modern_iers", OBSERVER, records=records(), month_rule="following_day"
    )
    _, default = opened("modern_iers")
    jdn = sample_year()[0]
    assert "provisional:following_day" in cal.day(jdn)["flags"]
    assert "provisional:following_day" not in default.day(jdn)["flags"]
    assert default.month_rule is not None and default.month_rule.rule == "aparahna_parts"


# --- the hybrid sunrise with the real provider ----------------------------------


def _hybrid_engine() -> ModernEngine:
    """The modern engine on ``modern_smh``'s components at the siddhantic observer's place,
    on local mean time (the provider reads the day from local mean midnight)."""
    preset = load_preset(REPO, "modern_smh")
    assert preset.modern is not None and preset.time_standard == "lmt"
    m = preset.modern
    ev = m["sunrise_event"]
    cfg = ModernConfig(
        kernel=str(m["kernel"]),
        delta_t=str(m["delta_t"]["id"]),
        delta_t_seconds=None,
        precession=str(m["precession"]),
        nutation=str(m["nutation"]),
        ayanamsa=str(m["ayanamsa"]["id"]),
        ayanamsa_equinox=str(m["ayanamsa"]["equinox"]),
        ayanamsa_aberration=None,
        ayanamsa_coefficients=None,
        observer_frame="geocentric",
        sunrise_event=Event(str(ev["reference"]), str(ev["refraction"]), str(ev["dip"]), None),
        node=str(m["node"]["value"]),
        time_standard="lmt",
        civil_day_start="midnight",
    )
    mp = load_modern_place(REPO, REGION, PLACE, records().data)
    obs = ModernObserver(mp.id, mp.latitude_deg, mp.longitude_deg, Fraction(0), mp.flags)
    return ModernEngine(
        cfg,
        obs,
        data=records().data,
        time_standards=load_time_standards(REPO, context_for(REPO)),
        parameters=engine_parameters.load(),
        ephemeris=Ephemeris.open(cfg.kernel),
    )


def test_the_hybrid_sunrise_runs_with_the_real_provider() -> None:
    provider = GeometricSunrise(_hybrid_engine())
    r = load_method("parahita", REPO, records=records())
    obs = load_place(REPO, REGION, PLACE, r.records.data)
    hybrid = build(r, obs, sunrise_provider=provider)
    assert hybrid.provenance["sunrise"]["provider"] == provider.id
    assert "sunrise_event=" in provider.id and "delta_t=" in provider.id
    quantum = r.parameters["siddhantic.hybrid_sunrise_quantum"]
    first = jdn_from_gregorian(GregorianDate(1963, 1, 1))
    for jdn in (first, first.plus_days(100), first.plus_days(200)):
        day = hybrid.day(jdn)
        assert "hybrid_sunrise:modern_geometric" in day.flags
        got = hybrid.engine.civil_day(jdn).sunrise_after_local_midnight
        assert isinstance(got, Nadika)
        exact = Fraction(provider.sunrise_fraction(jdn, obs)) * 60
        assert abs(Fraction(got.value) - exact) <= quantum * 60


def test_the_real_provider_refuses_another_place_or_a_standard_other_than_lmt() -> None:
    provider = GeometricSunrise(_hybrid_engine())
    other = load_place(REPO, REGION, "thiruvananthapuram", records().data)
    with pytest.raises(ValueError, match="computed at"):
        provider.sunrise_fraction(jdn_from_gregorian(GregorianDate(1963, 1, 1)), other)
    run, _ = opened("modern_iers")
    with pytest.raises(ValueError, match="local mean time"):
        GeometricSunrise(run.engine)
