"""A civil day's calendar leaves.

:class:`Calendar` binds a method run, a convention set and the era records
and gives, for one civil day, the calendar part of the day record
as a plain dict (:meth:`Calendar.day`): the dates, the weekday, the
eras keyed by era id, sunrise and sunset, the day's length, each
occurrence element with its occurrences, the solar month and the
saṅkrānti, and the flags. The record itself, its schema and its canonical
serialisation are ``io/record.py``'s and ``io/jsonl.py``'s. Exact values are written as
``"num/den"``
strings, never as floats.

A **convention set** (:class:`ConventionSet`) is a regional profile
(``regions/base.py``) or the ``text_only`` set: the
text's own sunrise as the civil day, ``at_sunrise`` assignment, no month
rule, the one era ``kali`` counted from the method's mean Meṣa saṅkrānti
(``sun: mean``) by its own ahargaṇa; ``masa.rasi_index`` (the Sun's rāśi
at the day's start), ``sankranti.instant`` and ``weekday.index`` emitted
and every leaf the text does not define ``not_in_preset``, leaf by leaf.

**Eras.** Each era of the set is counted by :func:`core.eras.era_year`
under its year-start option (the set's default unless the caller selects
another the set offers): a ``sun: mean`` option from the method's mean
Sun (:class:`calendar.months.MeanYearStream`), a ``sun: true`` option
from the solar months under the set's month rule
(:class:`calendar.months.MonthStream`). Under the geometric sunrise
(``procedure.sunrise=modern_geometric:<preset>``) a ``sun: true`` count
reaches back to the era's epoch, before the days the modern sunrise
serves: its years are counted on :class:`SplicedSource`, the geometric
days inside their range and the text's own days before it (``era_source``), so that a year starts on
the day its month
does wherever the geometric sunrise serves. The months and the
neighbouring days are read on :class:`BoundedSource`, from the geometric
range's first day only. Every era leaf carries ``year``,
``year_start`` and ``sun``; the era the run counts its days from carries
the day count: ``ahargana`` under a siddhantic run, ``jdn_difference`` (the JDN difference from the
era record's epoch) under a modern one; an era whose months
are named by rāśi carries ``masa``, ``masa_index`` and ``day`` when a
month rule is in force. A day outside an era's range gives
``not_in_range``.

**Flags**: the method's (``provisional_method``, ``seam:<element>``,
``before_composition:<id>``, ...), ``kshaya:`` and ``vriddhi:`` from
consecutive assigned labels (``calendar/assignment.py``), and
``provisional:<id>`` for each provisional part the day used: the month
rule wherever a month leaf is written under it, a script's name table
wherever its forms are written.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import TYPE_CHECKING, Any

from jyotirganita.calendar import elements
from jyotirganita.calendar.assignment import DayPoints, assign, ksaya_vrddhi
from jyotirganita.calendar.months import (
    MeanSun,
    MeanYearStream,
    MonthStream,
    NearestEntryMonthStream,
)
from jyotirganita.calendar.occurrences import (
    ElementSource,
    SiddhanticSource,
    SourceDay,
    day_occurrences,
    sankranti_in_day,
    tithi_name_index,
)
from jyotirganita.core.calendar import gregorian_from_jdn, julian_from_jdn
from jyotirganita.core.eras import NotInRange, Sun, YearStartStream, era_year
from jyotirganita.core.types import JDN, GregorianDate, JulianDate, Nadika
from jyotirganita.data.eras import EraFile
from jyotirganita.regions.base import EraSpec, MonthRuleSpec, Profile, ProfileError
from jyotirganita.siddhantic.surya import SuryaModel
from jyotirganita.siddhantic.tabular import TableModel

if TYPE_CHECKING:
    from jyotirganita.methods.compose import MethodRun

__all__ = [
    "AHARGANA",
    "JDN_DIFFERENCE",
    "NOT_IN_PRESET",
    "NOT_IN_RANGE",
    "NOT_MODELLED",
    "OCCURRENCE_ELEMENTS",
    "TEXT_ONLY",
    "Binding",
    "Calendar",
    "ConventionSet",
    "SplicedSource",
    "conventions_of",
]

NOT_IN_PRESET = "not_in_preset"
NOT_MODELLED = "not_modelled"
NOT_IN_RANGE = "not_in_range"
#: the elements a civil day is cut into
OCCURRENCE_ELEMENTS = ("tithi", "nakshatra", "yoga", "karana")
DAYS_PER_WEEK = 7
RASI_NAMING = "rasi"
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
#: 86400 seconds to the day, 60 nāḍikās to the day
SECONDS_PER_NADIKA = 1440 * SECONDS_PER_MINUTE // 60
#: the day-count leaf of the era a run counts from: the text's ahargaṇa, or the JDN difference
#: from the era record's epoch under the modern engine
AHARGANA = "ahargana"
JDN_DIFFERENCE = "jdn_difference"


@dataclass(frozen=True, slots=True)
class Binding:
    """What the calendar reads of a run, whichever its engine.

    ``source`` is the element stream; ``locator`` the integer mean Sun the
    month stream searches from (the text's own under a siddhantic run, a
    search aid calibrated on the engine under a modern one,
    ``modern/source.py``); ``mean_year`` whether a ``sun: mean`` year start
    is served (only by a text's mean Sun; otherwise the year starts are
    counted from the locator entry nearest an era's epoch,
    :class:`~jyotirganita.calendar.months.NearestEntryMonthStream`); ``era``
    and ``day_count`` the era the run's day count is counted from and its
    leaf; ``clock`` whether sunrise and sunset are stated on a clock
    standard (hh:mm:ss) rather than in nāḍikās after local mean midnight.
    """

    method_id: str
    source: ElementSource
    locator: MeanSun
    mean_year: bool
    engine: Any
    era: str
    day_count: str
    runs_from: JDN
    clock: bool = False


def _siddhantic_binding(run: MethodRun) -> Binding:
    resolved = run.resolved
    model = resolved.model
    sun = model.planets["sun"]
    if isinstance(model, SuryaModel):
        # the count from creation placed on the Kali record; the mean Sun at the epoch's
        # sunrise is a quarter day's motion past the Kali midnight (i.67)
        mean = MeanSun(
            model.revolutions[sun.mean],
            model.elements.civil_days[sun.mean],
            model.mean_sun_signs_at_epoch_sunrise(),
            run.runs_from,
        )
        mean_year = True
    elif isinstance(model, TableModel):
        # guṇakāra/hāraka rates (drgganita_1963): the integer mean Sun without its drift and dhruva
        # is a
        # search aid only, so a sun: mean year start is not served (Binding.mean_year)
        rate = model.rates[sun.mean]
        mean = MeanSun(rate.guna, rate.hara, 0, run.runs_from)
        mean_year = False
    else:
        mean = MeanSun(
            model.revolutions[sun.mean],
            model.civil_days,
            model.additive_signs.get(sun.mean, 0),
            run.runs_from,
        )
        mean_year = True
    return Binding(
        resolved.method.id,
        SiddhanticSource(run),
        mean,
        mean_year,
        run.engine,
        resolved.era,
        AHARGANA,
        run.runs_from,
    )


@dataclass(frozen=True, slots=True)
class ConventionSet:
    """The calendar conventions a preset names: a regional profile or ``text_only``."""

    id: str
    assignment: str
    month_rule: MonthRuleSpec | None
    eras: tuple[EraSpec, ...]
    profile: Profile | None = None
    provisional: Mapping[str, str] = field(default_factory=dict)

    def era_option(self, era: str, option: str | None) -> str:
        """The year-start option of ``era``: the caller's if the set offers it, else the default."""
        spec = next((e for e in self.eras if e.era == era), None)
        if spec is None:
            raise ProfileError(f"the {self.id} conventions report no era {era!r}")
        if option is None:
            return spec.default_option
        if option != spec.default_option and option not in spec.selectable:
            raise ProfileError(f"{self.id}: era {era} offers no year-start option {option!r}")
        return option


