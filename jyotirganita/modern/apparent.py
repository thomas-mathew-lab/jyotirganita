"""Apparent geocentric places: light time and annual aberration.

The procedure is the IAE's (indian_astronomical_ephemeris 2022, EXPLANATION, printed pp. 446–447,
PDF 453–454): "the barycentric position of the body at time t − Δt is
combined with the barycentric position of the Earth at time t and then the
correction for annual aberration is applied"
(``modern.apparent.iae.planetary_aberration``).

- **Light time** (``modern.light_time.iae.statement``): Δt is the light
  time over the distance, found by iteration from Δt = 0: the body's
  barycentric position at t − Δt less the Earth's at t, Δt the length of
  that vector over c. The speed of light is ``modern.constants.c``; the
  IAE's own coefficient (days per astronomical unit) is the same quantity
  in its units and is not used. The number of evaluations is the engine
  parameter ``modern.light_time_iterations``.
- **Annual aberration** (``modern.aberration.iae.annual``): the IAE's two
  formulas in α and δ are the first-order displacement of the direction u
  toward the observer's barycentric velocity v, applied here in their
  vector form, u′ = u + v/c − (u·v/c) u, normalised. The IAE states its
  formula to first order and the engine follows it; no relativistic term
  and no gravitational deflection by the Sun is applied, the procedure
  naming none.

The result is a direction in the GCRS (the kernel's frame, ICRF-aligned)
and the light-time distance. Positions are geocentric for every calendar
element (``observer_frame: geocentric``); a topocentric
place, for rise and set and eclipse local circumstances, passes the
observer's geocentric position and velocity, which shift the origin of
both corrections (diurnal parallax and diurnal aberration).

The kernel holds the system barycentre only for Mars, Jupiter and Saturn;
those barycentres stand for the planets (``MARS BARYCENTER`` and the
others, as the kernel's comment area names them).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from jyotirganita.core.types import TT
from jyotirganita.data.datum import Record
from jyotirganita.data.engine_parameters import EngineParameter
from jyotirganita.modern.kernels import Ephemeris
from jyotirganita.modern.timescales import SECONDS_PER_DAY, TimeScales, datum_value

__all__ = ["BODIES", "Apparent", "ApparentPlace"]

Vector = NDArray[np.float64]

#: the engine's body ids and the kernel's names for them
BODIES: Mapping[str, str] = {
    "sun": "SUN",
    "moon": "MOON",
    "mercury": "MERCURY",
    "venus": "VENUS",
    "mars": "MARS BARYCENTER",
    "jupiter": "JUPITER BARYCENTER",
    "saturn": "SATURN BARYCENTER",
}
_METRES_PER_KM = 1000


@dataclass(frozen=True, slots=True)
class ApparentPlace:
    """A body's apparent direction (GCRS unit vector) and its light-time distance (km)."""

    direction: Vector
    distance_km: float
    light_time_days: float


class Apparent:
    """The IAE's apparent-place procedure over a verified kernel (module docstring)."""

    def __init__(
        self,
        ephemeris: Ephemeris,
        scales: TimeScales,
        data: Mapping[str, Record],
        iterations: EngineParameter,
    ) -> None:
        if iterations.key != "modern.light_time_iterations" or iterations.kind != "iteration_cap":
            raise ValueError(
                "the light-time iteration is the engine parameter modern.light_time_iterations"
            )
        if iterations.value.denominator != 1 or iterations.value < 2:
            # one evaluation would return the place at reception, unretarded
            raise ValueError("modern.light_time_iterations is an integer of at least 2")
        self.ephemeris = ephemeris
        self.scales = scales
        self._n = int(iterations.value)
        c = datum_value(data, "modern.constants.c")
        # metres per second to kilometres per day
        self.c_km_per_day = float(c * SECONDS_PER_DAY / _METRES_PER_KM)

    def earth(self, t: TT) -> tuple[Vector, Vector]:
        """The Earth's barycentric position (km) and velocity (km/day) at TT ``t``."""
        jd1, jd2 = self.scales.tdb_parts(t)
        return self.ephemeris.barycentric("EARTH", jd1, jd2)

    def place(
        self,
        body: str,
        t: TT,
        observer: tuple[Vector, Vector] | None = None,
    ) -> ApparentPlace:
        """The apparent place of ``body`` at TT ``t`` (geocentric unless ``observer`` is given).

        ``observer`` is the observer's geocentric position (km) and velocity
        (km/day) in the GCRS; ``None`` is the geocentre.
        """
        try:
            name = BODIES[body]
        except KeyError:
            raise ValueError(f"no body {body!r} (served: {', '.join(BODIES)})") from None
        jd1, jd2 = self.scales.tdb_parts(t)
        pe, ve = self.ephemeris.barycentric("EARTH", jd1, jd2)
        if observer is not None:
            pe = pe + observer[0]
            ve = ve + observer[1]
        c = self.c_km_per_day
        dt = 0.0
        rel = np.zeros(3)
        for _ in range(self._n):
            pb, _vb = self.ephemeris.barycentric(name, jd1, jd2 - dt)
            rel = pb - pe
            dt = float(np.linalg.norm(rel)) / c
        dist = float(np.linalg.norm(rel))
        u = rel / dist
        beta = ve / c
        moved = u + beta - float(u @ beta) * u
        direction: Vector = moved / np.linalg.norm(moved)
        return ApparentPlace(direction, dist, dt)
