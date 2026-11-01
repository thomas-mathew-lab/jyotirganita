"""Date syntax of the CLI and of JSON.

A date entering the engine names its calendar; an untagged date is
rejected, never guessed.

- CLI: ``<calendar>:<y>-<m>-<d>`` with ``calendar`` ``julian`` or
  ``gregorian`` (``julian:1000-03-15``, ``gregorian:-44-03-15``), or
  ``jdn:<n>``. Years are astronomical: a negative year is written with a
  leading minus (``julian:-3101-02-18`` is 3102 B.C.).
- JSON: an object with exactly one key, ``julian`` or ``gregorian`` (an
  object ``{y, m, d}`` of integers) or ``jdn`` (an integer).

:func:`date_record` writes the ``dates`` object every record carries:
``{jdn, julian: {y, m, d}, gregorian: {y, m, d}}``.

**Instants** (the CLI's ``positions --at``, :func:`parse_cli_instant`):
a tagged date and a time part whose form names its reckoning, parsed
only under the engine it belongs to:

- siddhantic: ``<date>+<n>nadika``, *n* nāḍikās after the text's sunrise
  of that civil day, an integer, a decimal or a fraction ``a/b``, read
  exactly (``gregorian:1954-08-17+15nadika``,
  ``julian:1000-03-15+7/2nadika``); the instant is on the run's
  ``text_local:<text_id>``;
- modern: ``<date>T<hh>:<mm>[:<ss>[.<fraction>]]/<standard>``, a civil time
  on the named standard, which must be the run's
  (``gregorian:2022-08-17T06:30:00/ist``).

An instant without a time part, a time part of the other engine's form,
or a standard other than the run's is a hard error.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from fractions import Fraction
from typing import Any

from jyotirganita.core.calendar import (
    gregorian_from_jdn,
    jdn_from_gregorian,
    jdn_from_julian,
    julian_from_jdn,
)
from jyotirganita.core.types import (
    JDN,
    CivilInstant,
    GregorianDate,
    JulianDate,
    ModernCivilInstant,
    Nadika,
    SiddhanticCivilInstant,
)

__all__ = [
    "DateSyntaxError",
    "TaggedDate",
    "date_record",
    "jdn_of",
    "parse_cli_date",
    "parse_cli_instant",
    "parse_json_date",
]

type TaggedDate = JulianDate | GregorianDate | JDN
"""A date as the caller tagged it."""

_CLI = re.compile(r"^(?P<cal>julian|gregorian):(?P<y>-?\d+)-(?P<m>\d{1,2})-(?P<d>\d{1,2})$")
_CLI_JDN = re.compile(r"^jdn:(?P<n>-?\d+)$")
_CALENDARS: Mapping[str, type[JulianDate] | type[GregorianDate]] = {
    "julian": JulianDate,
    "gregorian": GregorianDate,
}


_SIDDHANTIC_TIME = re.compile(r"^(?P<date>.+)\+(?P<n>\d+(?:\.\d+|/[1-9]\d*)?)nadika$")
_MODERN_TIME = re.compile(
    r"^(?P<date>.+)T(?P<h>\d{2}):(?P<m>\d{2})(?::(?P<s>\d{2}(?:\.\d+)?))?/(?P<std>[a-z][a-z0-9_]*)$"
)
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400
HOURS_PER_DAY = 24


class DateSyntaxError(ValueError):
    """A date that is untagged or malformed."""


def _build(cls: type[JulianDate] | type[GregorianDate], y: int, m: int, d: int) -> TaggedDate:
    try:
        return cls(y, m, d)
    except (TypeError, ValueError) as e:
        raise DateSyntaxError(str(e)) from e


def parse_cli_date(text: str) -> TaggedDate:
    """A CLI date: ``julian:<y>-<m>-<d>``, ``gregorian:<y>-<m>-<d>`` or ``jdn:<n>``."""
    if not isinstance(text, str):
        raise DateSyntaxError("a CLI date is a string")
    s = text.strip()
    m = _CLI_JDN.match(s)
    if m is not None:
        return JDN(int(m["n"]))
    m = _CLI.match(s)
    if m is None:
        raise DateSyntaxError(
            f"{text!r}: a date names its calendar: julian:<y>-<m>-<d>, gregorian:<y>-<m>-<d> "
            "or jdn:<n>"
        )
    return _build(_CALENDARS[m["cal"]], int(m["y"]), int(m["m"]), int(m["d"]))


def _int(v: object, where: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise DateSyntaxError(f"{where} is an integer")
    return v


def parse_json_date(obj: object) -> TaggedDate:
    """A JSON date: ``{"julian": {y, m, d}}``, ``{"gregorian": {y, m, d}}`` or ``{"jdn": n}``."""
    if not isinstance(obj, Mapping) or len(obj) != 1:
        raise DateSyntaxError("a JSON date is an object with one key, julian, gregorian or jdn")
    ((tag, body),) = obj.items()
    if tag == "jdn":
        return JDN(_int(body, "jdn"))
    if tag not in _CALENDARS:
        raise DateSyntaxError(f"{tag!r} is not a calendar tag (julian, gregorian, jdn)")
    if not isinstance(body, Mapping) or set(body) != {"y", "m", "d"}:
        raise DateSyntaxError(f"a {tag} date is an object {{y, m, d}}")
    return _build(
        _CALENDARS[tag],
        _int(body["y"], f"{tag}.y"),
        _int(body["m"], f"{tag}.m"),
        _int(body["d"], f"{tag}.d"),
    )


def jdn_of(date: TaggedDate) -> JDN:
    """The JDN of a tagged date, through the converter of its own calendar."""
    if isinstance(date, JDN):
        return date
    if isinstance(date, JulianDate):
        return jdn_from_julian(date)
    if isinstance(date, GregorianDate):
        return jdn_from_gregorian(date)
    raise TypeError(f"an untagged date: {type(date).__name__}")


def date_record(jdn: JDN) -> dict[str, Any]:
    """The ``dates`` object of a record: the JDN and both calendar dates."""
    j = julian_from_jdn(jdn)
    g = gregorian_from_jdn(jdn)
    return {
        "jdn": jdn.value,
        "julian": {"y": j.y, "m": j.m, "d": j.d},
        "gregorian": {"y": g.y, "m": g.m, "d": g.d},
    }


def parse_cli_instant(text: str, kind: str, standard: str) -> CivilInstant:
    """A CLI instant under a ``kind`` (``siddhantic`` or ``modern``) run on ``standard``.

    The forms are the module docstring's; the date part is :func:`parse_cli_date`'s.
    """
    if not isinstance(text, str):
        raise DateSyntaxError("a CLI instant is a string")
    s = text.strip()
    sid = _SIDDHANTIC_TIME.match(s)
    mod = _MODERN_TIME.match(s)
    if kind == "siddhantic":
        if sid is None:
            raise DateSyntaxError(
                f"{text!r}: a siddhantic instant is <date>+<n>nadika (nāḍikās after the text's "
                "sunrise); a civil time belongs to a modern preset"
            )
        jdn = jdn_of(parse_cli_date(sid["date"]))
        return SiddhanticCivilInstant(jdn, Nadika(Fraction(sid["n"])), standard)
    if kind != "modern":
        raise DateSyntaxError(f"no engine {kind!r}")
    if mod is None:
        raise DateSyntaxError(
            f"{text!r}: a modern instant is <date>T<hh>:<mm>[:<ss>]/<standard> (a civil time); "
            "nāḍikās after sunrise belong to a siddhantic preset"
        )
    if mod["std"] != standard:
        raise DateSyntaxError(f"{text!r}: the instant names {mod['std']}; the run is on {standard}")
    h, m = int(mod["h"]), int(mod["m"])
    sec = Fraction(mod["s"] or 0)
    if h >= HOURS_PER_DAY or m >= SECONDS_PER_MINUTE or sec >= SECONDS_PER_MINUTE:
        raise DateSyntaxError(f"{text!r}: the time is outside the civil day")
    seconds = h * SECONDS_PER_HOUR + m * SECONDS_PER_MINUTE + sec
    jdn = jdn_of(parse_cli_date(mod["date"]))
    fraction = float(seconds / SECONDS_PER_DAY)
    if fraction >= 1:  # the seconds round to the next midnight as a float
        raise DateSyntaxError(f"{text!r}: the time rounds to the next day's midnight")
    return ModernCivilInstant(jdn, fraction, standard)
