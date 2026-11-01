"""The day record: one civil day under one configuration.

:class:`Records` builds the ``DayRecord`` of a civil day from what the
configuration (``jyotirganita/config.py``) already computes, and nothing
else:

- the header: ``method_id``, ``method_status`` (the registry's, as the
  run's provenance states it), ``config_hash``, ``parameters_sha256`` (the
  digest of the method's data files, its era file and
  ``engine_parameters.yaml``, ``methods/compose.py``; under the geometric
  sunrise it does not cover the modern preset's kernel, ΔT and place
  files), ``numeric: exact | float``
  and ``conventions``;
- the calendar leaves of :meth:`Calendar.day` unchanged in content, their
  ``"num/den"`` strings parsed back to exact fractions (written by the
  canonical writer as ``{"exact": "num/den"}`` under ``numeric: exact``,
  as the nearest double under ``numeric: float``), the occurrence
  elements limited to the configuration's ``output.elements``;
- under the modern engine, ``tt`` and ``ut1`` on the ``sunrise`` and
  ``sunset`` leaves beside the civil form: the Julian dates of those
  instants on each scale, as shortest round-trip floats (the occurrence
  rows' instants are the engine's quantised nāḍikās from the day's
  start, whose TT is the sunrise's or the day start's plus that span, and
  carry no scale of their own);
- the ``planets`` leaf (:class:`Positions`, below);
- ``derived_ut`` and ``derived_tt`` when the caller asked for them
  (``io/derived.py``), the only float-bearing fields of an exact record;
- ``flags``: the calendar's, the configuration's ``diagnostic:<id>``, and
  ``provisional:derived_ut.time_reckoning`` where a derived field stands,
  sorted;
- ``provenance``: the configuration's, the derived
  chain's under ``derived`` where it ran, and an informational
  ``environment`` block that no comparison reads.

**The planets leaf** (:class:`Positions`), moved here from the search's
evaluator with its mathematics unchanged so that the record and the
search build it in one place: ``planets: {body: {sidereal_longitude,
latitude | not_modelled, daily_motion, retrograde}}`` for the Sun, the
Moon, Mercury, Venus, Mars, Jupiter, Saturn, Rāhu and Ketu, and
``planets.<body>: not_modelled`` for a body the method does not serve.
It is built from the engine protocol only (``core/engine.py``):
``sidereal_longitude(body, instant(jdn, Nadika(0)))`` at the civil day's
start (the frame's sunrise, the method's computation instant as the
engine realises it), ``daily_motion`` (the gati under a siddhantic
method, the arc between consecutive day starts under ``modern_de``),
``latitude`` where served, ``retrograde`` as the sign of the daily
motion. Rāhu is the engine's ascending node (``node``), Ketu the
descending node, the ascending node plus half a circle; the nodes' daily
motion is the signed arc between consecutive day starts.
:meth:`Positions.at` gives the same shape at any instant of a civil day
(the API's ``positions``).

No ``math``, ``numpy`` or ``decimal`` import: the record's exact path is
the engine's own fractions.
"""

from __future__ import annotations

import json
import platform
import sys
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from importlib import resources
from itertools import pairwise
from typing import TYPE_CHECKING, Any

from jyotirganita.calendar.day import NOT_MODELLED, OCCURRENCE_ELEMENTS
from jyotirganita.calendar.encodings import sexagesimal
from jyotirganita.calendar.months import MonthNotFound, MonthRuleNotModelled
from jyotirganita.core.memo import DayMemo
from jyotirganita.core.types import (
    JDN,
    AngleUnit,
    CivilInstant,
    FloatDays,
    ModernCivilInstant,
    Nadika,
    NotModelled,
    SiddhanticCivilInstant,
)
from jyotirganita.data import engine_parameters
from jyotirganita.data.time_standards import OutOfForce
from jyotirganita.errors import Refusal
from jyotirganita.io import jsonl
from jyotirganita.modern.timescales import OutOfRange
from jyotirganita.siddhantic.endings import truncate_at_asu
from jyotirganita.siddhantic.engine import LINEAR_GATI, EngineRefusal

if TYPE_CHECKING:
    from jyotirganita.config import RunConfig
    from jyotirganita.io.derived import DerivedChain

