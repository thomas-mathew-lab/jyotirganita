"""Precession and frame bias: the matrices from the celestial frame to the equator of date.

Three theories, each selectable by id and none a default. Each
gives the matrix taking a vector's components in the kernels' celestial
frame (the ICRF of the JPL kernels, which TN36 calls the GCRS for a
geocentric vector) to the mean equator and equinox of date
(:meth:`PrecessionTheory.bias_precession`), the mean obliquity of date,
and, with a nutation, the matrix to the true equator and equinox of date
(:meth:`PrecessionTheory.bias_precession_nutation`). t is Julian centuries
of TT from J2000.0 for all three (``modern/timescales.py``).

- ``iau2006``: the Fukushima–Williams angles γ̄, φ̄, ψ̄ and ε_A of TN36
  eq. (5.40) (``data/tables/precession_iau2006.yaml``), "referred
  directly to the GCRS pole and origin without requiring the frame bias to
  be applied separately" (TN36 §5.4.5, p. 7). The matrix is the product of
  the four rotations TN36 §5.4.5 names, R1(−ε)·R3(−ψ)·R1(φ̄)·R3(γ̄),
  with ε = ε_A + Δε and ψ = ψ̄ + Δψ when nutation is applied and
  ε = ε_A, ψ = ψ̄ without it; TN36 calls the transformation from the true
  system to the GCRS Q(t), so this product, taking the GCRS to the true
  system, is read as Q's transpose (the frame
  composition reading).
- ``vondrak2011``: the long-term expressions of vondrak_2011 (Vondrák, Capitaine
  and Wallace 2011), evaluated as the paper's appendix states its
  subroutines ``ltp_PECL``, ``ltp_PEQU``, ``ltp_PMAT`` and ``ltp_PBMAT``
  (A22 pp. 12–18): the ecliptic pole from P_A, Q_A (eq. 8 and Table 1,
  with the corrigendum's C7 of Q_A adopted on the datum), the equator pole
  from X_A, Y_A (eq. 9 and Table 2), the matrix rows the equinox
  (normalised p_equ × p_ecl), p_equ × equinox and p_equ, then the
  first-order frame bias (DX, DE, DR) applied on the right. Nutation, when
  applied, is the classical nutation matrix of iau1980_nutation, transposed to take the
  mean system to the true one: R1(−(ε_A + Δε))·R3(−Δψ)·R1(ε_A), ε_A here
  the angle between Vondrák's two poles. Its range is the ±200 millennia
  the paper states (``modern.precession.vondrak2011.range``).
- ``iau1976``: Lieske's ζ_A, θ_A, z_A and ε_A as iau1980_nutation prints them
  (``data/tables/nutation_iau1980.yaml``, ``precession_iau1976``), the
  "IAU 1980 frame". iau1980_nutation's transformation is
  [CRS] = [P][N] [true] with [P] = R3(ζ_A)·R2(−θ_A)·R3(z_A) and [N] =
  R1(−ε_A)·R3(Δψ)·R1(ε_A + Δε); its CRS is taken as the kernels' frame
  with no bias, as iau1980_nutation applies none (the IAU 1980 frame
  reading).

No theory's range is extended or replaced by another's: a request outside
``vondrak2011``'s stated range is refused, and ``iau2006`` and ``iau1976``
state none (``range: unstated``), so outside their sources' own eras they
run as a stated convention.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

from jyotirganita.core.types import TT
from jyotirganita.data.datum import Record
from jyotirganita.modern.angles import (
    ARCSEC,
    Matrix,
    Polynomial,
    evaluate,
    polynomial,
    r1,
    r2,
    r3,
)
from jyotirganita.modern.nutation import NutationAngles
from jyotirganita.modern.tables import FetchedTable, TableError, load_table, number
from jyotirganita.modern.timescales import OutOfRange, TimeScales, datum_value

__all__ = [
    "THEORIES",
    "Iau1976",
    "Iau2006",
    "PrecessionTheory",
    "Vondrak2011",
    "make_precession",
    "nutation_matrix",
]

THEORIES = ("iau2006", "vondrak2011", "iau1976")


def nutation_matrix(eps_a: float, nut: NutationAngles) -> Matrix:
    """The classical nutation matrix, mean of date to true of date.

    The transpose of iau1980_nutation's [N] = R1(−ε_A)·R3(Δψ)·R1(ε_A + Δε), which takes
    the true system to the mean one.
    """
    return r1(-(eps_a + nut.deps)) @ r3(-nut.dpsi) @ r1(eps_a)


class PrecessionTheory(Protocol):
    """A precession theory (module docstring)."""

    @property
    def id(self) -> str: ...

    @property
    def range_text(self) -> str: ...

    def check(self, t_tt: TT) -> None:
        """Refuse an instant outside the theory's stated range (OutOfRange)."""

    def range_tt(self) -> tuple[TT | None, TT | None]:
        """The stated range's ends as TT instants (``None``: no end stated)."""

    def bias_precession(self, t: float) -> Matrix:
        """Celestial frame → mean equator and equinox of date."""

    def mean_obliquity(self, t: float) -> float:
        """ε_A in radians."""

    def bias_precession_nutation(self, t: float, nut: NutationAngles) -> Matrix:
        """Celestial frame → true equator and equinox of date."""

    def provenance(self) -> dict[str, Any]: ...


