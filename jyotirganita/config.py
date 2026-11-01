"""The configuration of a run: a preset at an observer, with overrides.

:func:`open_config` opens a preset exactly as ``tools/regression.py``
does (the siddhantic or the modern run, the calendar of its convention
set) and returns the :class:`RunConfig` that the record writer, the API
and the search all take, so that they share one configuration object,
its overrides, its ``diagnostic`` flags and its provenance block.

**Overrides** (``--set key=value``) are exactly these
fields:

- ``conventions.month_rule``: a month rule the convention set offers;
- ``conventions.era.<era id>.year_start``: a year-start option the set
  offers for that era;
- ``procedure.<slot>``: a procedure; the one slot an engine overrides is
  ``procedure.sunrise`` under a siddhantic preset, set to
  ``modern_geometric:<modern preset id>``, the declared geometric
  alternative computed by that modern preset at the
  same place on local mean time (``modern/hybrid.py``); every other slot
  is refused, naming the slot served;
- ``intraday``: ``linear_gati`` or ``full_evaluation`` (siddhantic only);
- ``time_standard``: a civil standard of ``data/time_standards/`` under
  a modern preset; under a siddhantic preset only the preset's own
  ``text_local:<text_id>`` (a text's instants reach a
  civil standard only through ``derived_ut``);
- ``output.elements`` and ``output.scripts``: comma-separated lists, the
  occurrence elements a record carries and the scripts of its names (an
  empty value is the empty list);
- under a modern preset only, the four
  switches of the modern engine, each defaulting to the preset's value:
  ``modern.sunrise_event`` (``<reference>/<refraction>/<dip>``, the dip
  ``none`` or ``<kind>:<height>m``, then optionally ``@<height>m``, the
  observer's height), ``modern.ayanamsa`` (``<id>/<equinox>``;
  ``citra_180/<equinox>/aberration`` or ``/no_aberration``;
  ``custom_linear`` and ``custom_polynomial`` with ``/<c0>,<c1>,…`` in
  arcseconds), ``modern.delta_t`` (``iers``, ``smh2016``, ``em2006``,
  ``zero``, ``constant:<seconds>``) and ``modern.node`` (``mean``,
  ``osculating``). A switched run carries ``diagnostic:<key>`` on every
  record; the kernel, precession and nutation stay the preset's.

Any other key is refused (field ``set``), listing the keys taken and
naming ``method``, ``composed``, ``runs_from`` and datum keys as refused
by design. A value equal to the preset's own is no override. Every
override that changes a field enters :class:`~jyotirganita.methods.presets.Resolved`
and so the configuration hash; a run under a procedure or intraday
override carries ``diagnostic:<procedure id>`` on every record and
candidate, and the staged search does no planet pruning.

Every refusal is a :class:`~jyotirganita.errors.Refusal` naming the field
(``preset``, ``observer``, ``set``, ``month_rule``, ``options``,
``procedure``, ``intraday``, ``time_standard``, ``output``), raised
before any day is computed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path
from typing import Any

from jyotirganita.calendar.day import (
    OCCURRENCE_ELEMENTS,
    TEXT_ONLY,
    Calendar,
    ConventionSet,
    conventions_of,
)
from jyotirganita.calendar.months import MonthRuleNotModelled
from jyotirganita.calendar.occurrences import SiddhanticSource
from jyotirganita.core.types import JDN
from jyotirganita.data.datum import Records, context_for, load_records
from jyotirganita.data.eras import EraFile, load_eras
from jyotirganita.data.time_standards import OutOfForce
from jyotirganita.errors import Refusal
from jyotirganita.methods.compose import build, load_method
from jyotirganita.methods.presets import (
    PRESETS_DIR,
    Preset,
    PresetError,
    Resolved,
    load_preset,
    modern_run,
    resolve,
)
from jyotirganita.provenance.hashing import file_sha256
from jyotirganita.regions.base import ProfileError, load_profile
from jyotirganita.regions.places import PlaceError, load_place
from jyotirganita.siddhantic.engine import (
    FULL_EVALUATION,
    LINEAR_GATI,
    EngineRefusal,
    NoSunriseAtPlace,
)

__all__ = [
    "INTRADAY_NAMES",
    "SET_KEYS",
    "RunConfig",
    "check_set_keys",
    "open_config",
]

#: the probe day of a month rule, this many days after runs_from (clear of the stream's edge);
#: structural: no computed value depends on which day it is
PROBE_DAYS = 1000
#: the intraday models a siddhantic run may be overridden to, by their --set names
INTRADAY_NAMES: Mapping[str, str] = {
    "linear_gati": LINEAR_GATI,
    "full_evaluation": FULL_EVALUATION,
}
#: the --set keys (the two patterned keys by their pattern)
SET_KEYS = (
    "conventions.month_rule",
    "conventions.era.<era id>.year_start",
    "procedure.<slot>",
    "procedure.sunrise",
    "intraday",
    "time_standard",
    "output.elements",
    "output.scripts",
    "modern.sunrise_event",
    "modern.ayanamsa",
    "modern.delta_t",
    "modern.node",
)
#: the modern engine's switches, served under a modern preset only
MODERN_SWITCHES = ("modern.sunrise_event", "modern.ayanamsa", "modern.delta_t", "modern.node")
#: what --set refuses by design, datum keys besides
REFUSED_BY_DESIGN = ("method", "composed", "runs_from")
#: the procedure slots an engine overrides, and the value form each takes
SERVED_PROCEDURES: Mapping[str, str] = {"sunrise": "modern_geometric:<modern preset id>"}
GEOMETRIC = "modern_geometric"
#: the procedure id a geometric-sunrise run is flagged with (diagnostic:<procedure id>)
GEOMETRIC_PROCEDURE = "sunrise.modern_geometric"
_ERA = re.compile(r"^conventions\.era\.(?P<era>[a-z][a-z0-9_]*)\.year_start\Z")
_PROCEDURE = re.compile(r"^procedure\.(?P<slot>[a-z][a-z0-9_.]*)\Z")
_PLAIN = frozenset(
    (
        "conventions.month_rule",
        "intraday",
        "time_standard",
        "output.elements",
        "output.scripts",
        *MODERN_SWITCHES,
    )
)
_EVENT = re.compile(r"^([a-z_]+)/([a-z_]+)/([a-z_]+)(?::(\d+(?:\.\d+)?)m)?(?:@(\d+(?:\.\d+)?)m)?\Z")
_COEFFS = re.compile(r"^-?\d+(?:\.\d+)?(?:,-?\d+(?:\.\d+)?)*\Z")


@dataclass(frozen=True, slots=True)
class RunConfig:
    """A preset bound to an observer with its overrides (module docstring).

    ``kind`` is ``siddhantic`` or ``modern``; ``numeric`` is ``exact`` or
    ``float``; ``runs_to`` is ``None`` for a siddhantic
    run (no upper end). ``overrides`` holds the ``--set`` keys whose value
    changed a field of the preset, ``diagnostic`` the flags they raise;
    ``elements`` and ``scripts`` are the output selection in force,
    ``time_standard`` the run's standard, ``sunrise`` the sunrise
    procedure (the preset's ``text`` or ``sunrise_event``, or the
    geometric alternative's id); ``notices`` the lines the CLI prints to
    stderr when the run opens.
    """

    repo: Path
    preset: Preset
    resolved: Resolved
    run: Any
    calendar: Calendar
    conventions: ConventionSet
    records: Records
    eras: Mapping[str, EraFile]
    kind: str
    numeric: str
    runs_from: JDN
    runs_to: JDN | None
    intraday: str
    month_rule: str | None
    options: Mapping[str, str]
    overrides: Mapping[str, str] = field(default_factory=dict)
    diagnostic: tuple[str, ...] = ()
    elements: tuple[str, ...] = OCCURRENCE_ELEMENTS
    scripts: tuple[str, ...] = ()
    time_standard: str = ""
    sunrise: str = ""
    #: what the CLI prints to stderr when the run opens (a run flagged for it)
    notices: tuple[str, ...] = ()
    #: the reading profiles loaded for this configuration, by id (a profile file is data)
    profiles: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def reading_profile(self, profile_id: Any) -> Any:
        """The reading profile ``profile_id`` (``search/profiles.py``), loaded once."""
        from jyotirganita.search.profiles import load_reading_profile

        key = str(profile_id)
        hit = self.profiles.get(key) if isinstance(profile_id, str) else None
        if hit is None:
            hit = load_reading_profile(self.repo, profile_id, self.records, self.eras)
            if isinstance(profile_id, str):  # only an id is a key
                self.profiles[key] = hit
        return hit

    @property
    def engine(self) -> Any:
        return self.run.engine

    @property
    def method_id(self) -> str:
        return str(self.preset.method)

    @property
    def observer(self) -> str:
        return self.resolved.observer

    @property
    def config_hash(self) -> str:
        return self.resolved.config_hash

    def provenance(self) -> dict[str, Any]:
        """The run's provenance block with the resolved configuration."""
        return {
            **self.run.provenance,
            "config_hash": self.resolved.config_hash,
            "preset": self.preset.id,
            "observer": self.resolved.observer,
            "month_rule": self.month_rule,
            "era_options": dict(self.calendar.options),
            "overrides": dict(self.overrides),
            "calendar_files": self.calendar_files(),
        }

    def calendar_files(self) -> dict[str, str]:
        """The SHA-256 of every file the configuration reads beside the method's run.

        The preset and the method registry; the regional profiles, names,
        places and coordinates (every file under ``regions/``); the era
        records; the calendar layer's own tables (``data/calendar/``); the
        time standards; and, under a siddhantic method, the file of its
        date of composition. Kept beside ``data_files``, not in it:
        ``parameters_sha256`` digests ``data_files`` only, and the step
        scans of the search are keyed on it (``search/stages.py``).
        """
        root = self.repo / "jyotirganita"
        paths = {
            root.joinpath(*PRESETS_DIR[1:], f"{self.preset.id}.yaml"),
            root / "methods" / "registry.yaml",
            *root.joinpath("regions").rglob("*.yaml"),
            *(self.repo / str(ef.path) for ef in self.eras.values()),
            *root.joinpath("data", "calendar").glob("*.yaml"),
            *root.joinpath("data", "time_standards").glob("*.yaml"),
        }
        resolved = getattr(self.run, "resolved", None)
        composed = None if resolved is None else resolved.method.composed
        if composed is not None:
            paths.add(self.repo / self.records.data[composed].path)
        files = {p.resolve().relative_to(self.repo.resolve()).as_posix(): p for p in paths}
        return {rel: file_sha256(files[rel]) for rel in sorted(files)}


def _conventions(
    repo: Path, preset: Preset, records: Records, eras: Mapping[str, EraFile]
) -> ConventionSet:
    if preset.conventions == TEXT_ONLY.id:
        return TEXT_ONLY
    return conventions_of(load_profile(repo, preset.conventions, records.data, eras))


def _probe_month_rule(cal: Calendar, runs_from: JDN, where: str) -> None:
    """Refuse a month rule the observer serves on no day, before the scan.

    A rule that needs a sunset where the place models none fails on every
    day; one probe day finds it.
    """
    if cal.months is None:
        return
    try:
        cal.months.month_of(runs_from.plus_days(PROBE_DAYS))
    except OutOfForce:
        # the probe day lies outside the civil standard's periods of force; the
        # standard is checked on each day asked (io/record.py serving)
        return
    except NoSunriseAtPlace as e:  # a latitude the text's sunrise rule does not serve
        raise Refusal("observer", f"{where}: {e}") from None
    except MonthRuleNotModelled as e:
        spec = cal.conventions.month_rule
        offered = [] if spec is None else sorted({spec.rule, *spec.alternatives})
        raise Refusal(
            "month_rule",
            f"{where}: {e}; the convention set offers {offered} (--set conventions.month_rule)",
        ) from None


def _check_year_starts(cal: Calendar) -> None:
    """Refuse, when the configuration opens, a year start the method cannot count.

    A ``sun: mean`` start under a method with no text's mean Sun, or a
    true-Sun start under a convention set with no month rule, was refused
    only on the first day computed.
    """
    for era, option in cal.options.items():
        try:
            cal.year_stream(era, option)
        except ProfileError as e:
            raise Refusal(f"conventions.era.{era}.year_start", str(e)) from None


#: the flag on every record whose true-Sun era years are counted on the splice
SPLICED_ERA_FLAG = "diagnostic:era_years.text_sunrise"


def _spliced_eras(cal: Calendar) -> list[str]:
    """The eras whose year-start option counts from the true Sun (counted on the splice).

    The geometric sunrise exists only on the modern run's days, and a
    true-Sun year start is counted from the era's epoch (``core/eras.py``),
    which lies before them: the count runs on the text's own days there
    (``calendar/day.py``, :class:`SplicedSource`).
    """
    out = []
    for era, option in cal.options.items():
        starts = cal.eras[era].era.year_starts or {}
        ys = starts.get(option)
        if ys is not None and ys.sun.value == "true":
            out.append(era)
    return out


def _switched(key: str, value: str, modern: Mapping[str, Any]) -> dict[str, Any]:
    """The preset's ``modern`` block under one switch (module docstring), or a refusal."""
    from jyotirganita.modern.ayanamsa import AYANAMSAS, EQUINOXES
    from jyotirganita.modern.deltat import MODELS
    from jyotirganita.modern.engine import NODES
    from jyotirganita.modern.riseset import Event

    out = dict(modern)
    if key == "modern.sunrise_event":
        m = _EVENT.match(value)
        if m is None:
            raise Refusal(key, f"{value!r} is <reference>/<refraction>/<dip>[:<h>m][@<h>m]")
        dip_height = None if m[4] is None else Fraction(m[4])
        try:
            Event(m[1], m[2], m[3], dip_height)
        except ValueError as e:
            raise Refusal(key, f"{value!r}: {e}") from None
        out["sunrise_event"] = {
            **modern["sunrise_event"],
            "reference": m[1],
            "refraction": m[2],
            "dip": m[3],
            "dip_height_m": m[4],
        }
        if m[5] is not None:
            out["observer_height_m"] = {
                "value": m[5],
                "basis": f"--set {key}={value}",
            }
        return out
    if key == "modern.ayanamsa":
        parts = value.split("/")
        aid, equinox, rest = parts[0], parts[1] if len(parts) > 1 else None, parts[2:]
        if aid not in AYANAMSAS or equinox not in EQUINOXES:
            raise Refusal(
                key,
                f"{value!r} is <id>/<equinox>[/...], the id one of {AYANAMSAS}, "
                f"the equinox one of {EQUINOXES}",
            )
        aberration: bool | None = None
        coeffs: list[str] | None = None
        if aid == "citra_180":
            if rest not in (["aberration"], ["no_aberration"]):
                raise Refusal(key, f"{value!r}: citra_180 names aberration or no_aberration")
            aberration = rest == ["aberration"]
        elif aid in ("custom_linear", "custom_polynomial"):
            if len(rest) != 1 or not _COEFFS.match(rest[0]):
                raise Refusal(key, f"{value!r}: {aid} names its coefficients, c0,c1,… arcseconds")
            coeffs = rest[0].split(",")
            if aid == "custom_linear" and len(coeffs) != 2:
                raise Refusal(key, f"{value!r}: custom_linear takes two coefficients")
        elif rest:
            raise Refusal(key, f"{value!r}: {aid} takes only its equinox")
        out["ayanamsa"] = {
            "id": aid,
            "equinox": equinox,
            "aberration": aberration,
            "coefficients": coeffs,
        }
        return out
    if key == "modern.delta_t":
        model, sep, seconds = value.partition(":")
        if model not in MODELS or (model == "constant") != bool(sep):
            raise Refusal(key, f"{value!r}: one of {MODELS}, constant as constant:<seconds>")
        if sep and not _COEFFS.match(seconds):
            raise Refusal(key, f"{value!r}: constant:<seconds>, a decimal number")
        out["delta_t"] = {"id": model, "seconds": seconds if sep else None}
        return out
    if value not in NODES:
        raise Refusal(key, f"{value!r}: the node is one of {NODES}")
    out["node"] = {**modern["node"], "value": value}
    return out


def _switch_value(key: str, modern: Mapping[str, Any]) -> str:
    """The preset's own value of a switch, in the switch's form (no override when equal)."""
    if key == "modern.sunrise_event":
        ev = modern["sunrise_event"]
        dip = ev["dip"] if ev["dip_height_m"] is None else f"{ev['dip']}:{ev['dip_height_m']}m"
        return f"{ev['reference']}/{ev['refraction']}/{dip}"
    if key == "modern.ayanamsa":
        ay = modern["ayanamsa"]
        out = f"{ay['id']}/{ay['equinox']}"
        if ay["aberration"] is not None:
            out += "/aberration" if ay["aberration"] else "/no_aberration"
        if ay["coefficients"] is not None:
            out += "/" + ",".join(str(c) for c in ay["coefficients"])
        return out
    if key == "modern.delta_t":
        dt = modern["delta_t"]
        return str(dt["id"]) if dt["seconds"] is None else f"{dt['id']}:{dt['seconds']}"
    return str(modern["node"]["value"])


def check_set_keys(overrides: Mapping[str, str], records: Records | None = None) -> None:
    """Refuse a ``--set`` key outside the fields of the module docstring."""
    taken = ", ".join(SET_KEYS)
    for key in sorted(overrides):
        if key in _PLAIN or _ERA.match(key) or _PROCEDURE.match(key):
            continue
        head = key.partition(".")[0]
        if key in REFUSED_BY_DESIGN or head in REFUSED_BY_DESIGN:
            why = f"{key!r} is refused by design: a run never sets its {head}"
        elif records is not None and key in records.data:
            why = f"{key!r} is a datum key, refused by design: data change only by a read"
        else:
            why = f"{key!r} is not a --set key"
        raise Refusal(
            "set",
            f"{why}; --set takes {taken}; method, composed, runs_from and datum keys are "
            "refused by design",
        )


def _list(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split(",") if v.strip())


def _elements(value: str, preset: Preset) -> tuple[str, ...]:
    asked = _list(value)
    unknown = sorted(set(asked) - set(OCCURRENCE_ELEMENTS))
    if unknown or len(set(asked)) != len(asked):
        raise Refusal(
            "output",
            f"output.elements {value!r}: a list of {', '.join(OCCURRENCE_ELEMENTS)}, each once",
        )
    return tuple(e for e in OCCURRENCE_ELEMENTS if e in asked)


def _scripts(value: str, conv: ConventionSet) -> tuple[str, ...]:
    asked = _list(value)
    if not asked:
        return ()
    if conv.profile is None:
        raise Refusal("output", f"the {conv.id} conventions hold no name table (output.scripts)")
    held = sorted({s for n in conv.profile.names.values() for s in n.forms})
    unknown = sorted(set(asked) - set(held))
    if unknown or len(set(asked)) != len(asked):
        raise Refusal("output", f"output.scripts {value!r}: the name table holds {held}")
    return asked


def _geometric(
    repo: Path, value: str, observer: str, records: Records, eras: Mapping[str, EraFile]
) -> tuple[Any, str, tuple[JDN, JDN]]:
    """The geometric sunrise provider ``modern_geometric:<modern preset id>`` names.

    With it, the days the modern run serves (its first and last), which
    bound the hybrid run: its sunrise exists only where the modern one does.
    """
    from jyotirganita.modern.hybrid import GeometricSunrise
    from jyotirganita.modern.kernels import KernelError

    kind, sep, mid = value.partition(":")
    if kind != GEOMETRIC or not sep or not mid:
        raise Refusal(
            "procedure",
            f"procedure.sunrise {value!r}: the preset's own (text) or "
            f"{SERVED_PROCEDURES['sunrise']}",
        )
    try:
        mpreset = load_preset(repo, mid)
    except (PresetError, FileNotFoundError) as e:
        raise Refusal("procedure", f"procedure.sunrise: {e}") from None
    if mpreset.engine != "modern":
        raise Refusal("procedure", f"procedure.sunrise: {mid} is not a modern preset")
    try:
        mres = resolve(mpreset, observer)
        mconv = _conventions(repo, mpreset, records, eras)
        mrun = modern_run(repo, mpreset, mres, mconv, records)
        provider = GeometricSunrise(mrun.engine)
    except (PresetError, PlaceError, ProfileError, ValueError, KernelError) as e:
        raise Refusal("procedure", f"procedure.sunrise={value} at {observer}: {e}") from None
    return provider, provider.id, (mrun.runs_from, mrun.runs_to)


def open_config(
    repo: Path,
    preset_id: str,
    observer: str | None,
    /,
    *,
    records: Records | None = None,
    **overrides: str,
) -> RunConfig:
    """Open ``preset_id`` at ``observer`` under ``overrides`` (module docstring).

    ``overrides`` are ``--set`` keys and values, passed by unpacking a
    mapping (``open_config(repo, p, o, **{"conventions.month_rule": r})``);
    the first three are positional only, so that a key named like them is
    refused as a ``--set`` key. A key
    ``records`` meets the keyword itself: the CLI and :func:`open_search`
    check their pairs with :func:`check_set_keys` first.
    """
    ctx = context_for(repo)
    records = records or load_records(repo, ctx)
    check_set_keys(overrides, records)
    slots = sorted(
        m["slot"] for k in overrides if (m := _PROCEDURE.match(k)) and m["slot"] != "sunrise"
    )
    if slots:
        raise Refusal(
            "procedure",
            f"{slots}: no engine offers a procedure override for these slots; the slots "
            f"overridden are {sorted(SERVED_PROCEDURES)} "
            f"(procedure.sunrise={SERVED_PROCEDURES['sunrise']})",
        )
    try:
        preset = load_preset(repo, preset_id)
    except (PresetError, FileNotFoundError) as e:
        raise Refusal("preset", str(e)) from None
    eras = load_eras(repo / "jyotirganita" / "data", ctx, repo)
    try:
        conv = _conventions(repo, preset, records, eras)
    except ProfileError as e:
        raise Refusal("preset", str(e)) from None

    changed: dict[str, str] = {}
    diagnostic: list[str] = []
    month_rule = overrides.get("conventions.month_rule")
    if month_rule is not None:
        spec = conv.month_rule
        if spec is None:
            raise Refusal("month_rule", f"the {conv.id} conventions have no month rule to select")
        if month_rule != spec.rule:
            changed["conventions.month_rule"] = month_rule
    options: dict[str, str] = {}
    for key, value in overrides.items():
        m = _ERA.match(key)
        if m is None:
            continue
        options[m["era"]] = value
        spec_era = next((e for e in conv.eras if e.era == m["era"]), None)
        if spec_era is None or value != spec_era.default_option:
            changed[key] = value
    elements = preset.elements
    if "output.elements" in overrides:
        elements = _elements(overrides["output.elements"], preset)
        if elements != preset.elements:
            changed["output.elements"] = ",".join(elements)
    scripts = preset.scripts
    if "output.scripts" in overrides:
        scripts = _scripts(overrides["output.scripts"], conv)
        if scripts != preset.scripts:
            changed["output.scripts"] = ",".join(scripts)

    model = preset.intraday
    standard = preset.time_standard
    sunrise = preset.sunrise
    provider = None
    hybrid_range: tuple[JDN, JDN] | None = None
    modern_block: Mapping[str, Any] | None = preset.modern
    if preset.engine == "modern":
        if "intraday" in overrides:
            raise Refusal(
                "intraday",
                f"{preset_id}: a modern run evaluates positions at each instant "
                f"({preset.intraday}); there is no intraday model to override",
            )
        if "procedure.sunrise" in overrides and overrides["procedure.sunrise"] != preset.sunrise:
            raise Refusal(
                "procedure",
                f"{preset_id}: a modern run's sunrise is its preset's sunrise_event; "
                "procedure.sunrise is overridden under a siddhantic preset only",
            )
        if "time_standard" in overrides:
            from jyotirganita.data.time_standards import load_time_standards

            held = load_time_standards(repo, ctx)
            standard = overrides["time_standard"]
            if standard not in held:
                raise Refusal(
                    "time_standard",
                    f"{standard!r}: the civil standards of data/time_standards/ are {sorted(held)}",
                )
            if standard != preset.time_standard:
                changed["time_standard"] = standard
        assert preset.modern is not None
        switched: dict[str, Any] = dict(preset.modern)
        for key in MODERN_SWITCHES:
            if key in overrides and overrides[key] != _switch_value(key, preset.modern):
                switched = _switched(key, overrides[key], switched)
                changed[key] = overrides[key]
                diagnostic.append(f"diagnostic:{key}")
        modern_block = switched
    else:
        asked_modern = [k for k in MODERN_SWITCHES if k in overrides]
        if asked_modern:
            raise Refusal(
                asked_modern[0],
                f"{preset_id}: the modern engine's switches are served under a modern preset "
                "only (a geometric sunrise takes its modern preset's settings)",
            )
        if "time_standard" in overrides and overrides["time_standard"] != preset.time_standard:
            raise Refusal(
                "time_standard",
                f"{overrides['time_standard']!r}: a siddhantic preset's instants are on its "
                f"text's own standard ({preset.time_standard}); a civil standard is reached "
                "through derived_ut only",
            )
        if "intraday" in overrides:
            name = overrides["intraday"]
            if name not in INTRADAY_NAMES:
                raise Refusal(
                    "intraday", f"{name!r}: a siddhantic run offers {sorted(INTRADAY_NAMES)}"
                )
            model = INTRADAY_NAMES[name]
            if model != preset.intraday:
                changed["intraday"] = name
                diagnostic.append(f"diagnostic:{model}")
        asked = overrides.get("procedure.sunrise")
        if asked is not None and asked != preset.sunrise:
            if not (observer or preset.observer_pinned):
                # an unpinned preset with no observer is the observer's refusal, not the
                # procedure's
                try:
                    resolve(preset, observer, changed)
                except PresetError as e:
                    raise Refusal("observer", str(e)) from None
            provider, sunrise, hybrid_range = _geometric(
                repo, asked, observer or preset.observer_pinned or "", records, eras
            )
            changed["procedure.sunrise"] = asked
            diagnostic.append(f"diagnostic:{GEOMETRIC_PROCEDURE}")

    try:
        resolved = resolve(preset, observer, changed)
    except PresetError as e:
        raise Refusal("observer", str(e)) from None
    region, _, place = resolved.observer.partition("/")
    from jyotirganita.modern.kernels import KernelError

    try:
        if preset.engine == "modern":
            mpreset = replace(preset, time_standard=standard, modern=modern_block)
            mrun = modern_run(repo, mpreset, resolved, conv, records)
            run: Any = mrun
            cal = Calendar(
                mrun.binding,
                conv,
                eras,
                options=options,
                scripts=scripts,
                month_rule=month_rule,
            )
            kind, numeric, runs_to = "modern", "float", mrun.runs_to
        else:
            obs = load_place(repo, region, place, records.data)
            srun = build(
                load_method(preset.method, repo, records=records),
                obs,
                intraday=model,
                sunrise_provider=provider,
            )
            run = srun
            era_source, era_range = None, None
            if hybrid_range is not None:  # the text's own days, for the year count
                own = build(load_method(preset.method, repo, records=records), obs, intraday=model)
                era_source, era_range = SiddhanticSource(own), hybrid_range
            cal = Calendar(
                srun,
                conv,
                eras,
                options=options,
                scripts=scripts,
                month_rule=month_rule,
                era_source=era_source,
                era_range=era_range,
            )
            kind, numeric, runs_to = "siddhantic", "exact", None
    except PlaceError as e:
        raise Refusal("observer", str(e)) from None
    except PresetError as e:
        raise Refusal("preset", str(e)) from None
    except KernelError as e:
        raise Refusal("kernel", str(e)) from None
    except EngineRefusal as e:  # a place whose route does not serve the method's text
        raise Refusal("observer" if "observer" in str(e) else "preset", str(e)) from None
    except ProfileError as e:
        text = str(e)
        where = "month_rule" if "month rule" in text else "options"
        raise Refusal(where, text) from None
    _check_year_starts(cal)
    runs_from: JDN = run.runs_from
    notices: list[str] = []
    if hybrid_range is not None and (spliced := _spliced_eras(cal)):
        diagnostic.append(SPLICED_ERA_FLAG)
        notices.append(
            f"procedure.sunrise={sunrise}: the years of {', '.join(spliced)} count from the "
            "true Sun from the era's epoch, before the days the geometric sunrise serves; "
            "they are counted on the text's own sunrise before those days and on the "
            f"geometric one within them (records flagged {SPLICED_ERA_FLAG})"
        )
    if hybrid_range is not None:  # the days both engines serve
        if runs_from.days_since(hybrid_range[0]) < 0:
            runs_from = hybrid_range[0]
        runs_to = hybrid_range[1]
    _probe_month_rule(cal, runs_from, f"{preset_id} at this observer")
    return RunConfig(
        repo,
        preset,
        resolved,
        run,
        cal,
        conv,
        records,
        eras,
        kind,
        numeric,
        runs_from,
        runs_to,
        model,
        month_rule,
        dict(cal.options),
        changed,
        tuple(sorted(diagnostic)),
        elements,
        scripts,
        standard,
        sunrise,
        tuple(notices),
    )
