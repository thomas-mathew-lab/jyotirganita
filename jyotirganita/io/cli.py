"""The command line: ``jyotirganita <command>``.

::

    jyotirganita generate --preset parahita_kerala --observer kerala/kozhikode \\
        --from gregorian:1954-08-17 --to gregorian:1955-08-16 --jsonl year.jsonl
    jyotirganita day --preset parahita_kerala --observer kerala/kozhikode \\
        --date julian:1000-03-15 --derived-ut mean --derived-tt smh2016
    jyotirganita positions --preset modern_iers --observer kerala/kozhikode \\
        --at gregorian:2022-08-17T06:30:00/ist --bodies sun,moon
    jyotirganita sankrantis --preset parahita_kerala --observer kerala/kozhikode \\
        --from gregorian:1954-01-01 --to gregorian:1954-12-31
    jyotirganita eclipses --preset modern_iers --observer kerala/kozhikode \\
        --from gregorian:2022-01-01 --to gregorian:2022-12-31
    jyotirganita search --preset parahita_kerala --observer kerala/kozhikode \\
        --query q.yaml --jsonl out.jsonl
    jyotirganita fetch-kernel de440 [--verify]

Every computing command takes ``--preset``, ``--observer`` (required: no
preset names a place of its own), ``--jsonl`` (an output path, ``-`` for standard
output, the default), ``--repo`` and ``--set key=value``, repeatable, with
exactly the keys of ``jyotirganita/config.py`` (the conventions, a
procedure, the intraday model, the time standard, the output selection);
any other key is refused, naming ``method``, ``composed``, ``runs_from``
and datum keys as refused by design. ``generate``, ``day`` and
``positions`` take ``--derived-ut mean | apparent:<eot_source>`` and
``--derived-tt <ΔT model>`` (``io/derived.py``). Dates are tagged
(``io/dates.py``: ``julian:``, ``gregorian:``, ``jdn:``); the instant of
``positions --at`` names its reckoning (``<date>+<n>nadika`` under a
siddhantic preset, ``<date>T<hh>:<mm>[:<ss>]/<standard>`` under a modern
one). One result per line, in the canonical form of ``io/jsonl.py``.

``search`` takes its own options: ``--query`` (a YAML or JSON query,
``search/query.schema.json``), ``--brute`` (the reference path), and
``--month-rule``, ``--intraday`` and ``--procedure slot=id`` as aliases of
their ``--set`` keys (``conventions.month_rule``, ``intraday``,
``procedure.<slot>``); the same key given both ways is a hard error.

``fetch-kernel`` fetches a registered JPL kernel once from its registry URL
into the package's ``data/ephemerides/``, or the absolute folder
``JYOTIRGANITA_KERNEL_DIR`` names, and verifies its size and hash
(``modern/kernels.py``); ``--verify`` checks a fetched file without the
network. It is the package's only network operation; a
modern run never fetches. Its refusals exit 1.

Every refusal (an unknown preset, place or ``--set`` key, an untagged
date, a window the run does not serve, a malformed query) is reported on
standard error as ``jyotirganita <command>: <field>: <message>`` with exit
status 2, before any day is computed. An empty result exits 0. A failure
of the engine's own numerics (a root bracket that does not close, a kernel
segment or table that cannot serve an instant the run's range admitted) is
reported as ``jyotirganita <command>: internal: <message>`` with exit
status 3, so that a script can tell it from a refusal; it is a fault to report, not a request to
change.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Iterable, Iterator, Sequence
from functools import cache
from pathlib import Path
from typing import Any, BinaryIO

from jyotirganita.data.datum import Records, context_for, load_records
from jyotirganita.data.eras import load_eras
from jyotirganita.errors import Refusal
from jyotirganita.io import jsonl
from jyotirganita.io.dates import DateSyntaxError, parse_cli_date, parse_cli_instant
from jyotirganita.modern.kernels import KernelError
from jyotirganita.modern.roots import RootError
from jyotirganita.modern.tables import TableError
from jyotirganita.search import open_search, search
from jyotirganita.search.profiles import load_reading_profile
from jyotirganita.search.query import check_shape, check_vocabulary, compile_query, read_query
from jyotirganita.search.results import Candidate, write_jsonl

__all__ = ["main"]

EXIT_REFUSED = 2
EXIT_FAILED = 1
EXIT_INTERNAL = 3
RECORD_COMMANDS = ("generate", "day", "positions")


def _repo() -> Path:
    """The tree whose data the run loads: the package's parent directory."""
    return Path(__file__).resolve().parents[2]


@cache
def _records(repo: Path) -> Records:
    """The datum records of ``repo``, loaded once per process."""
    return load_records(repo, context_for(repo))


