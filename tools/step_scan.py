"""The exhaustive daily step scan behind the search's planet bounds.

    python tools/step_scan.py --method parahita --jobs 4          # scan, chunked, resumable
    python tools/step_scan.py --method all --jobs 4               # every registered method
    python tools/step_scan.py --method parahita --write           # merge the chunks into the record
    python tools/step_scan.py --method drgganita --from-jdn N --to-jdn M --out FILE  # a short range

Per method and body (Mercury, Venus, Mars, Jupiter, Saturn and the node; never the Moon), over every
civil day from
``search.floor`` to ``search.horizon`` (``data/engine_parameters.yaml``),
cut to the method's ``runs_from`` and, under ``modern_de``, to the span
its runs serve, the scan evaluates the body's sidereal longitude at the
civil day's start (``instant(jdn, Nadika(0))``, the sunrise under a
siddhantic method) and records

- ``sunrise_step_max``: the largest absolute step from one day's start to
  the next's, the arc reduced into (−180°, 180°];
- ``motion_max``: the largest absolute day's motion, ``daily_motion``
  (the gati under a siddhantic method, the arc between consecutive
  civil-day starts under ``modern_de``); the node has no ``daily_motion``
  in either engine, so its record's ``motion_max`` is ``not_served`` and
  its bound is its step;
- ``value``: the larger of the two rounded up to the next arcsecond per
  day (an exact fraction ``k/3600`` of a degree under a siddhantic method,
  a decimal string rounded up under ``modern_de``), the bound the staged
  search multiplies by ``search.safety_factor``; the two maxima are
  recorded as computed (exact under a siddhantic method).

A record covers the days ``range.from_jdn`` to ``range.to_jdn``: the
longitude is evaluated on each of them and on the day after the last, so
every step that starts in the range and every day's motion in it is
scanned.

The scan runs at the text's meridian point (``SCAN_OBSERVER``) under the
method's registered procedures and ``intraday.linear_gati``; ``modern_de``
has no text meridian and runs at ``kerala/kozhikode`` under the
``modern_smh`` preset up to the day before ``modern_iers`` begins and
under ``modern_iers`` from that day on (the two differ only in their ΔT
series, which moves an instant and nothing else; the safety factor's
justification covers that term).

Each record carries the procedure ids in force, the intraday model, the
range and its cut, the tool and engine versions, and the method's
provenance ``data_files`` and ``parameters_sha256`` exactly as the run
computes them; ``tests/unit/test_derived.py`` fails when that hash no
longer matches the method's current files, and re-scans a seeded sample
year against the stored bound. A package that changes a method's data or
procedures re-runs this tool for it and commits the record.

Work is split into chunks of ``--chunk`` days written as JSON under
``--state`` (default ``<scratch>/step_scan/<method>/``); a chunk already
written is skipped, so an interrupted scan resumes where it stopped. Each
chunk carries the run's ``parameters_sha256`` and the digest of its
procedure ids (``procedures_sha256``), so that a chunk scanned under other
data or other procedures cannot enter a record.
``--write`` merges a method's chunks, checks that they tile its range and
that every chunk's two hashes equal the record's, refusing the merge
otherwise, and rewrites that method's records in
``jyotirganita/data/derived/search_step_bounds.yaml``; the other methods'
records are kept.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from jyotirganita import __version__
from jyotirganita.core.types import JDN, AngleUnit, ExactArc, FloatArc, Nadika
from jyotirganita.data import engine_parameters
from jyotirganita.data.datum import Records, context_for, load_records
from jyotirganita.data.yamlio import dump_canonical, load_exact
from jyotirganita.methods.compose import MethodRun, build, load_method
from jyotirganita.methods.registry import load_registry
from jyotirganita.regions.places import load_place
from jyotirganita.siddhantic.engine import LINEAR_GATI

__all__ = ["build_records", "scan_days", "segments", "write"]

REPO = Path(__file__).resolve().parent.parent
TOOL = "step_scan/1"
OUT = Path("jyotirganita") / "data" / "derived" / "search_step_bounds.yaml"
BODIES = ("mercury", "venus", "mars", "jupiter", "saturn", "node")
NODE = "node"
UNIT = "degree/day"
NOT_SERVED = "not_served"
#: the text's meridian point each siddhantic method is scanned at
SCAN_OBSERVER = {
    "aryabhatiya": "meridians/lanka",
    "parahita": "meridians/lanka",
    "drgganita": "meridians/drgganita_samarekha",
    "suryasiddhanta": "meridians/suryasiddhanta_lanka",
    "suryasiddhanta_paramesvara_recension": "meridians/suryasiddhanta_lanka",
}
MODERN = "modern_de"
MODERN_OBSERVER = "kerala/kozhikode"
#: the modern presets whose runs the scan follows, earliest first
MODERN_SEGMENTS = ("modern_smh", "modern_iers")
#: the modern components that fix a position's rate (ΔT moves the instant only)
MODERN_PROCEDURES = ("kernel", "precession", "nutation", "ayanamsa", "observer_frame", "node")
DEFAULT_CHUNK = 20000
ARCSECONDS_PER_DEGREE = 3600
DECIMALS = 9


# --- runs ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Segment:
    """Days ``first`` to ``last`` scanned under one run (``preset``: the modern preset or None)."""

    first: int
    last: int
    preset: str | None


def _records(repo: Path) -> Records:
    return load_records(repo, context_for(repo))


def siddhantic_run(repo: Path, method: str, records: Records) -> MethodRun:
    """The method at its text's meridian point under its registered procedures and linear_gati."""
    region, _, place = SCAN_OBSERVER[method].partition("/")
    obs = load_place(repo, region, place, records.data)
    return build(load_method(method, repo, records=records), obs, intraday=LINEAR_GATI)


