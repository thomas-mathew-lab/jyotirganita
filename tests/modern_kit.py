"""Shared loaders for the modern engine's tests: records, parameters, engines.

Every engine here is built from the repository's data (the datum files,
the fetched extracts under ``jyotirganita/data/tables/``, the engine
parameters) and the DE440 kernel the CI's fetch step verifies; nothing is
typed into a test. :func:`config` is the ``modern_iers`` preset's
configuration, read from its file, so a test that varies one component
names only that component.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

from jyotirganita.data import engine_parameters
from jyotirganita.data.datum import Record, Records, context_for, load_records
from jyotirganita.data.engine_parameters import EngineParameter
from jyotirganita.data.eras import load_eras
from jyotirganita.data.time_standards import TimeStandard, load_time_standards
from jyotirganita.methods.presets import _conventions, load_preset, modern_config
from jyotirganita.modern.engine import ModernConfig, ModernEngine
from jyotirganita.modern.kernels import Ephemeris
from jyotirganita.modern.riseset import ModernObserver
from jyotirganita.regions.places import load_modern_place

REPO = Path(__file__).resolve().parents[1]
#: the place of the engine tests: a Kerala place with cited modern coordinates (route (b))
REGION, PLACE = "kerala", "thiruvananthapuram"
PRESET = "modern_iers"


@cache
def records() -> Records:
    return load_records(REPO, context_for(REPO))


def data() -> Mapping[str, Record]:
    return records().data


@cache
def parameters() -> Mapping[str, EngineParameter]:
    return engine_parameters.load()


@cache
def time_standards() -> Mapping[str, TimeStandard]:
    return load_time_standards(REPO, context_for(REPO))


@cache
def ephemeris(kernel: str = "de440") -> Ephemeris:
    return Ephemeris.open(kernel)


@cache
def observer(place: str = PLACE, height_m: Fraction = Fraction(0)) -> ModernObserver:
    mp = load_modern_place(REPO, REGION, place, data())
    return ModernObserver(mp.id, mp.latitude_deg, mp.longitude_deg, height_m, mp.flags)


@cache
def config(preset_id: str = PRESET) -> ModernConfig:
    """A modern preset's engine configuration, as ``methods/presets.py`` builds it."""
    preset = load_preset(REPO, preset_id)
    eras = load_eras(REPO / "jyotirganita" / "data", context_for(REPO), REPO)
    return modern_config(preset, _conventions(REPO, preset, records(), eras), records())


def engine(preset_id: str = PRESET, place: str = PLACE, **changes: Any) -> ModernEngine:
    """An engine on ``preset_id``'s configuration with ``changes`` applied."""
    cfg = dataclasses.replace(config(preset_id), **changes)
    return ModernEngine(
        cfg,
        observer(place),
        data=data(),
        time_standards=time_standards(),
        parameters=parameters(),
        ephemeris=ephemeris(cfg.kernel),
    )


@cache
def default_engine() -> ModernEngine:
    return engine()
