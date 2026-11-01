"""The Rsine table and its rules against the printed examples.

laghubhaskariya_1963 II.2(ii)–3(i) and mahabhaskariya_1960 IV.3–4(i) (Shukla's worked examples, both
``editor_computed``): the Rsine and the Rversed-sine of an arc by the
table of Gītikā 12 with linear interpolation, exact in minutes and their
sexagesimal fractions, so compared exactly (Shukla's "rounded" values to
the nearest minute). aryabhatiya_1976 Gaṇita 11–12 (the editors' geometric
constructions of the table, ``editor_computed``): every Rsine, Rversed-sine
and chord they print at a multiple of the table's interval is the table's.
mahabhaskariya_1960 IV (Shukla's note): the parts of an anomaly in successive quadrants,
taken by Rsine and Rversed-sine in turn (``mahabhaskariya_1960_ch4_anomaly_quadrant_example``).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from fractions import Fraction

import pytest
from authority_kit import printed, records, text_value

from jyotirganita.core.exact import Rounding, round_to
from jyotirganita.siddhantic.epicycle import quadrant_parts
from jyotirganita.siddhantic.tables import RsineTable

Record = Callable[..., None]
FX = "authority/aryabhatiya/"
laghubhaskariya_1963 = FX + "laghubhaskariya_1963_rsine_example"
mahabhaskariya_1960 = FX + "mahabhaskariya_1960_ch4_rsine_rversine_example"
QUAD = FX + "mahabhaskariya_1960_ch4_anomaly_quadrant_example"
EXACT = "exact fractions of a minute (the rule's own arithmetic)"
MINUTES = 60


def table() -> RsineTable:
    diffs: list[int] = []
    while f"texts.aryabhatiya.trig.rsine_differences.d{len(diffs) + 1:02d}" in records().data:
        diffs.append(
            int(text_value("aryabhatiya", f"trig.rsine_differences.d{len(diffs) + 1:02d}"))
        )
    return RsineTable.of(int(text_value("aryabhatiya", "procedures.rsine.interval_minutes")), diffs)


# --- laghubhaskariya_1963 II.2(ii)–3(i): the Rsine of 24°
# ----------------------------------------------


def _laghubhaskariya_1963() -> dict[str, Fraction]:
    t, fx = table(), printed(laghubhaskariya_1963)
    arc = fx["input.bhuja_degrees"] * MINUTES
    q, r = divmod(arc, t.interval)
    return {
        "output.bhuja_minutes": Fraction(arc),
        "output.quotient": Fraction(q),
        "output.remainder": Fraction(r),
        "output.sum_six": Fraction(sum(t.differences[:q])),
        "output.interpolated": Fraction(r * t.differences[q], t.interval),
        "output.rsine": t.rsine(arc),
    }


@pytest.mark.parametrize(
    "value",
    [
        "output.bhuja_minutes",
        "output.quotient",
        "output.remainder",
        "output.sum_six",
        "output.interpolated",
        "output.rsine",
    ],
)
def test_laghubhaskariya_1963_rsine_of_24_degrees(value: str, record_comparison: Record) -> None:
    computed = _laghubhaskariya_1963()[value]
    record_comparison(
        fixture=laghubhaskariya_1963,
        value=value,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == printed(laghubhaskariya_1963)[value]


# --- mahabhaskariya_1960 IV.3–4(i): the Rsine and Rversed-sine of 32°
# ----------------------------------


def _mahabhaskariya_1960() -> dict[str, Fraction]:
    t, fx = table(), printed(mahabhaskariya_1960)
    arc = fx["input.arc_degrees"] * MINUTES
    q, r = divmod(arc, t.interval)
    out: dict[str, Fraction] = {
        "output.arc_minutes": Fraction(arc),
        "output.quotient": Fraction(q),
        "output.remainder": Fraction(r),
    }
    for kind, diffs, value in (
        ("rsine", t.differences, t.rsine(arc)),
        ("rversine", t.differences[::-1], t.rversine(arc)),
    ):
        out[f"output.{kind}.sum_eight"] = Fraction(sum(diffs[:q]))
        out[f"output.{kind}.ninth_difference"] = Fraction(diffs[q])
        out[f"output.{kind}.interpolated"] = Fraction(r * diffs[q], t.interval)
        out[f"output.{kind}.value"] = value
        out[f"output.{kind}.rounded"] = round_to(value, Fraction(1), Rounding.HALF_UP)
    return out


mahabhaskariya_1960_VALUES = [
    "output.arc_minutes",
    "output.quotient",
    "output.remainder",
    *[
        f"output.{k}.{v}"
        for k in ("rsine", "rversine")
        for v in ("sum_eight", "ninth_difference", "interpolated", "value", "rounded")
    ],
]


@pytest.mark.parametrize("value", mahabhaskariya_1960_VALUES)
def test_mahabhaskariya_1960_rsine_and_rversine_of_32_degrees(
    value: str, record_comparison: Record
) -> None:
    computed = _mahabhaskariya_1960()[value]
    record_comparison(
        fixture=mahabhaskariya_1960,
        value=value,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + "; 'rounded' to the nearest minute as printed",
    )
    assert computed == printed(mahabhaskariya_1960)[value]


# --- aryabhatiya_1976 Gaṇita 11–12: the editors' Rsines, Rversed-sines and chords
# ---------------------

_NAME = re.compile(r"^(?:output|summary)\.(rsin|rvers|chord)_(\d+)(?:_(\d+))?$")
_SERIAL = re.compile(r"^output\.rsine\.(\d+)$")


def _aryabhatiya_1976_value(t: RsineTable, name: str) -> Fraction | None:
    m = _NAME.match(name)
    if m:
        arc = int(m.group(2)) * MINUTES + int(m.group(3) or 0)
        if m.group(1) == "rsin":
            return t.rsine(arc)
        if m.group(1) == "rvers":
            return t.rversine(arc)
        return 2 * t.rsine(Fraction(arc, 2))  # the chord of an arc: twice the half-arc's Rsine
    s = _SERIAL.match(name)
    if s:
        return t.rsine(int(s.group(1)) * t.interval)
    if name == "input.radius":
        return Fraction(t.radius)
    return None


aryabhatiya_1976_CASES = [
    (fid, name)
    for fid in (
        FX + "aryabhatiya_1976_ganita11_12_ex1",
        FX + "aryabhatiya_1976_ganita11_12_ex2",
        FX + "aryabhatiya_1976_ganita11_12_ex3",
    )
    for name in printed(fid)._by_name
    if _aryabhatiya_1976_value(table(), name) is not None
]


@pytest.mark.parametrize(("fixture", "value"), aryabhatiya_1976_CASES)
def test_aryabhatiya_1976_the_table_gives_the_editors_values(
    fixture: str, value: str, record_comparison: Record
) -> None:
    computed = _aryabhatiya_1976_value(table(), value)
    record_comparison(
        fixture=fixture,
        value=value,
        computed=computed,
        tolerance=0,
        tolerance_reason="whole minutes at multiples of the interval: exact",
    )
    assert computed == printed(fixture)[value]


# --- mahabhaskariya_1960 IV: an anomaly's parts in successive quadrants
# -----------------------------------

_PART = re.compile(r"^(case\d+)\.output\.(\d+)\.(rsine|rversine)$")
QUAD_CASES = [n for n in printed(QUAD)._by_name if _PART.match(n)]


@pytest.mark.parametrize("value", QUAD_CASES)
def test_mahabhaskariya_1960_anomaly_parts_by_quadrant(
    value: str, record_comparison: Record
) -> None:
    m = _PART.match(value)
    assert m is not None
    fx = printed(QUAD)
    parts = quadrant_parts(Fraction(fx[f"{m.group(1)}.input.anomaly"]))
    kind, part = parts[int(m.group(2)) - 1]
    record_comparison(
        fixture=QUAD,
        value=value,
        computed=part,
        tolerance=0,
        tolerance_reason="whole degrees, and which function takes each part: exact",
    )
    assert kind == m.group(3) and part == fx[value]
