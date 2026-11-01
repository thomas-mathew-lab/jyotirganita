"""Unit tests of core/exact.py: parsing, canonical form, rounding, sexagesimal.

The numbers are arithmetic cases constructed for the test; none is a datum.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from jyotirganita.core import exact
from jyotirganita.core.exact import Rounding


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("12", Fraction(12)),
        ("-9/85", Fraction(-9, 85)),
        ("−9/85", Fraction(-9, 85)),
        ("0.0057183", Fraction(57183, 10_000_000)),
        (" 3/4 ", Fraction(3, 4)),
        ("+.5", Fraction(1, 2)),
    ],
)
def test_parse_fraction_is_exact(text: str, value: Fraction) -> None:
    assert exact.parse_fraction(text) == value


@pytest.mark.parametrize("text", ["1e3", "1/0", "3 / 4", "", "x", "1.2.3", "--1"])
def test_parse_fraction_refuses(text: str) -> None:
    with pytest.raises(ValueError):
        exact.parse_fraction(text)


def test_parse_fraction_refuses_a_float() -> None:
    with pytest.raises(TypeError):
        exact.parse_fraction(0.5)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "text"),
    [(Fraction(3), "3/1"), (Fraction(-3, 4), "-3/4"), (Fraction(0), "0/1"), (6, "6/1")],
)
def test_canonical_round_trip(value: Fraction, text: str) -> None:
    assert exact.to_canonical(value) == text
    assert exact.from_canonical(text) == value


@pytest.mark.parametrize("text", ["3", "6/4", "3/-4", "+3/4", "03/4", "-0/1", "3/04", "1/0"])
def test_from_canonical_is_strict(text: str) -> None:
    with pytest.raises(ValueError):
        exact.from_canonical(text)


def test_to_canonical_refuses_float() -> None:
    with pytest.raises(TypeError):
        exact.to_canonical(0.5)  # type: ignore[arg-type]


Q = Fraction(1, 10)


@pytest.mark.parametrize(
    ("rule", "x", "expected"),
    [
        (Rounding.TRUNCATE, Fraction(27, 100), Fraction(2, 10)),
        (Rounding.TRUNCATE, Fraction(-27, 100), Fraction(-2, 10)),
        (Rounding.FLOOR, Fraction(-27, 100), Fraction(-3, 10)),
        (Rounding.CEIL, Fraction(21, 100), Fraction(3, 10)),
        (Rounding.CEIL, Fraction(-27, 100), Fraction(-2, 10)),
        (Rounding.HALF_UP, Fraction(25, 100), Fraction(3, 10)),
        (Rounding.HALF_UP, Fraction(-25, 100), Fraction(-2, 10)),
        (Rounding.HALF_AWAY_FROM_ZERO, Fraction(-25, 100), Fraction(-3, 10)),
        (Rounding.HALF_EVEN, Fraction(25, 100), Fraction(2, 10)),
        (Rounding.HALF_EVEN, Fraction(35, 100), Fraction(4, 10)),
        (Rounding.HALF_EVEN, Fraction(-25, 100), Fraction(-2, 10)),
    ],
)
def test_rounding_rules(rule: Rounding, x: Fraction, expected: Fraction) -> None:
    assert exact.round_to(x, Q, rule) == expected


def test_rounding_refuses_float_and_bad_quantum() -> None:
    with pytest.raises(TypeError):
        exact.truncate(0.25, Q)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        exact.truncate(Fraction(1), 0)
    with pytest.raises(TypeError):
        exact.round_to(Fraction(1), Q, "truncate")  # type: ignore[arg-type]


def test_sexagesimal_value() -> None:
    assert exact.from_sexagesimal([4, 26, 17]) == 4 + Fraction(26, 60) + Fraction(17, 3600)
    assert exact.from_sexagesimal([0, 30], negative=True) == Fraction(-1, 2)


@pytest.mark.parametrize("parts", [[1, 60], [1, -1], [], [1, 2.5]])
def test_sexagesimal_refuses_bad_parts(parts: list[int]) -> None:
    with pytest.raises((ValueError, TypeError)):
        exact.from_sexagesimal(parts)


def test_to_sexagesimal_round_trip_and_carry() -> None:
    x = exact.from_sexagesimal([4, 26, 17])
    sx = exact.to_sexagesimal(x, 2, Rounding.TRUNCATE)
    assert sx.parts == (4, 26, 17) and not sx.negative
    assert sx.value == x
    # 59.5 vikalā rounds up and carries into the kalā and the degree
    y = exact.from_sexagesimal([1, 59, 59]) + Fraction(1, 7200)
    assert exact.to_sexagesimal(y, 2, Rounding.HALF_UP).parts == (2, 0, 0)
    assert exact.to_sexagesimal(y, 2, Rounding.TRUNCATE).parts == (1, 59, 59)


def test_to_sexagesimal_sign() -> None:
    sx = exact.to_sexagesimal(Fraction(-1, 120), 2, Rounding.TRUNCATE)
    assert sx.negative and sx.parts == (0, 0, 30)
    # a negative value that truncates to zero is zero, not negative zero
    z = exact.to_sexagesimal(Fraction(-1, 7201), 2, Rounding.TRUNCATE)
    assert not z.negative and z.parts == (0, 0, 0)


def test_rdms() -> None:
    deg = exact.from_rdms([4, 26, 17, 30])
    assert deg == 4 * 30 + 26 + Fraction(17, 60) + Fraction(30, 3600)
    form = exact.to_rdms(deg, 2, Rounding.TRUNCATE)
    assert form.parts == (4, 26, 17, 30)
    assert form.degrees == deg
    with pytest.raises(ValueError):
        exact.from_rdms([0, 30, 0])
    with pytest.raises(ValueError):
        exact.to_rdms(Fraction(-1), 2, Rounding.TRUNCATE)
