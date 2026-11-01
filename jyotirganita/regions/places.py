"""Place tables, ``regions/<region>/places.yaml``.

A place serves a siddhantic method by one of these routes,
which its entry names:

- ``text_units`` (route (a)): the place and its coordinates as the text
  itself states them, each coordinate the reading of a statement datum of
  that text (``statement``) with the value as read;
- ``modern_converted`` (route (b)): the place's latitude and longitude from
  a cited modern coordinate (a datum, its value read from it), brought
  into the text's terms by the text's own rules (``conversion``): the
  latitude in degrees, whose Rsine and that of the colatitude the engine
  takes from the text's table (laghubhaskariya_1963 II.17–18 works in those Rsines); the
  meridian offset in ghaṭīs from the longitude difference to the text's
  meridian (``meridian_longitude``, the meridian's modern longitude as a
  cited datum). The text's own route from a longitude difference to
  ghaṭīs passes through the yojana scale (laghubhaskariya_1963 I.24, I.31: the
  difference's share of the local circle in yojanas, then those yojanas'
  share of the same circle in ghaṭīs; goladipika_1916 v. 196, v. 201 the same for the
  Dṛk line); with no rounding stated, the two scalings cancel exactly and
  the offset is the difference × 60 ÷ 360. ``conversion`` names the rules
  per text. A text whose meridian is not its own datum's reaches the
  meridian through a statement identifying its line with it
  (``meridian_identification``, with the gap ``meridian_gap`` it stands
  in for): every record of that text's method carries the
  identification's flags (``provisional:<its key>``) and its provenance
  names the three keys;
- ``gap``: no route; ``gap`` names the gap datum, and a run for the place
  is refused naming it;
- ``user_coordinates``:
  the region's template for a place the user names by its coordinates,
  ``<region>/@<lat>,<lon>`` (:func:`user_coordinates`): route (b) with the
  entry's ``meridian_longitude`` and ``conversion`` and the user's latitude
  and longitude in place of cited data. The coordinates are input, not
  data: every record carries ``user_place``, and the
  provenance records them (``observer_coordinates``).

A provisional entry flags every record ``provisional:regions.<region>.<id>``.
A place reached from a modern latitude and longitude (route (b), tabled or
the user's) flags every record ``modern_coordinates`` under every method,
the modern engine's included.

The modern engine takes a place by its cited modern coordinates
alone (:func:`load_modern_place`): the latitude and longitude statements
of a ``modern_converted`` entry, read from their data as route (b) reads
them, without the text's conversion; a ``text_units`` entry states no
modern coordinate and a ``gap`` entry no route, and both are refused.

The file's structure is validated by the datum loader (schema
``places_file``); :func:`load_place` reads one entry into the engine's
:class:`~jyotirganita.siddhantic.engine.Observer` and checks that every
statement it names is a datum, not a gap, of the kind the route takes.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from jyotirganita.data.datum import PLACES_FILE, DatumError, Record
from jyotirganita.data.yamlio import load_exact
from jyotirganita.siddhantic.engine import Observer

__all__ = [
    "MODERN_FLAG",
    "USER_FLAG",
    "ModernPlace",
    "PlaceError",
    "load_modern_place",
    "load_place",
    "place_flag",
    "place_ids",
    "places_path",
    "user_coordinates",
]

#: the flag of every record at a place reached from modern coordinates
MODERN_FLAG = "modern_coordinates"
#: the flag of every record at coordinates the user supplied
USER_FLAG = "user_place"
#: the route of a region's template for user coordinates
USER_ROUTE = "user_coordinates"

#: the units route (a) accepts, by coordinate
_UNITS = {"latitude": "degrees_north", "meridian_offset": "ghatis_east"}
#: the units route (b) accepts, by coordinate
_MODERN_UNITS = {
    "latitude": "degrees_north",
    "longitude": "degrees_east",
    "meridian_longitude": "degrees_east",
}
GHATIS_PER_DAY = 60
DEGREES_PER_REVOLUTION = 360
MINUTES_PER_DEGREE = 60
MAX_LATITUDE = 90
MAX_LONGITUDE = 180
#: one coordinate: decimal degrees, or ``d:m`` or ``d:m:s`` (seconds decimal)
_COORD = r"-?(?:\d+(?:\.\d+)?|\d+:\d+(?::\d+(?:\.\d+)?)?)"
_USER = re.compile(rf"@({_COORD}),({_COORD})")


class PlaceError(ValueError):
    """A place that is absent, malformed, a gap, or not served by a method's text."""


