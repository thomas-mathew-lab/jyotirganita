"""Loader for ``data/engine_parameters.yaml``.

A malformed entry, a missing field, an unknown field, a float value or a
key used twice is a hard error naming the key.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from jyotirganita.core.exact import parse_fraction
from jyotirganita.data.yamlio import PrintedNumber, load_exact

__all__ = ["DEFAULT_PATH", "KINDS", "EngineParameter", "EngineParameterError", "load", "seed"]

DEFAULT_PATH = Path(__file__).resolve().parent / "engine_parameters.yaml"

KINDS = frozenset(
    {
        "seed",
        "scan_step",
        "tolerance",
        "iteration_cap",
        "resolution",
        "horizon",
        "quantum",
        "factor",
    }
)
_FIELDS = frozenset({"key", "kind", "value", "unit", "justification", "used_by"})


class EngineParameterError(ValueError):
    """A malformed ``engine_parameters.yaml``."""


@dataclass(frozen=True, slots=True)
class EngineParameter:
    """One engine parameter; ``value`` is exact."""

    key: str
    kind: str
    value: Fraction
    unit: str
    justification: str
    used_by: tuple[str, ...]


def _value(key: str, raw: object) -> Fraction:
    if isinstance(raw, bool):
        raise EngineParameterError(f"{key}: a boolean is not a parameter value")
    if isinstance(raw, int):
        return Fraction(raw)
    if isinstance(raw, PrintedNumber):
        raise EngineParameterError(
            f"{key}: write a non-integer value as a quoted exact decimal or ratio, not a float"
        )
    if isinstance(raw, str):
        try:
            return parse_fraction(raw)
        except ValueError as exc:
            raise EngineParameterError(f"{key}: {exc}") from None
    raise EngineParameterError(f"{key}: value must be an int or an exact string")


def load(path: Path = DEFAULT_PATH) -> dict[str, EngineParameter]:
    """Load and validate the engine parameters, keyed by ``key``."""
    doc = load_exact(path)
    if not isinstance(doc, dict) or set(doc) != {"parameters"}:
        raise EngineParameterError(f"{path}: the file holds one mapping, 'parameters'")
    entries = doc["parameters"]
    if not isinstance(entries, list):
        raise EngineParameterError(f"{path}: 'parameters' is a list")
    out: dict[str, EngineParameter] = {}
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            raise EngineParameterError(f"{path}: entry {i} is not a mapping")
        key = e.get("key")
        if not isinstance(key, str) or not key:
            raise EngineParameterError(f"{path}: entry {i} has no key")
        missing, extra = _FIELDS - set(e), set(e) - _FIELDS
        if missing:
            raise EngineParameterError(f"{key}: missing field(s) {sorted(missing)}")
        if extra:
            raise EngineParameterError(f"{key}: unknown field(s) {sorted(extra)}")
        if key in out:
            raise EngineParameterError(f"{key}: key used twice")
        if e["kind"] not in KINDS:
            raise EngineParameterError(f"{key}: kind {e['kind']!r} is not one of {sorted(KINDS)}")
        value = _value(key, e["value"])
        if e["kind"] == "seed" and (value.denominator != 1 or value < 0):
            raise EngineParameterError(f"{key}: a seed is a non-negative integer")
        if e["kind"] == "factor" and not value > 1:
            raise EngineParameterError(f"{key}: a factor widens a bound: a rational above one")
        for name in ("unit", "justification"):
            if not isinstance(e[name], str) or not e[name].strip():
                raise EngineParameterError(f"{key}: {name} is a non-empty string")
        used_by = e["used_by"]
        if not isinstance(used_by, list) or not all(isinstance(u, str) for u in used_by):
            raise EngineParameterError(f"{key}: used_by is a list of strings")
        out[key] = EngineParameter(
            key, e["kind"], value, e["unit"], e["justification"].strip(), tuple(used_by)
        )
    return out


def seed(key: str, path: Path = DEFAULT_PATH) -> int:
    """The integer seed ``key``; a missing key or a non-seed entry is an error.

    Every sampling test takes its seed through this function.
    """
    params = load(path)
    if key not in params:
        raise EngineParameterError(f"{key}: no such engine parameter")
    p = params[key]
    if p.kind != "seed":
        raise EngineParameterError(f"{key}: kind is {p.kind}, not seed")
    return p.value.numerator
