"""Regional profiles: ``regions/<region>/``.

A profile is three files beside its place table: ``names.yaml`` (the name
tables, ``names_file`` of the records schema), ``conventions.yaml`` (the
civil day, the assignment rule, the month rule, the eras it reports and
their year-start options, the ending encoding; ``conventions_file``) and
``places.yaml`` (``jyotirganita/regions/places.py``). Every part names
the datum that cites it; :func:`load_profile` checks that each named key
is a datum of the file (a gap where the part says so), that each name
class is complete and its ids unique, that the assignment and month rules
are registered (``calendar/assignment.py``, ``calendar/months.py``), and
that every era and year-start option exists in ``data/eras/``.

Nothing here knows Kerala: a second profile is a directory of the same
three files and, for an era of its own, an era record.

**Provisional parts**. The month rule carries
``provisional:regions.<region>.month_rule`` with its reason while its
statement has no second witness; a name table whose Indic forms await the
owner's sign-off carries ``provisional:regions.<region>.names.<script>``;
the karaṇa cycle (``names.yaml``'s ``karana_cycle``, a table datum) carries
``provisional:<its key>`` while that datum is at ``read``.
A record that uses the part carries the flag.

**The karaṇa cycle**. The table datum gives, for each
of the thirty tithis of the month, the karaṇa of its two halves: a cell
holding an integer names the movable karaṇa of that number (the profile's
karaṇa index of the same number), a cell holding a name names the karaṇa
whose Latin forms include it. :func:`load_profile` resolves the sixty
name indices from it and refuses a table of another shape, a number with
no karaṇa or a name that matches none or several.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from jyotirganita.calendar.elements import TITHI
from jyotirganita.data.datum import (
    CONVENTIONS_FILE,
    INDIC_SCRIPTS,
    NAMES_FILE,
    DatumError,
    Record,
)
from jyotirganita.data.eras import EraFile
from jyotirganita.data.yamlio import load_exact

__all__ = [
    "Ending",
    "EraSpec",
    "MonthRuleSpec",
    "Name",
    "Profile",
    "ProfileError",
    "load_profile",
    "profile_ids",
]

REGIONS_DIR = ("jyotirganita", "regions")


class ProfileError(ValueError):
    """A profile whose files do not resolve (a missing key, an unknown rule or era)."""


@dataclass(frozen=True, slots=True)
class Name:
    """One name: its class, index, canonical ASCII id and its printed forms by script."""

    cls: str
    index: int
    id: str
    forms: Mapping[str, tuple[str, ...]]
    keys: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class MonthRuleSpec:
    """The profile's month rule: the registered rule, its parameters, citation and flag.

    ``alternatives`` are the rules a run may select instead (the profile's
    ``month_rule.selectable``), each a
    spec of its own whose flag every record computed under it carries.
    """

    rule: str
    parameters: Mapping[str, Fraction]
    datum: str
    provisional: str | None
    flag: str | None
    alternatives: Mapping[str, MonthRuleSpec] = field(default_factory=dict)

    def select(self, rule: str | None) -> MonthRuleSpec:
        """The spec of ``rule``: the default when ``None``, a hard error for one not offered."""
        if rule is None or rule == self.rule:
            return self
        alt = self.alternatives.get(rule)
        if alt is None:
            raise ProfileError(
                f"month rule {rule!r} is not offered (default {self.rule}, selectable "
                f"{sorted(self.alternatives)})"
            )
        return alt


@dataclass(frozen=True, slots=True)
class EraSpec:
    """An era the profile reports, with its default and selectable year-start options."""

    era: str
    default_option: str
    selectable: tuple[str, ...]
    decision: str | None


@dataclass(frozen=True, slots=True)
class Ending:
    """The ending encoding the profile's almanacs print, with its citation."""

    unit: str
    direction: str
    reference: str
    datum: str


