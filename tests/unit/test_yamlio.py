"""Exact YAML loading and the canonical writer (jyotirganita/data/yamlio.py)."""

from __future__ import annotations

import pytest

from jyotirganita.data.yamlio import PrintedNumber, dump_canonical, loads_exact


def test_floats_stay_printed_text() -> None:
    got = loads_exact("a: 0.0057183\nb: 12\nc: -1.50\n")
    assert got == {"a": "0.0057183", "b": 12, "c": "-1.50"}
    assert isinstance(got["a"], PrintedNumber)


@pytest.mark.parametrize("text", ["a: .inf\n", "a: -.Inf\n", "a: .nan\n"])
def test_infinity_and_nan_refused(text: str) -> None:
    with pytest.raises(ValueError, match="infinity and NaN"):
        loads_exact(text)


def test_yaml_1_2_booleans_and_no_timestamps() -> None:
    got = loads_exact("on: 2026-10-02\nyes: no\noff: y\nt: true\nf: False\n")
    assert got == {"on": "2026-10-02", "yes": "no", "off": "y", "t": True, "f": False}


def test_canonical_round_trip() -> None:
    data = {
        "key": "bodies.moon.revolutions",
        "value": [4, 26, PrintedNumber("17.5")],
        "on": "2026-10-02",
        "read": [{"by": "m/2026-10-02-t", "clip": [0, 0, 216, 144], "note": "a\nb"}],
        "word": {"text": "कटपय", "decode": [1, 2]},
        "empty": [],
        "none": None,
    }
    text = dump_canonical(data)
    assert "value: [4, 26, 17.5]" in text
    assert "on: '2026-10-02'" not in text  # a date is plain text, not quoted
    assert "कटपय" in text
    assert loads_exact(text) == data
    assert dump_canonical(loads_exact(text)) == text


def test_canonical_form_writes_no_aliases() -> None:
    shared: list[str] = []
    text = dump_canonical({"a": shared, "b": shared})
    assert "&" not in text and "*" not in text
    assert loads_exact(text) == {"a": [], "b": []}
