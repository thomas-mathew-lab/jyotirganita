"""A method composed from the registry, its data and an observer.

:func:`load_method` resolves a registry entry: its text's data, the datum
stating each procedure (a layered method inherits its base's and adds the
layer slots), its correction layers from the base text's
``corrections.yaml``, its cited dates and its time base. :func:`build`
binds the result to one observer and returns a :class:`MethodRun`, whose
:meth:`MethodRun.day` is the method's computation for one civil day with
the record flags and a provenance block.

- **runs_from** is the first civil day of the text's own
  count: the epoch of the era record the time-base procedure names (the
  Kali epoch for ``ahargana.civil_days_since_kali_epoch``), unless the
  text's ``procedures.count_before_epoch`` datum says the count extends
  (no shipped text has one; one that extends is refused until the engine
  implements it). A day before it is refused with ``runs_from`` named.
- **Flags, never refusals**: a day whose completed Kali years (the
  base text's mean Sun's whole revolutions at its sunrise, the reckoning
  of ``layer.count_by_mean_mesha``) precede a cited year carries
  ``before_composition:<method id>`` (the method's ``composed``),
  ``before_composition:<layer id>`` (a layer's ``defined``) and
  ``before_epoch:<layer id>`` (a layer's ``epoch``); a year datum's
  threshold is :meth:`~jyotirganita.siddhantic.corrections.YearDatum.kali_threshold`.
  ``provisional_method`` while the method is provisional, and the
  ``provisional:<key>`` flags of every datum the computation read.
- **A recension differing in named data** (``replaces``): the base's data with each replaced datum
  read in place
  of the base's, checked here against the data (a datum of the base's
  text, not a gap, of the same unit and form, and read by the model);
  the procedures are the base's.
- **The zero-layer identity**: ``build(..., zero_layers=True)``
  runs the layered method with every rate zero; its positions equal the
  base method's exactly.
- **A sunrise gap**: when the sunrise slot's datum is a
  gap the run must name a geometric sunrise provider, whose sunrise is
  quantised to ``siddhantic.hybrid_sunrise_quantum``; every record then
  carries ``hybrid_sunrise:modern_geometric`` and provenance names the
  provider and the quantum.
- **The day's leaves**: the sunrise and the sunset
  in nāḍikās after local mean midnight with the standard
  ``text_local:<text>``, ``day_length_nadika``, and each element's
  proportional-parts ending (``ends_nadika_after_sunrise``, possibly 60 or
  more). ``seam:<element>`` flags a day whose chord ends in
  an element other than the next sunrise's, and the next day too.
- **Diagnostics**: ``build(..., intraday=
  "diagnostic.full_evaluation")`` flags every record
  ``diagnostic:diagnostic.full_evaluation``; :meth:`MethodRun.ending_root`
  is the exact-root ending by bisection to ``siddhantic.root_resolution``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from jyotirganita import __version__
from jyotirganita.calendar import elements
from jyotirganita.core.calendar import Weekday, julian_from_jdn
from jyotirganita.core.types import JDN, Ahargana, AngleUnit, ExactArc, Nadika
from jyotirganita.data import engine_parameters
from jyotirganita.data.datum import Record, Records, context_for, load_records
from jyotirganita.data.eras import load_eras
from jyotirganita.methods.registry import Method, load_registry
from jyotirganita.provenance.hashing import file_sha256, files_digest
from jyotirganita.siddhantic.ahargana import weekday_of_ahargana
from jyotirganita.siddhantic.corrections import Layer, YearDatum
from jyotirganita.siddhantic.endings import proportional_parts, root_bisection, seam
from jyotirganita.siddhantic.engine import (
    LAYER_SLOTS,
    LINEAR_GATI,
    BeforeRunsFrom,
    EngineRefusal,
    Observer,
    SiddhanticEngine,
    SunriseProvider,
    TextModel,
)
from jyotirganita.siddhantic.procedures import SLOTS, resolve
from jyotirganita.siddhantic.surya import SUPPORTED as SURYA_SUPPORTED
from jyotirganita.siddhantic.surya import SuryaEngine, SuryaModel
from jyotirganita.siddhantic.tabular import SUPPORTED as TABLE_SUPPORTED
from jyotirganita.siddhantic.tabular import TableEngine, TableModel
from jyotirganita.siddhantic.text import TextData

__all__ = [
    "REPO",
    "BeforeRunsFrom",
    "Component",
    "DayResult",
    "MethodRun",
    "ResolvedMethod",
    "build",
    "load_method",
]

REPO = Path(__file__).resolve().parents[2]
KARNA_RESOLUTION = "siddhantic.karna_root_resolution"
DAY_RADIUS_RESOLUTION = "siddhantic.day_radius_root_resolution"
ROOT_RESOLUTION = "siddhantic.root_resolution"
HYBRID_QUANTUM = "siddhantic.hybrid_sunrise_quantum"
RATE_UNIT = "arcminutes_per_year"

#: the elements whose endings a record states
ENDING_ELEMENTS = ("tithi", "nakshatra", "yoga", "karana")
#: the era record each time-base procedure counts from
TIME_BASE_ERA: Mapping[str, str] = {
    "ahargana.civil_days_since_kali_epoch": "kali",
    "ahargana.kali_dinagana": "kali",
    # the Sūrya-siddhānta counts from the end of creation (i.48–51); the count is placed
    # on the Kali record by the days to the Kali epoch (siddhantic/surya.py)
    "ahargana.civil_days_since_creation": "kali",
}
#: the weekday each weekday procedure counts the remainder from (laghubhaskariya_1963 I.8)
WEEKDAY_FIRST: Mapping[str, Weekday] = {
    "weekday.remainder_from_friday": Weekday.FRIDAY,
    "weekday.remainder_from_sunday": Weekday.SUNDAY,  # Sūrya-siddhānta i.51
}


@dataclass(frozen=True, slots=True)
class Component:
    """A cited year that drives a flag: ``flag`` is raised on a day before ``year``."""

    flag: str
    year: YearDatum


@dataclass(frozen=True, slots=True)
class ResolvedMethod:
    """A registry entry resolved against the data (no observer yet)."""

    method: Method
    repo: Path
    records: Records
    data: TextData
    procedures: Mapping[str, Record]  # slot -> the datum stating the text's rule
    model: TextModel | TableModel | SuryaModel
    layers: tuple[Layer, ...]
    components: tuple[Component, ...]
    era: str
    era_path: str  # the era record's file, relative to the repository
    epoch: JDN
    parameters: Mapping[str, Fraction]
    ce_to_kali_years: int  # Kali N elapsed begins in CE N − this + 1

    @property
    def runs_from(self) -> JDN:
        """The first civil day of the text's count."""
        return self.epoch

    @property
    def text_model(self) -> TextModel:
        """The yuga-rate, epicycle model (a hard error for a table-driven text)."""
        if not isinstance(self.model, TextModel):
            raise EngineRefusal(f"{self.method.id}: a table-driven text has no epicycle model")
        return self.model


