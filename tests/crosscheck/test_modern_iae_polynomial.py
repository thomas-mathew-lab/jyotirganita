"""The IAE mean-ayanāṃśa polynomial against an independent IAU 2006 evaluation.

The T⁴ check. The
IAE prints its mean ayanāṃśa (indian_astronomical_ephemeris PDF p. 387) as a constant plus a
polynomial in T whose T…T⁵ terms are the general precession in longitude
p_A. The independent route here: p_A computed from the IAU 2006
Fukushima–Williams angles of the fetched TN36 table
(``iau2006_precession``; ``modern/precession.py``), as the angle from
the J2000 equinox to the node of the ecliptic of date on the J2000 ecliptic
(Π_A) taken from the arc on the ecliptic of date from the equinox of date
to that node (Π_A + p_A), and fitted by least squares with a polynomial of
degree five in T over ±10 centuries. The fit's coefficients are compared
with the printed ones at one unit of each coefficient's last printed digit:
a fit of the theory's matrices, not its printed p_A series, reproduces the
printed digits to within that unit (the linear term by 0.83 of it), and the
T⁴ coefficient differs by a factor of about ten. The printed value stays
on the datum and the owner adopted an emendation with one more zero; the last test asserts that the
printed value disagrees, that the adopted one agrees at the printed
coefficient's unit, and that the datum names the decision.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction
from functools import cache

import numpy as np
import pytest
from modern_kit import data

from jyotirganita.modern.angles import ARCSEC, r1
from jyotirganita.modern.precession import Iau2006

Recorder = Callable[..., None]

KEY = "modern.ayanamsa.iae_lahiri.mean.c{}"
SOURCE = "indian_astronomical_ephemeris, printed p. 380 (PDF p. 387): the mean ayanāṃśa polynomial"
#: the fit: degree five, T over ±SPAN centuries in STEPS samples
SPAN, STEPS, DEGREE = 10, 401, 5


def _ecliptic_pole(p: Iau2006, t: float) -> np.ndarray:
    """The pole of the ecliptic of date in the GCRS: the third row of R1(ε_A)·P."""
    return np.asarray((r1(p.mean_obliquity(t)) @ p.bias_precession(t))[2])


def _p_a(p: Iau2006, t: float, e0: np.ndarray, g0: np.ndarray) -> float:
    e = _ecliptic_pole(p, t)
    g = p.bias_precession(t)[0]  # the mean equinox of date
    n = np.cross(e0, e)
    n /= np.linalg.norm(n)  # the ascending node of the ecliptic of date on the J2000 ecliptic
    big_pi = np.arctan2(np.cross(g0, n) @ e0, g0 @ n)
    arc = np.arctan2(np.cross(g, n) @ e, g @ n)  # equinox of date to the node, eastward
    return float(arc - big_pi)


@cache
def fitted() -> tuple[float, ...]:
    """The fitted coefficients of T¹ … T⁵, in arcseconds."""
    p = Iau2006()
    e0, g0 = _ecliptic_pole(p, 0.0), p.bias_precession(0.0)[0]
    ts = np.linspace(-SPAN, SPAN, STEPS)
    ts = ts[ts != 0]
    y = np.unwrap(np.array([_p_a(p, t, e0, g0) for t in ts])) / ARCSEC
    a = np.vstack([ts**k for k in range(1, DEGREE + 1)]).T
    coeffs, *_ = np.linalg.lstsq(a, y, rcond=None)
    return tuple(float(c) for c in coeffs)


def _printed(n: int) -> tuple[Fraction, Fraction]:
    """The printed coefficient (signed) and one unit of its last printed digit."""
    rec = data()[KEY.format(n)]
    places = len(str(rec.raw["value"]).partition(".")[2])
    assert isinstance(rec.value, Fraction)
    return rec.value, Fraction(1, 10**places)


@pytest.mark.parametrize("n", [1, 2, 3, 5])
def test_the_printed_coefficient_is_the_iau_2006_one(n: int, record_comparison: Recorder) -> None:
    value, unit = _printed(n)
    fit = fitted()[n - 1]
    record_comparison(
        id=f"iae_2022/mean_ayanamsa/c{n}",
        source=SOURCE,
        methods=["modern_de"],
        datum_keys=[KEY.format(n)],
        printed=str(value),
        computed=f"{fit:.12g}",
        tolerance=unit,
        tolerance_reason=(
            "one unit of the coefficient's last printed digit: the independent evaluation "
            "is a least-squares fit of the IAU 2006 matrices, not the theory's printed p_A "
            "series, and agrees with it to that unit"
        ),
    )
    assert abs(fit - float(value)) <= unit


def test_the_printed_t4_coefficient_disagrees_and_the_emendation_agrees(
    record_comparison: Recorder,
) -> None:
    rec = data()[KEY.format(4)]
    emendation = rec.raw["emendation"]
    places = len(str(rec.raw["value"]).partition(".")[2])
    unit = Fraction(1, 10**places)  # one unit of the printed coefficient's last digit
    printed = -Fraction(str(emendation["printed"]))
    assert isinstance(rec.value, Fraction)
    fit = fitted()[3]
    record_comparison(
        id="iae_2022/mean_ayanamsa/c4",
        source=SOURCE,
        methods=["modern_de"],
        datum_keys=[KEY.format(4)],
        printed=str(printed),
        computed=f"{fit:.12g}",
        tolerance=unit,
        tolerance_reason=(
            "NOT AGREED as printed: the printed T^4 coefficient is about ten times the "
            "independent evaluation's; the owner adopted an emendation with one more zero "
            ", which agrees within one unit of the "
            "printed coefficient's last digit; this test fails if either comparison or the "
            "record goes"
        ),
    )
    assert abs(fit - float(printed)) > unit
    assert abs(fit - float(rec.value)) <= unit
    # an emendation resting on inference says so
    assert emendation["evidence"].startswith("inference from an independent evaluation")
