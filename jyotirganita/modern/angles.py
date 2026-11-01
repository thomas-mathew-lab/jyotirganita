"""Angle units, frame rotations and printed polynomials.

- **Units.** A printed coefficient carries its unit as its table states it:
  ``deg``, ``arcsec``, ``rad`` or ``revolution`` (one turn, 2π). A
  microarcsecond is 10⁻⁶ arcsec; a table's unit is read from its own
  heading (``modern/nutation.py``), never assumed.
- **Rotations.** ``R1``, ``R2`` and ``R3`` are the rotation matrices "with
  positive angle about the axes 1, 2 and 3" of the coordinate frame, the
  convention of TN36 chapter 5 (p. 5) and iau1980_nutation ("direct rotations about
  the axes 1, 2 and 3 of the coordinate frame"): R3(θ) takes the
  components of a vector in a frame to its components in the frame turned
  by θ about axis 3, so R3(θ) = ((cos θ, sin θ, 0), (−sin θ, cos θ, 0),
  (0, 0, 1)). The invariant tests check that under this convention the
  IAU 2006 matrix's third row is the pole of the equator of date Vondrák's
  series gives (``tests/invariants``).
- **Polynomials.** A printed polynomial is a list of ``[coefficient,
  power, unit]`` rows (``data/tables/*.yaml``); :func:`polynomial` turns
  it into float coefficients in radians and :func:`evaluate` sums it in
  the time argument.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import pi

import numpy as np
from numpy.typing import NDArray

from jyotirganita.modern.tables import TableError, number

__all__ = [
    "ARCSEC",
    "MICROARCSEC",
    "Matrix",
    "Polynomial",
    "evaluate",
    "polynomial",
    "r1",
    "r2",
    "r3",
    "to_radians",
]

Matrix = NDArray[np.float64]

#: one arcsecond in radians (π / (180 × 3600))
ARCSEC = pi / (180 * 3600)
#: one microarcsecond in radians
MICROARCSEC = ARCSEC / (1000 * 1000)

_UNITS = {
    "deg": pi / 180,
    "arcsec": ARCSEC,
    "rad": 1.0,
    "revolution": 2 * pi,
}


def to_radians(value: float, unit: str) -> float:
    """``value`` in ``unit`` (``deg``, ``arcsec``, ``rad``, ``revolution``) as radians."""
    try:
        return value * _UNITS[unit]
    except KeyError:
        raise TableError(f"not an angle unit: {unit!r}") from None


Polynomial = tuple[tuple[float, int], ...]
"""Coefficients in radians, each with its power of the time argument."""


def polynomial(rows: Sequence[Sequence[object]]) -> Polynomial:
    """A printed polynomial (``[coefficient, power, unit]`` rows) in radians."""
    out: list[tuple[float, int]] = []
    for row in rows:
        if len(row) < 3 or not isinstance(row[1], int) or not isinstance(row[2], str):
            raise TableError(f"not a polynomial row [coefficient, power, unit]: {row!r}")
        out.append((to_radians(number(row[0]), row[2]), row[1]))
    return tuple(out)


def evaluate(poly: Polynomial, t: float) -> float:
    """Σ c tⁿ."""
    return float(sum(c * t**n for c, n in poly))


def r1(a: float) -> Matrix:
    """Rotation by ``a`` about axis 1 (module docstring)."""
    c, s = np.cos(a), np.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, s], [0.0, -s, c]])


def r2(a: float) -> Matrix:
    """Rotation by ``a`` about axis 2 (module docstring)."""
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0.0, -s], [0.0, 1.0, 0.0], [s, 0.0, c]])


def r3(a: float) -> Matrix:
    """Rotation by ``a`` about axis 3 (module docstring)."""
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])
