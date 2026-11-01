"""Solar months, month rules and the year-start streams.

**The vocabulary.** A solar month is named by the rāśi the Sun enters at
its start (``names.yaml`` class ``masa``, 1 = Meṣa); a
year-start rule of an era record is ``sankranti.<rasi>`` with a rāśi id of
:data:`RASI_IDS` (:func:`rule_rasi`).

**Month rules** (:data:`MONTH_RULES`) are registered functions, each with
its citation and the parameters a profile supplies as data. Each takes the
rāśi and a day near its entry and returns the first civil day of the month:

- ``aparahna_parts`` (``parts``, ``within``): the Sun's sidereal entry
  (the saṅkrānti) is located on the civil day it falls in, at its time
  after sunrise by the method's ending rule (``calendar/occurrences.py``);
  the daytime, sunrise to sunset, is divided into ``parts`` equal parts and
  the month begins that day when the entry falls within the first
  ``within`` of them, otherwise on the next day (sewell_dikshit_1896 Art. 28 rule (b),
  ``regions.kerala.conventions.month_rule.statement.sewell_dikshit_1896``; the boundary
  itself goes to the next day). A frame that states no sunset cannot
  serve it (:class:`MonthRuleNotModelled`).
- ``following_day`` (no parameters): the month begins on the civil day
  after the one in which the Sun's sidereal entry falls, whatever its
  hour. Witnessed by the saṅkramam rows and month headings of the Basel
  Mission almanac of 1868 (basel_panchangam_1868), whose pages are not yet keyed: its statement
  datum
  ``regions.kerala.conventions.month_rule.following_day.basel_panchangam_1868`` is a
  recorded gap and the rule ships provisional, flagged
  ``provisional:following_day``, selectable in the Kerala profile beside
  the default ``aparahna_parts``.
- ``sunset`` (no parameters): the month begins on the civil day of the
  entry when it falls after sunrise and before sunset, otherwise on the
  next day (sewell_dikshit_1896 Art. 28 rule (a), the rule sewell_dikshit_1896 gives for the Tamil
  and
  Tinnevelly countries: ``regions.kerala.conventions.month_rule.sunset.
  statement.sewell_dikshit_1896`` and ``.region.sewell_dikshit_1896``). An entry at sunset itself,
  which the rule does not name, goes to the next day. Selectable in the
  Kerala profile, flagged ``provisional:sunset``; a frame that states no
  sunset cannot serve it.
- ``fixed_tropical_offset`` (``offset``, ``days_after``): the month begins
  ``days_after`` civil days after the civil day in which the Sun's
  tropical longitude reaches ``offset`` plus 30° for each rāśi after Meṣa
  (the Calendar Reform Committee's kind; its data are
  not yet keyed). Evaluated on the engine protocol's ``tropical_longitude``; the
  siddhantic engine has none and the rule raises
  :class:`MonthRuleNotModelled` there.

**Year starts** (``core/eras.py``'s :class:`YearStartStream`).

- :class:`MeanYearStream` (``sun: mean``): the mean Sun's entries, from
  the method's revolutions of the Sun in its yuga and civil days (the
  ahargaṇa rule, laghubhaskariya_1963 I.15–17; the ``text_only`` count). The
  year starts on the first civil day at whose start the mean Sun has
  entered the rāśi: for Meṣa with no additive signs these are the days on
  which the engine's ``completed_years`` increases, so the stream and the
  method's year count agree by construction. Pure integer arithmetic.
- :class:`MonthStream` (``sun: true``): the true Sun's entries under the
  profile's month rule. The *K*-th entry is sought within ``SEARCH_DAYS``
  of the *K*-th mean entry and belongs to it: a year start is counted
  after a day ``after`` when its mean entry lies after ``after`` and its
  first civil day does too, so that the start current at an era's epoch
  is never counted as the epoch's first year. The epoch's own start may
  still fall after the epoch day, where the month rule moves it to a
  later day (the Śaka epoch under ``following_day``); ``moved_own_start``
  says so, and ``core/eras.py`` does not count it.

- :class:`NearestEntryMonthStream` (``sun: true`` under the modern engine):
  the same months, with the year starts counted from an era's epoch by
  the run's own locator (``modern/source.py``), which has no text's mean
  Sun: the start whose locator entry lies nearest the epoch is the
  epoch's own and is not counted; every later start is, those before the
  run's range by the locator's count (each lies more than ``SEARCH_DAYS``
  inside the window the locator places it in) and those inside it by the
  month rule.

Integers and fractions only: the tropical rule
reaches floats only through the modern engine's types.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from jyotirganita.calendar import elements
from jyotirganita.calendar.occurrences import ElementSource, SourceDay
from jyotirganita.core.eras import Sun
from jyotirganita.core.types import JDN, AngleUnit, FloatArc, Nadika, NotModelled

__all__ = [
    "MONTH_RULES",
    "RASI_IDS",
    "SEARCH_DAYS",
    "MeanSun",
    "MeanYearStream",
    "MonthNotFound",
    "MonthOf",
    "MonthRule",
    "MonthRuleNotModelled",
    "MonthStream",
    "NearestEntryMonthStream",
    "Sankranti",
    "rule_rasi",
]

#: the rāśis in order from Meṣa (``names.yaml`` masa ids)
RASI_IDS = (
    "mesha",
    "vrishabha",
    "mithuna",
    "karkata",
    "simha",
    "kanya",
    "tula",
    "vrishchika",
    "dhanu",
    "makara",
    "kumbha",
    "mina",
)
RULE_PREFIX = "sankranti."
SIGNS = 12
DEGREES_PER_SIGN = 30
DEGREES_PER_REVOLUTION = 360
#: half the signs: an arc of fewer signs past a boundary is "entered"
HALF_SIGNS = 6
#: the days searched on either side of a mean entry for the true one: the
#: Sun's equation of centre under every text served is a few degrees, a
#: few days, and the month rule moves the start by at most one more day
SEARCH_DAYS = 10


class MonthRuleNotModelled(ValueError):
    """A month rule that needs what the engine's frame does not state."""


