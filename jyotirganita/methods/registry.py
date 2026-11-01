"""The method registry, ``methods/registry.yaml``.

A method is a data record: ``id``, ``engine``, ``text`` (a parameter-set
directory under ``data/texts/``) or ``base`` plus ``layers`` and, for a
recension differing in named data, ``replaces`` (a base datum key to the
key of the datum of the same text that stands in its place), ``variants``
(each value with its cited ``composed`` year datum), ``procedures``,
``composed`` (the year datum of the text, or ``not_applicable`` for the
modern engine), ``status`` and ``sources``. Every one of these is present
(no hidden defaults). ``packages``, the development record's names for the
work that built the method, is read by the ledger, which holds a method
without them unreviewed; the engine ignores it. ``runs_from`` is derived
from the data by the engine and printed by the ledger, never typed: a
registry that writes it
fails to load. ``status`` is computed by the ledger from
the verification criteria; a written value that differs from the
computed one fails to load (:func:`load_registry` with ``computed``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

from jyotirganita.data.sources import Source, schema
from jyotirganita.data.yamlio import load_exact

__all__ = ["DEFAULT_PATH", "Method", "RegistryError", "load_registry"]

DEFAULT_PATH = Path(__file__).resolve().parent / "registry.yaml"


class RegistryError(ValueError):
    """A malformed registry entry, or a written status the ledger does not compute."""


@dataclass(frozen=True, slots=True)
class Method:
    """One registry entry."""

    id: str
    engine: str
    text: str | None  # a based method's is its base's
    base: str | None
    layers: tuple[str, ...]
    replaces: Mapping[str, str]  # base datum key -> the key standing in its place
    status: str
    sources: tuple[str, ...]
    packages: tuple[str, ...]
    composed: str | None
    raw: Mapping[str, Any]


def load_registry(
    path: Path,
    sources: Mapping[str, Source],
    computed: Mapping[str, tuple[str, str | None]] | None = None,
) -> dict[str, Method]:
    """Load and check the registry.

    ``computed`` maps a method id to the ledger's ``(status, first unmet
    criterion)``; when given, a written status that differs fails.
    """
    doc = load_exact(path)
    if isinstance(doc, dict) and isinstance(doc.get("methods", []), list):
        # a malformed methods list is left to the schema's RegistryError
        for i, entry in enumerate(doc.get("methods", [])):
            if isinstance(entry, dict) and "runs_from" in entry:
                raise RegistryError(
                    f"{path}: {entry.get('id', i)}: runs_from is derived from the epoch datum "
                    "and printed by the ledger, never typed"
                )
    errors = list(jsonschema.Draft202012Validator(schema("registry")).iter_errors(doc))
    if errors:
        e = jsonschema.exceptions.best_match(errors) or errors[0]
        where = "/".join(str(p) for p in e.absolute_path) or "(top)"
        raise RegistryError(f"{path}: {where}: {e.message}")
    out: dict[str, Method] = {}
    for entry in doc["methods"]:
        mid = entry["id"]
        if mid in out:
            raise RegistryError(f"{path}: {mid}: id used twice")
        has_text, has_base = "text" in entry, "base" in entry
        if has_text == has_base or has_base != ("layers" in entry):
            raise RegistryError(
                f"{path}: {mid}: a method names text, or base with layers, never both"
            )
        if "replaces" in entry and not has_base:
            raise RegistryError(
                f"{path}: {mid}: replaces names data of a base method; a method with "
                "text replaces nothing"
            )
        if has_base and not entry["layers"] and "replaces" not in entry:
            raise RegistryError(
                f"{path}: {mid}: a method on a base names a layer or a replaced datum; "
                "with neither it is its base"
            )
        replaces = dict(entry.get("replaces", {}))
        if len(set(replaces.values())) != len(replaces) or set(replaces) & set(replaces.values()):
            raise RegistryError(
                f"{path}: {mid}: replaces maps each datum to its own replacement, "
                "and no replacement is itself replaced"
            )
        for sid in entry["sources"]:
            if sid not in sources:
                raise RegistryError(f"{path}: {mid}: source {sid} is not in sources.yaml")
        if (entry["engine"] == "modern") != (entry["composed"] == "not_applicable"):
            raise RegistryError(
                f"{path}: {mid}: a siddhantic method names its composed year datum; "
                "a modern one writes composed: not_applicable"
            )
        composed = None if entry["composed"] == "not_applicable" else entry["composed"]
        out[mid] = Method(
            mid,
            entry["engine"],
            entry.get("text"),
            entry.get("base"),
            tuple(entry.get("layers", ())),
            replaces,
            entry["status"],
            tuple(entry["sources"]),
            tuple(entry.get("packages", ())),
            composed,
            entry,
        )
    for m in out.values():
        if m.base is not None:
            if m.base not in out:
                raise RegistryError(f"{path}: {m.id}: base {m.base} is not a registry entry")
            base = out[m.base]
            if base.base is not None:
                raise RegistryError(f"{path}: {m.id}: base {m.base} is itself based")
            prefix = f"texts.{base.text}."
            for old, new in m.replaces.items():
                if not (old.startswith(prefix) and new.startswith(prefix)):
                    raise RegistryError(
                        f"{path}: {m.id}: replaces {old} by {new}: both are data of the "
                        f"base's text {base.text}"
                    )
            out[m.id] = Method(
                m.id,
                m.engine,
                base.text,
                m.base,
                m.layers,
                m.replaces,
                m.status,
                m.sources,
                m.packages,
                m.composed,
                m.raw,
            )
    if computed is not None:
        for m in out.values():
            status, unmet = computed.get(m.id, ("provisional", "not computed"))
            if m.status != status:
                raise RegistryError(
                    f"{path}: {m.id}: written {m.status}, the ledger computes {status}"
                    + (f" (first unmet: {unmet})" if unmet else "")
                    + "; the status is computed, never typed"
                )
    return out
