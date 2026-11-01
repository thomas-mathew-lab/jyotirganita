"""File hashing for provenance and tier records.

The canonical serialisation of records and of the configuration hash is ``io/jsonl.py``'s and
``methods/presets.py``'s; this module holds the file-set hash that the
tier records, the derived records and ``parameters_sha256`` share.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

__all__ = ["file_sha256", "files_digest"]


def file_sha256(path: Path) -> str:
    """The hex SHA-256 of the bytes of ``path``."""
    with Path(path).open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def files_digest(entries: Iterable[tuple[str, str]]) -> str:
    """The hash of a set of files given as ``(relative path, sha256)`` pairs.

    Definition: the SHA-256 of the UTF-8 lines ``<path>\\0<sha256>\\n`` in
    sorted path order, written ``sha256:<hex>``. Paths use ``/`` and are
    relative to the repository root, so the digest is the same on every
    platform.
    """
    h = hashlib.sha256()
    for rel, digest in sorted(entries):
        if "\\" in rel or rel.startswith("/"):
            raise ValueError(f"not a relative POSIX path: {rel!r}")
        h.update(f"{rel}\0{digest}\n".encode())
    return f"sha256:{h.hexdigest()}"
