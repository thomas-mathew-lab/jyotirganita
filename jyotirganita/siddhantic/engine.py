"""The siddhantic engine for an epicyclic text.

:class:`TextModel` reads a text's elements, tables and procedure data
(``jyotirganita/data/texts/<text>/``) into exact numbers once;
:class:`SiddhanticEngine` binds a model, the method's layers and one
observer and implements the engine protocol of
:mod:`jyotirganita.core.engine` over ``ExactArc`` and
``SiddhanticCivilInstant``. No code here names a method; the registry
entry (``methods/registry.yaml``) names the text, its layers and, per
slot, the datum stating each procedure (:mod:`jyotirganita.methods.compose`).

The day, as the Āryabhaṭan procedures compute it (every step a registered
procedure, :mod:`jyotirganita.siddhantic.procedures`):

1. the ahargaṇa of the civil day at its sunrise (``time_base``);
2. each element's mean position at mean sunrise on the text's meridian
   (``mean_longitude``, ``mean_precision``, ``epoch_additive``;
   ``computation_instant``), its epoch additive and, per layer, the layer's
   correction for the completed years (``layer.*``);
3. the carry to the observer (``carry.*``), each statement with what it
   acts on, at what motion and on which bodies (``acts_on``, ``motion``,
   ``applies_to``): the deśāntara at mean motion on every
   mean element; the bhujāntara, the Sun's bhujāphala ÷ 21600 of a day,
   on the Sun's true longitude and on the mean of the Moon and the
   planets; the cara, the ascensional difference at the observer
   (:mod:`jyotirganita.siddhantic.sunrise`, from the declination of the
   Sun's longitude for true sunrise at the observer's equatorial point,
   ``declination``, ``declination.argument``, ``ascensional_difference``)
   ÷ 21600 of a day, on the true longitudes, at the true motion for the
   Sun and the Moon and the mean for the planets;
4. the true position: the Sun's and the Moon's manda correction; for Mars,
   Jupiter and Saturn the four-step order, for Mercury and Venus the
   three-step order (``order.superior``, ``order.inferior``), with the
   pulsating epicycles (``pulsation``), the Rsine table and its inverse.

Which bodies take which order follows the data: a body with its own
revolutions and a śīghra epicycle takes the Sun's mean position as its
śīghrocca (``texts.<text>.revolutions.other_sighroccas``); a body with
revolutions only for its śīghrocca takes the Sun's mean position as its
own (``texts.<text>.revolutions.mercury_venus``); a body with a manda
epicycle alone takes the manda correction alone.

**Hybrid sunrise**: where the text's
sunrise datum is a gap, a run must name a geometric sunrise provider. Its
sunrise, a float fraction of the day after local mean midnight, and its
sunset after it (``None`` where the Sun does not
set) are quantised to the engine parameter ``siddhantic.hybrid_sunrise_quantum``
and the mean positions are carried to it at mean motion like the
deśāntara; every record carries ``hybrid_sunrise:modern_geometric`` and
the quantum is in provenance. ``modern/hybrid.py`` supplies the provider.

**Sunrise and the day** (``sunrise``, ``half_day``): the sunrise is 15
nāḍikās after local mean midnight moved by the bhujāntara and the cara;
the sunset is the sunrise plus twice the half-day; the day's length is the
interval to the next computed sunrise (``day_length_nadika``).

**Inside the day** (``gati``, ``intraday``): the gati is
the difference of consecutive sunrise longitudes; a position *n*
nāḍikās after sunrise is the sunrise position plus *n*/60 of the gati, on
[0, 60) (``intraday.linear_gati``). The cara's own motion, which the text
states as the true daily motion, is the difference of consecutive
longitudes before the cara (for true sunrise at the observer's equatorial
point), so that the rule does not call itself. The
diagnostic ``diagnostic.full_evaluation`` evaluates the text's procedure
at a fractional day instead (the mean elements advanced at mean motion
before the equations, the carry as at sunrise) and flags every record
``diagnostic:diagnostic.full_evaluation``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Protocol

from jyotirganita.core.engine import Capabilities, CivilDayFrame
from jyotirganita.core.exact import Rounding, round_to
from jyotirganita.core.memo import DayMemo
from jyotirganita.core.types import (
    JDN,
    NOT_MODELLED,
    Ahargana,
    AngleUnit,
    ExactArc,
    Nadika,
    NotModelled,
    SiddhanticCivilInstant,
    SiderealLongitude,
    TropicalLongitude,
    TrueOfDate,
)
from jyotirganita.data.datum import Record
from jyotirganita.siddhantic.ahargana import ahargana_of_day
from jyotirganita.siddhantic.corrections import Layer
from jyotirganita.siddhantic.endings import chord, sunrise_difference
from jyotirganita.siddhantic.epicycle import Epicycle, manda_correction, sighra_correction
from jyotirganita.siddhantic.mean import mean_daily_motion, mean_longitude, node_from_mean
from jyotirganita.siddhantic.procedures import resolve
from jyotirganita.siddhantic.sunrise import (
    NoSunrise,
    SunriseTimes,
    TimeUnits,
    ascensional_difference,
    day_radius,
    earthsine,
    mean_sunrise,
    rsine_declination,
    signed_rsine,
    sunrise_after_midnight,
)
from jyotirganita.siddhantic.tables import RsineTable
from jyotirganita.siddhantic.text import TextData

__all__ = [
    "BeforeRunsFrom",
    "Carry",
    "DayPositions",
    "EngineRefusal",
    "NoSunriseAtPlace",
    "Observer",
    "SiddhanticEngine",
    "SunriseProvider",
    "TextModel",
]

DEGREES_PER_REVOLUTION = 360
DEGREES_PER_SIGN = 30
NADIKAS_PER_DAY = 60
GHATIS_PER_DAY = 60
MINUTES_PER_DEGREE = 60
DEGREES_PER_QUADRANT = 90
FULL_EVALUATION = "diagnostic.full_evaluation"
LINEAR_GATI = "intraday.linear_gati"

#: The procedure each slot must name for this engine.
SUPPORTED: Mapping[str, str] = {
    "time_base": "ahargana.civil_days_since_kali_epoch",
    "mean_longitude": "mean.yuga_rate_successive_division",
    "mean_precision": "rounding.truncate_at_vikala",
    "epoch_additive": "mean.moon_apogee_node_additive",
    "computation_instant": "computation_instant.meridian_mean_sunrise",
    "sunrise": "sunrise.mean_meridian_plus_carry",
    "carry.desantara": "carry.desantara_ghati",
    "carry.bhujantara": "carry.bhujantara",
    "carry.cara": "carry.cara",
    "rsine": "trig.rsine_table_linear",
    "rversine": "trig.rversine_table_linear",
    "arc": "trig.arc_table_linear",
    "bhuja_koti": "epicycle.bhuja_koti",
    "pulsation": "epicycle.pulsating",
    "manda": "epicycle.manda_bhujaphala",
    "sighra": "epicycle.sighra_karna",
    "order.superior": "order.superior_four_step",
    "order.inferior": "order.inferior_three_step",
    "declination": "declination.rsine_obliquity",
    "declination.argument": "declination_argument.svaniraksa_true_longitude",
    "ascensional_difference": "ascensional_difference.earthsine",
    "half_day": "half_day.quarter_day_plus_cara",
    "gati": "gati.sunrise_difference",
    "proportional_parts": "ending.proportional_parts",
    "intraday": LINEAR_GATI,
    "ending_rounding": "rounding.ending_truncate_at_asu",
}
#: the carry slots and what this engine runs of each
CARRY_SLOTS = ("carry.desantara", "carry.bhujantara", "carry.cara")
ALL_ELEMENTS = "all_elements"
LAYER_SLOTS: Mapping[str, str] = {
    "layer.step": "layer.step_per_completed_year",
    "layer.count_reckoning": "layer.count_by_mean_mesha",
    "layer.negative_count": "layer.negative_count_floor",
}

_REVOLUTIONS = re.compile(r"^([a-z_]+)\.revolutions$")
_MANDA_ODD = re.compile(r"^epicycles\.([a-z_]+)\.manda\.odd$")
_DIFFERENCE = "trig.rsine_differences.d{:02d}"
#: the datum the yoga's ending rests on: no text states a yoga rule
YOGA_ENDING = "procedures.proportional_parts.yoga_note.laghubhaskariya_1963"


class EngineRefusal(ValueError):
    """A request the engine refuses with a hard error."""


class BeforeRunsFrom(EngineRefusal):
    """A civil day before the method's ``runs_from``: the text's count does not exist."""


class NoSunriseAtPlace(EngineRefusal):
    """A day whose Sun the text's sunrise rule does not raise at the observer's latitude."""


def cara_at(
    observer: Observer, jdn: JDN, table: RsineTable, earthsine_value: Fraction, radius: Fraction
) -> Fraction:
    """:func:`~jyotirganita.siddhantic.sunrise.ascensional_difference`, refused by name."""
    try:
        return ascensional_difference(table, earthsine_value, radius)
    except NoSunrise as e:
        raise NoSunriseAtPlace(
            f"observer {observer.id} (latitude {observer.latitude_degrees}°): JDN {jdn.value}: {e}"
        ) from None


@dataclass(frozen=True, slots=True)
class Observer:
    """A place as a siddhantic method takes it.

    ``meridian_offset_ghatis`` east of the text's meridian (west negative);
    ``latitude_degrees`` north. ``route`` is the route by
    which the place reached these values (``text_units`` or
    ``modern_converted``). ``flags`` are the place's record flags
    (``provisional:<place id>`` for a provisional entry). ``text_flags``
    and ``route_data`` are ``(text, flag)`` and ``(text, key)`` pairs: the
    flags a record of that text's method carries for the route, and the data
    the route rests on for it (route (b) through another text's meridian), which its provenance
    names. ``coordinates`` are the latitude
    north and longitude east a user supplied (``regions/places.py``,
    route ``user_coordinates``), recorded in the provenance.
    """

    id: str
    texts: tuple[str, ...]
    meridian_offset_ghatis: Fraction
    latitude_degrees: Fraction
    flags: tuple[str, ...] = ()
    route: str = "text_units"
    text_flags: tuple[tuple[str, str], ...] = ()
    route_data: tuple[tuple[str, str], ...] = ()
    coordinates: tuple[Fraction, Fraction] | None = None

    def flags_for(self, text: str) -> tuple[str, ...]:
        """The place's flags with those its route raises for ``text``."""
        return tuple(sorted({*self.flags, *(f for t, f in self.text_flags if t == text)}))

    def route_data_for(self, text: str) -> tuple[str, ...]:
        """The keys of the data the route rests on for ``text``."""
        return tuple(k for t, k in self.route_data if t == text)


@dataclass(frozen=True, slots=True)
class Carry:
    """One carry statement: its slot, what it acts on, at what motion, on which bodies."""

    slot: str
    key: str
    acts_on: str
    motion: str
    applies_to: frozenset[str]


class SunriseProvider(Protocol):
    """A geometric sunrise for the hybrid alternative (``modern/hybrid.py``)."""

    @property
    def id(self) -> str:
        """The provider's id, recorded in provenance."""
        ...

    def sunrise_fraction(self, jdn: JDN, observer: Observer) -> float:
        """The sunrise of civil day ``jdn`` as a fraction of the day after local mean midnight."""
        ...

    def sunset_fraction(self, jdn: JDN, observer: Observer) -> float | None:
        """The sunset after that sunrise, as the same fraction; ``None`` where the Sun sets not."""
        ...


def hybrid_nadikas(f: float | None, quantum: Fraction, nadis_per_day: int) -> Nadika | None:
    """A provider's fraction of the day quantised to ``quantum``, in nāḍikās."""
    if f is None:
        return None
    return Nadika(round_to(Fraction(f), quantum, Rounding.HALF_EVEN) * nadis_per_day)


@dataclass(frozen=True, slots=True)
class Planet:
    """A body's elements: its mean element, its śīghrocca, its mandocca, its epicycles."""

    body: str
    mean: str  # the element whose mean position is the body's
    sighrocca: str | None
    mandocca: str | None  # a moving apogee element, or None for a fixed one
    apogee: Fraction | None  # a fixed apogee in degrees
    manda: Epicycle
    sighra: Epicycle | None
    order: str  # "manda" | "order.superior" | "order.inferior"


@dataclass(slots=True)
class TextModel:
    """A text's numbers, read once from its data."""

    text: str
    data: TextData
    procedures: Mapping[str, Record]
    table: RsineTable
    civil_days: int
    revolutions: Mapping[str, int]
    planets: Mapping[str, Planet]
    additive_signs: Mapping[str, int]
    node_element: str
    epicycle_divisor: int
    saka_to_kali_years: int
    karna_resolution: Fraction
    day_radius_resolution: Fraction
    rsin_obliquity: Fraction
    units: TimeUnits
    carries: tuple[Carry, ...]
    sunrise_gap: bool = False
    flags: tuple[str, ...] = field(default=())
    #: the key of the datum the yoga's proportional parts rest on (``basis:
    #: fallback_no_stated_rule``): read, so its flag
    #: reaches every record and its file the provenance
    yoga_ending: str = ""

    @classmethod
    def build(
        cls,
        data: TextData,
        procedures: Mapping[str, Record],
        karna_resolution: Fraction,
        day_radius_resolution: Fraction,
        sunrise_gap: bool = False,
    ) -> TextModel:
        """Read the model; ``procedures`` maps each slot to its datum (the registry's)."""
        for slot, expected in SUPPORTED.items():
            if slot == "sunrise" and sunrise_gap:
                continue
            rec = procedures.get(slot)
            if rec is None:
                raise EngineRefusal(f"{data.text}: no procedure datum for slot {slot!r}")
            name = rec.raw.get("procedure")
            if not isinstance(name, str):
                raise EngineRefusal(f"{rec.key}: the datum names no procedure")
            resolve(name, slot)
            if name != expected:
                raise EngineRefusal(
                    f"{rec.key}: procedure {name} for {slot!r} is not one this engine runs "
                    f"({expected})"
                )
            data.mark_used(rec)
        diffs: list[int] = []
        while data.has(_DIFFERENCE.format(len(diffs) + 1)):
            diffs.append(data.integer(_DIFFERENCE.format(len(diffs) + 1)))
        table = RsineTable.of(data.integer("procedures.rsine.interval_minutes"), diffs)
        if table.interval * len(diffs) != DEGREES_PER_QUADRANT * MINUTES_PER_DEGREE:
            # every rule here takes the table's last Rsine as the radius at 90°
            #
            raise EngineRefusal(
                f"{data.text}: the Rsine table spans {table.interval * len(diffs)}′, not a quadrant"
            )
        data.record("civil_days.rule")
        civil = data.integer("earth.rotations") - data.integer("sun.revolutions")
        suffixes = [k.removeprefix(data.prefix) for k in data._records]
        revolutions: dict[str, int] = {}
        for s in suffixes:
            m = _REVOLUTIONS.match(s)
            if m and m.group(1) != "earth":
                revolutions[m.group(1)] = data.integer(s)
        divisor = data.integer("procedures.manda.epicycle_divisor")
        planets: dict[str, Planet] = {}
        for s in sorted(suffixes):
            m = _MANDA_ODD.match(s)
            if not m:
                continue
            body = m.group(1)
            planets[body] = _planet(data, body, revolutions)
        additive = {
            "moon_apogee": data.integer("procedures.apogee_node_additive.moon_apogee_signs"),
            "moon_node": data.integer("procedures.apogee_node_additive.moon_node_signs"),
        }
        data.record("moon_node.direction")
        obliquity = data.fraction("obliquity")
        rsin_obliquity = table.rsine(obliquity * MINUTES_PER_DEGREE)
        units = TimeUnits(
            data.integer("time_units.nadis_per_day"),
            data.integer("time_units.vinadikas_per_nadi")
            * data.integer("time_units.pranas_per_vinadika"),
        )
        carries = _carries(data, procedures, tuple(planets))
        yoga = data.record(YOGA_ENDING)
        if yoga.raw.get("basis") not in ("stated", "fallback_no_stated_rule"):
            raise EngineRefusal(
                f"{yoga.key}: basis {yoga.raw.get('basis')!r} for the yoga's ending"
            )
        return cls(
            data.text,
            data,
            procedures,
            table,
            civil,
            revolutions,
            planets,
            additive,
            "moon_node",
            divisor,
            data.integer("procedures.ahargana.saka_to_kali_years"),
            karna_resolution,
            day_radius_resolution,
            rsin_obliquity,
            units,
            carries,
            sunrise_gap,
            yoga_ending=yoga.key,
        )


_CARRY_RUNS = {
    ("mean_before_equation", "mean"),
    ("true_after_equation", "mean"),
    ("true_after_equation", "true"),
}


def _carries(
    data: TextData, procedures: Mapping[str, Record], bodies: tuple[str, ...]
) -> tuple[Carry, ...]:
    """Every carry statement of the text, checked: each body corrected once per carry slot.

    A slot's statements are the slot's datum and every other datum of the
    text naming the same procedure (one statement per body or group, as the
    text states them, e.g. the Moon's bhujāntara apart from the Sun's).
    """
    out: list[Carry] = []
    for slot in CARRY_SLOTS:
        head = procedures[slot]
        name = head.raw["procedure"]
        recs = [r for r in data.records_with("procedure") if r.raw["procedure"] == name]
        covered: dict[str, str] = {}
        for r in recs:
            acts_on, motion = r.raw.get("acts_on"), r.raw.get("motion")
            applies = r.raw.get("applies_to")
            if acts_on is None or motion is None or applies is None:
                raise EngineRefusal(
                    f"{r.key}: a carry statement states acts_on, motion and applies_to "
                    "(none is assumed)"
                )
            if (acts_on, motion) not in _CARRY_RUNS:
                raise EngineRefusal(f"{r.key}: {acts_on} at {motion} motion is not run here")
            targets = frozenset(str(x) for x in applies)
            if slot == "carry.desantara":
                if targets != {ALL_ELEMENTS} or (acts_on, motion) != (
                    "mean_before_equation",
                    "mean",
                ):
                    raise EngineRefusal(
                        f"{r.key}: the deśāntara acts on all elements at mean motion"
                    )
            else:
                for body in targets:
                    if body not in bodies:
                        raise EngineRefusal(f"{r.key}: applies_to names {body!r}, not a body")
                    if body in covered:
                        raise EngineRefusal(f"{r.key}: {body} is corrected by {covered[body]} too")
                    covered[body] = r.key
            data.mark_used(r)
            out.append(Carry(slot, r.key, str(acts_on), str(motion), targets))
        if slot != "carry.desantara":
            missing = [b for b in bodies if b not in covered]
            if missing:
                raise EngineRefusal(
                    f"{head.key}: no statement of {slot} for {', '.join(missing)} "
                    "(a carry the text does not state is a gap)"
                )
    return tuple(out)


def _planet(data: TextData, body: str, revolutions: Mapping[str, int]) -> Planet:
    def epicycle(kind: str) -> Epicycle | None:
        if not data.has(f"epicycles.{body}.{kind}.odd"):
            return None
        odd = data.fraction(f"epicycles.{body}.{kind}.odd")
        even_key = f"epicycles.{body}.{kind}.even"
        return Epicycle(odd, data.fraction(even_key) if data.has(even_key) else odd)

    manda = epicycle("manda")
    assert manda is not None
    sighra = epicycle("sighra")
    own_sighrocca = f"{body}_sighrocca"
    moving_apogee = f"{body}_apogee" if f"{body}_apogee" in revolutions else None
    apogee = None if moving_apogee else data.fraction(f"{body}.apogee")
    if sighra is None:
        if body not in revolutions:
            raise EngineRefusal(f"{data.key(body)}: a luminary needs its own revolutions")
        return Planet(body, body, None, moving_apogee, apogee, manda, None, "manda")
    if own_sighrocca in revolutions:
        data.record("revolutions.mercury_venus")
        return Planet(body, "sun", own_sighrocca, None, apogee, manda, sighra, "order.inferior")
    if body in revolutions:
        data.record("revolutions.other_sighroccas")
        data.record("procedures.application_order.superior_bodies")
        return Planet(body, body, "sun", None, apogee, manda, sighra, "order.superior")
    raise EngineRefusal(f"{data.key(body)}: neither revolutions nor a śīghrocca's")


@dataclass(frozen=True, slots=True)
class DayTerms:
    """A day's sunrise terms: the Sun's bhujāphala, its declination, the cara."""

    bhujaphala_minutes: Fraction
    rsin_declination: Fraction
    cara_asus: Fraction
    times: SunriseTimes


@dataclass(frozen=True, slots=True)
class DayPositions:
    """The positions of one civil day at its sunrise, with the flags raised.

    ``mean`` holds each element at the observer's mean sunrise (the
    deśāntara and the layers applied), or at the provider's sunrise under
    the hybrid alternative; ``true`` each body at the text's sunrise, the
    carry's bhujāntara and cara applied as the text states. ``sunrise``
    and ``sunset`` are nāḍikās after local mean midnight (the provider's
    under the hybrid alternative); ``terms`` the sunrise terms
    (``None`` under the hybrid alternative).
    """

    jdn: JDN
    ahargana: Ahargana
    completed_years: int
    layer_counts: Mapping[str, int]
    mean: Mapping[str, Fraction]
    true: Mapping[str, Fraction]
    node: Fraction
    flags: tuple[str, ...]
    sunrise: Nadika
    sunset: Nadika | None
    terms: DayTerms | None


class SiddhanticEngine:
    """The engine protocol for a text model, its layers and one observer."""

    def __init__(
        self,
        model: TextModel,
        layers: tuple[Layer, ...],
        observer: Observer,
        epoch: JDN,
        *,
        sunrise_provider: SunriseProvider | None = None,
        hybrid_quantum: Fraction | None = None,
        intraday: str = LINEAR_GATI,
    ) -> None:
        if model.text not in observer.texts:
            raise EngineRefusal(
                f"observer {observer.id} has no coordinates for {model.text} "
                "(the place's route names the texts it serves)"
            )
        if model.sunrise_gap and sunrise_provider is None:
            raise EngineRefusal(
                f"{model.text}: the sunrise datum is a gap; a run names the declared "
                "geometric alternative"
            )
        if sunrise_provider is not None and hybrid_quantum is None:
            raise EngineRefusal("a hybrid sunrise needs siddhantic.hybrid_sunrise_quantum")
        if intraday not in (LINEAR_GATI, FULL_EVALUATION):
            raise EngineRefusal(f"intraday model {intraday!r}: {LINEAR_GATI} or {FULL_EVALUATION}")
        latitude = observer.latitude_degrees
        if abs(latitude) >= DEGREES_PER_QUADRANT:
            raise EngineRefusal(f"observer {observer.id}: latitude {latitude}° is not a place")
        self.model = model
        self.layers = layers
        self.observer = observer
        self.epoch = epoch
        self.sunrise_provider = sunrise_provider
        self.hybrid_quantum = hybrid_quantum
        self.intraday = intraday
        self.frame_id = f"text:{model.text}"
        self.standard = f"text_local:{model.text}"
        t = model.table
        self._rsin_latitude = signed_rsine(t, latitude)
        self._rcos_latitude = t.rsine((DEGREES_PER_QUADRANT - abs(latitude)) * MINUTES_PER_DEGREE)
        self._motion = {
            e: mean_daily_motion(rev, model.civil_days) for e, rev in model.revolutions.items()
        }
        self._carries = {
            body: tuple(c for c in model.carries if body in c.applies_to) for body in model.planets
        }
        self._layer_targets = {layer.id: self._targets(layer) for layer in layers}
        data_flags = {f for r in model.data.used.values() for f in r.flags}
        hybrid = {"hybrid_sunrise:modern_geometric"} if sunrise_provider is not None else set()
        diagnostic = {f"diagnostic:{FULL_EVALUATION}"} if intraday == FULL_EVALUATION else set()
        self._flags = tuple(
            sorted(data_flags | set(observer.flags_for(model.text)) | hybrid | diagnostic)
        )
        self._memo: DayMemo[int, DayPositions] = DayMemo()
        self._pre: DayMemo[int, tuple[dict[str, Fraction], Fraction]] = DayMemo()

    def _targets(self, layer: Layer) -> Mapping[str, str]:
        out: dict[str, str] = {}
        for name in layer.rates:
            if name in self.model.revolutions:
                out[name] = name
            elif f"{name}_sighrocca" in self.model.revolutions:
                out[name] = f"{name}_sighrocca"  # the body's own moving element
            else:
                raise EngineRefusal(f"layer {layer.id}: rate for {name}, which has no element")
        return out

    # --- the protocol -----------------------------------------------------------

    @property
    def time_base(self) -> type:
        return Ahargana

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(
            bodies=tuple(self.model.planets),
            node=True,
            not_modelled={
                "latitude": "no latitude rule keyed; the Moon's is a later package's",
                "tropical_longitude": "a siddhantic method has no tropical frame",
                "distance": "not modelled",
                "eclipses": "not modelled",
            },
        )

    def civil_day(self, jdn: JDN) -> CivilDayFrame[SiddhanticCivilInstant]:
        self._check_runs_from(jdn)
        day = self.day(jdn)
        sunrise = self.instant(jdn, Nadika(0))
        sunset: SiddhanticCivilInstant | NotModelled = NOT_MODELLED
        if day.sunset is not None:
            sunset = self.instant(jdn, day.sunset - day.sunrise)
        return CivilDayFrame(
            jdn=jdn,
            start=sunrise,
            end=self.instant(jdn.plus_days(1), Nadika(0)),
            sunrise=sunrise,
            sunset=sunset,
            sunrise_after_local_midnight=day.sunrise,
            meridian=f"{self.frame_id}+{self.observer.meridian_offset_ghatis}ghati",
            flags=day.flags,
            day_length_nadika=self.day_length(jdn),
        )

    def instant(self, jdn: JDN, after_start: Nadika) -> SiddhanticCivilInstant:
        return SiddhanticCivilInstant(jdn, after_start, self.standard)

    def sidereal_longitude(
        self, body: str, instant: SiddhanticCivilInstant
    ) -> SiderealLongitude[ExactArc]:
        if body not in self.model.planets:
            raise EngineRefusal(f"{self.model.text} serves no body {body!r}")
        return self._longitude(self._position(body, instant))

    def tropical_longitude(
        self, body: str, instant: SiddhanticCivilInstant
    ) -> TropicalLongitude[TrueOfDate] | NotModelled:
        return NOT_MODELLED

    def daily_motion(self, body: str, day: JDN) -> ExactArc | NotModelled:
        if body not in self.model.planets:
            raise EngineRefusal(f"{self.model.text} serves no body {body!r}")
        return ExactArc(self.gati(body, day), AngleUnit.DEGREE)

    def node(self, instant: SiddhanticCivilInstant) -> SiderealLongitude[ExactArc]:
        return self._longitude(self._position(None, instant))

    def latitude(self, body: str, instant: SiddhanticCivilInstant) -> ExactArc | NotModelled:
        return NOT_MODELLED

    # --- the day ------------------------------------------------------------------

    @property
    def runs_from(self) -> JDN:
        """The first civil day of the text's count."""
        return self.epoch

    @property
    def flags(self) -> tuple[str, ...]:
        """The flags every record of this engine carries."""
        return self._flags

    def _check_runs_from(self, jdn: JDN) -> None:
        if jdn.days_since(self.epoch) < 0:
            raise BeforeRunsFrom(
                f"JDN {jdn.value} is before runs_from (JDN {self.epoch.value}) of "
                f"{self.model.text}: the text's own count does not exist before it "
                ""
            )

    def _longitude(self, degrees: Fraction) -> SiderealLongitude[ExactArc]:
        return SiderealLongitude(ExactArc(degrees, AngleUnit.DEGREE), self.frame_id)

    def _position(self, body: str | None, instant: SiddhanticCivilInstant) -> Fraction:
        """A body's longitude (the node's for ``None``) at ``instant`` by the intraday model."""
        if instant.standard != self.standard:
            raise EngineRefusal(f"instant of {instant.standard}, engine of {self.standard}")
        jdn, n = instant.jdn, instant.nadika_after_sunrise
        day = self.day(jdn)
        at_sunrise = day.node if body is None else day.true[body]
        if n == Nadika(0):
            return at_sunrise
        nadis = self.model.units.nadis_per_day
        if self.intraday == FULL_EVALUATION:
            if not 0 <= n.value < nadis:
                chord(at_sunrise, Fraction(0), n, nadis)  # the same refusal as the chord's
            node, true = self._evaluate(jdn, n.value / nadis)
            return node if body is None else true[body]
        gati = self.node_gati(jdn) if body is None else self.gati(body, jdn)
        return chord(at_sunrise, gati, n, nadis)

    def gati(self, body: str, jdn: JDN) -> Fraction:
        """The body's true daily motion on ``jdn``: tomorrow's sunrise longitude less today's."""
        return sunrise_difference(self.day(jdn).true[body], self.day(jdn.plus_days(1)).true[body])

    def node_gati(self, jdn: JDN) -> Fraction:
        """The node's daily motion on ``jdn``, the same difference."""
        return sunrise_difference(self.day(jdn).node, self.day(jdn.plus_days(1)).node)

    def day_length(self, jdn: JDN) -> Nadika:
        """The computed interval from this sunrise to the next (``day_length_nadika``)."""
        nadis = Nadika(self.model.units.nadis_per_day)
        return nadis + self.day(jdn.plus_days(1)).sunrise - self.day(jdn).sunrise

    def _sunrise_after_midnight(self, jdn: JDN) -> tuple[Nadika, tuple[str, ...]]:
        assert self.sunrise_provider is not None and self.hybrid_quantum is not None
        f = self.sunrise_provider.sunrise_fraction(jdn, self.observer)
        q = round_to(Fraction(f), self.hybrid_quantum, Rounding.HALF_EVEN)
        return Nadika(q * NADIKAS_PER_DAY), ("hybrid_sunrise:modern_geometric",)

    def _offset_days(self, jdn: JDN) -> Fraction:
        """The time from the computation instant to the observer's mean sunrise, in days.

        Under the hybrid alternative, to the provider's sunrise instead.
        """
        offset = -self.observer.meridian_offset_ghatis / GHATIS_PER_DAY
        if self.sunrise_provider is not None:
            after, _ = self._sunrise_after_midnight(jdn)
            offset += (after.value - mean_sunrise(self.model.units).value) / NADIKAS_PER_DAY
        return offset

    def _mean(
        self, jdn: JDN, extra_days: Fraction
    ) -> tuple[Ahargana, int, dict[str, int], dict[str, Fraction]]:
        """The mean elements at the observer's mean sunrise plus ``extra_days``."""
        m = self.model
        ahargana = ahargana_of_day(m.text, self.epoch, jdn)
        a = ahargana.day
        years = mean_longitude(m.revolutions["sun"], m.civil_days, a).revolutions
        counts = {layer.id: layer.count(years, m.saka_to_kali_years) for layer in self.layers}
        offset = self._offset_days(jdn) + extra_days
        mean: dict[str, Fraction] = {}
        for element, rev in m.revolutions.items():
            lon = mean_longitude(rev, m.civil_days, a).degrees + self._motion[element] * offset
            signs = m.additive_signs.get(element, 0)
            if element == m.node_element:
                lon = node_from_mean(lon, signs)
            else:
                lon += signs * DEGREES_PER_SIGN
            mean[element] = lon
        for layer in self.layers:
            for name, element in self._layer_targets[layer.id].items():
                mean[element] += layer.correction(name, counts[layer.id])
        return ahargana, years, counts, {k: v % DEGREES_PER_REVOLUTION for k, v in mean.items()}

    def _bhujaphala_minutes(self, mean: Mapping[str, Fraction]) -> Fraction:
        """The Sun's signed bhujāphala in minutes (positive when additive; laghubhaskariya_1963
        II.3(ii)–4(i))."""
        sun = self.model.planets["sun"]
        apogee = mean[sun.mandocca] if sun.mandocca else sun.apogee
        assert apogee is not None
        return self._manda(sun, mean[sun.mean] - apogee, arc=False) * MINUTES_PER_DEGREE

    def _body(
        self,
        p: Planet,
        mean: Mapping[str, Fraction],
        dt: Mapping[str, Fraction],
        gati: Fraction | None,
        *,
        cara: bool,
    ) -> Fraction:
        """A body's true longitude with its carry statements applied.

        ``dt`` maps each carry slot to its time value in days; ``gati`` is the
        body's true motion for a statement at the true motion, ``None`` before
        the cara, where no true motion is known yet: a statement at the true
        motion acting there is refused rather than applied at zero motion
        (release review F-L6; no shipped text has one).
        """
        carries = [c for c in self._carries[p.body] if cara or c.slot != "carry.cara"]
        shifted = dict(mean)
        for c in carries:
            if c.acts_on == "mean_before_equation":
                shifted[p.mean] += self._motion[p.mean] * dt[c.slot]
        t = self._true(p, shifted)
        for c in carries:
            if c.acts_on == "true_after_equation":
                if c.motion == "mean":
                    motion = self._motion[p.mean]
                elif gati is None:
                    raise EngineRefusal(
                        f"{p.body}: {c.slot} acts at the true motion before the cara, "
                        "where the engine has no true motion"
                    )
                else:
                    motion = gati
                t += motion * dt[c.slot]
        return t % DEGREES_PER_REVOLUTION

    def _pre_cara(self, jdn: JDN) -> tuple[dict[str, Fraction], Fraction]:
        """Every body before the cara (true sunrise at the equatorial point), and dt_b."""
        memo = self._pre.get(jdn.value)
        if memo is not None:
            return memo
        _, _, _, mean = self._mean(jdn, Fraction(0))
        dt_b = self._bhujaphala_minutes(mean) / self.model.units.asus_per_day
        dt = {"carry.bhujantara": dt_b, "carry.cara": Fraction(0)}
        pre = {b: self._body(p, mean, dt, None, cara=False) for b, p in self.model.planets.items()}
        self._pre[jdn.value] = (pre, dt_b)
        return pre, dt_b

    def _terms(self, jdn: JDN) -> DayTerms:
        """The day's sunrise terms from the Sun before the cara (mahabhaskariya_1960 IV.25;
        laghubhaskariya_1963 II.16–20)."""
        m = self.model
        pre, _ = self._pre_cara(jdn)
        _, _, _, mean = self._mean(jdn, Fraction(0))
        bhujaphala = self._bhujaphala_minutes(mean)
        rsin_d = rsine_declination(m.table, m.rsin_obliquity, pre["sun"])
        radius = day_radius(m.table, rsin_d, m.day_radius_resolution)
        e = earthsine(self._rsin_latitude, self._rcos_latitude, rsin_d)
        cara = cara_at(self.observer, jdn, m.table, e, radius)
        return DayTerms(bhujaphala, rsin_d, cara, sunrise_after_midnight(bhujaphala, cara, m.units))

    def _carry_inputs(self, jdn: JDN) -> tuple[dict[str, Fraction], dict[str, Fraction]]:
        """The carry's time values and each body's motion for the cara (pre-cara difference)."""
        terms = self._terms(jdn)
        dt = {"carry.bhujantara": terms.times.bhujantara_days, "carry.cara": terms.times.cara_days}
        pre, _ = self._pre_cara(jdn)
        nxt, _ = self._pre_cara(jdn.plus_days(1))
        gati = {b: sunrise_difference(pre[b], nxt[b]) for b in self.model.planets}
        return dt, gati

    def day(self, jdn: JDN) -> DayPositions:
        """Every body's mean and true position at the sunrise of civil day ``jdn``."""
        self._check_runs_from(jdn)
        memo = self._memo.get(jdn.value)
        if memo is not None:
            return memo
        m = self.model
        ahargana, years, counts, mean = self._mean(jdn, Fraction(0))
        terms: DayTerms | None = None
        sunset: Nadika | None = None
        flags = self._flags
        if self.sunrise_provider is not None:
            true = {b: self._true(p, mean) % DEGREES_PER_REVOLUTION for b, p in m.planets.items()}
            sunrise, hybrid = self._sunrise_after_midnight(jdn)
            flags = tuple(sorted(set(flags) | set(hybrid)))
            assert self.hybrid_quantum is not None
            sunset = hybrid_nadikas(
                self.sunrise_provider.sunset_fraction(jdn, self.observer),
                self.hybrid_quantum,
                NADIKAS_PER_DAY,
            )
        else:
            terms = self._terms(jdn)
            dt, gati = self._carry_inputs(jdn)
            true = {b: self._body(p, mean, dt, gati[b], cara=True) for b, p in m.planets.items()}
            sunrise, sunset = terms.times.sunrise, terms.times.sunset
        out = DayPositions(
            jdn,
            ahargana,
            years,
            counts,
            mean,
            true,
            mean[m.node_element],
            flags,
            sunrise,
            sunset,
            terms,
        )
        self._memo[jdn.value] = out
        return out

    def _evaluate(self, jdn: JDN, extra_days: Fraction) -> tuple[Fraction, dict[str, Fraction]]:
        """The full evaluation at a fractional day (diagnostic).

        The mean elements are advanced at mean motion by ``extra_days`` before
        the equations; the carry's time values and motions are those of the
        day's sunrise. Returns the node and the bodies.
        """
        m = self.model
        _, _, _, mean = self._mean(jdn, extra_days)
        if self.sunrise_provider is not None:
            true = {b: self._true(p, mean) % DEGREES_PER_REVOLUTION for b, p in m.planets.items()}
        else:
            dt, gati = self._carry_inputs(jdn)
            true = {b: self._body(p, mean, dt, gati[b], cara=True) for b, p in m.planets.items()}
        return mean[m.node_element], true

    def evaluate(self, jdn: JDN, n: Nadika) -> tuple[Fraction, dict[str, Fraction]]:
        """The full evaluation *n* nāḍikās after sunrise ``jdn`` (any *n*; diagnostic)."""
        self._check_runs_from(jdn)
        return self._evaluate(jdn, n.value / self.model.units.nadis_per_day)

    def _manda(self, p: Planet, kendra: Fraction, *, arc: bool) -> Fraction:
        m = self.model
        return manda_correction(p.manda, kendra, m.table, m.epicycle_divisor, arc=arc)

    def _sighra(self, p: Planet, kendra: Fraction) -> Fraction:
        m = self.model
        assert p.sighra is not None
        return sighra_correction(p.sighra, kendra, m.table, m.epicycle_divisor, m.karna_resolution)

    def _true(self, p: Planet, mean: Mapping[str, Fraction]) -> Fraction:
        planet = mean[p.mean]
        apogee = mean[p.mandocca] if p.mandocca else p.apogee
        assert apogee is not None
        if p.order == "manda":
            # laghubhaskariya_1963 II.3(ii)–4(i), II.23–24: the bhujāphala applied as it is
            return planet + self._manda(p, planet - apogee, arc=False)
        assert p.sighrocca is not None
        sighrocca = mean[p.sighrocca]
        if p.order == "order.superior":
            # laghubhaskariya_1963 II.33–37(i)
            m1 = planet + self._manda(p, planet - apogee, arc=True) / 2
            m2 = m1 + self._sighra(p, sighrocca - m1) / 2
            true_mean = planet + self._manda(p, m2 - apogee, arc=True)
            return true_mean + self._sighra(p, sighrocca - true_mean)
        # laghubhaskariya_1963 II.37(ii)–39: half the śīghra on the mandocca, with the reverse sign
        corrected_apogee = apogee - self._sighra(p, sighrocca - planet) / 2
        true_mean = planet + self._manda(p, planet - corrected_apogee, arc=True)
        return true_mean + self._sighra(p, sighrocca - true_mean)
