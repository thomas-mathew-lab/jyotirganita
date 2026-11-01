"""Rise and set at an observer.

A body rises or sets when the geometric altitude of its centre, seen from
the observer (topocentric: the observer's position and velocity enter the
light time and the aberration of ``modern/apparent.py``),
crosses the threshold the event definition builds, every term explicit:

    h₀ = − (refraction + semidiameter + dip)

- **reference** ``centre`` (no semidiameter) or ``upper_limb``: the Sun's
  semidiameter is the IAE's fixed value (``modern.sun.semidiameter.iae``,
  indian_astronomical_ephemeris 2022, the statements of its sunrise tables); another body's is its
  radius (``modern.constants.radius.<body>``) over its topocentric
  distance;
- **refraction** ``none`` or a model whose horizontal refraction is a datum:
  ``iae_general`` (``modern.refraction.iae_general.horizontal``, the IAE's
  general tables) and ``iae_india`` (``modern.refraction.iae_india.
  horizontal``, its Indian stations and calendar);
- **dip** ``none`` or one of the IAE's three coefficients with a height of
  the observer above the ground (``modern.dip.iae.statement``):
  ``depression`` (the additional arc of depression for rising and setting,
  refraction included), ``sensible_horizon`` and ``geometric``, each in
  arcminutes times the square root of the height in metres.

The observer is a geodetic latitude, an east longitude and a height above
the reference ellipsoid, whose equatorial radius and flattening are the
IAE's (``modern.constants.earth_equatorial_radius``, ``.earth_flattening``).
The terrestrial position is carried to the true equator and equinox of
date by Greenwich apparent sidereal time (``modern/frames.py``; polar
motion not applied) and to the GCRS by the frame's matrix; its velocity is
the Earth's rotation at the rate of the Earth rotation angle. The altitude
is measured from the plane normal to the geodetic vertical. The instants
are found by ``modern/roots.py``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from math import asin, pi, sqrt

import numpy as np

from jyotirganita.core.types import TT, UT1
from jyotirganita.data.datum import Record
from jyotirganita.modern.angles import r3
from jyotirganita.modern.apparent import Apparent
from jyotirganita.modern.frames import Frame, Vector
from jyotirganita.modern.roots import RootFinder
from jyotirganita.modern.timescales import datum_value

__all__ = [
    "DIPS",
    "REFERENCES",
    "REFRACTIONS",
    "Event",
    "ModernObserver",
    "RiseSet",
]

REFERENCES = ("centre", "upper_limb")
REFRACTIONS = ("none", "iae_general", "iae_india")
DIPS = ("none", "depression", "sensible_horizon", "geometric")
_ARCMIN = pi / (180 * 60)
_METRES_PER_KM = 1000


@dataclass(frozen=True, slots=True)
class ModernObserver:
    """A place as the modern engine takes it: geodetic latitude, east longitude, height."""

    id: str
    latitude_deg: Fraction
    longitude_deg: Fraction
    height_m: Fraction
    flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("latitude_deg", "longitude_deg", "height_m"):
            if not isinstance(getattr(self, name), Fraction):
                raise TypeError(f"an observer's {name} is a Fraction")
        if not -90 <= self.latitude_deg <= 90 or not -180 <= self.longitude_deg <= 180:
            raise ValueError(f"observer {self.id}: latitude or longitude out of range")


@dataclass(frozen=True, slots=True)
class Event:
    """The rise/set event definition, every term named."""

    reference: str
    refraction: str
    dip: str
    dip_height_m: Fraction | None

    def __post_init__(self) -> None:
        if self.reference not in REFERENCES:
            raise ValueError(f"event reference {self.reference!r} not in {REFERENCES}")
        if self.refraction not in REFRACTIONS:
            raise ValueError(f"event refraction {self.refraction!r} not in {REFRACTIONS}")
        if self.dip not in DIPS:
            raise ValueError(f"event dip {self.dip!r} not in {DIPS}")
        if (self.dip == "none") != (self.dip_height_m is None):
            raise ValueError("a dip names its height above the ground, and only a dip does")
        if self.dip_height_m is not None and self.dip_height_m < 0:
            raise ValueError("a dip height is not negative")

    @property
    def id(self) -> str:
        dip = "none" if self.dip == "none" else f"{self.dip}:{self.dip_height_m}m"
        return f"{self.reference}/{self.refraction}/{dip}"


class RiseSet:
    """Rise and set of a body at one observer under one event definition (module docstring)."""

    def __init__(
        self,
        frame: Frame,
        apparent: Apparent,
        data: Mapping[str, Record],
        event: Event,
        observer: ModernObserver,
        ut1_of: Callable[[TT], UT1],
        roots: RootFinder,
    ) -> None:
        self.frame = frame
        self.apparent = apparent
        self.event = event
        self.observer = observer
        self.ut1_of = ut1_of
        self.roots = roots
        self._data = data
        a = float(datum_value(data, "modern.constants.earth_equatorial_radius")) / _METRES_PER_KM
        f = float(datum_value(data, "modern.constants.earth_flattening"))
        e2 = 2 * f - f * f
        phi = np.radians(float(observer.latitude_deg))
        lam = np.radians(float(observer.longitude_deg))
        h = float(observer.height_m) / _METRES_PER_KM
        n = a / sqrt(1 - e2 * np.sin(phi) ** 2)
        self._itrs = np.array(
            [
                (n + h) * np.cos(phi) * np.cos(lam),
                (n + h) * np.cos(phi) * np.sin(lam),
                (n * (1 - e2) + h) * np.sin(phi),
            ]
        )
        self._up = np.array([np.cos(phi) * np.cos(lam), np.cos(phi) * np.sin(lam), np.sin(phi)])
        self._fixed = self._fixed_depression()

    def _fixed_depression(self) -> float:
        """Refraction and dip in radians (the semidiameter is added per body)."""
        ev = self.event
        out = 0.0
        if ev.refraction != "none":
            key = f"modern.refraction.{ev.refraction}.horizontal"
            out += float(datum_value(self._data, key)) * _ARCMIN
        if ev.dip != "none":
            assert ev.dip_height_m is not None
            coeff = float(datum_value(self._data, f"modern.dip.iae.{ev.dip}"))
            out += coeff * sqrt(float(ev.dip_height_m)) * _ARCMIN
        return out

    def observer_gcrs(self, tt: TT) -> tuple[Vector, Vector, Vector]:
        """The observer's geocentric position (km), velocity (km/day) and vertical, GCRS."""
        t = self.frame.scales.centuries(tt)
        _, m = self.frame.state(t)
        gst = self.frame.gst(self.ut1_of(tt), tt)
        rot = r3(-gst)
        pos_true = rot @ self._itrs
        omega = np.array([0.0, 0.0, self.frame.rotation_rate()])
        vel_true = np.cross(omega, pos_true)
        up_true = rot @ self._up
        return m.T @ pos_true, m.T @ vel_true, m.T @ up_true

    def semidiameter(self, body: str, distance_km: float) -> float:
        if self.event.reference == "centre":
            return 0.0
        if body == "sun":
            return float(datum_value(self._data, "modern.sun.semidiameter.iae")) * _ARCMIN
        radius = float(datum_value(self._data, f"modern.constants.radius.{body}"))
        return asin(radius / distance_km)

    def altitude(self, body: str, tt: TT) -> tuple[float, float]:
        """The topocentric geometric altitude of the body's centre and the event's threshold."""
        pos, vel, up = self.observer_gcrs(tt)
        p = self.apparent.place(body, tt, observer=(pos, vel))
        alt = asin(float(np.clip(p.direction @ up, -1.0, 1.0)))
        return alt, -(self._fixed + self.semidiameter(body, p.distance_km))

    def events(self, body: str, start: TT, end: TT) -> list[tuple[TT, str]]:
        """Every rise and set of ``body`` in [start, end), in order: ``(instant, 'rise'|'set')``."""

        def f(t: TT) -> float:
            alt, threshold = self.altitude(body, t)
            return alt - threshold

        return [(t, "rise" if s > 0 else "set") for t, s in self.roots.crossings(f, start, end)]
