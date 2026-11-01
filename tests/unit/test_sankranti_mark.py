"""One saṅkrānti mark per month start, decided by one route.

A code review found a saṅkrānti
within seconds of a sunrise marked on no civil
day, or on two: the day record, :func:`jyotirganita.api.sankrantis` and
the search's ``sankranti_day`` tested day *n*'s ending time against the
day's length, while the month stream (``calendar/months.py``) decides the
day by the Sun's rāśi at the sunrises of *n* and *n* + 1, and the two
routes disagree by seconds there. The cases are the review's (parahita
under the Kerala profile at Thiruvananthapuram: the Meṣa entry of JDN
1920196–1920197, and the month starting on JDN 1491112). The mark now
follows the month stream's route; the instant stays the day's own
estimate. Engine output only, as change detectors of the route; no
printed value enters here.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import pytest
from modern_kit import records
from record_kit import REPO
from search_kit import config as search_config
from search_kit import query

from jyotirganita import api
from jyotirganita.calendar import elements
from jyotirganita.calendar.occurrences import SourceDay, sankranti_in_day
from jyotirganita.config import RunConfig, open_config
from jyotirganita.core.calendar import Weekday
from jyotirganita.core.types import JDN, Nadika
from jyotirganita.search import search

PRESET = "parahita_kerala"
PLACE = "kerala/thiruvananthapuram"
#: (first day, last day, the day the month stream puts the entry on, the rāśi entered)
CASES = [(1920190, 1920205, 1920196, 1), (1491100, 1491115, 1491111, 4)]


@pytest.fixture(scope="module")
def cfg() -> RunConfig:
    return open_config(REPO, PRESET, PLACE, records=records())


@pytest.mark.parametrize(("first", "last", "day", "rasi"), CASES)
def test_one_mark_on_the_month_streams_day(
    cfg: RunConfig, first: int, last: int, day: int, rasi: int
) -> None:
    marks = [
        (s["dates"]["jdn"], s["rasi_index"]) for s in api.sankrantis(cfg, (JDN(first), JDN(last)))
    ]
    assert marks == [(day, rasi)]
    months = cfg.calendar.months
    assert months is not None
    assert months.sankranti(rasi, JDN(day)).day == JDN(day)
    assert cfg.calendar.sankranti(JDN(day))["rasi_index"] == rasi


@pytest.mark.parametrize(("first", "last", "day", "rasi"), CASES)
def test_the_search_finds_the_marked_day(first: int, last: int, day: int, rasi: int) -> None:
    sc = search_config(PRESET, PLACE)
    doc = query([{"element": "sankranti_day", "value": rasi}], first, last)
    assert [c.jdn for c in search(sc, doc)] == [day]


# --- the route on synthetic days ------------------------------------------------------------

LENGTH = Nadika(Fraction(60))


@dataclass
class _Days:
    """Civil days whose Sun stands in ``rasis[i]`` at sunrise, its sign ending at ``ends[i]``."""

    rasis: list[int]
    ends: list[Fraction]

    @property
    def id(self) -> str:
        return "synthetic"

    @property
    def runs_from(self) -> JDN:
        return JDN(0)

    def day(self, jdn: JDN) -> SourceDay:
        i = jdn.value
        rasi = elements.RASI.id
        return SourceDay(
            jdn,
            LENGTH,
            Nadika(0),
            None,
            None,
            {rasi: self.rasis[i]},
            {rasi: Nadika(self.ends[i])},
            {},
            (),
            "lmt",
            None,
            Weekday(0),
            None,
        )


def _marks(days: _Days) -> list[tuple[int, int, Fraction]]:
    out = []
    for n in range(len(days.rasis) - 1):
        s = sankranti_in_day(days, JDN(n))
        if s is not None:
            out.append((n, s[0], s[1].value))
    return out


def test_an_ending_estimate_past_the_day_is_marked_where_the_label_changes() -> None:
    """F1: the estimate falls after the day's end, the next sunrise is already in the sign."""
    days = _Days([12, 12, 1, 1], [Fraction(120), Fraction(6001, 100), Fraction(1800), Fraction(0)])
    assert _marks(days) == [(1, 1, Fraction(6001, 100))]


def test_an_ending_estimate_inside_the_day_is_not_marked_twice() -> None:
    """The mirror case: the estimate falls inside day 1, the next sunrise is still in the sign."""
    days = _Days(
        [12, 12, 12, 1, 1],
        [Fraction(120), Fraction(5999, 100), Fraction(1, 100), Fraction(1800), Fraction(0)],
    )
    assert _marks(days) == [(2, 1, Fraction(1, 100))]


def test_an_estimate_at_the_days_length_follows_the_label() -> None:
    """An estimate equal to the day's length: the label decides, either way."""
    at_end = Fraction(60)
    changed = _Days([12, 12, 1, 1], [Fraction(120), at_end, Fraction(1800), Fraction(0)])
    unchanged = _Days(
        [12, 12, 12, 1, 1], [Fraction(120), at_end, Fraction(0), Fraction(1800), Fraction(0)]
    )
    assert _marks(changed) == [(1, 1, at_end)]
    assert _marks(unchanged) == [(2, 1, Fraction(0))]
