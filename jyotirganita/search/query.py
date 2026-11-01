"""The query: its schema, its vocabulary and every refusal before the scan.

A query is a YAML or JSON document (:func:`read_query`) validated against
``search/query.schema.json`` (:func:`check_shape`) and then compiled
against a :class:`~jyotirganita.search.config.SearchConfig` and its
reading profile (:func:`compile_query`). Compiling resolves every name to
its index through the profile's vocabulary, every element's match mode
(the constraint's own, else the profile's), every planet's place, every
era and year-start option, and checks the window and every constraint
against what the method serves. Each failure is a :class:`SearchError`
naming the field and the range or capability the method offers, raised
before any day is computed, in ``require`` and ``report`` mode alike. A query that compiles is
servable: an empty result is a finding.

**Values.** A name or an index, or a list of them meaning any of them
(an unreadable digit in a record). Indices are the fixed mathematics of
``calendar/elements.py``: a rāśi 1–12 (1 = Meṣa), a nakṣatra or yoga 1–27, a tithi
of the month 1–30 (or ``{paksha: sukla|krishna, n: 1–15}``, or ``{paksha,
name}``; kṛṣṇa 15 is the new moon, tithi 30), a karaṇa of the month 1–60
(a name means every karaṇa of the month the profile's karaṇa cycle names
so), a weekday 1–7 (1 = Sunday). ``era_year``, ``era_day`` and
``day_of_month`` take an integer, a list or ``{from, to}``. ``ayana`` is
``uttarayana`` (the Sun's sidereal rāśi from Makara through Mithuna) or
``dakshinayana`` (from Karka through Dhanu), reckoned from the method's
sidereal Makara and Karka saṅkrāntis (sewell_dikshit_1896 Art. 23).

**Mode.** ``require`` (filters) or ``report`` (evaluated and reported,
never filters); a constraint without ``mode`` is ``require``, and the
result states the mode used. ``near_miss: {max_misses: n}`` returns, as
a class of its own, days on which every ``require`` constraint but at
most *n* holds.

No ``math``, ``numpy`` or ``decimal`` import.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from jyotirganita.calendar import elements
from jyotirganita.core.eras import NotInRange, era_year
from jyotirganita.core.types import JDN
from jyotirganita.io.dates import DateSyntaxError, jdn_of, parse_json_date
from jyotirganita.io.record import serving
from jyotirganita.regions.base import ProfileError
from jyotirganita.search.config import SearchConfig
from jyotirganita.search.errors import SearchError
from jyotirganita.search.profiles import (
    MATCH_MODES,
    NAME_CLASS,
    OCCURRENCE,
    ProfileEntry,
    ReadingProfile,
)

__all__ = [
    "AYANA",
    "Constraint",
    "Query",
    "check_shape",
    "check_vocabulary",
    "compile_query",
    "read_query",
]

TITHIS_PER_PAKSA = 15
DAYS_PER_WEEK = 7
#: a solar month runs 29 to 32 civil days; structural: it decides only whether a query
#: is refused as malformed, never which days a query returns
MAX_DAY_OF_MONTH = 30 + 2
NADIKAS_PER_DAY = 60
#: the rāśis of the two ayanas, from the sidereal Makara (10) and Karka (4) saṅkrāntis
MAKARA, KARKA = 10, 4
SIGNS = elements.RASI.count
AYANA: Mapping[str, frozenset[int]] = {
    "uttarayana": frozenset((MAKARA - 1 + k) % SIGNS + 1 for k in range(SIGNS // 2)),
    "dakshinayana": frozenset((KARKA - 1 + k) % SIGNS + 1 for k in range(SIGNS // 2)),
}
#: the number of indices an element's values range over
INDEX_COUNT: Mapping[str, int] = {
    "masa": SIGNS,
    "sun_rasi": SIGNS,
    "moon_rasi": SIGNS,
    "planet_rasi": SIGNS,
    "sankranti_day": SIGNS,
    "nakshatra": elements.NAKSATRA.count,
    "planet_nakshatra": elements.NAKSATRA.count,
    "yoga": elements.YOGA.count,
    "tithi": elements.TITHI.count,
    "karana": elements.KARANA.count,
    "weekday": DAYS_PER_WEEK,
}
NODES = ("rahu", "ketu")
#: the elements whose names come from the vocabulary
NAMED = tuple(NAME_CLASS)
MONTH_ELEMENTS = ("masa", "day_of_month")


@cache
def _schema() -> Mapping[str, Any]:
    text = resources.files("jyotirganita.search").joinpath("query.schema.json").read_text("utf-8")
    doc: Mapping[str, Any] = json.loads(text)
    return doc


@dataclass(frozen=True, slots=True)
class Constraint:
    """One compiled constraint (module docstring); ``given`` is the constraint as written."""

    index: int
    element: str
    mode: str
    given: Mapping[str, Any]
    match: str | None = None
    values: frozenset[int] = frozenset()
    body: str | None = None
    position: bool | str | None = None
    retrograde: bool | None = None
    era: str | None = None
    year_start: str | None = None
    ranges: tuple[tuple[int, int], ...] = ()
    nadika: Fraction | None = None
    of: tuple[int, ...] = ()
    eclipse: str | None = None
    visible: bool | None = None
    entry: ProfileEntry | None = None

    @property
    def field(self) -> str:
        return f"constraints[{self.index}]"

    @property
    def require(self) -> bool:
        return self.mode == "require"

    def holds_number(self, n: int) -> bool:
        return any(lo <= n <= hi for lo, hi in self.ranges)

    def flags(self) -> tuple[str, ...]:
        """The flags every candidate evaluated under this constraint carries."""
        if self.entry is not None and self.entry.provisional is not None:
            return (self.entry.flag,)
        return ()


@dataclass(frozen=True, slots=True)
class Query:
    """A compiled query: profile, window, constraints and the near-miss allowance."""

    profile: ReadingProfile
    first: JDN
    last: JDN
    constraints: tuple[Constraint, ...]
    near_miss: bool
    max_misses: int
    sha256: str
    doc: Mapping[str, Any]

    @property
    def required(self) -> tuple[Constraint, ...]:
        return tuple(c for c in self.constraints if c.require)


def read_query(path: Path) -> Any:
    """A query document from a ``.yaml``/``.yml`` or ``.json`` file."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        try:
            return plain(json.loads(text, object_pairs_hook=_unique_pairs))
        except json.JSONDecodeError as e:
            raise SearchError(str(path), f"not JSON: {e}") from None
        except _DuplicateKey as e:
            raise SearchError(str(path), f"not JSON: the key {e} appears twice") from None
    if path.suffix in (".yaml", ".yml"):
        try:
            return plain(yaml.load(text, Loader=_UniqueKeyLoader))
        except _DuplicateKey as e:
            raise SearchError(str(path), f"not YAML: the key {e} appears twice") from None
        except yaml.YAMLError as e:
            raise SearchError(str(path), f"not YAML: {e}") from None
    raise SearchError(str(path), "a query file is .yaml, .yml or .json")