class Iau2006:
    """IAU 2006 precession by the Fukushima–Williams angles (module docstring)."""

    id = "iau2006"
    range_text = "unstated (TN36 states no range for the IAU 2006 expressions)"

    def __init__(self, table: FetchedTable | None = None) -> None:
        self.table = table or load_table("precession_iau2006")
        fw = self.table["fukushima_williams"]
        self._eps0 = polynomial(self.table["eps0"])
        self._gamma: Polynomial = polynomial(fw["gamma_bar"])
        self._phi: Polynomial = polynomial(fw["phi_bar"])
        self._psi: Polynomial = polynomial(fw["psi_bar"])
        # ε_A = ε0 + the printed polynomial in t (TN36 eq. 5.40)
        self._eps_a: Polynomial = self._eps0 + polynomial(fw["eps_a"])

    def check(self, t_tt: TT) -> None:
        return None

    def range_tt(self) -> tuple[TT | None, TT | None]:
        return None, None

    def mean_obliquity(self, t: float) -> float:
        return evaluate(self._eps_a, t)

    def _fw(self, t: float, dpsi: float, deps: float) -> Matrix:
        return (
            r1(-(evaluate(self._eps_a, t) + deps))
            @ r3(-(evaluate(self._psi, t) + dpsi))
            @ r1(evaluate(self._phi, t))
            @ r3(evaluate(self._gamma, t))
        )

    def bias_precession(self, t: float) -> Matrix:
        return self._fw(t, 0.0, 0.0)

    def bias_precession_nutation(self, t: float, nut: NutationAngles) -> Matrix:
        return self._fw(t, nut.dpsi, nut.deps)

    def provenance(self) -> dict[str, Any]:
        return {
            "precession": self.id,
            "table": {"source": self.table.source, "sha256": self.table.fetched_sha256},
            "range": self.range_text,
        }


_V = "modern.precession.vondrak2011."


def _arcsec(cell: object) -> float:
    return number(cell) * ARCSEC


