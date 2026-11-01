"""Reading profiles and the name vocabulary.

A **reading profile** (``search/reading_profiles/<id>.yaml``) supplies the
match mode of every element that needs one and does not state its own:
the occurrence elements (``tithi``, ``nakshatra``, ``yoga``, ``karana``:
``assigned``, ``any_occurrence`` or ``at_time``) and the position
elements (``planet_rasi``, ``planet_nakshatra``, ``moon_rasi``,
``sun_rasi``, ``ayana``: ``at_sunrise`` or ``any_time_in_day``), and for
the planet elements the default place (``position: true`` or ``mean``,
with ``position_by_body`` for a body read otherwise). Every entry cites
the statements it encodes by datum key: a statement of
``jyotirganita/data/search/reading_rules.yaml`` or of the names region's
``conventions.yaml`` (where the profile keys the same rule), each a loaded datum
that is not a gap. An entry for which no printed rule was found carries
``provisional: <reason>`` and ``searched: [<gap keys>]``, each a gap
record; every candidate evaluated under it carries
``provisional:search.reading_profiles.<profile>.<element>``. An entry may
name a ``threshold`` datum (a number, with ``threshold_unit``) under which
a matched constraint's margin raises ``boundary_sensitive``; without a
keyed threshold no entry states one and the flag is never emitted.

The **vocabulary** is generated from the profile's ``names`` region
(``regions/<region>/names.yaml``) when the profile loads: for each name
class its canonical ids and its listed Latin spellings, compared
case-insensitively; no spelling lives in code. The rāśi elements
(``masa``, ``sun_rasi``, ``moon_rasi``, ``planet_rasi``,
``sankranti_day``) take the ``masa`` class, whose index is the rāśi of the
solar month; ``weekday`` takes ``vara``; ``planet_nakshatra`` takes
``nakshatra``. A name that is neither an id nor a listed spelling is a
hard error naming the nearest ids by edit distance. The indices are the
fixed mathematics of ``calendar/elements.py``, so a text preset (``text_only``
conventions, no name table of its own) resolves names through the
profile's region too.

No ``math``, ``numpy`` or ``decimal`` import.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jyotirganita.data.datum import Records
from jyotirganita.data.eras import EraFile
from jyotirganita.data.yamlio import load_exact
from jyotirganita.regions.base import Profile, ProfileError, load_profile
from jyotirganita.search.errors import SearchError

__all__ = [
    "MATCH_MODES",
    "OCCURRENCE",
    "POSITION",
    "PROFILES_DIR",
    "ProfileEntry",
    "ReadingProfile",
    "Vocabulary",
    "load_reading_profile",
    "profile_ids",
]

PROFILES_DIR = ("jyotirganita", "search", "reading_profiles")
#: the occurrence elements and their match modes
OCCURRENCE = ("tithi", "nakshatra", "yoga", "karana")
OCCURRENCE_MODES = ("assigned", "any_occurrence", "at_time")
#: the position elements and their match modes
POSITION = ("planet_rasi", "planet_nakshatra", "moon_rasi", "sun_rasi", "ayana")
POSITION_MODES = ("at_sunrise", "any_time_in_day")
MATCH_MODES: Mapping[str, tuple[str, ...]] = {
    **dict.fromkeys(OCCURRENCE, OCCURRENCE_MODES),
    **dict.fromkeys(POSITION, POSITION_MODES),
}
#: elements a profile may cite without a match mode
CITED_ONLY = ("eclipse",)
PLANET_ELEMENTS = ("planet_rasi", "planet_nakshatra")
PLANET_BODIES = ("mercury", "venus", "mars", "jupiter", "saturn", "rahu", "ketu")
POSITIONS = (True, "mean")


def _position(p: Any) -> bool:
    """``True`` or ``"mean"``: by identity, so that 1 does not pass as ``True``."""
    return p is True or (isinstance(p, str) and p in POSITIONS)


THRESHOLD_UNITS = ("nadika", "degree", "day")
CITATION_FILE = "jyotirganita/data/search/reading_rules.yaml"
ENTRY_FIELDS = (
    "element",
    "match",
    "position",
    "position_by_body",
    "cites",
    "provisional",
    "searched",
    "threshold",
    "threshold_unit",
    "note",
)
PROFILE_FIELDS = ("profile", "names", "description", "entries")
#: the vocabulary class each element's names come from
NAME_CLASS: Mapping[str, str] = {
    "masa": "masa",
    "sun_rasi": "masa",
    "moon_rasi": "masa",
    "planet_rasi": "masa",
    "sankranti_day": "masa",
    "nakshatra": "nakshatra",
    "planet_nakshatra": "nakshatra",
    "yoga": "yoga",
    "karana": "karana",
    "tithi": "tithi",
    "weekday": "vara",
}
#: how many nearest ids a miss names
NEAREST = 3


@dataclass(frozen=True, slots=True)
class ProfileEntry:
    """One element's reading: its match mode, default place, citations and provisional state."""

    element: str
    match: str | None
    position: bool | str | None
    position_by_body: Mapping[str, bool | str]
    cites: tuple[str, ...]
    provisional: str | None
    searched: tuple[str, ...]
    threshold: str | None
    threshold_unit: str | None
    flag: str

    def position_for(self, body: str) -> bool | str | None:
        """The default place of ``body`` under this entry."""
        return self.position_by_body.get(body, self.position)


