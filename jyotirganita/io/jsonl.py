"""The canonical JSON form of a record or a candidate.

One serialiser for every line the engine writes: the day record
(``io/record.py``, ``io/record.schema.json``) and the search candidate
(``search/results.py``, ``search/candidate.schema.json``), and the same
form for the configuration hash (``methods/presets.py``, keys sorted
there, since a configuration has no schema of its own).

:func:`canonical` turns a value into plain JSON values:

- the keys of an object in the order its schema's ``properties`` lists
  them, then any key the schema does not list, sorted (an object keyed
  by data, the ``eras`` block keyed by era id, is sorted);
- a ``Fraction`` as ``{"exact": "num/den"}`` (reduced, the denominator
  always written, the sign on the numerator) under ``numeric: exact``,
  and as the nearest double under ``numeric: float``;
- a ``float`` refused under ``numeric: exact`` except inside a subtree
  the schema marks ``"x-derived": true`` (``derived_ut``, ``derived_tt``:
  placements made outside the method), and written
  in shortest round-trip form (Python's ``repr``) everywhere else;
- a :class:`Stated` (an exact value with the text's own form beside it) as ``{"exact": "num/den",
  <form>: [parts],
  "rounding": <datum key>}`` under ``numeric: exact`` and as the double
  of its exact value under ``numeric: float``;
- ``bool``, ``None``, ``int`` and ``str`` as they are; a list in its given
  order (the producer fixes it: ``flags`` sorted, the occurrence rows in
  time order).

:func:`dumps` writes one line: separators ``(',', ':')``, ASCII escapes,
NaN and Infinity refused. :func:`write_lines` writes lines in binary,
each ended by ``\\n``. The determinism suite compares these bytes, not
parsed numbers, so a float that leaks into the exact path
fails there and in the schema test.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, BinaryIO

__all__ = ["DERIVED", "Stated", "canonical", "dumps", "write_lines"]

#: the schema keyword marking a subtree whose floats an exact record may carry
DERIVED = "x-derived"


@dataclass(frozen=True, slots=True)
class Stated:
    """An exact value with the text's own form as the text's rounding rule produces it.

    ``form`` is ``nadika`` (``[ghaṭī, vighaṭī, asu]``) or ``rdms``; ``rounding``
    is the key of the datum stating the rule. The exact
    value is never rounded; the parts are the text's printed form of it.
    """

    exact: Fraction
    form: str
    parts: tuple[int, ...]
    rounding: str


class _Walk:
    """One serialisation: the schema's ``$defs`` and the record's numeric family."""

    def __init__(self, root: Mapping[str, Any], numeric: str) -> None:
        if numeric not in ("exact", "float"):
            raise ValueError(f"numeric is exact or float, not {numeric!r}")
        self.defs: Mapping[str, Any] = root.get("$defs", {})
        self.numeric = numeric

    def resolve(self, spec: Any) -> Mapping[str, Any] | None:
        """The schema node ``spec`` names, following one ``$ref`` at a time."""
        seen = 0
        while isinstance(spec, Mapping) and "$ref" in spec:
            name = str(spec["$ref"]).rpartition("/")[2]
            spec = self.defs.get(name)
            seen += 1
            if seen > len(self.defs) + 1:  # pragma: no cover - a cyclic schema
                raise ValueError("the schema's $ref chain does not end")
        return spec if isinstance(spec, Mapping) else None

    def branch(self, spec: Mapping[str, Any] | None, v: Any) -> Mapping[str, Any] | None:
        """The branch of a ``oneOf``/``anyOf`` that describes an object or a list value."""
        if spec is None:
            return None
        for key in ("oneOf", "anyOf"):
            options = spec.get(key)
            if not options:
                continue
            want = "object" if isinstance(v, Mapping) else "array"
            for option in options:
                node = self.resolve(option)
                if node is None:
                    continue
                if node.get("type") == want or (want == "object" and "properties" in node):
                    merged = dict(node)
                    if spec.get(DERIVED):
                        merged[DERIVED] = True
                    return merged
            return spec
        return spec

    def value(self, v: Any, spec: Any, derived: bool) -> Any:
        node = self.branch(self.resolve(spec), v)
        derived = derived or bool(node and node.get(DERIVED))
        if isinstance(v, bool) or v is None or isinstance(v, int | str):
            return v
        if isinstance(v, Stated):
            if self.numeric != "exact":
                return float(v.exact)
            q = v.exact
            return {
                "exact": f"{q.numerator}/{q.denominator}",
                v.form: list(v.parts),
                "rounding": v.rounding,
            }
        if isinstance(v, Fraction):
            if self.numeric == "exact":
                return {"exact": f"{v.numerator}/{v.denominator}"}
            return float(v)
        if isinstance(v, float):
            if self.numeric == "exact" and not derived:
                raise ValueError(f"a float {v!r} outside a derived field of a numeric: exact line")
            return v
        if isinstance(v, Mapping):
            props: Mapping[str, Any] = (node or {}).get("properties") or {}
            extra = (node or {}).get("additionalProperties")
            patterns: Mapping[str, Any] = (node or {}).get("patternProperties") or {}
            other = next(iter(patterns.values()), extra if isinstance(extra, Mapping) else None)
            keys = [k for k in props if k in v] + sorted(k for k in v if k not in props)
            return {k: self.value(v[k], props.get(k, other), derived) for k in keys}
        if isinstance(v, list | tuple):
            items = (node or {}).get("items")
            return [self.value(x, items, derived) for x in v]
        raise TypeError(f"{type(v).__name__} is not serialisable in a canonical line")


def canonical(v: Any, numeric: str, schema: Mapping[str, Any]) -> Any:
    """``v`` as plain JSON values in the canonical form (module docstring)."""
    return _Walk(schema, numeric).value(v, schema, False)


def dumps(v: Any, numeric: str, schema: Mapping[str, Any]) -> str:
    """One canonical JSON line, without its ``\\n``."""
    return json.dumps(
        canonical(v, numeric, schema), separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def write_lines(lines: Iterable[str], out: BinaryIO) -> int:
    """Write each line in binary, ``\\n`` ended; the count written."""
    n = 0
    for line in lines:
        out.write(line.encode("ascii") + b"\n")
        n += 1
    return n