class Vondrak2011:
    """Vondrák, Capitaine and Wallace 2011 long-term precession (module docstring)."""

    id = "vondrak2011"

    def __init__(self, data: Mapping[str, Record], scales: TimeScales) -> None:
        self._eps0 = float(datum_value(data, _V + "eps0")) * ARCSEC
        self._pq_poly = self._poly(data, _V + "ecliptic_polynomial")
        self._xy_poly = self._poly(data, _V + "equator_polynomial")
        self._pq_per = self._periodic(data, _V + "ecliptic_periodic")
        self._xy_per = self._periodic(data, _V + "equator_periodic")
        bias = {str(r[0]): _arcsec(r[1]) for r in self._table(data, _V + "frame_bias")}
        dx, de, dr = bias["DX"], bias["DE"], bias["DR"]
        # ltp_PBMAT: RPB = RP · B (A22 p. 18)
        self._bias = np.array([[1.0, dr, -dx], [-dr, 1.0, -de], [dx, de, 1.0]])
        rng = data[_V + "ecliptic_polynomial"].raw.get("range")
        if not isinstance(rng, dict):
            raise TableError(f"{_V}ecliptic_polynomial records no range")
        self._years = (int(rng["from"]["year"]), int(rng["to"]["year"]))
        self._scales = scales
        self.range_text = (
            f"decimal years {self._years[0]} to {self._years[1]} (±200 millennia from J2000.0, "
            f"{_V}range)"
        )

    @staticmethod
    def _table(data: Mapping[str, Record], key: str) -> tuple[tuple[object, ...], ...]:
        rec = data.get(key)
        if rec is None or rec.status == "gap" or not isinstance(rec.value, tuple):
            raise TableError(f"the Vondrák theory needs the table datum {key}")
        return rec.value

    def _poly(self, data: Mapping[str, Record], key: str) -> NDArray[np.float64]:
        rows = sorted(self._table(data, key), key=lambda r: int(str(r[0])))
        if [int(str(r[0])) for r in rows] != list(range(len(rows))):
            raise TableError(f"{key}: the powers are not 0 … n")
        return np.array([[_arcsec(r[1]), _arcsec(r[2])] for r in rows], dtype=np.float64)

    def _periodic(self, data: Mapping[str, Record], key: str) -> NDArray[np.float64]:
        """Rows (period, C and C of the two quantities, S and S of the two)."""
        rows = self._table(data, key)
        out = []
        for c_row, s_row in zip(rows[0::2], rows[1::2], strict=True):
            n = str(c_row[1])[1:]
            if str(c_row[1]) != f"C{n}" or str(s_row[1]) != f"S{n}":
                raise TableError(f"{key}: rows {c_row[1]} and {s_row[1]} are not a C/S pair")
            out.append(
                [number(c_row[4]), _arcsec(c_row[2]), _arcsec(c_row[3]),
                 _arcsec(s_row[2]), _arcsec(s_row[3])]
            )  # fmt: skip
        return np.array(out, dtype=np.float64)

    @staticmethod
    def _series(
        t: float, per: NDArray[np.float64], poly: NDArray[np.float64]
    ) -> tuple[float, float]:
        a = 2 * np.pi * t / per[:, 0]
        c, s = np.cos(a), np.sin(a)
        u = float(np.sum(c * per[:, 1] + s * per[:, 3]))
        v = float(np.sum(c * per[:, 2] + s * per[:, 4]))
        w = t ** np.arange(len(poly))
        return u + float(w @ poly[:, 0]), v + float(w @ poly[:, 1])

    def ecliptic_pole(self, t: float) -> NDArray[np.float64]:
        """``ltp_PECL``: the ecliptic pole in the J2000.0 mean equator and equinox."""
        p, q = self._series(t, self._pq_per, self._pq_poly)
        z = np.sqrt(max(1 - p * p - q * q, 0.0))
        s, c = np.sin(self._eps0), np.cos(self._eps0)
        return np.array([p, -q * c - z * s, -q * s + z * c])

    def equator_pole(self, t: float) -> NDArray[np.float64]:
        """``ltp_PEQU``: the equator pole in the J2000.0 mean equator and equinox."""
        x, y = self._series(t, self._xy_per, self._xy_poly)
        w = x * x + y * y
        return np.array([x, y, np.sqrt(1 - w) if w < 1 else 0.0])

    def precession(self, t: float) -> Matrix:
        """``ltp_PMAT``: J2000.0 mean equator and equinox → mean of date."""
        peq = self.equator_pole(t)
        pec = self.ecliptic_pole(t)
        v = np.cross(peq, pec)
        eqx = v / np.linalg.norm(v)
        return np.array([eqx, np.cross(peq, eqx), peq])

    def range_tt(self) -> tuple[TT | None, TT | None]:
        lo, hi = self._years
        return self._scales.tt_of_decimal_year(lo), self._scales.tt_of_decimal_year(hi)

    def check(self, t_tt: TT) -> None:
        y = self._scales.decimal_year(t_tt)
        if not (self._years[0] <= y <= self._years[1]):
            raise OutOfRange(
                f"precession vondrak2011: decimal year {y:.2f} is outside {self.range_text}; "
                "no other theory is substituted"
            )

    def bias_precession(self, t: float) -> Matrix:
        """``ltp_PBMAT``: the celestial frame (GCRS) → mean of date."""
        out: Matrix = self.precession(t) @ self._bias
        return out

    def mean_obliquity(self, t: float) -> float:
        peq, pec = self.equator_pole(t), self.ecliptic_pole(t)
        return float(np.arctan2(np.linalg.norm(np.cross(peq, pec)), float(peq @ pec)))

    def bias_precession_nutation(self, t: float, nut: NutationAngles) -> Matrix:
        return nutation_matrix(self.mean_obliquity(t), nut) @ self.bias_precession(t)

    def provenance(self) -> dict[str, Any]:
        return {"precession": self.id, "source": "vondrak_2011", "range": self.range_text}


class Iau1976:
    """Lieske's IAU 1976 precession as iau1980_nutation prints it (module docstring)."""

    id = "iau1976"
    range_text = "unstated (iau1980_nutation states no range for Lieske's expressions)"

    def __init__(self, table: FetchedTable | None = None) -> None:
        self.table = table or load_table("nutation_iau1980")
        p = self.table["precession_iau1976"]
        self._zeta = polynomial(p["zeta_a"])
        self._theta = polynomial(p["theta_a"])
        self._z = polynomial(p["z_a"])
        self._eps_a = polynomial(p["eps_a"])

    def check(self, t_tt: TT) -> None:
        return None

    def range_tt(self) -> tuple[TT | None, TT | None]:
        return None, None

    def mean_obliquity(self, t: float) -> float:
        return evaluate(self._eps_a, t)

    def bias_precession(self, t: float) -> Matrix:
        # the transpose of [P] = R3(ζ_A)·R2(−θ_A)·R3(z_A): CRS → mean of date
        z, theta, zeta = (evaluate(p, t) for p in (self._z, self._theta, self._zeta))
        return r3(-z) @ r2(theta) @ r3(-zeta)

    def bias_precession_nutation(self, t: float, nut: NutationAngles) -> Matrix:
        return nutation_matrix(self.mean_obliquity(t), nut) @ self.bias_precession(t)

    def provenance(self) -> dict[str, Any]:
        return {
            "precession": self.id,
            "table": {"source": self.table.source, "sha256": self.table.fetched_sha256},
            "frame_bias": "none (iau1980_nutation applies none)",
            "range": self.range_text,
        }


def make_precession(
    theory_id: str, data: Mapping[str, Record], scales: TimeScales
) -> PrecessionTheory:
    """The precession theory ``theory_id`` (one of :data:`THEORIES`; no default)."""
    if theory_id == "iau2006":
        return Iau2006()
    if theory_id == "vondrak2011":
        return Vondrak2011(data, scales)
    if theory_id == "iau1976":
        return Iau1976()
    raise ValueError(f"unknown precession theory {theory_id!r}; registered: {', '.join(THEORIES)}")
