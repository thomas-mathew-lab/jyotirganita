"""Environment perturbation changes no output byte.

The surface: the exact arithmetic and its formatting, the
firewall's findings, the engine parameters and the data hashing; and the record. Each runs in a
fresh interpreter
under several time zones, locales and hash seeds; every output must be
byte-identical.

The record's surface:

- a few days of every preset of the table, written through
  :func:`jyotirganita.api.generate` and :func:`jyotirganita.api.dumps`,
  in fresh interpreters under the perturbations: the lines are compared
  byte for byte. A siddhantic line is exact throughout (integers and
  fractions; the text's own form is derived from the exact value), so its
  identity is the identity of its exact fields. A modern line is compared
  bitwise, on this platform only: across platforms the modern engine is
  compared to a stated tolerance, never bit for bit, and the derived placements
  (``derived_ut``, ``derived_tt``, floats from the modern engine's chain)
  are compared under that rule (``DERIVED_TOLERANCE_DAYS``, with its
  reason), the rest of their line byte for byte;
- the partial-versus-batch identity: the bytes of ``generate`` over a
  window equal the concatenation of ``day`` over its days and of
  ``generate`` over its two halves, for every preset, each mode on a
  configuration opened afresh (so that no memo of one mode serves
  another), and once more with the memo width cut to one day
  (``core/memo.py``), so that a day's record does not depend on where its
  window starts or on what the run still remembers;
- the committed regression files' leaves of the siddhantic presets,
  parsed and re-serialised through the record's writer (``io/jsonl.py``),
  equal the record's same leaves byte for byte: the two writers agree.

The ``modern_antiquity`` items carry the ``de441`` marker. The second-OS
comparison exists only where a run started by hand exists: none does, so it is **not measured**.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Iterator
from fractions import Fraction
from typing import Any

import pytest
from record_kit import CI_PRESETS, REPO, RUNS, day_of
from record_kit import config as kit_config

from jyotirganita import api
from jyotirganita.config import RunConfig, open_config
from jyotirganita.core import memo
from jyotirganita.core.exact import to_canonical
from jyotirganita.core.types import JDN
from jyotirganita.data.datum import context_for, load_records
from jyotirganita.io import jsonl
from jyotirganita.io.record import record_schema

#: the days of each preset the fresh-interpreter run writes
RECORD_DAYS = 3
#: the window of the partial-versus-batch identity (split into two halves)
WINDOW_DAYS = 4
#: the siddhantic presets, whose regression files hold exact leaves
SIDDHANTIC = tuple(p for p in CI_PRESETS if not p.startswith("modern_"))
#: the derived placements under the modern-engine rule: on one platform they are
#: bitwise equal, and the tolerance is the one a cross-platform run would use, a
#: microsecond in days, far above binary64 rounding of a Julian date (~4e-11 days at
#: JD 2.4e6) and far below the derived chain's own accuracy (the equation of time
#: to seconds); it is a check of the comparison rule, not a measured tolerance.
DERIVED_TOLERANCE_DAYS = 1e-6 / 86400
DERIVED = ("derived_ut", "derived_tt")

_SCRIPT = r"""
import sys
from fractions import Fraction
from pathlib import Path

from jyotirganita.core import exact
from jyotirganita.data import engine_parameters, firewall
from jyotirganita.provenance.hashing import files_digest

repo = Path(sys.argv[1])
out = []
x = Fraction(1234567, 3600) + Fraction(-1, 7)
for rule in exact.Rounding:
    out.append(f"{rule.name} {exact.to_sexagesimal(x, 3, rule)} {exact.to_rdms(x, 2, rule)}")
