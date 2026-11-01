"""The perturbation of one datum for data mutation coverage.

The rule, by the datum's form (for a numeral-word, by its ``value_form``),
applied to the value the loader adopts (``emendation.adopted`` where the
datum carries an emendation, ``value`` otherwise) and parsed again by the
loader's own parser, so that the sign (``negative``) is applied as it is
on load:

- ``integer``: one unit added;
- ``fraction``: one unit in the last printed place added (an integer by
  one, a ratio ``n/d`` by ``1/d``, a decimal by one unit of its last
  decimal place, written with the same places and minus sign);
- ``sexagesimal`` and ``rdms``: the last component by one unit, added, or
  subtracted where adding would leave the part's range (a part of 59, a
  degree of 29);
- ``table``: the table as a whole, one datum: every numeric entry shifted
  by the rules above (an integer cell, a list of parts on its last
  component, a printed number on its last place), the label columns
  (``LABEL_COLUMNS``) and printed text cells unchanged; a table with no
  numeric entry is outside the measurement;
- ``text`` and ``status: gap``: outside the measurement (listed on their
  own line, never as undetected).

The perturbation lives here and in the test harness only (``--mutate`` in
``tests/conftest.py``); nothing
under ``jyotirganita/`` can be perturbed by any switch. :func:`install`
patches :class:`~jyotirganita.data.datum.Record` construction in the test
process, so that every loader path (``load_records``, ``load_datum_file``
and the era and time-standard loaders that call it) hands out the
perturbed record: its parsed ``value`` and a copy of its ``raw`` whose
adopted printed value is the perturbed one (readers of ``raw``, the era
loader among them, see the same perturbation). The validation of the
file runs on the printed file before the patch applies.

**The read probe.** :func:`install_probe` records, in an unperturbed test
process, which data the process reads after loading: a record's ``value``
attribute, or its ``raw`` mapping's ``value`` or ``emendation`` entry, or
the whole mapping (iteration, ``items``, ``values``, a copy), counted
conservatively as a read of the value. The tool runs each suite file in a
process of its own under the probe (module caches never cross a file), and
runs a datum's mutation over the files that read it. A run is
deterministic, so a file that never reads a value passes perturbed exactly
as it passes unperturbed: a datum that no suite of its methods reads is
recorded ``undetected`` with ``read: false``, without a run.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from jyotirganita.core.exact import parse_fraction
from jyotirganita.data import datum as datum_module
from jyotirganita.data.datum import DatumError, Record

__all__ = [
    "LABEL_COLUMNS",
    "OUTSIDE",
    "install",
    "install_probe",
    "perturb",
    "perturbed_printed",
]

#: table columns that label a row rather than tabulate a value
LABEL_COLUMNS = frozenset({"serial", "power"})
#: why a record is outside the measurement, by kind or form
OUTSIDE = {"gap": "status: gap", "text": "form: text", "no_numeric_entry": "a table of no number"}

_DECIMAL = re.compile(r"^([+\-−]?)(\d*)\.(\d+)$")
_RATIO = re.compile(r"^([+\-−]?)(\d+)/(\d+)$")
_INT = re.compile(r"^([+\-−]?)(\d+)$")


def _shift_number_text(s: str) -> str | None:
    """A printed number one unit up in its last place, written as printed; None if not one."""
    t = s.strip()
    try:
        parse_fraction(t)
    except (TypeError, ValueError):
        return None
    m = _DECIMAL.match(t)
    if m:
        sign, whole, frac = m.groups()
        places = len(frac)
        unit = 10**places
        n = int((whole or "0") + frac) * (-1 if sign in ("-", "−") else 1) + 1
        minus = "−" if "−" in sign else "-"
        a = abs(n)
        body = f"{a // unit}.{a % unit:0{places}d}"
        if not whole and a // unit == 0:
            body = body[1:]  # printed without a leading zero
        return (minus if n < 0 else ("+" if sign == "+" else "")) + body
    m = _RATIO.match(t)
    if m:
        sign, num, den = m.groups()
        n = int(num) * (-1 if sign in ("-", "−") else 1) + 1
        minus = "−" if "−" in sign else "-"
        return (minus if n < 0 else ("+" if sign == "+" else "")) + f"{abs(n)}/{den}"
    m = _INT.match(t)
    if m:
        sign, num = m.groups()
        n = int(num) * (-1 if sign in ("-", "−") else 1) + 1
        minus = "−" if "−" in sign else "-"
        return (minus if n < 0 else ("+" if sign == "+" else "")) + str(abs(n))
    return None


def _shift_parts(parts: list[int], form: str) -> list[int]:
    """The last component by one unit, up, or down where up leaves the part's range."""
    out = list(parts)
    i = len(out) - 1
    if i == 0:
        out[0] += 1
        return out
    limit = 30 if (form == "rdms" and i == 1) else 60  # a degree below 30, a part below 60
    out[i] = out[i] + 1 if out[i] + 1 < limit else out[i] - 1
    return out


def _is_parts(x: object) -> bool:
    return isinstance(x, list) and bool(x) and all(type(p) is int for p in x)


