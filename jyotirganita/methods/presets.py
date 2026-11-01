"""Presets: ``methods/presets/<id>.yaml``.

A preset is a complete configuration but for the observer: its method, a
value for every variant the method declares, its convention set (a
regional profile or ``text_only``), its time standard, its intraday model,
its sunrise, its output selection and its engine data set (the text and
the layers). Nothing is defaulted: a missing or
unknown field, a time standard other than ``text_local:<text_id>`` for a
siddhantic method, a variant without a value or an engine data set that
is not the method's is rejected. The caller names the observer on every
call (``<region>/<place>`` from that region's ``places.yaml``) unless the
convention set pins one, in which case a call naming another is
rejected (:func:`resolve`).

The resolved configuration (the preset, the observer and every override)
is canonicalised (keys sorted, separators ``(',', ':')``, ASCII escapes)
and hashed (SHA-256); the hash is in every output. The keys are sorted.

Only the presets of the preset table may exist (:data:`PRESET_TABLE`). Each preset's header states
the printed practice it represents and what is hypothesis, and points to
``docs/verification.md``, which prints its date range (from the
method's ``runs_from``, no upper end) and its **effective composition
date** (:func:`effective_composition`): the latest of the method's
``composed``, its layers' ``defined`` and its selected variants'
``composed`` dates. Nothing refuses on it; a day
before it carries ``before_composition:<id>`` of the latest component.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jyotirganita.calendar.day import TEXT_ONLY, Calendar, ConventionSet, conventions_of
from jyotirganita.calendar.months import MeanSun
from jyotirganita.core.types import JDN
from jyotirganita.data.datum import Records, context_for, load_records
from jyotirganita.data.eras import EraFile, load_eras
from jyotirganita.data.yamlio import load_exact
from jyotirganita.methods.compose import MethodRun, ResolvedMethod, build, load_method
from jyotirganita.methods.registry import load_registry
from jyotirganita.regions.base import load_profile
from jyotirganita.regions.places import load_place
from jyotirganita.siddhantic.corrections import YearDatum
from jyotirganita.siddhantic.engine import FULL_EVALUATION, LINEAR_GATI
from jyotirganita.siddhantic.surya import SuryaModel
from jyotirganita.siddhantic.tabular import TableModel

if TYPE_CHECKING:
    from jyotirganita.modern.engine import ModernConfig
    from jyotirganita.modern.run import ModernRun

__all__ = [
    "PRESETS_DIR",
    "PRESET_TABLE",
    "Composition",
    "Preset",
    "PresetError",
    "Resolved",
    "effective_composition",
    "load_preset",
    "modern_config",
    "modern_run",
    "open_modern_preset",
    "open_preset",
    "parse_preset",
    "preset_ids",
    "resolve",
]

PRESETS_DIR = ("jyotirganita", "methods", "presets")
#: the preset table: no other preset exists
PRESET_TABLE = (
    "aryabhatiya_text",
    "ardharatrika_text",
    "parahita_kerala",
    "drgganita_kerala",
    "vakya_vararuci_kerala",
    "vakya_madhava_kerala",
    "suryasiddhanta_text",
    "suryasiddhanta_paramesvara_recension_text",
    "aryabhatiya_kerala",
    "suryasiddhanta_kerala",
    "suryasiddhanta_paramesvara_recension_kerala",
    "tantrasangraha_kerala",
    "modern_iers",
    "modern_smh",
    "modern_antiquity",
    "modern_crc",
)
FIELDS = (
    "preset",
    "header",
    "method",
    "variants",
    "conventions",
    "time_standard",
    "intraday",
    "sunrise",
    "output",
    "engine_data",
    "observer",
)
#: a modern preset's engine block: every component named
MODERN_FIELDS = (
    "kernel",
    "delta_t",
    "precession",
    "nutation",
    "ayanamsa",
    "observer_frame",
    "sunrise_event",
    "node",
    "observer_height_m",
)
MODERN_AYANAMSA_FIELDS = ("id", "equinox", "aberration", "coefficients")
MODERN_EVENT_FIELDS = ("reference", "refraction", "dip", "dip_height_m", "datum")
MODERN_CITED_FIELDS = ("value", "datum")
MODERN_HEIGHT_FIELDS = ("value", "basis")
MODERN_DELTA_T_FIELDS = ("id", "seconds")
#: a modern preset's intraday: positions evaluated at each instant, no chord
MODERN_INTRADAY = "modern.at_instant"
#: a modern preset's sunrise: its engine block's sunrise_event
MODERN_SUNRISE = "sunrise_event"
HEADER_FIELDS = ("represents", "hypothesis", "range")
OUTPUT_FIELDS = ("elements", "scripts")
INTRADAY = (LINEAR_GATI, FULL_EVALUATION)
TEXT_SUNRISE = "text"
TEXT_LOCAL = "text_local:"
RANGE_POINTER = "docs/verification.md"


class PresetError(ValueError):
    """A preset that is incomplete, unknown or inconsistent with its method."""


@dataclass(frozen=True, slots=True)
class Preset:
    """A preset as its file states it, checked against the registry."""

    id: str
    header: Mapping[str, str]
    method: str
    variants: Mapping[str, str]
    conventions: str
    time_standard: str
    intraday: str
    sunrise: str
    elements: tuple[str, ...]
    scripts: tuple[str, ...]
    text: str
    layers: tuple[str, ...]
    observer_required: bool
    observer_pinned: str | None
    path: str
    engine: str = "siddhantic"
    modern: Mapping[str, Any] | None = None

    def as_config(self) -> dict[str, Any]:
        """The preset's fields as a plain dict (the hashed configuration, observer apart)."""
        out = self._config()
        if self.modern is not None:
            out["modern"] = json.loads(json.dumps(self.modern, default=str))
        return out

    def _config(self) -> dict[str, Any]:
        return {
            "preset": self.id,
            "method": self.method,
            "variants": dict(self.variants),
            "conventions": self.conventions,
            "time_standard": self.time_standard,
            "intraday": self.intraday,
            "sunrise": self.sunrise,
            "output": {"elements": list(self.elements), "scripts": list(self.scripts)},
            "engine_data": {"text": self.text, "layers": list(self.layers)},
        }


