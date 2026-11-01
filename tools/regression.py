"""Write or check the regression files ``tests/regression/<preset>.jsonl``.

    python tools/regression.py            # write every preset's file
    python tools/regression.py --check    # exit 1 if a file differs from a fresh run
    python tools/regression.py --preset parahita_kerala
    python tools/regression.py --preset aryabhatiya_text --observer kerala/kozhikode

A regression file is a **change detector**, not evidence: one method-year of a preset's calendar
leaves (``jyotirganita/calendar/day.py``), the provenance block left out,
one canonical JSON object per line (keys sorted, separators ``(',', ':')``,
ASCII escapes, exact values as ``"num/den"``). Its first line is the
header: what the file is, the preset, the observer, the configuration
hash (with the run's overrides in it, ``jyotirganita/config.py``: the
``drgganita_kerala`` file's month rule is one) and the days it holds. A
change to it is made only with a ``CHANGELOG.md`` entry naming the file and the
version changed. It is never cited as
evidence.

The year: 365 civil days from a fixed Gregorian day of the 1950s (``FIRST``),
the decade of the calendar_reform_committee_1955 and rashtriya_panchanga_1959 statements the time
standards and the
year-start options are compared with; at Kozhikode, the place the
profile's table lists first, unless ``RUNS`` names another observer (and a
month rule) for the preset: the Sūrya-siddhānta's ``text_only`` presets
keep the text's own meridian at the equator, where the cara vanishes;
their files carry its sunrise, carry and endings. The ``drgganita_kerala``
file runs at Kozhikode under the profile's default aparāhna rule, by route (b)
through the editor's identification, on grahanamandana_1965's Rsine table, both flagged provisional.
A modern
preset whose run does not serve
that day (``modern_iers``: the IERS series begins in 1972) starts on the
same day of 2022 (``FIRST_LATE``), the year of the IAE volume indian_astronomical_ephemeris. The
file of a preset on DE441 is checked under the ``de441`` tier
(``tests/regression/test_regression.py``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jyotirganita.calendar.day import Calendar
from jyotirganita.config import open_config
from jyotirganita.core.calendar import jdn_from_gregorian
from jyotirganita.core.types import JDN, GregorianDate
from jyotirganita.data.datum import context_for, load_records
from jyotirganita.methods.presets import load_preset, preset_ids

REPO = Path(__file__).resolve().parent.parent
OUT = Path("tests") / "regression"
OBSERVER = "kerala/kozhikode"
#: a preset's own observer and month rule where Kozhikode and the default rule do not serve
RUNS: dict[str, dict[str, str]] = {
    # the text's meridian on the equator
    "suryasiddhanta_text": {"observer": "meridians/suryasiddhanta_lanka"},
    "suryasiddhanta_paramesvara_recension_text": {"observer": "meridians/suryasiddhanta_lanka"},
}
FIRST = GregorianDate(1954, 8, 17)
FIRST_LATE = GregorianDate(2022, 8, 17)
DAYS = 365
HEADER = (
    "CHANGE DETECTOR, NOT EVIDENCE: the engine's own earlier output for "
    "one method-year, written by tools/regression.py; nothing is claimed from it. A change "
    "needs a CHANGELOG.md entry naming this file and a new version."
)


def _line(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def kernel_of(repo: Path, preset_id: str) -> str | None:
    """The kernel a modern preset names, ``None`` for a siddhantic one."""
    preset = load_preset(repo, preset_id)
    return None if preset.modern is None else str(preset.modern["kernel"])


def run_of(preset_id: str, observer: str | None = None) -> tuple[str, str | None]:
    """The observer and month rule a preset's file runs at (``RUNS``, else Kozhikode)."""
    run = RUNS.get(preset_id, {})
    return observer or run.get("observer", OBSERVER), run.get("month_rule")


def _opened(
    repo: Path, preset_id: str, observer: str, month_rule: str | None
) -> tuple[str, Calendar, JDN]:
    records = load_records(repo, context_for(repo))
    first = jdn_from_gregorian(FIRST)
    sets = {} if month_rule is None else {"conventions.month_rule": month_rule}
    config = open_config(repo, preset_id, observer, records=records, **sets)
    if config.kind == "modern":
        last = first.plus_days(DAYS)
        assert config.runs_to is not None
        if first.days_since(config.runs_from) < 0 or config.runs_to.days_since(last) < 0:
            first = jdn_from_gregorian(FIRST_LATE)
    return config.config_hash, config.calendar, first


def render(repo: Path, preset_id: str, observer: str | None = None) -> str:
    """The regression file of ``preset_id`` as text, at ``observer`` (default: ``run_of``)."""
    where, month_rule = run_of(preset_id, observer)
    config_hash, cal, first = _opened(repo, preset_id, where, month_rule)
    header: dict[str, Any] = {
        "header": HEADER,
        "preset": preset_id,
        "observer": where,
        "config_hash": config_hash,
        "from_jdn": first.value,
        "days": DAYS,
    }
    if month_rule is not None:
        header["month_rule"] = month_rule
    lines = [_line(header)]
    lines += [_line(cal.day(first.plus_days(i))) for i in range(DAYS)]
    return "".join(lines)


def path_of(repo: Path, preset_id: str) -> Path:
    return repo / OUT / f"{preset_id}.jsonl"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write or check the regression files.")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--preset", action="append")
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument(
        "--observer", help="region/place (default: the preset's entry in RUNS, else Kozhikode)"
    )
    args = parser.parse_args(argv)
    failed = 0
    for pid in args.preset or preset_ids(args.repo):
        text = render(args.repo, pid, args.observer)
        path = path_of(args.repo, pid)
        if args.check:
            old = path.read_text(encoding="ascii") if path.is_file() else ""
            if old != text:
                failed += 1
                old_lines, new_lines = old.splitlines(), text.splitlines()
                diff = [
                    i for i, (a, b) in enumerate(zip(old_lines, new_lines, strict=False)) if a != b
                ]
                print(f"regression: {path.relative_to(args.repo)} differs (lines {diff[:10]})")
            else:
                print(f"regression: {path.relative_to(args.repo)} is current")
        else:
            path.write_bytes(text.encode("ascii"))
            print(f"regression: wrote {path.relative_to(args.repo)} ({DAYS} days)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
