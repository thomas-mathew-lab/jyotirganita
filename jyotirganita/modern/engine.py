"""The modern engine: the engine protocol over the JPL kernels.

:class:`ModernEngine` binds one configuration (:class:`ModernConfig`, every component named, nothing
defaulted) and one observer
(:class:`~jyotirganita.modern.riseset.ModernObserver`) and serves the
engine protocol of ``core/engine.py`` over ``FloatArc`` and
``ModernCivilInstant``, with TT as its time base.

**Clock.** A civil instant is read on the configuration's time standard
(``data/time_standards/``): a standard defined as an offset from
Universal Time reaches TT through UTC and the leap-second table where the
table holds (1972 on), and before that through Greenwich mean time read as
UT1 (``core.types.ut1_from_gmt``) and the ΔT model; a local mean time
reaches UT1 at the observer's longitude and TT through the ΔT model.
UT1, wherever the engine needs it (sidereal time), is TT less the ΔT
model's value. A standard out of force on a day is refused.

**Range.** Every instant is checked against the components' stated
ranges: the kernel's span (TDB), the ΔT model's range and the precession
theory's; a component that states no range imposes none. Refusals name the component; nothing is
composed or extrapolated.

**Positions.** Apparent geocentric places (``modern/apparent.py``,
``observer_frame: geocentric``, the only frame served for the calendar
elements) on the true ecliptic and equinox of date or the
mean (``modern/frames.py``), less the ayanāṃśa of the same nutation
instance (``core.types.sidereal_from_tropical``; ``modern/ayanamsa.py``).
The daily motion is the sidereal arc between the starts of the civil day
and the next. The node: ``mean`` is Ω, the fifth
fundamental argument of the configured nutation theory, referred to the
mean equinox of date (plus Δψ on the true equinox); ``osculating`` is the
ascending node of the Moon's geocentric osculating orbit on the ecliptic of
date, from the kernel's geometric state. Rāhu's output and the latitude
both use :meth:`ModernEngine.node`.

**The civil day** (``civil_day``): the convention set's start, ``sunrise``
(the first rise of the Sun's event in the civil date, local midnight to
local midnight on the standard) or ``midnight``; its end is the next
day's start. An instant inside the day is its start plus a duration in
days of TT.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from math import floor
from typing import Any

import numpy as np

from jyotirganita.core.engine import Capabilities, CivilDayFrame
from jyotirganita.core.memo import DayMemo
from jyotirganita.core.types import (
    JDN,
    NOT_MODELLED,
    TT,
    UT1,
    AngleUnit,
    FloatArc,
    FloatDays,
    MeanOfDate,
    ModernCivilInstant,
    Nadika,
    SiderealLongitude,
    TropicalLongitude,
    TrueOfDate,
    civil_from_utc,
    gmt_from_ut1,
    mean_time_from_ut1,
    sidereal_from_tropical,
    sidereal_from_tropical_mean,
    ut1_from_gmt,
    ut1_from_mean_time,
    ut1_from_tt,
    utc_from_civil,
)
from jyotirganita.data.datum import Record
from jyotirganita.data.engine_parameters import EngineParameter
from jyotirganita.data.time_standards import TimeStandard
from jyotirganita.modern.angles import r1
from jyotirganita.modern.apparent import BODIES, Apparent, ApparentPlace
from jyotirganita.modern.ayanamsa import AyanamsaModel, make_ayanamsa
from jyotirganita.modern.deltat import DeltaTModel, make_model, tt_of_ut1
from jyotirganita.modern.eclipses import Eclipses
from jyotirganita.modern.frames import Frame
from jyotirganita.modern.kernels import Ephemeris, KernelEntry, KernelError, load_registry
from jyotirganita.modern.nutation import NutationAngles, make_nutation
from jyotirganita.modern.precession import PrecessionTheory, make_precession
from jyotirganita.modern.riseset import Event, ModernObserver, RiseSet
from jyotirganita.modern.roots import RootFinder
from jyotirganita.modern.timescales import SECONDS_PER_DAY, OutOfRange, TimeScales

__all__ = [
    "CIVIL_DAY_STARTS",
    "NODES",
    "OBSERVER_FRAMES",
    "ModernConfig",
    "ModernEngine",
    "preset_range",
    "range_text",
    "stated_range",
]

CIVIL_DAY_STARTS = ("sunrise", "midnight")
NODES = ("mean", "osculating")
OBSERVER_FRAMES = ("geocentric",)
NADIKAS_PER_DAY = 60
_DEG = AngleUnit.DEGREE
_HALF_CIRCLE = 180


@dataclass(frozen=True, slots=True)
class ModernConfig:
    """Every component of a modern run, named (no hidden defaults)."""

    kernel: str
    delta_t: str
    delta_t_seconds: Fraction | None
    precession: str
    nutation: str
    ayanamsa: str
    ayanamsa_equinox: str
    ayanamsa_aberration: bool | None
    ayanamsa_coefficients: tuple[Fraction, ...] | None
    observer_frame: str
    sunrise_event: Event
    node: str
    time_standard: str
    civil_day_start: str

    def __post_init__(self) -> None:
        if self.observer_frame not in OBSERVER_FRAMES:
            raise ValueError(
                f"observer_frame {self.observer_frame!r}: the calendar elements are served "
                f"geocentric only"
            )
        if self.node not in NODES:
            raise ValueError(f"node {self.node!r} is not one of {NODES}")
        if self.civil_day_start not in CIVIL_DAY_STARTS:
            raise ValueError(f"civil-day start {self.civil_day_start!r} not in {CIVIL_DAY_STARTS}")


def stated_range(
    entry: KernelEntry, delta_t: DeltaTModel, precession: PrecessionTheory
) -> tuple[TT, TT]:
    """A run's range: the kernel's span (a day inside each end, its TDB read as TT) intersected
    with the ΔT model's and the precession theory's stated ranges; a component
    that states no range imposes none, and nothing is extrapolated."""
    if entry.span_from_jd is None or entry.span_to_jd is None:
        raise KernelError(f"kernel {entry.id} records no span (not yet fetched and verified)")
    lo_whole, hi_whole = floor(entry.span_from_jd), floor(entry.span_to_jd)
    lo = TT(lo_whole + 1, float(entry.span_from_jd - lo_whole))
    hi = TT(hi_whole - 1, float(entry.span_to_jd - hi_whole))
    for a, b in (delta_t.range_tt(), precession.range_tt()):
        if a is not None and lo < a:
            lo = a
        if b is not None and b < hi:
            hi = b
    if not lo < hi:
        raise OutOfRange("the components' stated ranges do not overlap")
    return lo, hi


def _jd(x: Fraction | None) -> str:
    return "unrecorded" if x is None else str(float(x))


def range_text(entry: KernelEntry, delta_t: DeltaTModel, precession: PrecessionTheory) -> str:
    """The components' stated ranges, as the sources state them."""
    return (
        f"kernel {entry.id} {_jd(entry.span_from_jd)}–{_jd(entry.span_to_jd)} (TDB JD); "
        f"ΔT {delta_t.id}: "
        f"{delta_t.range_text}; precession {precession.id}: {precession.range_text}"
    )