def _coordinate_value(text: str) -> Fraction:
    sign = -1 if text.startswith("-") else 1
    parts = text.lstrip("-").split(":")
    out = Fraction(0)
    for i, part in enumerate(parts):
        v = Fraction(part)
        if i and v >= MINUTES_PER_DEGREE:
            raise PlaceError(f"user coordinates: {text!r} has a minute or second of 60 or more")
        out += v / MINUTES_PER_DEGREE**i
    return sign * out


def user_coordinates(place_id: str) -> tuple[Fraction, Fraction] | None:
    """The latitude north and longitude east ``place_id`` names, or ``None`` for a tabled id.

    ``@<lat>,<lon>``, each in decimal degrees or ``d:m[:s]``, negative south
    and west; read exactly (no float).
    """
    if not place_id.startswith("@"):
        return None
    m = _USER.fullmatch(place_id)
    if m is None:
        raise PlaceError(
            f"user coordinates are @<lat>,<lon> in degrees north and east (decimal or d:m[:s]), "
            f"not {place_id!r}"
        )
    lat, lon = _coordinate_value(m[1]), _coordinate_value(m[2])
    if abs(lat) > MAX_LATITUDE:
        raise PlaceError(f"user coordinates {place_id!r}: latitude beyond ±{MAX_LATITUDE}°")
    if abs(lon) > MAX_LONGITUDE:
        raise PlaceError(f"user coordinates {place_id!r}: longitude beyond ±{MAX_LONGITUDE}°")
    return lat, lon


def places_path(repo: Path, region: str) -> Path:
    """The place table of ``region``."""
    return repo / "jyotirganita" / "regions" / region / PLACES_FILE


def place_flag(region: str, place_id: str) -> str:
    """The flag a provisional place puts on every record."""
    return f"provisional:regions.{region}.{place_id}"


def _statement(
    entry: Mapping[str, Any], name: str, records: Mapping[str, Record], where: str
) -> Record:
    c = entry.get(name)
    if c is None:
        raise PlaceError(f"{where}: route {entry['route']} needs {name}")
    rec = records.get(c["statement"])
    if rec is None or rec.kind == "gap":
        raise PlaceError(f"{where}: {name} reads {c['statement']}, which is not a datum")
    return rec


def _coordinate(
    entry: Mapping[str, Any], name: str, records: Mapping[str, Record], where: str
) -> Fraction:
    rec = _statement(entry, name, records, where)
    c = entry[name]
    if c["unit"] != _UNITS[name]:
        raise PlaceError(f"{where}: {name} in {c['unit']}, route text_units takes {_UNITS[name]}")
    if "value" not in c:
        raise PlaceError(f"{where}: route text_units gives {name} its value as read")
    if not any(rec.key.startswith(f"texts.{t}.") for t in entry["texts"]):
        raise PlaceError(f"{where}: {name} reads {rec.key}, a datum of none of its texts")
    return Fraction(c["value"])


def _degrees(rec: Record, where: str) -> Fraction:
    """A sexagesimal ``[deg, min(, sec)]`` or a decimal datum as degrees."""
    v = rec.value
    if isinstance(v, list):
        # a tabled coordinate gets the user route's checks,
        # its length and its parts' types among them
        if (
            not 1 <= len(v) <= 3
            or any(isinstance(p, bool) or not isinstance(p, int | Fraction) for p in v)
            or any(not 0 <= Fraction(p) < MINUTES_PER_DEGREE for p in v[1:])
        ):
            raise PlaceError(f"{where}: {rec.key} is not [deg, min(, sec)] ({v!r})")
        # the degree's sign holds for its minutes and seconds: [-10, 30] is −10.5°
        # (every shipped datum is positive)
        sign = -1 if Fraction(v[0]) < 0 else 1
        out = Fraction(0)
        for i, part in enumerate(v):
            out += abs(Fraction(part)) / MINUTES_PER_DEGREE**i
        return sign * out
    if isinstance(v, bool) or not isinstance(v, int | Fraction):
        raise PlaceError(f"{where}: {rec.key} is not a coordinate ({v!r})")
    return Fraction(v)