@dataclass(frozen=True, slots=True)
class DayResult:
    """One civil day as the method computes it at its sunrise, with flags and provenance."""

    method_id: str
    method_status: str
    jdn: JDN
    ahargana: Ahargana
    weekday: Weekday
    completed_kali_years: int
    layer_counts: Mapping[str, int]
    mean: Mapping[str, Fraction]
    true: Mapping[str, Fraction]
    node: Fraction
    flags: tuple[str, ...]
    provenance: Mapping[str, Any]
    sunrise: Nadika  # after local mean midnight, under ``standard``
    sunset: Nadika | None  # the provider's under the hybrid alternative
    day_length_nadika: Nadika
    standard: str
    endings: Mapping[str, Nadika]  # the proportional-parts ending of each element


def _year(records: Records, key: str) -> YearDatum:
    rec = records.data.get(key)
    if rec is None or rec.kind == "gap":
        raise EngineRefusal(f"{key}: a cited year datum is needed, and it is absent or a gap")
    value = rec.value
    if isinstance(value, bool) or not isinstance(value, int):
        raise EngineRefusal(f"{key}: a year datum is an integer year ({value!r})")
    unit = str(rec.raw.get("unit"))
    convention = rec.raw.get("convention")
    if convention is None:
        raise EngineRefusal(f"{key}: a year datum states its convention")
    return YearDatum.of(key, value, unit, str(convention))


