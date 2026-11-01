"""The constants firewall.

Scans every ``.py`` file under the package for numeric literals and for the
banned float-world imports.

**Literals.** Allowed without annotation: the closed set
(:data:`ALLOWED`, compared by magnitude), and the entries of
``data/firewall_allow.yaml``, each with a one-line reason; an entry scoped
to a ``module`` is reserved for a constant the
module derives in its docstring from the calendars' own leap rules, so the
firewall also requires the literal's text in that module's docstring. Any
other literal fails unless its line carries exactly one tag:

- ``# datum: <key>`` — the key must load from the datum files, must not be
  a ``status: gap`` datum, and the literal must equal the datum's value as
  parsed by its ``form``;
- ``# engine-parameter: <key>`` — an entry of ``data/engine_parameters.yaml``
  whose value the literal must equal;
- ``# derived: <key>`` — a derived record of ``data/derived/`` whose value
  the literal must equal.

A tag on a line with no literal for it to cover is reported (a stale tag).
A tag on a line whose literals are all in the closed set or the allow-list
is asserted all the same: one of them must equal the value it names.

What counts as a literal: every ``int``, ``float`` and ``complex`` constant
(``bool`` excluded), a unary minus applied to one (the signed value is what
a tag is compared with), and a numeric string passed to ``Fraction``,
``int``, ``float`` or ``Decimal`` (``Fraction("0.0057183")`` is the same
literal written another way). A float's value is taken exactly from its
source text, never through binary floating point.

**Imports.** ``math``, ``cmath``, ``numpy`` and ``decimal`` may not be
imported (by ``import``, ``from … import``, ``importlib.import_module`` or
``__import__``) under ``siddhantic/``, ``calendar/``, ``search/`` or in
``core/exact.py``.

The datum index comes from the loader (``data/datum.py``): a tag names
only a datum that loads under every rule of the datum model.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from jyotirganita.core.exact import parse_fraction
from jyotirganita.data import engine_parameters
from jyotirganita.data.datum import context_for, datum_files, load_datum_file
from jyotirganita.data.yamlio import load_exact

__all__ = [
    "ALLOWED",
    "BANNED_IMPORTS",
    "BAN_SCOPES",
    "AllowEntry",
    "Finding",
    "TagTarget",
    "check_package",
    "check_source",
    "load_allow_list",
    "load_datum_index",
    "load_derived_index",
    "load_engine_parameter_index",
]

# the closed set (with 5, 10, 100 and 1000).
ALLOWED: frozenset[Fraction] = frozenset(
    Fraction(v)
    for v in (
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        10,
        12,
        15,
        24,
        27,
        30,
        60,
        90,
        100,
        180,
        360,
        1000,
        1440,
        3600,
        86400,
    )
) | {Fraction(1, 2)}

BANNED_IMPORTS = frozenset({"math", "cmath", "numpy", "decimal"})

# Package-relative POSIX paths: a directory prefix ends in "/".
BAN_SCOPES = ("siddhantic/", "calendar/", "search/", "core/exact.py")

_TAG = re.compile(r"#\s*(datum|engine-parameter|derived):\s*(\S+)")
_NUMERIC_CALLS = frozenset({"Fraction", "int", "float", "Decimal"})


@dataclass(frozen=True, slots=True)
class Finding:
    """One firewall failure."""

    path: str
    line: int
    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.message}"


@dataclass(frozen=True, slots=True)
class TagTarget:
    """What a tag resolves to: a status and an exact value (``None`` if non-scalar)."""

    key: str
    status: str
    value: Fraction | None
    origin: str


@dataclass(frozen=True, slots=True)
class AllowEntry:
    """One entry of ``firewall_allow.yaml``."""

    value: Fraction
    reason: str
    module: str | None


class FirewallConfigError(ValueError):
    """A malformed allow-list, datum file or derived record."""


# --- indices ------------------------------------------------------------------


def _exact(raw: object, where: str) -> Fraction:
    if isinstance(raw, bool):
        raise FirewallConfigError(f"{where}: a boolean is not a number")
    if isinstance(raw, int):
        return Fraction(raw)
    if isinstance(raw, str):  # includes PrintedNumber
        return parse_fraction(raw)
    raise FirewallConfigError(f"{where}: not an exact number: {raw!r}")


def load_datum_index(data_root: Path) -> dict[str, TagTarget]:
    """Every datum key of the repository with its status and scalar value.

    The datum files load through :mod:`jyotirganita.data.datum`, the
    loader, so a tag can name only a datum that passes every rule of
    the datum model; the repository is the parent of the package of
    ``data_root``. A numeral-word's value is its decode; a table or text
    datum has no scalar value, and a tag naming it fails.
    """
    repo = data_root.parent.parent
    ctx = context_for(repo)
    index: dict[str, TagTarget] = {}
    for path in datum_files(repo):
        for rec in load_datum_file(path, ctx, repo=repo):
            if rec.key in index:
                raise FirewallConfigError(
                    f"{rec.path}: {rec.key}: key also defined in {index[rec.key].origin}"
                )
            value = Fraction(rec.value) if isinstance(rec.value, int | Fraction) else None
            index[rec.key] = TagTarget(rec.key, rec.status, value, rec.path)
    return index


def load_engine_parameter_index(path: Path) -> dict[str, TagTarget]:
    """The engine parameters as tag targets."""
    if not path.exists():
        return {}
    return {
        k: TagTarget(k, "engine_parameter", p.value, str(path))
        for k, p in engine_parameters.load(path).items()
    }


def load_derived_index(derived_dir: Path) -> dict[str, TagTarget]:
    """Derived records by key: a list of ``{key, value, ...}`` per file.

    The full derived-record schema and its hash check are
    ``data/derived.py``'s; the firewall needs only the key and the value.
    """
    index: dict[str, TagTarget] = {}
    if not derived_dir.is_dir():
        return index
    for path in sorted(derived_dir.glob("*.yaml")):
        doc = load_exact(path)
        if not isinstance(doc, list):
            raise FirewallConfigError(f"{path}: a derived file is a list of records")
        for i, rec in enumerate(doc):
            if not isinstance(rec, dict) or not isinstance(rec.get("key"), str):
                raise FirewallConfigError(f"{path}: record {i} has no key")
            key = rec["key"]
            if key in index:
                raise FirewallConfigError(f"{path}: derived key {key} defined twice")
            index[key] = TagTarget(
                key, "derived", _exact(rec.get("value"), f"{path}:{key}"), str(path)
            )
    return index


def load_allow_list(path: Path) -> list[AllowEntry]:
    """Read ``firewall_allow.yaml``: ``entries: [{value, reason, module?}]``."""
    doc = load_exact(path)
    if not isinstance(doc, dict) or set(doc) != {"entries"} or not isinstance(doc["entries"], list):
        raise FirewallConfigError(f"{path}: the file holds one mapping, 'entries', a list")
    out: list[AllowEntry] = []
    for i, e in enumerate(doc["entries"]):
        where = f"{path}: entry {i}"
        if not isinstance(e, dict) or not {"value", "reason"} <= set(e) <= {
            "value",
            "reason",
            "module",
        }:
            raise FirewallConfigError(f"{where}: fields are value, reason and optional module")
        reason = e["reason"]
        if not isinstance(reason, str) or not reason.strip() or "\n" in reason.strip():
            raise FirewallConfigError(f"{where}: reason is one non-empty line")
        module = e.get("module")
        if module is not None and not isinstance(module, str):
            raise FirewallConfigError(f"{where}: module is a package-relative path")
        value = _exact(e["value"], where)
        if abs(value) in ALLOWED:
            raise FirewallConfigError(f"{where}: {value} is already in the closed set")
        out.append(AllowEntry(value, reason.strip(), module))
    return out


# --- scanning -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Literal:
    line: int
    value: Fraction | None  # None for a complex literal
    text: str


def _literal_value(text: str) -> Fraction:
    t = text.replace("_", "").strip()
    if t[:2].lower() in ("0x", "0o", "0b"):
        return Fraction(int(t, 0))
    return Fraction(t)


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


class _Collector(ast.NodeVisitor):
    def __init__(self, source: str) -> None:
        self.source = source
        self.literals: list[_Literal] = []
        self.imports: list[tuple[int, str]] = []
        self._covered: set[int] = set()

    def _add_number(self, node: ast.Constant, negative: bool) -> None:
        self._covered.add(id(node))
        if isinstance(node.value, complex):
            self.literals.append(_Literal(node.lineno, None, repr(node.value)))
            return
        text = ast.get_source_segment(self.source, node) or repr(node.value)
        value = _literal_value(text)
        self.literals.append(_Literal(node.lineno, -value if negative else value, text))

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        operand = node.operand
        if (
            isinstance(node.op, ast.USub)
            and isinstance(operand, ast.Constant)
            and _is_number(operand.value)
        ):
            self._add_number(operand, negative=True)
            return
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if id(node) not in self._covered and _is_number(node.value):
            self._add_number(node, negative=False)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name in _NUMERIC_CALLS and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                try:
                    value = parse_fraction(first.value.replace("_", ""))
                except ValueError:
                    value = None
                if value is not None:
                    self.literals.append(_Literal(first.lineno, value, repr(first.value)))
        if name in ("import_module", "__import__") and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                self.imports.append((node.lineno, first.value))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append((node.lineno, alias.name))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and node.level == 0:
            self.imports.append((node.lineno, node.module))


def _is_number(v: object) -> bool:
    return isinstance(v, int | float | complex) and not isinstance(v, bool)


def _tags(source: str) -> dict[int, list[tuple[str, str]]]:
    tags: dict[int, list[tuple[str, str]]] = {}
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            for kind, key in _TAG.findall(tok.string):
                tags.setdefault(tok.start[0], []).append((kind, key))
    return tags


def _module_docstring(source: str) -> str:
    try:
        return ast.get_docstring(ast.parse(source)) or ""
    except SyntaxError:
        return ""


def _in_ban_scope(rel: str) -> bool:
    return any(rel.startswith(s) if s.endswith("/") else rel == s for s in BAN_SCOPES)


def check_source(
    source: str,
    rel: str,
    *,
    allow: Iterable[AllowEntry],
    datums: Mapping[str, TagTarget],
    params: Mapping[str, TagTarget],
    derived: Mapping[str, TagTarget],
    display: str | None = None,
) -> list[Finding]:
    """Check one module's source; ``rel`` is its package-relative POSIX path."""
    shown = display or rel
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [Finding(shown, exc.lineno or 0, "syntax", str(exc))]
    collector = _Collector(source)
    collector.visit(tree)
    findings: list[Finding] = []

    if _in_ban_scope(rel):
        for line, name in collector.imports:
            if name.split(".")[0] in BANNED_IMPORTS:
                findings.append(
                    Finding(shown, line, "import-ban", f"import of {name} in an exact-only module")
                )

    allow_list = list(allow)
    docstring = _module_docstring(source)
    tags = _tags(source)
    used_tag_lines: set[int] = set()
    tables: dict[str, Mapping[str, TagTarget]] = {
        "datum": datums,
        "engine-parameter": params,
        "derived": derived,
    }
    allowed_on_line: dict[int, list[_Literal]] = {}

    def resolve(line: int, kind: str, key: str) -> TagTarget | None:
        target = tables[kind].get(key)
        if target is None:
            findings.append(Finding(shown, line, "tag", f"{kind} key {key} does not load"))
        elif target.status == "gap":
            findings.append(Finding(shown, line, "tag", f"{kind} key {key} is a gap datum"))
        elif target.value is None:
            findings.append(
                Finding(shown, line, "tag", f"{kind} key {key} has no scalar value to compare")
            )
        else:
            return target
        return None

    for lit in collector.literals:
        if lit.value is None:
            findings.append(Finding(shown, lit.line, "literal", f"complex literal {lit.text}"))
            continue
        if abs(lit.value) in ALLOWED or any(_allows(a, lit, rel, docstring) for a in allow_list):
            allowed_on_line.setdefault(lit.line, []).append(lit)
            continue
        line_tags = tags.get(lit.line, [])
        if not line_tags:
            findings.append(Finding(shown, lit.line, "literal", f"untagged literal {lit.text}"))
            continue
        used_tag_lines.add(lit.line)
        if len(line_tags) > 1:
            findings.append(Finding(shown, lit.line, "tag", "more than one tag on one line"))
            continue
        kind, key = line_tags[0]
        target = resolve(lit.line, kind, key)
        if target is not None and target.value != lit.value:
            findings.append(
                Finding(
                    shown,
                    lit.line,
                    "tag-value",
                    f"literal {lit.text} = {lit.value} differs from {kind} {key} = {target.value}",
                )
            )
    # A tag on a line whose only literals are allowed ones is still asserted:
    # it must name a value one of them equals (a present tag is never ignored).
    for line in sorted(set(tags) - used_tag_lines):
        lits = allowed_on_line.get(line)
        if not lits:
            findings.append(Finding(shown, line, "tag", "tag on a line with no literal it covers"))
            continue
        if len(tags[line]) > 1:
            findings.append(Finding(shown, line, "tag", "more than one tag on one line"))
            continue
        kind, key = tags[line][0]
        target = resolve(line, kind, key)
        if target is not None and all(lit.value != target.value for lit in lits):
            shown_lits = ", ".join(lit.text for lit in lits)
            findings.append(
                Finding(
                    shown,
                    line,
                    "tag-value",
                    f"no literal on the line ({shown_lits}) equals {kind} {key} = {target.value}",
                )
            )
    return findings


def _allows(entry: AllowEntry, lit: _Literal, rel: str, docstring: str) -> bool:
    if lit.value is None or abs(lit.value) != entry.value:
        return False
    if entry.module is None:
        return True
    return entry.module == rel and lit.text.replace("_", "") in docstring


def check_package(package_root: Path) -> list[Finding]:
    """Check every ``.py`` file under ``package_root`` against its own data files."""
    data_root = package_root / "data"
    allow_path = data_root / "firewall_allow.yaml"
    allow = load_allow_list(allow_path) if allow_path.exists() else []
    datums = load_datum_index(data_root)
    params = load_engine_parameter_index(data_root / "engine_parameters.yaml")
    derived = load_derived_index(data_root / "derived")
    findings: list[Finding] = []
    for path in sorted(package_root.rglob("*.py")):
        rel = path.relative_to(package_root).as_posix()
        source = path.read_text(encoding="utf-8")
        findings.extend(
            check_source(
                source,
                rel,
                allow=allow,
                datums=datums,
                params=params,
                derived=derived,
                display=path.as_posix(),
            )
        )
    return findings