#: the ``text_only`` set (module docstring)
TEXT_ONLY = ConventionSet("text_only", "at_sunrise", None, (EraSpec("kali", "mean", (), None),))


def conventions_of(profile: Profile) -> ConventionSet:
    """A regional profile as a convention set."""
    return ConventionSet(
        profile.region,
        profile.assignment,
        profile.month_rule,
        profile.eras,
        profile,
        profile.provisional,
    )


def _q(x: Fraction | Nadika) -> str:
    v = x.value if isinstance(x, Nadika) else Fraction(x)
    return f"{v.numerator}/{v.denominator}"


def _hms(after_midnight: Nadika) -> str:
    """Nāḍikās after midnight as hh:mm:ss on the clock, to the nearest second (half to even)."""
    seconds = round(after_midnight.value * SECONDS_PER_NADIKA)
    h, rest = divmod(seconds, SECONDS_PER_HOUR)
    m, sec = divmod(rest, SECONDS_PER_MINUTE)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _ymd(d: JulianDate | GregorianDate) -> dict[str, int]:
    return {"y": d.y, "m": d.m, "d": d.d}


def _vara_index(sd: SourceDay) -> int:
    """The week-day as ``names.yaml``'s vara index, 1 = Sunday (Weekday's value is Monday = 0)."""
    return (sd.weekday.value + 1) % DAYS_PER_WEEK + 1


