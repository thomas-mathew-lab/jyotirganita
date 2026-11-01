"""The datum model: schema, loader and rules.

Three kinds of file carry printed values, and each value carries the same
block (``value``, ``form``, ``unit``, ``script``, ``read``,
``second_read``, ``status`` and the optional fields the schema allows):

- a **datum file** under ``jyotirganita/data/`` (texts, eras, time
  standards) or ``jyotirganita/regions/``: a YAML list of datums;
- an **authority fixture** under ``tests/authority/``: one worked example,
  its class, the datum keys it exercises and its printed values;
- a **corpus file** under ``corpora/<corpus>/cells/``: transcribed cells.

A file is validated against ``schema/records.schema.json``; the loader then
applies the rules a schema cannot state, each failure a :class:`DatumError`
naming the file, the key and the rule:

- the source is in ``sources.yaml`` and held (a value from an unheld source
  is a gap), the file is named where the source has several, the
  PDF page lies in the file;
- ``status: verified`` (or ``validated``, ``corroborated``) is never
  written; ``read`` loads under a ``provisional`` or a ``validated``
  method, never under a ``corroborated`` one (the strict gates of
  this list bind the top grade; a ``validated`` method's open readings
  must not change a computed number, ``docs/verification.md`` V1);
- ``double_read`` needs a second read by another context, and, where the
  value is ``cross_model`` (a numeral-word, a table, an Indic-script value,
  a corpus cell), by another model id; a third look decides a
  disagreement;
- a text-layer read only for a born-digital file, a transcription read
  only for a corpus cell;
- ``form`` fixes how ``value`` parses; a sexagesimal carries its parts,
  never a decimal; a misprint that breaks its own form loads only with an
  ``emendation`` whose ``printed`` is the value;
- a numeral-word's own decode equals ``emendation.adopted`` or ``value``,
  or the datum carries ``mismatch_issue`` and loads only under a method
  not ``corroborated``, its records flagged ``provisional:<key>``;
- an issue field (``read_issue``, ``mismatch_issue``, a contradiction's
  ``issue``) names an entry of the issue register; a tree that holds no
  register (the public copy) writes ``disputed`` instead, and a tree that
  holds one never does;
- an ``owner_signoff`` names its ``ref`` and its ``signed_hash`` matches
  (otherwise "re-sign needed"); a datum that decides a procedure, an
  emendation or a control answer needs ``scope: individual``; an
  emendation whose evidence is an Indic reading loads only under a
  method not ``corroborated`` until it is signed off;
- ``verified_by`` names fixtures and datum keys, never a source, and never
  one whose copy has no established licence (karanapaddhati_2018, tantrasangraha_2011);
- a datum marked ``kind: model`` carries ``range`` (``unstated``, or its
  ends with the datum that states them) and may carry ``accuracy``; no
  other datum carries either.

``verified`` is not decided here: the development tree's ledger computes it
(``docs/verification.md``).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any, Literal

import jsonschema

from jyotirganita.core.exact import from_rdms, from_sexagesimal, parse_fraction
from jyotirganita.data.sources import Source, load_sources, schema
from jyotirganita.data.yamlio import dump_canonical, load_exact, loads_exact

__all__ = [
    "CONVENTIONS_FILE",
    "DISPUTED",
    "ERAS_DIR",
    "INDIC_SCRIPTS",
    "NAMES_FILE",
    "RECORDED",
    "RECORD_IDS",
    "STRICT_STATUS",
    "TIME_STANDARDS_DIR",
    "Context",
    "DatumError",
    "Fixture",
    "Record",
    "Records",
    "check_verified_by",
    "context_for",
    "corpus_files",
    "datum_files",
    "fixture_files",
    "identity_model",
    "load_corpus_file",
    "load_datum_file",
    "load_fixture",
    "load_records",
    "model_statements",
    "non_canonical",
    "signed_hash",
]

MethodStatus = Literal["provisional", "validated", "corroborated"]
#: the grade whose loading gates are the strict ones listed above
STRICT_STATUS = "corroborated"

INDIC_SCRIPTS = frozenset({"devanagari", "malayalam", "grantha", "tamil"})
_CROSS_MODEL_FORMS = frozenset({"numeral_word", "table"})
_SCALAR_FORMS = frozenset({"integer", "fraction", "sexagesimal", "rdms"})
_WRITTEN_COMPUTED = frozenset({"verified", "validated", "corroborated", "provisional"})
_SOURCE_ID = re.compile(r"^([a-z][a-z0-9_]*)(?![a-z0-9_./])")
_FIXTURE_ID = re.compile(r"^authority/[a-z0-9_]+(/[a-z0-9_]+)+$")
_KEY = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")
_DECISION_REF = re.compile(r"^D-[0-9]{3}$")
_ISSUE_ROW = re.compile(r"^\| (I-[0-9]{3}) \|", re.MULTILINE)
_DECISION_ROW = re.compile(r"^\| (D-[0-9]{3}) \|", re.MULTILINE)

# Files under jyotirganita/data/ that are registries, not datum files; and
# directories whose files have formats of their own (derived records,
# fetched kernels and tables).
_NOT_DATUM_FILES = frozenset({"sources.yaml", "engine_parameters.yaml", "firewall_allow.yaml"})
_NOT_DATUM_DIRS = frozenset({"derived", "ephemerides", "schema", "tables"})
ERAS_DIR = "eras"  # data/eras/<era_id>.yaml: era records
PLACES_FILE = "places.yaml"  # regions/<region>/places.yaml: a place table
NAMES_FILE = "names.yaml"  # regions/<region>/names.yaml: name tables
CONVENTIONS_FILE = "conventions.yaml"  # regions/<region>/conventions.yaml
TIME_STANDARDS_DIR = "time_standards"  # data/time_standards/<id>.yaml
# a regional profile's mapping files and the schema definition each is validated against
_REGION_FILES = {
    PLACES_FILE: "places_file",
    NAMES_FILE: "names_file",
    CONVENTIONS_FILE: "conventions_file",
}
PROCEDURE_FILES = frozenset({"procedures.yaml", "corrections.yaml"})
PROCEDURE_ONLY_FIELDS = ("procedure", "acts_on", "motion", "applies_to", "no_printed_example")


class DatumError(ValueError):
    """A datum, fixture or corpus cell that breaks a rule of the datum model."""


# --- context -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Context:
    """What the rules look up: the sources registry and the issue and decision ids.

    ``registers`` is whether the tree holds the issue and decision ids at all
    (the registers or ``RECORD_IDS``); a tree without them cites none and
    writes ``DISPUTED`` and ``RECORDED`` in their place.
    """

    sources: Mapping[str, Source]
    issues: frozenset[str]
    decisions: frozenset[str]
    registers: bool = True


#: the issue and decision ids the records cite, shipped for a tree without the
#: two registers (an installed package), written from the registers and the records
RECORD_IDS = ("jyotirganita", "data", "record_ids.json")
#: the issue field of a tree without the registers: the reads disagreed, and the
#: record of the disagreement is kept with the development record
DISPUTED = "disputed"
#: the sign-off ``ref`` of a tree without the registers: the owner's answer is kept
#: with the development record
RECORDED = "development-record"


def _ids(path: Path, rx: re.Pattern[str], shipped: str, repo: Path) -> frozenset[str]:
    """The ids of the register at ``path``; where it is absent, those of ``RECORD_IDS``."""
    if path.is_file():
        return frozenset(rx.findall(path.read_text(encoding="utf-8")))
    ids = repo.joinpath(*RECORD_IDS)
    if not ids.is_file():
        return frozenset()
    return frozenset(json.loads(ids.read_text(encoding="utf-8"))[shipped])


def context_for(repo: Path) -> Context:
    """The context of the repository at ``repo``.

    The issue and decision ids are read from ``ISSUES.md`` and
    ``DECISIONS.md`` where the tree holds them, and otherwise from the
    shipped ``RECORD_IDS``, which lists the ids the records cite.
    """
    registers = any(
        p.is_file() for p in (repo / "ISSUES.md", repo / "DECISIONS.md", repo.joinpath(*RECORD_IDS))
    )
    return Context(
        load_sources(repo / "jyotirganita" / "data" / "sources.yaml"),
        _ids(repo / "ISSUES.md", _ISSUE_ROW, "issues", repo),
        _ids(repo / "DECISIONS.md", _DECISION_ROW, "decisions", repo),
        registers,
    )


# --- records -------------------------------------------------------------------


def identity_model(identity: str) -> str:
    """The model id of a reader identity ``<model>/<date>-<tag>`` (or ``text-layer``)."""
    return identity.split("/", 1)[0]


@dataclass(frozen=True, slots=True)
class Record:
    """One printed value (a datum, a fixture value or a corpus cell) or a gap."""

    key: str
    kind: Literal["datum", "gap", "fixture_value", "corpus_cell"]
    path: str
    raw: Mapping[str, Any]
    status: Literal["read", "double_read", "gap"]
    source: str | None
    file: str | None
    form: str | None
    script: str | None
    value: object
    cross_model: bool
    indic: bool
    first_reader: str | None
    agreeing_reader: str | None
    flags: tuple[str, ...]
    signed_off: bool
    verified_by: tuple[str, ...]
    owner: str | None = None  # the fixture id or corpus id a value belongs to

    @property
    def cross_model_pair(self) -> bool:
        """Whether the two agreeing reads carry different model ids."""
        if self.first_reader is None or self.agreeing_reader is None:
            return False
        return identity_model(self.first_reader) != identity_model(self.agreeing_reader)


@dataclass(frozen=True, slots=True)
class Fixture:
    """An authority fixture: one printed worked example."""

    id: str
    path: str
    methods: tuple[str, ...]
    cls: Literal["text_computed", "editor_computed"]
    source: str
    datum_keys: tuple[str, ...]
    values: tuple[Record, ...]
    raw: Mapping[str, Any]

    @property
    def status(self) -> Literal["read", "double_read"]:
        """``double_read`` when every printed value is."""
        return "double_read" if all(v.status == "double_read" for v in self.values) else "read"


@dataclass(slots=True)
class Records:
    """Every datum, fixture and corpus cell of a repository, by key or id."""

    data: dict[str, Record] = field(default_factory=dict)
    fixtures: dict[str, Fixture] = field(default_factory=dict)
    cells: dict[str, Record] = field(default_factory=dict)

    def values(self) -> Iterator[Record]:
        """Every printed value: data, fixture values, corpus cells."""
        yield from self.data.values()
        for fx in self.fixtures.values():
            yield from fx.values
        yield from self.cells.values()


# --- schema --------------------------------------------------------------------


@cache
def _validator(definition: str) -> jsonschema.Draft202012Validator:
    doc = schema("records")
    return jsonschema.Draft202012Validator({"$defs": doc["$defs"], "$ref": f"#/$defs/{definition}"})


def _validate(doc: object, definition: str, where: str) -> None:
    errors = list(_validator(definition).iter_errors(doc))
    if not errors:
        return
    # an error inside allOf also leaves its properties "unevaluated"; report the cause
    causes = [e for e in errors if e.validator != "unevaluatedProperties"] or errors
    best = jsonschema.exceptions.best_match(causes) or causes[0]
    path = list(best.absolute_path)
    at = where
    if isinstance(doc, list) and path and isinstance(path[0], int):
        item = doc[path[0]]
        if isinstance(item, dict) and isinstance(item.get("key"), str):
            at = f"{where}: {item['key']}"
    loc = "/".join(str(p) for p in path) or "(top)"
    raise DatumError(f"{at}: schema ({loc}): {best.message}")


def _refuse_written_status(items: Sequence[object], where: str) -> None:
    for item in items:
        if isinstance(item, dict) and item.get("status") in _WRITTEN_COMPUTED:
            key = item.get("key", item.get("name", "?"))
            raise DatumError(
                f"{where}: {key}: status {item['status']} is computed by the ledger, never written"
            )


# --- form parsing --------------------------------------------------------------


def _ints(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(p, int) and not isinstance(p, bool) for p in value
    )


def _check_printed(
    form: str, value: object, raw: Mapping[str, Any], fail: Callable[[str], None]
) -> None:
    """The printed value has the shape its form declares (a misprint may break the range)."""
    if form == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            fail("form integer needs an integer value")
    elif form == "fraction":
        ok = isinstance(value, int) and not isinstance(value, bool)
        if isinstance(value, str):
            try:
                parse_fraction(value)
                ok = True
            except ValueError:
                ok = False
        if not ok:
            fail("form fraction needs an integer, a ratio or a printed decimal")
    elif form in ("sexagesimal", "rdms"):
        if not _ints(value) or not value:
            fail(f"form {form} carries its parts as a list of integers, never a decimal ")
        if form == "rdms" and len(value) < 2:  # type: ignore[arg-type]
            fail("form rdms needs at least [rāśi, degree]")
    elif form == "table":
        columns = raw.get("columns")
        if columns is None:
            fail("form table names its columns")
        if not isinstance(value, list) or not value:
            fail("form table needs a list of rows")
        assert isinstance(value, list) and isinstance(columns, list)
        for i, row in enumerate(value):
            if not isinstance(row, list) or len(row) != len(columns):
                fail(f"table row {i} does not have the {len(columns)} columns named")
            for cell in row:
                if not (cell is None or isinstance(cell, int | str) or _ints(cell)):
                    fail(f"table row {i}: a cell is a number, a printed text or a list of parts")
    elif form == "text":
        if not isinstance(value, str) or not value.strip():
            fail("form text needs a non-empty string")


def _parse(form: str, value: object, negative: bool, fail: Callable[[str], None]) -> object:
    """The exact value of a well-formed printed value by its form."""
    try:
        if form == "integer":
            assert isinstance(value, int)
            return -value if negative else value
        if form == "fraction":
            f = Fraction(value) if isinstance(value, int) else parse_fraction(str(value))
            return -f if negative else f
        if form == "sexagesimal":
            assert isinstance(value, list)
            return from_sexagesimal(value, negative=negative)
        if form == "rdms":
            assert isinstance(value, list)
            return from_rdms(value, negative=negative)
    except (ValueError, TypeError) as e:
        fail(f"form {form}: {e}; a printed misprint loads only with an emendation")
    if form == "table":
        assert isinstance(value, list)
        return tuple(tuple(tuple(c) if isinstance(c, list) else c for c in row) for row in value)
    return value


def _same(a: object, b: object) -> bool:
    """Printed-form equality: ``17.5`` and ``17.50`` differ, as printed values do."""
    return json.dumps(a, ensure_ascii=False, sort_keys=True) == json.dumps(
        b, ensure_ascii=False, sort_keys=True
    )


def signed_hash(raw: Mapping[str, Any]) -> str:
    """The ``signed_hash`` of a datum: its value, adopted emendation and word at signing.

    Definition: the SHA-256 of the compact JSON
    array ``[value, emendation.adopted or null, word.text or null]`` (keys
    sorted, Unicode as is), written ``sha256:<hex>``.
    """
    emendation = raw.get("emendation") or {}
    word = raw.get("word") or {}
    payload = [raw.get("value"), emendation.get("adopted"), word.get("text")]
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- the value block -----------------------------------------------------------


def _file_entry(src: Source, name: str | None, fail: Callable[[str], None]) -> dict[str, Any]:
    pdfs = [f for f in src.files if f["path"].endswith(".pdf")]
    if name is None:
        if len(pdfs) != 1:
            fail(f"{src.id} holds {len(pdfs)} PDF files; the datum names its `file`")
        return pdfs[0]
    exact = [f for f in src.files if f["path"] == name]
    if exact:
        return exact[0]
    # a bare file name must name one file
    named = [f for f in src.files if f["path"].rsplit("/", 1)[-1] == name]
    if len(named) > 1:
        fail(f"file {name} names {len(named)} files of {src.id}; give its path")
    if named:
        return named[0]
    fail(f"file {name} is not a file of {src.id} in sources.yaml")
    raise AssertionError


def _check_reads(
    raw: Mapping[str, Any],
    *,
    kind: str,
    file_entry: Mapping[str, Any],
    cross_model: bool,
    fail: Callable[[str], None],
) -> tuple[str, str | None]:
    """The first reader and the agreeing reader; refuses reads that do not count."""
    reads: list[dict[str, Any]] = list(raw["read"])
    seconds: list[dict[str, Any]] = list(raw.get("second_read", []))
    looks: list[dict[str, Any]] = (
        [raw["third_look"], *raw.get("further_look", [])] if "third_look" in raw else []
    )
    if "further_look" in raw and "third_look" not in raw:
        fail("a further look follows a third look")
    for r in [*reads, *seconds, *(lk["read"] for lk in looks)]:
        who = r["by"]
        if who.startswith("text-layer/"):
            if not file_entry.get("born_digital"):
                fail(
                    f"a text-layer read ({who}) is one of the two reads only for "
                    "a born-digital file"
                )
            if r["dpi"] is not None or r["clip"] != "page" or r["delivered_ppi"] != "vector":
                fail("a text-layer read records dpi: null, clip: page, delivered_ppi: vector")
        elif who.startswith("transcription/"):
            if kind != "corpus_cell":
                fail(f"a transcription read ({who}) is a first read of a corpus cell only")
            if "sha256" not in r:
                fail("a transcription read records the transcription file's sha256")
        else:
            clip = r["clip"]
            if r["dpi"] is None or clip == "page" or r["delivered_ppi"] in ("vector", "none"):
                fail(f"{who}: a page read records its dpi, clip and delivered pixels per inch")
            x0, y0, x1, y1 = (parse_fraction(str(c)) for c in clip)
            if not (x0 < x1 and y0 < y1):
                fail(f"{who}: clip {clip} is not x0 < x1, y0 < y1")
    later = [*seconds, *(lk["read"] for lk in looks)]
    if any(r["by"].startswith("transcription/") for r in later):
        # (item 7: it passed as a second reader of another model)
        fail("a transcription read is a first read of a corpus cell only")
    first = reads[0]["by"]
    if any(r["by"] != first for r in reads):
        fail(
            "every `read` entry is the first reader's (a re-read appends "
            "to it); another context's read is a second_read"
        )
    for r in seconds:
        if r["by"] == first:
            fail(f"{first} made the first read; a second read by the same context does not count")
    status = raw["status"]
    agreeing: str | None = None
    if "further_look" in raw:
        return _check_further_looks(
            raw, first, seconds, looks, status=status, cross_model=cross_model, fail=fail
        )
    if "third_look" in raw:
        tl = raw["third_look"]
        third = tl["read"]["by"]
        if tl["matches"] == "look" or "look" in tl:
            fail("a third look has no earlier look to match; matches: look is a further look's")
        if third == first or any(r["by"] == third for r in seconds):
            fail("a third look is a context different from both readers")
        if tl["matches"] == "read":
            agreeing = third
            pair_models = {identity_model(first), identity_model(third)}
        elif tl["matches"] == "second_read":
            if not seconds:
                fail("a third look matching the second read needs the second read recorded")
            first, agreeing = seconds[0]["by"], third
            pair_models = {identity_model(first), identity_model(third)}
        else:
            if status != "read":
                fail("a third look that matches neither reading leaves the datum at read")
            if "read_issue" not in raw:
                fail("a third look that matches neither reading carries read_issue")
            return first, None
        if status != "double_read":
            fail("a third look that matches a reading makes the datum double_read")
        if cross_model and len(pair_models) < 2:
            fail("a cross_model value is double_read only by two reads whose model ids differ")
        return first, agreeing
    if status == "read":
        if seconds:
            fail(
                "status read with a second_read: an agreement is "
                "double_read, a disagreement a recorded issue"
            )
        return first, None
    if not seconds:
        fail("status double_read needs a second_read")
    for r in seconds:
        if not cross_model or identity_model(r["by"]) != identity_model(first):
            agreeing = r["by"]
            break
    if agreeing is None:
        fail(
            "a cross_model value is double_read only by two reads whose model ids differ "
            f"(both are {identity_model(first)})"
        )
    return first, agreeing


def _check_further_looks(
    raw: Mapping[str, Any],
    first: str,
    seconds: Sequence[Mapping[str, Any]],
    looks: Sequence[Mapping[str, Any]],
    *,
    status: str,
    cross_model: bool,
    fail: Callable[[str], None],
) -> tuple[str, str | None]:
    """A third look followed by further looks: who carries the adopted reading.

    Every look is a context different from every earlier reader. A reading
    is carried by its originator (the first reader for ``read``, the second
    reader for ``second_read``, a look for the reading it made that matched
    neither) and by every look that matched it, directly or through
    ``matches: look`` naming the earlier look; the last look's
    reading is adopted when its carriers are two contexts and, on a
    ``cross_model`` value, two model ids. Otherwise the datum stays
    at ``read`` with ``read_issue``.
    """
    seen = [first, *(r["by"] for r in seconds)]
    origin_of: dict[str, str] = {}
    for i, lk in enumerate(looks):
        who = lk["read"]["by"]
        if who in seen:
            fail("a third or further look is a context different from every earlier reader")
        seen.append(who)
        if lk["matches"] == "look":
            named = lk.get("look")
            if i == 0 or named not in origin_of:
                fail("a look with matches: look names an earlier third or further look in `look`")
            origin_of[who] = origin_of[str(named)]
        else:
            if "look" in lk:
                fail("`look` goes only with matches: look")
            origin_of[who] = {"read": "read", "second_read": "second_read"}.get(lk["matches"], who)
    if any(lk["matches"] == "second_read" for lk in looks) and not seconds:
        fail("a look matching the second read needs the second read recorded")
    last = looks[-1]
    origin = origin_of[last["read"]["by"]]
    carriers: list[str] = []
    if last["matches"] != "neither":
        if origin == "read":
            carriers = [first]
        elif origin == "second_read":
            carriers = [seconds[0]["by"]]
        carriers += [lk["read"]["by"] for lk in looks if origin_of[lk["read"]["by"]] == origin]
    models = {identity_model(c) for c in carriers}
    adopted = len(carriers) >= 2 and (not cross_model or len(models) >= 2)
    if not adopted:
        if status != "read":
            fail(
                "the last look's reading is not carried by two contexts (and, on a "
                "cross_model value, two model ids): the datum stays at read"
            )
        if "read_issue" not in raw:
            fail("a datum left at read by its looks carries read_issue")
        return first, None
    if status != "double_read":
        fail("a reading carried by two contexts of two models is adopted: double_read")
    origin = carriers[0]
    agreeing = next(
        (c for c in carriers[1:] if identity_model(c) != identity_model(origin)), carriers[1]
    )
    return origin, agreeing


def _check_signoff(
    so: Mapping[str, Any],
    raw: Mapping[str, Any],
    ctx: Context,
    fail: Callable[[str], None],
    what: str,
) -> None:
    ref = so["ref"].strip()
    if not ref:
        fail(f"{what} has no ref: a sign-off without a ref fails to load")
    if ref == RECORDED:
        if ctx.registers:
            fail(f"{what} ref {RECORDED} is written only where the registers are not held")
    elif _DECISION_REF.match(ref):
        if ref not in ctx.decisions:
            fail(f"{what} ref {ref} is not in the decision register")
    elif not ref.startswith("https://"):
        fail(f"{what} ref is a URL of the owner's answer or a decision id")
    if so["signed_hash"] != signed_hash(raw):
        fail(f"{what} signed_hash no longer matches the datum: re-sign needed")


def _check_issue(what: str, issue: str, ctx: Context, fail: Callable[[str], None]) -> None:
    if issue == DISPUTED:
        if ctx.registers:
            fail(f"{what} {DISPUTED} is written only where the registers are not held")
    elif issue not in ctx.issues:
        fail(f"{what} {issue} is not in the issue register")


def _check_block(
    raw: Mapping[str, Any],
    *,
    key: str,
    kind: Literal["datum", "fixture_value", "corpus_cell"],
    place: Mapping[str, Any],
    path: str,
    ctx: Context,
    method_status: MethodStatus,
    owner: str | None = None,
) -> Record:
    where = f"{path}: {key}"

    def fail(rule: str) -> None:
        raise DatumError(f"{where}: {rule}")

    sid = place.get("source")
    if not isinstance(sid, str) or sid not in ctx.sources:
        fail(f"source {sid} is not in sources.yaml")
    src = ctx.sources[str(sid)]
    if src.kind != "library":
        fail(f"source {sid} is an online table, not a page; fetched tables are not datum files")
    if not src.held:
        fail(f"source {sid} is not held (sources.yaml gap); a value from an unheld source is a gap")
    if not src.files:
        fail(f"source {sid} holds no page file (a software mirror)")
    for need in ("edition_page", "pdf_page", "locus"):
        if need not in place:
            fail(f"{need} is required: both page numbers and the locus")
    entry = _file_entry(src, place.get("file"), fail)
    pages = entry.get("pages")
    if isinstance(pages, int) and place["pdf_page"] > pages:
        fail(f"pdf_page {place['pdf_page']} is beyond the {pages} pages of {entry['path']}")

    form: str = raw["form"]
    script: str = raw["script"]
    word = raw.get("word")
    indic = script in INDIC_SCRIPTS or (word is not None and word["script"] in INDIC_SCRIPTS)
    cross_model = form in _CROSS_MODEL_FORMS or indic or kind == "corpus_cell"

    # fields that belong to one form only
    if (form == "numeral_word") != ("value_form" in raw) or (form == "numeral_word") != (
        word is not None
    ):
        fail("a numeral_word carries value_form and word; no other form does")
    if (form == "table") != ("columns" in raw):
        fail("a table names its columns; no other form does")
    scalar_form = raw.get("value_form", form)
    if raw.get("negative") and scalar_form not in ("sexagesimal", "rdms", "integer", "fraction"):
        fail("negative applies to a number")

    _check_printed(scalar_form, raw["value"], raw, fail)
    emendation = raw.get("emendation")
    if emendation is not None:
        if not _same(emendation["printed"], raw["value"]):
            fail("emendation.printed is the value as printed")
        _check_printed(scalar_form, emendation["adopted"], raw, fail)
        if _same(emendation["printed"], emendation["adopted"]):
            fail("an emendation adopts a value different from the printed one")
        adopted = emendation["adopted"]
    else:
        adopted = raw["value"]
    value = _parse(scalar_form, adopted, bool(raw.get("negative")), fail)

    flags: list[str] = []
    if word is not None:
        _check_printed(scalar_form, word["decode"], raw, fail)
        if not _same(word["decode"], adopted):
            issue = raw.get("mismatch_issue")
            if issue is None:
                target = "emendation.adopted" if emendation is not None else "value"
                fail(
                    f"the word's decode differs from {target} and the datum carries no "
                    "mismatch_issue"
                )
            if method_status == STRICT_STATUS:
                fail(
                    f"mismatch_issue {issue}: a numeral-word whose decodes differ loads only "
                    "while its method is not corroborated"
                )
            flags.append(f"provisional:{key}")
    for field_name in ("mismatch_issue", "read_issue"):
        if field_name in raw:
            _check_issue(field_name, raw[field_name], ctx, fail)
    contradiction = raw.get("contradiction")
    if contradiction is not None:
        _check_issue("contradiction issue", contradiction["issue"], ctx, fail)
        if key in contradiction["with"]:
            fail("a datum does not contradict itself")
        flags.append(f"provisional:{key}")

    first, agreeing = _check_reads(
        raw, kind=kind, file_entry=entry, cross_model=cross_model, fail=fail
    )
    if raw["status"] == "read" and method_status == STRICT_STATUS:
        fail("status read loads only under a method not corroborated")

    signoff = raw.get("owner_signoff")
    decides = raw.get("decides")
    if decides is not None and not indic:
        fail(
            "decides marks an Indic reading that decides a procedure, an "
            "emendation, a control answer or a method's identity"
        )
    if signoff is not None:
        if not indic:
            fail("owner_signoff is for Indic-script data")
        _check_signoff(signoff, raw, ctx, fail, "owner_signoff")
        if decides is not None and signoff["scope"] != "individual":
            fail(
                "a reading that decides a procedure, an emendation, a control "
                "answer or a method's identity is signed off with scope: individual "
                ""
            )
    signed_off = (not indic) or signoff is not None
    if indic and signoff is None and method_status == STRICT_STATUS:
        fail("an Indic-script value loads under a corroborated method only with owner_signoff")
    if emendation is not None and emendation["evidence_indic"]:
        eso = emendation["owner_signoff"]
        if eso is None:
            if method_status == STRICT_STATUS:
                fail(
                    "an emendation whose evidence is an Indic reading needs "
                    "owner_signoff before its method is corroborated"
                )
            flags.append(f"provisional:{key}")
            signed_off = False
        else:
            _check_signoff(eso, raw, ctx, fail, "emendation.owner_signoff")
            if eso["scope"] != "individual":
                fail(
                    "an emendation resting on an Indic reading is signed off with scope: individual"
                )
    elif emendation is not None and emendation["owner_signoff"] is not None:
        fail("emendation.owner_signoff is for an emendation whose evidence is an Indic reading")
    if "provisional" in raw:
        flags.append(f"provisional:{key}")
    npe = raw.get("no_printed_example")
    if npe is not None and npe["external"] == "pending":
        # a procedure without a printed example, its external comparison pending
        #
        flags.append(f"provisional:{key}")

    verified_by: tuple[str, ...] = tuple(raw.get("verified_by", ()))
    for v in verified_by:
        m = _SOURCE_ID.match(v)
        if m:
            cited = m.group(1)
            if cited in ctx.sources and ctx.sources[cited].excluded:
                fail(f"verified_by cites {cited}, a copy without an established licence")
            fail(f"verified_by names fixtures and datum keys, not a source ({v})")
        if not (_FIXTURE_ID.match(v) or _KEY.match(v)):
            fail(f"verified_by entry {v!r} is neither a fixture id nor a datum key")

    return Record(
        key=key,
        kind=kind,
        path=path,
        raw=raw,
        status=raw["status"],
        source=str(sid),
        file=entry["path"],
        form=form,
        script=script,
        value=value,
        cross_model=cross_model,
        indic=indic,
        first_reader=first,
        agreeing_reader=agreeing,
        flags=tuple(dict.fromkeys(flags)),
        signed_off=signed_off,
        verified_by=verified_by,
        owner=owner,
    )


# --- files ---------------------------------------------------------------------


def _rel(path: Path, repo: Path | None) -> str:
    if repo is not None and path.resolve().is_relative_to(repo.resolve()):
        return path.resolve().relative_to(repo.resolve()).as_posix()
    return str(path)


def _end_order(end: Mapping[str, Any]) -> tuple[int, int, int]:
    """A range end as a sortable (year, month, day); a bare year is its first day."""
    if "year" in end:
        return (end["year"], 1, 1)
    y, m, d = (int(x) for x in end["date"].split("-"))
    return (y, m, d)


def _check_interval(lo: Mapping[str, Any], hi: Mapping[str, Any], what: str) -> None:
    cals = {e["calendar"] for e in (lo, hi) if "calendar" in e}
    if len(cals) > 1:
        raise DatumError(f"{what}: its two ends are dated in different calendars")
    if _end_order(lo) > _end_order(hi):
        raise DatumError(f"{what}: from lies after to")


def _check_model(item: Mapping[str, Any], rel: str, key: str) -> None:
    """``kind: model`` carries ``range`` and may carry ``accuracy``; no other datum
    carries either."""
    model = item.get("kind") == "model"
    if model and "range" not in item:
        raise DatumError(
            f"{rel}: {key}: a model datum carries range: {{from, to, stated_by}} or range: unstated"
        )
    if not model and ("range" in item or "accuracy" in item):
        raise DatumError(f"{rel}: {key}: range and accuracy belong on a datum marked kind: model ")
    rng = item.get("range")
    if isinstance(rng, dict):
        _check_interval(rng["from"], rng["to"], f"{rel}: {key}: range")
    for acc in item.get("accuracy", ()):
        iv = acc["interval"]
        _check_interval(iv["from"], iv["to"], f"{rel}: {key}: accuracy interval")


def model_statements(item: Mapping[str, Any]) -> list[str]:
    """The datum keys a model datum's range and accuracy name as their statements."""
    out = []
    rng = item.get("range")
    if isinstance(rng, dict):
        out.append(rng["stated_by"])
    out.extend(acc["stated_by"] for acc in item.get("accuracy", ()))
    return out