__all__ = [
    "BODIES",
    "NODES",
    "Positions",
    "Records",
    "Sweep",
    "dumps",
    "parsed_leaves",
    "record_schema",
    "sampled_sweep",
]

#: the bodies of the planets leaf, in the record's order
BODIES = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "rahu", "ketu")
NODES = ("rahu", "ketu")
CIRCLE = Fraction(360)
HALF = Fraction(180)
ROW_FRACTIONS = ("start", "end", "ends_nadika_after_sunrise")
#: the longitudes a day's records ask for at most: each body at two instants (core/memo.py)
LONGITUDES_PER_DAY = 2 * len(BODIES)
#: the equal steps into which a sweep divides a day whose motion is not linear in time
#: (Positions.sweep); structural: between samples the motion is taken as monotone, which
#: fails only at a station, and a station is found where the step's sign changes about a
#: sample and refined there, so the count only has to keep a body's stations (weeks
#: apart; the true node's, days) one to a step, which a quarter day does
SWEEP_SEGMENTS = 4
#: the ending-rounding procedure whose printed form the record writes beside the exact value
ENDING_TRUNCATE_AT_ASU = "rounding.ending_truncate_at_asu"
#: the flag every record carrying a derived field bears (no text states its reckoning)
RECKONING_FLAG = "provisional:derived_ut.time_reckoning"
#: the record's keys in schema order (io/record.schema.json lists the same)
HEADER = ("method_id", "method_status", "config_hash", "parameters_sha256", "numeric")


def _deg(arc: Any) -> Fraction:
    """An arc in degrees as an exact fraction (a float converts exactly)."""
    return Fraction(arc.to(AngleUnit.DEGREE).value) % CIRCLE


def signed(x: Fraction) -> Fraction:
    """An arc reduced into (−180°, 180°]."""
    r = x % CIRCLE
    return r - CIRCLE if r > HALF else r


@cache
def record_schema() -> Mapping[str, Any]:
    """``io/record.schema.json``, parsed (its ``properties`` order is the key order)."""
    text = resources.files("jyotirganita.io").joinpath("record.schema.json").read_text("utf-8")
    doc: Mapping[str, Any] = json.loads(text)
    return doc


def dumps(record: Mapping[str, Any]) -> str:
    """One record as a canonical JSON line (``io/jsonl.py``), without its ``\\n``."""
    return jsonl.dumps(record, str(record["numeric"]), record_schema())


@dataclass(frozen=True, slots=True)
class Sweep:
    """The arc a body's place covers through one civil day (:meth:`Positions.sweep`).

    Offsets in degrees from the body's place at the day's start, signed in
    the direction of increasing longitude: ``lo`` ≤ 0 ≤ ``hi`` bound the
    places the body takes at some instant of the day; ``end`` is the offset
    its motion reaches at the day's end, the next day's start, which belongs
    to the next day and so is not covered; ``hi_open`` says that ``hi`` is
    reached only there (a lower bound reached only there needs no mark: the
    places just above it lie in its span).
    """

    lo: Fraction
    hi: Fraction
    end: Fraction
    hi_open: bool

    @classmethod
    def chord(cls, end: Fraction) -> Sweep:
        """The sweep of a uniform motion by ``end`` over the day, its end not covered."""
        return cls(min(end, Fraction(0)), max(end, Fraction(0)), end, end > 0)


def sampled_sweep(
    lam: Fraction, at: Callable[[Fraction], Fraction], span: Fraction, resolution: Fraction
) -> Sweep:
    """The sweep of the path ``at`` over [0, ``span``), ``lam`` its place at 0.

    ``at`` gives the place (degrees) at a time after the day's start, in
    any unit, and is evaluated from one step before 0 to one step after
    ``span``; :data:`SWEEP_SEGMENTS` steps divide the span. The offsets are
    summed step by step, each step reduced into (−180°, 180°]. Where the
    step changes sign about a sample (a station), the extreme place between
    the neighbouring samples, within the day, is found by ternary search to
    ``resolution`` and counted (:meth:`Positions.sweep`).
    """
    k = SWEEP_SEGMENTS
    h = span / k
    ts = [h * i for i in range(-1, k + 2)]
    places = [lam if i == 1 else at(t) for i, t in enumerate(ts)]
    offs = [signed(places[0] - lam), Fraction(0)]
    for a, b in pairwise(places[1:]):
        offs.append(offs[-1] + signed(b - a))
    # covered: the samples from the start up to, not including, the end (index k + 1)
    covered = offs[1 : k + 1]
    for i in range(1, k + 2):
        before, after = offs[i] - offs[i - 1], offs[i + 1] - offs[i]
        if before * after < 0:
            lo, hi = max(ts[i - 1], Fraction(0)), min(ts[i + 1], span)
            covered.append(
                _extreme(at, offs[i], places[i], lo, hi, highest=before > 0, resolution=resolution)
            )
    end = offs[k + 1]
    top = max(covered)
    return Sweep(min(*covered, end), max(top, end), end, end > top)