@dataclass(frozen=True, slots=True)
class Profile:
    """A regional profile resolved against its data."""

    region: str
    names: Mapping[tuple[str, int], Name]
    counts: Mapping[str, int]
    civil_day_start: str
    civil_day_datum: str
    assignment: str
    assignment_datum: str
    month_rule: MonthRuleSpec
    eras: tuple[EraSpec, ...]
    ending: Ending
    sunrise_event: str
    name_flags: Mapping[str, str]
    provisional: Mapping[str, str]
    paths: tuple[str, ...]
    karana_cycle: tuple[int, ...]
    karana_flag: str | None

    def name(self, cls: str, index: int) -> Name:
        """The name of class ``cls`` at ``index`` (a hard error for an unknown one)."""
        n = self.names.get((cls, index))
        if n is None:
            raise ProfileError(f"{self.region}: no {cls} name at index {index}")
        return n

    def era_option(self, era: str, option: str | None = None) -> str:
        """The year-start option of ``era``: ``option`` if offered, else the default."""
        spec = next((e for e in self.eras if e.era == era), None)
        if spec is None:
            raise ProfileError(f"{self.region} reports no era {era!r}")
        if option is None:
            return spec.default_option
        if option != spec.default_option and option not in spec.selectable:
            raise ProfileError(f"{self.region}: era {era} has no selectable option {option!r}")
        return option


def _dir(repo: Path, region: str) -> Path:
    return repo.joinpath(*REGIONS_DIR, region)


def profile_ids(repo: Path) -> list[str]:
    """The regions with a complete profile (names and conventions beside the place table)."""
    root = repo.joinpath(*REGIONS_DIR)
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and (p / NAMES_FILE).is_file() and (p / CONVENTIONS_FILE).is_file()
    )


def _datum(records: Mapping[str, Record], key: str, where: str, *, gap: bool = False) -> Record:
    rec = records.get(key)
    if rec is None:
        raise ProfileError(f"{where} names {key}, which is not a loaded datum")
    if (rec.kind == "gap") != gap:
        state = "a gap" if rec.kind == "gap" else "a datum"
        raise ProfileError(f"{where} names {key}, {state} where the part expects the other")
    return rec


def _names(
    doc: Mapping[str, Any], records: Mapping[str, Record], where: str
) -> tuple[dict[tuple[str, int], Name], dict[str, int], dict[str, str]]:
    counts = {c: int(v["count"]) for c, v in doc["classes"].items()}
    out: dict[tuple[str, int], Name] = {}
    seen: dict[str, set[str]] = {c: set() for c in counts}
    unsigned: set[str] = set()
    for n in doc["names"]:
        cls = n["class"]
        if cls not in counts:
            raise ProfileError(f"{where}: name {n['id']} of an undeclared class {cls}")
        if n["id"] in seen[cls]:
            raise ProfileError(f"{where}: {cls} id {n['id']} is not unique")
        seen[cls].add(n["id"])
        forms: dict[str, tuple[str, ...]] = {}
        keys: dict[str, tuple[str, ...]] = {}
        for script, ks in n["forms"].items():
            recs = [records.get(k) for k in ks]
            for k, r in zip(ks, recs, strict=True):
                if r is None:
                    raise ProfileError(f"{where}: {cls} {n['id']}: {k} is not a loaded datum")
            keys[script] = tuple(ks)
            forms[script] = tuple(str(r.raw["value"]) for r in recs if r and r.kind != "gap")
            for r in recs:
                if r and r.kind != "gap" and r.script in INDIC_SCRIPTS and not r.signed_off:
                    unsigned.add(r.script)
        if not forms.get("latin"):
            raise ProfileError(f"{where}: {cls} {n['id']} has no accepted Latin spelling")
        if (cls, n["index"]) in out:
            raise ProfileError(f"{where}: two {cls} names at index {n['index']}")
        out[(cls, n["index"])] = Name(cls, n["index"], n["id"], forms, keys)
    for cls, count in counts.items():
        # the indices, not only their number; the
        # tithi class names 1–15 and the new moon, TITHI.count (its index note)
        want = list(range(1, count + 1))
        if cls == TITHI.id:
            want = [*range(1, count), TITHI.count]
        have = sorted(i for c, i in out if c == cls)
        if have != want:
            raise ProfileError(
                f"{where}: class {cls} declares {count} names; its indices are not {want}"
            )
    region = doc["region"]
    flags = {s: f"provisional:regions.{region}.names.{s}" for s in sorted(unsigned)}
    return out, counts, flags