def modern_run(repo: Path, preset: str, records: Records) -> Any:
    from jyotirganita.methods.presets import open_modern_preset

    _res, run, _cal = open_modern_preset(repo, preset, MODERN_OBSERVER, records=records)
    return run


def scan_methods(repo: Path) -> list[str]:
    """The registered methods the scan serves: the siddhantic ones above and modern_de."""
    reg = load_registry(
        repo / "jyotirganita" / "methods" / "registry.yaml", context_for(repo).sources
    )
    out = [m for m in reg if m in SCAN_OBSERVER or m == MODERN]
    unknown = [m for m in reg if m not in out]
    if unknown:
        raise SystemExit(f"step_scan: no scan observer for registered method(s) {unknown}")
    return out


def segments(repo: Path, method: str, records: Records) -> list[Segment]:
    """The day ranges the method's record covers, by run (module docstring)."""
    params = engine_parameters.load()
    floor = params["search.floor"].value.numerator
    horizon = params["search.horizon"].value.numerator
    if method != MODERN:
        run = siddhantic_run(repo, method, records)
        return [Segment(max(floor, run.runs_from.value), horizon, None)]
    runs = [modern_run(repo, p, records) for p in MODERN_SEGMENTS]
    out: list[Segment] = []
    for i, (preset, run) in enumerate(zip(MODERN_SEGMENTS, runs, strict=True)):
        first = max(floor, run.runs_from.value, out[-1].last + 1 if out else floor)
        # the day after a segment's last must be served by the same run (the last step)
        last = min(horizon, run.runs_to.value - 1)
        if i + 1 < len(runs):
            last = min(last, runs[i + 1].runs_from.value - 1)
        if first <= last:
            out.append(Segment(first, last, preset))
    return out


def chunks(segs: Sequence[Segment], size: int) -> Iterator[Segment]:
    for s in segs:
        a = s.first
        while a <= s.last:
            b = min(s.last, a + size - 1)
            yield Segment(a, b, s.preset)
            a = b + 1


# --- the scan -----------------------------------------------------------------------