class SplicedSource:
    """``inner``'s days from ``first`` through ``last``, ``outer``'s elsewhere (module docstring).

    The two sources compute the same method at the same observer; the
    splice is the year count's only (``Calendar``'s ``era_source``).
    """

    def __init__(self, inner: ElementSource, outer: ElementSource, first: JDN, last: JDN) -> None:
        if inner.id != outer.id:
            raise ValueError(f"a splice of {inner.id} and {outer.id}: one method's days only")
        self.inner, self.outer, self.first, self.last = inner, outer, first, last

    @property
    def id(self) -> str:
        return self.inner.id

    @property
    def runs_from(self) -> JDN:
        return self.outer.runs_from

    def day(self, jdn: JDN) -> SourceDay:
        inside = jdn.days_since(self.first) >= 0 and self.last.days_since(jdn) >= 0
        return (self.inner if inside else self.outer).day(jdn)


class BoundedSource:
    """``inner``'s days, served from ``first`` on (module docstring).

    The geometric sunrise serves a narrower range than its method run's
    ``runs_from``; the month stream and the neighbouring days look no
    earlier than ``first``.
    """

    def __init__(self, inner: ElementSource, first: JDN) -> None:
        self.inner, self.first = inner, first

    @property
    def id(self) -> str:
        return self.inner.id

    @property
    def runs_from(self) -> JDN:
        r = self.inner.runs_from
        return self.first if r.days_since(self.first) < 0 else r

    def day(self, jdn: JDN) -> SourceDay:
        return self.inner.day(jdn)