def preset_range(
    kernel: str, delta_t: str, precession: str, data: Mapping[str, Record]
) -> tuple[TT, TT, str]:
    """A preset's range from its components' ids, without opening the kernel (the ledger's)."""
    scales = TimeScales(data)
    entry = load_registry().get(kernel)
    if entry is None:
        raise KernelError(f"no kernel {kernel!r} in the registry")
    dt = make_model(delta_t, scales, data)
    prec = make_precession(precession, data, scales)
    lo, hi = stated_range(entry, dt, prec)
    return lo, hi, range_text(entry, dt, prec)


def _deg(radians: float) -> FloatArc:
    return FloatArc(float(np.degrees(radians)), _DEG)


class ModernEngine:
    """The engine protocol over the JPL kernels (module docstring)."""

    def __init__(
        self,
        config: ModernConfig,
        observer: ModernObserver,
        *,
        data: Mapping[str, Record],
        time_standards: Mapping[str, TimeStandard],
        parameters: Mapping[str, EngineParameter],
        ephemeris: Ephemeris | None = None,
    ) -> None:
        self.config = config
        self.observer = observer
        self._data = data
        self.scales = TimeScales(data)
        self.ephemeris = ephemeris or Ephemeris.open(config.kernel)
        if self.ephemeris.entry.id != config.kernel:
            raise KernelError(f"the ephemeris is {self.ephemeris.entry.id}, not {config.kernel}")
        self.delta_t: DeltaTModel = make_model(
            config.delta_t, self.scales, data, constant_seconds=config.delta_t_seconds
        )
        self.precession = make_precession(config.precession, data, self.scales)
        self.nutation = make_nutation(config.nutation)
        self.frame = Frame(
            self.precession, self.nutation, self.scales, parameters["modern.cio_locator_step"]
        )
        self.apparent = Apparent(
            self.ephemeris, self.scales, data, parameters["modern.light_time_iterations"]
        )
        self.ayanamsa: AyanamsaModel = make_ayanamsa(
            config.ayanamsa,
            equinox=config.ayanamsa_equinox,
            data=data,
            scales=self.scales,
            frame=self.frame,
            apparent=self.apparent,
            aberration=config.ayanamsa_aberration,
            coefficients=config.ayanamsa_coefficients,
        )
        if config.time_standard not in time_standards:
            raise ValueError(f"no time standard {config.time_standard!r}")
        self.standard = time_standards[config.time_standard]
        self.element_roots = RootFinder.of(
            parameters["modern.root.scan_step"],
            parameters["modern.root.tolerance"],
            parameters["modern.root.iteration_cap"],
        )
        self.riseset = RiseSet(
            self.frame,
            self.apparent,
            data,
            config.sunrise_event,
            observer,
            self.ut1_of,
            RootFinder.of(
                parameters["modern.riseset.scan_step"],
                parameters["modern.root.tolerance"],
                parameters["modern.root.iteration_cap"],
            ),
        )
        self._places: dict[str, tuple[tuple[int, float], ApparentPlace]] = {}
        self._frames: DayMemo[int, CivilDayFrame[ModernCivilInstant]] = DayMemo()
        self._starts: DayMemo[int, tuple[TT, TT, TT | None, TT]] = DayMemo()

    # --- the protocol's fixed members ----------------------------------------------

    @property
    def time_base(self) -> type:
        return TT

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(
            tuple(BODIES),
            True,
            {
                "eclipses": "provisional:eclipse (modern/eclipses.py; no published canon "
                "compared yet)"
            },
        )

    def eclipses(self) -> Eclipses:
        """The eclipse geometry at the engine's observer, provisional (``modern/eclipses.py``)."""
        return Eclipses(self.apparent, self.riseset, self._data, self.riseset.roots, self.check)

    # --- range and clock -------------------------------------------------------------

    def check(self, tt: TT) -> None:
        """Refuse an instant outside a component's stated range, naming the component."""
        jd1, jd2 = self.scales.tdb_parts(tt)
        if not self.ephemeris.covers(jd1 + jd2):
            e = self.ephemeris.entry
            raise OutOfRange(
                f"kernel {e.id}: TT JD {tt.jd_whole + tt.jd_fraction:.5f} is outside its span "
                f"{e.span_from_jd}–{e.span_to_jd} (TDB)"
            )
        self.delta_t.delta_t(tt)
        self.precession.check(tt)

    def range_tt(self) -> tuple[TT, TT]:
        """The run's range (:func:`stated_range`)."""
        return stated_range(self.ephemeris.entry, self.delta_t, self.precession)

    def bounding_components(self) -> tuple[str, str]:
        """The components whose stated ranges bound :meth:`range_tt` below and above."""
        lo, hi = self.range_tt()
        names = (
            (self.delta_t.range_tt(), f"ΔT model {self.delta_t.id}"),
            (self.precession.range_tt(), f"precession {self.precession.id}"),
        )
        low = high = f"kernel {self.ephemeris.entry.id}"
        for (a, b), name in names:
            if a is not None and a == lo:
                low = name
            if b is not None and b == hi:
                high = name
        return low, high

    def range_text(self) -> str:
        """The components' stated ranges, for messages and provenance."""
        return range_text(self.ephemeris.entry, self.delta_t, self.precession)

    def served_days(self) -> tuple[JDN, JDN]:
        """The first and last civil days whose bounds lie inside :meth:`range_tt`, with a day's
        margin on each side for the next day's start and the time standard's offset."""
        lo, hi = self.range_tt()
        first = floor(lo.jd_whole + lo.jd_fraction + Fraction(1, 2)) + 2
        last = floor(hi.jd_whole + hi.jd_fraction + Fraction(1, 2)) - 2
        return JDN(first), JDN(last)

    def ut1_of(self, tt: TT) -> UT1:
        """UT1 = TT − ΔT under the configured model (refused outside its range)."""
        return ut1_from_tt(tt, FloatDays(self.delta_t.delta_t(tt) / SECONDS_PER_DAY))

    def _offset(self, day: JDN) -> Fraction:
        return self.standard.offset_on(day, self.observer.longitude_deg)

    def tt_of_civil(self, instant: ModernCivilInstant) -> TT:
        """The TT of a civil instant on the configuration's standard (module docstring)."""
        if instant.standard != self.standard.id:
            raise ValueError(
                f"an instant on {instant.standard}, the engine's is {self.standard.id}"
            )
        off = self._offset(instant.jdn)
        if self.standard.kind == "local_mean_time":
            tt, _ = tt_of_ut1(self.delta_t, ut1_from_mean_time(instant, off))
            return tt
        utc = utc_from_civil(instant, off)
        if self.scales.leap.covers(utc):
            return self.scales.tt_from_utc(utc)
        tt, _ = tt_of_ut1(self.delta_t, ut1_from_gmt(utc))
        return tt

    def civil_of_tt(self, tt: TT, near: JDN) -> ModernCivilInstant:
        """The civil instant of TT ``tt``; ``near`` is a civil day within one of it."""
        sid = self.standard.id
        if self.standard.kind == "local_mean_time":
            return mean_time_from_ut1(self.ut1_of(tt), self._offset(near), sid)
        try:
            utc = self.scales.utc_from_tt(tt)
        except OutOfRange:
            utc = gmt_from_ut1(self.ut1_of(tt))
        else:
            if not self.scales.leap.covers(utc):
                utc = gmt_from_ut1(self.ut1_of(tt))
        out = civil_from_utc(utc, self._offset(near), sid)
        if out.jdn != near:
            out = civil_from_utc(utc, self._offset(out.jdn), sid)
        return out

    # --- positions --------------------------------------------------------------------

    def place(self, body: str, tt: TT) -> ApparentPlace:
        """The apparent geocentric place of ``body`` at TT ``tt`` (last instant kept)."""
        key = (tt.jd_whole, tt.jd_fraction)
        hit = self._places.get(body)
        if hit is None or hit[0] != key:
            hit = (key, self.apparent.place(body, tt))
            self._places[body] = hit
        return hit[1]

    def _true(self, body: str, tt: TT) -> tuple[float, float, NutationAngles]:
        return self.frame.true_ecliptic(self.place(body, tt).direction, self.scales.centuries(tt))

    def tropical_at(self, body: str, tt: TT) -> TropicalLongitude[TrueOfDate]:
        lon, _lat, nut = self._true(body, tt)
        return TropicalLongitude(_deg(lon), TrueOfDate, nut.identity)

    def sidereal_at(self, body: str, tt: TT) -> SiderealLongitude[FloatArc]:
        """The sidereal longitude of ``body`` at TT ``tt`` under the configured ayanāṃśa."""
        t = self.scales.centuries(tt)
        u = self.place(body, tt).direction
        if self.ayanamsa.equinox == "true":
            lon, _lat, nut = self.frame.true_ecliptic(u, t)
            trop = TropicalLongitude(_deg(lon), TrueOfDate, nut.identity)
            return sidereal_from_tropical(trop, self.ayanamsa.at(tt, nut))
        lon, _lat = self.frame.mean_ecliptic(u, t)
        mean = TropicalLongitude(_deg(lon), MeanOfDate, None)
        return sidereal_from_tropical_mean(mean, self.ayanamsa.at(tt, None))

    def node_at(self, tt: TT) -> SiderealLongitude[FloatArc]:
        """The Moon's ascending node, as :attr:`ModernConfig.node` names it (module docstring)."""
        t = self.scales.centuries(tt)
        nut, m = self.frame.state(t)
        true_eq = self.ayanamsa.equinox == "true"
        if self.config.node == "mean":
            omega = self.nutation.mean_node(t) + (nut.dpsi if true_eq else 0.0)
        else:
            jd1, jd2 = self.scales.tdb_parts(tt)
            pm, vm = self.ephemeris.barycentric("MOON", jd1, jd2)
            pe, ve = self.ephemeris.barycentric("EARTH", jd1, jd2)
            if true_eq:
                rot = r1(self.precession.mean_obliquity(t) + nut.deps) @ m
            else:
                rot = r1(self.precession.mean_obliquity(t)) @ self.precession.bias_precession(t)
            h = np.cross(rot @ (pm - pe), rot @ (vm - ve))
            omega = float(np.arctan2(h[0], -h[1]))
        if true_eq:
            trop = TropicalLongitude(_deg(omega), TrueOfDate, nut.identity)
            return sidereal_from_tropical(trop, self.ayanamsa.at(tt, nut))
        mean = TropicalLongitude(_deg(omega), MeanOfDate, None)
        return sidereal_from_tropical_mean(mean, self.ayanamsa.at(tt, None))

    # --- the civil day ------------------------------------------------------------------

    def day_bounds(self, jdn: JDN) -> tuple[TT, TT, TT | None, TT]:
        """The day's start, its sunrise, its sunset (or ``None``) and its local midnight, in TT."""
        hit = self._starts.get(jdn.value)
        if hit is not None:
            return hit
        sid = self.standard.id
        m0 = self.tt_of_civil(ModernCivilInstant(jdn, 0.0, sid))
        m1 = self.tt_of_civil(ModernCivilInstant(jdn.plus_days(1), 0.0, sid))
        self.check(m0)
        self.check(m1)
        events = self.riseset.events("sun", m0, m1)
        rises = [t for t, k in events if k == "rise"]
        if not rises:
            raise OutOfRange(f"no sunrise on JDN {jdn.value} at {self.observer.id}")
        sunrise = rises[0]
        sets = [t for t, k in events if k == "set" and sunrise < t]
        sunset = sets[0] if sets else None
        start = sunrise if self.config.civil_day_start == "sunrise" else m0
        out = (start, sunrise, sunset, m0)
        self._starts[jdn.value] = out
        return out

    def civil_day(self, jdn: JDN) -> CivilDayFrame[ModernCivilInstant]:
        hit = self._frames.get(jdn.value)
        if hit is not None:
            return hit
        start, sunrise, sunset, _ = self.day_bounds(jdn)
        nxt = jdn.plus_days(1)
        end = self.day_bounds(nxt)[0]
        frame = CivilDayFrame(
            jdn,
            self.civil_of_tt(start, jdn),
            self.civil_of_tt(end, nxt),
            self.civil_of_tt(sunrise, jdn),
            self.civil_of_tt(sunset, jdn) if sunset is not None else NOT_MODELLED,
            None,
            self.standard.id,
            self.observer.flags,
        )
        self._frames[jdn.value] = frame
        return frame

    def instant(self, jdn: JDN, after_start: Nadika) -> ModernCivilInstant:
        start = self.day_bounds(jdn)[0]
        days = float(after_start.value) / NADIKAS_PER_DAY
        return self.civil_of_tt(start + FloatDays(days), jdn)

    # --- the protocol's positions ---------------------------------------------------------

    def _tt(self, instant: ModernCivilInstant) -> TT:
        tt = self.tt_of_civil(instant)
        self.check(tt)
        return tt

    def sidereal_longitude(
        self, body: str, instant: ModernCivilInstant
    ) -> SiderealLongitude[FloatArc]:
        return self.sidereal_at(body, self._tt(instant))

    def tropical_longitude(
        self, body: str, instant: ModernCivilInstant
    ) -> TropicalLongitude[TrueOfDate]:
        return self.tropical_at(body, self._tt(instant))

    def daily_motion(self, body: str, day: JDN) -> FloatArc:
        """The sidereal arc from this civil day's start to the next's, in (−180°, 180°]."""
        a = self.sidereal_at(body, self.day_bounds(day)[0])
        b = self.sidereal_at(body, self.day_bounds(day.plus_days(1))[0])
        d = (b - a).to(_DEG).value % 360
        return FloatArc(d - 360 if d > _HALF_CIRCLE else d, _DEG)

    def node(self, instant: ModernCivilInstant) -> SiderealLongitude[FloatArc]:
        return self.node_at(self._tt(instant))

    def latitude(self, body: str, instant: ModernCivilInstant) -> FloatArc:
        """The apparent ecliptic latitude of date (the true ecliptic)."""
        _lon, lat, _nut = self._true(body, self._tt(instant))
        return _deg(lat)

    def provenance(self) -> dict[str, Any]:
        c = self.config
        e = self.ephemeris.entry
        return {
            "engine": "modern",
            "kernel": {"id": e.id, "sha256": e.sha256, "source": e.source},
            "delta_t": self.delta_t.provenance(e.id),
            "precession": self.precession.provenance(),
            "nutation": self.nutation.provenance(),
            "ayanamsa": self.ayanamsa.provenance(),
            "observer_frame": c.observer_frame,
            "sunrise_event": c.sunrise_event.id,
            "node": c.node,
            "time_standard": self.standard.id,
            "civil_day_start": c.civil_day_start,
            "observer": {
                "id": self.observer.id,
                "latitude_deg": str(self.observer.latitude_deg),
                "longitude_deg": str(self.observer.longitude_deg),
                "height_m": str(self.observer.height_m),
            },
            "polar_motion": "not applied",
        }