@dataclass(frozen=True, slots=True)
class Resolved:
    """A preset bound to an observer: the canonical configuration and its hash.

    ``overrides`` are the run fields a caller changed from the preset's
    (``--set``), by their ``--set`` key; they enter
    ``config`` under ``overrides`` and so the hash, and a run without
    one hashes as the preset alone.
    """

    preset: Preset
    observer: str
    config: Mapping[str, Any]
    canonical: bytes
    config_hash: str
    overrides: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Composition:
    """The effective composition date: its component id and year, and its first civil day."""

    component: str
    year: YearDatum
    kali_threshold: int
    first_day: JDN


def _need(doc: Mapping[str, Any], fields: tuple[str, ...], where: str) -> None:
    missing = [f for f in fields if f not in doc]
    extra = sorted(set(doc) - set(fields))
    if missing or extra:
        raise PresetError(f"{where}: missing {missing}, unknown {extra} (no hidden defaults)")


def _parse_modern(block: Any, where: str) -> dict[str, Any]:
    """A modern preset's engine block, every field present (no hidden defaults)."""
    if not isinstance(block, dict):
        raise PresetError(f"{where}: modern is a mapping")
    _need(block, MODERN_FIELDS, f"{where}: modern")
    for name, fields in (
        ("delta_t", MODERN_DELTA_T_FIELDS),
        ("ayanamsa", MODERN_AYANAMSA_FIELDS),
        ("sunrise_event", MODERN_EVENT_FIELDS),
        ("observer_frame", MODERN_CITED_FIELDS),
        ("node", MODERN_CITED_FIELDS),
        ("observer_height_m", MODERN_HEIGHT_FIELDS),
    ):
        if not isinstance(block[name], dict):
            raise PresetError(f"{where}: modern.{name} is a mapping")
        _need(block[name], fields, f"{where}: modern.{name}")
    # a deep copy: the nested mappings are not shared with the caller's document
    return copy.deepcopy(dict(block))