out.append(exact.to_canonical(x))
out.append(repr(sorted(engine_parameters.load().items())))
plant = "VALUE = 0.0057183\n"
findings = firewall.check_source(
    plant, "siddhantic/plant.py", allow=[], datums={}, params={}, derived={}
)
out.extend(str(f) for f in findings)
names = {f"k{i}" for i in range(50)}
out.append(files_digest((n, n) for n in names))
sys.stdout.write("\n".join(out))
"""

_ENVIRONMENTS = (
    {"TZ": "UTC", "LC_ALL": "C", "LANG": "C", "PYTHONHASHSEED": "0"},
    {"TZ": "Pacific/Kiritimati", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "PYTHONHASHSEED": "1"},
    {
        "TZ": "America/St_Johns",
        "LC_ALL": "",
        "LANG": "de_DE.UTF-8",
        "PYTHONHASHSEED": "random",
    },
    {"TZ": "Asia/Kolkata", "LC_ALL": "", "LANG": "ml_IN.UTF-8", "PYTHONHASHSEED": "4242"},
)


def _run(extra: dict[str, str], script: str = _SCRIPT) -> bytes:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(REPO), **extra}
    result = subprocess.run(
        [sys.executable, "-c", script, str(REPO)],
        env=env,
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    return result.stdout


def test_environment_perturbation_is_byte_identical() -> None:
    outputs = [_run(e) for e in _ENVIRONMENTS]
    assert b"0.0057183" in outputs[0]
    for env, out in zip(_ENVIRONMENTS[1:], outputs[1:], strict=True):
        assert out == outputs[0], f"output differs under {env}"


# --- the record -----------------------------------------------------------

_RECORD_SCRIPT = r"""
import sys
from pathlib import Path

repo = Path(sys.argv[1])
sys.path.insert(0, str(repo / "tests"))
from record_kit import RUNS, config, day_of

from jyotirganita import api

out = []
for preset in sys.argv[2].split(","):
    cfg = config(preset)
    first = day_of(cfg)
    last = first.plus_days(int(sys.argv[3]) - 1)
    out.extend(api.dumps(r) for r in api.generate(cfg, first, last))
    # the derived chain needs a modern longitude: not at a modern preset, nor at the
    # text-units meridian places of the Drgganita and the Surya-siddhanta (record_kit.RUNS)
    if not preset.startswith("modern_") and "observer" not in RUNS.get(preset, {}):
        # the Surya-siddhanta's bhujantara moves the place, not the sunrise: its equation
        # of time comes from a modern preset
        surya = cfg.method_id.startswith("suryasiddhanta")
        eot = "modern:modern_smh" if surya else "text_bhujantara"
        out.extend(
            api.dumps(r)
            for r in api.generate(
                cfg, first, first, derived_ut=f"apparent:{eot}", derived_tt="em2006"
            )
        )