class MonthNotFound(ValueError):
    """A civil day before the first month start a run serves (the days after ``runs_from``).

    Also a year start the day's era count needs that lies before the run's
    range (:class:`NearestEntryMonthStream`): refused by name, never a bare
    error.
    """


def rule_rasi(rule: str) -> int:
    """The rāśi (1–12) a year-start rule ``sankranti.<rasi>`` names."""
    if not rule.startswith(RULE_PREFIX) or rule[len(RULE_PREFIX) :] not in RASI_IDS:
        raise ValueError(f"{rule!r} is not a year-start rule (sankranti.<rasi>, {RASI_IDS})")
    return RASI_IDS.index(rule[len(RULE_PREFIX) :]) + 1


def _previous(rasi: int) -> int:
    return (rasi - 2) % SIGNS + 1


def _entered(label: int, rasi: int) -> bool:
    """Whether a Sun in rāśi ``label`` has entered ``rasi`` (within half a circle after it)."""
    return (label - rasi) % SIGNS < HALF_SIGNS


@dataclass(frozen=True, slots=True)
class Sankranti:
    """The Sun's sidereal entry into ``rasi``: its civil day and its time after the day's start."""

    rasi: int
    day: JDN
    after_start: Nadika
    sunrise: Nadika | None
    sunset: Nadika | None
    length: Nadika


@dataclass(frozen=True, slots=True)
class MonthOf:
    """A civil day's solar month: its rāśi, first civil day and the day's place in it."""

    rasi: int
    first_day: JDN
    day_of_month: int