def _extreme(
    at: Callable[[Fraction], Fraction],
    ref_off: Fraction,
    ref_place: Fraction,
    lo: Fraction,
    hi: Fraction,
    *,
    highest: bool,
    resolution: Fraction,
) -> Fraction:
    """The greatest (``highest``) or least offset of the path on (lo, hi), by ternary search.

    Only the places at the instants evaluated, all inside (lo, hi), are
    counted, so that a station beyond the day's end is never taken for one
    inside it.
    """
    sign = 1 if highest else -1
    found: list[Fraction] = []
    while not found or hi - lo > resolution:
        third = (hi - lo) / 3
        m1, m2 = lo + third, hi - third
        f1 = ref_off + signed(at(m1) - ref_place)
        f2 = ref_off + signed(at(m2) - ref_place)
        found += (f1, f2)
        if sign * f1 < sign * f2:
            lo = m1
        else:
            hi = m2
    return max(found) if highest else min(found)


# --- the planets leaf ----------------------------------------------------------------------


class Positions:
    """The ``planets`` leaf of a configuration's civil days (module docstring)."""

    def __init__(self, config: RunConfig) -> None:
        self.config = config
        self.engine = config.engine
        self.exact = config.numeric == "exact"
        caps = self.engine.capabilities
        self.bodies = tuple(b for b in caps.bodies) + (NODES if caps.node else ())
        self._lon: DayMemo[tuple[str, int, object], Fraction] = DayMemo(LONGITUDES_PER_DAY)
        self._motion: DayMemo[tuple[str, int, object], Fraction | None] = DayMemo(
            LONGITUDES_PER_DAY
        )
        self._sweep: DayMemo[tuple[str, int, object], Sweep] = DayMemo(LONGITUDES_PER_DAY)
        params = engine_parameters.load()
        # the width to which a station's extreme place is found: the engine's own root
        # resolution, in the sampled path's time unit (nāḍikās, or days under modern_de)
        self.resolution = params[
            "siddhantic.root_resolution" if config.kind == "siddhantic" else "modern.root.tolerance"
        ].value

    def out(self, x: Fraction | None) -> Any:
        """A value as the record writes it: exact, or the nearest double."""
        if x is None:
            return None
        return x if self.exact else float(x)

    def lon(self, body: str, jdn: JDN, position: object = True) -> Fraction:
        """The body's sidereal longitude at the start of civil day ``jdn`` (degrees, exact)."""
        key = (body, jdn.value, position)
        hit = self._lon.get(key)
        if hit is not None:
            return hit
        if position == "mean":
            self._check_mean(body)
        if body == "ketu":
            v = (self.lon("rahu", jdn, position) + HALF) % CIRCLE
        elif position == "mean":
            run = self.config.run
            planet = run.resolved.model.planets[body]
            v = Fraction(run.day(jdn).mean[planet.mean]) % CIRCLE
        else:
            inst = self.engine.instant(jdn, Nadika(0))
            arc = (
                self.engine.node(inst)
                if body == "rahu"
                else self.engine.sidereal_longitude(body, inst)
            )
            v = _deg(arc.arc)
        self._lon[key] = v
        return v

    def _check_mean(self, body: str) -> None:
        """Refuse a mean place the method does not serve, as the query does (F5b)."""
        c = self.config
        if c.kind != "siddhantic":
            raise Refusal(
                "position",
                f"position: mean is not served under {c.method_id}: the modern engine computes "
                "no mean longitude (state position: true)",
            )
        if body in NODES:
            raise Refusal("position", f"{body}: the node has one place: position: true")
        if body not in c.run.resolved.model.planets:
            raise Refusal("position", f"{c.method_id} keeps no mean place of {body!r}")

    def motion(self, body: str, jdn: JDN, position: object = True) -> Fraction | None:
        """The body's daily motion on ``jdn``: the engine's, or the signed step (node, mean)."""
        key = (body, jdn.value, position)
        if key in self._motion:
            return self._motion[key]
        out: Fraction | None
        if body in NODES or position == "mean":
            out = signed(self.lon(body, jdn.plus_days(1), position) - self.lon(body, jdn, position))
        else:
            m = self.engine.daily_motion(body, jdn)
            out = None if isinstance(m, NotModelled) else Fraction(m.to(AngleUnit.DEGREE).value)
        self._motion[key] = out
        return out

    def sweep(self, body: str, jdn: JDN, position: object = True) -> Sweep:
        """The arc the body's place covers through civil day ``jdn`` on the engine's own motion.

        The places are those :meth:`at` (the API's ``positions``) returns at
        the day's instants, from its start up to, not including, the next
        day's start, which belongs to the next day:

        - ``linear_gati`` (a siddhantic method's default): the day's chord,
          linear in time, over [0, min(*L*, 60)) nāḍikās after sunrise, *L*
          the day's computed length, the chord's own domain (the sliver beyond sixty nāḍikās belongs
          to the seam rule).
          The chord is read from the engine at half that span and doubled,
          exactly.
        - ``full_evaluation`` (diagnostic) over the same span, and the modern
          engine over the whole day: the place sampled at
          :data:`SWEEP_SEGMENTS` equal steps of the span (and one step beyond
          each end), the motion between samples taken as monotone; where the
          step changes sign about a sample (a station), the extreme place
          between its neighbours is found by ternary search to the engine's
          own root resolution (``siddhantic.root_resolution``,
          ``modern.root.tolerance``) and counted.
        - ``position: mean``: the mean longitude moves uniformly, from its
          place at this day's start to the next day's, that end not covered.

        Ketu's sweep is Rāhu's, half a circle round.
        """
        key = (body, jdn.value, position)
        hit = self._sweep.get(key)
        if hit is not None:
            return hit
        if body == "ketu":
            out = self.sweep("rahu", jdn, position)
        elif position == "mean":
            lam = self.lon(body, jdn, position)
            out = Sweep.chord(signed(self.lon(body, jdn.plus_days(1), position) - lam))
        elif self.config.kind == "siddhantic":
            out = self._siddhantic_sweep(body, jdn)
        else:
            out = self._modern_sweep(body, jdn)
        self._sweep[key] = out
        return out

    def _siddhantic_sweep(self, body: str, jdn: JDN) -> Sweep:
        eng = self.engine
        lam = self.lon(body, jdn)
        span = min(
            self.config.calendar.source.day(jdn).length.value,
            Fraction(eng.model.units.nadis_per_day),
        )
        if eng.intraday == LINEAR_GATI:
            inst = eng.instant(jdn, Nadika(span / 2))
            arc = eng.node(inst) if body == "rahu" else eng.sidereal_longitude(body, inst)
            return Sweep.chord(2 * signed(_deg(arc.arc) - lam))

        def at(t: Fraction) -> Fraction:
            node, true = eng.evaluate(jdn, Nadika(t))
            place: Fraction = (node if body == "rahu" else true[body]) % CIRCLE
            return place

        return sampled_sweep(lam, at, span, self.resolution)

    def _modern_sweep(self, body: str, jdn: JDN) -> Sweep:
        eng = self.engine
        start = eng.day_bounds(jdn)[0]
        span = Fraction((eng.day_bounds(jdn.plus_days(1))[0] - start).value)

        def at(t: Fraction) -> Fraction:
            tt = start + FloatDays(float(t))
            return _deg((eng.node_at(tt) if body == "rahu" else eng.sidereal_at(body, tt)).arc)

        return sampled_sweep(self.lon(body, jdn), at, span, self.resolution)

    def planets(self, jdn: JDN) -> dict[str, Any]:
        """The record's planets leaf for civil day ``jdn`` (module docstring)."""
        out: dict[str, Any] = {}
        inst = None
        for body in BODIES:
            if body not in self.bodies:
                out[body] = NOT_MODELLED
                continue
            lam = self.lon(body, jdn)
            mot = self.motion(body, jdn)
            lat: Any = NOT_MODELLED
            if body not in NODES:
                inst = inst or self.engine.instant(jdn, Nadika(0))
                la = self.engine.latitude(body, inst)
                if not isinstance(la, NotModelled):
                    lat = self.out(Fraction(la.to(AngleUnit.DEGREE).value))
            out[body] = {
                "sidereal_longitude": self.out(lam),
                "latitude": lat,
                "daily_motion": NOT_MODELLED if mot is None else self.out(mot),
                "retrograde": NOT_MODELLED if mot is None else mot < 0,
            }
        return out

    def at(self, instant: CivilInstant, bodies: Iterable[str]) -> dict[str, Any]:
        """The planets leaf's shape for ``bodies`` at ``instant`` (the API's ``positions``).

        The instant is the configuration's engine's own form:
        a :class:`SiddhanticCivilInstant` on the text's standard under a
        siddhantic method, a :class:`ModernCivilInstant` on the run's civil
        standard under ``modern_de``; any other is a hard error. The daily
        motion is the civil day's, as in the planets leaf.
        """
        asked = tuple(bodies)
        unknown = [b for b in asked if b not in self.bodies]
        if unknown or not asked:
            raise Refusal(
                "bodies",
                f"{unknown or 'none'}: {self.config.method_id} serves {list(self.bodies)}",
            )
        want = SiddhanticCivilInstant if self.config.kind == "siddhantic" else ModernCivilInstant
        if not isinstance(instant, want):
            raise Refusal(
                "instant",
                f"a {self.config.kind} configuration takes a {want.__name__}, "
                f"not a {type(instant).__name__}",
            )
        if instant.standard != self.engine.instant(instant.jdn, Nadika(0)).standard:
            raise Refusal(
                "instant",
                f"the instant is on {instant.standard}; the run's standard is "
                f"{self.engine.instant(instant.jdn, Nadika(0)).standard}",
            )
        if isinstance(instant, SiddhanticCivilInstant):
            length = self.config.calendar.source.day(instant.jdn).length
            if not (0 <= instant.nadika_after_sunrise.value < length.value):
                raise Refusal(
                    "instant",
                    f"{_nadika_text(instant.nadika_after_sunrise)} nāḍikās after sunrise is "
                    f"outside civil day {instant.jdn.value} (0 to {_nadika_text(length)}, "
                    "nāḍikā;vināḍikā,vipala truncated)",
                )
        out: dict[str, Any] = {}
        for body in asked:
            if body == "ketu":
                node = self.engine.node(instant)
                lam = (_deg(node.arc) + HALF) % CIRCLE
            elif body == "rahu":
                lam = _deg(self.engine.node(instant).arc)
            else:
                lam = _deg(self.engine.sidereal_longitude(body, instant).arc)
            mot = self.motion(body, instant.jdn)
            lat: Any = NOT_MODELLED
            if body not in NODES:
                la = self.engine.latitude(body, instant)
                if not isinstance(la, NotModelled):
                    lat = self.out(Fraction(la.to(AngleUnit.DEGREE).value))
            out[body] = {
                "sidereal_longitude": self.out(lam),
                "latitude": lat,
                "daily_motion": NOT_MODELLED if mot is None else self.out(mot),
                "retrograde": NOT_MODELLED if mot is None else mot < 0,
            }
        return out