sys.stdout.write("\n".join(out))
"""


def _record_run(extra: dict[str, str], presets: tuple[str, ...]) -> list[str]:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(REPO), **extra}
    result = subprocess.run(
        [sys.executable, "-c", _RECORD_SCRIPT, str(REPO), ",".join(presets), str(RECORD_DAYS)],
        env=env,
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    return result.stdout.decode("ascii").split("\n")


def _split_derived(line: str) -> tuple[str, dict[str, Any]]:
    """The line with its derived placements taken out, and those placements."""
    rec = json.loads(line)
    derived = {k: rec.pop(k) for k in DERIVED if k in rec}
    return json.dumps(rec, sort_keys=True), derived


def _numbers(x: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(x, dict):
        for k, v in sorted(x.items()):
            yield from _numbers(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _numbers(v, f"{path}[{i}]")
    else:
        yield path, x


def _same_derived(a: dict[str, Any], b: dict[str, Any]) -> bool:
    na, nb = dict(_numbers(a)), dict(_numbers(b))
    if na.keys() != nb.keys():
        return False
    for k, va in na.items():
        vb = nb[k]
        if isinstance(va, float) and isinstance(vb, float):
            if abs(va - vb) > DERIVED_TOLERANCE_DAYS:
                return False
        elif va != vb:
            return False
    return True


def _compare_runs(presets: tuple[str, ...]) -> None:
    runs = [_record_run(e, presets) for e in _ENVIRONMENTS]
    assert len(runs[0]) == len(presets) * RECORD_DAYS + sum(
        1 for p in presets if not p.startswith("modern_") and "observer" not in RUNS.get(p, {})
    )
    for env, run in zip(_ENVIRONMENTS[1:], runs[1:], strict=True):
        assert len(run) == len(runs[0]), f"line count differs under {env}"
        for a, b in zip(runs[0], run, strict=True):
            if '"derived_ut"' not in a and '"derived_tt"' not in a:
                assert a == b, f"a record line differs under {env}"
                continue
            rest_a, der_a = _split_derived(a)
            rest_b, der_b = _split_derived(b)
            assert rest_a == rest_b, f"a record line differs under {env} outside derived"
            assert _same_derived(der_a, der_b), f"derived placements differ under {env}"


def test_records_byte_identical_in_fresh_interpreters() -> None:
    _compare_runs(CI_PRESETS)


@pytest.mark.de441
def test_modern_antiquity_records_byte_identical_in_fresh_interpreters() -> None:
    _compare_runs(("modern_antiquity",))


def _fresh(preset: str) -> RunConfig:
    """The preset opened afresh: its own run, calendar and memos."""
    run = dict(RUNS.get(preset, {}))
    observer = run.pop("observer", "kerala/kozhikode")
    records = load_records(REPO, context_for(REPO))
    return open_config(REPO, preset, observer, records=records, **run)


def _window_bytes(preset: str) -> tuple[list[str], list[str], list[str]]:
    first = day_of(kit_config(preset))
    last = first.plus_days(WINDOW_DAYS - 1)
    mid = first.plus_days(WINDOW_DAYS // 2 - 1)
    batch = [api.dumps(r) for r in api.generate(_fresh(preset), first, last)]
    cfg = _fresh(preset)
    by_day = [api.dumps(api.day(cfg, JDN(n))) for n in range(last.value, first.value - 1, -1)]
    by_day.reverse()  # computed last day first, so no memo of an earlier day serves a later
    halves_cfg = _fresh(preset)
    halves = [api.dumps(r) for r in api.generate(halves_cfg, mid.plus_days(1), last)]
    halves = [api.dumps(r) for r in api.generate(halves_cfg, first, mid)] + halves
    return batch, by_day, halves


@pytest.mark.parametrize("preset", CI_PRESETS)
def test_partial_and_batch_identity(preset: str) -> None:
    batch, by_day, halves = _window_bytes(preset)
    assert len(batch) == WINDOW_DAYS
    assert by_day == batch
    assert halves == batch


@pytest.mark.de441
def test_partial_and_batch_identity_modern_antiquity() -> None:
    batch, by_day, halves = _window_bytes("modern_antiquity")
    assert by_day == batch and halves == batch


@pytest.mark.parametrize("preset", ("parahita_kerala", "modern_smh"))
def test_a_memo_of_one_day_changes_no_byte(preset: str, monkeypatch: pytest.MonkeyPatch) -> None:
    first = day_of(kit_config(preset))
    last = first.plus_days(WINDOW_DAYS - 1)
    wide = [api.dumps(r) for r in api.generate(_fresh(preset), first, last)]
    monkeypatch.setattr(memo, "MEMO_DAYS", 1)
    narrow = [api.dumps(r) for r in api.generate(_fresh(preset), first, last)]
    assert narrow == wide


_RATIO = re.compile(r"^-?\d+/\d+$")


def _as_record_leaf(reg: Any, rec: Any) -> Any:
    """The regression leaf ``reg`` in the record's representation, beside its leaf ``rec``."""
    if isinstance(rec, jsonl.Stated):
        assert isinstance(reg, str) and _RATIO.match(reg), reg
        exact = Fraction(reg)
        return jsonl.Stated(exact, rec.form, rec.parts, rec.rounding) if exact == rec.exact else reg
    if isinstance(rec, Fraction):
        assert isinstance(reg, str) and _RATIO.match(reg), reg
        assert reg == to_canonical(Fraction(reg))  # the regression writer's canonical form
        return Fraction(reg)
    if isinstance(rec, dict) and isinstance(reg, dict):
        return {k: _as_record_leaf(v, rec.get(k)) for k, v in reg.items()}
    if isinstance(rec, list) and isinstance(reg, list) and len(rec) == len(reg):
        return [_as_record_leaf(a, b) for a, b in zip(reg, rec, strict=True)]
    return reg


@pytest.mark.parametrize("preset", SIDDHANTIC)
def test_regression_leaves_through_the_record_writer(preset: str) -> None:
    cfg = kit_config(preset)
    lines = (REPO / "tests" / "regression" / f"{preset}.jsonl").read_text("ascii").splitlines()
    header = json.loads(lines[0])
    assert header["config_hash"] == cfg.config_hash
    schema = record_schema()
    builder = api.records(cfg)
    for text in lines[1 : 1 + RECORD_DAYS]:
        reg = json.loads(text)
        rec = builder.record(JDN(reg["dates"]["jdn"]))
        shared = sorted(set(reg) & set(rec))
        assert shared == sorted(reg), sorted(set(reg) - set(rec))
        ours = jsonl.dumps({k: rec[k] for k in shared}, "exact", schema)
        theirs = jsonl.dumps({k: _as_record_leaf(reg[k], rec[k]) for k in shared}, "exact", schema)
        assert theirs == ours, f"{preset} day {reg['dates']['jdn']}"