def _signed(arc: Any) -> Any:
    """An arc (ExactArc or FloatArc, one type throughout) reduced into (−180°, 180°]."""
    circle = type(arc).of_int(360, AngleUnit.DEGREE)
    half = type(arc).of_int(180, AngleUnit.DEGREE)
    a = arc.to(AngleUnit.DEGREE).mod_arc(circle)
    return a - circle if a > half else a


def _abs(arc: Any) -> Any:
    return -arc if arc < type(arc).of_int(0, AngleUnit.DEGREE) else arc


def _num(arc: ExactArc | FloatArc) -> str:
    v = arc.to(AngleUnit.DEGREE).value
    if isinstance(v, Fraction):
        return f"{v.numerator}/{v.denominator}"
    return repr(v)


def _parse(s: str) -> Fraction | float:
    return Fraction(s) if "/" in s else float(s)


def scan_days(engine: Any, first: int, last: int) -> dict[str, dict[str, Any]]:
    """Per body: the largest absolute step and day's motion over days ``first``..``last``."""
    out: dict[str, dict[str, Any]] = {}
    prev: dict[str, Any] = {}
    for jv in range(first, last + 2):
        j = JDN(jv)
        inst = engine.instant(j, Nadika(0))
        for body in BODIES:
            lon = (engine.node(inst) if body == NODE else engine.sidereal_longitude(body, inst)).arc
            rec = out.setdefault(
                body, {"step": None, "step_day": None, "motion": None, "motion_day": None}
            )
            if body in prev:
                step = _abs(_signed(lon - prev[body]))
                if rec["step"] is None or step > rec["step"]:
                    rec["step"], rec["step_day"] = step, jv - 1
            prev[body] = lon
            if jv <= last and body != NODE:
                m = _abs(engine.daily_motion(body, j))
                if rec["motion"] is None or m > rec["motion"]:
                    rec["motion"], rec["motion_day"] = m, jv
    return {
        b: {
            "step": _num(r["step"]),
            "step_day": r["step_day"],
            "motion": NOT_SERVED if r["motion"] is None else _num(r["motion"]),
            "motion_day": r["motion_day"],
        }
        for b, r in out.items()
    }


_RECORDS: dict[str, Records] = {}


def _engine(repo: Path, method: str, preset: str | None) -> Any:
    """A fresh run's engine: a run memoises its days, so one per chunk keeps memory flat."""
    key = str(repo)
    if key not in _RECORDS:
        _RECORDS[key] = _records(repo)
    records = _RECORDS[key]
    run = (
        siddhantic_run(repo, method, records)
        if preset is None
        else modern_run(repo, preset, records)
    )
    return run.engine


def _chunk_path(state: Path, method: str, c: Segment) -> Path:
    return state / method / f"chunk_{c.first}_{c.last}.json"


def procedures_digest(procs: Any) -> str:
    """The SHA-256 of the procedure ids in force, canonical JSON."""
    text = json.dumps(procs, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("ascii")).hexdigest()


def _hashes(repo: Path, method: str) -> dict[str, str]:
    """The run's ``parameters_sha256`` and procedures digest, as a chunk and a record carry them."""
    key = str(repo)
    if key not in _RECORDS:
        _RECORDS[key] = _records(repo)
    procs, prov = _procedures(repo, method, _RECORDS[key])
    return {
        "parameters_sha256": str(prov["parameters_sha256"]),
        "procedures_sha256": procedures_digest(procs),
    }


def run_chunk(repo: str, state: str, method: str, c: Segment) -> str:
    path = _chunk_path(Path(state), method, c)
    if path.is_file():
        return f"{method} {c.first}-{c.last}: kept"
    t0 = time.time()
    result = scan_days(_engine(Path(repo), method, c.preset), c.first, c.last)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    payload: dict[str, Any] = {"method": method, "first": c.first, "last": c.last}
    payload["preset"] = c.preset
    payload.update(_hashes(Path(repo), method))
    payload["seconds"] = round(time.time() - t0, 1)
    payload["bodies"] = result
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    tmp.replace(path)
    return f"{method} {c.first}-{c.last}: {payload['seconds']} s"