def load_datum_file(
    path: Path,
    ctx: Context,
    method_status: MethodStatus = "provisional",
    repo: Path | None = None,
) -> list[Record]:
    """The data of one datum file: a YAML list of datums and gaps, or a record file.

    An era record (``data/eras/<era_id>.yaml``), a time
    standard (``data/time_standards/<id>.yaml``) and a region's place
    table, name tables and conventions (``regions/<region>/``) are
    mappings whose ``data`` list holds their datums; their structure is read
    by ``jyotirganita/data/eras.py``, ``data/time_standards.py`` and
    ``regions/``.
    """
    rel = _rel(path, repo)
    whole = load_exact(path)
    if isinstance(whole, dict) and path.parent.name == ERAS_DIR:
        _refuse_written_status(whole.get("data", []), rel)
        _validate(whole, "era_file", rel)
        if whole["era"] != path.stem:
            raise DatumError(f"{rel}: era {whole['era']} is not its file name ({path.stem})")
        doc = whole["data"]
    elif isinstance(whole, dict) and path.name in _REGION_FILES:
        _refuse_written_status(whole.get("data", []), rel)
        _validate(whole, _REGION_FILES[path.name], rel)
        if whole["region"] != path.parent.name:
            raise DatumError(
                f"{rel}: region {whole['region']} is not its directory ({path.parent.name})"
            )
        doc = whole["data"]
    elif isinstance(whole, dict) and path.parent.name == TIME_STANDARDS_DIR:
        _refuse_written_status(whole.get("data", []), rel)
        _validate(whole, "time_standard_file", rel)
        if whole["standard"] != path.stem:
            raise DatumError(
                f"{rel}: standard {whole['standard']} is not its file name ({path.stem})"
            )
        doc = whole["data"]
    elif not isinstance(whole, list):
        raise DatumError(
            f"{rel}: a datum file is a list of datums, an era record under "
            f"{ERAS_DIR}/, a time standard under {TIME_STANDARDS_DIR}/ or a region's "
            f"{', '.join(sorted(_REGION_FILES))} (docs/data.md)"
        )
    else:
        doc = whole
        _refuse_written_status(doc, rel)
        _validate(doc, "datum_file", rel)
    out: list[Record] = []
    procedures = path.name == "procedures.yaml"
    procedure_fields = path.name in PROCEDURE_FILES
    for item in doc:
        key = item["key"]
        if not procedure_fields:
            for name in PROCEDURE_ONLY_FIELDS:
                if name in item:
                    raise DatumError(
                        f"{rel}: {key}: {name} belongs on a procedure datum of a text's "
                        "procedures.yaml or corrections.yaml"
                    )
        if item["status"] == "gap":
            sid = item.get("source")
            if sid is not None and sid not in ctx.sources:
                raise DatumError(f"{rel}: {key}: source {sid} is not in sources.yaml")
            out.append(
                Record(
                    key,
                    "gap",
                    rel,
                    item,
                    "gap",
                    sid,
                    None,
                    None,
                    None,
                    None,
                    False,
                    False,
                    None,
                    None,
                    (),
                    True,
                    (),
                )
            )
            continue
        if procedures and "basis" not in item:
            raise DatumError(
                f"{rel}: {key}: a procedure datum carries basis: stated | inferred_from_example "
                "| fallback_no_stated_rule"
            )
        if ("basis" in item) != ("basis_ref" in item):
            raise DatumError(f"{rel}: {key}: basis names its verse or fixture in basis_ref")
        _check_model(item, rel, key)
        out.append(
            _check_block(
                item,
                key=key,
                kind="datum",
                place=item,
                path=rel,
                ctx=ctx,
                method_status=method_status,
            )
        )
    return out


