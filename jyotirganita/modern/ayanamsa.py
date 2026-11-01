"""Ayanāṃśas of the modern engine.

Every ayanāṃśa is selected by id, with its equinox (``true`` or ``mean``)
named by the caller; nothing is defaulted. A ``true`` ayanāṃśa
is an :class:`~jyotirganita.core.types.Ayanamsa` of kind ``TrueOfDate``
carrying the :class:`NutationIdentity` of the nutation instance passed in,
which must be the one that produced the longitude it will meet (``sidereal_from_tropical`` refuses
any other pairing).

- ``iae_lahiri`` (indian_astronomical_ephemeris 2022, printed pp. 380 and 421): the mean ayanāṃśa is
  the IAE's printed polynomial in T = (JD − 2451545)/36525
  (``modern.ayanamsa.iae_lahiri.mean.c0`` … ``.c5``,
  ``.time_argument``), JD read on TT, the scale of the precession
  polynomial the IAE names as its source (``.mean_statement``); it accumulates precession by that
  polynomial only, whatever
  frame the engine runs. The true ayanāṃśa is mean +
  nutation in longitude (``.true_definition``) with the Δψ of the very
  instance passed in. ``range: unstated``: outside the IAE's own tabulated
  years the polynomial runs as a convention.
- ``citra_180``: Spica at 180° of sidereal longitude (calendar_reform_committee_1955's suggestion,
  ``modern.ayanamsa.citra_180.calendar_reform_committee_1955_statement``), in three parts:
  (1) the star's position of date from the Hipparcos extract
  (``data/tables/hipparcos.yaml``, ICRS at the catalogue epoch its ReadMe
  states, J1991.25), carried by linear space motion with the catalogue's
  proper motions and zero radial velocity (the catalogue gives none); with zero radial velocity the
  parallax does not enter
  the barycentric direction, and the annual parallax (at most the
  catalogue parallax, 12.44 mas) is not applied; (2) its reduction, named
  by the caller: the equinox (true or mean of date) and whether annual
  aberration is applied (``modern/apparent.py``); (3) the type that
  follows, ``TrueOfDate`` with the nutation identity or ``MeanOfDate``.
  No source we hold states the reduction (calendar_reform_committee_1955 states none); the presets'
  choice is declared in their headers.
- ``custom_linear`` and ``custom_polynomial``: scan instruments, exact by
  definition: a polynomial in T (Julian centuries of TT from J2000.0, the
  engine's time argument) with coefficients in arcseconds that the caller
  gives, on the equinox the caller names; ``custom_linear`` takes two.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from fractions import Fraction
from math import pi
from typing import Any, Protocol

import numpy as np

from jyotirganita.core.types import (
    TT,
    AngleUnit,
    Ayanamsa,
    FloatArc,
    MeanOfDate,
    TrueOfDate,
)
from jyotirganita.data.datum import Record
from jyotirganita.modern.angles import ARCSEC
from jyotirganita.modern.apparent import Apparent
from jyotirganita.modern.frames import Frame, Vector
from jyotirganita.modern.nutation import NutationAngles
from jyotirganita.modern.tables import FetchedTable, TableError, load_table, number
from jyotirganita.modern.timescales import TimeScales, datum_value

__all__ = [
    "AYANAMSAS",
    "EQUINOXES",
    "AyanamsaModel",
    "Citra180",
    "CustomPolynomial",
    "IaeLahiri",
    "make_ayanamsa",
]

AYANAMSAS = ("iae_lahiri", "citra_180", "custom_linear", "custom_polynomial")
EQUINOXES = ("true", "mean")
_MILLIARCSEC = ARCSEC / 1000
_HALF_TURN = pi
_IAE = "modern.ayanamsa.iae_lahiri."


class AyanamsaModel(Protocol):
    """An ayanāṃśa bound to its equinox (module docstring)."""

    @property
    def id(self) -> str: ...

    @property
    def equinox(self) -> str: ...

    def at(self, t: TT, nut: NutationAngles | None) -> Ayanamsa[Any]:
        """The ayanāṃśa at TT ``t``; ``nut`` is the instance of the longitude it will meet."""
        ...

    def provenance(self) -> dict[str, Any]: ...


def _check_equinox(equinox: str) -> None:
    if equinox not in EQUINOXES:
        raise ValueError(f"an ayanāṃśa's equinox is one of {EQUINOXES}, not {equinox!r}")


def _typed(
    radians: float, equinox: str, nut: NutationAngles | None, ayanamsa_id: str
) -> Ayanamsa[Any]:
    arc = FloatArc(float(np.degrees(radians)), AngleUnit.DEGREE)
    if equinox == "true":
        if nut is None:
            raise ValueError(f"{ayanamsa_id} on the true equinox needs the nutation instance")
        return Ayanamsa(arc, TrueOfDate, nut.identity, ayanamsa_id)
    if nut is not None:
        raise ValueError(f"{ayanamsa_id} on the mean equinox takes no nutation")
    return Ayanamsa(arc, MeanOfDate, None, ayanamsa_id)


class _Poly:
    """A polynomial in T with coefficients in arcseconds, summed in float."""

    def __init__(self, coefficients: Sequence[Fraction]) -> None:
        self._c = tuple(float(c) * ARCSEC for c in coefficients)

    def __call__(self, t: float) -> float:
        out = 0.0
        for c in reversed(self._c):
            out = out * t + c
        return out


class IaeLahiri:
    """The IAE's ayanāṃśa: its printed polynomial, plus Δψ when true (module docstring)."""

    id = "iae_lahiri"

    def __init__(self, data: Mapping[str, Record], scales: TimeScales, equinox: str) -> None:
        _check_equinox(equinox)
        self.equinox = equinox
        self.scales = scales
        c0 = (
            datum_value(data, _IAE + "mean.c0.degrees") * 3600
            + datum_value(data, _IAE + "mean.c0.arcminutes") * 60
            + datum_value(data, _IAE + "mean.c0.arcseconds")
        )
        rest = [datum_value(data, _IAE + f"mean.c{k}") for k in range(1, 6)]
        self._poly = _Poly([c0, *rest])

    def mean_radians(self, t: TT) -> float:
        """The mean ayanāṃśa at TT ``t`` in radians, by the printed polynomial only."""
        return self._poly(self.scales.centuries(t))

    def at(self, t: TT, nut: NutationAngles | None) -> Ayanamsa[Any]:
        value = self.mean_radians(t)
        if self.equinox == "true":
            if nut is None:
                raise ValueError("iae_lahiri on the true equinox needs the nutation instance")
            value += nut.dpsi
        return _typed(value, self.equinox, nut, self.id)

    def provenance(self) -> dict[str, Any]:
        return {
            "ayanamsa": self.id,
            "equinox": self.equinox,
            "data": _IAE + "mean.*",
            "range": "unstated",
        }