class _DuplicateKey(Exception):
    """A key given twice in one mapping (item 10: the last won)."""


def _unique_pairs(pairs: list[tuple[Any, Any]]) -> dict[Any, Any]:
    out: dict[Any, Any] = {}
    for k, v in pairs:
        if k in out:
            raise _DuplicateKey(repr(k))
        out[k] = v
    return out


class _UniqueKeyLoader(yaml.SafeLoader):
    """The safe loader, refusing a key given twice in one mapping."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        keys = [self.construct_object(k, deep=deep) for k, _ in node.value]
        for i, k in enumerate(keys):
            if k in keys[:i]:
                raise _DuplicateKey(repr(k))
        return super().construct_mapping(node, deep=deep)


def plain(doc: Any) -> Any:
    """A copy of ``doc`` in which an integral float is an int.

    JSON Schema counts 1.0 an integer, which the compiler's ``int`` tests did
    not; the copy also keeps a compiled
    query from sharing the caller's mappings (item 9).
    """
    if isinstance(doc, Mapping):
        return {k: plain(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [plain(v) for v in doc]
    if isinstance(doc, float) and doc.is_integer():
        return int(doc)
    return doc


def _where(path: Sequence[Any]) -> str:
    out = ""
    for p in path:
        out += f"[{p}]" if isinstance(p, int) else (f".{p}" if out else str(p))
    return out or "query"


def check_shape(doc: Any) -> None:
    """Validate ``doc`` against ``search/query.schema.json``; the first error names its field."""
    validator = jsonschema.Draft202012Validator(_schema())
    errors = list(validator.iter_errors(doc))
    if not errors:
        return
    e = jsonschema.exceptions.best_match(errors) or errors[0]
    deepest = e
    while deepest.context:
        deepest = jsonschema.exceptions.best_match(deepest.context) or deepest.context[0]
    path = list(deepest.absolute_path)
    if deepest.validator == "required" and isinstance(deepest.instance, Mapping):
        path += [k for k in deepest.validator_value if k not in deepest.instance][:1]
    raise SearchError(_where(path), deepest.message)


def canonical_sha256(doc: Any) -> str:
    """SHA-256 of the query's canonical JSON form (keys sorted, ``(',', ':')``, ASCII)."""
    text = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


