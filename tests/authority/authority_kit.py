"""Loaders shared by the authority tests: a fixture's printed values and the era records.

The fixture files live in ``tests/authority/<text>/``; the tests that read
them sit here, beside this module.

A printed value is read through :func:`jyotirganita.data.datum.load_fixture`,
so a test sees the value the loader accepted (the adopted emendation where
the fixture records one, parsed by its form) and never a number typed into
the test.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from jyotirganita.core.eras import Era
from jyotirganita.core.types import JDN
from jyotirganita.data.datum import Fixture, Records, context_for, load_fixture, load_records
from jyotirganita.data.eras import load_eras

REPO = Path(__file__).resolve().parents[2]


class Printed:
    """The printed values of one fixture, by name."""

    def __init__(self, fixture_id: str) -> None:
        self.id = fixture_id
        self.fixture: Fixture = load_fixture(
            REPO / "tests" / f"{fixture_id}.yaml", context_for(REPO), repo=REPO
        )
        self._by_name = {r.key.split("#", 1)[1]: r for r in self.fixture.values}

    def __getitem__(self, name: str) -> Any:
        """The value as adopted (the emendation's where there is one), parsed by its form."""
        return self._by_name[name].value

    def columns(self, name: str) -> list[str]:
        """The column names of a table value."""
        return list(self._by_name[name].raw["columns"])

    def rows(self, name: str) -> list[dict[str, Any]]:
        """A table value's rows as mappings from column name to cell."""
        cols = self.columns(name)
        return [dict(zip(cols, row, strict=True)) for row in self[name]]


@cache
def printed(fixture_id: str) -> Printed:
    """The printed values of the fixture ``fixture_id`` (``authority/<text>/<example>``)."""
    return Printed(fixture_id)


@cache
def eras() -> dict[str, Era]:
    """The era records of ``jyotirganita/data/eras/`` (Kali, Śaka, Kollam), by id."""
    files = load_eras(REPO / "jyotirganita" / "data", context_for(REPO), REPO)
    return {k: ef.era for k, ef in files.items()}


def epoch(era_id: str) -> JDN:
    """The epoch day of ``era_id``'s record; an era without one is a hard error."""
    day = eras()[era_id].epoch
    if day is None:
        raise AssertionError(f"era {era_id} has no epoch day")
    return day


@cache
def records() -> Records:
    """Every record of the repository, loaded once per test session."""
    return load_records(REPO, context_for(REPO))


def text_value(text: str, suffix: str) -> Any:
    """The loader's value of the datum ``texts.<text>.<suffix>``."""
    return records().data[f"texts.{text}.{suffix}"].value
