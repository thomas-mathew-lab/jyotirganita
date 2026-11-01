"""The frames of date and the Earth's rotation.

A :class:`Frame` binds one precession theory and one nutation theory
(``modern/precession.py``, ``modern/nutation.py``) and serves:

- **the ecliptic of date.** A celestial (GCRS) direction is carried to the
  true equator and equinox of date by the theory's matrix and turned into
  the ecliptic by R1(ε), ε = ε_A + Δε (true) or ε_A (mean): the longitude
  is measured from the equinox of date along the ecliptic of date. A true
  longitude carries the :class:`NutationIdentity` of the nutation instance
  that produced it.
- **the Earth's rotation.** Greenwich apparent sidereal time by TN36
  eq. (5.30), GST = ERA(UT1) − EO: the Earth rotation angle of eq. (5.14)
  (``data/tables/precession_iau2006.yaml``, ``era``; "insensitive at the
  microarcsecond level to the precession-nutation model", TN36 p. 9) less
  the equation of the origins, "the CIO based right ascension of the
  equinox along the moving equator" (TN36 p. 17). EO is computed from the
  configured theory itself: the CIO is the first axis of Q(t) of eq.
  (5.10), Q = M(X, Y)·R3(s), with X, Y the celestial pole of the theory's
  matrix and s the CIO locator of eq. (5.8),
  s = −∫ (X Ẏ − Y Ẋ)/(1 + Z) dt, the constant σ0N0 − Σ0N0 (tens of µas)
  omitted; EO is minus the CIO's right ascension in the true equator and
  equinox of date. The series form eq. (5.9) is not used: TN36 (p. 6)
  gives it as equivalent "within 1 microarcsecond over one century", and
  under a long-term theory it drifts by arcseconds (1.6″ at −20
  centuries, 7″ at −27). The integral follows the precession-only pole
  and is summed on a grid of ``modern.cio_locator_step``
  (``data/engine_parameters.yaml``), each step the area its chord sweeps
  with the denominator taken at the endpoints' mean Z (a quadrature of
  the integral, not its exact value along the chord),
  −(Xa Yb − Xb Ya)/(1 + (Za + Zb)/2); the nutation's part of the
  pole enters through −½[X Y − Xp Yp], the full pole's product less the
  precession-only pole's (the form of eq. (5.9), to which eq. (5.8)
  reduces near the reference pole). The nutation's own share of the
  integral is omitted: a few milliarcseconds per century, under a
  hundredth of a second of time in every served range. One route
  serves all three theories, so a long-term theory gets a sidereal time
  consistent with its own pole (the sidereal-time
  reading). Polar motion is not applied (the TIO and the CIP's terrestrial
  position, up to about 0.5″, are not modelled).
"""

from __future__ import annotations

from fractions import Fraction
from math import floor, pi

import numpy as np
from numpy.typing import NDArray

from jyotirganita.core.exact import parse_fraction
from jyotirganita.core.types import TT, UT1, NutationIdentity
from jyotirganita.data.engine_parameters import EngineParameter
from jyotirganita.modern.angles import Matrix, r1
from jyotirganita.modern.nutation import NutationAngles, NutationTheory
from jyotirganita.modern.precession import PrecessionTheory
from jyotirganita.modern.tables import FetchedTable, TableError, load_table
from jyotirganita.modern.timescales import TimeScales

__all__ = ["Frame", "Vector"]

Vector = NDArray[np.float64]
TWO_PI = 2 * pi


def _era_terms(table: FetchedTable) -> tuple[Fraction, Fraction]:
    rows = list(table["era"])
    if [(r[1], r[2]) for r in rows] != [(0, "revolution"), (1, "revolution")]:
        raise TableError(f"{table.path.name}: the ERA is not two terms in revolutions")
    text = [str(r[0]).replace("−", "-") for r in rows]
    return parse_fraction(text[0]), parse_fraction(text[1])