# --- the calendar leaves, parsed -------------------------------------------------------------


def _fraction(v: Any) -> Any:
    if isinstance(v, str) and "/" in v:
        n, _, d = v.partition("/")
        if n.lstrip("-").isdigit() and d.isdigit():
            return Fraction(int(n), int(d))
    return v


def parsed_leaves(key: str, v: Any) -> Any:
    """A calendar leaf with its ``"num/den"`` strings parsed back to fractions."""
    if key in OCCURRENCE_ELEMENTS and isinstance(v, list):
        return [{k: (_fraction(x) if k in ROW_FRACTIONS else x) for k, x in r.items()} for r in v]
    if key == "day_length_nadika":
        return _fraction(v)
    if key in ("sunrise", "sunset") and isinstance(v, Mapping):
        return {k: _fraction(x) for k, x in v.items()}
    if key == "sankranti" and isinstance(v, Mapping):
        return {k: (_fraction(x) if k == "instant" else x) for k, x in v.items()}
    return v


# --- the record --------------------------------------------------------------------------------


def environment() -> dict[str, str]:
    """The informational environment block, read by no comparison."""
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": sys.platform,
        "machine": platform.machine(),
    }


def _nadika_text(n: Nadika) -> str:
    """``n`` as ``nāḍikā;vināḍikā,vipala``, truncated (a message's form)."""
    if n.value < 0:
        return str(n.value)
    whole, sixtieths = sexagesimal(n.value)
    vinadika, rest = sexagesimal(sixtieths)
    return f"{whole};{vinadika:02d},{int(rest):02d}"


