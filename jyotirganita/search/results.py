"""Candidates and their serialisation.

A :class:`Candidate` is one civil day the search returns: its class (``match``, every ``require``
constraint holds; ``near_miss``, all but at
most ``max_misses`` hold), the day-record fields the constraints
touched (with the civil-day boundaries and the era dates, so that a
caller sees when another day convention would move it), one entry per
constraint (``matched``, the evidence, and the margin when it failed, in
the query's units), ``misses`` on a near miss, the flags,
and the provenance block (the run's, plus the reading profile, the
query's SHA-256, the derived records used and the pruning summary).

:func:`dumps` writes a candidate in the records' canonical form
as far as it is fixed: the keys of each object in the order
``search/candidate.schema.json`` lists them and sorted where it lists
none, separators ``(',', ':')``, ASCII escapes, ``flags`` sorted, exact
values as ``{"exact": "num/den"}`` (the denominator always written, the
sign on the numerator) under ``numeric: exact`` and floats in shortest
round-trip form under ``numeric: float``, NaN and Infinity refused.
:func:`write_jsonl` writes one candidate per line, in binary, ``\\n``
ended. The writer is ``io/jsonl.py``, shared with the day record; what a
candidate carries is fixed here.

No ``math``, ``numpy`` or ``decimal`` import.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from typing import Any, BinaryIO

from jyotirganita.io import jsonl

__all__ = ["Candidate", "candidate_schema", "comparable", "dumps", "to_json", "write_jsonl"]


@cache
def candidate_schema() -> Mapping[str, Any]:
    """``search/candidate.schema.json``, parsed (its ``properties`` order is the key order)."""
    text = (
        resources.files("jyotirganita.search").joinpath("candidate.schema.json").read_text("utf-8")
    )
    doc: Mapping[str, Any] = json.loads(text)
    return doc


@dataclass(frozen=True, slots=True)
class Candidate:
    """One civil day the search returns (module docstring)."""

    cls: str
    method_id: str
    numeric: str
    dates: Mapping[str, Any]
    fields: Mapping[str, Any]
    constraints: tuple[Mapping[str, Any], ...]
    misses: tuple[Mapping[str, Any], ...]
    flags: tuple[str, ...]
    provenance: Mapping[str, Any] = field(default_factory=dict)

    @property
    def jdn(self) -> int:
        return int(self.dates["jdn"])

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "class": self.cls,
            "method_id": self.method_id,
            "numeric": self.numeric,
            "dates": dict(self.dates),
            "fields": dict(self.fields),
            "constraints": [dict(c) for c in self.constraints],
            "flags": sorted(self.flags),
            "provenance": dict(self.provenance),
        }
        if self.cls == "near_miss":
            out["misses"] = [dict(m) for m in self.misses]
        return out


def to_json(c: Candidate) -> dict[str, Any]:
    """The candidate as plain JSON values in canonical key order (module docstring)."""
    out = jsonl.canonical(c.as_dict(), c.numeric, candidate_schema())
    assert isinstance(out, dict)
    return out


def dumps(c: Candidate) -> str:
    """One canonical JSON line (without its ``\\n``)."""
    return jsonl.dumps(c.as_dict(), c.numeric, candidate_schema())


def write_jsonl(candidates: Iterable[Candidate], out: BinaryIO) -> int:
    """Write each candidate as one line; the count written."""
    return jsonl.write_lines((dumps(c) for c in candidates), out)


def comparable(c: Candidate) -> dict[str, Any]:
    """What two paths must agree on: the candidate without its provenance."""
    out = to_json(c)
    out.pop("provenance")
    return out