_EPOCH = re.compile(r"Epoch=J(\d+(?:\.\d+)?)\)")


def _catalogue_epoch(table: FetchedTable) -> float:
    """The catalogue epoch stated in the ReadMe lines of the position columns."""
    epochs = {m.group(1) for line in table["readme_lines"] for m in _EPOCH.finditer(line)}
    if len(epochs) != 1:
        raise TableError(f"{table.path.name}: the ReadMe states {len(epochs)} epochs, not one")
    return float(Fraction(epochs.pop()))


class Citra180:
    """Spica at 180° under a named reduction (module docstring)."""

    id = "citra_180"

    def __init__(
        self,
        frame: Frame,
        apparent: Apparent,
        equinox: str,
        aberration: bool,
        table: FetchedTable | None = None,
    ) -> None:
        _check_equinox(equinox)
        if not isinstance(aberration, bool):
            raise TypeError("citra_180's aberration is named: true or false")
        tab = table or load_table("hipparcos")
        star = tab["stars"]["spica"]
        units = {k: star[k]["unit"] for k in ("RAICRS", "DEICRS", "pmRA", "pmDE")}
        if units != {"RAICRS": "deg", "DEICRS": "deg", "pmRA": "mas/yr", "pmDE": "mas/yr"}:
            raise TableError(f"{tab.path.name}: Spica's columns are not in the units expected")
        self.frame = frame
        self.apparent = apparent
        self.equinox = equinox
        self.aberration = aberration
        self.table = tab
        self.epoch_year = _catalogue_epoch(tab)
        a = np.radians(number(star["RAICRS"]["value"]))
        d = np.radians(number(star["DEICRS"]["value"]))
        self._p = np.array([np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d)])
        e_a = np.array([-np.sin(a), np.cos(a), 0.0])
        e_d = np.array([-np.sin(d) * np.cos(a), -np.sin(d) * np.sin(a), np.cos(d)])
        mu_a = number(star["pmRA"]["value"]) * _MILLIARCSEC  # μα cos δ, per Julian year
        mu_d = number(star["pmDE"]["value"]) * _MILLIARCSEC
        self._mu = mu_a * e_a + mu_d * e_d

    def direction(self, t: TT) -> Vector:
        """Spica's direction at TT ``t`` (GCRS), aberrated or not as the reduction names."""
        years = self.frame.scales.decimal_year(t) - self.epoch_year
        u = self._p + self._mu * years
        u = u / np.linalg.norm(u)
        if self.aberration:
            _, ve = self.apparent.earth(t)
            beta = ve / self.apparent.c_km_per_day
            u = u + beta - float(u @ beta) * u
            u = u / np.linalg.norm(u)
        out: Vector = u
        return out

    def longitude(self, t: TT) -> tuple[float, NutationAngles | None]:
        """Spica's longitude of date (radians) on the named equinox, with the nutation used."""
        tc = self.frame.scales.centuries(t)
        u = self.direction(t)
        if self.equinox == "true":
            lon, _lat, nut = self.frame.true_ecliptic(u, tc)
            return lon, nut
        lon, _lat = self.frame.mean_ecliptic(u, tc)
        return lon, None

    def at(self, t: TT, nut: NutationAngles | None) -> Ayanamsa[Any]:
        lon, own = self.longitude(t)
        if self.equinox == "true":
            if nut is None or own is None or own != nut:
                raise ValueError(
                    "citra_180 on the true equinox meets only the frame's own nutation"
                )
        elif nut is not None:
            raise ValueError("citra_180 on the mean equinox takes no nutation")
        return _typed(lon - _HALF_TURN, self.equinox, nut, self.id)

    def provenance(self) -> dict[str, Any]:
        return {
            "ayanamsa": self.id,
            "equinox": self.equinox,
            "aberration": self.aberration,
            "catalogue": {"source": self.table.source, "sha256": self.table.fetched_sha256},
            "epoch": f"J{self.epoch_year}",
            "space_motion": "linear, zero radial velocity; annual parallax not applied",
        }


