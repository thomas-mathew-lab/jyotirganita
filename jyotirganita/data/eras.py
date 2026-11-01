"""Era records: ``data/eras/<era_id>.yaml`` read into :class:`~jyotirganita.core.eras.Era`.

The file format is ``era_file`` of
``schema/records.schema.json``. An era
record is a mapping: its structure (epoch, counting, year-start options,
range, month naming, or a cycle), each part naming the datum that cites
it, and under ``data`` the datums themselves, loaded by
:func:`jyotirganita.data.datum.load_datum_file` under every rule of
the datum model. Every key the structure names must be a datum of the same
file, so a record is self-contained.

An epoch's date is the datum's printed text (its adopted emendation when
it carries one), or the ``date`` cell of a one-row table datum (an epoch
printed as a row of a table, keyed as the table it is), parsed by
:func:`jyotirganita.core.calendar.parse_printed_date` in the calendar the
record names, and the record names the datum
(``calendar_ref``) whose page states that calendar: the
year never decides it.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jyotirganita.core.calendar import jdn_from_gregorian, jdn_from_julian, parse_printed_date
from jyotirganita.core.eras import Cycle, Era, EraRange, Sun, YearStart
from jyotirganita.core.types import JDN, GregorianDate, JulianDate
from jyotirganita.data.datum import ERAS_DIR, Context, DatumError, Record, load_datum_file
from jyotirganita.data.yamlio import load_exact

__all__ = ["EraFile", "era_files", "load_era", "load_eras"]


class EraFile:
    """One loaded era record: the :class:`Era` and the datums of its file."""

    def __init__(self, era: Era, data: Mapping[str, Record], path: str) -> None:
        self.era = era
        self.data = data
        self.path = path


def era_files(data_root: Path) -> list[Path]:
    """The era records under ``data_root`` (``jyotirganita/data``)."""
    return sorted((data_root / ERAS_DIR).glob("*.yaml"))


def _printed(rec: Record) -> object:
    em = rec.raw.get("emendation")
    return em["adopted"] if em else rec.raw["value"]


def _need(data: Mapping[str, Record], key: str, rel: str, what: str) -> Record:
    rec = data.get(key)
    if rec is None:
        raise DatumError(f"{rel}: {what} names {key}, which is not a datum of this file")
    if rec.kind == "gap":
        raise DatumError(f"{rel}: {what} names {key}, a gap: the era cannot be built on it")
    return rec


def _table_date(rec: Record, rows: object, rel: str) -> object:
    """The ``date`` cell of a one-row table datum (an epoch printed as a table row)."""
    columns = rec.raw["columns"]
    if "date" not in columns or not isinstance(rows, list) or len(rows) != 1:
        raise DatumError(
            f"{rel}: {rec.key}: an epoch date from a table is one row with a `date` column"
        )
    return rows[0][columns.index("date")]


def _epoch(spec: Mapping[str, Any], data: Mapping[str, Record], rel: str) -> JDN:
    rec = _need(data, spec["date"], rel, "epoch.date")
    _need(data, spec["calendar_ref"], rel, "epoch.calendar_ref")
    if spec["day_start"] != "unstated":
        _need(data, spec["day_start"], rel, "epoch.day_start")
    text = _printed(rec)
    if rec.form == "table":
        text = _table_date(rec, text, rel)
    if not isinstance(text, str):
        raise DatumError(f"{rel}: {rec.key}: an epoch date is a printed date (form: text)")
    try:
        if spec["calendar"] == "julian":
            return jdn_from_julian(parse_printed_date(text, JulianDate))
        return jdn_from_gregorian(parse_printed_date(text, GregorianDate))
    except ValueError as e:
        raise DatumError(f"{rel}: {rec.key}: {e}") from e


def _names(rec: Record, rel: str) -> tuple[str, ...]:
    v = _printed(rec)
    if not isinstance(v, list) or not v:
        raise DatumError(f"{rel}: {rec.key}: a cycle's names are a printed list")
    out: list[str] = []
    for row in v:
        name = row[0] if isinstance(row, list) and len(row) == 1 else row
        if not isinstance(name, str) or not name:
            raise DatumError(f"{rel}: {rec.key}: a cycle name is a string")
        out.append(name)
    return tuple(out)


def load_era(path: Path, ctx: Context, repo: Path | None = None) -> EraFile:
    """One era record, checked: every named datum present, the epoch parsed."""
    records = load_datum_file(path, ctx, "provisional", repo)
    rel = records[0].path if records else str(path)
    data = {r.key: r for r in records}
    doc = load_exact(path)
    assert isinstance(doc, dict)
    era_id = doc["era"]
    _need(data, doc["range"]["datum"], rel, "range.datum")

    if "cycle" in doc:
        c = doc["cycle"]
        names = _names(_need(data, c["names"], rel, "cycle.names"), rel)
        a = c["anchor"]
        _need(data, a["datum"], rel, "cycle.anchor.datum")
        if a["name"] not in names:
            raise DatumError(f"{rel}: cycle anchor name {a['name']!r} is not in {c['names']}")
        if c["length"] != len(names):
            raise DatumError(f"{rel}: cycle length {c['length']} but {len(names)} names")
        rng = doc["range"]
        if rng["from"] == "epoch":
            raise DatumError(f"{rel}: a cyclic era has no epoch: its range is in JDNs")
        era = Era(
            era_id,
            EraRange(JDN(rng["from"]), None if rng["to"] == "open" else JDN(rng["to"])),
            cycle=Cycle(len(names), names, a["era"], a["year"], names.index(a["name"])),
        )
        return EraFile(era, data, rel)

    epoch = _epoch(doc["epoch"], data, rel)
    _need(data, doc["counting"]["datum"], rel, "counting.datum")
    _need(data, doc["months"]["datum"], rel, "months.datum")
    starts: dict[str, YearStart] = {}
    for option, ys in doc["year_start"].items():
        _need(data, ys["datum"], rel, f"year_start.{option}.datum")
        own = epoch if ys["epoch"] == "era" else _epoch(ys["epoch"], data, rel)
        if own.days_since(epoch) < 0:
            raise DatumError(f"{rel}: year_start.{option}: its epoch precedes the era's")
        sun = Sun.TRUE if ys["sun"] is True else Sun.MEAN
        starts[option] = YearStart(option, ys["rule"], sun, own, ys["datum"])
    rng = doc["range"]
    lo = epoch if rng["from"] == "epoch" else JDN(rng["from"])
    hi = None if rng["to"] == "open" else JDN(rng["to"])
    era = Era(
        era_id,
        EraRange(lo, hi),
        epoch=epoch,
        counting=doc["counting"]["mode"],
        year_starts=starts,
        month_naming=doc["months"]["naming"],
    )
    return EraFile(era, data, rel)


def load_eras(data_root: Path, ctx: Context, repo: Path | None = None) -> dict[str, EraFile]:
    """Every era record under ``data_root``, by era id."""
    out: dict[str, EraFile] = {}
    for path in era_files(data_root):
        ef = load_era(path, ctx, repo)
        if ef.era.id in out:  # the later file replaced the earlier
            raise DatumError(f"{ef.path}: era {ef.era.id} is also defined in {out[ef.era.id].path}")
        out[ef.era.id] = ef
    for ef in out.values():
        cyc = ef.era.cycle
        if cyc is not None and cyc.anchor_era not in out:
            raise DatumError(f"{ef.path}: cycle anchored to era {cyc.anchor_era}, which is absent")
        if cyc is not None and out[cyc.anchor_era].era.cycle is not None:
            # a cycle anchors to a counted era, never to another cycle
            raise DatumError(f"{ef.path}: cycle anchored to era {cyc.anchor_era}, itself a cycle")
    return out