# --- the record ---------------------------------------------------------------------


def _maximum(values: Sequence[tuple[Fraction | float, int]]) -> tuple[Fraction | float, int]:
    best = values[0]
    for v in values[1:]:
        if v[0] > best[0]:
            best = v
    return best


def _modern_value(v: float) -> str:
    """A float bound rounded up to the next arcsecond, as a decimal string rounded up."""
    k = -((-Fraction(v) * ARCSECONDS_PER_DEGREE) // 1)
    deg = Fraction(k, ARCSECONDS_PER_DEGREE)
    scale = 10**DECIMALS
    q = -((-deg * scale) // 1)
    whole, frac = divmod(int(q), scale)
    return f"{whole}.{frac:0{DECIMALS}d}"


def _exact_text(v: Fraction | float) -> str:
    if isinstance(v, Fraction):
        return f"{v.numerator}/{v.denominator}"
    return _modern_value(v)


def _bound_text(v: Fraction | float) -> str:
    """The bound: the maximum rounded up to the next arcsecond per day (exact, never below it)."""
    if isinstance(v, Fraction):
        b = Fraction(-((-v * ARCSECONDS_PER_DEGREE) // 1), ARCSECONDS_PER_DEGREE)
        return f"{b.numerator}/{b.denominator}"
    return _modern_value(v)


def _procedures(repo: Path, method: str, records: Records) -> tuple[dict[str, Any], dict[str, Any]]:
    """The procedure ids in force and the run's provenance (data_files, parameters_sha256)."""
    if method != MODERN:
        run = siddhantic_run(repo, method, records)
        procs: dict[str, Any] = {
            slot: str(rec.raw.get("procedure", rec.kind))
            for slot, rec in sorted(run.resolved.procedures.items())
        }
        return procs, run.provenance
    provs = [modern_run(repo, p, records).provenance for p in MODERN_SEGMENTS]
    first = provs[0]
    for p in provs[1:]:
        if p["parameters_sha256"] != first["parameters_sha256"]:
            raise SystemExit("step_scan: the modern segments load different files")
    procs = {k: first[k] for k in MODERN_PROCEDURES}
    procs["delta_t"] = [p["delta_t"] for p in provs]
    procs["presets"] = list(MODERN_SEGMENTS)
    return procs, first


def build_records(
    repo: Path, method: str, state: Path, records: Records, scanned_on: str
) -> list[dict[str, Any]]:
    segs = segments(repo, method, records)
    first, last = segs[0].first, segs[-1].last
    files = sorted((state / method).glob("chunk_*.json"))
    loaded = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    loaded.sort(key=lambda d: d["first"])
    expect = first
    for d in loaded:
        if d["first"] != expect:
            raise SystemExit(f"step_scan: {method}: chunks do not tile the range at JDN {expect}")
        expect = d["last"] + 1
    if expect != last + 1:
        raise SystemExit(f"step_scan: {method}: chunks end at JDN {expect - 1}, not {last}")
    procs, prov = _procedures(repo, method, records)
    want = {
        "parameters_sha256": str(prov["parameters_sha256"]),
        "procedures_sha256": procedures_digest(procs),
    }
    for d in loaded:
        got = {k: d.get(k) for k in want}
        if got != want:
            raise SystemExit(
                f"step_scan: {method}: chunk {d['first']}-{d['last']} was scanned under other "
                f"hashes ({got}) than the record's ({want}); re-scan it"
            )
    observer = MODERN_OBSERVER if method == MODERN else SCAN_OBSERVER[method]
    cut = (
        "search.floor to search.horizon, cut to the span the modern runs serve"
        if method == MODERN
        else "search.floor to search.horizon, cut to the method's runs_from"
    )
    out = []
    for body in BODIES:
        steps = [(_parse(d["bodies"][body]["step"]), d["bodies"][body]["step_day"]) for d in loaded]
        step, step_day = _maximum(steps)
        if body == NODE:
            motion: Any = NOT_SERVED
            motion_day = None
            value = step
        else:
            motions = [
                (_parse(d["bodies"][body]["motion"]), d["bodies"][body]["motion_day"])
                for d in loaded
            ]
            motion, motion_day = _maximum(motions)
            value = motion if motion > step else step
        out.append(
            {
                "key": f"derived.search.step_bound.{method}.{body}",
                "value": _bound_text(value),
                "sunrise_step_max": {"value": _exact_text(step), "day": step_day},
                "motion_max": (
                    NOT_SERVED
                    if motion == NOT_SERVED
                    else {"value": _exact_text(motion), "day": motion_day}
                ),
                "unit": UNIT,
                "method": method,
                "body": body,
                "observer": observer,
                "procedures": procs,
                "intraday": "modern.at_instant" if method == MODERN else LINEAR_GATI,
                "range": {"from_jdn": first, "to_jdn": last, "cut": cut},
                "tool": TOOL,
                "engine_version": __version__,
                "data_files": dict(prov["data_files"]),
                "parameters_sha256": prov["parameters_sha256"],
                "scanned_on": scanned_on,
            }
        )
    return out


def write(repo: Path, method: str, state: Path, scanned_on: str) -> Path:
    records = _records(repo)
    new = build_records(repo, method, state, records, scanned_on)
    path = repo / OUT
    old = load_exact(path) if path.is_file() else []
    kept = [r for r in old if r.get("method") != method]
    order = {m: i for i, m in enumerate(scan_methods(repo))}
    merged = sorted(
        kept + new, key=lambda r: (order.get(r["method"], len(order)), BODIES.index(r["body"]))
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_canonical(merged), encoding="utf-8")
    return path


def _state_default() -> Path:
    base = os.environ.get("JYOTIRGANITA_SCRATCH") or os.environ.get("TMPDIR") or "/tmp"
    return Path(base) / "step_scan"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--method", required=True, help="a registered method id, or 'all'")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--chunk", type=int, default=DEFAULT_CHUNK)
    ap.add_argument("--state", type=Path, default=None)
    ap.add_argument("--write", action="store_true", help="merge the chunks into the record file")
    ap.add_argument("--from-jdn", type=int)
    ap.add_argument("--to-jdn", type=int)
    ap.add_argument("--preset", help="the modern preset of a short range")
    ap.add_argument("--out", type=Path, help="a short range's result as JSON")
    ap.add_argument("--scanned-on", default=dt.date.today().isoformat())
    args = ap.parse_args(argv)
    state = args.state or _state_default()
    methods = scan_methods(REPO) if args.method == "all" else [args.method]
    for m in methods:
        if m not in SCAN_OBSERVER and m != MODERN:
            ap.error(f"no scan observer for {m!r}")
    if args.from_jdn is not None or args.to_jdn is not None:
        if args.from_jdn is None or args.to_jdn is None or len(methods) != 1:
            ap.error("a short range names one method, --from-jdn and --to-jdn")
        result = scan_days(_engine(REPO, methods[0], args.preset), args.from_jdn, args.to_jdn)
        text = json.dumps({"method": methods[0], "bodies": result}, indent=1)
        if args.out:
            args.out.write_text(text, encoding="utf-8")
        else:
            print(text)
        return 0
    if args.write:
        for m in methods:
            print(f"step_scan: wrote {write(REPO, m, state, args.scanned_on)} for {m}")
        return 0
    records = _records(REPO)
    tasks = [(m, c) for m in methods for c in chunks(segments(REPO, m, records), args.chunk)]
    if args.jobs <= 1:
        for m, c in tasks:
            print(run_chunk(str(REPO), str(state), m, c), flush=True)
        return 0
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futs = [pool.submit(run_chunk, str(REPO), str(state), m, c) for m, c in tasks]
        for f in as_completed(futs):
            print(f.result(), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