def _karana_cycle(
    doc: Mapping[str, Any],
    names: Mapping[tuple[str, int], Name],
    counts: Mapping[str, int],
    records: Mapping[str, Record],
    where: str,
) -> tuple[tuple[int, ...], str | None]:
    """The karaṇa name index of each karaṇa of the month, and the flag while unsettled."""
    if "karana" not in counts:
        return (), None
    key = doc.get("karana_cycle")
    if key is None:
        raise ProfileError(f"{where}: the profile names karaṇas and gives no karana_cycle")
    rec = _datum(records, key, f"{where}: karana_cycle")
    if rec.form != "table" or not isinstance(rec.value, tuple):
        raise ProfileError(f"{where}: karana_cycle {key} is not a table datum")
    count = counts["karana"]
    out: list[int] = []
    for serial, row in enumerate(rec.value, start=1):
        if len(row) != 3 or row[0] != serial:
            raise ProfileError(f"{where}: {key} row {serial} is not [serial, first, second]")
        for cell in row[1:]:
            if isinstance(cell, int) and not isinstance(cell, bool):
                if ("karana", cell) not in names:
                    raise ProfileError(f"{where}: {key} row {serial} names karaṇa {cell}")
                out.append(cell)
                continue
            hits = [
                i
                for i in range(1, count + 1)
                if str(cell) in names[("karana", i)].forms.get("latin", ())
            ]
            if len(hits) != 1:
                raise ProfileError(
                    f"{where}: {key} row {serial}: {len(hits)} karaṇa names match a cell"
                )
            out.append(hits[0])
    from jyotirganita.calendar.elements import KARANA

    if len(out) != KARANA.count:
        raise ProfileError(f"{where}: {key} gives {len(out)} karaṇas, not {KARANA.count}")
    if set(out) != set(range(1, count + 1)):
        raise ProfileError(f"{where}: {key} does not name every karaṇa of the profile")
    flag = f"provisional:{key}" if rec.status != "double_read" else None
    return tuple(out), flag


