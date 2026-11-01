"""Shared configurations and record sets for the record, API and CLI tests.

Every configuration is a shipped preset opened through
:func:`jyotirganita.config.open_config` with the records loaded once
(``modern_kit.records``), at the observer and month rule its regression
file runs at (``tools/regression.py``). The record sets are the cases the
schema test needs: one record per preset of the table, one under
an intraday override and one under a procedure override, records with
the derived fields under each equation-of-time source, a day before the
composition date and a ``text_only`` preset. No value here is typed from
a source or from memory; the records are the engine's own output and
evidence for nothing.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

from modern_kit import records

from jyotirganita.config import RunConfig, open_config
from jyotirganita.core.types import JDN
from jyotirganita.io.derived import derived_chain
from jyotirganita.io.record import Records

REPO = Path(__file__).resolve().parents[1]
OBSERVER = "kerala/kozhikode"
#: the place and month rule of each preset's regression file (tools/regression.py RUNS)
RUNS: Mapping[str, Mapping[str, str]] = {
    "suryasiddhanta_text": {"observer": "meridians/suryasiddhanta_lanka"},
    "suryasiddhanta_paramesvara_recension_text": {"observer": "meridians/suryasiddhanta_lanka"},
}
#: the presets of the preset table the CI tier opens (modern_antiquity is the de441 tier's)
CI_PRESETS = (
    "aryabhatiya_text",
    "parahita_kerala",
    "drgganita_kerala",
    "suryasiddhanta_text",
    "suryasiddhanta_paramesvara_recension_text",
    "aryabhatiya_kerala",
    "suryasiddhanta_kerala",
    "suryasiddhanta_paramesvara_recension_kerala",
    "modern_iers",
    "modern_smh",
)
#: the regression files' first day (tools/regression.py FIRST and FIRST_LATE) and the day before
DAY = JDN(2434972)
DAY_LATE = JDN(2459809)
#: a civil day of 600 CE (Julian), before the Parahita's composition and the Kollam epoch
EARLY = JDN(1940300)
GEOMETRIC = "modern_geometric:modern_smh"


@cache
def config(preset: str, **sets: str) -> RunConfig:
    run = dict(RUNS.get(preset, {}))
    observer = run.pop("observer", OBSERVER)
    return open_config(REPO, preset, observer, records=records(), **{**run, **sets})


def day_of(cfg: RunConfig) -> JDN:
    """The regression file's first day, or the late one where the run does not serve it."""
    if cfg.runs_to is not None and DAY.days_since(cfg.runs_from) < 0:
        return DAY_LATE
    return DAY


def record(
    cfg: RunConfig,
    jdn: JDN,
    derived_ut: str | None = None,
    derived_tt: str | None = None,
) -> dict[str, Any]:
    return Records(cfg, derived=derived_chain(cfg, derived_ut, derived_tt)).record(jdn)


def line(
    cfg: RunConfig, jdn: JDN, derived_ut: str | None = None, derived_tt: str | None = None
) -> str:
    return Records(cfg, derived=derived_chain(cfg, derived_ut, derived_tt)).dumps(jdn)


@cache
def schema_cases() -> tuple[tuple[str, str], ...]:
    """(case id, canonical line) for every case of the schema test (module docstring)."""
    out: list[tuple[str, str]] = []
    for preset in CI_PRESETS:
        cfg = config(preset)
        d = day_of(cfg)
        for jdn in (d.plus_days(-1), d):
            out.append((f"{preset}@{jdn.value}", line(cfg, jdn)))
    par = config("parahita_kerala")
    out.append(("intraday", line(config("parahita_kerala", intraday="full_evaluation"), DAY)))
    out.append(
        ("procedure", line(config("aryabhatiya_text", **{"procedure.sunrise": GEOMETRIC}), DAY))
    )
    out.append(("derived_mean", line(par, DAY, "mean", "smh2016")))
    out.append(("derived_bhujantara", line(par, DAY, "apparent:text_bhujantara")))
    out.append(("before_composition", line(par, EARLY)))
    return tuple(out)


def parsed_cases() -> list[tuple[str, dict[str, Any]]]:
    return [(cid, json.loads(text)) for cid, text in schema_cases()]