def parse_preset(doc: Any, where: str, repo: Path) -> Preset:
    """A preset from its document, checked against the registry under ``repo``."""
    if not isinstance(doc, dict):
        raise PresetError(f"{where}: a preset is a mapping")
    modern_doc = "modern" in doc
    _need(doc, (*FIELDS, "modern") if modern_doc else FIELDS, where)
    pid = doc["preset"]
    if pid not in PRESET_TABLE:
        raise PresetError(f"{where}: {pid!r} is not in the preset table")
    header = doc["header"]
    _need(header, HEADER_FIELDS, f"{where}: header")
    if RANGE_POINTER not in header["range"]:
        raise PresetError(f"{where}: header.range points to {RANGE_POINTER}")
    ctx = context_for(repo)
    registry = load_registry(repo / "jyotirganita" / "methods" / "registry.yaml", ctx.sources)
    method = registry.get(doc["method"])
    if method is None:
        raise PresetError(f"{where}: no method {doc['method']!r} in the registry")
    base = registry[method.base] if method.base else method
    declared: Mapping[str, Any] = method.raw.get("variants", {})
    variants = doc["variants"]
    if set(variants) != set(declared):
        raise PresetError(
            f"{where}: variants {sorted(variants)} are not the method's {sorted(declared)}"
        )
    for name, value in variants.items():
        if value not in declared[name]:
            raise PresetError(f"{where}: variant {name} has no value {value!r}")
    data = doc["engine_data"]
    _need(data, ("text", "layers"), f"{where}: engine_data")
    if data["text"] != base.text or tuple(data["layers"]) != method.layers:
        raise PresetError(f"{where}: engine_data is not the method's text and layers")
    if (method.engine == "modern") != modern_doc:
        raise PresetError(f"{where}: a modern preset, and only one, names its modern block")
    modern: dict[str, Any] | None = None
    if method.engine == "siddhantic":
        if doc["time_standard"] != f"{TEXT_LOCAL}{base.text}":
            raise PresetError(f"{where}: a siddhantic preset names {TEXT_LOCAL}{base.text}")
        if doc["intraday"] not in INTRADAY:
            raise PresetError(f"{where}: intraday {doc['intraday']!r} is not one of {INTRADAY}")
        if doc["sunrise"] != TEXT_SUNRISE:
            raise PresetError(f"{where}: sunrise {doc['sunrise']!r} (only the text's is served)")
    else:
        if str(doc["time_standard"]).startswith(TEXT_LOCAL):
            raise PresetError(f"{where}: a modern preset names a clock standard, not a text's")
        if doc["intraday"] != MODERN_INTRADAY:
            raise PresetError(f"{where}: a modern preset's intraday is {MODERN_INTRADAY}")
        if doc["sunrise"] != MODERN_SUNRISE:
            raise PresetError(f"{where}: a modern preset's sunrise is {MODERN_SUNRISE}")
        modern = _parse_modern(doc["modern"], where)
    out = doc["output"]
    _need(out, OUTPUT_FIELDS, f"{where}: output")
    for name in OUTPUT_FIELDS:  # a string would become its characters
        if not isinstance(out[name], list) or not all(isinstance(x, str) for x in out[name]):
            raise PresetError(f"{where}: output.{name} is a list of names")
    obs = doc["observer"]
    if not isinstance(obs, dict) or set(obs) not in ({"required"}, {"pinned"}):
        raise PresetError(
            f"{where}: observer is {{required: true}} or {{pinned: <region>/<place>}}"
        )
    if "required" in obs and obs["required"] is not True:
        raise PresetError(f"{where}: observer.required is true (the observer is never defaulted)")
    if "pinned" in obs and not (isinstance(obs["pinned"], str) and "/" in obs["pinned"]):
        # a null pin turned the observer optional
        raise PresetError(f"{where}: observer.pinned is <region>/<place>")
    return Preset(
        pid,
        dict(header),
        method.id,
        dict(variants),
        doc["conventions"],
        doc["time_standard"],
        doc["intraday"],
        doc["sunrise"],
        tuple(out["elements"]),
        tuple(out["scripts"]),
        data["text"],
        tuple(data["layers"]),
        "required" in obs,
        obs.get("pinned"),
        where,
        method.engine,
        modern,
    )


def preset_ids(repo: Path) -> list[str]:
    """The preset files under ``methods/presets/``, by stem."""
    return sorted(p.stem for p in repo.joinpath(*PRESETS_DIR).glob("*.yaml"))


def load_preset(repo: Path, preset_id: str) -> Preset:
    """The preset ``preset_id`` (a hard error for a preset with no file)."""
    path = repo.joinpath(*PRESETS_DIR, f"{preset_id}.yaml")
    if not path.is_file():
        raise PresetError(f"no preset {preset_id!r} (has {preset_ids(repo)})")
    rel = path.relative_to(repo).as_posix()
    p = parse_preset(load_exact(path), rel, repo)
    if p.id != preset_id:
        raise PresetError(f"{rel}: names preset {p.id!r}")
    return p