def _slot_records(method: Method, records: Records, *, layer: bool) -> dict[str, Record]:
    out: dict[str, Record] = {}
    for slot, key in method.raw["procedures"].items():
        if slot not in SLOTS:
            raise EngineRefusal(f"{method.id}: procedures names an unknown slot {slot!r}")
        if layer != (slot in LAYER_SLOTS):
            raise EngineRefusal(
                f"{method.id}: slot {slot!r} belongs on "
                + ("the base method" if layer else "a layered method")
                + " (a layered method adds its layer slots only)"
            )
        rec = records.data.get(key)
        if rec is None:
            raise EngineRefusal(f"{method.id}: {slot}: {key} is not a datum")
        if rec.kind != "gap":
            name = rec.raw.get("procedure")
            if not isinstance(name, str):
                raise EngineRefusal(f"{key}: the datum names no procedure")
            resolve(name, slot)
        out[slot] = rec
    return out


def _replacements(method: Method, records: Records, text_dir: str) -> dict[str, str]:
    """``method``'s ``replaces``, each pair checked against the data."""
    for old, new in method.replaces.items():
        a, b = records.data.get(old), records.data.get(new)
        for key, rec in ((old, a), (new, b)):
            if rec is None:
                raise EngineRefusal(f"{method.id}: replaces names {key}, which is not a datum")
            if rec.kind == "gap":
                raise EngineRefusal(f"{method.id}: replaces names {key}, which is a gap")
            if not rec.path.startswith(text_dir):
                raise EngineRefusal(
                    f"{method.id}: replaces names {key}, which is not in {text_dir}"
                )
        assert a is not None and b is not None
        for field, x, y in (
            ("unit", a.raw.get("unit"), b.raw.get("unit")),
            ("form", _value_form(a), _value_form(b)),
        ):
            if x != y:
                raise EngineRefusal(
                    f"{method.id}: replaces {old} by {new}: {field} {x!r} is not {y!r}"
                )
    return dict(method.replaces)


def _value_form(rec: Record) -> object:
    """The form of the value the engine reads: a numeral-word's is its ``value_form``."""
    return rec.raw.get("value_form") if rec.form == "numeral_word" else rec.form


def _layer(data: TextData, layer_id: str, records: Records) -> Layer:
    rates: dict[str, Fraction] = {}
    prefix = data.key(f"{layer_id}.rates.")
    for key, rec in records.data.items():
        if not key.startswith(prefix):
            continue
        element = key.removeprefix(prefix)
        if "." in element:
            continue  # a second witness of a rate
        if rec.kind == "gap":
            # skipping it would leave the element uncorrected silently; no shipped layer
            # has one
            raise EngineRefusal(f"{key}: a layer rate is a gap")
        data.mark_used(rec)
        if rec.form == "text":
            continue  # a stated null rate (the Sun's, grahacaranibandhana_1954 p. x)
        if rec.raw.get("unit") != RATE_UNIT:
            raise EngineRefusal(f"{key}: a layer rate is in {RATE_UNIT}")
        rates[element] = data.fraction(key.removeprefix(data.prefix))
    if not rates:
        raise EngineRefusal(f"layer {layer_id}: no rates under {prefix}")
    epoch = _year(records, data.key(f"{layer_id}.epoch"))
    defined = _year(records, data.key(f"{layer_id}.defined"))
    for k in (epoch.key, defined.key):
        data.mark_used(records.data[k])
    return Layer(layer_id, epoch, defined, rates)