@contextmanager
def serving(jdn: JDN, field: str = "date") -> Iterator[None]:
    """Refuse, naming the range, a day whose computation needs an instant outside it.

    A model's range error (:class:`~jyotirganita.modern.timescales.OutOfRange`:
    the kernel's, the ΔT model's) raised while a day inside ``runs_from`` …
    ``runs_to`` is computed becomes a :class:`~jyotirganita.errors.Refusal`
    (a hard error that names what bounds it, never a traceback).
    The day's elements look ahead (the node's motion to the next day, a
    month's end to its next saṅkrānti), so the last day a run serves lies
    before ``runs_to`` by as much as that look ahead needs, which depends on
    the day.

    The day's other refusals become :class:`~jyotirganita.errors.Refusal`
    the same way: the
    engine's refusal of a quantity (``EngineRefusal``, named by ``field``),
    a civil standard not in force on the day (``time_standard``), a day
    before the first month the run serves (``field``) and a month rule the
    day's sunrise and sunset do not serve (``month_rule``).
    """
    try:
        yield
    except OutOfRange as e:
        raise Refusal(
            field,
            f"JDN {jdn.value} cannot be served: its record needs an instant outside a "
            f"stated range ({e})",
        ) from None
    except OutOfForce as e:
        raise Refusal("time_standard", f"JDN {jdn.value} cannot be served: {e}") from None
    except MonthRuleNotModelled as e:
        raise Refusal("month_rule", f"JDN {jdn.value} cannot be served: {e}") from None
    except (EngineRefusal, MonthNotFound) as e:
        raise Refusal(field, f"JDN {jdn.value} cannot be served: {e}") from None


