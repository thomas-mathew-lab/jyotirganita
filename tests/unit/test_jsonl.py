"""The canonical JSON writer and the derived-time conversions.

``io/jsonl.py``: keys in schema order, then unlisted keys sorted; a
``Fraction`` as ``{"exact": "n/d"}`` under ``numeric: exact`` and as its
double under ``numeric: float``; a float refused on the exact path outside
an ``x-derived`` subtree; NaN refused; one ASCII line per value. The
conversions of ``core/types.py`` that place a text's instant on UT1 are
checked against their stated definitions, with inputs chosen so that the
expected value follows from the definition alone (no value from a source
or from memory).
"""

from __future__ import annotations

import io
import json
from fractions import Fraction

import pytest

from jyotirganita.core.types import (
    JDN,
    UT1,
    FloatDays,
    Nadika,
    SiddhanticCivilInstant,
    jd_at_midnight,
    ut1_from_apparent_reckoning,
    ut1_from_text_local,
)
from jyotirganita.io import jsonl

SCHEMA = {
    "$defs": {"leaf": {"type": "object", "properties": {"b": {}, "a": {}}}},
    "type": "object",
    "properties": {
        "z": {},
        "m": {"$ref": "#/$defs/leaf"},
        "d": {"type": "object", "x-derived": True, "properties": {"v": {}}},
        "eras": {"type": "object", "patternProperties": {"^.*$": {"$ref": "#/$defs/leaf"}}},
    },
}


def test_schema_order_then_sorted_extras() -> None:
    v = {"y": 1, "m": {"a": 1, "b": 2, "c": 3}, "x": 2, "z": 0}
    assert jsonl.dumps(v, "exact", SCHEMA) == '{"z":0,"m":{"b":2,"a":1,"c":3},"x":2,"y":1}'


def test_data_keyed_objects_sorted_and_their_values_follow_the_pattern() -> None:
    v = {"eras": {"saka": {"a": 1, "b": 2}, "kollam": {"a": 3, "b": 4}}}
    out = jsonl.dumps(v, "exact", SCHEMA)
    assert out == '{"eras":{"kollam":{"b":4,"a":3},"saka":{"b":2,"a":1}}}'


def test_fraction_by_numeric_family() -> None:
    v = {"z": Fraction(-6, 4)}
    assert jsonl.dumps(v, "exact", SCHEMA) == '{"z":{"exact":"-3/2"}}'
    assert jsonl.dumps({"z": Fraction(5)}, "exact", SCHEMA) == '{"z":{"exact":"5/1"}}'
    assert jsonl.dumps(v, "float", SCHEMA) == '{"z":-1.5}'


def test_stated_writes_the_texts_form_beside_exact() -> None:
    v = {"z": jsonl.Stated(Fraction(3, 2), "nadika", (1, 30, 0), "texts.x.rule")}
    out = jsonl.dumps(v, "exact", SCHEMA)
    assert out == '{"z":{"exact":"3/2","nadika":[1,30,0],"rounding":"texts.x.rule"}}'
    assert jsonl.dumps(v, "float", SCHEMA) == '{"z":1.5}'


def test_float_refused_on_the_exact_path_except_in_a_derived_subtree() -> None:
    with pytest.raises(ValueError, match="derived"):
        jsonl.dumps({"z": 0.5}, "exact", SCHEMA)
    assert jsonl.dumps({"d": {"v": 0.5}}, "exact", SCHEMA) == '{"d":{"v":0.5}}'
    assert jsonl.dumps({"z": 0.1}, "float", SCHEMA) == '{"z":0.1}'


def test_nan_unknown_types_and_numeric_names_refused() -> None:
    with pytest.raises(ValueError):
        jsonl.dumps({"d": {"v": float("nan")}}, "exact", SCHEMA)
    with pytest.raises(TypeError):
        jsonl.dumps({"z": {1, 2}}, "exact", SCHEMA)
    with pytest.raises(ValueError, match="numeric"):
        jsonl.dumps({"z": 1}, "decimal", SCHEMA)


def test_ascii_compact_and_newline_ended() -> None:
    line = jsonl.dumps({"z": "Śaka"}, "exact", SCHEMA)
    assert line == '{"z":"\\u015aaka"}' and json.loads(line) == {"z": "Śaka"}
    buf = io.BytesIO()
    assert jsonl.write_lines([line, line], buf) == 2
    assert buf.getvalue() == (line + "\n" + line + "\n").encode("ascii")


# --- the derived-time conversions -----------------------------------------------------------


def _jd(t: UT1) -> Fraction:
    return Fraction(t.jd_whole) + Fraction(t.jd_fraction)


def test_text_local_at_greenwich_is_midnight_plus_the_nadikas() -> None:
    day = JDN(2434972)
    # a quarter day (15 nāḍikās) after local mean midnight, plus a quarter day more
    inst = SiddhanticCivilInstant(day, Nadika(15), "text_local:x")
    t = ut1_from_text_local(inst, Nadika(15), Fraction(0))
    assert _jd(t) == jd_at_midnight(day) + Fraction(1, 2)


def test_text_local_east_longitude_is_earlier_on_ut1() -> None:
    day = JDN(2434972)
    inst = SiddhanticCivilInstant(day, Nadika(0), "text_local:x")
    at_greenwich = _jd(ut1_from_text_local(inst, Nadika(0), Fraction(0)))
    east = _jd(ut1_from_text_local(inst, Nadika(0), Fraction(90)))
    assert at_greenwich - east == Fraction(1, 4)  # 90° is a quarter of the day


def test_apparent_reckoning_subtracts_the_equation_of_time() -> None:
    t = UT1(2434972, 0.25)
    out = ut1_from_apparent_reckoning(t, FloatDays(0.125))
    assert (out.jd_whole, out.jd_fraction) == (2434972, 0.125)
    with pytest.raises(TypeError):
        ut1_from_apparent_reckoning(t, 0.125)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ut1_from_text_local(t, Nadika(0), Fraction(0))  # type: ignore[arg-type]
