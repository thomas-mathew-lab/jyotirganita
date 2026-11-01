"""The Python API: one constructor and six functions.

::

    from jyotirganita import open_config, generate
    config = open_config(repo, "parahita_kerala", "kerala/kozhikode")
    for record in generate(config, JDN(2434972), JDN(2435336)):
        ...

- :func:`open_config` — a preset resolved at its observer, with its run,
  its calendar and its ``--set`` overrides (``jyotirganita/config.py``);
  the search takes the same object.
- :func:`generate` — the day records of a window, first to last
  inclusive, in JDN order, streamed (``io/record.py``).
- :func:`day` — the record of one tagged date.
- :func:`positions` — the ``planets`` leaf's shape for the named bodies at
  a :data:`~jyotirganita.core.types.CivilInstant` of the configuration's
  engine; a body outside ``capabilities.bodies`` is a hard error naming
  the bodies served.
- :func:`sankrantis` — the saṅkrānti instants of a window from the
  calendar's month stream, each with the rāśi entered and the first day
  the configuration's month rule assigns (exact under a siddhantic
  method).
- :func:`eclipses` — modern only: the lunar and solar eclipses whose
  greatest instant falls in the window, at the observer
  (``modern/eclipses.py``), every result flagged ``provisional:eclipse``
  (no published eclipse canon compared yet); a hard error under a siddhantic configuration,
  naming the capability.
- :func:`search` — the inverse search, kept here for this module's
  callers; the top-level package does not re-export it, because
  ``jyotirganita.search`` names its subpackage: use
  ``from jyotirganita.search import open_search, search``.

Every result carries the provenance block. A day before
``runs_from`` is a hard error naming it; a day before the
composition date is served and flagged ``before_composition:<id>``.
Every refusal is a :class:`~jyotirganita.errors.Refusal` naming the field.
The derived placements of :mod:`jyotirganita.io.derived` are asked for
with ``derived_ut`` and ``derived_tt`` (``generate``, ``day``,
``positions``); they are never part of the configuration hash.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from fractions import Fraction
from typing import Any, cast

from jyotirganita.config import RunConfig, open_config
from jyotirganita.core.types import (
    JDN,
    CivilInstant,
    ModernCivilInstant,
    SiddhanticCivilInstant,
)
from jyotirganita.errors import Refusal
from jyotirganita.io import jsonl
from jyotirganita.io.dates import TaggedDate, date_record, jdn_of
from jyotirganita.io.derived import derived_chain
from jyotirganita.io.record import Records, record_schema, serving
from jyotirganita.search import search

__all__ = [
    "day",
    "dumps",
    "eclipses",
    "generate",
    "open_config",
    "positions",
    "records",
    "sankrantis",
    "search",
]

ECLIPSE_FLAG = "provisional:eclipse"
#: the result kinds other than the day record, with their key order
_ORDER: Mapping[str, tuple[str, ...]] = {
    "positions": (
        "kind",
        "method_id",
        "config_hash",
        "numeric",
        "instant",
        "planets",
        "derived_ut",
        "derived_tt",
        "flags",
        "provenance",
    ),
    "sankranti": (
        "kind",
        "method_id",
        "config_hash",
        "numeric",
        "dates",
        "rasi_index",
        "instant",
        "assigned_day1",
        "flags",
        "provenance",
    ),
    "eclipse": (
        "kind",
        "method_id",
        "config_hash",
        "numeric",
        "dates",
        "eclipse",
        "flags",
        "provenance",
    ),
}


def _schema(kind: str) -> dict[str, Any]:
    rec = record_schema()
    props: dict[str, Any] = {k: {} for k in _ORDER[kind]}
    if kind == "positions":
        props["planets"] = {"additionalProperties": {"$ref": "#/$defs/body"}}
        props["derived_ut"] = rec["properties"]["derived_ut"]
        props["derived_tt"] = rec["properties"]["derived_tt"]
        props["instant"] = {
            "properties": {
                "jdn": {},
                "nadika_after_sunrise": {},
                "local_fraction": {"x-derived": True},
                "standard": {},
            }
        }
    if kind == "eclipse":
        props["eclipse"] = {"x-derived": True}
    props["provenance"] = rec["properties"]["provenance"]
    return {"$defs": rec["$defs"], "properties": props}


def dumps(result: Mapping[str, Any]) -> str:
    """One canonical JSON line of a record or of another result of this module."""
    kind = result.get("kind")
    schema = record_schema() if kind is None else _schema(str(kind))
    return jsonl.dumps(result, str(result["numeric"]), schema)


def _jdn(date: TaggedDate | JDN) -> JDN:
    return date if isinstance(date, JDN) else jdn_of(date)


def records(
    config: RunConfig, *, derived_ut: str | None = None, derived_tt: str | None = None
) -> Records:
    """The record builder of ``config`` with the derived placements asked for."""
    return Records(config, derived=derived_chain(config, derived_ut, derived_tt))


def generate(
    config: RunConfig,
    first_jdn: TaggedDate | JDN,
    last_jdn: TaggedDate | JDN,
    *,
    derived_ut: str | None = None,
    derived_tt: str | None = None,
) -> Iterator[dict[str, Any]]:
    """The records of ``first_jdn`` to ``last_jdn`` inclusive, in JDN order (streamed).

    Both ends are checked before the first day is yielded: a window
    before ``runs_from`` or after ``runs_to`` is refused naming the bound,
    and the last day's record is built first, so a last day the run cannot
    serve (its look ahead past ``runs_to``, a derived placement outside its
    model's range) is refused before any line is written; an empty window
    (last before first) yields nothing.
    """
    first, last = _jdn(first_jdn), _jdn(last_jdn)
    builder = records(config, derived_ut=derived_ut, derived_tt=derived_tt)
    if last.days_since(first) >= 0:
        builder.served(first)
        builder.served(last)
        builder.record(last)

    def stream() -> Iterator[dict[str, Any]]:
        for n in range(first.value, last.value + 1):
            yield builder.record(JDN(n))

    return stream()


def day(
    config: RunConfig,
    date: TaggedDate | JDN,
    *,
    derived_ut: str | None = None,
    derived_tt: str | None = None,
) -> dict[str, Any]:
    """The record of one civil day."""
    return records(config, derived_ut=derived_ut, derived_tt=derived_tt).record(_jdn(date))


def _instant_leaf(instant: CivilInstant) -> dict[str, Any]:
    if isinstance(instant, SiddhanticCivilInstant):
        return {
            "jdn": instant.jdn.value,
            "nadika_after_sunrise": instant.nadika_after_sunrise.value,
            "standard": instant.standard,
        }
    if isinstance(instant, ModernCivilInstant):
        return {
            "jdn": instant.jdn.value,
            "local_fraction": instant.local_fraction,
            "standard": instant.standard,
        }
    raise Refusal("instant", f"an instant is a CivilInstant, not {type(instant).__name__}")


def _day_flags(config: RunConfig, jdn: JDN) -> list[str]:
    sd = config.calendar.source.day(jdn)
    return sorted(set(sd.flags) | set(config.diagnostic))


def positions(
    config: RunConfig,
    instant: CivilInstant,
    bodies: Iterable[str],
    *,
    derived_ut: str | None = None,
    derived_tt: str | None = None,
) -> dict[str, Any]:
    """The planets leaf's shape for ``bodies`` at ``instant`` (module docstring)."""
    builder = records(config, derived_ut=derived_ut, derived_tt=derived_tt)
    builder.served(instant.jdn)
    with serving(instant.jdn, "at"):
        planets = builder.positions.at(instant, bodies)
    out: dict[str, Any] = {
        "kind": "positions",
        "method_id": config.method_id,
        "config_hash": config.config_hash,
        "numeric": config.numeric,
        "instant": _instant_leaf(instant),
        "planets": planets,
    }
    flags = _day_flags(config, instant.jdn)
    if builder.derived is not None:
        if not isinstance(instant, SiddhanticCivilInstant):
            raise Refusal("at", "the derived placements place a siddhantic instant only")
        sd = config.calendar.source.day(instant.jdn)
        out.update(
            builder.derived.fields(
                instant.jdn, sd.sunrise_after_midnight, instant.nadika_after_sunrise
            )
        )
        flags = sorted({*flags, "provisional:derived_ut.time_reckoning"})
    out["flags"] = flags
    out["provenance"] = builder.provenance
    return out


def _window(window: tuple[TaggedDate | JDN, TaggedDate | JDN]) -> tuple[JDN, JDN]:
    first, last = (_jdn(w) for w in window)
    return first, last


def sankrantis(
    config: RunConfig, window: tuple[TaggedDate | JDN, TaggedDate | JDN]
) -> Iterator[dict[str, Any]]:
    """The saṅkrāntis of the window's civil days, in time order (module docstring).

    ``instant`` is in nāḍikās after the civil day's start (exact under a
    siddhantic method); ``assigned_day1`` is the JDN of the first day of
    the month entered under the configuration's month rule, ``null``
    where the rule gives the month another rāśi's start, ``not_in_preset``
    with no month rule.
    """
    first, last = _window(window)
    builder = records(config)
    cal = config.calendar
    if last.days_since(first) >= 0:
        builder.served(first)
        builder.served(last)
        with serving(last):
            cal.sankranti(last)

    def stream() -> Iterator[dict[str, Any]]:
        for n in range(first.value, last.value + 1):
            jdn = JDN(n)
            with serving(jdn):
                leaf = cal.sankranti(jdn)
            if leaf is None:
                continue
            instant = leaf["instant"]
            num, _, den = str(instant).partition("/")
            yield {
                "kind": "sankranti",
                "method_id": config.method_id,
                "config_hash": config.config_hash,
                "numeric": config.numeric,
                "dates": date_record(jdn),
                "rasi_index": leaf["rasi_index"],
                "instant": Fraction(int(num), int(den)),
                "assigned_day1": leaf["assigned_day1"],
                # the month rule's own flag, as the day records carry it
                "flags": sorted({*_day_flags(config, jdn), *cal.month_rule_flags()}),
                "provenance": builder.provenance,
            }

    return stream()


def eclipses(
    config: RunConfig, window: tuple[TaggedDate | JDN, TaggedDate | JDN]
) -> Iterator[dict[str, Any]]:
    """The eclipses whose greatest instant falls in the window (modern only, provisional)."""
    if config.kind != "modern":
        caps = config.engine.capabilities
        raise Refusal(
            "eclipses",
            f"{config.method_id} does not model eclipses "
            f"({caps.not_modelled.get('eclipses', 'not modelled')}); a modern preset does, "
            "provisionally",
        )
    first, last = _window(window)
    builder = records(config)
    if last.days_since(first) >= 0:
        builder.served(first)
        builder.served(last)
    from jyotirganita.search.evaluate import Evaluator
    from jyotirganita.search.query import Query

    scan = Evaluator(config, Query(cast(Any, None), first, last, (), False, 0, "", {}))
    if last.days_since(first) >= 0:
        with serving(last):
            scan.eclipses(last)

    def stream() -> Iterator[dict[str, Any]]:
        for n in range(first.value, last.value + 1):
            jdn = JDN(n)
            with serving(jdn):
                found = scan.eclipses(jdn)
            for e in found:
                body = {k: v for k, v in e.items() if not k.startswith("_")}
                yield {
                    "kind": "eclipse",
                    "method_id": config.method_id,
                    "config_hash": config.config_hash,
                    "numeric": config.numeric,
                    "dates": date_record(jdn),
                    "eclipse": body,
                    "flags": sorted({*_day_flags(config, jdn), ECLIPSE_FLAG}),
                    "provenance": builder.provenance,
                }

    return stream()