class Records:
    """The day records of one configuration (module docstring).

    ``derived`` is the derived chain the caller asked for, or ``None``;
    ``positions`` may be shared with a search over the same configuration.
    """

    def __init__(
        self,
        config: RunConfig,
        *,
        derived: DerivedChain | None = None,
        positions: Positions | None = None,
    ) -> None:
        self.config = config
        self.derived = derived
        self.positions = positions or Positions(config)
        prov: dict[str, Any] = dict(config.provenance())
        if derived is not None:
            prov["derived"] = derived.provenance()
        prov["environment"] = environment()
        self.provenance = prov
        self.ending_form = _ending_form(config)
        self.header = {
            "method_id": config.method_id,
            "method_status": str(config.run.provenance["method_status"]),
            "config_hash": config.config_hash,
            "parameters_sha256": str(config.run.provenance["parameters_sha256"]),
            "numeric": config.numeric,
        }

    def served(self, jdn: JDN) -> None:
        """Refuse a day before ``runs_from`` or after ``runs_to``, naming the bound."""
        c = self.config
        if jdn.days_since(c.runs_from) < 0:
            why = (
                "the text's own count does not exist before it"
                if c.kind == "siddhantic"
                else f"the run's first day ({c.run.engine.range_text()})"
            )
            raise Refusal(
                "date",
                f"JDN {jdn.value} is before {c.method_id}'s runs_from (JDN {c.runs_from.value}): "
                + why,
            )
        if c.runs_to is not None and c.runs_to.days_since(jdn) < 0:
            # a siddhantic run ends only where its geometric sunrise's modern run ends
            bound = (
                c.run.engine.range_text()
                if c.kind == "modern"
                else f"the modern run of procedure.sunrise={c.overrides['procedure.sunrise']}"
            )
            raise Refusal(
                "date",
                f"JDN {jdn.value} is after the run's last day (JDN {c.runs_to.value}; {bound})",
            )

    def _modern_scales(self, jdn: JDN, leaf: Any, which: int) -> Any:
        """The modern sunrise or sunset leaf with its TT and UT1 Julian dates beside it."""
        if not isinstance(leaf, Mapping):
            return leaf
        eng = self.config.engine
        tt = eng.day_bounds(jdn)[which]
        ut1 = eng.ut1_of(tt)
        return {
            **leaf,
            "tt": tt.jd_whole + tt.jd_fraction,
            "ut1": ut1.jd_whole + ut1.jd_fraction,
        }

    def record(self, jdn: JDN) -> dict[str, Any]:
        """The record of civil day ``jdn`` (module docstring).

        A day inside the run whose record needs an instant beyond it (near
        ``runs_to``: the node's next day, the month's next saṅkrānti) is
        refused naming the range (:func:`serving`).
        """
        self.served(jdn)
        with serving(jdn):
            return self._record(jdn)

    def _record(self, jdn: JDN) -> dict[str, Any]:
        c = self.config
        cal = c.calendar.day(jdn)
        leaves = {k: parsed_leaves(k, v) for k, v in cal.items()}
        out: dict[str, Any] = {**self.header, "method_id": leaves["method_id"]}
        out["conventions"] = leaves["conventions"]
        for k in ("dates", "weekday", "eras", "sunrise", "sunset", "day_length_nadika"):
            out[k] = leaves[k]
        if c.kind == "modern":
            out["sunrise"] = self._modern_scales(jdn, out["sunrise"], 1)
            out["sunset"] = self._modern_scales(jdn, out["sunset"], 2)
        flags = set(leaves["flags"]) | set(c.diagnostic)
        if self.derived is not None:
            out.update(self.derived.fields(jdn, cal_sunrise(leaves["sunrise"]), Nadika(0)))
            flags.add(RECKONING_FLAG)
        for e in OCCURRENCE_ELEMENTS:
            if e in c.elements:
                out[e] = [self._stated_row(r) for r in leaves[e]]
        out["masa"] = leaves["masa"]
        out["sankranti"] = leaves["sankranti"]
        out["planets"] = self.positions.planets(jdn)
        out["flags"] = sorted(flags)
        out["provenance"] = self.provenance
        return out

    def _stated_row(self, row: Mapping[str, Any]) -> Mapping[str, Any]:
        """An occurrence row with the text's own form beside each exact ending."""
        if self.ending_form is None:
            return row
        key, vinadikas, pranas = self.ending_form
        out = dict(row)
        for k in ROW_FRACTIONS:
            x = row.get(k)
            if isinstance(x, Fraction):
                parts = truncate_at_asu(Nadika(x), vinadikas, pranas)
                out[k] = jsonl.Stated(x, "nadika", tuple(parts), key)
        return out

    def dumps(self, jdn: JDN) -> str:
        """The canonical line of civil day ``jdn``."""
        return dumps(self.record(jdn))