def load_method(
    method_id: str, repo: Path = REPO, *, records: Records | None = None
) -> ResolvedMethod:
    """Resolve the registry entry ``method_id`` against the data under ``repo``."""
    ctx = context_for(repo)
    records = records or load_records(repo, ctx)
    registry = load_registry(repo / "jyotirganita" / "methods" / "registry.yaml", ctx.sources)
    method = registry.get(method_id)
    if method is None:
        raise EngineRefusal(f"no method {method_id!r} in the registry (has {sorted(registry)})")
    if method.engine != "siddhantic" or method.text is None:
        raise EngineRefusal(f"{method_id}: engine {method.engine} is not composed here")
    base = registry[method.base] if method.base else method
    text_dir = f"jyotirganita/data/texts/{method.text}/"
    replaces = _replacements(method, records, text_dir)
    data = TextData(method.text, records.data, replaces)
    procedures = _slot_records(base, records, layer=False)
    if method.base:
        procedures.update(_slot_records(method, records, layer=True))
    if method.layers:
        for slot, expected in LAYER_SLOTS.items():
            got = procedures.get(slot)
            if got is None or got.raw.get("procedure") != expected:
                raise EngineRefusal(f"{method_id}: slot {slot} must name {expected}")
            data.mark_used(got)
    params_path = repo / "jyotirganita" / "data" / "engine_parameters.yaml"
    params = {k: p.value for k, p in engine_parameters.load(params_path).items()}
    sunrise = procedures.get("sunrise")
    sunrise_gap = sunrise is not None and sunrise.kind == "gap"
    stated = {s: r for s, r in procedures.items() if r.kind != "gap"}
    mean_rule = (
        stated["mean_longitude"].raw.get("procedure") if "mean_longitude" in stated else None
    )
    model: TextModel | TableModel | SuryaModel
    if mean_rule == TABLE_SUPPORTED["mean_longitude"]:
        # a table-driven text (drgganita_1963): guṇakāra/hāra rates and jyā tables
        if method.layers:
            raise EngineRefusal(f"{method_id}: a table-driven text runs no correction layer")
        model = TableModel.build(data, stated, params[DAY_RADIUS_RESOLUTION])
    elif mean_rule == SURYA_SUPPORTED["mean_longitude"]:
        # rates from creation, the varying epicycle, the four processes
        if method.layers:
            raise EngineRefusal(f"{method_id}: the Sūrya-siddhānta runs no correction layer")
        model = SuryaModel.build(data, stated, params[KARNA_RESOLUTION])
    else:
        model = TextModel.build(
            data,
            stated,
            params[KARNA_RESOLUTION],
            params[DAY_RADIUS_RESOLUTION],
            sunrise_gap=sunrise_gap,
        )
    unread = [old for old, new in replaces.items() if new not in data.used]
    if unread:
        raise EngineRefusal(
            f"{method_id}: replaces names {', '.join(unread)}, which the model does not read"
        )
    layers = tuple(_layer(data, lid, records) for lid in method.layers)
    composed = method.composed
    assert composed is not None  # load_registry refuses a siddhantic method without it
    components = [Component(f"before_composition:{method.id}", _year(records, composed))]
    for layer in layers:
        components.append(Component(f"before_composition:{layer.id}", layer.defined))
        components.append(Component(f"before_epoch:{layer.id}", layer.epoch))
    time_base = str(procedures["time_base"].raw["procedure"])
    era = TIME_BASE_ERA.get(time_base)
    if era is None:
        raise EngineRefusal(f"{method_id}: time base {time_base} names no era record")
    eras = load_eras(repo / "jyotirganita" / "data", ctx, repo)
    era_file = eras.get(era)
    if era_file is None:  # release review AS11
        raise EngineRefusal(f"{method_id}: the era record {era} is not loaded")
    epoch = era_file.era.epoch
    if epoch is None:
        raise EngineRefusal(f"{method_id}: the era record {era} has no epoch day")
    if data.has("procedures.count_before_epoch"):
        extends = data.record("procedures.count_before_epoch").raw.get("extends")
        if extends is True:
            raise EngineRefusal(
                f"{data.key('procedures.count_before_epoch')}: a count that extends before "
                "its epoch is not implemented by this engine"
            )
    return ResolvedMethod(
        method,
        repo,
        records,
        data,
        procedures,
        model,
        layers,
        tuple(components),
        era,
        era_file.path,
        epoch,
        params,
        # the years from the CE year 1 to the Kali epoch's year on the era record's own
        # calendar (Julian, astronomical numbering): Kali N elapsed begins in CE N − 3101
        1 - julian_from_jdn(epoch).y,
    )