class Calendar:
    """The calendar leaves of one method run under one convention set (module docstring).

    ``era_source`` (the text's own days) and ``era_range`` (the days the
    run's own source serves) are given together under the geometric
    sunrise only: a true-Sun year count then runs on their splice.
    """

    def __init__(
        self,
        run: MethodRun | Binding,
        conventions: ConventionSet,
        eras: Mapping[str, EraFile],
        *,
        options: Mapping[str, str] | None = None,
        scripts: Sequence[str] = (),
        month_rule: str | None = None,
        era_source: ElementSource | None = None,
        era_range: tuple[JDN, JDN] | None = None,
    ) -> None:
        if (era_source is None) != (era_range is None):
            raise ValueError("era_source and era_range are given together")
        self.run = run
        self.conventions = conventions
        self.month_rule: MonthRuleSpec | None = None
        if conventions.month_rule is not None:
            self.month_rule = conventions.month_rule.select(month_rule)
        elif month_rule is not None:
            raise ProfileError(f"the {conventions.id} conventions have no month rule to select")
        b = run if isinstance(run, Binding) else _siddhantic_binding(run)
        self.binding = b
        self.source: ElementSource = b.source
        if era_range is not None:  # the geometric sunrise's days only
            self.source = BoundedSource(b.source, era_range[0])
        self.mean = b.locator
        self.mean_stream = MeanYearStream(self.mean)
        self.months: MonthStream | None = None
        #: the stream a true-Sun year count runs on: the month stream, or its splice
        self.year_months: MonthStream | None = None
        if self.month_rule is not None:
            stream = MonthStream if b.mean_year else NearestEntryMonthStream
            spec = (self.mean, self.month_rule.rule, self.month_rule.parameters, b.engine)
            self.months = stream(self.source, *spec)
            self.year_months = self.months
            if era_source is not None and era_range is not None:
                spliced = SplicedSource(self.source, era_source, *era_range)
                self.year_months = stream(spliced, *spec)
        self.options = {
            e.era: conventions.era_option(e.era, (options or {}).get(e.era))
            for e in conventions.eras
        }
        unknown = set(options or {}) - set(self.options)
        if unknown:
            raise ProfileError(f"{conventions.id} reports no era {sorted(unknown)}")
        self.eras: dict[str, EraFile] = {}
        for e in conventions.eras:
            ef = eras.get(e.era)
            if ef is None:
                raise ProfileError(f"no era record for {e.era}")
            self.eras[e.era] = ef
        self.time_base_era = b.era
        if conventions.id == TEXT_ONLY.id:
            kali = self.eras["kali"].era
            if b.day_count != AHARGANA or b.era != "kali" or kali.epoch != b.runs_from:
                raise ProfileError(
                    f"text_only: {b.method_id} does not count from the Kali epoch by its own "
                    "ahargaṇa; its Kali-day datum is not modelled here"
                )
        if scripts and conventions.profile is None:
            raise ProfileError(f"the {conventions.id} conventions hold no name table")
        self.scripts = tuple(scripts)

    # --- streams ------------------------------------------------------------------

    def _stream(self, sun: Sun) -> YearStartStream:
        if sun is Sun.MEAN:
            if not self.binding.mean_year:
                raise ProfileError(
                    f"{self.binding.method_id} has no text's mean Sun: a sun: mean year start "
                    "is not served"
                )
            return self.mean_stream
        if self.year_months is None:
            raise ProfileError(
                f"the {self.conventions.id} conventions have no month rule: a true-Sun year "
                "start is not served"
            )
        return self.year_months

    def _assigned(self, sd: SourceDay, element: str) -> int:
        points = DayPoints(sd.length, sd.sunrise, sd.midnight)
        return assign(self.conventions.assignment, day_occurrences(sd, element), points)

    def assigned(self, sd: SourceDay, element: str) -> int:
        """The label the set's assignment rule gives ``element`` on ``sd`` (the search)."""
        return self._assigned(sd, element)

    def year_stream(self, era: str, option: str) -> YearStartStream:
        """The stream that counts ``era``'s years under ``option`` (the search).

        The same stream :meth:`day` counts the era leaf from; a hard error
        for an era the set does not report or an option the record lacks.
        """
        ef = self.eras.get(era)
        if ef is None:
            raise ProfileError(f"the {self.conventions.id} conventions report no era {era!r}")
        starts = ef.era.year_starts or {}
        if option not in starts:
            raise ProfileError(f"era {era} has no year-start option {option!r} ({sorted(starts)})")
        return self._stream(starts[option].sun)

    def _neighbour(self, jdn: JDN) -> SourceDay | None:
        if jdn.days_since(self.source.runs_from) < 0:
            return None
        return self.source.day(jdn)

    # --- names ----------------------------------------------------------------------

    def _name(self, cls: str, index: int, flags: set[str]) -> dict[str, Any] | str:
        profile = self.conventions.profile
        if profile is None:
            return NOT_IN_PRESET
        n = profile.name(cls, index)
        if not self.scripts:
            return n.id
        forms: dict[str, Any] = {}
        for s in self.scripts:
            have = n.forms.get(s, ())
            forms[s] = list(have) if have else NOT_IN_PRESET
            if have and s in profile.name_flags:
                flags.add(profile.name_flags[s])
        return {"id": n.id, "forms": forms}

    def _element_name(self, element: str, index: int, flags: set[str]) -> Any:
        if element == "tithi":
            name_index, paksa = tithi_name_index(index)
            return {"paksa": paksa, "name": self._name("tithi", name_index, flags)}
        if element == "karana":
            profile = self.conventions.profile
            if profile is None:
                return NOT_IN_PRESET
            if profile.karana_flag is not None:
                flags.add(profile.karana_flag)
            return self._name("karana", profile.karana_cycle[index - 1], flags)
        return self._name(element, index, flags)

    # --- the day --------------------------------------------------------------------

    def day(self, jdn: JDN) -> dict[str, Any]:
        """The calendar leaves of civil day ``jdn`` (module docstring)."""
        sd = self.source.day(jdn)
        flags: set[str] = set(sd.flags)
        prev, nxt = self._neighbour(jdn.plus_days(-1)), self._neighbour(jdn.plus_days(1))
        out: dict[str, Any] = {
            "method_id": self.binding.method_id,
            "conventions": self.conventions.id,
            "dates": {
                "jdn": jdn.value,
                "julian": _ymd(julian_from_jdn(jdn)),
                "gregorian": _ymd(gregorian_from_jdn(jdn)),
            },
            "weekday": {
                "index": _vara_index(sd),
                "name": self._name("vara", _vara_index(sd), flags),
            },
        }
        month = self.months.month_of(jdn) if self.months is not None else None
        if month is not None:
            flags.update(self.month_rule_flags())
        out["eras"] = self._eras(jdn, sd, month, flags)
        out["sunrise"] = self._instant(sd.sunrise_after_midnight, sd.standard)
        sunset = (
            None
            if sd.sunset is None or sd.sunrise_after_midnight is None
            else sd.sunrise_after_midnight + sd.sunset
        )
        out["sunset"] = self._instant(sunset, sd.standard)
        out["day_length_nadika"] = _q(sd.length)
        for e in OCCURRENCE_ELEMENTS:
            assigned = self._assigned(sd, e)
            rows = []
            first = True
            for o in day_occurrences(sd, e):
                rows.append(
                    {
                        "index": o.index,
                        "name": self._element_name(e, o.index, flags),
                        "assigned": first and o.index == assigned,
                        "start": None if o.start is None else _q(o.start),
                        "end": None if o.end is None else _q(o.end),
                        "ends_nadika_after_sunrise": _q(o.ends_after_start),
                    }
                )
                if o.index == assigned:
                    first = False
            out[e] = rows
            count = elements.ELEMENTS[e].count
            p = None if prev is None else self._assigned(prev, e)
            f = None if nxt is None else self._assigned(nxt, e)
            flags.update(ksaya_vrddhi(e, count, p, assigned, f))
        out["masa"] = self._masa(sd, month, flags)
        out["sankranti"] = self.sankranti(jdn)
        out["flags"] = sorted(flags)
        return out

    def _instant(self, after_midnight: Nadika | None, standard: str) -> Any:
        if after_midnight is None:
            return NOT_MODELLED
        if self.binding.clock:
            return {"local": _hms(after_midnight), "standard": standard}
        return {"nadika_after_local_midnight": _q(after_midnight), "standard": standard}

    def _eras(self, jdn: JDN, sd: SourceDay, month: Any, flags: set[str]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for spec in self.conventions.eras:
            ef = self.eras[spec.era]
            era = ef.era
            option = self.options[spec.era]
            assert era.year_starts is not None
            ys = era.year_starts[option]
            y = era_year(era, jdn, option, self._stream(ys.sun))
            if isinstance(y, NotInRange):
                out[spec.era] = NOT_IN_RANGE
                continue
            leaf: dict[str, Any] = {"year": y.year, "year_start": option, "sun": ys.sun.value}
            if spec.era == self.time_base_era:
                if self.binding.day_count == AHARGANA and sd.ahargana is not None:
                    leaf[AHARGANA] = sd.ahargana
                elif self.binding.day_count == JDN_DIFFERENCE and era.epoch is not None:
                    leaf[JDN_DIFFERENCE] = jdn.days_since(era.epoch)
            if era.month_naming == RASI_NAMING and month is not None:
                leaf["masa"] = self._name("masa", month.rasi, flags)
                leaf["masa_index"] = month.rasi
                leaf["day"] = month.day_of_month
            out[spec.era] = leaf
        return out

    def _masa(self, sd: SourceDay, month: Any, flags: set[str]) -> dict[str, Any]:
        if month is None:
            return {
                "rasi_index": sd.labels[elements.RASI.id],
                "name": NOT_IN_PRESET,
                "day": NOT_IN_PRESET,
            }
        return {
            "rasi_index": month.rasi,
            "name": self._name("masa", month.rasi, flags),
            "day": month.day_of_month,
        }

    def month_rule_flags(self) -> tuple[str, ...]:
        """The flag a record that uses the month rule carries (``provisional:<rule>``), if any."""
        if self.months is None or self.month_rule is None or self.month_rule.flag is None:
            return ()
        return (self.month_rule.flag,)

    def sankranti(self, jdn: JDN) -> Any:
        """The ``sankranti`` leaf of civil day ``jdn`` (the API's ``sankrantis``), or ``None``."""
        s = sankranti_in_day(self.source, jdn)
        if s is None:
            return None
        entering, t = s
        leaf: dict[str, Any] = {"rasi_index": entering, "instant": _q(t)}
        if self.months is None:
            leaf["assigned_day1"] = NOT_IN_PRESET
        else:
            m = self.months.month_of(jdn.plus_days(1))
            leaf["assigned_day1"] = m.first_day.value if m.rasi == entering else None
        return leaf