def load_fixture(
    path: Path,
    ctx: Context,
    method_status: MethodStatus = "provisional",
    repo: Path | None = None,
) -> Fixture:
    """One authority fixture under ``tests/authority/``."""
    rel = _rel(path, repo)
    doc = load_exact(path)
    if not isinstance(doc, dict):
        raise DatumError(f"{rel}: a fixture is a mapping (docs/data.md)")
    _refuse_written_status(doc.get("values", []), rel)
    _validate(doc, "fixture_file", rel)
    if repo is not None:
        expected = (
            "authority/" + Path(rel).relative_to("tests/authority").with_suffix("").as_posix()
        )
        if doc["id"] != expected:
            raise DatumError(f"{rel}: fixture id {doc['id']} is not its path ({expected})")
    if doc["class"] == "editor_computed" and doc["precision"] is None:
        raise DatumError(f"{rel}: an editor_computed example states the editor's precision")
    base = {k: doc[k] for k in ("source", "file", "edition_page", "pdf_page", "locus") if k in doc}
    names: set[str] = set()
    values: list[Record] = []
    for v in doc["values"]:
        if v["name"] in names:
            raise DatumError(f"{rel}: value {v['name']} named twice")
        names.add(v["name"])
        place = {
            **base,
            **{k: v[k] for k in ("source", "file", "edition_page", "pdf_page", "locus") if k in v},
        }
        values.append(
            _check_block(
                v,
                key=f"{doc['id']}#{v['name']}",
                kind="fixture_value",
                place=place,
                path=rel,
                ctx=ctx,
                method_status=method_status,
                owner=doc["id"],
            )
        )
    return Fixture(
        doc["id"],
        rel,
        tuple(doc["methods"]),
        doc["class"],
        doc["source"],
        tuple(doc["datum_keys"]),
        tuple(values),
        doc,
    )


