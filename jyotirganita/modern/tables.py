"""The verified loader of the fetched tables under ``data/tables/``.

Every table the modern engine reads from a fetched file (a closed list:
the IERS series and leap seconds, the ΔT tables, the
precession and nutation coefficients, the Hipparcos extract) is a small
extract written by a script under ``tools/extract_*.py`` with a ``fetch``
header: the source id, the fetched file's SHA-256, the script and its
version, and what was extracted. :func:`load_table` refuses an extract
whose header is missing or incomplete, whose source is not in the sources
registry, or whose recorded hash (or a companion file's, such as the
obliquity table beside the longitude table) is not a file recorded on that source
(``data/sources.yaml``): an extract never loads without the fetch it
claims. These values carry no ``read`` block; they are not page reads and
never a second witness for one.

:func:`number` turns a printed coefficient (an exact decimal string, with
a Unicode minus or an exponent where the source prints one) into the
float the modern engine computes with; the modern engine is the only
place floats meet the data.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from jyotirganita.core.exact import parse_fraction
from jyotirganita.data.sources import Source, load_sources
from jyotirganita.data.yamlio import load_exact

__all__ = ["TABLES_DIR", "FetchedTable", "TableError", "load_table", "number"]

TABLES_DIR = Path(__file__).resolve().parent.parent / "data" / "tables"
UNICODE_MINUS = "−"
_HEADER = ("source", "sha256", "script", "script_version", "extracted")


class TableError(RuntimeError):
    """A fetched-table extract that may not load (a hard error)."""


@dataclass(frozen=True, slots=True)
class FetchedTable:
    """A verified extract: its name, fetch header, body and the extract file's own hash.

    ``instance`` (the SHA-256 of the extract file) identifies the loaded
    coefficient set, so that two values computed from different files are
    never combined (the nutation-model identity).
    """

    name: str
    source: str
    fetched_sha256: str
    script: str
    script_version: int
    body: Mapping[str, Any]
    path: Path
    instance: str

    def __getitem__(self, key: str) -> Any:
        try:
            return self.body[key]
        except KeyError:
            raise TableError(f"{self.path.name}: no field {key!r}") from None


def number(printed: object) -> float:
    """A printed coefficient as a float (U+2212 minus, a ratio and an exponent accepted).

    An integer passes through; a string is the decimal or ratio as printed,
    read exactly first (``core/exact.py``) and only then rounded to a
    float; exponent notation, which the exact parser refuses, is read by
    ``float``. Anything else is refused rather than guessed.
    """
    if isinstance(printed, bool):
        raise TableError("a boolean is not a coefficient")
    if isinstance(printed, int):
        return float(printed)
    if isinstance(printed, str):
        text = printed.strip().replace(UNICODE_MINUS, "-").lstrip("+")
        try:
            return float(parse_fraction(text))
        except ValueError:
            pass
        try:
            value = float(text)
        except ValueError:
            raise TableError(f"not a printed number: {printed!r}") from None
        if value - value != 0:  # inf or nan
            raise TableError(f"not a finite printed number: {printed!r}")
        return value
    raise TableError(f"not a printed number: {printed!r}")


@cache
def _sources() -> Mapping[str, Source]:
    return load_sources()


def load_table(name: str, *, directory: Path = TABLES_DIR) -> FetchedTable:
    """The extract ``data/tables/<name>.yaml``, its fetch header checked against the registry."""
    path = directory / f"{name}.yaml"
    if not path.is_file():
        raise TableError(f"no fetched table {name!r} ({path})")
    raw = path.read_bytes()
    doc = load_exact(path)
    if not isinstance(doc, dict) or doc.get("table") != name:
        raise TableError(f"{path.name}: not the extract {name!r} (table: {name})")
    fetch = doc.get("fetch")
    if not isinstance(fetch, dict):
        raise TableError(f"{path.name}: no fetch header")
    missing = [f for f in _HEADER if fetch.get(f) in (None, "")]
    if missing:
        raise TableError(f"{path.name}: the fetch header lacks {missing}")
    source = _sources().get(fetch["source"])
    if source is None:
        raise TableError(f"{path.name}: source {fetch['source']!r} is not in data/sources.yaml")
    recorded = {f.get("sha256") for f in source.files}
    # the fetched file and every companion file the header names (an
    # obliquity table, a statement PDF, a readme); an archive member's hash
    # (``member_sha256``) is inside a recorded file, not a file of its own
    companions = [
        k for k in fetch if k == "sha256" or (k.endswith("_sha256") and k != "member_sha256")
    ]
    for k in companions:
        if fetch[k] not in recorded:
            raise TableError(
                f"{path.name}: the fetch header's {k} {fetch[k]} is not a file recorded "
                f"on {source.id}"
            )
    script = str(fetch["script"])
    if not (script.startswith("tools/extract_") and script.endswith(".py")):
        raise TableError(f"{path.name}: the extracting script is tools/extract_*.py, not {script}")
    body = {k: v for k, v in doc.items() if k not in ("table", "fetch")}
    return FetchedTable(
        name,
        source.id,
        str(fetch["sha256"]),
        script,
        int(fetch["script_version"]),
        body,
        path,
        hashlib.sha256(raw).hexdigest(),
    )
