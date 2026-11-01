"""Eclipse geometry on the modern engine, provisional.

Code and unit tests only: every result carries the flag
``provisional:eclipse``; no comparison against Schram's tables (sewell_dikshit_1896) or a
fetched eclipse canon has been made yet.

**Lunar eclipses** (geocentric). At an instant, with the apparent
geocentric places of the Sun and the Moon (``modern/apparent.py``):
``d`` is the angle between the Moon and the antisolar point; the Moon's
semi-diameter is ``s☾ = asin(R☾/r☾)`` and the Sun's ``s☉ = asin(R☉/r☉)``
(the radii ``modern.constants.radius.*``); the parallaxes are
``π = asin(R⊕/r)`` with the Earth's equatorial radius
(``modern.constants.earth_equatorial_radius``). The shadow's angular radii
at the Moon's distance are the umbra's ``π☾ + π☉ − s☉`` and the
penumbra's ``π☾ + π☉ + s☉``, **without the enlargement** that eclipse
computations apply for the atmosphere: that enlargement is a recorded gap
(``modern.eclipse.shadow_enlargement``). Contacts are the instants
``d = ρ + s☾`` (first and last, penumbral and umbral) and ``d = ρ − s☾``
(totality's); magnitudes at greatest eclipse are ``(ρ + s☾ − d)/(2 s☾)``.

**Solar eclipses at an observer** (topocentric: the observer's position
and velocity enter the light time and the aberration, as for rise and
set). ``d`` is the angle between the Sun and the Moon; the contacts are
``d = s☉ + s☾`` (first and fourth) and ``d = |s☉ − s☾|`` (second and
third, total or annular); the magnitude at greatest eclipse is
``(s☉ + s☾ − d)/(2 s☉)``, and ``s☾/s☉`` when ``d < |s☉ − s☾|`` (the central
phase; exact internal tangency stays partial).

The greatest eclipse is the minimum of ``d`` in the window, found by
golden-section search to ``modern.root.tolerance``; contacts are roots on
the absolute grid of ``modern.riseset.scan_step`` (``modern/roots.py``).
Instants are TT; the caller names the window (a syzygy found from the
element stream is the natural centre). Both ends of the window are
checked against the components' stated ranges before the search
(``ModernEngine.check``): a window that crosses a model's boundary is
refused naming it, never searched in part.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import asin, sqrt

import numpy as np

from jyotirganita.core.types import TT, FloatDays
from jyotirganita.data.datum import Record
from jyotirganita.modern.apparent import Apparent
from jyotirganita.modern.riseset import RiseSet
from jyotirganita.modern.roots import RootError, RootFinder
from jyotirganita.modern.timescales import datum_value

__all__ = ["ECLIPSE_FLAG", "Eclipses", "LunarEclipse", "SolarEclipse", "golden_minimum", "window"]

ECLIPSE_FLAG = "provisional:eclipse"
#: the golden section, (√5 − 1)/2
_GOLDEN = (sqrt(5) - 1) / 2


@dataclass(frozen=True, slots=True)
class LunarEclipse:
    """A lunar eclipse: its greatest instant, magnitudes and contacts (``None`` where none)."""

    greatest: TT
    penumbral_magnitude: float
    umbral_magnitude: float
    penumbral: tuple[TT, TT] | None
    partial: tuple[TT, TT] | None
    total: tuple[TT, TT] | None
    flags: tuple[str, ...] = (ECLIPSE_FLAG,)


@dataclass(frozen=True, slots=True)
class SolarEclipse:
    """A solar eclipse at an observer: greatest instant, magnitude, contacts and kind."""

    greatest: TT
    magnitude: float
    kind: str  # partial | total | annular
    outer: tuple[TT, TT]
    inner: tuple[TT, TT] | None
    flags: tuple[str, ...] = (ECLIPSE_FLAG,)


def _angle(u: np.ndarray, v: np.ndarray) -> float:
    """The angle between two unit vectors, by the arctangent form (stable at small angles)."""
    return float(np.arctan2(np.linalg.norm(np.cross(u, v)), float(u @ v)))


def golden_minimum(f: Callable[[TT], float], a: TT, b: TT, tolerance: float, cap: int) -> TT:
    """The minimum of a unimodal ``f`` on [a, b] by golden-section search."""
    base = a.jd_whole
    lo, hi = a.jd_fraction, (b.jd_whole - base) + b.jd_fraction
    if not lo < hi:  # a reversed window
        raise ValueError("golden_minimum: the window's start is not before its end")

    def g(x: float) -> float:
        return f(TT(base, x))

    x1, x2 = hi - _GOLDEN * (hi - lo), lo + _GOLDEN * (hi - lo)
    f1, f2 = g(x1), g(x2)
    for _ in range(cap):
        if hi - lo <= tolerance:
            return TT(base, (lo + hi) / 2)
        if f1 < f2:
            hi, x2, f2 = x2, x1, f1
            x1 = hi - _GOLDEN * (hi - lo)
            f1 = g(x1)
        else:
            lo, x1, f1 = x1, x2, f2
            x2 = lo + _GOLDEN * (hi - lo)
            f2 = g(x2)
    if hi - lo <= tolerance:  # closed by the last permitted step
        return TT(base, (lo + hi) / 2)
    raise RootError(f"the golden-section search did not close in {cap} iterations")


class Eclipses:
    """Lunar eclipses and local solar eclipses (module docstring)."""

    def __init__(
        self,
        apparent: Apparent,
        riseset: RiseSet,
        data: Mapping[str, Record],
        roots: RootFinder,
        check: Callable[[TT], None],
    ) -> None:
        self.apparent = apparent
        self.check = check
        self.riseset = riseset
        self.roots = roots
        self.r_sun = float(datum_value(data, "modern.constants.radius.sun"))
        self.r_moon = float(datum_value(data, "modern.constants.radius.moon"))
        metres = float(datum_value(data, "modern.constants.earth_equatorial_radius"))
        self.r_earth = metres / _METRES_PER_KM

    # --- lunar --------------------------------------------------------------------

    def _lunar_state(self, t: TT) -> tuple[float, float, float, float]:
        """d, the Moon's semi-diameter, the umbra's and the penumbra's radii (radians)."""
        sun = self.apparent.place("sun", t)
        moon = self.apparent.place("moon", t)
        d = _angle(moon.direction, -sun.direction)
        s_m = asin(self.r_moon / moon.distance_km)
        s_s = asin(self.r_sun / sun.distance_km)
        par = asin(self.r_earth / moon.distance_km) + asin(self.r_earth / sun.distance_km)
        return d, s_m, par - s_s, par + s_s

    def lunar(self, start: TT, end: TT) -> LunarEclipse | None:
        """The lunar eclipse in [start, end), or ``None`` (the window holds one opposition)."""
        self.check(start)
        self.check(end)
        tol, cap = self.roots.tolerance, self.roots.cap
        greatest = golden_minimum(lambda t: self._lunar_state(t)[0], start, end, tol, cap)
        d, s_m, umbra, pen = self._lunar_state(greatest)
        pen_mag = (pen + s_m - d) / (2 * s_m)
        if pen_mag <= 0:
            return None
        umb_mag = (umbra + s_m - d) / (2 * s_m)

        def pair(sign: int, which: int) -> tuple[TT, TT] | None:
            def f(t: TT) -> float:
                st = self._lunar_state(t)
                return st[0] - (st[which] + sign * st[1])

            if not f(greatest) < 0:
                return None
            ins = [t for t, s in self.roots.crossings(f, start, greatest) if s < 0]
            outs = [t for t, s in self.roots.crossings(f, greatest, end) if s > 0]
            if not ins or not outs:
                raise RootError("a lunar contact lies outside the window")
            return ins[-1], outs[0]

        return LunarEclipse(
            greatest,
            pen_mag,
            umb_mag,
            pair(1, 3),
            pair(1, 2) if umb_mag > 0 else None,
            pair(-1, 2) if umb_mag > 0 else None,
        )

    # --- solar, at the observer ---------------------------------------------------------

    def _solar_state(self, t: TT) -> tuple[float, float, float]:
        """d, the Sun's and the Moon's topocentric semi-diameters (radians)."""
        pos, vel, _ = self.riseset.observer_gcrs(t)
        sun = self.apparent.place("sun", t, observer=(pos, vel))
        moon = self.apparent.place("moon", t, observer=(pos, vel))
        d = _angle(sun.direction, moon.direction)
        return d, asin(self.r_sun / sun.distance_km), asin(self.r_moon / moon.distance_km)

    def solar(self, start: TT, end: TT) -> SolarEclipse | None:
        """The solar eclipse at the observer in [start, end), or ``None``."""
        self.check(start)
        self.check(end)
        tol, cap = self.roots.tolerance, self.roots.cap
        greatest = golden_minimum(lambda t: self._solar_state(t)[0], start, end, tol, cap)
        d, s_s, s_m = self._solar_state(greatest)
        if not d < s_s + s_m:
            return None

        def pair(inner: bool) -> tuple[TT, TT]:
            def f(t: TT) -> float:
                dd, ss, sm = self._solar_state(t)
                return dd - (abs(ss - sm) if inner else ss + sm)

            ins = [t for t, s in self.roots.crossings(f, start, greatest) if s < 0]
            outs = [t for t, s in self.roots.crossings(f, greatest, end) if s > 0]
            if not ins or not outs:
                raise RootError("a solar contact lies outside the window")
            return ins[-1], outs[0]

        # strict: at exact internal tangency there is no central phase to time, and its
        # contact search would find no crossing; there
        # the partial formula gives the same ratio when the Moon is the smaller disc
        central = d < abs(s_s - s_m)
        kind = "partial" if not central else ("total" if s_m >= s_s else "annular")
        # inside the central phase the Moon's disc lies within the Sun's (or covers it): the
        # magnitude is the ratio of the diameters
        magnitude = s_m / s_s if central else (s_s + s_m - d) / (2 * s_s)
        return SolarEclipse(
            greatest,
            magnitude,
            kind,
            pair(False),
            pair(True) if central else None,
        )


_METRES_PER_KM = 1000


def window(centre: TT, half_days: float) -> tuple[TT, TT]:
    """[centre − half, centre + half): a search window around a syzygy."""
    if not half_days > 0:
        raise ValueError(f"window: a half-width is positive ({half_days})")
    return centre + FloatDays(-half_days), centre + FloatDays(half_days)