class CustomPolynomial:
    """A scan instrument: a caller's polynomial in T, arcseconds, on a named equinox."""

    def __init__(
        self,
        ayanamsa_id: str,
        scales: TimeScales,
        equinox: str,
        coefficients: Sequence[Fraction],
    ) -> None:
        _check_equinox(equinox)
        if ayanamsa_id not in ("custom_linear", "custom_polynomial"):
            raise ValueError(f"not a custom ayanāṃśa: {ayanamsa_id!r}")
        coeffs = tuple(coefficients)
        if not coeffs or not all(isinstance(c, Fraction) for c in coeffs):
            raise TypeError("a custom ayanāṃśa's coefficients are Fractions (arcseconds)")
        if ayanamsa_id == "custom_linear" and len(coeffs) != 2:
            raise ValueError(
                "custom_linear takes two coefficients: the value at J2000.0 and the rate"
            )
        self.id = ayanamsa_id
        self.equinox = equinox
        self.scales = scales
        self.coefficients = coeffs
        self._poly = _Poly(coeffs)

    def at(self, t: TT, nut: NutationAngles | None) -> Ayanamsa[Any]:
        return _typed(self._poly(self.scales.centuries(t)), self.equinox, nut, self.id)

    def provenance(self) -> dict[str, Any]:
        return {
            "ayanamsa": self.id,
            "equinox": self.equinox,
            "coefficients_arcsec": [str(c) for c in self.coefficients],
            "time_argument": "Julian centuries of TT from J2000.0",
        }


def make_ayanamsa(
    ayanamsa_id: str,
    *,
    equinox: str,
    data: Mapping[str, Record],
    scales: TimeScales,
    frame: Frame | None = None,
    apparent: Apparent | None = None,
    aberration: bool | None = None,
    coefficients: Sequence[Fraction] | None = None,
) -> AyanamsaModel:
    """The ayanāṃśa ``ayanamsa_id`` (one of :data:`AYANAMSAS`), every choice named."""
    if ayanamsa_id == "iae_lahiri":
        if aberration is not None or coefficients is not None:
            raise ValueError("iae_lahiri takes neither aberration nor coefficients")
        return IaeLahiri(data, scales, equinox)
    if ayanamsa_id == "citra_180":
        if frame is None or apparent is None or aberration is None:
            raise ValueError(
                "citra_180 needs the frame, the apparent-place procedure and its aberration"
            )
        if coefficients is not None:
            raise ValueError("citra_180 takes no coefficients")
        return Citra180(frame, apparent, equinox, aberration)
    if ayanamsa_id in ("custom_linear", "custom_polynomial"):
        if coefficients is None or aberration is not None:
            raise ValueError(f"{ayanamsa_id} takes its coefficients and no aberration")
        return CustomPolynomial(ayanamsa_id, scales, equinox, coefficients)
    raise ValueError(f"unknown ayanāṃśa {ayanamsa_id!r}; registered: {', '.join(AYANAMSAS)}")
