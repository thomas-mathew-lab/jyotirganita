"""Derived records: their own loader, never the datum loader.

A derived record is a quantity the project computes from its own data —
neither read from a page nor chosen as an engine parameter — written by a
named tool into ``jyotirganita/data/derived/<file>.yaml`` (a list of
records, ``derived.schema.json``). The first are the search's planet step
bounds (``tools/step_scan.py``), one record per method
and body, keyed ``derived.search.step_bound.<method>.<body>``.

:func:`load_derived` refuses, as hard errors: a record the schema
rejects (a field missing or unknown), a key defined twice, a value or a
maximum that is not exact (an integer, a ratio ``num/den`` or a decimal
string, parsed exactly), and a method the registry lacks. Each record
lists the files its producing run loaded with their SHA-256 and the
digest of that list (``parameters_sha256``, exactly as the method's
provenance block computes it); :func:`hash_status` compares the listed
files with the files on disk (``current`` or ``stale: <reason>``), and
the search compares the digest with the run it serves before pruning on
the record. The firewall reads the same files through
``data/firewall.py``'s ``load_derived_index`` (key and value only), and
the ledger lists the records in a section of their own.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import jsonschema

from jyotirganita.data.datum import context_for
from jyotirganita.data.yamlio import load_exact
from jyotirganita.methods.registry import load_registry
from jyotirganita.provenance.hashing import file_sha256, files_digest

__all__ = [
    "DERIVED_DIR",
    "DerivedError",
    "DerivedRecord",
    "hash_status",
    "load_derived",
    "step_bound_key",
]

DERIVED_DIR = ("jyotirganita", "data", "derived")
SCHEMA = ("jyotirganita", "data", "schema", "derived.schema.json")
STEP_BOUND = "derived.search.step_bound"


class DerivedError(ValueError):
    """A derived record that does not load."""


@dataclass(frozen=True, slots=True)
class DerivedRecord:
    """One derived record, its value and maxima exact (module docstring)."""

    key: str
    value: Fraction
    method: str
    body: str
    observer: str
    procedures: Mapping[str, Any]
    intraday: str
    from_jdn: int
    to_jdn: int
    data_files: Mapping[str, str]
    parameters_sha256: str
    scanned_on: str
    path: str
    raw: Mapping[str, Any]


def step_bound_key(method: str, body: str) -> str:
    return f"{STEP_BOUND}.{method}.{body}"


def _exact(v: Any, where: str) -> Fraction:
    if isinstance(v, bool) or not isinstance(v, int | str):
        raise DerivedError(f"{where}: {v!r} is not an exact value (an integer or a string)")
    try:
        return Fraction(v)
    except (ValueError, ZeroDivisionError):
        raise DerivedError(f"{where}: {v!r} is not an exact value") from None


def _plain(doc: Any) -> Any:
    """The document as JSON values (a date YAML parsed back to its text)."""
    return json.loads(json.dumps(doc, default=str))


def load_derived(repo: Path, root: Path | None = None) -> dict[str, DerivedRecord]:
    """Every derived record under ``jyotirganita/data/derived/``, by key (module docstring).

    ``root`` reads the record files from another directory (the tests'),
    with the schema and the registry still ``repo``'s.
    """
    root = repo.joinpath(*DERIVED_DIR) if root is None else root
    out: dict[str, DerivedRecord] = {}
    if not root.is_dir():
        return out
    schema = json.loads(repo.joinpath(*SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    registry = load_registry(
        repo / "jyotirganita" / "methods" / "registry.yaml", context_for(repo).sources
    )
    for path in sorted(root.glob("*.yaml")):
        rel = path.relative_to(repo).as_posix() if path.is_relative_to(repo) else path.name
        doc = _plain(load_exact(path))
        errors = list(validator.iter_errors(doc))
        if errors:
            e = jsonschema.exceptions.best_match(errors) or errors[0]
            where = "/".join(str(p) for p in e.absolute_path)
            raise DerivedError(f"{rel}: {where}: {e.message}")
        for i, r in enumerate(doc):
            where = f"{rel}: record {i} ({r['key']})"
            if r["key"] in out:
                raise DerivedError(f"{where}: key defined twice")
            if r["key"] != step_bound_key(r["method"], r["body"]):
                raise DerivedError(f"{where}: the key names another method or body")
            if r["method"] not in registry:
                raise DerivedError(f"{where}: no method {r['method']!r} in the registry")
            if r["range"]["to_jdn"] < r["range"]["from_jdn"]:  #
                raise DerivedError(f"{where}: the scanned range ends before it starts")
            value = _exact(r["value"], f"{where}: value")
            maxima = [r["sunrise_step_max"]["value"]]
            if r["motion_max"] != "not_served":
                maxima.append(r["motion_max"]["value"])
            for m in maxima:
                if _exact(m, f"{where}: maximum") > value:
                    raise DerivedError(f"{where}: a maximum exceeds the bound")
            out[r["key"]] = DerivedRecord(
                r["key"],
                value,
                r["method"],
                r["body"],
                r["observer"],
                r["procedures"],
                r["intraday"],
                r["range"]["from_jdn"],
                r["range"]["to_jdn"],
                r["data_files"],
                r["parameters_sha256"],
                r["scanned_on"],
                rel,
                r,
            )
    return out


def hash_status(repo: Path, rec: DerivedRecord) -> str:
    """``current``, or ``stale: <reason>`` when a listed file changed or the digest disagrees."""
    if files_digest(rec.data_files.items()) != rec.parameters_sha256:
        return "stale: parameters_sha256 is not the digest of the listed files"
    for rel, digest in sorted(rec.data_files.items()):
        p = repo / rel
        if not p.is_file():
            return f"stale: {rel} is missing"
        if file_sha256(p) != digest:
            return f"stale: {rel} changed"
    return "current"