def _modern(
    entry: Mapping[str, Any], name: str, records: Mapping[str, Record], where: str
) -> Fraction:
    rec = _statement(entry, name, records, where)
    c = entry[name]
    if c["unit"] != _MODERN_UNITS[name] or rec.raw.get("unit") != _MODERN_UNITS[name]:
        raise PlaceError(f"{where}: {name} in {c['unit']}, route (b) takes {_MODERN_UNITS[name]}")
    if "value" in c:
        raise PlaceError(f"{where}: route (b) reads {name}'s value from its datum, not the entry")
    deg = _degrees(rec, where)
    limit = MAX_LATITUDE if name == "latitude" else MAX_LONGITUDE
    if abs(deg) > limit:  # as user coordinates
        raise PlaceError(f"{where}: {rec.key}: {name} beyond ±{limit}°")
    return deg


def _rule(records: Mapping[str, Record], key: str, text: str, where: str, *, gap: bool) -> Record:
    rec = records.get(key)
    if rec is None or (rec.kind == "gap") is not gap:
        what = "a gap" if gap else "a datum"
        raise PlaceError(f"{where}: the conversion names {key}, which is not {what}")
    if not rec.key.startswith(f"texts.{text}."):
        raise PlaceError(f"{where}: the conversion names {key}, no rule of {text}")
    return rec


def _converted(
    entry: Mapping[str, Any],
    records: Mapping[str, Record],
    where: str,
    user: tuple[Fraction, Fraction] | None = None,
) -> tuple[Fraction, Fraction, tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]:
    """Latitude, offset, and the route's ``(text, flag)`` and ``(text, key)`` pairs.

    ``user``: the user's latitude and longitude, in place of the entry's data.
    """
    conversions = entry.get("conversion")
    if conversions is None:
        raise PlaceError(f"{where}: route (b) names the text's conversion rules")
    texts = list(entry["texts"])
    if sorted(conversions) != sorted(texts):
        raise PlaceError(f"{where}: route (b) names the conversion rules of each of {texts}")
    meridian = _statement(entry, "meridian_longitude", records, where)
    text_flags: list[tuple[str, str]] = []
    route_data: list[tuple[str, str]] = []
    for text in texts:
        rules = conversions[text]
        for name in ("latitude", "meridian_offset"):
            _rule(records, rules[name], text, where, gap=False)
        ident = rules.get("meridian_identification")
        if meridian.key.startswith(f"texts.{text}."):
            if ident is not None:
                raise PlaceError(f"{where}: {text}'s meridian is its own datum; no identification")
            continue
        if ident is None:
            raise PlaceError(
                f"{where}: meridian_longitude reads {meridian.key}, not a datum of {text}; "
                f"route (b) for {text} names the statement identifying its line with it"
            )
        rec = _rule(records, ident, text, where, gap=False)
        gap = _rule(records, rules["meridian_gap"], text, where, gap=True)
        text_flags += [(text, f) for f in sorted({f"provisional:{rec.key}", *rec.flags})]
        route_data += [(text, rec.key), (text, gap.key), (text, meridian.key)]
    if user is None:
        latitude = _modern(entry, "latitude", records, where)
        longitude = _modern(entry, "longitude", records, where)
    else:
        latitude, longitude = user
    difference = longitude - _modern(entry, "meridian_longitude", records, where)
    offset = difference * GHATIS_PER_DAY / DEGREES_PER_REVOLUTION
    return latitude, offset, tuple(text_flags), tuple(route_data)


def _entries(repo: Path, region: str) -> dict[str, Any]:
    path = places_path(repo, region)
    if not path.is_file():
        raise PlaceError(f"no place table for region {region!r} ({path})")
    try:
        doc = load_exact(path)
    except DatumError as e:  # pragma: no cover - the datum loader reports it first
        raise PlaceError(str(e)) from None
    return {e["id"]: e for e in doc["places"]}