class MethodRun:
    """A resolved method bound to one observer: the day's computation with flags."""

    def __init__(
        self,
        resolved: ResolvedMethod,
        observer: Observer,
        *,
        zero_layers: bool = False,
        sunrise_provider: SunriseProvider | None = None,
        intraday: str = LINEAR_GATI,
    ) -> None:
        self.resolved = resolved
        layers = tuple(x.zeroed() for x in resolved.layers) if zero_layers else resolved.layers
        quantum = resolved.parameters[HYBRID_QUANTUM] if sunrise_provider is not None else None
        model = resolved.model
        self.engine: SiddhanticEngine | TableEngine | SuryaEngine
        if isinstance(model, SuryaModel):
            self.engine = SuryaEngine(
                model,
                observer,
                resolved.epoch,
                sunrise_provider=sunrise_provider,
                hybrid_quantum=quantum,
                intraday=intraday,
            )
        elif isinstance(model, TableModel):
            self.engine = TableEngine(
                model,
                observer,
                resolved.epoch,
                sunrise_provider=sunrise_provider,
                hybrid_quantum=quantum,
                intraday=intraday,
            )
        else:
            self.engine = SiddhanticEngine(
                model,
                layers,
                observer,
                resolved.epoch,
                sunrise_provider=sunrise_provider,
                hybrid_quantum=quantum,
                intraday=intraday,
            )
        self.zero_layers = zero_layers
        weekday_rule = str(resolved.procedures["weekday"].raw["procedure"])
        first = WEEKDAY_FIRST.get(weekday_rule)
        if first is None:  # release review AS11
            raise EngineRefusal(f"{resolved.method.id}: weekday rule {weekday_rule} is not mapped")
        if isinstance(model, SuryaModel):
            # the count from creation (i.51) at the Kali epoch: the weekday of the record's
            # day count is the remainder of the days to the epoch, counted from the first
            first = weekday_of_ahargana(model.days_to_epoch, first)
        self._first = first
        method = resolved.method
        status = {"provisional_method"} if method.status == "provisional" else set()
        self._flags = frozenset(self.engine.flags) | status
        self.provenance = self._provenance(sunrise_provider, quantum)

    @property
    def runs_from(self) -> JDN:
        """The first civil day of the text's count."""
        return self.engine.runs_from

    def _provenance(
        self, provider: SunriseProvider | None, quantum: Fraction | None
    ) -> dict[str, Any]:
        r = self.resolved
        route_data = self.engine.observer.route_data_for(r.model.text)
        used = sorted(
            {rec.path for rec in r.data.used.values()}
            | {"jyotirganita/data/engine_parameters.yaml", r.era_path}
        )
        files = {rel: file_sha256(r.repo / rel) for rel in used}
        # the observer's route data belong to the place, as its coordinates do: hashed
        # beside it, outside data_files, so that the step scan at the text's meridian
        # point serves the place (search/stages.py compares parameters_sha256)
        route_files = {
            rel: file_sha256(r.repo / rel)
            for rel in sorted({r.records.data[k].path for k in route_data})
        }
        out: dict[str, Any] = {
            "engine": "siddhantic",
            "version": __version__,
            "method_id": r.method.id,
            "method_status": r.method.status,
            "text": r.model.text,
            "layers": [x.id for x in r.layers],
            "zero_layers": self.zero_layers,
            "observer": self.engine.observer.id,
            "runs_from": r.runs_from.value,
            "data_files": files,
            "parameters_sha256": files_digest(files.items()),
            "engine_parameters": {
                KARNA_RESOLUTION: str(r.parameters[KARNA_RESOLUTION]),
                DAY_RADIUS_RESOLUTION: str(r.parameters[DAY_RADIUS_RESOLUTION]),
            },
            "observer_route": self.engine.observer.route,
            "intraday": self.engine.intraday,
            "sunrise": "text",
        }
        coords = self.engine.observer.coordinates
        if coords is not None:  # the user's coordinates, input not data
            out["observer_coordinates"] = {
                "latitude_deg": str(coords[0]),
                "longitude_deg": str(coords[1]),
                "source": "user",
            }
        if route_data:  # route (b) through another text's meridian
            out["observer_route_data"] = list(route_data)
            out["observer_route_files"] = route_files
        if r.method.replaces:  # the data read in place of the base's
            out["replaces"] = dict(r.method.replaces)
        if provider is not None:
            out["sunrise"] = {"provider": provider.id, HYBRID_QUANTUM: str(quantum)}
            out["engine_parameters"][HYBRID_QUANTUM] = str(quantum)
        return out

    def flags_for(self, completed_kali_years: int) -> tuple[str, ...]:
        """The flags of a day with ``completed_kali_years`` at its sunrise."""
        s2k = self.resolved.model.saka_to_kali_years
        dated = {
            c.flag
            for c in self.resolved.components
            if completed_kali_years < c.year.kali_threshold(s2k, self.resolved.ce_to_kali_years)
        }
        return tuple(sorted(self._flags | dated))

    def _elements(self, sun: Fraction, moon: Fraction) -> dict[str, int]:
        s, m = ExactArc(sun, AngleUnit.DEGREE), ExactArc(moon, AngleUnit.DEGREE)
        return {e: elements.index(elements.ELEMENTS[e], s, m) for e in ENDING_ELEMENTS}

    def seams(self, jdn: JDN) -> tuple[str, ...]:
        """``seam:<element>`` for each element changing at sunrise ``jdn`` or ``jdn``+1.

        A seam at sunrise *d* + 1: the element in force at the end of day
        *d*'s chord (its sunrise position plus its gati) differs from the
        element at sunrise *d* + 1; both days' records carry it.
        """
        out: set[str] = set()
        for d in (jdn.plus_days(-1), jdn):
            if d.days_since(self.runs_from) < 0:
                continue
            eng = self.engine
            today, nxt = eng.day(d), eng.day(d.plus_days(1))
            end = {b: today.true[b] + eng.gati(b, d) for b in ("sun", "moon")}
            at_end = self._elements(end["sun"], end["moon"])
            at_next = self._elements(nxt.true["sun"], nxt.true["moon"])
            out |= {f"seam:{e}" for e in ENDING_ELEMENTS if seam(at_end[e], at_next[e])}
        return tuple(sorted(out))

    def endings(self, jdn: JDN) -> dict[str, Nadika]:
        """Each element's proportional-parts ending after sunrise ``jdn`` (laghubhaskariya_1963
        II.25–28).

        The yoga's: no text states a yoga rule (laghubhaskariya_1963 II.29 is the
        vyatīpāta); it runs on the fallback datum the model's
        ``yoga_ending`` names, the nakṣatra's rule on the sum.
        """
        eng = self.engine
        d = eng.day(jdn)
        sun, moon = (ExactArc(d.true[b], AngleUnit.DEGREE) for b in ("sun", "moon"))
        gs, gm = (ExactArc(eng.gati(b, jdn), AngleUnit.DEGREE) for b in ("sun", "moon"))
        nadis = self.resolved.model.units.nadis_per_day
        out: dict[str, Nadika] = {}
        for e in ENDING_ELEMENTS:
            el = elements.ELEMENTS[e]
            left = elements.remaining(el, sun, moon).value
            out[e] = proportional_parts(left, elements.motion(el, gs, gm).value, nadis)
        return out

    def ending_root(self, element: str, jdn: JDN) -> Nadika:
        """The exact-root ending of ``element`` after sunrise ``jdn`` (diagnostic).

        Bisection in exact arithmetic on the full evaluation to
        ``siddhantic.root_resolution``, over the two days after sunrise.
        """
        el = elements.ELEMENTS[element]
        eng = self.engine
        d = eng.day(jdn)
        start = self._elements(d.true["sun"], d.true["moon"])[element]

        def crossed(n: Fraction) -> bool:
            _, true = eng.evaluate(jdn, Nadika(n))
            return self._elements(true["sun"], true["moon"])[el.id] != start

        nadis = self.resolved.model.units.nadis_per_day
        hi = Fraction(2 * nadis)
        if not crossed(hi):
            raise EngineRefusal(f"{element} does not end within two days of sunrise {jdn.value}")
        res = self.resolved.parameters[ROOT_RESOLUTION]
        return Nadika(root_bisection(crossed, Fraction(0), hi, res))

    def day(self, jdn: JDN) -> DayResult:
        """The method's computation for civil day ``jdn`` (a hard error before ``runs_from``)."""
        frame = self.engine.civil_day(jdn)
        d = self.engine.day(jdn)
        flags = set(self.flags_for(d.completed_years)) | set(frame.flags) | set(self.seams(jdn))
        assert frame.day_length_nadika is not None
        return DayResult(
            self.resolved.method.id,
            self.resolved.method.status,
            jdn,
            d.ahargana,
            weekday_of_ahargana(d.ahargana.day, self._first),
            d.completed_years,
            d.layer_counts,
            d.mean,
            d.true,
            d.node,
            tuple(sorted(flags)),
            self.provenance,
            d.sunrise,
            d.sunset,
            frame.day_length_nadika,
            self.engine.standard,
            self.endings(jdn),
        )


def build(
    resolved: ResolvedMethod,
    observer: Observer,
    *,
    zero_layers: bool = False,
    sunrise_provider: SunriseProvider | None = None,
    intraday: str = LINEAR_GATI,
) -> MethodRun:
    """Bind ``resolved`` to ``observer`` (the observer is always named)."""
    return MethodRun(
        resolved,
        observer,
        zero_layers=zero_layers,
        sunrise_provider=sunrise_provider,
        intraday=intraday,
    )