def load_corpus_file(path: Path, ctx: Context, repo: Path | None = None) -> list[Record]:
    """The cells of one corpus file under ``corpora/<corpus>/cells/``."""
    rel = _rel(path, repo)
    doc = load_exact(path)
    if not isinstance(doc, dict):
        raise DatumError(f"{rel}: a corpus file is a mapping (docs/data.md)")
    _refuse_written_status(doc.get("cells", []), rel)
    _validate(doc, "corpus_file", rel)
    base = {k: doc[k] for k in ("source", "file") if k in doc}
    return [
        _check_block(
            c,
            key=c["key"],
            kind="corpus_cell",
            place={**base, **c},
            path=rel,
            ctx=ctx,
            method_status="provisional",
            owner=doc["corpus"],
        )
        for c in doc["cells"]
    ]


def datum_files(repo: Path) -> list[Path]:
    """The datum files of the repository: under ``jyotirganita/data/`` and ``regions/``."""
    data = repo / "jyotirganita" / "data"
    out: list[Path] = []
    for path in sorted(data.rglob("*.yaml")):
        rel = path.relative_to(data)
        if rel.parts[0] in _NOT_DATUM_DIRS or (
            len(rel.parts) == 1 and rel.name in _NOT_DATUM_FILES
        ):
            continue
        out.append(path)
    out.extend(sorted((repo / "jyotirganita" / "regions").rglob("*.yaml")))
    return out


