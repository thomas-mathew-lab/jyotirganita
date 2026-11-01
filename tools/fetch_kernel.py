"""Fetch a JPL DE kernel once and verify it against the registry.

    python tools/fetch_kernel.py de440            # fetch (if absent) and verify
    python tools/fetch_kernel.py de440 --verify   # verify only, no network
    python tools/fetch_kernel.py de441 --record   # first verified fetch: print the
                                                  # size, hash and span to record

The kernel goes to the git-ignored ``jyotirganita/data/ephemerides/``, or
the folder ``JYOTIRGANITA_KERNEL_DIR`` names, as the engine looks for it
(:func:`~jyotirganita.modern.kernels.kernel_directory`; ``--dir`` overrides
both), and is never committed (``.gitignore``). The engine
never fetches at run time: a run naming a kernel that is absent
is refused with the installed command ``jyotirganita fetch-kernel`` in the
message, which does what the first two forms do (``modern/kernels.py``,
:func:`~jyotirganita.modern.kernels.fetch`); this tool keeps
``--record`` and the ``--dir`` option.

``--record`` is for the one fetch that establishes an entry's hash (the
hash is written only from a verified fetch, never from
a published checksum alone): the tool downloads from the registry's URL,
checks the byte size against the registry and against the host's
``Content-Length``, and prints the SHA-256 and the span read from the
kernel's segment summaries, which are written into
``data/tables/kernels.yaml`` with the fetch date and identity.
"""

from __future__ import annotations

import argparse
import sys
from itertools import pairwise
from pathlib import Path

from jyotirganita.modern.kernels import (
    KernelError,
    download,
    fetch,
    kernel_directory,
    load_registry,
    sha256_of,
)


def span_jd(path: Path) -> tuple[str, str]:
    """The kernel's span, as JD strings: over every pair of bodies the file joins, the latest
    first start and the earliest last end.

    A pair may be covered by several consecutive segments (DE441 splits each
    pair in two); they must abut, and the pair's span is their union. Taken
    over every pair the file holds, so that every body is covered over the
    whole span.
    """
    from jplephem.spk import SPK

    kernel = SPK.open(str(path))
    try:
        pairs: dict[tuple[int, int], list[tuple[float, float]]] = {}
        for seg in kernel.segments:
            pairs.setdefault((seg.center, seg.target), []).append((seg.start_jd, seg.end_jd))
    finally:
        kernel.close()
    starts, ends = [], []
    for pair, spans in pairs.items():
        spans.sort()
        for (_, end), (start, _) in pairwise(spans):
            if start != end:
                raise KernelError(f"{path.name}: the segments of {pair} do not abut")
        starts.append(spans[0][0])
        ends.append(spans[-1][1])
    return repr(max(starts)), repr(min(ends))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch and verify a registered JPL kernel.")
    parser.add_argument("kernel", help="registry id, e.g. de440")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify", action="store_true", help="verify the fetched file only")
    mode.add_argument("--record", action="store_true", help="first fetch: print hash and span")
    parser.add_argument("--dir", type=Path, default=None)
    args = parser.parse_args(argv)

    registry = load_registry()
    entry = registry.get(args.kernel)
    if entry is None:
        print(f"fetch_kernel: {args.kernel!r} has no registry entry", file=sys.stderr)
        return 2
    if args.dir is None:
        try:
            args.dir = kernel_directory()
        except KernelError as e:
            print(f"fetch_kernel: {e}", file=sys.stderr)
            return 2
    args.dir.mkdir(parents=True, exist_ok=True)
    target = args.dir / entry.file
    if args.record:
        length = download(entry.url, target) if not target.is_file() else -1
        size = target.stat().st_size
        if size != entry.bytes or (length >= 0 and length != size):
            print(
                f"fetch_kernel: {target} has {size} bytes; registry {entry.bytes}, "
                f"host Content-Length {length}",
                file=sys.stderr,
            )
            return 1
        start, end = span_jd(target)
        print(f"kernel: {args.kernel}\nbytes: {size}\nsha256: {sha256_of(target)}")
        print(f"span: {{from_jd: '{start}', to_jd: '{end}'}}")
        return 0
    try:
        path = fetch(args.kernel, verify_only=args.verify, registry=registry, directory=args.dir)
    except KernelError as exc:
        print(f"fetch_kernel: {exc}", file=sys.stderr)
        return 1
    print(f"fetch_kernel: {args.kernel} verified at {path} (sha256 {entry.sha256})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
