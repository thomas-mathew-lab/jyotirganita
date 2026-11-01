"""A text's data as the siddhantic engine reads it.

:class:`TextData` holds the datums of one text directory
``jyotirganita/data/texts/<text>/`` by key, as the datum loader accepted
them (an emendation's adopted value, the sign applied, the form parsed).
Every datum the engine reads is noted, so that a record carries the flags
of exactly the data it used (``provisional:<key>``)
and its provenance lists the files they came from.

Keys are ``texts.<text>.<suffix>``; the engine names the suffix. A missing
key or a gap where a value is needed is a hard error naming the key: nothing is defaulted.

A method defined by ``replaces`` reads, under each replaced
key, the datum that stands in its place: the engine names the base key and
receives the replacement, which is what the record's flags and provenance
name (``used`` is keyed by the datum read).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from fractions import Fraction

from jyotirganita.data.datum import Record

__all__ = ["MissingDatum", "TextData"]


class MissingDatum(LookupError):
    """A datum the engine needs is absent or a gap."""


class TextData:
    """The data of one text, by key suffix, with the keys read recorded."""

    def __init__(
        self,
        text: str,
        records: Mapping[str, Record],
        replaces: Mapping[str, str] | None = None,
    ) -> None:
        self.text = text
        self.prefix = f"texts.{text}."
        self._records = {k: r for k, r in records.items() if k.startswith(self.prefix)}
        own = dict(self._records)  # each replacement reads the text's own datum, in any order
        for old, new in (replaces or {}).items():
            if old not in own or new not in own:
                raise MissingDatum(f"replaces {old} by {new}: both are data of {self.text}")
            if new in (replaces or {}):
                # a chain would depend on the order of the mapping
                raise MissingDatum(f"replaces {old} by {new}, which is itself replaced")
            self._records[old] = own[new]
        self._used: dict[str, Record] = {}

    def key(self, suffix: str) -> str:
        """The full key of ``suffix``."""
        return self.prefix + suffix

    def has(self, suffix: str) -> bool:
        """Whether a non-gap datum ``suffix`` exists (not recorded as used)."""
        r = self._records.get(self.key(suffix))
        return r is not None and r.kind != "gap"

    def record(self, suffix: str) -> Record:
        """The datum ``suffix``, recorded as used; a gap or an absence is an error."""
        key = self.key(suffix)
        r = self._records.get(key)
        if r is None:
            raise MissingDatum(f"{key}: no such datum in data/texts/{self.text}/")
        if r.kind == "gap":
            raise MissingDatum(f"{key}: the datum is a gap ({r.raw.get('reason', '')})")
        self._used[r.key] = r
        return r

    def integer(self, suffix: str) -> int:
        """An integer datum."""
        v = self.record(suffix).value
        if isinstance(v, bool) or not isinstance(v, int):
            raise TypeError(f"{self.key(suffix)}: not an integer ({v!r})")
        return v

    def fraction(self, suffix: str) -> Fraction:
        """An integer or fraction datum, as a ``Fraction`` (its sign applied)."""
        v = self.record(suffix).value
        if isinstance(v, bool) or not isinstance(v, int | Fraction):
            raise TypeError(f"{self.key(suffix)}: not a number ({v!r})")
        return Fraction(v)

    def records_with(self, field_name: str) -> Iterable[Record]:
        """Every datum carrying ``field_name`` (procedure data: ``procedure``)."""
        seen: dict[str, Record] = {}
        for r in self._records.values():  # a replacement appears under two keys: once here
            if field_name in r.raw:
                seen.setdefault(r.key, r)
        return iter(seen.values())

    def mark_used(self, record: Record) -> None:
        """Record ``record`` (a datum of this text) as used."""
        if record.key not in self._records:
            raise MissingDatum(f"{record.key} is not a datum of {self.text}")
        self._used[record.key] = record

    @property
    def held(self) -> Mapping[str, Record]:
        """Every datum held, by key; a replaced key holds its replacement. Not recorded as used."""
        return dict(self._records)

    @property
    def used(self) -> Mapping[str, Record]:
        """The data read so far, by key."""
        return dict(self._used)