def fixture_files(repo: Path) -> list[Path]:
    """The authority fixtures."""
    return sorted((repo / "tests" / "authority").rglob("*.yaml"))


def corpus_files(repo: Path) -> list[Path]:
    """The corpus cell files."""
    return sorted((repo / "corpora").glob("*/cells/**/*.yaml"))


def non_canonical(path: Path) -> bool:
    """Whether a record file differs from its canonical rewrite (docs/data.md)."""
    text = path.read_text(encoding="utf-8")
    return dump_canonical(loads_exact(text)) != text


def check_verified_by(out: Records, ctx: Context, *, fixtures_held: bool = True) -> None:
    """Every datum's ``verified_by`` names a datum or fixture resting on no excluded copy.

    A fixture's values may name their own sources, each checked. Fixture values and corpus cells
    carry no
    ``verified_by`` (their schemas). Without ``fixtures_held`` (a tree without
    ``tests/authority/``, as an installed package is) the fixtures
    named are not checked.
    """
    for rec in out.data.values():
        for v in rec.verified_by:
            if v.startswith("authority/"):
                if not fixtures_held:
                    continue
                cited_fx = out.fixtures.get(v)
                if cited_fx is None:
                    raise DatumError(f"{rec.path}: {rec.key}: verified_by {v} is not a fixture")
                fx_sources = {cited_fx.source} | {x.source for x in cited_fx.values if x.source}
                if any(ctx.sources[s].excluded for s in fx_sources):
                    raise DatumError(
                        f"{rec.path}: {rec.key}: verified_by {v} rests on {cited_fx.source}, "
                        "a copy without an established licence"
                    )
            else:
                w = out.data.get(v)
                if w is None or w.kind == "gap":
                    raise DatumError(f"{rec.path}: {rec.key}: verified_by {v} is not a datum")
                if w.source is not None and ctx.sources[w.source].excluded:
                    raise DatumError(
                        f"{rec.path}: {rec.key}: verified_by {v} rests on {w.source}, a copy "
                        "without an established licence"
                    )


