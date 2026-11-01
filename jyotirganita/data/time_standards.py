"""Civil time standards: ``data/time_standards/<id>.yaml``.

A standard is an offset from Universal Time east of Greenwich, constant
over each of its periods of force (``utc_offset``), or the local mean
time of the observer's meridian (``local_mean_time``), whose offset is
the observer's longitude east as a fraction of the day. The file format
is ``time_standard_file`` of ``schema/records.schema.json``; its datums
(the printed definitions) are loaded by
:func:`jyotirganita.data.datum.load_datum_file` like any other.

**Dates of force.** A period runs from the wall-clock midnight that
begins its ``from`` date to the one that begins its ``to`` date (the
IANA database's UNTIL column, read as it states: a bare year is 1
January, a bare month its first day). Where no page states them they are
read from a fetched table under ``data/tables/``, and every period is checked against
the line it names: its offset is the line's STDOFF plus its SAVE, its end
the line's UNTIL and its start the previous line's UNTIL. A day outside
every period is refused (:class:`OutOfForce`), never given a neighbour's
offset.

A siddhantic preset's standard ``text_local:<text_id>`` is not a civil
standard and is not defined here.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal

from jyotirganita.core.calendar import jdn_from_gregorian
from jyotirganita.core.types import JDN, GregorianDate
from jyotirganita.data.datum import TIME_STANDARDS_DIR, Context, DatumError, load_datum_file
from jyotirganita.data.yamlio import load_exact

__all__ = [
    "OutOfForce",
    "Period",
    "TimeStandard",
    "load_time_standard",
    "load_time_standards",
    "offset_days",
    "zone_line",
]

SECONDS_PER_DAY = 86400
SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60
DEGREES_PER_REVOLUTION = 360
#: the month abbreviations of the IANA database's UNTIL column, January first
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
TABLES_DIR = "tables"

type Kind = Literal["utc_offset", "local_mean_time"]


class OutOfForce(ValueError):
    """A day outside every period of a standard's force."""


@dataclass(frozen=True, slots=True)
class Period:
    """A period of force: civil days ``start`` ≤ d < ``end`` (``None``: open) at ``offset``.

    ``offset`` is east of Greenwich, in days; ``war_time`` marks a period
    of daylight saving.
    """

    start: JDN | None
    end: JDN | None
    offset: Fraction
    war_time: bool = False

    def holds(self, day: JDN) -> bool:
        """Whether civil day ``day`` lies in this period."""
        return (self.start is None or day.days_since(self.start) >= 0) and (
            self.end is None or self.end.days_since(day) > 0
        )


@dataclass(frozen=True, slots=True)
class TimeStandard:
    """A civil time standard: its kind, its periods of force and the datum or line citing it."""

    id: str
    title: str
    kind: Kind
    periods: tuple[Period, ...]
    citation: str
    path: str

    def offset_on(self, day: JDN, longitude_east: Fraction | None = None) -> Fraction:
        """The offset east of Greenwich, in days, in force on civil day ``day``.

        A local mean time needs the observer's longitude east, in degrees.
        """
        if not isinstance(day, JDN):
            raise TypeError(f"a standard is evaluated on a JDN, not {type(day).__name__}")
        if self.kind == "local_mean_time":
            if longitude_east is None:
                raise ValueError(f"{self.id}: local mean time needs the observer's longitude")
            return Fraction(longitude_east) / DEGREES_PER_REVOLUTION
        for p in self.periods:
            if p.holds(day):
                return p.offset
        raise OutOfForce(
            f"{self.id} is not in force on JDN {day.value} ({self.path}: its periods of force)"
        )


def offset_days(text: str) -> Fraction:
    """``+HH:MM[:SS]`` or an IANA ``H:MM[:SS]`` (``-`` for zero) as a fraction of a day."""
    s = text.strip()
    if s == "-":
        return Fraction(0)
    sign = -1 if s.startswith("-") else 1
    parts = [int(x) for x in s.lstrip("+-").split(":")]
    while len(parts) < 3:
        parts.append(0)
    h, m, sec = parts
    seconds = h * SECONDS_PER_HOUR + m * SECONDS_PER_MINUTE + sec
    return Fraction(sign * seconds, SECONDS_PER_DAY)


def _until(fields: list[str], where: str) -> GregorianDate | None:
    """The UNTIL column (year [month [day]]) as the date whose midnight it names."""
    if not fields:
        return None
    y = int(fields[0])
    m = MONTHS.index(fields[1]) + 1 if len(fields) > 1 else 1
    d = int(fields[2]) if len(fields) > 2 else 1
    if len(fields) > 3:
        raise DatumError(f"{where}: an UNTIL with a time of day is not read here ({fields})")
    return GregorianDate(y, m, d)


