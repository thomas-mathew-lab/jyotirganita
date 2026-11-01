"""Exact YAML loading for the data files.

PyYAML reads ``0.0057183`` as a binary float, which is not the printed value.
Every data file of this package is read through :func:`load_exact`, whose
loader keeps each YAML float scalar as a :class:`PrintedNumber` (the scalar's
text, a ``str``) so that it can be parsed exactly with
:func:`jyotirganita.core.exact.parse_fraction`. Integers stay ``int``.

Only ``true`` and ``false`` are booleans (YAML 1.2): YAML 1.1 would read
the datum field ``on`` as ``True``. Dates are not resolved: ``on:
2026-10-02`` stays the string it is, so a datum loads the same in every
time zone and validates against its JSON Schema as text.

:func:`dump_canonical` writes the canonical form of a data file: keys in
the order given, block style for mappings and flow style for lists of
scalars,
Unicode as is, no line folding, no anchors or aliases, each ``PrintedNumber``
as its own text. A
datum file kept in that form survives a load and a rewrite unchanged
(a reader's entry is added to a datum file that way), which
is why datum files carry no YAML comments (``docs/data.md``).

Each file loaded from ``jyotirganita/data/`` is noted with
:func:`jyotirganita.provenance.loads.note_loaded`, which is how the test
plugin learns which data files a test tier loaded.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

from jyotirganita.provenance.loads import note_loaded

__all__ = ["PrintedNumber", "dump_canonical", "load_exact", "loads_exact"]

_TIMESTAMP = "tag:yaml.org,2002:timestamp"
_BOOL = "tag:yaml.org,2002:bool"
# YAML 1.2 booleans only: YAML 1.1 reads the datum field "on" (and yes, no,
# off) as a boolean
_BOOL_RX = re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$")


def _resolvers() -> dict[str, list[tuple[str, re.Pattern[str]]]]:
    out: dict[str, list[tuple[str, re.Pattern[str]]]] = {}
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items():
        kept = [
            (tag, _BOOL_RX if tag == _BOOL else rx)
            for tag, rx in resolvers
            if tag != _TIMESTAMP and (tag != _BOOL or first in "tTfF")
        ]
        if kept:
            out[first] = kept
    return out


_RESOLVERS = _resolvers()


class PrintedNumber(str):
    """The text of a YAML float scalar, kept exact (parse with ``parse_fraction``)."""

    __slots__ = ()


class _ExactLoader(yaml.SafeLoader):
    """SafeLoader that keeps floats as their printed text and dates as text."""

    yaml_implicit_resolvers = _RESOLVERS

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        """A mapping; a key given twice is refused (SafeLoader kept the last silently)."""
        seen: set[Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise ValueError(f"{key_node.start_mark}: the key {key!r} is given twice")
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


class _CanonicalDumper(yaml.SafeDumper):
    """SafeDumper with the loader's resolution rules (no timestamps)."""

    yaml_implicit_resolvers = _RESOLVERS

    def ignore_aliases(self, data: Any) -> bool:
        """No anchors: a shared object is written out at each use."""
        return True


def _represent_printed(dumper: yaml.SafeDumper, data: PrintedNumber) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:float", str(data))


def _represent_str(dumper: yaml.SafeDumper, data: str) -> yaml.Node:
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


def _represent_dict(dumper: yaml.SafeDumper, data: dict[Any, Any]) -> yaml.Node:
    return dumper.represent_mapping("tag:yaml.org,2002:map", data, flow_style=False)


def _represent_list(dumper: yaml.SafeDumper, data: list[Any]) -> yaml.Node:
    leaf = all(not isinstance(v, dict | list) for v in data)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=leaf)


_CanonicalDumper.add_representer(PrintedNumber, _represent_printed)
_CanonicalDumper.add_representer(str, _represent_str)
_CanonicalDumper.add_representer(dict, _represent_dict)
_CanonicalDumper.add_representer(list, _represent_list)


# YAML 1.1 also reads 010 as 8, 0x10 as 16 and 1:30 as 90 (sexagesimal); a datum's
# number is decimal as printed
_DECIMAL_INT = re.compile(r"^[-+]?(?:0|[1-9][0-9]*)$")
_DECIMAL_FLOAT = re.compile(r"^[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?$")


def _construct_int(loader: yaml.SafeLoader, node: yaml.Node) -> int:
    assert isinstance(node, yaml.ScalarNode)
    text = str(loader.construct_scalar(node))
    if not _DECIMAL_INT.match(text):
        raise ValueError(f"{node.start_mark}: {text!r} is not a decimal integer")
    return int(text)


def _construct_float(loader: yaml.SafeLoader, node: yaml.Node) -> PrintedNumber:
    assert isinstance(node, yaml.ScalarNode)
    text = str(loader.construct_scalar(node))
    if text.lower().lstrip("+-") in {".inf", ".nan"}:
        raise ValueError(f"{node.start_mark}: infinity and NaN are not data")
    if not _DECIMAL_FLOAT.match(text):
        raise ValueError(f"{node.start_mark}: {text!r} is not a decimal number")
    return PrintedNumber(text)


_ExactLoader.add_constructor("tag:yaml.org,2002:int", _construct_int)
_ExactLoader.add_constructor("tag:yaml.org,2002:float", _construct_float)


def loads_exact(text: str) -> Any:
    """Load YAML text with floats and dates kept as text (no load is noted)."""
    return yaml.load(text, Loader=_ExactLoader)


def dump_canonical(data: Any) -> str:
    """The canonical text of ``data`` (see the module docstring)."""
    return yaml.dump(
        data,
        Dumper=_CanonicalDumper,
        sort_keys=False,
        allow_unicode=True,
        width=sys.maxsize,
    )


def load_exact(path: Path) -> Any:
    """Load ``path`` with floats kept exact; note the load for provenance."""
    note_loaded(path)
    with path.open("rb") as fh:
        return yaml.load(fh, Loader=_ExactLoader)
