"""Rational rates and table-driven corrections: the Dṛggaṇita (drgganita_1963 Part II).

A text of this kind states its mean motions as a guṇakāra and a hāraka
(revolutions in so many civil days, drgganita_1963 II.2–10), a drift of one unit of
arc in so many days, and a dhruva added to or subtracted from each mean
at the Kali epoch (II.12b–15a); the true positions come from tabulated
corrections (the jyā tables, II.26–42) by its own interpolation (II.44–45)
and its own application orders (II.19–24, II.43). Every step is a
registered procedure (:mod:`jyotirganita.siddhantic.procedures`) whose
datum states it; nothing here names a value.

The mean (``mean.guna_hara_drift``, ``mean.dhruva_signed``; drgganita_1963 II.11–12a,
"having set down the Kali day count, multiply by the guṇakāra, divide by
the hāraka: the quotient is the revolutions and the rest; after the
correction stated here is made, apply its own dhruva"): for a Kali day
count *A* the mean is the fractional part of *A*·guṇa/hāra revolutions,
plus *A*/*N* of the drift's unit (one unit in *N* days, its sign as the
verse states it, a constant correction to the rate),
plus the signed dhruva.

The true position (``table.*``, ``order.*``; drgganita_1963 II.19–25, II.43–45):

- the kendra is the body less its ucca (II.19); in the six signs from
  Meṣa the tabulated correction is subtracted, from Tulā added;
- the manda correction is read from the body's one manda table, the
  śīghra correction from its mṛgādi table when the kendra lies in the six
  signs from Makara and from its karkyādi table otherwise (II.25), each
  at the bhujā of the kendra;
- a table holds the correction at each multiple of its step; between two
  entries the value is the linear interpolation less (g/d)(e/d)·Δ²/q,
  *g* and *e* the kalās gone and to go in the step, Δ² the next step's
  difference less the current one, *d* and *q* the text's divisors
  (II.44–45, "the product of the gone and to-go parts, each divided by
  bhadra, multiplied by the difference of the differences, divided by
  nirmogha, is positive; negative where the next is greater"); in the
  last step, which has no next difference, the preceding pair's second
  difference serves (``table.last_step_preceding_difference``: the
  engine's fallback, no stated rule);
- the Sun and the Moon take the manda correction alone (II.43a); Mars,
  Jupiter and Saturn the four steps of II.20–21; Mercury and Venus, whose
  mean is the Sun's and whose own computed mean is the śīghrocca (II.18),
  the four steps of II.22–24;
- the node is the complement of the computed Rāhu, taken once (II.43b).

**The sunrise and the carry**, which the text defers to
earlier works (drgganita_1963 I.ii.7), are the Dṛk-school rules, each slot's datum
in ``procedures.yaml`` (goladipika_1916 the Goladīpikā, grahanamandana_1965 and golasara_1970 where
it is
silent; ``docs/methods/drgganita.md`` §I):

- the means are those of the mean Sun's rising on the unmaṇḍala at the
  samarekhā (goladipika_1916 v. 195; the computation instant, I.ii.6); the
  deśāntara (v. 196–198), the bhujāntara (v. 202–203) and the cara
  (v. 205–207) each move every mean element at its mean motion by a time
  (``carry.*_mean_elements``, ``carry.desantara_yojana``): −offset/60 of
  a day, the Sun's bhujāphala ÷ 21600 of a day, −cara ÷ 21600 of a day;
  the node, the complement of the computed Rāhu, is reversed by itself
  (grahanamandana_1965 śl. 22b); the record's means are the means so carried to the
  sunrise, on which the equations act;
- the bhujāphala is the Sun's manda correction from its table at the
  observer's mean sunrise; the cara the Āryabhaṭan rule the Goladīpikā
  states (v. 73–74, 78–79: the declination from the Rsine of the
  greatest declination v. 73a states, the day-radius, the earthsine, the
  arc in asus, a prāṇa a kalā), from the true Sun before the cara;
- the sunrise is a quarter day after local mean midnight moved by the
  bhujāntara and the cara, the sunset the sunrise plus twice the half-day
  (v. 109), as :mod:`jyotirganita.siddhantic.sunrise` computes them;
- the Rsines are the table of grahanamandana_1965 śl. 25A–B, the manuscripts' verses, read
  by linear interpolation (``trig.rsine_table_linear``, the fallback: no
  Dṛk page states one); the Dṛggaṇita states no table (the gap
  ``texts.drgganita.trig.rsine_table``), so every record carries
  ``provisional:texts.drgganita.trig.rsine_table`` (the owner's
  individual sign-off pending);
- the Moon's latitude is grahanamandana_1965 śl. 37's (``latitude.great_sine_moon``); the
  planets' is not modelled (goladipika_1916 v. 127–128 divide by hypotenuses the
  tables do not give).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction

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
from jyotirganita.siddhantic.endings import chord, sunrise_difference
from jyotirganita.siddhantic.engine import (
    BeforeRunsFrom,
    EngineRefusal,
    Observer,
    SunriseProvider,
    cara_at,
    hybrid_nadikas,
)
from jyotirganita.siddhantic.procedures import resolve
from jyotirganita.siddhantic.sunrise import (
    SunriseTimes,
    TimeUnits,
    day_radius,
    earthsine,
    rsine_declination,
    signed_rsine,
    sunrise_after_midnight,
)
from jyotirganita.siddhantic.tables import RsineTable
from jyotirganita.siddhantic.text import TextData

__all__ = [
    "DayUnits",
    "JyaTable",
    "RationalRate",
    "TableEngine",
    "TableModel",
    "bhuja",
    "mean_longitude_rational",
]

DEGREES_PER_REVOLUTION = 360
DEGREES_PER_HALF_ORBIT = 180
DEGREES_PER_QUADRANT = 90
MINUTES_PER_DEGREE = 60
NADIKAS_PER_DAY = 60
QUARTERS_PER_DAY = 4
FULL_EVALUATION = "diagnostic.full_evaluation"
LINEAR_GATI = "intraday.linear_gati"

#: arc units a datum's ``unit`` may name, in degrees
ARC_UNITS: Mapping[str, Fraction] = {
    "degrees": Fraction(1),
    "arcminutes": Fraction(1, MINUTES_PER_DEGREE),
    "arcseconds": Fraction(1, MINUTES_PER_DEGREE * MINUTES_PER_DEGREE),
}
#: a drift's unit: one unit of arc in so many days
DRIFT_UNITS: Mapping[str, Fraction] = {
    "days_per_arcminute": ARC_UNITS["arcminutes"],
    "days_per_arcsecond": ARC_UNITS["arcseconds"],
}

#: the procedure each slot must name for this engine
SUPPORTED: Mapping[str, str] = {
    "time_base": "ahargana.kali_dinagana",
    "mean_longitude": "mean.guna_hara_drift",
    "epoch_additive": "mean.dhruva_signed",
    "computation_instant": "computation_instant.dhruva_sunrise",
    "sighrocca": "sighrocca.sun_mean_or_own",
    "kendra": "table.kendra_body_less_ucca",
    "table_branch": "table.manda_one_sighra_two",
    "interpolation": "table.second_difference",
    "interpolation.last_step": "table.last_step_preceding_difference",
    "order.luminaries": "order.manda_only",
    "order.superior": "order.superior_drgganita",
    "order.inferior": "order.inferior_drgganita",
    "node_complement": "node.complement_once",
    # the Dṛk-school rules the text defers to (drgganita_1963 I.ii.7)
    "sunrise": "sunrise.mean_meridian_plus_carry",
    "carry.desantara": "carry.desantara_yojana",
    "carry.bhujantara": "carry.bhujantara_mean_elements",
    "carry.cara": "carry.cara_mean_elements",
    "declination": "declination.rsine_obliquity",
    "declination.argument": "declination_argument.svaniraksa_true_longitude",
    "ascensional_difference": "ascensional_difference.earthsine",
    "half_day": "half_day.quarter_day_plus_cara",
    "gati": "gati.sunrise_difference",
    "proportional_parts": "ending.proportional_parts",
    "intraday": LINEAR_GATI,
    "rsine": "trig.rsine_table_linear",
    "arc": "trig.arc_table_linear",
    "latitude": "latitude.great_sine_moon",
}
#: the slots whose rule no Dṛk page states: the engine's fallback (``basis:
#: fallback_no_stated_rule``)
FALLBACK_SLOTS = ("interpolation.last_step", "gati", "rsine", "arc")
#: the carry slots: each moves every mean element at its mean motion (goladipika_1916 v. 195–207)
CARRY_SLOTS = ("carry.desantara", "carry.bhujantara", "carry.cara")
CARRY = ("mean_before_equation", "mean", ("all_elements",))
MRGADI, KARKYADI, MANDA = "sighra_mrgadi", "sighra_karkyadi", "manda"
MOON = "moon"

_GUNA = re.compile(r"^part2\.([a-z_]+)\.guna$")
_ENTRY = re.compile(r"^table\.([a-z]+)\.([a-z_]+)\.e(\d\d)$")
#: the Rsine table the Dṛk line runs on (grahanamandana_1965 śl. 25A–B) and the gap it fills
_RSINE = re.compile(r"^trig\.rsine_table\.quoted\.([a-z0-9_]+)\.e(\d\d)$")
RSINE_GAP = "trig.rsine_table"
#: goladipika_1916 v. 73a: the Rsine of the greatest declination; v. 79a: a prāṇa is a kalā
RSIN_OBLIQUITY = "procedures.declination.verses.v073a.goladipika_1916.n1"
PRANA_KALA = "procedures.ascensional_difference.verses.v079a.goladipika_1916"
#: grahanamandana_1965 śl. 37: the Moon's latitude, its multiplier and divisor
MOON_LATITUDE = (
    "latitude.rule.moon.grahanamandana_1965.sl37a.n1",
    "latitude.rule.moon.grahanamandana_1965.sl37b.n1",
)


def _floor(x: Fraction) -> int:
    """The floor of an exact number (no ``math`` under ``siddhantic/``)."""
    return x.numerator // x.denominator


class TableRefusal(EngineRefusal):
    """A request the table-driven engine refuses with a hard error."""


@dataclass(frozen=True, slots=True)
class DayUnits:
    """The record's day: nāḍikās in a civil day (the record's unit)."""

    nadis_per_day: int


@dataclass(frozen=True, slots=True)
class RationalRate:
    """An element's mean motion as the text states it (drgganita_1963 II.2–15a).

    ``guna`` revolutions in ``hara`` days; ``drift_degrees_per_day`` the
    signed drift (one unit in *N* days); ``dhruva_degrees`` the signed
    dhruva at the Kali epoch.
    """

    element: str
    guna: int
    hara: int
    drift_degrees_per_day: Fraction
    dhruva_degrees: Fraction


def mean_longitude_rational(rate: RationalRate, days: Fraction) -> Fraction:
    """The mean in degrees after ``days`` Kali days, before any layer (drgganita_1963 II.11–12a).

    The quotient's whole revolutions are dropped (``bhagaṇādi``), the drift
    and the dhruva added with their signs; the result is not reduced.
    """
    revolutions = rate.guna * days / rate.hara
    part = revolutions - _floor(revolutions)
    return part * DEGREES_PER_REVOLUTION + rate.drift_degrees_per_day * days + rate.dhruva_degrees


def bhuja(kendra: Fraction) -> Fraction:
    """The bhujā (doḥ) of a kendra in degrees, 0 to 90 (the quadrant's arc gone or to go)."""
    k = kendra % DEGREES_PER_REVOLUTION
    if k <= DEGREES_PER_QUADRANT:
        return k
    if k <= DEGREES_PER_HALF_ORBIT:
        return DEGREES_PER_HALF_ORBIT - k
    if k <= DEGREES_PER_HALF_ORBIT + DEGREES_PER_QUADRANT:
        return k - DEGREES_PER_HALF_ORBIT
    return DEGREES_PER_REVOLUTION - k


@dataclass(frozen=True, slots=True)
class JyaTable:
    """One tabulated correction: its entries at each step of the bhujā (drgganita_1963 II.26–42).

    ``entries`` in degrees, the first at one ``step`` (the value at 0 is 0);
    ``arc_divisor`` and ``difference_divisor`` the divisors of II.44–45
    (bhadra, nirmogha), applied to the kalās gone and to go in the step;
    ``last_step`` the key of the datum the last step's second difference
    rests on (``basis: fallback_no_stated_rule``).
    """

    key: str
    entries: tuple[Fraction, ...]
    step_degrees: Fraction
    arc_divisor: Fraction
    difference_divisor: Fraction
    last_step: str

    def __post_init__(self) -> None:
        # the last step's fallback reads the pair before it: a table of one entry has none
        #
        if len(self.entries) < 2:
            raise TableRefusal(f"{self.key}: a table of {len(self.entries)} entries")

    def value(self, bhuja_degrees: Fraction) -> Fraction:
        """The correction at ``bhuja_degrees`` by II.44–45, in degrees (not signed)."""
        f = (Fraction(0), *self.entries)
        last = len(self.entries)
        if not 0 <= bhuja_degrees <= self.step_degrees * last:
            raise TableRefusal(f"{self.key}: bhujā {bhuja_degrees}° outside the table")
        seg = self.step_degrees * MINUTES_PER_DEGREE
        b = bhuja_degrees * MINUTES_PER_DEGREE
        n = _floor(b / seg)
        if n >= last:
            return f[last]
        gone = b - n * seg
        to_go = seg - gone
        current = f[n + 1] - f[n]
        if n + 2 <= last:
            second = (f[n + 2] - f[n + 1]) - current
        else:
            # the last step has no next difference: the preceding pair's, the engine's
            # fallback (self.last_step: procedures.interpolation.last_step, no stated rule)
            second = current - (f[n] - f[n - 1])
        linear = f[n] + current * gone / seg
        product = (gone / self.arc_divisor) * (to_go / self.arc_divisor)
        return linear - product * second / self.difference_divisor


@dataclass(frozen=True, slots=True)
class TableBody:
    """A body as the table-driven text computes it."""

    body: str
    mean: str  # the element whose mean is the body's
    mandocca: str | None  # a moving ucca element (the Moon's tuṅga)
    apogee: Fraction | None  # a fixed mandocca in degrees
    sighrocca: str | None
    order: str  # "order.luminaries" | "order.superior" | "order.inferior"


@dataclass(slots=True)
class TableModel:
    """A table-driven text's numbers, read once from its data."""

    text: str
    data: TextData
    procedures: Mapping[str, Record]
    rates: Mapping[str, RationalRate]
    tables: Mapping[tuple[str, str], JyaTable]
    planets: Mapping[str, TableBody]
    complemented: frozenset[str]
    node_element: str
    saka_to_kali_years: int
    units: DayUnits
    table: RsineTable
    rsin_obliquity: Fraction
    time: TimeUnits
    day_radius_resolution: Fraction
    moon_latitude: tuple[int, int]  # grahanamandana_1965 śl. 37: multiplier, divisor
    flags: tuple[str, ...] = field(default=())

    @property
    def revolutions(self) -> Mapping[str, int]:
        """Each element's guṇakāra (revolutions in its hāraka's days)."""
        return {e: r.guna for e, r in self.rates.items()}

    @classmethod
    def build(
        cls,
        data: TextData,
        procedures: Mapping[str, Record],
        day_radius_resolution: Fraction,
    ) -> TableModel:
        """Read the model; ``procedures`` maps each slot to its datum (the registry's)."""
        for slot, expected in SUPPORTED.items():
            rec = _named(data, procedures, slot)
            if rec.raw["procedure"] != expected:
                raise TableRefusal(
                    f"{rec.key}: procedure {rec.raw['procedure']} for {slot!r} is not one "
                    f"this engine runs ({expected})"
                )
        for slot in FALLBACK_SLOTS:
            rec = procedures[slot]
            if rec.raw.get("basis") != "fallback_no_stated_rule":
                raise TableRefusal(f"{rec.key}: {slot} is the engine's fallback, no stated rule")
        for slot in CARRY_SLOTS:
            rec = procedures[slot]
            got = (
                rec.raw.get("acts_on"),
                rec.raw.get("motion"),
                tuple(rec.raw.get("applies_to", ())),
            )
            if got != CARRY:
                raise TableRefusal(
                    f"{rec.key}: {slot} is run on every mean element at mean motion "
                    f"(acts_on, motion, applies_to {CARRY}), not {got}"
                )
        suffixes = sorted(k.removeprefix(data.prefix) for k in data._records)
        rates: dict[str, RationalRate] = {}
        for s in suffixes:
            m = _GUNA.match(s)
            if m:
                rates[m.group(1)] = _rate(data, m.group(1))
        div_arc = data.fraction("procedures.interpolation.divisor_arc")
        div_diff = data.fraction("procedures.interpolation.divisor_diff")
        last_step = _named(data, procedures, "interpolation.last_step")
        if last_step.raw.get("basis") != "fallback_no_stated_rule":
            raise TableRefusal(f"{last_step.key}: the last step's rule is the engine's fallback")
        step_unit = ARC_UNITS.get(str(data.record("table.step").raw.get("unit")))
        if step_unit is None:  # release review item 3
            raise TableRefusal(f"{data.key('table.step')}: the step names its arc unit")
        step = data.fraction("table.step") * step_unit
        entries: dict[tuple[str, str], dict[int, Fraction]] = {}
        for s in suffixes:
            m = _ENTRY.match(s)
            if m:
                rec = data.record(s)
                unit = ARC_UNITS.get(str(rec.raw.get("unit")))
                if unit is None:
                    raise TableRefusal(f"{rec.key}: a table entry names its arc unit")
                entries.setdefault((m.group(1), m.group(2)), {})[int(m.group(3))] = (
                    data.fraction(s) * unit
                )
        if not (step > 0 and div_arc > 0 and div_diff > 0):
            raise TableRefusal(f"{data.key('table.step')}: a step or divisor not positive")
        tables: dict[tuple[str, str], JyaTable] = {}
        for (body, kind), es in sorted(entries.items()):
            if sorted(es) != list(range(1, len(es) + 1)):
                raise TableRefusal(f"table {body}.{kind}: entries not numbered 1…{len(es)}")
            # a table runs over the quadrant of the bhujā
            if step * len(es) != DEGREES_PER_QUADRANT:
                raise TableRefusal(
                    f"table {body}.{kind}: {len(es)} entries of {step}° do not span a quadrant"
                )
            tables[(body, kind)] = JyaTable(
                data.key(f"table.{body}.{kind}"),
                tuple(es[i] for i in sorted(es)),
                step,
                div_arc,
                div_diff,
                last_step.key,
            )
        orders = {
            slot: frozenset(str(b) for b in procedures[slot].raw.get("applies_to", ()))
            for slot in ("order.luminaries", "order.superior", "order.inferior")
        }
        planets: dict[str, TableBody] = {}
        sun = "sun"
        for slot, bodies in orders.items():
            for body in sorted(bodies):
                if body in planets:
                    raise TableRefusal(f"{procedures[slot].key}: {body} is in two orders")
                if (body, MANDA) not in tables:
                    raise TableRefusal(f"{procedures[slot].key}: {body} has no manda table")
                planets[body] = _body(data, body, slot, rates, tables, sun)
        complement = procedures["node_complement"]
        complemented = frozenset(str(b) for b in complement.raw.get("applies_to", ()))
        if len(complemented) != 1 or not complemented <= set(rates):
            raise TableRefusal(f"{complement.key}: applies_to names the one node element")
        (node,) = complemented
        rsine, gap = _rsine_table(data, suffixes)
        # goladipika_1916 v. 79: the asus of a day are the minutes of a circle
        data.record(PRANA_KALA)
        time = TimeUnits(
            NADIKAS_PER_DAY, DEGREES_PER_REVOLUTION * MINUTES_PER_DEGREE // NADIKAS_PER_DAY
        )
        return cls(
            data.text,
            data,
            procedures,
            rates,
            tables,
            dict(sorted(planets.items())),
            complemented,
            node,
            data.integer("part1.ahargana.n1"),
            DayUnits(NADIKAS_PER_DAY),
            rsine,
            Fraction(data.integer(RSIN_OBLIQUITY)),
            time,
            day_radius_resolution,
            (data.integer(MOON_LATITUDE[0]), data.integer(MOON_LATITUDE[1])),
            (f"provisional:{gap}",),
        )

    def phala(self, body: str, kind: str, kendra: Fraction) -> Fraction:
        """The signed correction in degrees for ``kendra`` (II.19, II.25, II.44–45)."""
        k = kendra % DEGREES_PER_REVOLUTION
        if kind not in (MANDA, "sighra"):
            raise TableRefusal(f"{self.text}: no correction kind {kind!r}")
        if kind != MANDA:
            near = k >= DEGREES_PER_HALF_ORBIT + DEGREES_PER_QUADRANT or k < DEGREES_PER_QUADRANT
            kind = MRGADI if near else KARKYADI
        table = self.tables.get((body, kind))
        if table is None:
            raise TableRefusal(f"{self.text}: no {kind} table for {body}")
        v = table.value(bhuja(k))
        # II.19: subtractive in the six signs from Meṣa, additive from Tulā
        return -v if k < DEGREES_PER_HALF_ORBIT else v

    def true(self, p: TableBody, mean: Mapping[str, Fraction]) -> Fraction:
        """The body's true longitude (II.20–24, II.43a), not reduced."""
        p0 = mean[p.mean]
        ucca = mean[p.mandocca] if p.mandocca else p.apogee
        assert ucca is not None
        if p.order == "order.luminaries":
            return p0 + self.phala(p.body, MANDA, p0 - ucca)
        assert p.sighrocca is not None
        s = mean[p.sighrocca]
        if p.order == "order.superior":
            # II.20–21: half manda on the mean; half śīghra on that; the whole manda
            # from that on the mean; the whole śīghra from that on the manda-corrected mean
            p1 = p0 + self.phala(p.body, MANDA, p0 - ucca) / 2
            p2 = p1 + self.phala(p.body, "sighra", p1 - s) / 2
            p3 = p0 + self.phala(p.body, MANDA, p2 - ucca)
            return p3 + self.phala(p.body, "sighra", p3 - s)
        if p.order != "order.inferior":
            raise TableRefusal(f"{self.text}: no order {p.order!r} for {p.body}")
        # II.22–24: half śīghra on the mean; from that half manda on the mean; from that the
        # whole śīghra on the mere mean; from that the whole manda on the śīghra-corrected one
        p1 = p0 + self.phala(p.body, "sighra", p0 - s) / 2
        p2 = p0 + self.phala(p.body, MANDA, p1 - ucca) / 2
        p3 = p0 + self.phala(p.body, "sighra", p2 - s)
        return p3 + self.phala(p.body, MANDA, p3 - ucca)


def _rsine_table(data: TextData, suffixes: list[str]) -> tuple[RsineTable, str]:
    """The Rsine table of grahanamandana_1965 śl. 25A–B and the key of the gap it fills.

    The Dṛggaṇita states no table (``texts.drgganita.trig.rsine_table``, a
    gap); the Dṛk line runs on the one grahanamandana_1965's manuscripts carry, numbered
    e01… in printed order, its interval the quadrant over their count.
    """
    gap = data.key(RSINE_GAP)
    rec = data._records.get(gap)
    if rec is None or rec.kind != "gap":
        raise TableRefusal(f"{gap}: the table fills this gap, which must be recorded")
    entries: dict[int, int] = {}
    witnesses: set[str] = set()
    for s in suffixes:
        m = _RSINE.match(s)
        if m:
            # one witness's table (grahanamandana_1965), never entries mixed from two
            witnesses.add(m.group(1))
            if len(witnesses) > 1:
                raise TableRefusal(f"{gap}: entries from witnesses {sorted(witnesses)}")
            entries[int(m.group(2))] = data.integer(s)
    if not entries or sorted(entries) != list(range(1, len(entries) + 1)):
        raise TableRefusal(f"{gap}: the Rsine table's entries are not numbered 1…{len(entries)}")
    try:
        table = RsineTable.of_sines([entries[i] for i in sorted(entries)])
    except ValueError as e:
        raise TableRefusal(f"{gap}: {e}") from None
    return table, gap


def _named(data: TextData, procedures: Mapping[str, Record], slot: str) -> Record:
    rec = procedures.get(slot)
    if rec is None:
        raise TableRefusal(f"{data.text}: no procedure datum for slot {slot!r}")
    name = rec.raw.get("procedure")
    if not isinstance(name, str):
        raise TableRefusal(f"{rec.key}: the datum names no procedure")
    resolve(name, slot)
    data.mark_used(rec)
    return rec


def _arc(data: TextData, suffix: str) -> Fraction:
    rec = data.record(suffix)
    unit = ARC_UNITS.get(str(rec.raw.get("unit")))
    if unit is None:
        raise TableRefusal(f"{rec.key}: unit {rec.raw.get('unit')!r} is not an arc unit")
    return data.fraction(suffix) * unit


def _rate(data: TextData, element: str) -> RationalRate:
    drift = data.record(f"part2.{element}.drift")
    per = DRIFT_UNITS.get(str(drift.raw.get("unit")))
    if per is None:
        raise TableRefusal(f"{drift.key}: a drift is one unit of arc in so many days")
    days = data.integer(f"part2.{element}.drift")  # signed by the verse's sense
    if days == 0:
        raise TableRefusal(f"{drift.key}: a drift of one unit in 0 days")
    data.record(f"part2.{element}.drift.sense")
    # a rate is revolutions in civil days
    for part, unit in (("guna", "revolutions"), ("hara", "civil_days")):
        rec = data.record(f"part2.{element}.{part}")
        if rec.raw.get("unit") != unit:
            raise TableRefusal(f"{rec.key}: the {part} is in {unit}, not {rec.raw.get('unit')}")
    return RationalRate(
        element,
        data.integer(f"part2.{element}.guna"),
        data.integer(f"part2.{element}.hara"),
        per / days,
        _arc(data, f"part2.{element}.dhruva"),
    )


def _body(
    data: TextData,
    body: str,
    slot: str,
    rates: Mapping[str, RationalRate],
    tables: Mapping[tuple[str, str], JyaTable],
    sun: str,
) -> TableBody:
    moving = f"{body}_apogee" if f"{body}_apogee" in rates else None
    apogee = None if moving else _arc(data, f"part2.{body}.mandocca")
    if slot == "order.luminaries":
        if body not in rates:
            raise TableRefusal(f"{data.key(body)}: a luminary needs its own rate")
        return TableBody(body, body, moving, apogee, None, slot)
    for kind in (MRGADI, KARKYADI):
        if (body, kind) not in tables:
            raise TableRefusal(f"{data.key(body)}: no {kind} table")
    if body not in rates:
        raise TableRefusal(f"{data.key(body)}: no rate")
    if slot == "order.superior":
        # II.18: the mean Sun is the śīghrocca of Mars, Saturn and Jupiter
        return TableBody(body, body, moving, apogee, sun, slot)
    # II.18: of Venus and Mercury the own mean is the śīghrocca, the mean is the Sun's
    return TableBody(body, sun, moving, apogee, body, slot)


@dataclass(frozen=True, slots=True)
class TableDay:
    """One civil day's positions at the computation instant, with the flags raised.

    The fields of :class:`jyotirganita.siddhantic.engine.DayPositions`:
    ``mean`` and ``true`` at the text's sunrise (the means carried by the
    deśāntara, the bhujāntara and the cara, goladipika_1916 v. 195); under the hybrid
    alternative at the provider's sunrise, with the provider's ``sunset``
    and ``terms`` ``None``.
    """

    jdn: JDN
    ahargana: Ahargana
    completed_years: int
    layer_counts: Mapping[str, int]  # empty: the text runs no layer
    mean: Mapping[str, Fraction]
    true: Mapping[str, Fraction]
    node: Fraction
    flags: tuple[str, ...]
    sunrise: Nadika
    sunset: Nadika | None
    terms: TableTerms | None = None


@dataclass(frozen=True, slots=True)
class TableTerms:
    """A day's sunrise terms: the Sun's bhujāphala, its declination, the cara, the times.

    ``shift_days`` is the time from the computation instant (the mean Sun's
    rising at the samarekhā, goladipika_1916 v. 195) to the text's sunrise at the
    observer, at which the means are taken: the deśāntara, the bhujāntara
    and the cara together (goladipika_1916 v. 196–207).
    """

    bhujaphala_minutes: Fraction
    rsin_declination: Fraction
    cara_asus: Fraction
    times: SunriseTimes
    shift_days: Fraction


class TableEngine:
    """The engine protocol for a table-driven text and one observer (no layer).

    The observer's meridian offset and latitude are carried by the Dṛk-school
    rules (module docstring); a place reaches the text by its route.
    """

    def __init__(
        self,
        model: TableModel,
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
        latitude = observer.latitude_degrees
        if abs(latitude) >= DEGREES_PER_QUADRANT:
            raise EngineRefusal(f"observer {observer.id}: latitude {latitude}° is not a place")
        if sunrise_provider is not None and hybrid_quantum is None:
            raise EngineRefusal("a hybrid sunrise needs siddhantic.hybrid_sunrise_quantum")
        if intraday not in (LINEAR_GATI, FULL_EVALUATION):
            raise EngineRefusal(f"intraday model {intraday!r}: {LINEAR_GATI} or {FULL_EVALUATION}")
        self.model = model
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
        data_flags = {f for r in model.data.used.values() for f in r.flags} | set(model.flags)
        hybrid = {"hybrid_sunrise:modern_geometric"} if sunrise_provider is not None else set()
        diagnostic = {f"diagnostic:{FULL_EVALUATION}"} if intraday == FULL_EVALUATION else set()
        place = set(observer.flags_for(model.text))
        self._flags = tuple(sorted(data_flags | place | hybrid | diagnostic))
        self._memo: DayMemo[int, TableDay] = DayMemo()
        self._terms_memo: DayMemo[int, TableTerms] = DayMemo()

    # --- the protocol -----------------------------------------------------------

    @property
    def time_base(self) -> type:
        return Ahargana

    @property
    def capabilities(self) -> Capabilities:
        no_latitude = {
            f"latitude.{b}": "the Sun has no latitude"
            if b == "sun"
            else "goladipika_1916 v. 127–128 divide by the manda and śīghra hypotenuses, which the "
            "Dṛggaṇita's tables do not give (texts.drgganita.latitude.rule)"
            for b in self.model.planets
            if b != MOON
        }
        return Capabilities(
            bodies=tuple(self.model.planets),
            node=True,
            not_modelled={
                **no_latitude,
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
            raise TableRefusal(f"{self.model.text} serves no body {body!r}")
        return self._longitude(self._position(body, instant))

    def tropical_longitude(
        self, body: str, instant: SiddhanticCivilInstant
    ) -> TropicalLongitude[TrueOfDate] | NotModelled:
        return NOT_MODELLED

    def daily_motion(self, body: str, day: JDN) -> ExactArc | NotModelled:
        if body not in self.model.planets:
            raise TableRefusal(f"{self.model.text} serves no body {body!r}")
        return ExactArc(self.gati(body, day), AngleUnit.DEGREE)

    def node(self, instant: SiddhanticCivilInstant) -> SiderealLongitude[ExactArc]:
        return self._longitude(self._position(None, instant))

    def latitude(self, body: str, instant: SiddhanticCivilInstant) -> ExactArc | NotModelled:
        """The Moon's latitude at ``instant`` in degrees, north positive (grahanamandana_1965 śl.
        37–38).

        The Great Sine of the Moon less the node, times the verse's
        multiplier, divided by its divisor, in minutes; north while the
        difference lies in the six signs from Meṣa. The other bodies' is not
        modelled (``capabilities``).
        """
        if body not in self.model.planets:
            raise TableRefusal(f"{self.model.text} serves no body {body!r}")
        if body != MOON:
            return NOT_MODELLED
        arg = (self._position(MOON, instant) - self._position(None, instant)) % (
            DEGREES_PER_REVOLUTION
        )
        multiplier, divisor = self.model.moon_latitude
        minutes = self.model.table.rsine(bhuja(arg) * MINUTES_PER_DEGREE) * multiplier / divisor
        if arg >= DEGREES_PER_HALF_ORBIT:
            minutes = -minutes
        return ExactArc(minutes / MINUTES_PER_DEGREE, AngleUnit.DEGREE)

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
        if instant.standard != self.standard:
            raise TableRefusal(f"instant of {instant.standard}, engine of {self.standard}")
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
        """The body's daily motion on ``jdn``: tomorrow's longitude less today's."""
        return sunrise_difference(self.day(jdn).true[body], self.day(jdn.plus_days(1)).true[body])

    def node_gati(self, jdn: JDN) -> Fraction:
        """The node's daily motion on ``jdn``, the same difference."""
        return sunrise_difference(self.day(jdn).node, self.day(jdn.plus_days(1)).node)

    def day_length(self, jdn: JDN) -> Nadika:
        """The interval from this sunrise to the next (``day_length_nadika``)."""
        nadis = Nadika(self.model.units.nadis_per_day)
        return nadis + self.day(jdn.plus_days(1)).sunrise - self.day(jdn).sunrise

    def _mean_sunrise(self) -> Nadika:
        return Nadika(Fraction(self.model.units.nadis_per_day, QUARTERS_PER_DAY))

    def _desantara_days(self) -> Fraction:
        """The deśāntara as a time in days: the offset east in ghaṭīs, subtracted (goladipika_1916
        v. 196)."""
        return -self.observer.meridian_offset_ghatis / self.model.units.nadis_per_day

    def _hybrid(self, jdn: JDN) -> tuple[Nadika, Fraction]:
        """A hybrid provider's sunrise, quantised, and the shift of the means to it.

        The means are carried at mean motion from the computation instant by
        the deśāntara and the provider's sunrise less the mean sunrise, as the Āryabhaṭan engine
        carries them.
        """
        assert self.sunrise_provider is not None and self.hybrid_quantum is not None
        f = self.sunrise_provider.sunrise_fraction(jdn, self.observer)
        q = round_to(Fraction(f), self.hybrid_quantum, Rounding.HALF_EVEN)
        nadis = self.model.units.nadis_per_day
        after = Nadika(q * nadis)
        shift = self._desantara_days() + (after.value - self._mean_sunrise().value) / nadis
        return after, shift

    def _means_at(self, jdn: JDN, days: Fraction) -> dict[str, Fraction]:
        """Every mean element ``days`` after the computation instant of ``jdn`` (reduced)."""
        m = self.model
        a = Fraction(ahargana_of_day(m.text, self.epoch, jdn).day)
        return {
            e: mean_longitude_rational(r, a + days) % DEGREES_PER_REVOLUTION
            for e, r in m.rates.items()
        }

    def _bhujaphala_minutes(self, mean: Mapping[str, Fraction]) -> Fraction:
        """The Sun's signed bhujāphala in minutes, its manda correction (goladipika_1916 v. 202)."""
        m = self.model
        sun = m.planets["sun"]
        ucca = mean[sun.mandocca] if sun.mandocca else sun.apogee
        assert ucca is not None
        return m.phala("sun", MANDA, mean[sun.mean] - ucca) * MINUTES_PER_DEGREE

    def _terms(self, jdn: JDN) -> TableTerms:
        """The day's sunrise terms (goladipika_1916 v. 73–74, 78–79, 109, 195–207).

        The bhujāphala from the means at the observer's mean sunrise; the
        declination and the cara from the true Sun before the cara (the
        deśāntara and the bhujāntara applied; goladipika_1916 v. 73a ``sphuṭa``, no ayana).
        """
        memo = self._terms_memo.get(jdn.value)
        if memo is not None:
            return memo
        m = self.model
        d = self._desantara_days()
        bhujaphala = self._bhujaphala_minutes(self._means_at(jdn, d))
        b = bhujaphala / m.time.asus_per_day
        sun = m.true(m.planets["sun"], self._means_at(jdn, d + b))
        rsin_d = rsine_declination(m.table, m.rsin_obliquity, sun % DEGREES_PER_REVOLUTION)
        radius = day_radius(m.table, rsin_d, m.day_radius_resolution)
        e = earthsine(self._rsin_latitude, self._rcos_latitude, rsin_d)
        cara = cara_at(self.observer, jdn, m.table, e, radius)
        times = sunrise_after_midnight(bhujaphala, cara, m.time)
        out = TableTerms(
            bhujaphala, rsin_d, cara, times, d + times.bhujantara_days + times.cara_days
        )
        self._terms_memo[jdn.value] = out
        return out

    def _shift(self, jdn: JDN) -> Fraction:
        """The time from the computation instant at which the day's means are taken."""
        if self.sunrise_provider is not None:
            return self._hybrid(jdn)[1]
        return self._terms(jdn).shift_days

    def _positions(self, mean: Mapping[str, Fraction]) -> tuple[Fraction, dict[str, Fraction]]:
        m = self.model
        true = {b: m.true(p, mean) % DEGREES_PER_REVOLUTION for b, p in m.planets.items()}
        # II.43b: the Rāhu subtracted from a circle is the true node, once
        node = (DEGREES_PER_REVOLUTION - mean[m.node_element]) % DEGREES_PER_REVOLUTION
        return node, true

    def day(self, jdn: JDN) -> TableDay:
        """Every body's mean and true position at the text's sunrise of civil day ``jdn``."""
        self._check_runs_from(jdn)
        memo = self._memo.get(jdn.value)
        if memo is not None:
            return memo
        m = self.model
        ahargana = ahargana_of_day(m.text, self.epoch, jdn)
        a = Fraction(ahargana.day)
        sun = m.rates["sun"]
        years = _floor(mean_longitude_rational(sun, a) / DEGREES_PER_REVOLUTION) + _floor(
            sun.guna * a / sun.hara
        )
        terms: TableTerms | None = None
        sunset: Nadika | None = None
        if self.sunrise_provider is not None:
            sunrise, shift = self._hybrid(jdn)
            assert self.hybrid_quantum is not None
            sunset = hybrid_nadikas(
                self.sunrise_provider.sunset_fraction(jdn, self.observer),
                self.hybrid_quantum,
                self.model.units.nadis_per_day,
            )
        else:
            terms = self._terms(jdn)
            sunrise, sunset = terms.times.sunrise, terms.times.sunset
            shift = terms.shift_days
        mean = self._means_at(jdn, shift)
        # the means carried to the sunrise (goladipika_1916 v. 195: the corrections from the
        # deśāntara
        # on act on the means), and the true positions from them
        node, true = self._positions(mean)
        out = TableDay(
            jdn, ahargana, years, {}, mean, true, node, self._flags, sunrise, sunset, terms
        )
        self._memo[jdn.value] = out
        return out

    def _evaluate(self, jdn: JDN, extra_days: Fraction) -> tuple[Fraction, dict[str, Fraction]]:
        """The full evaluation at a fractional day (diagnostic).

        The means are advanced at mean motion by ``extra_days`` beyond the
        day's sunrise; the carry is that of the sunrise.
        """
        return self._positions(self._means_at(jdn, self._shift(jdn) + extra_days))

    def evaluate(self, jdn: JDN, n: Nadika) -> tuple[Fraction, dict[str, Fraction]]:
        """The full evaluation *n* nāḍikās after sunrise ``jdn`` (any *n*; diagnostic).

        An *n* that reaches before the epoch's sunrise is refused as the day
        before it is; the two sunrises are compared
        with their own shifts, not as whole days apart.
        """
        self._check_runs_from(jdn)
        days = n.value / self.model.units.nadis_per_day
        if jdn.days_since(self.epoch) + self._shift(jdn) + days < self._shift(self.epoch):
            raise BeforeRunsFrom(
                f"{n.value} nāḍikās after the sunrise of JDN {jdn.value} is before runs_from "
                f"(JDN {self.epoch.value}) of {self.model.text}"
            )
        return self._evaluate(jdn, days)
