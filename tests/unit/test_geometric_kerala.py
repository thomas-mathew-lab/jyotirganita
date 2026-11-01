"""The geometric sunrise under the Kerala presets.

``procedure.sunrise=modern_geometric:<preset>`` was refused under every
``*_kerala`` preset: a true-Sun era counts its years from its epoch, before
the days the modern sunrise serves. The owner kept it with a warning: the
years are counted on the text's own days before the geometric range and
on the geometric days within it (``calendar/day.py``, ``SplicedSource``),
every record carries ``diagnostic:era_years.text_sunrise``, and the run's
notice says so (the CLI prints it). The hybrid's sunset is the modern
engine's too, so every Kerala month rule serves it. Engine output only, as
change detectors of the route; no printed value enters here.
"""

from __future__ import annotations

import io
from fractions import Fraction
from typing import Any

import pytest
from modern_kit import records
from record_kit import GEOMETRIC, REPO

from jyotirganita import api
from jyotirganita.calendar.day import SplicedSource
from jyotirganita.calendar.occurrences import SourceDay
from jyotirganita.config import SPLICED_ERA_FLAG, RunConfig, open_config
from jyotirganita.core.exact import Rounding, round_to
from jyotirganita.core.types import JDN
from jyotirganita.io.cli import main

PRESET = "parahita_kerala"
PLACE = "kerala/thrissur"
RULE = {"conventions.month_rule": "following_day"}
#: the twelve days around the Meṣa entry of 1990 (JDN 2447996 is its first day under both)
MESHA_1990 = range(2447990, 2448002)


@pytest.fixture(scope="module")
def hybrid() -> RunConfig:
    return open_config(
        REPO, PRESET, PLACE, records=records(), **{"procedure.sunrise": GEOMETRIC, **RULE}
    )


@pytest.fixture(scope="module")
def text() -> RunConfig:
    return open_config(REPO, PRESET, PLACE, records=records(), **RULE)


def _years(rec: dict[str, Any]) -> dict[str, int]:
    return {e: v["year"] for e, v in rec["eras"].items() if isinstance(v, dict)}


def test_the_run_opens_flagged_with_a_notice(hybrid: RunConfig) -> None:
    assert SPLICED_ERA_FLAG in hybrid.diagnostic
    assert len(hybrid.notices) == 1 and SPLICED_ERA_FLAG in hybrid.notices[0]
    true_sun = [
        e
        for e, o in hybrid.options.items()
        if (hybrid.eras[e].era.year_starts or {})[o].sun.value == "true"
    ]
    assert true_sun and all(e in hybrid.notices[0] for e in true_sun)
    rec = api.day(hybrid, JDN(MESHA_1990[0]))
    assert SPLICED_ERA_FLAG in rec["flags"] and "hybrid_sunrise:modern_geometric" in rec["flags"]


def test_a_text_preset_without_a_true_sun_era_is_not_flagged() -> None:
    cfg = open_config(
        REPO, "aryabhatiya_text", PLACE, records=records(), **{"procedure.sunrise": GEOMETRIC}
    )
    assert SPLICED_ERA_FLAG not in cfg.diagnostic and cfg.notices == ()


def test_the_year_turns_on_the_first_day_of_the_month_shown(
    hybrid: RunConfig, text: RunConfig
) -> None:
    """Where the two sunrises agree on the month's first day, the two counts agree too."""
    turned = []
    prev: dict[str, int] | None = None
    for j in MESHA_1990:
        rec = api.day(hybrid, JDN(j))
        years = _years(rec)
        assert years == _years(api.day(text, JDN(j)))
        if prev is not None and years != prev:
            turned.append(j)
            assert rec["masa"]["day"] == 1
        prev = years
    assert turned == [2447996]


def test_the_months_follow_the_geometric_sunrise(hybrid: RunConfig, text: RunConfig) -> None:
    """A Karkaṭaka entry of 1991 the two sunrises put on neighbouring days (a scan of 1990–2009)."""
    marks = [
        [s["dates"]["jdn"] for s in api.sankrantis(cfg, (JDN(2448440), JDN(2448470)))]
        for cfg in (hybrid, text)
    ]
    assert marks[0] != marks[1] and {abs(marks[0][0] - marks[1][0])} == {1}


@pytest.mark.parametrize("rule", [None, "sunset"])
def test_the_month_rules_that_read_the_sunset_open_on_the_modern_sunset(rule: str | None) -> None:
    """The provider's sunset, quantised as its sunrise is, is the record's."""
    sets = {"procedure.sunrise": GEOMETRIC}
    if rule is not None:
        sets["conventions.month_rule"] = rule
    cfg = open_config(REPO, PRESET, PLACE, records=records(), **sets)
    jdn = JDN(MESHA_1990[0])
    rec = api.day(cfg, jdn)
    assert rec["masa"]["day"] >= 1
    engine = cfg.run.engine
    f = engine.sunrise_provider.sunset_fraction(jdn, engine.observer)
    expected = round_to(Fraction(f), engine.hybrid_quantum, Rounding.HALF_EVEN) * 60
    assert Fraction(rec["sunset"]["nadika_after_local_midnight"]) == expected
    sunrise = Fraction(rec["sunrise"]["nadika_after_local_midnight"])
    assert sunrise < expected < sunrise + 60


def test_the_cli_prints_the_notice(capsys: pytest.CaptureFixture[str]) -> None:
    argv = [
        "day",
        "--preset",
        PRESET,
        "--observer",
        PLACE,
        "--date",
        f"jdn:{MESHA_1990[0]}",
        "--set",
        f"procedure.sunrise={GEOMETRIC}",
        "--set",
        "conventions.month_rule=following_day",
    ]
    assert main(argv, out=io.BytesIO()) == 0
    err = capsys.readouterr().err
    assert "note:" in err and SPLICED_ERA_FLAG in err


# --- the splice on synthetic days --------------------------------------------------------


class _Named:
    def __init__(self, name: str, mark: str) -> None:
        self.name, self.mark = name, mark

    @property
    def id(self) -> str:
        return self.name

    @property
    def runs_from(self) -> JDN:
        return JDN(0 if self.mark == "outer" else 10)

    def day(self, jdn: JDN) -> SourceDay:
        return self.mark  # type: ignore[return-value]


def test_the_splice_takes_the_inner_days_in_range_only() -> None:
    s = SplicedSource(_Named("m", "inner"), _Named("m", "outer"), JDN(10), JDN(20))
    picked = {j: str(s.day(JDN(j))) for j in (9, 10, 15, 20, 21)}
    assert picked == {9: "outer", 10: "inner", 15: "inner", 20: "inner", 21: "outer"}
    assert s.runs_from == JDN(0) and s.id == "m"
    with pytest.raises(ValueError, match="one method"):
        SplicedSource(_Named("m", "inner"), _Named("n", "outer"), JDN(10), JDN(20))
