"""Exact arithmetic helpers: fractions, sexagesimal forms, rounding.

Everything here is integers and :class:`fractions.Fraction`; no ``math``,
``numpy`` or ``decimal`` import is permitted in this module.

Rounding and truncation are *named functions*. Which one a text applies, at
which place, is a procedure datum with its citation and basis; nothing in this module chooses a
rule.

Printed forms handled here:

- a fraction or a decimal as printed, with the ASCII hyphen-minus or the
  Unicode minus U+2212 (``"−9/85"``), parsed exactly (:func:`parse_fraction`);
- the canonical serialised fraction ``num/den`` of the records: reduced,
  the denominator always written, the sign on the numerator
  (:func:`to_canonical`, :func:`from_canonical`);
- sexagesimal parts ``[whole, p1, p2, ...]`` with each later part in
  ``[0, 60)`` and the sign carried separately (:func:`from_sexagesimal`,
  :func:`to_sexagesimal`);
- rāśi–degree–kalā–vikalā ``[r, d, m, s]``: one rāśi is 30 degrees, one kalā
  1/60 degree, one vikalā 1/60 kalā (:func:`from_rdms`, :func:`to_rdms`).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

__all__ = [
    "Rdms",
    "Rounding",
    "Sexagesimal",
    "ceil_to",
    "floor_to",
    "from_canonical",
    "from_rdms",
    "from_sexagesimal",
    "parse_fraction",
    "round_half_away_from_zero",
    "round_half_even",
    "round_half_up",
    "round_to",
    "to_canonical",
    "to_rdms",
    "to_sexagesimal",
    "truncate",
]

SEXAGESIMAL_BASE = 60
DEGREES_PER_RASI = 30
UNICODE_MINUS = "−"

_DECIMAL = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)$")
_RATIO = re.compile(r"^[+-]?\d+/\d+$")
_CANONICAL = re.compile(r"\A(0|-?[1-9][0-9]*)/([1-9][0-9]*)\Z")  # ASCII digits, no newline


def _require_exact(x: object, name: str) -> Fraction:
    """Return ``x`` as a Fraction, refusing floats, bools and other types."""
    if isinstance(x, bool) or not isinstance(x, int | Fraction):
        raise TypeError(f"{name} must be int or Fraction, not {type(x).__name__}")
    return Fraction(x)


def _require_quantum(quantum: object) -> Fraction:
    q = _require_exact(quantum, "quantum")
    if q <= 0:
        raise ValueError(f"quantum must be positive, got {q}")
    return q


def parse_fraction(text: str) -> Fraction:
    """Parse a printed integer, ratio or decimal exactly.

    Accepts ``"57753336"``, ``"-9/85"``, ``"−9/85"`` (Unicode minus) and
    ``"0.0057183"``. A decimal is read as the exact rational it denotes,
    never through a float. Exponent notation, spaces inside the number and
    a zero denominator are refused.
    """
    if not isinstance(text, str):
        raise TypeError(f"printed value must be a string, not {type(text).__name__}")
    s = text.strip().replace(UNICODE_MINUS, "-")
    if _RATIO.match(s):
        num, den = s.split("/")
        if int(den) == 0:
            raise ValueError(f"zero denominator in {text!r}")
        return Fraction(int(num), int(den))
    if _DECIMAL.match(s):
        return Fraction(s)
    raise ValueError(f"not an exact printed number: {text!r}")


def to_canonical(x: Fraction | int) -> str:
    """Serialise ``x`` in the canonical form ``num/den``.

    The fraction is reduced, the denominator is always written (``3/1``) and
    the sign sits on the numerator (``-3/4``).
    """
    f = _require_exact(x, "x")
    return f"{f.numerator}/{f.denominator}"


def from_canonical(text: str) -> Fraction:
    """Parse the canonical form written by :func:`to_canonical`, strictly.

    A non-reduced fraction, a missing denominator, a sign on the denominator,
    a leading ``+`` or a leading zero is refused, so that each value has one
    serialisation.
    """
    m = _CANONICAL.match(text)
    if m is None:
        raise ValueError(f"not a canonical num/den string: {text!r}")
    num_text, den_text = text.split("/")
    f = Fraction(int(num_text), int(den_text))
    if f.numerator != int(num_text) or f.denominator != int(den_text):
        raise ValueError(f"canonical fraction must be reduced: {text!r}")
    return f


# --- rounding procedures ---------------------------------------------------


def truncate(x: Fraction | int, quantum: Fraction | int) -> Fraction:
    """The multiple of ``quantum`` nearest ``x`` toward zero."""
    v, q = _require_exact(x, "x"), _require_quantum(quantum)
    n = abs(v) // q
    return (n * q) if v >= 0 else -(n * q)


def floor_to(x: Fraction | int, quantum: Fraction | int) -> Fraction:
    """The largest multiple of ``quantum`` not above ``x``."""
    v, q = _require_exact(x, "x"), _require_quantum(quantum)
    return (v // q) * q


def ceil_to(x: Fraction | int, quantum: Fraction | int) -> Fraction:
    """The smallest multiple of ``quantum`` not below ``x``."""
    v, q = _require_exact(x, "x"), _require_quantum(quantum)
    return -((-v) // q) * q


def round_half_up(x: Fraction | int, quantum: Fraction | int) -> Fraction:
    """Nearest multiple of ``quantum``; an exact half goes toward +∞."""
    v, q = _require_exact(x, "x"), _require_quantum(quantum)
    return ((v / q) + Fraction(1, 2)) // 1 * q


def round_half_away_from_zero(x: Fraction | int, quantum: Fraction | int) -> Fraction:
    """Nearest multiple of ``quantum``; an exact half goes away from zero."""
    v, q = _require_exact(x, "x"), _require_quantum(quantum)
    n = ((abs(v) / q) + Fraction(1, 2)) // 1
    return (n * q) if v >= 0 else -(n * q)


def round_half_even(x: Fraction | int, quantum: Fraction | int) -> Fraction:
    """Nearest multiple of ``quantum``; an exact half goes to the even multiple."""
    v, q = _require_exact(x, "x"), _require_quantum(quantum)
    return Fraction(round(v / q)) * q


class Rounding(Enum):
    """The named rounding procedures, for procedure data to refer to."""

    TRUNCATE = "truncate"
    FLOOR = "floor"
    CEIL = "ceil"
    HALF_UP = "round_half_up"
    HALF_AWAY_FROM_ZERO = "round_half_away_from_zero"
    HALF_EVEN = "round_half_even"


_ROUNDING: dict[Rounding, Callable[[Fraction, Fraction], Fraction]] = {
    Rounding.TRUNCATE: truncate,
    Rounding.FLOOR: floor_to,
    Rounding.CEIL: ceil_to,
    Rounding.HALF_UP: round_half_up,
    Rounding.HALF_AWAY_FROM_ZERO: round_half_away_from_zero,
    Rounding.HALF_EVEN: round_half_even,
}


def round_to(x: Fraction | int, quantum: Fraction | int, rule: Rounding) -> Fraction:
    """Apply the named rule ``rule`` at ``quantum``."""
    if not isinstance(rule, Rounding):
        raise TypeError(f"rule must be a Rounding, not {type(rule).__name__}")
    return _ROUNDING[rule](_require_exact(x, "x"), _require_quantum(quantum))


# --- sexagesimal -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Sexagesimal:
    """A signed sexagesimal number: ``negative`` and ``parts = [whole, p1, ...]``."""

    negative: bool
    parts: tuple[int, ...]

    def __post_init__(self) -> None:
        _check_parts(self.parts)
        if self.negative and all(p == 0 for p in self.parts):
            raise ValueError("negative zero is not a sexagesimal number")

    @property
    def value(self) -> Fraction:
        """The exact value."""
        return from_sexagesimal(self.parts, negative=self.negative)


def _check_parts(parts: Sequence[int]) -> None:
    if len(parts) == 0:
        raise ValueError("a sexagesimal number needs at least one part")
    for i, p in enumerate(parts):
        if isinstance(p, bool) or not isinstance(p, int):
            raise TypeError(f"sexagesimal part {i} must be int, not {type(p).__name__}")
        if p < 0:
            raise ValueError(f"sexagesimal part {i} is negative ({p}); the sign is separate")
        if i > 0 and p >= SEXAGESIMAL_BASE:
            raise ValueError(f"sexagesimal part {i} is {p}, not below {SEXAGESIMAL_BASE}")


def from_sexagesimal(parts: Sequence[int], *, negative: bool = False) -> Fraction:
    """The exact value of ``parts = [whole, p1, p2, ...]``: whole + p1/60 + p2/60² + …"""
    _check_parts(parts)
    total = Fraction(0)
    scale = Fraction(1)
    for p in parts:
        total += p * scale
        scale /= SEXAGESIMAL_BASE
    return -total if negative else total


def to_sexagesimal(x: Fraction | int, places: int, rule: Rounding) -> Sexagesimal:
    """Write ``x`` with ``places`` sexagesimal places, the last rounded by ``rule``.

    The rule is applied to the signed value, so ``TRUNCATE`` and ``FLOOR``
    differ for a negative ``x``, as they should.
    """
    if isinstance(places, bool) or not isinstance(places, int) or places < 0:
        raise ValueError(f"places must be a non-negative int, got {places!r}")
    quantum = Fraction(1, SEXAGESIMAL_BASE**places)
    v = round_to(x, quantum, rule)
    negative = v < 0
    units = abs(v) / quantum
    if units.denominator != 1:
        raise AssertionError("rounded value is not a whole number of quanta")
    n = units.numerator
    digits: list[int] = []
    for _ in range(places):
        n, r = divmod(n, SEXAGESIMAL_BASE)
        digits.append(r)
    parts = (n, *reversed(digits))
    if negative and all(p == 0 for p in parts):
        negative = False
    return Sexagesimal(negative, parts)


# --- rāśi, degree, kalā, vikalā ---------------------------------------------


def from_rdms(parts: Sequence[int], *, negative: bool = False) -> Fraction:
    """Degrees from a printed ``[rāśi, degree, kalā, vikalā]`` (degree below 30).

    Shorter forms ``[r, d]`` and ``[r, d, m]`` are accepted; a longer form
    continues sexagesimally below the vikalā.
    """
    if len(parts) < 2:
        raise ValueError("an rdms form needs at least [rāśi, degree]")
    r, d = parts[0], parts[1]
    _check_parts(list(parts))
    if d >= DEGREES_PER_RASI:
        raise ValueError(f"degree part {d} is not below {DEGREES_PER_RASI}")
    degrees = from_sexagesimal([d, *parts[2:]])
    total = r * DEGREES_PER_RASI + degrees
    return -total if negative else total


@dataclass(frozen=True, slots=True)
class Rdms:
    """A non-negative angle written ``(rāśi, degree, kalā, vikalā, …)``."""

    parts: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.parts) < 2:
            raise ValueError("an rdms form needs at least (rāśi, degree)")
        _check_parts(self.parts)
        if self.parts[1] >= DEGREES_PER_RASI:
            raise ValueError(f"degree part {self.parts[1]} is not below {DEGREES_PER_RASI}")

    @property
    def degrees(self) -> Fraction:
        """The exact angle in degrees."""
        return from_rdms(self.parts)


def to_rdms(degrees: Fraction | int, places: int, rule: Rounding) -> Rdms:
    """Write non-negative ``degrees`` as ``(r, d, kalā, vikalā, …)``.

    ``places`` counts the sexagesimal places after the degree (2 for
    kalā–vikalā); the last place is rounded by ``rule``.
    """
    v = _require_exact(degrees, "degrees")
    if v < 0:
        raise ValueError("to_rdms takes a non-negative angle; normalise first")
    sx = to_sexagesimal(v, places, rule)
    r, d = divmod(sx.parts[0], DEGREES_PER_RASI)
    return Rdms((r, d, *sx.parts[1:]))