def perturbed_printed(form: str, printed: object, columns: list[str] | None) -> object | None:
    """The perturbed printed value of ``form``, or None when nothing numeric is in it."""
    if form == "integer" and type(printed) is int:
        return printed + 1
    if form == "fraction":
        if type(printed) is int:
            return printed + 1
        return _shift_number_text(str(printed))
    if form in ("sexagesimal", "rdms") and _is_parts(printed):
        assert isinstance(printed, list)
        return _shift_parts(printed, form)
    if form == "table" and isinstance(printed, list) and columns is not None:
        changed = False
        rows: list[list[object]] = []
        for row in printed:
            new_row: list[object] = []
            for col, cell in zip(columns, row, strict=True):
                new: object = cell
                if col not in LABEL_COLUMNS:
                    if type(cell) is int:
                        new = cell + 1
                    elif _is_parts(cell):
                        assert isinstance(cell, list)
                        new = _shift_parts(cell, "sexagesimal")
                    elif isinstance(cell, str):
                        shifted = _shift_number_text(cell)
                        new = cell if shifted is None else shifted
                changed = changed or new != cell
                new_row.append(new)
            rows.append(new_row)
        return rows if changed else None
    return None


def perturb(rec: Record) -> tuple[object, Mapping[str, Any]] | str:
    """The perturbed (value, raw) of a datum, or the reason it is outside the measurement."""
    if rec.kind == "gap":
        return OUTSIDE["gap"]
    raw = rec.raw
    form = str(raw.get("value_form", raw["form"]))
    if form == "text":
        return OUTSIDE["text"]
    em = raw.get("emendation")
    adopted = em["adopted"] if em is not None else raw["value"]
    new = perturbed_printed(form, adopted, raw.get("columns"))
    if new is None:
        return OUTSIDE["no_numeric_entry"] if form == "table" else f"form {form}: not perturbable"

    def fail(msg: str) -> None:
        raise DatumError(f"{rec.key}: the perturbed value does not parse: {msg}")

    value = datum_module._parse(form, new, bool(raw.get("negative")), fail)
    new_raw = dict(raw)
    if em is not None:
        new_raw["emendation"] = {**em, "adopted": new}
    else:
        new_raw["value"] = new
    return value, new_raw


class _Patch:
    """The installed perturbation: the key, and how often its record was built."""

    def __init__(self, key: str) -> None:
        self.key = key
        self.built = 0
        self.outside: str | None = None
        self._made: list[Mapping[str, Any]] = []  # kept alive so their ids stay unique


def install(key: str) -> _Patch:
    """Perturb the datum ``key`` wherever a record of it is built in this process."""
    patch = _Patch(key)
    original = Record.__init__

    def init(self: Record, *args: Any, **kwargs: Any) -> None:
        original(self, *args, **kwargs)
        if self.key != key or self.kind not in ("datum", "gap"):
            return
        if any(self.raw is m for m in patch._made):
            return  # already the perturbed record (a copy made with dataclasses.replace)
        out = perturb(self)
        if isinstance(out, str):
            patch.outside = out
            return
        value, raw = out
        patch._made.append(raw)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "raw", raw)
        patch.built += 1

    Record.__init__ = init  # type: ignore[method-assign]
    return patch


# --- the read probe -------------------------------------------------------------------------

_VALUE_KEYS = frozenset({"value", "emendation"})


class _Probe:
    """The keys whose value this process has read since loading."""

    def __init__(self) -> None:
        self.read: set[str] = set()


class _TrackedRaw(dict[str, Any]):
    """A record's ``raw`` that notes a read of its value (or of the whole mapping)."""

    __slots__ = ("_key", "_probe")
    _key: str
    _probe: _Probe

    def _note(self) -> None:
        self._probe.read.add(self._key)

    def __getitem__(self, k: str) -> Any:
        if k in _VALUE_KEYS:
            self._note()
        return super().__getitem__(k)

    def get(self, k: str, default: Any = None) -> Any:
        if k in _VALUE_KEYS:
            self._note()
        return super().get(k, default)

    def __iter__(self) -> Any:
        self._note()
        return super().__iter__()

    def items(self) -> Any:
        self._note()
        return super().items()

    def values(self) -> Any:
        self._note()
        return super().values()

    def copy(self) -> dict[str, Any]:
        self._note()
        return dict(super().items())


def install_probe() -> _Probe:
    """Note every datum whose value this process reads after its record is built."""
    probe = _Probe()
    original = Record.__init__
    value_slot = Record.__dict__["value"]  # the slot's member descriptor

    class _Tracked(Record):
        __slots__ = ()

        @property
        def value(self) -> object:
            probe.read.add(self.key)
            return value_slot.__get__(self, Record)

        @value.setter
        def value(self, v: object) -> None:  # the dataclass __init__ of a copy (replace)
            value_slot.__set__(self, v)

    def init(self: Record, *args: Any, **kwargs: Any) -> None:
        original(self, *args, **kwargs)
        if self.kind not in ("datum", "gap") or isinstance(self.raw, _TrackedRaw):
            return
        raw = _TrackedRaw(dict.items(self.raw) if isinstance(self.raw, dict) else self.raw)
        raw._key = self.key
        raw._probe = probe
        object.__setattr__(self, "raw", raw)
        object.__setattr__(self, "__class__", _Tracked)

    Record.__init__ = init  # type: ignore[method-assign]
    return probe