def _ending_form(config: RunConfig) -> tuple[str, int, int] | None:
    """The ending-rounding datum's key and the text's units, where the text states the rule.

    An exact
    leaf carries the text's own form only where the text registers a
    rounding procedure for that quantity, and only by that procedure. The
    one such procedure the record's leaves meet is
    ``rounding.ending_truncate_at_asu`` (mahabhaskariya_1960 IV.31–32) on the occurrence
    rows' instants after sunrise; its units are the text's
    ``time_units.vinadikas_per_nadi`` and ``time_units.pranas_per_vinadika``.
    A text whose ``ending_rounding`` slot names another procedure (a
    deferral) gets ``exact`` only (``docs/data.md`` lists the leaves).
    """
    if config.kind != "siddhantic":
        return None
    resolved = config.run.resolved
    rec = resolved.procedures.get("ending_rounding")
    if rec is None or rec.raw.get("procedure") != ENDING_TRUNCATE_AT_ASU:
        return None
    data = resolved.data
    return (
        rec.key,
        data.integer("time_units.vinadikas_per_nadi"),
        data.integer("time_units.pranas_per_vinadika"),
    )


def cal_sunrise(leaf: Any) -> Nadika | None:
    """The siddhantic sunrise leaf's nāḍikās after local mean midnight, or ``None``."""
    if isinstance(leaf, Mapping) and "nadika_after_local_midnight" in leaf:
        v = leaf["nadika_after_local_midnight"]
        if isinstance(v, Fraction):
            return Nadika(v)
    return None
