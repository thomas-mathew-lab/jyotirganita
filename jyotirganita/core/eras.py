"""Era arithmetic, generic over era records.

This module knows no era by name. An :class:`Era` is built from a data
file ``data/eras/<era_id>.yaml`` by ``jyotirganita/data/eras.py``: its
epoch (a tagged Julian or Gregorian date, cited, and the JDN computed from
it), whether its years are counted elapsed or current, its year-start
options (each a rule from the registered vocabulary with its ``sun``
component, ``true`` or ``mean``, and the epoch the option counts from),
its range, and its month naming; or, for a cyclic record, a cycle of
year names anchored to a year of another era.

**Years.** The first civil days of the years come from a
:class:`YearStartStream`: the calendar layer's month stream for an almanac
era (the day the named saṅkrānti is assigned to, true or mean Sun),
or a method's mean year for the ``text_only`` Kali count. For a day
*D* in the era's range, let *k* be the number of year starts in
(*epoch*, *D*]: the year is *k* when the era counts elapsed years and
*k* + 1 when it counts current years. For an elapsed count the year *N*
is therefore the one that begins when *N* years have elapsed, and the elapsed and current readings
of one printed year number
begin exactly one year apart (:func:`first_day_of_year`).

**The epoch's own start.** An epoch is the first day of the year 0. A
month rule may give the year start that belongs to the epoch a later
civil day: the Śaka epoch is the day of its Meṣa saṅkrānti, and
``following_day`` begins the month on the next day. That start is the
year 0's, not the year 1's, and is not counted in *k*
(:meth:`YearStartStream.moved_own_start`).

**Days.** The era's day count is the number of civil days from the epoch's
civil day to *D* (:func:`days_from_epoch`): the Kali ahargaṇa when the era
is Kali and the epoch datum is the Kali epoch's.

**Range.** A day outside the era's range gives :data:`NOT_IN_RANGE`, never a negative year and never
a refusal.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Protocol, final

from jyotirganita.core.types import JDN

__all__ = [
    "NOT_IN_RANGE",
    "Counting",
    "Cycle",
    "Era",
    "EraRange",
    "EraYear",
    "NotInRange",
    "Sun",
    "YearStart",
    "YearStartStream",
    "cycle_name",
    "day_from_epoch_days",
    "days_from_epoch",
    "era_year",
    "first_day_of_year",
    "in_range",
]

type Counting = Literal["elapsed", "current"]
COUNTINGS = ("elapsed", "current")


def _check_counting(counting: object, what: str) -> None:
    """Refuse a counting other than elapsed or current."""
    if counting not in COUNTINGS:
        raise ValueError(f"{what}: counting {counting!r} is not one of {COUNTINGS}")


class Sun(Enum):
    """Whether the true Sun's entry (the almanac's) or the mean Sun's starts the year."""

    TRUE = "true"
    MEAN = "mean"


@final
class NotInRange:
    """The value of an era for a day outside its range."""

    _instance: NotInRange | None = None

    def __new__(cls) -> NotInRange:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "not_in_range"


NOT_IN_RANGE = NotInRange()


@final
@dataclass(frozen=True, slots=True)
class EraRange:
    """The civil days an era serves: ``from_jdn`` through ``to_jdn`` (``None``: open)."""

    from_jdn: JDN
    to_jdn: JDN | None

    def __post_init__(self) -> None:
        if not isinstance(self.from_jdn, JDN) or not (
            self.to_jdn is None or isinstance(self.to_jdn, JDN)
        ):
            raise TypeError("an era range is (JDN, JDN | None)")
        if self.to_jdn is not None and self.to_jdn.days_since(self.from_jdn) < 0:
            raise ValueError("an era range ends before it begins")


@final
@dataclass(frozen=True, slots=True)
class YearStart:
    """One year-start option of an era: a registered rule, its Sun, its epoch."""

    option: str
    rule: str
    sun: Sun
    epoch: JDN
    datum: str


@final
@dataclass(frozen=True, slots=True)
class Cycle:
    """A cyclic year-name rule: ``names[(anchor_index + year − anchor_year) mod length]``.

    ``year`` is a year of the era ``anchor_era`` in that era's own counting,
    the same counting the anchor datum states its year in.
    """

    length: int
    names: tuple[str, ...]
    anchor_era: str
    anchor_year: int
    anchor_index: int

    def __post_init__(self) -> None:
        if self.length != len(self.names) or self.length < 1:
            raise ValueError("a cycle's length is the number of its names")
        if not (0 <= self.anchor_index < self.length):
            raise ValueError("a cycle's anchor names one of its names")


@final
@dataclass(frozen=True, slots=True)
class Era:
    """An era record: counted from an epoch, or cyclic."""

    id: str
    range: EraRange
    epoch: JDN | None = None
    counting: Counting | None = None
    year_starts: Mapping[str, YearStart] | None = None
    month_naming: str | None = None
    cycle: Cycle | None = None

    def __post_init__(self) -> None:
        counted = (self.epoch, self.counting, self.year_starts, self.month_naming)
        if self.cycle is None:
            if any(v is None for v in counted):
                raise ValueError(
                    f"era {self.id}: a counted era names its epoch, counting, year starts "
                    "and month naming"
                )
            assert self.year_starts is not None
            if not self.year_starts:
                raise ValueError(f"era {self.id}: at least one year-start option")
            _check_counting(self.counting, f"era {self.id}")
        elif any(v is not None for v in counted):
            raise ValueError(f"era {self.id}: a cyclic era has a cycle and nothing else")


