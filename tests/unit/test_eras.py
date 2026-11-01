"""Era arithmetic over planted era records.

The fourth, fictitious era and the three-name cycle are planted: their
dates, years and names are invented test values, not readings of any
source. They show that ``core/eras.py`` serves a new era record without a
code change, under both ``sun`` values, and that a day outside the era's
range gives ``not_in_range``.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from records_kit import FABLE, Sample, datum, read

from jyotirganita.core.calendar import jdn_from_julian
from jyotirganita.core.eras import (
    NOT_IN_RANGE,
    Era,
    EraRange,
    EraYear,
    Sun,
    YearStart,
    cycle_name,
    day_from_epoch_days,
    days_from_epoch,
    era_year,
    first_day_of_year,
)
from jyotirganita.core.types import JDN, JulianDate
from jyotirganita.data.datum import DatumError, context_for
from jyotirganita.data.eras import load_era, load_eras

# --- planted streams -------------------------------------------------------------------

# A planted "true Sun" stream: irregular year lengths, cycling.
TRUE_LENGTHS = (365, 366, 365, 365, 366, 364, 366)
# A planted "mean Sun" stream: year n starts at floor(origin + n * MEAN_YEAR).
MEAN_YEAR = Fraction(146101, 400)


class PlantedStream:
    """Year starts from a planted origin, one sequence per ``sun`` value."""

    def __init__(self, origin: JDN) -> None:
        self.origin = origin
        self.calls: list[Sun] = []

    def _start(self, sun: Sun, n: int) -> JDN:
        """The n-th year start counted from the origin (n may be negative)."""
        if sun is Sun.MEAN:
            return self.origin.plus_days(int((n * MEAN_YEAR) // 1))
        cycle = sum(TRUE_LENGTHS)
        q, r = divmod(n, len(TRUE_LENGTHS))
        return self.origin.plus_days(q * cycle + sum(TRUE_LENGTHS[:r]))

    def _index_on_or_before(self, sun: Sun, day: JDN) -> int:
        n = day.days_since(self.origin) // 366
        while self._start(sun, n + 1).days_since(day) <= 0:
            n += 1
        while self._start(sun, n).days_since(day) > 0:
            n -= 1
        return n

    def starts_between(self, rule: str, sun: Sun, after: JDN, through: JDN) -> int:
        self.calls.append(sun)
        if through.days_since(after) <= 0:
            return 0
        return self._index_on_or_before(sun, through) - self._index_on_or_before(sun, after)

    def nth_start_after(self, rule: str, sun: Sun, after: JDN, n: int) -> JDN:
        assert n >= 1
        self.calls.append(sun)
        return self._start(sun, self._index_on_or_before(sun, after) + n)

    def moved_own_start(self, rule: str, sun: Sun, epoch: JDN) -> int:
        return 0  # the planted epochs are year starts under the planted rule


# --- planted records ------------------------------------------------------------------


def text(key: str, value: str) -> dict[str, Any]:
    return datum(key, value=value, form="text", unit="statement")


EPOCH_TEXT = "March 1, 1000 A.D."  # planted
EPOCH_JDN = jdn_from_julian(JulianDate(1000, 3, 1))
LAST_JDN = EPOCH_JDN.plus_days(40000)


def fict_record(**over: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "era": "fict",
        "epoch": {
            "date": "eras.fict.epoch",
            "calendar": "julian",
            "calendar_ref": "eras.fict.calendar",
            "day_start": "unstated",
        },
        "counting": {"mode": "elapsed", "datum": "eras.fict.counting"},
        "year_start": {
            "true_sun": {
                "rule": "sankranti.mesha",
                "sun": True,
                "epoch": "era",
                "datum": "eras.fict.year_start.true_sun",
            },
            "mean_sun": {
                "rule": "sankranti.mesha",
                "sun": "mean",
                "epoch": "era",
                "datum": "eras.fict.year_start.mean_sun",
            },
        },
        "range": {"from": "epoch", "to": LAST_JDN.value, "datum": "eras.fict.range"},
        "months": {"naming": "rasi", "datum": "eras.fict.months"},
        "notes": "planted",
        "data": [
            text("eras.fict.epoch", EPOCH_TEXT),
            text("eras.fict.calendar", "planted: Old Style"),
            text("eras.fict.counting", "planted: years elapsed"),
            text("eras.fict.year_start.true_sun", "planted: true Mesha"),
            text("eras.fict.year_start.mean_sun", "planted: mean Mesha"),
            text("eras.fict.range", "planted: from the epoch"),
            text("eras.fict.months", "planted: months by rasi"),
        ],
    }
    doc.update(over)
    return doc


def cycle_record() -> dict[str, Any]:
    return {
        "era": "trio",
        "cycle": {
            "length": 3,
            "names": "eras.trio.names",
            "anchor": {"datum": "eras.trio.anchor", "era": "fict", "year": 7, "name": "beta"},
        },
        "range": {"from": EPOCH_JDN.value, "to": "open", "datum": "eras.trio.range"},
        "notes": "planted",
        "data": [
            datum(
                "eras.trio.names",
                value=[["alpha"], ["beta"], ["gamma"]],
                form="table",
                columns=["name"],
                unit="names",
                second_read=[read(FABLE)],
            ),
            text("eras.trio.anchor", "planted: year 7 is beta"),
            text("eras.trio.range", "planted"),
        ],
    }


@pytest.fixture
def sample(tmp_path: Path) -> Sample:
    return Sample(tmp_path)


def load(sample: Sample, doc: dict[str, Any]) -> Era:
    path = sample.write(f"jyotirganita/data/eras/{doc['era']}.yaml", doc)
    return load_era(path, context_for(sample.root), sample.root).era


# --- the fourth era ------------------------------------------------------------------


def test_fourth_era_loads_from_its_record_alone(sample: Sample) -> None:
    era = load(sample, fict_record())
    assert era.id == "fict"
    assert era.epoch == EPOCH_JDN
    assert era.counting == "elapsed"
    assert era.year_starts is not None
    assert {o.sun for o in era.year_starts.values()} == {Sun.TRUE, Sun.MEAN}


def test_both_sun_values_reach_the_stream_and_give_their_own_years(sample: Sample) -> None:
    era = load(sample, fict_record())
    stream = PlantedStream(EPOCH_JDN)
    # A day where the planted true and mean sequences have counted different
    # numbers of years: the arithmetic follows the option's Sun.
    found = False
    for k in range(1, 100):
        day = EPOCH_JDN.plus_days(k * 365 + 3)
        t = era_year(era, day, "true_sun", stream)
        m = era_year(era, day, "mean_sun", stream)
        assert isinstance(t, EraYear) and isinstance(m, EraYear)
        if t.year != m.year:
            found = True
            break
    assert found
    assert Sun.TRUE in stream.calls and Sun.MEAN in stream.calls


@pytest.mark.parametrize("option", ["true_sun", "mean_sun"])
def test_year_counts_start_at_the_epoch(sample: Sample, option: str) -> None:
    era = load(sample, fict_record())
    stream = PlantedStream(EPOCH_JDN)
    y0 = era_year(era, EPOCH_JDN, option, stream)
    assert y0 == EraYear("fict", option, 0, EPOCH_JDN)  # elapsed: none yet
    first = first_day_of_year(era, 1, option, "elapsed", stream)
    assert isinstance(first, JDN)
    before = era_year(era, first.plus_days(-1), option, stream)
    after = era_year(era, first, option, stream)
    assert isinstance(before, EraYear) and isinstance(after, EraYear)
    assert (before.year, after.year) == (0, 1)
    assert after.first_day == first


def test_current_counting_is_one_more_than_elapsed(sample: Sample) -> None:
    elapsed = load(sample, fict_record())
    current = load(sample, fict_record(counting={"mode": "current", "datum": "eras.fict.counting"}))
    stream = PlantedStream(EPOCH_JDN)
    for k in (0, 1, 500, 12345, 39999):
        day = EPOCH_JDN.plus_days(k)
        e = era_year(elapsed, day, "true_sun", stream)
        c = era_year(current, day, "true_sun", stream)
        assert isinstance(e, EraYear) and isinstance(c, EraYear)
        assert c.year == e.year + 1
        assert c.first_day == e.first_day


@pytest.mark.parametrize("option", ["true_sun", "mean_sun"])
def test_convention_elapsed_and_current_begin_one_year_apart(sample: Sample, option: str) -> None:
    """the two readings of one year number begin one year apart."""
    era = load(sample, fict_record())
    stream = PlantedStream(EPOCH_JDN)
    for n in (1, 2, 17, 60):
        as_elapsed = first_day_of_year(era, n, option, "elapsed", stream)
        as_current = first_day_of_year(era, n, option, "current", stream)
        assert isinstance(as_elapsed, JDN) and isinstance(as_current, JDN)
        # exactly one year apart: as_elapsed is the next year start after as_current
        assert stream.nth_start_after("r", era.year_starts[option].sun, as_current, 1) == (  # type: ignore[index]
            as_elapsed
        )
        y = era_year(era, as_current, option, stream)
        assert isinstance(y, EraYear) and y.year == n - 1  # the record counts elapsed


def test_days_outside_the_range_are_not_in_range(sample: Sample) -> None:
    era = load(sample, fict_record())
    stream = PlantedStream(EPOCH_JDN)
    for day in (EPOCH_JDN.plus_days(-1), LAST_JDN.plus_days(1)):
        assert era_year(era, day, "true_sun", stream) is NOT_IN_RANGE
        assert era_year(era, day, "mean_sun", stream) is NOT_IN_RANGE
        assert days_from_epoch(era, day) is NOT_IN_RANGE
    assert isinstance(era_year(era, LAST_JDN, "true_sun", stream), EraYear)
    assert first_day_of_year(era, 0, "true_sun", "current", stream) is NOT_IN_RANGE
    assert first_day_of_year(era, 500, "true_sun", "elapsed", stream) is NOT_IN_RANGE
    assert repr(NOT_IN_RANGE) == "not_in_range"


def test_epoch_day_counts_round_trip_at_the_boundaries(sample: Sample) -> None:
    era = load(sample, fict_record())
    for n in (0, 1, 2, 39998, 39999, 40000):
        day = day_from_epoch_days(era, n)
        assert isinstance(day, JDN)
        assert days_from_epoch(era, day) == n
    assert day_from_epoch_days(era, -1) is NOT_IN_RANGE
    assert day_from_epoch_days(era, 40001) is NOT_IN_RANGE


def test_an_unknown_option_is_refused(sample: Sample) -> None:
    era = load(sample, fict_record())
    with pytest.raises(KeyError, match="no year-start option"):
        era_year(era, EPOCH_JDN, "kanya", PlantedStream(EPOCH_JDN))


# --- the cyclic form --------------------------------------------------------------------


def test_cyclic_era_names_years_modulo_its_length(sample: Sample) -> None:
    sample.write("jyotirganita/data/eras/fict.yaml", fict_record())
    sample.write("jyotirganita/data/eras/trio.yaml", cycle_record())
    eras = load_eras(sample.root / "jyotirganita" / "data", context_for(sample.root), sample.root)
    fict, trio = eras["fict"].era, eras["trio"].era
    stream = PlantedStream(EPOCH_JDN)
    seen = {}
    for n in range(0, 12):
        start = first_day_of_year(fict, n, "true_sun", "elapsed", stream)
        assert isinstance(start, JDN)
        seen[n] = cycle_name(trio, fict, start, "true_sun", stream)
    assert seen[7] == "beta"  # the anchor
    assert [seen[n] for n in (8, 9, 10)] == ["gamma", "alpha", "beta"]
    assert all(seen[n] == seen[n + 3] for n in range(0, 9))
    assert cycle_name(trio, fict, EPOCH_JDN.plus_days(-1), "true_sun", stream) is NOT_IN_RANGE


def test_cyclic_record_with_an_unknown_anchor_name_fails(sample: Sample) -> None:
    doc = cycle_record()
    doc["cycle"]["anchor"]["name"] = "delta"
    with pytest.raises(DatumError, match="anchor name"):
        load(sample, doc)


# --- the record's own rules ------------------------------------------------------------


def test_era_record_names_only_its_own_datums(sample: Sample) -> None:
    doc = fict_record()
    doc["counting"]["datum"] = "eras.fict.elsewhere"
    with pytest.raises(DatumError, match="not a datum of this file"):
        load(sample, doc)


def test_era_record_without_month_naming_fails_the_schema(sample: Sample) -> None:
    doc = fict_record()
    del doc["months"]
    with pytest.raises(DatumError):
        load(sample, doc)


def test_era_file_name_is_its_id(sample: Sample) -> None:
    doc = fict_record()
    path = sample.write("jyotirganita/data/eras/other.yaml", doc)
    with pytest.raises(DatumError, match="not its file name"):
        load_era(path, context_for(sample.root), sample.root)


def test_epoch_printed_weekday_must_match(sample: Sample) -> None:
    doc = fict_record()
    doc["data"][0] = text("eras.fict.epoch", "Sunday, " + EPOCH_TEXT)
    wd_ok = load(sample, fict_record()).epoch
    assert wd_ok == EPOCH_JDN
    from jyotirganita.core.calendar import weekday

    if weekday(EPOCH_JDN).name != "SUNDAY":
        with pytest.raises(DatumError, match="weekday"):
            load(sample, doc)


def table_epoch(rows: list[list[Any]], columns: list[str]) -> dict[str, Any]:
    return datum(
        "eras.fict.epoch",
        value=rows,
        form="table",
        columns=columns,
        unit="statement",
        second_read=[read(FABLE)],
    )


def test_epoch_may_be_the_date_cell_of_a_one_row_table(sample: Sample) -> None:
    doc = fict_record()
    doc["data"][0] = table_epoch([["planted era", EPOCH_TEXT, 7]], ["era", "date", "n"])
    assert load(sample, doc).epoch == EPOCH_JDN


@pytest.mark.parametrize(
    "rows,columns",
    [
        ([["planted era", EPOCH_TEXT]], ["era", "when"]),
        ([["a", EPOCH_TEXT], ["b", EPOCH_TEXT]], ["era", "date"]),
    ],
)
def test_a_table_epoch_is_one_row_with_a_date_column(
    sample: Sample, rows: list[list[Any]], columns: list[str]
) -> None:
    doc = fict_record()
    doc["data"][0] = table_epoch(rows, columns)
    with pytest.raises(DatumError, match="one row with a `date` column"):
        load(sample, doc)


def test_hand_built_era_needs_a_complete_record() -> None:
    rng = EraRange(JDN(0), None)
    with pytest.raises(ValueError, match="counted era"):
        Era("x", rng, epoch=JDN(0))
    ys = {"a": YearStart("a", "r", Sun.TRUE, JDN(0), "k.k")}
    Era("x", rng, epoch=JDN(0), counting="current", year_starts=ys, month_naming="rasi")


# --- contradictions ---------------------------------------------------------------------


def test_a_contradiction_names_an_issue_and_existing_datums(sample: Sample) -> None:
    from jyotirganita.data.datum import load_records

    doc = fict_record()
    doc["data"].append(
        text("eras.fict.epoch_other", "March 5, 1000 A.D.")
        | {"contradiction": {"issue": "I-999", "with": ["eras.fict.epoch"]}}
    )
    sample.write("jyotirganita/data/eras/fict.yaml", doc)
    with pytest.raises(DatumError, match=r"not in the issue register"):
        load_records(sample.root)
    doc["data"][-1]["contradiction"] = {"issue": "I-901", "with": ["eras.fict.nowhere"]}
    sample.write("jyotirganita/data/eras/fict.yaml", doc)
    with pytest.raises(DatumError, match="not a datum"):
        load_records(sample.root)