def _distance(a: str, b: str) -> int:
    """The plain edit distance (insertions, deletions, substitutions) between two strings."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class Vocabulary:
    """The names of one region's ``names.yaml``: ids and Latin spellings per class."""

    def __init__(self, profile: Profile) -> None:
        self.region = profile.region
        self.counts = dict(profile.counts)
        self.karana_cycle = profile.karana_cycle
        self.ids: dict[str, dict[int, str]] = {}
        self._lookup: dict[str, dict[str, int]] = {}
        for (cls, index), name in sorted(profile.names.items()):
            self.ids.setdefault(cls, {})[index] = name.id
            table = self._lookup.setdefault(cls, {})
            for spelling in (name.id, *name.forms.get("latin", ())):
                k = spelling.casefold()
                if table.get(k, index) != index:
                    raise ProfileError(
                        f"{profile.region}: the {cls} spelling {spelling!r} names two indices"
                    )
                table[k] = index

    def classes(self) -> tuple[str, ...]:
        return tuple(sorted(self._lookup))

    def spellings(self, cls: str) -> Mapping[str, int]:
        """Every accepted spelling of ``cls`` (case-folded) with its index."""
        return self._lookup[cls]

    def index(self, cls: str, name: str, field: str) -> int:
        """The index of ``name`` in class ``cls``; a hard error naming the nearest ids on a miss."""
        hit = self._lookup[cls].get(name.casefold())
        if hit is not None:
            return hit
        ids = sorted(self.ids[cls].values())
        near = sorted(ids, key=lambda i: (_distance(name.casefold(), i), i))[:NEAREST]
        raise SearchError(
            field,
            f"{name!r} is neither an id nor a listed Latin spelling of a {cls} name in "
            f"regions/{self.region}/names.yaml; nearest ids: {', '.join(near)}",
        )

    def name_id(self, cls: str, index: int) -> str:
        return self.ids[cls][index]


@dataclass(frozen=True, slots=True)
class ReadingProfile:
    """A reading profile resolved against the data: its entries by element and its vocabulary."""

    id: str
    names: str
    description: str
    entries: Mapping[str, ProfileEntry]
    vocabulary: Vocabulary
    path: str

    def entry(self, element: str) -> ProfileEntry | None:
        return self.entries.get(element)


def profile_ids(repo: Path) -> list[str]:
    """The reading profiles that ship."""
    return sorted(p.stem for p in repo.joinpath(*PROFILES_DIR).glob("*.yaml"))


def _cited(records: Records, key: Any, where: str, allowed: tuple[str, ...]) -> str:
    rec = records.data.get(str(key))
    if rec is None:
        raise SearchError(where, f"{key} is not a loaded datum")
    if rec.kind == "gap":
        raise SearchError(where, f"{key} is a gap; a citation names a keyed statement")
    if rec.path not in allowed:
        raise SearchError(where, f"{key} is in {rec.path}, not in {' or '.join(allowed)}")
    return str(key)


def _gap(records: Records, key: Any, where: str) -> str:
    rec = records.data.get(str(key))
    if rec is None or rec.kind != "gap":
        raise SearchError(where, f"{key} is not a gap record (searched names the gaps searched)")
    return str(key)