# --- the mean Sun -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MeanSun:
    """The mean Sun of a method: revolutions in its yuga, civil days, additive signs, epoch."""

    revolutions: int
    civil_days: int
    additive_signs: int | Fraction  # the mean Sun in signs at the epoch day's start
    epoch: JDN

    def _numerator(self, a: int, rasi: int) -> int | Fraction:
        # SIGNS × civil days × (mean Sun in revolutions − the rāśi's start)
        return SIGNS * self.revolutions * a + (self.additive_signs - rasi + 1) * self.civil_days

    def entries(self, rasi: int, day: JDN) -> int:
        """The mean entries into ``rasi`` counted to the start of ``day`` (a floor; may be < 0)."""
        a = day.days_since(self.epoch)
        return self._numerator(a, rasi) // (SIGNS * self.civil_days)

    def entry_day(self, rasi: int, k: int) -> JDN:
        """The first civil day at whose start the ``k``-th entry into ``rasi`` has happened."""
        target = SIGNS * self.civil_days * k - (self.additive_signs - rasi + 1) * self.civil_days
        a = -(-target // (SIGNS * self.revolutions))
        return self.epoch.plus_days(a)


class MeanYearStream:
    """The mean Sun's year starts (``sun: mean``), a :class:`YearStartStream`."""

    def __init__(self, mean: MeanSun) -> None:
        self.mean = mean

    def _rasi(self, rule: str, sun: Sun) -> int:
        if sun is not Sun.MEAN:
            raise ValueError("the mean year serves sun: mean only (the true Sun is MonthStream's)")
        return rule_rasi(rule)

    def starts_between(self, rule: str, sun: Sun, after: JDN, through: JDN) -> int:
        r = self._rasi(rule, sun)
        if through.days_since(after) <= 0:
            return 0
        return self.mean.entries(r, through) - self.mean.entries(r, after)

    def nth_start_after(self, rule: str, sun: Sun, after: JDN, n: int) -> JDN:
        r = self._rasi(rule, sun)
        if n < 1:
            raise ValueError("n ≥ 1")
        return self.mean.entry_day(r, self.mean.entries(r, after) + n)

    def moved_own_start(self, rule: str, sun: Sun, epoch: JDN) -> int:
        """0: no month rule moves a mean entry (core/eras.py, "The epoch's own start")."""
        self._rasi(rule, sun)
        return 0


# --- month rules --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MonthRule:
    """A registered month rule: its parameters (supplied as data), function and citation."""

    name: str
    parameters: tuple[str, ...]
    fn: Callable[[MonthStream, int, JDN, Mapping[str, Fraction]], JDN]
    citation: str


def _aparahna_parts(stream: MonthStream, rasi: int, near: JDN, p: Mapping[str, Fraction]) -> JDN:
    s = stream.sankranti(rasi, near)
    if s.sunrise is None or s.sunset is None:
        raise MonthRuleNotModelled("aparahna_parts needs the day's sunrise and sunset")
    after_sunrise = s.after_start - s.sunrise
    if after_sunrise < Nadika(0):
        raise MonthRuleNotModelled(
            "aparahna_parts: an entry before the sunrise of a civil day that starts earlier "
            "is not stated by the rule"
        )
    boundary = (s.sunset - s.sunrise) * (p["within"] / p["parts"])
    return s.day if after_sunrise < boundary else s.day.plus_days(1)


def _sunset(stream: MonthStream, rasi: int, near: JDN, p: Mapping[str, Fraction]) -> JDN:
    s = stream.sankranti(rasi, near)
    if s.sunrise is None or s.sunset is None:
        raise MonthRuleNotModelled("sunset needs the day's sunrise and sunset")
    if s.after_start < s.sunrise:
        raise MonthRuleNotModelled(
            "sunset: an entry before the sunrise of a civil day that starts earlier "
            "is not stated by the rule"
        )
    # the rule names an entry before sunset and one after it; one at sunset is
    # taken as not before it
    return s.day if s.after_start < s.sunset else s.day.plus_days(1)


def _following_day(stream: MonthStream, rasi: int, near: JDN, p: Mapping[str, Fraction]) -> JDN:
    return stream.sankranti(rasi, near).day.plus_days(1)


def _fixed_tropical_offset(
    stream: MonthStream, rasi: int, near: JDN, p: Mapping[str, Fraction]
) -> JDN:
    eng = stream.engine
    if eng is None:
        raise MonthRuleNotModelled("fixed_tropical_offset needs an engine")
    deg = AngleUnit.DEGREE
    off = p["offset"]
    target = FloatArc.of_int(off.numerator, deg) / off.denominator + FloatArc.of_int(
        DEGREES_PER_SIGN * (rasi - 1), deg
    )
    circle = FloatArc.of_int(DEGREES_PER_REVOLUTION, deg)
    half = FloatArc.of_int(DEGREES_PER_REVOLUTION // 2, deg)

    def entered(d: JDN) -> bool:
        lon = eng.tropical_longitude("sun", eng.instant(d, Nadika(0)))
        if isinstance(lon, NotModelled):
            raise MonthRuleNotModelled(
                "fixed_tropical_offset is evaluated on the tropical longitude, which this "
                "engine does not serve"
            )
        return bool((lon.arc.to(deg) - target).mod_arc(circle) < half)

    day = stream.bisect(entered, near)
    return day.plus_days(int(p["days_after"]))


MONTH_RULES: Mapping[str, MonthRule] = {
    r.name: r
    for r in (
        MonthRule(
            "aparahna_parts",
            ("parts", "within"),
            _aparahna_parts,
            "sewell_dikshit_1896 Art. 28 rule (b) "
            "(regions.kerala.conventions.month_rule.statement.sewell_dikshit_1896)",
        ),
        MonthRule(
            "following_day",
            (),
            _following_day,
            "the Basel Mission almanac of 1868 (basel_panchangam_1868), its saṅkramam rows and "
            "month headings "
            "(regions.kerala.conventions.month_rule.following_day.basel_panchangam_1868, a "
            "recorded gap)",
        ),
        MonthRule(
            "sunset",
            (),
            _sunset,
            "sewell_dikshit_1896 Art. 28 rule (a), the rule of the Tamil and Tinnevelly countries "
            "(regions.kerala.conventions.month_rule.sunset.statement.sewell_dikshit_1896, "
            ".region.sewell_dikshit_1896)",
        ),
        MonthRule(
            "fixed_tropical_offset",
            ("offset", "days_after"),
            _fixed_tropical_offset,
            "the Calendar Reform Committee's kind (its data not yet keyed)",
        ),
    )
}


def _check_parameters(rule: str, p: Mapping[str, Fraction]) -> None:
    """Refuse parameter values the rule cannot use."""
    if rule == "aparahna_parts" and not 0 < p["within"] <= p["parts"]:
        raise ValueError(f"aparahna_parts: within {p['within']} of {p['parts']} parts")
    if rule == "fixed_tropical_offset" and (
        p["days_after"] < 0 or p["days_after"].denominator != 1
    ):
        raise ValueError(f"fixed_tropical_offset: days_after {p['days_after']} is not whole")


# --- the true Sun's months ------------------------------------------------------------


class MonthStream:
    """The solar months of one method and observer under a month rule (module docstring).

    A :class:`YearStartStream` for ``sun: true``; :meth:`month_of` gives a
    day's month.
    """

    def __init__(
        self,
        source: ElementSource,
        mean: MeanSun,
        rule: str,
        parameters: Mapping[str, Fraction],
        engine: Any = None,
    ) -> None:
        if rule not in MONTH_RULES:
            raise KeyError(f"no month rule {rule!r} ({sorted(MONTH_RULES)})")
        missing = set(MONTH_RULES[rule].parameters) - set(parameters)
        if missing:
            raise ValueError(f"month rule {rule} needs {sorted(missing)}")
        _check_parameters(rule, parameters)
        self.source, self.mean, self.rule = source, mean, MONTH_RULES[rule]
        self.parameters = dict(parameters)
        self.engine = engine
        self._starts: dict[tuple[int, int], JDN] = {}
        self._moved: dict[tuple[str, int], int] = {}

    # the search

    def _day(self, d: JDN) -> SourceDay:
        return self.source.day(d)

    def bisect(self, entered: Callable[[JDN], bool], near: JDN) -> JDN:
        """The civil day in whose interval ``entered`` turns true, within the search of ``near``."""
        lo, hi = near.plus_days(-SEARCH_DAYS), near.plus_days(SEARCH_DAYS)
        first = self.source.runs_from
        if lo.days_since(first) < 0:
            lo = first
        if entered(lo) or not entered(hi):
            raise ValueError(
                f"no entry within {SEARCH_DAYS} days of JDN {near.value} "
                f"(searched JDN {lo.value}–{hi.value})"
            )
        while hi.days_since(lo) > 1:
            mid = lo.plus_days(hi.days_since(lo) // 2)
            if entered(mid):
                hi = mid
            else:
                lo = mid
        return lo

    def sankranti(self, rasi: int, near: JDN) -> Sankranti:
        """The Sun's sidereal entry into ``rasi`` nearest ``near`` (within the search)."""
        rasi_el = elements.RASI.id
        s = self.bisect(lambda d: _entered(self._day(d).labels[rasi_el], rasi), near)
        sd = self._day(s)
        if sd.labels[rasi_el] != _previous(rasi):
            raise ValueError(f"the Sun passes two rāśis on JDN {s.value}")
        return Sankranti(rasi, s, sd.endings[rasi_el], sd.sunrise, sd.sunset, sd.length)

    def start(self, rasi: int, k: int) -> JDN:
        """The first civil day of the month of the ``k``-th entry into ``rasi``."""
        key = (rasi, k)
        hit = self._starts.get(key)
        if hit is None:
            near = self.mean.entry_day(rasi, k)
            hit = self.rule.fn(self, rasi, near, self.parameters)
            self._starts[key] = hit
        return hit

    # a day's month

    def month_of(self, day: JDN) -> MonthOf:
        """The solar month ``day`` falls in."""
        r = self._day(day).labels[elements.RASI.id]
        best: tuple[int, JDN] | None = None
        horizon = day.plus_days(SEARCH_DAYS + 1)
        for rasi in (_previous(r), r, r % SIGNS + 1):
            k = self.mean.entries(rasi, horizon)
            for kk in (k, k - 1):
                if self.mean.entry_day(rasi, kk).days_since(self.source.runs_from) <= SEARCH_DAYS:
                    continue
                first = self.start(rasi, kk)
                if day.days_since(first) >= 0:
                    # the entry before it starts earlier still: it is not sought (a look-back
                    # of two years otherwise, past a bounded source's first day; the release
                    # review's L1, L4)
                    if best is None or first.days_since(best[1]) > 0:
                        best = (rasi, first)
                    break
        if best is None:
            raise MonthNotFound(
                f"no month start found for JDN {day.value}: the day falls before the first "
                f"month the run serves (an entry within {SEARCH_DAYS} days of runs_from, JDN "
                f"{self.source.runs_from.value}, opens no month)"
            )
        return MonthOf(best[0], best[1], day.days_since(best[1]) + 1)

    # the YearStartStream protocol (sun: true)

    def _rasi(self, rule: str, sun: Sun) -> int:
        if sun is not Sun.TRUE:
            raise ValueError("the month stream serves sun: true (the mean Sun is MeanYearStream's)")
        return rule_rasi(rule)

    def _counted(self, r: int, after: JDN, k: int) -> bool:
        return self.start(r, k).days_since(after) > 0

    def starts_between(self, rule: str, sun: Sun, after: JDN, through: JDN) -> int:
        r = self._rasi(rule, sun)
        if through.days_since(after) <= 0:
            return 0
        margin = SEARCH_DAYS + 1
        first = self.mean.entries(r, after) + 1
        last = self.mean.entries(r, through.plus_days(margin))
        if last < first:
            return 0
        sure_hi = self.mean.entries(r, through.plus_days(-margin))
        edge = {k for k in (first, first + 1) if k <= last} | set(
            range(max(first, sure_hi), last + 1)
        )
        middle = (last - first + 1) - len(edge)
        hits = sum(
            1
            for k in edge
            if self._counted(r, after, k) and through.days_since(self.start(r, k)) >= 0
        )
        return middle + hits

    def nth_start_after(self, rule: str, sun: Sun, after: JDN, n: int) -> JDN:
        r = self._rasi(rule, sun)
        if n < 1:
            raise ValueError("n ≥ 1")
        k = self.mean.entries(r, after) + 1
        while not self._counted(r, after, k):
            k += 1
        return self.start(r, k + n - 1)

    def moved_own_start(self, rule: str, sun: Sun, epoch: JDN) -> int:
        """1 when the first start after ``epoch`` is the epoch's own, moved past it, else 0.

        The epoch is a year start under some rule; the first start counted
        after it is the epoch's own when it lies nearer the epoch than the
        start after it (core/eras.py).
        """
        self._rasi(rule, sun)
        key = (rule, epoch.value)
        hit = self._moved.get(key)
        if hit is None:
            first = self.nth_start_after(rule, sun, epoch, 1)
            second = self.nth_start_after(rule, sun, epoch, 2)
            hit = 1 if 2 * first.days_since(epoch) < second.days_since(first) else 0
            self._moved[key] = hit
        return hit


class NearestEntryMonthStream(MonthStream):
    """Year starts counted from the locator entry nearest the epoch (module docstring)."""

    def _own(self, r: int, after: JDN) -> int:
        """The locator entry nearest ``after``: the epoch's own year start."""
        k = self.mean.entries(r, after)
        before, later = self.mean.entry_day(r, k), self.mean.entry_day(r, k + 1)
        return k if after.days_since(before) <= later.days_since(after) else k + 1

    def moved_own_start(self, rule: str, sun: Sun, epoch: JDN) -> int:
        """0: the epoch's own start, the nearest locator entry's, is never counted here."""
        self._rasi(rule, sun)
        return 0

    def _first_served(self, r: int) -> int:
        """The first entry whose month the run's range serves (its search window inside it)."""
        return self.mean.entries(r, self.source.runs_from.plus_days(SEARCH_DAYS)) + 1

    def starts_between(self, rule: str, sun: Sun, after: JDN, through: JDN) -> int:
        r = self._rasi(rule, sun)
        if through.days_since(after) <= 0:
            return 0
        lower = self._own(r, after) + 1
        served = self._first_served(r)
        margin = SEARCH_DAYS + 1
        last = self.mean.entries(r, through.plus_days(margin))
        unserved = max(0, min(served, last + 1) - lower)
        lo = max(lower, served)
        if last < lo:
            return unserved
        sure_hi = self.mean.entries(r, through.plus_days(-margin))
        sure = max(0, min(sure_hi, last) - lo + 1)
        edge = range(max(lo, sure_hi + 1), last + 1)
        hits = sum(1 for k in edge if through.days_since(self.start(r, k)) >= 0)
        return unserved + sure + hits

    def nth_start_after(self, rule: str, sun: Sun, after: JDN, n: int) -> JDN:
        r = self._rasi(rule, sun)
        if n < 1:
            raise ValueError("n ≥ 1")
        k = self._own(r, after) + n
        if k < self._first_served(r):
            raise MonthNotFound(
                f"the year start {n} after JDN {after.value} lies before the run's range "
                f"(from JDN {self.source.runs_from.value}); its first day is not computed"
            )
        return self.start(r, k)
