"""The sources registry, ``data/sources.yaml``.

Each source name maps to its title, edition, the held files with their
SHA-256, ``born_digital`` per file and for the source, and
``verified_basis``: ``durable``, ``scan_sufficient``, ``scan_pending`` or
``excluded`` (karanapaddhati_2018 and tantrasangraha_2011, which are read and keyed from but never
witness ``verified``). A source that is not held carries ``gap``. Online
tables have their own entries whose fields the fetching package fills.

The file is validated against ``schema/sources.schema.json``; a malformed
entry is a hard error naming the id.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema

from jyotirganita.data.yamlio import load_exact

__all__ = [
    "DEFAULT_PATH",
    "EXCLUDED_BY_POLICY",
    "Source",
    "SourcesError",
    "load_sources",
    "schema",
]

DEFAULT_PATH = Path(__file__).resolve().parent / "sources.yaml"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "sources.schema.json"

# The copies without an established licence.
EXCLUDED_BY_POLICY = frozenset({"karanapaddhati_2018", "tantrasangraha_2011"})


class SourcesError(ValueError):
    """A malformed sources registry."""


@dataclass(frozen=True, slots=True)
class Source:
    """One registry entry as the datum loader and the ledger use it."""

    id: str
    kind: str
    title: str
    held: bool
    born_digital: bool | None
    verified_basis: str | None
    files: tuple[dict[str, Any], ...]
    page_map: tuple[dict[str, Any], ...]

    @property
    def excluded(self) -> bool:
        return self.verified_basis == "excluded"


@cache
def schema(name: str) -> dict[str, Any]:
    """A JSON Schema of ``jyotirganita/data/schema/`` by file stem."""
    path = Path(__file__).resolve().parent / "schema" / f"{name}.schema.json"
    with path.open("rb") as fh:
        doc: dict[str, Any] = json.load(fh)
    return doc


def _validate(doc: object, path: Path) -> None:
    validator = jsonschema.Draft202012Validator(schema("sources"))
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    if errors:
        e = errors[0]
        where = "/".join(str(p) for p in e.absolute_path) or "(top)"
        raise SourcesError(f"{path}: {where}: {e.message}")


def load_sources(path: Path = DEFAULT_PATH) -> dict[str, Source]:
    """Load and validate the registry, keyed by id."""
    doc = load_exact(path)
    _validate(doc, path)
    out: dict[str, Source] = {}
    for sid, e in doc["sources"].items():
        if e["kind"] == "online":
            # the fetched files of the record (url, sha256, ...): the primary and any more_files
            fetched: list[dict[str, Any]] = []
            if e["sha256"] is not None:
                fetched.append({k: e[k] for k in ("url", "fetched", "sha256", "query")})
            fetched.extend(e.get("more_files", ()))
            out[sid] = Source(sid, "online", e["title"], False, None, None, tuple(fetched), ())
            continue
        held = bool(e["held"])
        if held and not (e["files"] or e.get("mirror")):
            raise SourcesError(f"{sid}: held but lists no file and no mirror")
        if not held and ("gap" not in e or e["files"]):
            raise SourcesError(f"{sid}: a source that is not held carries gap and no files")
        if held and e["born_digital"] is None:
            raise SourcesError(f"{sid}: a held source states born_digital")
        if (sid in EXCLUDED_BY_POLICY) != (e["verified_basis"] == "excluded"):
            raise SourcesError(
                f"{sid}: verified_basis excluded is exactly the list of copies without an "
                f"established licence "
                f"{sorted(EXCLUDED_BY_POLICY)}"
            )
        pdf_flags = [f["born_digital"] for f in e["files"] if "born_digital" in f]
        if pdf_flags and e["born_digital"] != all(pdf_flags):
            raise SourcesError(f"{sid}: born_digital is true only when every PDF is")
        out[sid] = Source(
            sid,
            "library",
            e["title"],
            held,
            e["born_digital"],
            e["verified_basis"],
            tuple(e["files"]),
            tuple(e.get("page_map", ())),
        )
    return out