def zone_line(line: str, where: str) -> tuple[Fraction, Fraction, GregorianDate | None]:
    """An IANA zone line (first or continuation): STDOFF, SAVE (a fixed amount) and UNTIL."""
    body = line.split("#", 1)[0].split()
    if body and body[0] == "Zone":
        body = body[2:]
    if len(body) < 3:
        raise DatumError(f"{where}: not a zone line: {line!r}")
    stdoff, rules = body[0], body[1]
    if rules != "-" and not rules[:1].isdigit():
        raise DatumError(f"{where}: a named rule set ({rules}) is not read here")
    return offset_days(stdoff), offset_days(rules), _until(body[3:], where)


def _iso(text: str) -> GregorianDate:
    y, m, d = (int(x) for x in text.split("-"))
    return GregorianDate(y, m, d)


def _table(repo: Path, name: str) -> dict[str, Any]:
    path = repo / "jyotirganita" / "data" / TABLES_DIR / f"{name}.yaml"
    doc = load_exact(path)
    if not isinstance(doc, dict) or doc.get("table") != name:
        raise DatumError(f"{path}: not the fetched table {name}")
    return doc


def _periods(doc: dict[str, Any], repo: Path, rel: str) -> tuple[Period, ...]:
    force = doc["in_force"]
    if "periods" not in force:
        return (Period(None, None, Fraction(0)),)
    table = _table(repo, force["table"])
    lines: list[str] = table["lines"]
    out: list[Period] = []
    for p in force["periods"]:
        n = p["line"]
        where = f"{rel}: period from {p['from']} (table {force['table']} line {n})"
        if not 1 < n <= len(lines):
            raise DatumError(f"{where}: no such continuation line")
        std, save, until = zone_line(lines[n - 1], where)
        _, _, began = zone_line(lines[n - 2], where)
        offset = offset_days(p["offset"])
        if offset != std + save:
            raise DatumError(f"{where}: offset {p['offset']} is not the line's STDOFF + SAVE")
        if began != _iso(p["from"]):
            raise DatumError(f"{where}: from is not the previous line's UNTIL ({began})")
        end = None if p["to"] == "open" else _iso(p["to"])
        if end != until:
            raise DatumError(f"{where}: to is not the line's UNTIL ({until})")
        out.append(
            Period(
                jdn_from_gregorian(began),
                None if end is None else jdn_from_gregorian(end),
                offset,
                bool(p.get("war_time", False)),
            )
        )
    for a, b in pairwise(out):
        if a.end != b.start:
            raise DatumError(f"{rel}: the periods of force are not contiguous")
    return tuple(out)


def load_time_standard(path: Path, ctx: Context, repo: Path) -> TimeStandard:
    """One standard, checked: its datums load, its periods agree with the table's lines."""
    records = load_datum_file(path, ctx, "provisional", repo)
    rel = path.relative_to(repo).as_posix()
    data = {r.key: r for r in records}
    doc = load_exact(path)
    assert isinstance(doc, dict)
    d = doc["definition"]
    kind: Kind = d["kind"]
    for key in (d.get("datum"), *d.get("witnesses", ())):
        if key is not None and (key not in data or data[key].kind == "gap"):
            raise DatumError(f"{rel}: definition names {key}, which is not a datum of this file")
    if "datum" in d:
        citation = d["datum"]
    elif "table" in d:
        citation = f"{d['table']}:{d['line']}"
        std, save, _ = zone_line(_table(repo, d["table"])["lines"][d["line"] - 1], rel)
        if offset_days(d["offset"]) != std + save:
            raise DatumError(f"{rel}: the definition's offset is not the table line's")
    else:
        raise DatumError(f"{rel}: a definition names its datum or its table line")
    if kind == "utc_offset" and "offset" not in d:
        raise DatumError(f"{rel}: an offset standard states its offset")
    periods = _periods(doc, repo, rel)
    if kind == "utc_offset" and "periods" not in doc["in_force"]:
        raise DatumError(f"{rel}: an offset standard states its periods of force")
    return TimeStandard(doc["standard"], doc["title"], kind, periods, citation, rel)


def load_time_standards(repo: Path, ctx: Context) -> dict[str, TimeStandard]:
    """Every standard under ``jyotirganita/data/time_standards/``, by id."""
    root = repo / "jyotirganita" / "data" / TIME_STANDARDS_DIR
    out = {}
    for path in sorted(root.glob("*.yaml")):
        ts = load_time_standard(path, ctx, repo)
        out[ts.id] = ts
    return out