def load_records(
    repo: Path,
    ctx: Context | None = None,
    method_status: Callable[[str, Sequence[str]], MethodStatus] | None = None,
) -> Records:
    """Every record of the repository, cross-checked.

    ``method_status(kind, names)`` gives the status the records load under:
    for a datum file, ``names`` is the file's path relative to the repository
    (``jyotirganita/data/texts/<text>/...``);
    for a fixture, its methods. The default is ``provisional``, which is
    every method's status until the ledger computes otherwise.
    """
    ctx = ctx or context_for(repo)

    def status_of(kind: str, names: Sequence[str]) -> MethodStatus:
        return method_status(kind, names) if method_status is not None else "provisional"

    out = Records()
    seen: dict[str, str] = {}

    def add(rec: Record) -> None:
        if rec.key in seen:
            raise DatumError(f"{rec.path}: {rec.key}: key also defined in {seen[rec.key]}")
        seen[rec.key] = rec.path

    for path in datum_files(repo):
        rel = _rel(path, repo)
        for rec in load_datum_file(path, ctx, status_of("datum", [rel]), repo):
            add(rec)
            out.data[rec.key] = rec
    # An installed package ships the data without the tests: its records'
    # references to fixtures are checked in the tree that has them.
    fixtures_held = (repo / "tests" / "authority").is_dir()
    for path in fixture_files(repo):
        fx_doc = load_exact(path)
        methods = fx_doc.get("methods", []) if isinstance(fx_doc, dict) else []
        fx = load_fixture(path, ctx, status_of("fixture", methods), repo)
        if fx.id in out.fixtures:
            raise DatumError(f"{fx.path}: fixture id {fx.id} also in {out.fixtures[fx.id].path}")
        out.fixtures[fx.id] = fx
    for path in corpus_files(repo):
        for rec in load_corpus_file(path, ctx, repo):
            add(rec)
            out.cells[rec.key] = rec

    check_verified_by(out, ctx, fixtures_held=fixtures_held)
    for rec in out.data.values():
        for stated in model_statements(rec.raw):
            w = out.data.get(stated)
            if w is None or w.kind == "gap":
                raise DatumError(
                    f"{rec.path}: {rec.key}: range or accuracy stated_by {stated} is not a datum"
                )
        contradiction = rec.raw.get("contradiction")
        if contradiction is not None:
            for other in contradiction["with"]:
                w = out.data.get(other)
                if w is None or w.kind == "gap":
                    raise DatumError(
                        f"{rec.path}: {rec.key}: contradiction names {other}, which is not a datum"
                    )
        basis = rec.raw.get("basis")
        if basis == "inferred_from_example" and fixtures_held:
            basis_fx = out.fixtures.get(rec.raw["basis_ref"])
            if basis_fx is None or basis_fx.cls != "text_computed":
                raise DatumError(
                    f"{rec.path}: {rec.key}: basis inferred_from_example names a text_computed "
                    "fixture in basis_ref"
                )
    for fx in out.fixtures.values():
        for k in fx.datum_keys:
            if k not in out.data:
                raise DatumError(f"{fx.path}: datum_keys names {k}, which is not a datum")
    return out