def _pairs(values: Sequence[str], field: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for v in values:
        key, sep, val = v.partition("=")
        if not sep or not key:
            raise Refusal(field, f"{v!r}: expected key=value")
        if key in out:
            raise Refusal(field, f"{key} is given twice")
        out[key] = val
    return out


def _date(text: str, field: str) -> Any:
    try:
        return parse_cli_date(text)
    except DateSyntaxError as e:
        raise Refusal(field, str(e)) from None


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--preset", required=True, help="a preset id (methods/presets/)")
    p.add_argument("--observer", help="region/place (required)")
    p.add_argument("--jsonl", default="-", help="output path, or - for standard output")
    p.add_argument("--set", dest="set_", action="append", default=[], metavar="KEY=VALUE")
    p.add_argument("--repo", type=Path, default=None, help="the source tree (default: this one)")


def _derived(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--derived-ut", dest="derived_ut", help="mean or apparent:<eot_source> (io/derived.py)"
    )
    p.add_argument("--derived-tt", dest="derived_tt", help="a ΔT model of modern/deltat.py")


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="jyotirganita", description="jyotirganita engine")
    sub = ap.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate", help="the day records of a window")
    _common(g)
    g.add_argument("--from", dest="first", required=True, help="a tagged date")
    g.add_argument("--to", dest="last", required=True, help="a tagged date")
    _derived(g)
    d = sub.add_parser("day", help="the record of one day")
    _common(d)
    d.add_argument("--date", required=True, help="a tagged date")
    _derived(d)
    p = sub.add_parser("positions", help="the planets at an instant")
    _common(p)
    p.add_argument("--at", required=True, help="<date>+<n>nadika or <date>T<hh>:<mm>/<std>")
    p.add_argument("--bodies", required=True, help="a comma-separated list of bodies")
    _derived(p)
    for name, text in (
        ("sankrantis", "the saṅkrānti instants of a window"),
        ("eclipses", "the eclipses of a window (modern presets, provisional)"),
    ):
        w = sub.add_parser(name, help=text)
        _common(w)
        w.add_argument("--from", dest="first", required=True, help="a tagged date")
        w.add_argument("--to", dest="last", required=True, help="a tagged date")
    s = sub.add_parser("search", help="the inverse search")
    _common(s)
    s.add_argument("--query", required=True, type=Path, help="a YAML or JSON query file")
    s.add_argument("--brute", action="store_true", help="the reference path")
    s.add_argument("--month-rule", dest="month_rule", help="alias of conventions.month_rule")
    s.add_argument("--intraday", help="alias of --set intraday (linear_gati, full_evaluation)")
    s.add_argument("--procedure", action="append", default=[], metavar="SLOT=ID")
    k = sub.add_parser(
        "fetch-kernel",
        help="fetch and verify a registered JPL kernel, once (into $JYOTIRGANITA_KERNEL_DIR "
        "when set, else the package's data/ephemerides/)",
    )
    k.add_argument("kernel", help="a registry id (data/tables/kernels.yaml), e.g. de440")
    k.add_argument("--verify", action="store_true", help="verify a fetched file, no network")
    return ap


def _target(args: argparse.Namespace) -> Path:
    """The ``--jsonl`` path, refused when its directory does not exist."""
    path = Path(args.jsonl)
    if not path.parent.is_dir():
        raise Refusal("jsonl", f"{args.jsonl}: the directory {path.parent} does not exist")
    return path


def _write_to[N](
    write: Callable[[BinaryIO], N], args: argparse.Namespace, out: BinaryIO | None
) -> N:
    if args.jsonl == "-":
        target = out if out is not None else sys.stdout.buffer
        n = write(target)
        target.flush()
        return n
    # written beside the target and renamed on success: a refusal part way leaves no
    # partial file, and an earlier file of that name is kept as it was
    target_path = _target(args)
    part = target_path.with_name(f".{target_path.name}.part")
    try:
        with part.open("wb") as fh:
            n = write(fh)
        part.replace(target_path)
    finally:
        part.unlink(missing_ok=True)
    return n


def _write(lines: Iterable[str], args: argparse.Namespace, out: BinaryIO | None) -> int:
    return _write_to(lambda fh: jsonl.write_lines(lines, fh), args, out)


def _config(args: argparse.Namespace) -> Any:
    from jyotirganita.config import check_set_keys, open_config

    repo = args.repo or _repo()
    sets = _pairs(args.set_, "set")
    check_set_keys(sets)  # before the call: --set records=... met its keyword
    cfg = open_config(repo, args.preset, args.observer, records=_records(repo), **sets)
    for line in cfg.notices:
        print(f"jyotirganita {args.command}: note: {line}", file=sys.stderr)
    return cfg