def load_profile(
    repo: Path, region: str, records: Mapping[str, Record], eras: Mapping[str, EraFile]
) -> Profile:
    """The profile of ``region``, resolved against ``records`` (the loaded data) and ``eras``."""
    from jyotirganita.calendar.assignment import ASSIGNMENT_RULES
    from jyotirganita.calendar.months import MONTH_RULES

    d = _dir(repo, region)
    names_path, conv_path = d / NAMES_FILE, d / CONVENTIONS_FILE
    for path in (names_path, conv_path):
        if not path.is_file():
            raise ProfileError(f"region {region!r} has no {path.name} ({path})")
    try:
        ndoc, cdoc = load_exact(names_path), load_exact(conv_path)
    except DatumError as e:  # pragma: no cover - the datum loader reports it first
        raise ProfileError(str(e)) from None
    rel_n = f"regions/{region}/{NAMES_FILE}"
    rel_c = f"regions/{region}/{CONVENTIONS_FILE}"
    names, counts, name_flags = _names(ndoc, records, rel_n)
    karana_cycle, karana_flag = _karana_cycle(ndoc, names, counts, records, rel_n)

    cd = cdoc["civil_day"]
    _datum(records, cd["datum"], f"{rel_c}: civil_day")
    for w in cd.get("witnesses", ()):
        _datum(records, w, f"{rel_c}: civil_day.witnesses")
    a = cdoc["assignment"]
    if a["default"] not in ASSIGNMENT_RULES:
        raise ProfileError(f"{rel_c}: assignment {a['default']} is not a registered rule")
    _datum(records, a["datum"], f"{rel_c}: assignment")
    for part in ("ksaya", "vrddhi"):
        _datum(records, cdoc["ksaya_vrddhi"][part], f"{rel_c}: ksaya_vrddhi.{part}")

    m = cdoc["month_rule"]
    rule = MONTH_RULES.get(m["rule"])
    if rule is None:
        raise ProfileError(f"{rel_c}: month rule {m['rule']} is not a registered rule")
    _datum(records, m["datum"], f"{rel_c}: month_rule")
    params: dict[str, Fraction] = {}
    for name in rule.parameters:
        if name not in m:
            raise ProfileError(f"{rel_c}: month rule {m['rule']} needs its parameter {name}")
        v = _datum(records, m[name], f"{rel_c}: month_rule.{name}").value
        if isinstance(v, bool) or not isinstance(v, int | Fraction):
            raise ProfileError(f"{rel_c}: month_rule.{name} ({m[name]}) is not a number datum")
        params[name] = Fraction(v)
    for g in m["searched"]:
        _datum(records, g, f"{rel_c}: month_rule.searched", gap=True)
    provisional: dict[str, str] = {}
    flag = None
    if "provisional" in m:
        flag = f"provisional:regions.{region}.month_rule"
        provisional[flag] = m["provisional"]
    alternatives: dict[str, MonthRuleSpec] = {}
    for s in m.get("selectable", ()):
        where = f"{rel_c}: month_rule.selectable.{s['rule']}"
        alt = MONTH_RULES.get(s["rule"])
        if alt is None or s["rule"] == m["rule"]:
            raise ProfileError(f"{where}: not a registered rule other than the default")
        if alt.parameters:
            raise ProfileError(f"{where}: a selectable rule with parameters is not supported")
        stated = records.get(s["datum"])
        if stated is None:
            raise ProfileError(f"{where} names {s['datum']}, which is not a loaded datum")
        if stated.kind == "gap" and "provisional" not in s:
            raise ProfileError(f"{where}: a rule whose statement is a gap ships provisional")
        alt_flag = None
        if "provisional" in s:
            alt_flag = f"provisional:{s['rule']}"
            provisional[alt_flag] = s["provisional"]
        alternatives[s["rule"]] = MonthRuleSpec(
            s["rule"], {}, s["datum"], s.get("provisional"), alt_flag
        )
    spec = MonthRuleSpec(m["rule"], params, m["datum"], m.get("provisional"), flag, alternatives)

    specs: list[EraSpec] = []
    for entry in cdoc["eras"]:
        where = f"{rel_c}: eras.{entry['era']}"
        ef = eras.get(entry["era"])
        if ef is None:
            raise ProfileError(f"{where}: no era record data/eras/{entry['era']}.yaml")
        options = ef.era.year_starts or {}
        ys = entry.get("year_start")
        if ys is None:
            if len(options) != 1:
                raise ProfileError(f"{where}: the era has {len(options)} year starts; name one")
            specs.append(EraSpec(entry["era"], next(iter(options)), (), None))
            continue
        chosen = (ys["default"], *ys["selectable"])
        for option in chosen:
            if option not in options:
                raise ProfileError(f"{where}: no year-start option {option!r} ({sorted(options)})")
            if option not in ys["witnesses"]:
                raise ProfileError(f"{where}: option {option!r} names no witness")
        for option, keys in ys["witnesses"].items():
            if option not in chosen:
                raise ProfileError(f"{where}: a witness for {option!r}, which is not offered")
            for k in keys:
                _datum(records, k, f"{where}.year_start.witnesses.{option}")
        specs.append(
            EraSpec(entry["era"], ys["default"], tuple(ys["selectable"]), ys.get("decision"))
        )

    en = cdoc["encodings"]["ending"]
    _datum(records, en["datum"], f"{rel_c}: encodings.ending")
    ending = Ending(en["unit"], en["direction"], en["reference"], en["datum"])
    sunrise_event = cdoc["sunrise_event"]
    if sunrise_event not in records:
        raise ProfileError(f"{rel_c}: sunrise_event names {sunrise_event}, not a loaded datum")
    if cdoc["time_standard"] not in records:
        raise ProfileError(f"{rel_c}: time_standard names {cdoc['time_standard']}")
    for script, f in name_flags.items():
        provisional[f] = f"the {script} names await the owner's sign-off"
    if karana_flag is not None:
        provisional[karana_flag] = "the karaṇa cycle is read once and awaits its second read"
    return Profile(
        region,
        names,
        counts,
        cd["start"],
        cd["datum"],
        a["default"],
        a["datum"],
        spec,
        tuple(specs),
        ending,
        sunrise_event,
        name_flags,
        provisional,
        (rel_n, rel_c),
        karana_cycle,
        karana_flag,
    )