def resolve(
    preset: Preset, observer: str | None, overrides: Mapping[str, str] | None = None
) -> Resolved:
    """Bind ``preset`` to ``observer`` (``<region>/<place>``) and hash the configuration.

    ``overrides`` (the ``--set`` keys and values that change a field of the
    preset) are hashed with it; an empty mapping is no override.
    """
    if observer is None:
        if preset.observer_pinned is None:
            raise PresetError(f"{preset.id}: the caller names the observer")
        observer = preset.observer_pinned
    elif preset.observer_pinned is not None and observer != preset.observer_pinned:
        raise PresetError(
            f"{preset.id}: the {preset.conventions} conventions pin the observer "
            f"{preset.observer_pinned}; {observer} is rejected"
        )
    region, sep, place = observer.partition("/")
    if not sep or not region or not place:
        raise PresetError(f"an observer is <region>/<place>, not {observer!r}")
    config: dict[str, Any] = {**preset.as_config(), "observer": observer}
    if overrides:
        config["overrides"] = dict(sorted(overrides.items()))
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )
    digest = hashlib.sha256(canonical).hexdigest()
    return Resolved(preset, observer, config, canonical, digest, dict(overrides or {}))


def effective_composition(resolved: ResolvedMethod) -> Composition:
    """The latest ``before_composition`` component of a method (its variants have none yet)."""
    s2k = resolved.model.saka_to_kali_years
    comps = [c for c in resolved.components if c.flag.startswith("before_composition:")]
    if not comps:
        raise PresetError(f"{resolved.method.id}: no composition date")
    ce = resolved.ce_to_kali_years
    latest = max(comps, key=lambda c: c.year.kali_threshold(s2k, ce))
    threshold = latest.year.kali_threshold(s2k, ce)
    m = resolved.model
    sun = m.planets["sun"]
    # completed_years counts the Sun's revolutions from the epoch, without additive signs
    if isinstance(m, SuryaModel):
        # counted from the Kali midnight; the day starts a quarter day later (i.67)
        signs = m.mean_sun_signs_at_epoch_sunrise()
        days = m.elements.civil_days[sun.mean]
        mean = MeanSun(m.revolutions[sun.mean], days, signs, resolved.epoch)
    elif isinstance(m, TableModel):
        rate = m.rates[sun.mean]
        mean = MeanSun(rate.guna, rate.hara, 0, resolved.epoch)
    else:
        mean = MeanSun(m.revolutions[sun.mean], m.civil_days, 0, resolved.epoch)
    first = mean.entry_day(1, threshold)
    return Composition(latest.flag.partition(":")[2], latest.year, threshold, first)


def _conventions(
    repo: Path, preset: Preset, records: Records, eras: Mapping[str, EraFile]
) -> ConventionSet:
    if preset.conventions == TEXT_ONLY.id:
        return TEXT_ONLY
    return conventions_of(load_profile(repo, preset.conventions, records.data, eras))


def _cited(records: Records, key: Any, where: str) -> str:
    rec = records.data.get(str(key))
    if rec is None or rec.status == "gap":
        raise PresetError(f"{where}: {key} is not a datum (a modern component cites one)")
    return str(key)


def _fraction(v: Any, where: str) -> Fraction:
    got = _fraction_or_none(v, where)
    if got is None:
        raise PresetError(f"{where}: a number, not null")
    return got


def _fraction_or_none(v: Any, where: str) -> Fraction | None:
    if v is None:
        return None
    try:
        return Fraction(str(v))
    except (ValueError, ZeroDivisionError):  # "1/0"
        raise PresetError(f"{where}: {v!r} is not a number") from None


def modern_config(preset: Preset, conv: ConventionSet, records: Records) -> ModernConfig:
    """A modern preset's engine configuration: its block, its standard, its conventions' day."""
    from jyotirganita.modern.engine import ModernConfig
    from jyotirganita.modern.riseset import Event

    m = preset.modern
    if m is None:
        raise PresetError(f"{preset.id} is not a modern preset")
    where = f"{preset.path}: modern"
    if conv.profile is None:
        raise PresetError(f"{where}: the {conv.id} conventions state no civil day for a clock")
    ev = m["sunrise_event"]
    _cited(records, ev["datum"], f"{where}.sunrise_event")
    _cited(records, m["observer_frame"]["datum"], f"{where}.observer_frame")
    _cited(records, m["node"]["datum"], f"{where}.node")
    ay = m["ayanamsa"]
    coeffs = ay["coefficients"]
    if coeffs is not None and not isinstance(coeffs, list):
        # "123" became three coefficients
        raise PresetError(f"{where}.ayanamsa: coefficients is a list of numbers")
    return ModernConfig(
        kernel=str(m["kernel"]),
        delta_t=str(m["delta_t"]["id"]),
        delta_t_seconds=_fraction_or_none(m["delta_t"]["seconds"], f"{where}.delta_t"),
        precession=str(m["precession"]),
        nutation=str(m["nutation"]),
        ayanamsa=str(ay["id"]),
        ayanamsa_equinox=str(ay["equinox"]),
        ayanamsa_aberration=ay["aberration"],
        ayanamsa_coefficients=None
        if coeffs is None
        else tuple(_fraction(c, f"{where}.ayanamsa") for c in coeffs),
        observer_frame=str(m["observer_frame"]["value"]),
        sunrise_event=Event(
            str(ev["reference"]),
            str(ev["refraction"]),
            str(ev["dip"]),
            _fraction_or_none(ev["dip_height_m"], f"{where}.sunrise_event"),
        ),
        node=str(m["node"]["value"]),
        time_standard=preset.time_standard,
        civil_day_start=conv.profile.civil_day_start,
    )


