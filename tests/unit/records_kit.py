"""Planted sample repositories for the loader's unit tests.

Every value here is a planted test value, not a reading of any source:
the sources are invented ids with invented hashes, and the datum values
are arbitrary. A sample repository has its own ``sources.yaml``,
``ISSUES.md`` and ``DECISIONS.md``, so the tests do not depend on the
committed registry.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from jyotirganita.data.datum import signed_hash
from jyotirganita.data.yamlio import dump_canonical

OPUS = "claude-opus-5-5/2026-10-02-t1"
OPUS_2 = "claude-opus-5-5/2026-10-03-t2"
FABLE = "claude-fable-5-1/2026-10-03-t3"
FABLE_2 = "claude-fable-5-1/2026-10-04-t4"


def _file(path: str, sha: str, pages: int, born_digital: bool) -> dict[str, Any]:
    return {
        "path": path,
        "sha256": sha * 64,
        "bytes": 1000,
        "born_digital": born_digital,
        "inspection": "planted",
        "pages": pages,
    }


def _lib(
    files: list[dict[str, Any]], *, basis: str = "durable", held: bool = True
) -> dict[str, Any]:
    e: dict[str, Any] = {
        "kind": "library",
        "title": "planted",
        "author": "planted",
        "edition": "planted",
        "year": 1900,
        "copyright": "public-domain",
        "held": held,
        "verified_basis": basis,
        "verified_basis_note": "planted",
        "files": files,
        "born_digital": all(f["born_digital"] for f in files) if files else None,
    }
    if not held:
        e["gap"] = "planted: not held"
    return e


SOURCES: dict[str, Any] = {
    "aryabhatiya_1976": _lib([_file("aryabhatiya_1976.pdf", "1", 300, False)]),
    "grahacaranibandhana_1954": _lib([_file("grahacaranibandhana_1954.pdf", "2", 50, True)]),
    "drgganita_1963": _lib(
        [
            _file("drgganita_1963-v1.pdf", "3", 100, False),
            _file("drgganita_1963-v2.pdf", "4", 80, False),
        ]
    ),
    "vakyakarana_1962": _lib(
        [_file("vakyakarana_1962.pdf", "5", 100, False)], basis="scan_pending"
    ),
    "venvaroha_1956": _lib([], held=False),
    "tantrasangraha_2011": _lib(
        [_file("tantrasangraha_2011.pdf", "6", 600, True)], basis="excluded"
    ),
}

ISSUES = "# Issues\n\n| id | finding |\n|---|---|\n| I-901 | planted |\n| I-902 | planted |\n"
DECISIONS = "# Decisions\n\n| id | decision |\n|---|---|\n| D-901 | planted |\n"


def read(by: str = OPUS, **over: Any) -> dict[str, Any]:
    r: dict[str, Any] = {
        "by": by,
        "on": "2026-10-02",
        "dpi": 600,
        "clip": [0, 0, 216, 144],
        "delivered_ppi": 600,
        "note": "",
    }
    r.update(over)
    return r


def datum(key: str = "texts.sample.revolutions", **over: Any) -> dict[str, Any]:
    """A planted double-read Latin integer datum; ``over`` replaces fields."""
    d: dict[str, Any] = {
        "key": key,
        "value": 4320000,
        "form": "integer",
        "unit": "revolutions_per_mahayuga",
        "script": "latin",
        "source": "aryabhatiya_1976",
        "edition_page": 6,
        "pdf_page": 34,
        "locus": "planted locus",
        "read": [read()],
        "second_read": [read(OPUS_2)],
        "status": "double_read",
        "verified_by": [],
        "emendation": None,
        "notes": "",
    }
    for k, v in over.items():
        if v is DROP:
            d.pop(k, None)
        else:
            d[k] = v
    return d


DROP = object()


def numeral_word(key: str = "texts.sample.word", **over: Any) -> dict[str, Any]:
    """A planted numeral-word datum, cross-model double read, decodes agreeing."""
    base = datum(
        key,
        form="numeral_word",
        value_form="integer",
        value=1577917500,
        word={
            "text": "planted-word",
            "script": "devanagari",
            "system": "katapayadi",
            "decode": 1577917500,
        },
        second_read=[read(FABLE)],
    )
    base.update(over)
    return base


def signoff(d: dict[str, Any], scope: str = "batch", ref: str = "D-901") -> dict[str, Any]:
    return {
        "on": "2026-10-05",
        "by": "owner",
        "ref": ref,
        "scope": scope,
        "signed_hash": signed_hash(d),
        "note": "",
    }


def fixture(fid: str = "authority/sample/ex_one", **over: Any) -> dict[str, Any]:
    f: dict[str, Any] = {
        "id": fid,
        "methods": ["sample"],
        "class": "text_computed",
        "source": "aryabhatiya_1976",
        "edition_page": 12,
        "pdf_page": 40,
        "locus": "planted example",
        "rounding": "planted: truncate to kalā",
        "precision": None,
        "datum_keys": [],
        "notes": "",
        "values": [
            {
                "name": "input.days",
                "role": "input",
                "value": 1000,
                "form": "integer",
                "unit": "days",
                "script": "latin",
                "read": [read()],
                "second_read": [read(OPUS_2)],
                "status": "double_read",
            },
            {
                "name": "output.longitude",
                "role": "output",
                "value": [3, 12, 7],
                "form": "rdms",
                "unit": "rdms",
                "script": "latin",
                "read": [read()],
                "second_read": [read(OPUS_2)],
                "status": "double_read",
            },
        ],
    }
    f.update(over)
    return f


class Sample:
    """A planted repository tree under ``root``."""

    def __init__(self, root: Path) -> None:
        self.root = root
        data = root / "jyotirganita" / "data"
        data.mkdir(parents=True)
        (data / "sources.yaml").write_text(
            dump_canonical({"sources": copy.deepcopy(SOURCES)}), encoding="utf-8"
        )
        (root / "ISSUES.md").write_text(ISSUES, encoding="utf-8")
        (root / "DECISIONS.md").write_text(DECISIONS, encoding="utf-8")

    def write(self, rel: str, doc: object) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump_canonical(doc), encoding="utf-8")
        return path

    def data(self, items: list[dict[str, Any]], rel: str = "texts/sample/elements.yaml") -> Path:
        return self.write(f"jyotirganita/data/{rel}", items)

    def fixture(self, doc: dict[str, Any]) -> Path:
        return self.write(f"tests/{doc['id']}.yaml", doc)