class Frame:
    """A precession theory and a nutation theory: the frames of date (module docstring)."""

    def __init__(
        self,
        precession: PrecessionTheory,
        nutation: NutationTheory,
        scales: TimeScales,
        cio_step: EngineParameter,
        era_table: FetchedTable | None = None,
    ) -> None:
        if cio_step.key != "modern.cio_locator_step" or cio_step.unit != "julian_centuries":
            raise ValueError(
                "the CIO locator's grid is the engine parameter modern.cio_locator_step"
            )
        self.precession = precession
        self.nutation = nutation
        self.scales = scales
        self._h = float(cio_step.value)
        # the float too: 1/10**400 is positive and its float 0
        if not (cio_step.value > 0 and self._h > 0):
            raise ValueError("modern.cio_locator_step is positive")
        c0, c1 = _era_terms(era_table or load_table("precession_iau2006"))
        # ERA = 2π(day fraction + c0 + (c1 − 1) Tu), the form of TN36 eq. (5.15)
        self._era0 = float(c0)
        self._era1 = float(c1 - 1)
        self._epoch = float(scales.epoch_jd)
        self._knots: dict[int, float] = {0: 0.0}
        self._last: tuple[float, NutationAngles, Matrix] | None = None

    @property
    def identity(self) -> NutationIdentity:
        return self.nutation.identity

    # --- the equator and ecliptic of date ---------------------------------

    def state(self, t: float) -> tuple[NutationAngles, Matrix]:
        """Δψ, Δε and the matrix GCRS → true equator and equinox at t (the last t cached)."""
        if self._last is None or self._last[0] != t:
            nut = self.nutation.angles(t)
            self._last = (t, nut, self.precession.bias_precession_nutation(t, nut))
        return self._last[1], self._last[2]

    def true_equator(self, u: Vector, t: float) -> Vector:
        _, m = self.state(t)
        out: Vector = m @ u
        return out

    def true_ecliptic(self, u: Vector, t: float) -> tuple[float, float, NutationAngles]:
        """Longitude and latitude (radians) of direction ``u`` on the true ecliptic of date."""
        nut, m = self.state(t)
        v = r1(self.precession.mean_obliquity(t) + nut.deps) @ (m @ u)
        return (*self._lon_lat(v), nut)

    def mean_ecliptic(self, u: Vector, t: float) -> tuple[float, float]:
        """Longitude and latitude (radians) on the mean ecliptic and equinox of date."""
        v = r1(self.precession.mean_obliquity(t)) @ (self.precession.bias_precession(t) @ u)
        return self._lon_lat(v)

    @staticmethod
    def _lon_lat(v: Vector) -> tuple[float, float]:
        lon = float(np.mod(np.arctan2(v[1], v[0]), TWO_PI))
        lat = float(np.arctan2(v[2], np.hypot(v[0], v[1])))
        return lon, lat

    # --- the Earth's rotation ---------------------------------------------

    def era(self, t: UT1) -> float:
        """The Earth rotation angle, TN36 eq. (5.15), in [0, 2π)."""
        tu = (t.jd_whole - self._epoch) + t.jd_fraction
        frac = t.jd_whole % 1 + t.jd_fraction
        return float(np.mod(TWO_PI * (frac + self._era0 + self._era1 * tu), TWO_PI))

    def rotation_rate(self) -> float:
        """dERA/dTu, the Earth's rotation in radians per day of UT1 (TN36 eq. 5.15)."""
        return TWO_PI * (self._era1 + 1)

    def _pole(self, t: float) -> tuple[float, float, float]:
        row = self.precession.bias_precession(t)[2]
        return float(row[0]), float(row[1]), float(row[2])

    @staticmethod
    def _sweep(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
        """−∫ (X dY − Y dX)/(1 + Z) along the chord from pole ``a`` to pole ``b``, with
        ``Z`` taken at the endpoints' mean (a quadrature step)."""
        return -(a[0] * b[1] - b[0] * a[1]) / (1 + (a[2] + b[2]) / 2)

    def _integral(self, t: float) -> tuple[float, float, float]:
        """−∫ from 0 to t of (X Ẏ − Y Ẋ)/(1 + Z) dt along the precession-only pole, TN36
        eq. (5.8), with that pole's X and Y at t."""
        h = self._h
        k = floor(t / h) if t >= 0 else -floor(-t / h)
        step = 1 if k >= 0 else -1
        j = 0
        while j != k:
            nxt = j + step
            if nxt not in self._knots:
                self._knots[nxt] = self._knots[j] + self._sweep(
                    self._pole(j * h), self._pole(nxt * h)
                )
            j = nxt
        end = self._pole(t)
        return self._knots[k] + self._sweep(self._pole(k * h), end), end[0], end[1]

    def cio_locator(self, t: float) -> float:
        """s of TN36 eq. (5.8), the constant σ0N0 − Σ0N0 omitted (module docstring)."""
        _, m = self.state(t)
        x, y = float(m[2, 0]), float(m[2, 1])
        s, xp, yp = self._integral(t)
        return -(x * y - xp * yp) / 2 + s

    def equation_of_origins(self, t: float) -> float:
        """EO: minus the right ascension of the CIO in the true equator and equinox (radians)."""
        _, m = self.state(t)
        x, y, z = (float(c) for c in m[2])
        a = 1 / (1 + z)
        q = np.array(
            [
                [1 - a * x * x, -a * x * y, x],
                [-a * x * y, 1 - a * y * y, y],
                [-x, -y, 1 - a * (x * x + y * y)],
            ]
        )
        s = self.cio_locator(t)
        cio = q @ np.array([np.cos(s), -np.sin(s), 0.0])
        v = m @ cio
        return float(-np.arctan2(v[1], v[0]))

    def gst(self, ut1: UT1, tt: TT) -> float:
        """Greenwich apparent sidereal time, ERA(UT1) − EO(TT), in [0, 2π)."""
        t = self.scales.centuries(tt)
        return float(np.mod(self.era(ut1) - self.equation_of_origins(t), TWO_PI))