def modern_run(
    repo: Path,
    preset: Preset,
    res: Resolved,
    conv: ConventionSet,
    records: Records,
) -> ModernRun:
    """The modern run of ``preset`` at ``res``'s observer (its standard, its conventions' day)."""
    from jyotirganita.data import engine_parameters
    from jyotirganita.data.time_standards import load_time_standards
    from jyotirganita.modern.riseset import ModernObserver
    from jyotirganita.modern.run import ModernRun
    from jyotirganita.regions.places import load_modern_place

    assert preset.modern is not None
    ctx = context_for(repo)
    registry = load_registry(repo / "jyotirganita" / "methods" / "registry.yaml", ctx.sources)
    region, _, place = res.observer.partition("/")
    mp = load_modern_place(repo, region, place, records.data)
    height = _fraction_or_none(preset.modern["observer_height_m"]["value"], preset.path)
    if height is None:
        raise PresetError(f"{preset.path}: modern.observer_height_m names a value")
    observer = ModernObserver(mp.id, mp.latitude_deg, mp.longitude_deg, height, mp.flags)
    return ModernRun(
        registry[preset.method],
        modern_config(preset, conv, records),
        observer,
        repo=repo,
        data=records.data,
        time_standards=load_time_standards(repo, ctx),
        parameters=engine_parameters.load(),
    )


def _open(
    repo: Path, preset_id: str, observer: str | None, records: Records | None
) -> tuple[Preset, Resolved, Records, Mapping[str, EraFile], ConventionSet]:
    preset = load_preset(repo, preset_id)
    res = resolve(preset, observer)
    ctx = context_for(repo)
    records = records or load_records(repo, ctx)
    eras = load_eras(repo / "jyotirganita" / "data", ctx, repo)
    return preset, res, records, eras, _conventions(repo, preset, records, eras)


def open_preset(
    repo: Path,
    preset_id: str,
    observer: str | None,
    *,
    records: Records | None = None,
    options: Mapping[str, str] | None = None,
    month_rule: str | None = None,
) -> tuple[Resolved, MethodRun, Calendar]:
    """Load, resolve and build a siddhantic preset: its configuration, its run and its calendar."""
    preset, res, records, eras, conv = _open(repo, preset_id, observer, records)
    if preset.engine != "siddhantic":
        raise PresetError(f"{preset_id} is a {preset.engine} preset (open_modern_preset)")
    region, _, place = res.observer.partition("/")
    obs = load_place(repo, region, place, records.data)
    run = build(load_method(preset.method, repo, records=records), obs, intraday=preset.intraday)
    cal = Calendar(run, conv, eras, options=options, scripts=preset.scripts, month_rule=month_rule)
    return res, run, cal


def open_modern_preset(
    repo: Path,
    preset_id: str,
    observer: str | None,
    *,
    records: Records | None = None,
    options: Mapping[str, str] | None = None,
    month_rule: str | None = None,
) -> tuple[Resolved, ModernRun, Calendar]:
    """Load, resolve and build a modern preset: its configuration, its run and its calendar."""
    preset, res, records, eras, conv = _open(repo, preset_id, observer, records)
    if preset.engine != "modern":
        raise PresetError(f"{preset_id} is a {preset.engine} preset (open_preset)")
    run = modern_run(repo, preset, res, conv, records)
    cal = Calendar(
        run.binding, conv, eras, options=options, scripts=preset.scripts, month_rule=month_rule
    )
    return res, run, cal
