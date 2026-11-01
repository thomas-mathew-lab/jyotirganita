"""The registry field ``replaces``.

Each refusal, refused by name: in the registry loader
(``replaces`` without a base; a base with neither a layer nor a replaced
datum; a datum replaced twice, or a replacement itself replaced; a key
outside the base's text; a base that is itself based) and against the
data in :func:`~jyotirganita.methods.compose.load_method` (a key that is
not a datum, a gap, a different unit or form, a datum the model does not
read). The registry entries here are planted beside the real
``suryasiddhanta`` entry; the data are the repository's.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

from jyotirganita.data.datum import Records, context_for, load_records
from jyotirganita.methods import compose
from jyotirganita.methods.compose import REPO, load_method
from jyotirganita.methods.registry import Method, RegistryError, load_registry
from jyotirganita.siddhantic.engine import EngineRefusal

REGISTRY = REPO / "jyotirganita" / "methods" / "registry.yaml"
NEW = "suryasiddhanta_paramesvara_recension"
APOGEE = "texts.suryasiddhanta.moon_apogee.revolutions"
NODE = "texts.suryasiddhanta.moon_node.revolutions"
suryasiddhanta_paramesvara_1957_APOGEE = (
    "texts.suryasiddhanta.witness.suryasiddhanta_paramesvara_1957.moon_apogee.revolutions"
)
suryasiddhanta_paramesvara_1957_NODE = (
    "texts.suryasiddhanta.witness.suryasiddhanta_paramesvara_1957.moon_node.revolutions"
)


@cache
def _real() -> dict[str, dict[str, Any]]:
    doc = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return {m["id"]: m for m in doc["methods"]}


@cache
def records() -> Records:
    return load_records(REPO, context_for(REPO))


def _entry(**over: Any) -> dict[str, Any]:
    e = dict(_real()[NEW])
    e.update(over)
    return {k: v for k, v in e.items() if v is not None}


def _write(tmp_path: Path, *entries: Mapping[str, Any]) -> Path:
    p = tmp_path / "registry.yaml"
    doc = {"methods": [_real()["suryasiddhanta"], *entries]}
    p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


def _load(path: Path) -> dict[str, Method]:
    return load_registry(path, context_for(REPO).sources)


# --- the registry loader --------------------------------------------------------------


def test_the_registered_entry_loads_with_its_two_replacements() -> None:
    m = _load(REGISTRY)[NEW]
    assert m.base == "suryasiddhanta" and m.text == "suryasiddhanta" and m.layers == ()
    assert dict(m.replaces) == {
        APOGEE: suryasiddhanta_paramesvara_1957_APOGEE,
        NODE: suryasiddhanta_paramesvara_1957_NODE,
    }


def test_replaces_without_a_base_is_refused(tmp_path: Path) -> None:
    bad = _entry(base=None, layers=None, text="suryasiddhanta")
    with pytest.raises(RegistryError, match="a method with text replaces nothing"):
        _load(_write(tmp_path, bad))


def test_a_base_with_neither_a_layer_nor_a_replacement_is_refused(tmp_path: Path) -> None:
    bad = _entry()
    del bad["replaces"]
    with pytest.raises(RegistryError, match="with neither it is its base"):
        _load(_write(tmp_path, bad))


def test_a_shared_replacement_is_refused(tmp_path: Path) -> None:
    bad = _entry(
        replaces={
            APOGEE: suryasiddhanta_paramesvara_1957_APOGEE,
            NODE: suryasiddhanta_paramesvara_1957_APOGEE,
        }
    )
    with pytest.raises(RegistryError, match="each datum to its own replacement"):
        _load(_write(tmp_path, bad))


def test_a_replacement_that_is_itself_replaced_is_refused(tmp_path: Path) -> None:
    bad = _entry(replaces={APOGEE: NODE, NODE: suryasiddhanta_paramesvara_1957_NODE})
    with pytest.raises(RegistryError, match="no replacement is itself replaced"):
        _load(_write(tmp_path, bad))


def test_a_key_outside_the_base_s_text_is_refused(tmp_path: Path) -> None:
    bad = _entry(replaces={APOGEE: "texts.aryabhatiya.moon_apogee.revolutions"})
    with pytest.raises(RegistryError, match="both are data of the base's text suryasiddhanta"):
        _load(_write(tmp_path, bad))


def test_a_base_that_is_itself_based_is_refused(tmp_path: Path) -> None:
    second = _entry(id="second_recension", base=NEW)
    with pytest.raises(RegistryError, match=f"base {NEW} is itself based"):
        _load(_write(tmp_path, _entry(), second))


# --- against the data ----------------------------------------------------------------


def _compose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replaces: Mapping[str, str]
) -> compose.ResolvedMethod:
    path = _write(tmp_path, _entry(replaces=dict(replaces)))
    monkeypatch.setattr(compose, "load_registry", lambda _p, sources: load_registry(path, sources))
    return load_method(NEW, REPO, records=records())


def test_a_key_that_is_not_a_datum_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = "texts.suryasiddhanta.moon_apogee.no_such_datum"
    with pytest.raises(EngineRefusal, match=f"replaces names {missing}, which is not a datum"):
        _compose(tmp_path, monkeypatch, {missing: suryasiddhanta_paramesvara_1957_APOGEE})


def test_a_gap_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gap = "texts.suryasiddhanta.composed.recension.suryasiddhanta_paramesvara_1957"
    with pytest.raises(EngineRefusal, match=f"replaces names {gap}, which is a gap"):
        _compose(tmp_path, monkeypatch, {APOGEE: gap})


def test_a_different_unit_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    other = "texts.suryasiddhanta.kalpa.multiplier"
    with pytest.raises(EngineRefusal, match=f"replaces {APOGEE} by {other}: unit"):
        _compose(tmp_path, monkeypatch, {APOGEE: other})


def test_a_different_form_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # a statement (form text) in place of a number
    statement = (
        "texts.suryasiddhanta.witness.suryasiddhanta_paramesvara_1957.epoch.krta_end.planets.i57a"
    )
    rec = records().data[statement]
    assert rec.form == "text"
    with pytest.raises(EngineRefusal, match=f"replaces {APOGEE} by {statement}: (unit|form)"):
        _compose(tmp_path, monkeypatch, {APOGEE: statement})


def test_a_datum_the_model_does_not_read_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # two of Shukla's Introduction figures: the same unit and form, read by no model
    a = (
        "texts.suryasiddhanta.witness.suryasiddhanta_paramesvara_1957.intro.p16.mallikarjuna."
        "moon_apogee.revolutions"
    )
    b = (
        "texts.suryasiddhanta.witness.suryasiddhanta_paramesvara_1957.intro.p16.paramesvara."
        "moon_apogee.revolutions"
    )
    with pytest.raises(EngineRefusal, match=f"replaces names {a}, which the model does not read"):
        _compose(tmp_path, monkeypatch, {a: b})


def test_the_composed_method_reads_the_replacements_and_says_so() -> None:
    r = load_method(NEW, REPO, records=records())
    base = load_method("suryasiddhanta", REPO, records=records())
    assert set(r.data.used) ^ set(base.data.used) == {
        APOGEE,
        NODE,
        suryasiddhanta_paramesvara_1957_APOGEE,
        suryasiddhanta_paramesvara_1957_NODE,
    }
    assert r.procedures.keys() == base.procedures.keys()
    assert all(r.procedures[s].key == base.procedures[s].key for s in base.procedures)
    assert r.runs_from == base.runs_from