# --- values ---------------------------------------------------------------------------


def _listed(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else [value]


def _index(cls: str, element: str, v: Any, profile: ReadingProfile, where: str) -> int:
    count = INDEX_COUNT[element]
    if isinstance(v, bool):
        raise SearchError(where, f"{v!r} is not a name or an index")
    if isinstance(v, int):
        if not 1 <= v <= count:
            raise SearchError(where, f"index {v} is out of range: a {element} index is 1–{count}")
        return v
    return profile.vocabulary.index(cls, str(v), where)


def _tithi(v: Any, profile: ReadingProfile, where: str) -> int:
    count = elements.TITHI.count
    if isinstance(v, int) and not isinstance(v, bool):
        if not 1 <= v <= count:
            raise SearchError(
                where, f"index {v} is out of range: a tithi of the month is 1–{count}"
            )
        return v
    paksha = v["paksha"]
    if "n" in v:
        n = v["n"]
        if not 1 <= n <= TITHIS_PER_PAKSA:
            raise SearchError(
                f"{where}.n", f"{n} is out of range: a tithi of a pakṣa is 1–{TITHIS_PER_PAKSA}"
            )
        return int(n) if paksha == "sukla" else TITHIS_PER_PAKSA + int(n)
    name = profile.vocabulary.index("tithi", v["name"], f"{where}.name")
    if name == count:  # the new moon's own name
        if paksha != "krishna":
            raise SearchError(f"{where}.paksha", "the new-moon tithi is of the kṛṣṇa pakṣa")
        return count
    if name == TITHIS_PER_PAKSA and paksha != "sukla":
        raise SearchError(f"{where}.paksha", "the full-moon tithi is of the śukla pakṣa")
    return name if paksha == "sukla" else TITHIS_PER_PAKSA + name


def _karana(v: Any, profile: ReadingProfile, where: str) -> frozenset[int]:
    if isinstance(v, int) and not isinstance(v, bool):
        return frozenset({_index("karana", "karana", v, profile, where)})
    name = profile.vocabulary.index("karana", str(v), where)
    cycle = profile.vocabulary.karana_cycle
    return frozenset(i + 1 for i, n in enumerate(cycle) if n == name)


def _values(element: str, value: Any, profile: ReadingProfile, where: str) -> frozenset[int]:
    out: set[int] = set()
    for i, v in enumerate(_listed(value)):
        w = f"{where}[{i}]" if isinstance(value, list) else where
        if element == "tithi":
            out.add(_tithi(v, profile, w))
        elif element == "karana":
            out |= _karana(v, profile, w)
        else:
            out.add(_index(NAME_CLASS[element], element, v, profile, w))
    return frozenset(out)


def _ranges(value: Any, where: str) -> tuple[tuple[int, int], ...]:
    if isinstance(value, Mapping):
        if value["to"] < value["from"]:
            raise SearchError(where, f"the range ends ({value['to']}) before it starts")
        return ((value["from"], value["to"]),)
    return tuple((v, v) for v in _listed(value))


def _nadika(v: Any, where: str) -> Fraction:
    n = Fraction(v) if isinstance(v, int) else Fraction(str(v))
    if not n < NADIKAS_PER_DAY:
        raise SearchError(
            where, f"{v}: a time is fewer than {NADIKAS_PER_DAY} nāḍikās after sunrise"
        )
    return n


# --- the window -----------------------------------------------------------------------


def _date(doc: Any, where: str) -> JDN:
    try:
        return jdn_of(parse_json_date(doc))
    except DateSyntaxError as e:
        raise SearchError(where, str(e)) from None


def _window(doc: Mapping[str, Any], config: SearchConfig) -> tuple[JDN, JDN]:
    first = _date(doc["from"], "window.from")
    last = _date(doc["to"], "window.to")
    if last.days_since(first) < 0:
        raise SearchError(
            "window.to", f"JDN {last.value} is before window.from (JDN {first.value})"
        )
    rf = config.runs_from
    if first.days_since(rf) < 0:
        raise SearchError(
            "window.from",
            f"JDN {first.value} is before runs_from (JDN {rf.value}) of {config.method_id}: the "
            "method's own count does not exist before it",
        )
    if config.runs_to is not None:
        if config.runs_to.days_since(last) < 0:
            _low, high = config.engine.bounding_components()
            raise SearchError(
                "window.to",
                f"JDN {last.value} is after the last day the run serves (JDN "
                f"{config.runs_to.value}, bounded by {high}; {config.engine.range_text()})",
            )
        if first.days_since(config.runs_from) < 0:  # pragma: no cover - refused above
            raise SearchError("window.from", "before the run's range")
    # the first days of a modern run lie before its first month or era-year start and have
    # no record; the days a run cannot serve come first, so the window's first day decides
    # (item 3: the search failed part-way with MonthNotFound)
    with serving(first, "window.from"):
        config.calendar.day(first)
    return first, last


# --- constraints ----------------------------------------------------------------------


def _match(c: Mapping[str, Any], entry: ProfileEntry | None, where: str) -> str:
    element = c["element"]
    match = c.get("match")
    if match is None:
        if entry is None or entry.match is None:
            raise SearchError(f"{where}.match", f"the reading profile gives {element} no match")
        match = entry.match
    if match == "at_time" and "nadika" not in c:
        raise SearchError(f"{where}.nadika", "match at_time names the nāḍikā after sunrise")
    if match != "at_time" and "nadika" in c:
        raise SearchError(f"{where}.nadika", "a time belongs to match at_time")
    return str(match)


def _era_years(
    config: SearchConfig, era: str, option: str, window: tuple[JDN, JDN]
) -> tuple[int, int | None] | None:
    """The years of ``era`` under ``option`` a day of the window can carry.

    The window lies within the run's range (:func:`_window`), so its ends
    bound the years on both sides: a year no day of the window carries is
    refused, also where the run's and the era's ranges are open.
    """
    ef = config.calendar.eras[era]
    e = ef.era
    starts = e.year_starts or {}
    first, last = window
    lo = max((e.range.from_jdn, first, starts[option].epoch), key=_v)
    stream = config.calendar.year_stream(era, option)
    try:
        y_lo = era_year(e, lo, option, stream)
    except ValueError as err:
        # the stream cannot count so near the run's first day; the staged search reads
        # the year on the window's first day, so the window is refused here (tolerated
        # here, it would fail part-way through the search)
        raise SearchError(
            "window.from",
            f"JDN {lo.value}: the year of era {era} under {option} is not counted this near "
            f"the run's first day ({err}); start the window later",
        ) from None
    hi_day = last if e.range.to_jdn is None else min(e.range.to_jdn, last, key=_v)
    try:
        y_hi = era_year(e, hi_day, option, stream)
    except ValueError:
        y_hi = None
    if isinstance(y_lo, NotInRange):
        return None
    hi = None if y_hi is None or isinstance(y_hi, NotInRange) else y_hi.year
    return y_lo.year, hi


def _v(d: JDN) -> int:
    return d.value


def _check_numbers(c: Constraint, lo: int | None, hi: int | None, what: str, where: str) -> None:
    for a, b in c.ranges:
        if (lo is not None and b < lo) or (hi is not None and a > hi):
            span = f"{lo if lo is not None else '…'}–{hi if hi is not None else '…'}"
            raise SearchError(where, f"{a if a == b else f'{a}–{b}'} is outside {what} ({span})")


def _era_year(
    c: Mapping[str, Any],
    config: SearchConfig,
    base: Constraint,
    where: str,
    window: tuple[JDN, JDN],
) -> Constraint:
    era = c["era"]
    eras = [e.era for e in config.conventions.eras]
    if era not in eras:
        raise SearchError(
            f"{where}.era", f"the {config.conventions.id} conventions carry no era {era!r} ({eras})"
        )
    record = config.calendar.eras[era].era
    options = sorted(record.year_starts or {})
    option = c.get("year_start", config.calendar.options[era])
    if option not in options:
        raise SearchError(
            f"{where}.year_start", f"era {era} defines no year-start option {option!r} ({options})"
        )
    try:
        # the convention set's offer, as --set and Calendar.era_option enforce it
        config.conventions.era_option(era, option)
        config.calendar.year_stream(era, option)
    except ProfileError as e:
        raise SearchError(f"{where}.year_start", str(e)) from None
    out = _replace(base, era=era, year_start=option, ranges=_ranges(c["value"], f"{where}.value"))
    years = _era_years(config, era, option, window)
    if years is not None:
        _check_numbers(
            out, years[0], years[1], f"the years of era {era} the window spans", f"{where}.value"
        )
    return out


def _era_day(
    c: Mapping[str, Any], config: SearchConfig, base: Constraint, where: str
) -> Constraint:
    era = c["era"]
    own = config.calendar.time_base_era
    if era != own:
        raise SearchError(
            f"{where}.era",
            f"era_day is matched against the day count {config.method_id} keeps, from era {own} "
            f"; {era!r} is not it",
        )
    out = _replace(base, era=era, ranges=_ranges(c["value"], f"{where}.value"))
    record = config.calendar.eras[era].era
    lo_day = max(record.range.from_jdn, config.runs_from, key=_v)
    count_lo = _day_count(config, lo_day)
    hi_day = record.range.to_jdn
    if config.runs_to is not None:
        hi_day = config.runs_to if hi_day is None else min(hi_day, config.runs_to, key=_v)
    count_hi = None if hi_day is None else count_lo + hi_day.days_since(lo_day)
    _check_numbers(
        out, count_lo, count_hi, f"the days of era {era} the run counts", f"{where}.value"
    )
    return out


def _day_count(config: SearchConfig, day: JDN) -> int:
    """The run's own day count on ``day``: the ahargaṇa, or the JDN difference (modern)."""
    leaf = config.calendar.binding.day_count
    if leaf == "ahargana":
        count = config.calendar.source.day(day).ahargana
        assert count is not None
        return count
    epoch = config.calendar.eras[config.calendar.time_base_era].era.epoch
    assert epoch is not None
    return day.days_since(epoch)


def _replace(c: Constraint, **kw: Any) -> Constraint:
    fields = {f: getattr(c, f) for f in c.__dataclass_fields__}
    fields.update(kw)
    return Constraint(**fields)


def _planet(c: Mapping[str, Any], config: SearchConfig, base: Constraint, where: str) -> Constraint:
    body = c["body"]
    caps = config.engine.capabilities
    if body in NODES:
        if not caps.node:
            raise SearchError(f"{where}.body", f"{config.method_id} serves no node")
    elif body not in caps.bodies:
        raise SearchError(
            f"{where}.body",
            f"{config.method_id} serves no body {body!r} (serves {sorted(caps.bodies)})",
        )
    entry = base.entry
    position = c.get("position", entry.position_for(body) if entry is not None else None)
    if position not in (True, "mean"):
        raise SearchError(f"{where}.position", "true or mean")
    if position == "mean":
        if config.kind != "siddhantic":
            raise SearchError(
                f"{where}.position",
                f"position: mean is not served under {config.method_id}: the modern engine "
                "computes no mean longitude (state position: true)",
            )
        if body in NODES:
            raise SearchError(f"{where}.position", "the node has one place: position: true")
    return _replace(base, body=body, position=position, retrograde=c.get("retrograde"))


def _occurrence_refs(
    c: Mapping[str, Any], seen: Mapping[str, list[int]], where: str
) -> tuple[int, ...]:
    out: list[int] = []
    for el in c["of"]:
        idx = seen.get(el, [])
        if len(idx) != 1:
            raise SearchError(
                f"{where}.of",
                f"{el}: names the element of exactly one {el} constraint of the query "
                f"(found {len(idx)})",
            )
        out.append(idx[0])
    return tuple(out)


def _day_of_month(value: Any, where: str) -> tuple[tuple[int, int], ...]:
    r = _ranges(value, where)
    for a, b in r:
        if a < 1 or b > MAX_DAY_OF_MONTH:
            raise SearchError(
                where,
                f"{a if a == b else f'{a}–{b}'} is out of range: a day of a solar month "
                f"is 1–{MAX_DAY_OF_MONTH}",
            )
    return r


def check_vocabulary(doc: Any, profile: ReadingProfile) -> None:
    """The checks the reading profile settles alone, before any run is opened.

    ``doc`` has passed :func:`check_shape`. Every name and index, every
    match mode and time, and every day of a month are checked as
    :func:`compile_query` checks them; what needs the run (the window, an
    era, a body, a month rule) waits for it. The CLI calls this before
    opening the configuration, so that a malformed query is refused
    without loading a kernel.
    """
    for i, c in enumerate(doc["constraints"]):
        where = f"constraints[{i}]"
        element = c["element"]
        if element in MATCH_MODES:
            _match(c, profile.entry(element), where)
        if "nadika" in c:  # an at_time constraint's too
            _nadika(c["nadika"], f"{where}.nadika")
        if element == "day_of_month":
            _day_of_month(c["value"], f"{where}.value")
        elif element in NAMED:
            _values(element, c["value"], profile, f"{where}.value")


def compile_query(doc: Any, config: SearchConfig) -> Query:
    """Check ``doc`` and compile it against ``config`` (module docstring)."""
    doc = plain(doc)
    check_shape(doc)
    profile: ReadingProfile = config.reading_profile(doc["reading_profile"])
    first, last = _window(doc["window"], config)
    raw: list[Mapping[str, Any]] = doc["constraints"]
    seen: dict[str, list[int]] = {}
    for i, c in enumerate(raw):
        if c["element"] in OCCURRENCE:
            seen.setdefault(c["element"], []).append(i)
    out: list[Constraint] = []
    for i, c in enumerate(raw):
        where = f"constraints[{i}]"
        element = c["element"]
        base = Constraint(i, element, c.get("mode", "require"), c, entry=profile.entry(element))
        if element in MATCH_MODES:
            base = _replace(base, match=_match(c, base.entry, where))
            if "nadika" in c:
                base = _replace(base, nadika=_nadika(c["nadika"], f"{where}.nadika"))
        if element in MONTH_ELEMENTS and config.calendar.months is None:
            raise SearchError(
                f"{where}.element",
                f"{element} needs a month rule; the {config.conventions.id} conventions of "
                f"{config.preset.id} have none (sun_rasi gives the Sun's sidereal rāśi)",
            )
        if element == "era_year":
            out.append(_era_year(c, config, base, where, (first, last)))
        elif element == "era_day":
            out.append(_era_day(c, config, base, where))
        elif element == "day_of_month":
            out.append(_replace(base, ranges=_day_of_month(c["value"], f"{where}.value")))
        elif element == "ayana":
            out.append(_replace(base, values=AYANA[c["value"]]))
        elif element in ("planet_rasi", "planet_nakshatra"):
            pc = _replace(base, values=_values(element, c["value"], profile, f"{where}.value"))
            out.append(_planet(c, config, pc, where))
        elif element in NAMED:
            out.append(
                _replace(base, values=_values(element, c["value"], profile, f"{where}.value"))
            )
        elif element == "eclipse":
            if config.kind != "modern":
                reason = config.engine.capabilities.not_modelled.get("eclipses", "not modelled")
                raise SearchError(
                    f"{where}.element",
                    f"an eclipse is not served under {config.method_id} ({reason}); the modern "
                    "engine serves it, provisionally",
                )
            out.append(_replace(base, eclipse=c["value"], visible=c.get("visible_at_observer")))
        elif element == "overlap":
            out.append(_replace(base, of=_occurrence_refs(c, seen, where)))
        elif element == "at_time":
            out.append(
                _replace(
                    base,
                    of=_occurrence_refs(c, seen, where),
                    nadika=_nadika(c["nadika"], f"{where}.nadika"),
                )
            )
        else:  # pragma: no cover - the schema's enumeration
            raise SearchError(f"{where}.element", f"{element!r}")
    required = sum(1 for c in out if c.require)
    near = doc.get("near_miss")
    max_misses = 0
    if near is not None:
        max_misses = near["max_misses"]
        if max_misses > required:
            raise SearchError(
                "near_miss.max_misses",
                f"{max_misses} exceeds the {required} require constraint(s) of the query",
            )
    return Query(
        profile,
        first,
        last,
        tuple(out),
        near is not None,
        max_misses,
        canonical_sha256(doc),
        doc,
    )
