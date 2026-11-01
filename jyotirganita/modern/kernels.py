"""The kernel registry and the verified kernel loader.

``data/tables/kernels.yaml`` records, for each JPL DE kernel the engine may
load, its official URL, byte size, SHA-256 and time span. A kernel without
a registry entry never loads; a file whose size or hash differs from its
entry never loads; a kernel whose hash has not been recorded from a
verified fetch (``sha256: null``) never loads. Kernels live in the
git-ignored ``data/ephemerides/`` directory of the installed package, or in
the folder the environment variable ``JYOTIRGANITA_KERNEL_DIR`` names
(:func:`kernel_directory`), fetched once by ``jyotirganita fetch-kernel``
(:func:`fetch`) and never at run time. The folder changes no computed value:
a kernel loads only when its size and SHA-256 equal its registry entry,
wherever it lies, and the folder is not part of a record.

The span is read from the kernel's own segment summaries at the verified
fetch (the earliest start and latest end over the segments the engine
uses) and recorded in the registry as Julian dates in the kernel's time
argument (TDB, taken as TT, ``modern.timescales.teph_tdb.statement``).

:class:`Ephemeris` evaluates a verified kernel's SPK segments (Chebyshev,
type 2) through jplephem and refuses an instant outside the registry's
span. The bodies are named as the kernel's own comment area names them
(``MOON (301)``): the integer ids are read from that list, so the engine
holds no NAIF number. Positions are barycentric (the chain of segments to
the solar-system barycentre), in kilometres and kilometres per day.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import urllib.request
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from jplephem.spk import SPK

from jyotirganita.core.exact import parse_fraction
from jyotirganita.data.yamlio import load_exact

__all__ = [
    "EPHEMERIDES_DIR",
    "KERNEL_DIR_VARIABLE",
    "REGISTRY_PATH",
    "Ephemeris",
    "KernelEntry",
    "KernelError",
    "download",
    "fetch",
    "kernel_directory",
    "load_registry",
    "sha256_of",
    "verified_path",
]

_DATA = Path(__file__).resolve().parent.parent / "data"
REGISTRY_PATH = _DATA / "tables" / "kernels.yaml"
EPHEMERIDES_DIR = _DATA / "ephemerides"
#: the environment variable that names another folder for the fetched kernels
KERNEL_DIR_VARIABLE = "JYOTIRGANITA_KERNEL_DIR"
#: the NAIF id at which every chain of centres ends
SOLAR_SYSTEM_BARYCENTRE = 0


class KernelError(RuntimeError):
    """A kernel that may not load: no registry entry, a wrong hash, a missing file."""


@dataclass(frozen=True, slots=True)
class KernelEntry:
    """One registry entry; ``sha256`` and the span are ``None`` until a verified fetch."""

    id: str
    url: str
    file: str
    bytes: int
    sha256: str | None
    span_from_jd: Fraction | None
    span_to_jd: Fraction | None
    source: str
    fetched: str | None
    fetched_by: str | None
    notes: str

    @property
    def recorded(self) -> bool:
        """Whether a verified fetch has recorded the hash and the span."""
        return self.sha256 is not None and self.span_from_jd is not None


def _jd(raw: object, where: str) -> Fraction | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return parse_fraction(raw)
    if isinstance(raw, int) and not isinstance(raw, bool):
        return Fraction(raw)
    raise KernelError(f"{where}: a Julian date is an integer or an exact decimal string")


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, KernelEntry]:
    """The registry, keyed by kernel id; a malformed entry is a hard error."""
    doc = load_exact(path)
    if not isinstance(doc, dict) or doc.get("table") != "kernels":
        raise KernelError(f"{path}: not the kernel registry (table: kernels)")
    out: dict[str, KernelEntry] = {}
    need = {"url", "file", "bytes", "sha256", "span", "source", "fetched", "fetched_by", "notes"}
    for kid, raw in doc["kernels"].items():
        if not isinstance(raw, dict) or set(raw) != need:
            raise KernelError(f"{path}: {kid}: an entry has exactly the fields {sorted(need)}")
        span: dict[str, Any] = raw["span"] or {}
        if (span.get("from_jd") is None) != (span.get("to_jd") is None):
            # a span is recorded whole or not at all
            raise KernelError(f"{path}: {kid}: the span records one end only")
        out[kid] = KernelEntry(
            id=kid,
            url=raw["url"],
            file=raw["file"],
            bytes=int(raw["bytes"]),
            sha256=raw["sha256"],
            span_from_jd=_jd(span.get("from_jd"), f"{kid}.span.from_jd"),
            span_to_jd=_jd(span.get("to_jd"), f"{kid}.span.to_jd"),
            source=raw["source"],
            fetched=None if raw["fetched"] is None else str(raw["fetched"]),
            fetched_by=raw["fetched_by"],
            notes=raw["notes"],
        )
    return out


def kernel_directory() -> Path:
    """The folder that holds the fetched kernels.

    The absolute path in ``JYOTIRGANITA_KERNEL_DIR`` when that variable is
    set (a leading ``~`` is the home folder), else the package's own
    ``data/ephemerides/``. A variable set to an empty or another relative
    path is refused, never read as the package folder or
    against the current directory. The folder need not exist yet:
    :func:`fetch` creates it, and :func:`verified_path` names it when a
    kernel is absent.
    """
    raw = os.environ.get(KERNEL_DIR_VARIABLE)
    if raw is None:
        return EPHEMERIDES_DIR
    if raw.strip() == "":
        raise KernelError(f"{KERNEL_DIR_VARIABLE} is set but empty; unset it or name a folder")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise KernelError(
            f"{KERNEL_DIR_VARIABLE}={raw!r} is not an absolute path; name the folder in full"
        )
    return path


def sha256_of(path: Path) -> str:
    """The SHA-256 of a file, read in chunks."""
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def verified_path(
    kernel_id: str,
    *,
    registry: dict[str, KernelEntry] | None = None,
    directory: Path | None = None,
) -> Path:
    """The path of a registered, fetched kernel whose size and hash match its entry.

    Every refusal names the kernel and what is wrong: no entry,
    no recorded hash, the file absent (fetch it with ``jyotirganita fetch-kernel``),
    a size or hash that differs.
    """
    directory = kernel_directory() if directory is None else directory
    reg = registry if registry is not None else load_registry()
    entry = reg.get(kernel_id)
    if entry is None:
        raise KernelError(
            f"kernel {kernel_id!r} has no entry in the kernel registry "
            "(data/tables/kernels.yaml); a kernel without an entry never loads"
        )
    if entry.sha256 is None:
        raise KernelError(
            f"kernel {kernel_id!r}: the registry records no hash yet; it is written only "
            "from a verified fetch"
        )
    path = directory / entry.file
    if not path.is_file():
        raise KernelError(
            f"kernel {kernel_id!r} is not fetched: {path} is absent; run "
            f"`jyotirganita fetch-kernel {kernel_id}` (no fetch happens at run time)"
        )
    size = path.stat().st_size
    if size != entry.bytes:
        raise KernelError(
            f"kernel {kernel_id!r}: {path} has {size} bytes, the registry {entry.bytes}"
        )
    digest = sha256_of(path)
    if digest != entry.sha256:
        raise KernelError(
            f"kernel {kernel_id!r}: SHA-256 {digest} differs from the registry's {entry.sha256}"
        )
    return path


def download(url: str, target: Path) -> int:
    """Stream ``url`` to ``target`` by way of a ``.part`` file; returns the host's Content-Length.

    The length is ``-1`` when the host sends none. Nothing is verified here:
    :func:`fetch` and ``tools/fetch_kernel.py --record`` check what arrived.
    """
    part = target.with_name(target.name + ".part")
    with urllib.request.urlopen(url) as resp:
        length = int(resp.headers.get("Content-Length", "-1"))
        with part.open("wb") as out:
            shutil.copyfileobj(resp, out)
    os.replace(part, target)
    return length


def fetch(
    kernel_id: str,
    *,
    verify_only: bool = False,
    registry: dict[str, KernelEntry] | None = None,
    directory: Path | None = None,
) -> Path:
    """Fetch a registered kernel from its registry URL, once, and verify it.

    The one network operation of the package, run only by the
    ``jyotirganita fetch-kernel`` command, never by a computation. A file
    already present is not fetched again; ``verify_only`` never fetches.
    The kernel is refused before any download when its entry is missing or
    records no hash, and after it when its size or hash differs
    (:func:`verified_path`).
    """
    directory = kernel_directory() if directory is None else directory
    reg = registry if registry is not None else load_registry()
    entry = reg.get(kernel_id)
    if entry is None or entry.sha256 is None:
        return verified_path(kernel_id, registry=reg, directory=directory)
    target = directory / entry.file
    if not verify_only and not target.is_file():
        directory.mkdir(parents=True, exist_ok=True)
        download(entry.url, target)
    return verified_path(kernel_id, registry=reg, directory=directory)


def check_chains(kernel_id: str, parent: dict[int, int]) -> None:
    """Refuse a kernel whose chain of centres from some body cycles or does not end at the
    solar-system barycentre."""
    for body in parent:
        seen = {body}
        node = body
        while node in parent:
            node = parent[node]
            if node in seen:
                raise KernelError(f"kernel {kernel_id}: the centres of body {body} form a cycle")
            seen.add(node)
        if node != SOLAR_SYSTEM_BARYCENTRE:
            raise KernelError(
                f"kernel {kernel_id}: body {body}'s chain of centres ends at {node}, "
                "not the solar-system barycentre"
            )


_BODY = re.compile(r"([A-Z][A-Z]*(?: [A-Z]+)*) \((\d+)\)")


@dataclass(slots=True)
class Ephemeris:
    """A verified kernel, evaluated from its segments (module docstring)."""

    entry: KernelEntry
    path: Path
    spk: Any
    ids: dict[str, int]
    _parent: dict[int, int] = field(default_factory=dict)
    _segments: dict[tuple[int, int], list[Any]] = field(default_factory=dict)

    @classmethod
    def open(
        cls,
        kernel_id: str,
        *,
        registry: dict[str, KernelEntry] | None = None,
        directory: Path | None = None,
    ) -> Ephemeris:
        reg = registry if registry is not None else load_registry()
        path = verified_path(kernel_id, registry=reg, directory=directory)
        spk = SPK.open(str(path))
        present = {s.target for s in spk.segments} | {s.center for s in spk.segments}
        ids: dict[str, int] = {}
        for m in _BODY.finditer(spk.comments()):
            name, num = m.group(1), int(m.group(2))
            if num in present:
                if ids.get(name, num) != num:
                    raise KernelError(f"kernel {kernel_id}: its comment names {name} twice")
                ids[name] = num
        parent: dict[int, int] = {}
        segments: dict[tuple[int, int], list[Any]] = {}
        for seg in spk.segments:
            if parent.get(seg.target, seg.center) != seg.center:
                raise KernelError(f"kernel {kernel_id}: body {seg.target} has two centres")
            parent[seg.target] = seg.center
            segments.setdefault((seg.center, seg.target), []).append(seg)
        for pair in segments.values():
            pair.sort(key=lambda s: s.start_jd)
        check_chains(kernel_id, parent)
        return cls(reg[kernel_id], path, spk, ids, parent, segments)

    def body_id(self, name: str) -> int:
        """The kernel's id for a body named as its comment names it."""
        try:
            return self.ids[name]
        except KeyError:
            raise KernelError(
                f"kernel {self.entry.id} names no body {name!r} (it names {sorted(self.ids)})"
            ) from None

    def covers(self, jd: float) -> bool:
        lo, hi = self.entry.span_from_jd, self.entry.span_to_jd
        return lo is not None and hi is not None and float(lo) <= jd <= float(hi)

    def barycentric(self, name: str, jd1: float, jd2: float) -> tuple[np.ndarray, np.ndarray]:
        """Position (km) and velocity (km/day) of a body relative to the barycentre, at TDB."""
        jd = jd1 + jd2
        if not self.covers(jd):
            raise KernelError(
                f"kernel {self.entry.id}: JD {jd:.5f} is outside its span "
                f"{self.entry.span_from_jd}–{self.entry.span_to_jd} (TDB)"
            )
        target = self.body_id(name)
        pos = np.zeros(3)
        vel = np.zeros(3)
        while target in self._parent:
            center = self._parent[target]
            p, v = self._segment(center, target, jd).compute_and_differentiate(jd1, jd2)
            pos = pos + p
            vel = vel + v
            target = center
        return pos, vel

    def _segment(self, center: int, target: int, jd: float) -> Any:
        """The segment of the pair that covers ``jd`` (a pair may have several, DE441's two)."""
        for seg in self._segments[(center, target)]:
            if seg.start_jd <= jd <= seg.end_jd:
                return seg
        raise KernelError(f"kernel {self.entry.id}: no segment of {center}→{target} covers JD {jd}")

    def close(self) -> None:
        self.spk.close()