def place_ids(repo: Path, region: str) -> list[str]:
    """The ids of ``region``'s tabled places, in file order (the user template is no place)."""
    return [k for k, e in _entries(repo, region).items() if e["route"] != USER_ROUTE]


def _entry(
    repo: Path, region: str, place_id: str
) -> tuple[dict[str, Any], tuple[Fraction, Fraction] | None, str]:
    """The entry serving ``place_id``, the user's coordinates if it names them, and its id."""
    user = user_coordinates(place_id)
    entries = _entries(repo, region)
    if user is not None:
        found = [e for e in entries.values() if e["route"] == USER_ROUTE]
        if not found:
            raise PlaceError(
                f"region {region}: its place table has no {USER_ROUTE} entry, so user "
                f"coordinates are not served there"
            )
        return found[0], user, found[0]["id"]
    entry = entries.get(place_id)
    if entry is None or entry["route"] == USER_ROUTE:
        tabled = sorted(k for k, e in entries.items() if e["route"] != USER_ROUTE)
        raise PlaceError(f"region {region}: no place {place_id!r} (has {tabled})")
    return entry, None, place_id


def load_place(repo: Path, region: str, place_id: str, records: Mapping[str, Record]) -> Observer:
    """The observer ``place_id`` of ``region``'s place table (``records``: the loaded data).

    ``place_id`` ``@<lat>,<lon>`` names user coordinates (module docstring).
    """
    entry, user, entry_id = _entry(repo, region, place_id)
    where = f"regions/{region}/{PLACES_FILE}: {entry_id}"
    route = entry["route"]
    if route == "gap":
        gap = entry.get("gap")
        rec = records.get(gap) if gap else None
        if rec is None or rec.kind != "gap":
            raise PlaceError(f"{where}: route gap names its gap datum")
        raise PlaceError(f"{where}: no route serves this place: {gap} ({rec.raw['reason']})")
    text_flags: tuple[tuple[str, str], ...] = ()
    route_data: tuple[tuple[str, str], ...] = ()
    coordinates = None
    if route == "text_units":
        latitude = _coordinate(entry, "latitude", records, where)
        offset = _coordinate(entry, "meridian_offset", records, where)
    else:
        latitude, offset, text_flags, route_data = _converted(entry, records, where, user)
        if user is not None:
            coordinates = user
    return Observer(
        f"{region}.{place_id}",
        tuple(entry["texts"]),
        offset,
        latitude,
        _flags(region, entry, user),
        route,
        text_flags,
        route_data,
        coordinates,
    )


def _flags(
    region: str, entry: Mapping[str, Any], user: tuple[Fraction, Fraction] | None
) -> tuple[str, ...]:
    flags = {place_flag(region, entry["id"])} if entry.get("provisional") else set()
    if entry["route"] in ("modern_converted", USER_ROUTE):
        flags.add(MODERN_FLAG)
    if user is not None:
        flags.add(USER_FLAG)
    return tuple(sorted(flags))


@dataclass(frozen=True, slots=True)
class ModernPlace:
    """A place as the modern engine takes it: cited latitude north and longitude east."""

    id: str
    latitude_deg: Fraction
    longitude_deg: Fraction
    flags: tuple[str, ...]
    statements: tuple[str, ...]


def load_modern_place(
    repo: Path, region: str, place_id: str, records: Mapping[str, Record]
) -> ModernPlace:
    """The cited modern coordinates of ``place_id``, or the user's (module docstring)."""
    entry, user, entry_id = _entry(repo, region, place_id)
    where = f"regions/{region}/{PLACES_FILE}: {entry_id}"
    flags = _flags(region, entry, user)
    if user is not None:
        return ModernPlace(f"{region}.{place_id}", user[0], user[1], flags, ())
    if entry["route"] != "modern_converted":
        raise PlaceError(
            f"{where}: route {entry['route']} states no cited modern latitude and longitude"
        )
    latitude = _modern(entry, "latitude", records, where)
    longitude = _modern(entry, "longitude", records, where)
    keys = (entry["latitude"]["statement"], entry["longitude"]["statement"])
    return ModernPlace(f"{region}.{place_id}", latitude, longitude, flags, keys)