@final
@dataclass(frozen=True, slots=True)
class EraYear:
    """The year of an era on a day: its number, the option, the year's first civil day."""

    era: str
    option: str
    year: int
    first_day: JDN


class YearStartStream(Protocol):
    """The first civil days of the years under one rule and Sun.

    The calendar layer's month stream implements it for the almanac eras; a method's mean year for
    the ``text_only`` Kali count.
    """

    def starts_between(self, rule: str, sun: Sun, after: JDN, through: JDN) -> int:
        """The number of year starts in (``after``, ``through``]; 0 when ``through`` ≤ ``after``."""
        ...

    def nth_start_after(self, rule: str, sun: Sun, after: JDN, n: int) -> JDN:
        """The ``n``-th year start strictly after ``after`` (``n`` ≥ 1)."""
        ...

    def moved_own_start(self, rule: str, sun: Sun, epoch: JDN) -> int:
        """1 when the first start strictly after ``epoch`` is the epoch's own, else 0.

        The epoch's own start lies after the epoch day when the month rule
        moved it there (module docstring, "The epoch's own start").
        """
        ...


def in_range(era: Era, day: JDN) -> bool:
    """Whether ``day`` is in ``era``'s range."""
    if not isinstance(day, JDN):
        raise TypeError(f"an era is evaluated on a JDN, not {type(day).__name__}")
    r = era.range
    return day.days_since(r.from_jdn) >= 0 and (r.to_jdn is None or r.to_jdn.days_since(day) >= 0)


def _counted(era: Era) -> tuple[JDN, Counting, Mapping[str, YearStart]]:
    if era.cycle is not None:
        raise ValueError(f"era {era.id} is cyclic: its years are names (cycle_name)")
    assert era.epoch is not None and era.counting is not None and era.year_starts is not None
    return era.epoch, era.counting, era.year_starts


def _option(era: Era, option: str) -> YearStart:
    _, _, starts = _counted(era)
    if option not in starts:
        raise KeyError(f"era {era.id} has no year-start option {option!r} ({sorted(starts)})")
    return starts[option]


def days_from_epoch(era: Era, day: JDN) -> int | NotInRange:
    """Civil days from the era's epoch day to ``day`` (the Kali ahargaṇa for Kali)."""
    epoch, _, _ = _counted(era)
    if not in_range(era, day):
        return NOT_IN_RANGE
    return day.days_since(epoch)


def day_from_epoch_days(era: Era, days: int) -> JDN | NotInRange:
    """The civil day ``days`` after the era's epoch day (the inverse of :func:`days_from_epoch`)."""
    if isinstance(days, bool) or not isinstance(days, int):
        raise TypeError("a day count is an int")
    epoch, _, _ = _counted(era)
    day = epoch.plus_days(days)
    return day if in_range(era, day) else NOT_IN_RANGE


def era_year(era: Era, day: JDN, option: str, stream: YearStartStream) -> EraYear | NotInRange:
    """The year of ``era`` on ``day`` under the year-start ``option`` (module docstring)."""
    _, counting, _ = _counted(era)
    ys = _option(era, option)
    if not in_range(era, day) or day.days_since(ys.epoch) < 0:
        return NOT_IN_RANGE
    own = stream.moved_own_start(ys.rule, ys.sun, ys.epoch)
    k = max(0, stream.starts_between(ys.rule, ys.sun, ys.epoch, day) - own)
    first = ys.epoch if k == 0 else stream.nth_start_after(ys.rule, ys.sun, ys.epoch, k + own)
    return EraYear(era.id, option, k if counting == "elapsed" else k + 1, first)


def first_day_of_year(
    era: Era, year: int, option: str, reading: Counting, stream: YearStartStream
) -> JDN | NotInRange:
    """The first civil day of ``year`` read as ``reading`` (elapsed or current).

    Read elapsed, year *N* begins when *N* years have elapsed: the *N*-th
    year start after the epoch (the epoch itself for *N* = 0), not counting
    the epoch's own start where a month rule moved it past the epoch
    (``moved_own_start``). Read
    current, year *N* is the *N*-th year: the (*N* − 1)-th start. A year
    before the era's first gives :data:`NOT_IN_RANGE`.
    """
    if isinstance(year, bool) or not isinstance(year, int):
        raise TypeError("a year number is an int")
    _check_counting(reading, "a year's reading")
    ys = _option(era, option)
    n = year if reading == "elapsed" else year - 1
    if n < 0:
        return NOT_IN_RANGE
    own = 0 if n == 0 else stream.moved_own_start(ys.rule, ys.sun, ys.epoch)
    day = ys.epoch if n == 0 else stream.nth_start_after(ys.rule, ys.sun, ys.epoch, n + own)
    return day if in_range(era, day) else NOT_IN_RANGE


def cycle_name(
    cycle_era: Era, base: Era, day: JDN, option: str, stream: YearStartStream
) -> str | NotInRange:
    """The year name of the cyclic ``cycle_era`` on ``day``, from ``base``'s year count."""
    cycle = cycle_era.cycle
    if cycle is None:
        raise ValueError(f"era {cycle_era.id} is not cyclic")
    if cycle.anchor_era != base.id:
        raise ValueError(f"era {cycle_era.id} is anchored to {cycle.anchor_era}, not {base.id}")
    if not in_range(cycle_era, day):
        return NOT_IN_RANGE
    y = era_year(base, day, option, stream)
    if isinstance(y, NotInRange):
        return NOT_IN_RANGE
    return cycle.names[(cycle.anchor_index + y.year - cycle.anchor_year) % cycle.length]