def _results(args: argparse.Namespace) -> Iterator[dict[str, Any]] | list[dict[str, Any]]:
    from jyotirganita import api

    config = _config(args)
    kw: dict[str, Any] = {}
    if args.command in RECORD_COMMANDS:
        kw = {"derived_ut": args.derived_ut, "derived_tt": args.derived_tt}
    if args.command == "generate":
        first, last = _date(args.first, "from"), _date(args.last, "to")
        return api.generate(config, first, last, **kw)
    if args.command == "day":
        return [api.day(config, _date(args.date, "date"), **kw)]
    if args.command == "positions":
        try:
            instant = parse_cli_instant(args.at, config.kind, config.time_standard)
        except DateSyntaxError as e:
            raise Refusal("at", str(e)) from None
        bodies = [b.strip() for b in args.bodies.split(",") if b.strip()]
        return [api.positions(config, instant, bodies, **kw)]
    window = (_date(args.first, "from"), _date(args.last, "to"))
    if args.command == "sankrantis":
        return api.sankrantis(config, window)
    return api.eclipses(config, window)


def _run(args: argparse.Namespace, out: BinaryIO | None) -> int:
    from jyotirganita import api

    results = _results(args)
    n = _write((api.dumps(r) for r in results), args, out)
    print(f"{args.command}: {n} line(s)", file=sys.stderr)
    return 0


def _search(args: argparse.Namespace, out: BinaryIO | None) -> int:
    procedures = _pairs(args.procedure, "procedure")
    sets = _pairs(args.set_, "set")
    repo = args.repo or _repo()
    try:
        doc = read_query(args.query)
    except OSError as e:
        raise Refusal("query", f"{args.query}: {e.strerror or e}") from None
    # the query's shape and vocabulary first: a malformed query waits for no kernel
    check_shape(doc)
    records = _records(repo)
    profile = load_reading_profile(
        repo,
        doc["reading_profile"],
        records,
        load_eras(repo / "jyotirganita" / "data", context_for(repo), repo),
    )
    check_vocabulary(doc, profile)
    config = open_search(
        repo,
        args.preset,
        args.observer,
        month_rule=args.month_rule,
        intraday=args.intraday,
        procedures=procedures,
        sets=sets,
        records=records,
    )
    for line in config.notices:
        print(f"jyotirganita search: note: {line}", file=sys.stderr)
    config.profiles[doc["reading_profile"]] = profile
    query = compile_query(doc, config)
    candidates = search(config, query, brute=args.brute)
    counts = {"match": 0, "near_miss": 0}

    def counted() -> Iterator[Candidate]:
        for c in candidates:
            counts[c.cls] += 1
            yield c

    # the part-and-rename of _write
    _write_to(lambda fh: write_jsonl(counted(), fh), args, out)
    print(f"search: {counts['match']} match, {counts['near_miss']} near_miss", file=sys.stderr)
    return 0


def _fetch_kernel(args: argparse.Namespace, out: BinaryIO | None) -> int:
    from jyotirganita.modern.kernels import KernelError, fetch, load_registry

    registry = load_registry()
    entry = registry.get(args.kernel)
    if entry is not None and not args.verify:
        print(f"fetch-kernel: {args.kernel}: {entry.bytes} bytes from {entry.url}", file=sys.stderr)
    try:
        path = fetch(args.kernel, verify_only=args.verify, registry=registry)
    except KernelError as e:
        print(f"jyotirganita fetch-kernel: {e}", file=sys.stderr)
        return EXIT_FAILED
    except OSError as e:
        print(
            f"jyotirganita fetch-kernel: {args.kernel}: the download failed: {e}", file=sys.stderr
        )
        return EXIT_FAILED
    print(f"fetch-kernel: {args.kernel} verified at {path}", file=sys.stderr)
    return 0


COMMANDS: dict[str, Callable[[argparse.Namespace, BinaryIO | None], int]] = {
    "generate": _run,
    "day": _run,
    "positions": _run,
    "sankrantis": _run,
    "eclipses": _run,
    "search": _search,
    "fetch-kernel": _fetch_kernel,
}


def main(argv: Sequence[str] | None = None, out: BinaryIO | None = None) -> int:
    """The console script ``jyotirganita`` (module docstring)."""
    args = _parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args, out)
    except Refusal as e:
        print(f"jyotirganita {args.command}: {e.field}: {e.message}", file=sys.stderr)
        return EXIT_REFUSED
    except (RootError, KernelError, TableError) as e:
        print(f"jyotirganita {args.command}: internal: {type(e).__name__}: {e}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
