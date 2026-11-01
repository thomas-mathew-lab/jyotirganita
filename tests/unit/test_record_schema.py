"""The day record's schema test.

One record per preset of the table the CI tier serves (at the observer
and month rule of its regression file), plus one under an intraday
override, one under a procedure override (the geometric sunrise), one
with the derived fields under each equation-of-time source, one on a day
before the composition date and the ``text_only`` presets
(``record_kit.schema_cases``). Each canonical line is validated against
``io/record.schema.json``, and against the schema with ``$defs/q``
narrowed to the record's own ``numeric`` representation, so that a float
leaking into the exact path fails by the schema as well as by the writer
(``io/jsonl.py`` refuses it). Every leaf the schema lists is exercised by
at least one record; every sentinel stands only on the leaves the schema
gives it, and each appears on at least one; the keys are in schema order.
The engine's output is evidence for nothing here:
the test checks the record's form, not its values.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Iterator, Mapping
from fractions import Fraction
from typing import Any

import jsonschema
import pytest
from record_kit import CI_PRESETS, config, day_of, line, parsed_cases, schema_cases

from jyotirganita.io.record import record_schema

SENTINELS: Mapping[str, tuple[str, ...]] = {
    "not_modelled": (
        r"^sunrise$",
        r"^sunset$",
        r"^planets\.[a-z]+$",
        r"^planets\.[a-z]+\.(latitude|daily_motion|retrograde)$",
    ),
    "not_in_preset": (
        r"^weekday\.name$",
        r"^(nakshatra|yoga|karana)\[\]\.name$",
        r"^tithi\[\]\.name(\.name)?$",
        r"^masa\.(name|day)$",
        r"^sankranti\.assigned_day1$",
        r"^.*\.forms\.\*$",
    ),
    "not_in_range": (r"^eras\.\*$",),
}
#: objects keyed by data, whose keys a path writes as ``*``
KEYED = ("eras", "forms")


def _narrowed(numeric: str) -> dict[str, Any]:
    s = copy.deepcopy(dict(record_schema()))
    s["$defs"]["q"] = {"$ref": "#/$defs/exact"} if numeric == "exact" else {"type": "number"}
    return s


def _schema_leaves(node: Any, defs: Mapping[str, Any], path: str, out: set[str]) -> None:
    if not isinstance(node, Mapping):
        return
    if "$ref" in node:
        name = str(node["$ref"]).rpartition("/")[2]
        if name not in ("q", "exact"):  # an exact-or-float value is one leaf
            _schema_leaves(defs[name], defs, path, out)
        return
    for key in ("anyOf", "oneOf"):
        for option in node.get(key, ()):
            _schema_leaves(option, defs, path, out)
    for k, sub in (node.get("properties") or {}).items():
        p = f"{path}.{k}" if path else k
        if p.startswith("provenance."):
            continue
        out.add(p)
        _schema_leaves(sub, defs, p, out)
    for sub in (node.get("patternProperties") or {}).values():
        p = f"{path}.*"
        out.add(p)
        _schema_leaves(sub, defs, p, out)
    if "items" in node:
        _schema_leaves(node["items"], defs, f"{path}[]", out)


def schema_leaves() -> set[str]:
    out: set[str] = set()
    s = record_schema()
    _schema_leaves(s, s["$defs"], "", out)
    return out


def _walk(v: Any, path: str) -> Iterator[tuple[str, Any]]:
    yield path, v
    if path == "provenance":
        return
    if isinstance(v, Mapping) and set(v) != {"exact"}:
        keyed = path.rpartition(".")[2] in KEYED or path in KEYED
        for k, x in v.items():
            name = "*" if keyed else k
            yield from _walk(x, f"{path}.{name}" if path else name)
    elif isinstance(v, list):
        for x in v:
            yield from _walk(x, f"{path}[]")


@pytest.mark.parametrize("case", [c for c, _ in schema_cases()])
def test_each_record_validates(case: str) -> None:
    doc = dict(parsed_cases())[case]
    jsonschema.Draft202012Validator(record_schema()).validate(doc)
    jsonschema.Draft202012Validator(_narrowed(doc["numeric"])).validate(doc)


#: the leaves of ``apparent:modern:``, which no shipped method serves: the Āryabhaṭīya and the
#: Parahita apply the text's bhujāntara (the modern equation is refused there), the others serve
#: only text_units places; named so that a method serving it fails this test
UNSERVED = (
    "derived_ut.equation_of_time.apparent_minus_mean_days",
    "derived_ut.equation_of_time.argument_delta_t_seconds",
)


def test_every_leaf_is_exercised() -> None:
    seen = {p for _, doc in parsed_cases() for p, _ in _walk(doc, "")}
    missing = sorted(schema_leaves() - seen)
    assert missing == list(UNSERVED)


def test_sentinels_stand_where_they_belong_and_each_appears() -> None:
    found: dict[str, set[str]] = {s: set() for s in SENTINELS}
    wrong: list[str] = []
    for case, doc in parsed_cases():
        for path, v in _walk(doc, ""):
            if isinstance(v, str) and v in SENTINELS:
                found[v].add(path)
                if not any(re.match(rx, path) for rx in SENTINELS[v]):
                    wrong.append(f"{case}: {v} at {path}")
            if v is None and path not in ("sankranti", "sankranti.assigned_day1"):
                ok = re.match(r"^(tithi|nakshatra|yoga|karana)\[\]\.(start|end)$", path) or (
                    path.startswith("derived_ut.")
                )
                if not ok:
                    wrong.append(f"{case}: null at {path}")
    assert wrong == []
    assert all(found[s] for s in SENTINELS), {s: sorted(p) for s, p in found.items()}


def test_no_float_on_the_exact_path() -> None:
    for case, text in schema_cases():
        doc = json.loads(text)
        if doc["numeric"] != "exact":
            continue
        for path, v in _walk(doc, ""):
            if isinstance(v, float):
                assert path.startswith(("derived_ut.", "derived_tt.")), f"{case}: {path}"


def test_keys_are_in_schema_order() -> None:
    order = list(record_schema()["properties"])
    for case, doc in parsed_cases():
        keys = list(doc)
        assert keys == [k for k in order if k in doc], case
        planets = list(doc["planets"])
        assert planets == list(record_schema()["properties"]["planets"]["properties"]), case
        assert keys[-2:] == ["flags", "provenance"] and doc["flags"] == sorted(doc["flags"])


def test_the_cases_cover_the_named_flags() -> None:
    docs = dict(parsed_cases())
    assert "diagnostic:diagnostic.full_evaluation" in docs["intraday"]["flags"]
    assert "diagnostic:sunrise.modern_geometric" in docs["procedure"]["flags"]
    # the hybrid's sunset is the modern engine's
    assert "nadika_after_local_midnight" in docs["procedure"]["sunset"]
    assert any(f.startswith("before_composition:") for f in docs["before_composition"]["flags"])
    assert any(v == "not_in_range" for v in docs["before_composition"]["eras"].values())
    for case in ("derived_mean", "derived_bhujantara"):
        assert "provisional:derived_ut.time_reckoning" in docs[case]["flags"]
    text_only = [d for c, d in docs.items() if c.startswith("aryabhatiya_text@")]
    assert text_only and all(d["conventions"] == "text_only" for d in text_only)


# --- the text's own form beside exact -------------------------------------

ENDING_ROUNDING = "rounding.ending_truncate_at_asu"
ROW_KEYS = ("start", "end", "ends_nadika_after_sunrise")


def _units(method_cfg: Any) -> tuple[int, int] | None:
    rm = method_cfg.run.resolved
    rec = rm.procedures.get("ending_rounding")
    if rec is None or rec.raw.get("procedure") != ENDING_ROUNDING:
        return None
    return (
        rm.data.integer("time_units.vinadikas_per_nadi"),
        rm.data.integer("time_units.pranas_per_vinadika"),
    )


@pytest.mark.parametrize("preset", CI_PRESETS)
def test_the_texts_form_stands_where_the_text_states_its_rounding(preset: str) -> None:
    cfg = config(preset)
    doc = json.loads(line(cfg, day_of(cfg)))
    units = _units(cfg) if cfg.kind == "siddhantic" else None
    stated = 0
    for path, v in _walk(doc, ""):
        if not (isinstance(v, Mapping) and "exact" in v):
            continue
        is_row = re.match(
            r"^(tithi|nakshatra|yoga|karana)\[\]\.(start|end|ends_nadika_after_sunrise)$", path
        )
        if units is None or not is_row:
            assert set(v) == {"exact"}, f"{preset}: {path} carries a form no rule states"
            continue
        assert set(v) == {"exact", "nadika", "rounding"}, path
        rec = cfg.run.resolved.procedures["ending_rounding"]
        assert v["rounding"] == rec.key
        vpn, ppv = units
        g, vi, a = v["nadika"]
        x = Fraction(v["exact"])
        printed = g + Fraction(vi, vpn) + Fraction(a, vpn * ppv)
        # truncation: the printed form is at most one asu below the exact value, never above
        assert 0 <= x - printed < Fraction(1, vpn * ppv), path
        assert 0 <= vi < vpn and 0 <= a < ppv
        stated += 1
    assert (stated > 0) == (units is not None), preset