def _entry(
    doc: Any, profile_id: str, records: Records, allowed: tuple[str, ...], where: str
) -> ProfileEntry:
    if not isinstance(doc, Mapping):
        raise SearchError(where, "an entry is a mapping")
    unknown = set(doc) - set(ENTRY_FIELDS)
    if unknown:
        raise SearchError(where, f"unknown fields {sorted(unknown)}")
    element = doc.get("element")
    if element not in MATCH_MODES and element not in CITED_ONLY:
        raise SearchError(
            f"{where}.element",
            f"{element!r} is not an element that takes a reading "
            f"({', '.join([*MATCH_MODES, *CITED_ONLY])})",
        )
    where = f"{where} ({element})"
    match = doc.get("match")
    if element in MATCH_MODES:
        if match not in MATCH_MODES[str(element)]:
            raise SearchError(
                f"{where}.match", f"{match!r}: {element} is matched {MATCH_MODES[str(element)]}"
            )
    elif match is not None:
        raise SearchError(f"{where}.match", f"{element} takes no match mode")
    if match == "at_time":
        raise SearchError(f"{where}.match", "at_time needs a time, which only a query states")
    position = doc.get("position")
    by_body = doc.get("position_by_body") or {}
    if element in PLANET_ELEMENTS:
        if not _position(position):
            raise SearchError(f"{where}.position", f"{position!r}: true or mean")
        if not isinstance(by_body, Mapping):
            raise SearchError(f"{where}.position_by_body", "a mapping body → position")
        for body, p in by_body.items():
            if body not in PLANET_BODIES or not _position(p):
                raise SearchError(f"{where}.position_by_body", f"{body}: {p!r}")
    elif "position" in doc or "position_by_body" in doc:
        raise SearchError(f"{where}.position", f"{element} takes no position")
    cites = doc.get("cites")
    if not isinstance(cites, list) or not cites:
        raise SearchError(f"{where}.cites", "every entry cites at least one keyed statement")
    keys = tuple(_cited(records, k, f"{where}.cites", allowed) for k in cites)
    provisional = doc.get("provisional")
    searched = doc.get("searched") or []
    if provisional is not None:
        if not isinstance(provisional, str) or not provisional:
            raise SearchError(f"{where}.provisional", "a provisional entry states its reason")
        if not isinstance(searched, list) or not searched:
            raise SearchError(f"{where}.searched", "a provisional entry names the gaps searched")
    elif searched:
        raise SearchError(f"{where}.searched", "searched belongs to a provisional entry")
    gaps = tuple(_gap(records, k, f"{where}.searched") for k in searched)
    threshold = doc.get("threshold")
    unit = doc.get("threshold_unit")
    if threshold is not None:
        rec = records.data.get(str(threshold))
        if rec is None or rec.kind == "gap" or isinstance(rec.value, bool):
            raise SearchError(f"{where}.threshold", f"{threshold} is not a keyed datum")
        if rec.form not in ("integer", "fraction"):
            raise SearchError(f"{where}.threshold", f"{threshold} is not a number datum")
        if unit not in THRESHOLD_UNITS:
            raise SearchError(f"{where}.threshold_unit", f"{unit!r}: one of {THRESHOLD_UNITS}")
    elif unit is not None:
        raise SearchError(f"{where}.threshold_unit", "a unit belongs to a threshold")
    return ProfileEntry(
        str(element),
        match,
        position,
        dict(by_body),
        keys,
        provisional,
        gaps,
        None if threshold is None else str(threshold),
        unit,
        f"provisional:search.reading_profiles.{profile_id}.{element}",
    )


def load_reading_profile(
    repo: Path, profile_id: str, records: Records, eras: Mapping[str, EraFile]
) -> ReadingProfile:
    """The reading profile ``profile_id``, its citations resolved and its vocabulary generated."""
    if not isinstance(profile_id, str):
        raise SearchError("reading_profile", "a reading profile is named")
    path = repo.joinpath(*PROFILES_DIR, f"{profile_id}.yaml")
    if not path.is_file():
        raise SearchError(
            "reading_profile",
            f"no reading profile {profile_id!r} (ships: {', '.join(profile_ids(repo))})",
        )
    rel = path.relative_to(repo).as_posix()
    doc = load_exact(path)
    if not isinstance(doc, Mapping) or set(doc) != set(PROFILE_FIELDS):
        raise SearchError(rel, f"a reading profile has exactly the fields {PROFILE_FIELDS}")
    if doc["profile"] != profile_id:
        raise SearchError(f"{rel}: profile", f"{doc['profile']!r} is not the file's id")
    region = doc["names"]
    try:
        regional = load_profile(repo, str(region), records.data, eras)
    except ProfileError as e:
        raise SearchError(f"{rel}: names", str(e)) from None
    allowed = (CITATION_FILE, f"jyotirganita/regions/{region}/conventions.yaml")
    entries: dict[str, ProfileEntry] = {}
    if not isinstance(doc["entries"], list):
        raise SearchError(f"{rel}: entries", "a list of entries")
    for i, item in enumerate(doc["entries"]):
        pe = _entry(item, profile_id, records, allowed, f"{rel}: entries[{i}]")
        if pe.element in entries:
            raise SearchError(f"{rel}: entries[{i}]", f"a second entry for {pe.element}")
        entries[pe.element] = pe
    missing = [el for el in MATCH_MODES if el not in entries]
    if missing:
        raise SearchError(f"{rel}: entries", f"no entry for {missing}; each needs a match mode")
    return ReadingProfile(
        profile_id, str(region), str(doc["description"]), entries, Vocabulary(regional), rel
    )
