"""Nutation in longitude and obliquity.

Two theories, each selectable by id and none a default:

- ``iau2000a``: the IAU 2000A series in its "IAU 2000_R06" form, the IAU
  2006 adjustments already applied as the tables' headings state (TN36
  tables 5.3a and 5.3b, ``data/tables/nutation_iau2000a.yaml``; chosen
  in place of 2000B, which has no open published table). As the headings state:
  Δψ = Σ [A_i sin ARG + A″_i cos ARG] + Σ [A′_i sin ARG + A″′_i cos ARG] t,
  Δε = Σ [B_i cos ARG + B″_i sin ARG] + Σ [B′_i cos ARG + B″′_i sin ARG] t,
  in microarcseconds, ARG the integer combination of the fourteen
  fundamental arguments of TN36 eqs. (5.43) and (5.44)
  (``data/tables/precession_iau2006.yaml``, ``delaunay`` and
  ``planetary``), which the headings name ("those of the IERS
  Conventions 2003").
- ``iau1980``: the 106-term IAU 1980 series of iau1980_nutation (Table 5.1 of IERS
  Technical Note 21, ``data/tables/nutation_iau1980.yaml``) with that
  edition's own fundamental arguments: Δψ = Σ (A + A′ t) sin ARG,
  Δε = Σ (B + B′ t) cos ARG, in the unit the table states (0.0001″),
  "referred to the mean equator and equinox of date" (its caption).

t is Julian centuries of TT from J2000.0 for both (TN36 p. 22, the
statement ``time_argument``; iau1980_nutation's ``time_argument``).

**Identity.** Each theory carries a :class:`~jyotirganita.core.types.
NutationIdentity` whose ``instance`` is a hash of the extract files it was
built from, so a Δψ is only ever subtracted from a longitude computed with
the same coefficients.

**The mean node.** Ω, the mean longitude of the Moon's ascending node, is
the fifth fundamental argument of the same theory (TN36 eq. 5.43 F5;
iau1980_nutation's F5), so the node a preset names under ``node: mean`` is cited to
the same table as the series.

**Accuracy and range.** Neither theory's source states a range; TN36
states the accuracy of 2000A (the statement ``iau2000a_accuracy``). The
engine records ``range: unstated`` and the preset header says so.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

import numpy as np
from numpy.typing import NDArray

from jyotirganita.core.types import NutationIdentity
from jyotirganita.modern.angles import (
    ARCSEC,
    MICROARCSEC,
    Polynomial,
    evaluate,
    polynomial,
)
from jyotirganita.modern.tables import FetchedTable, TableError, load_table, number

__all__ = ["THEORIES", "NutationAngles", "NutationTheory", "make_nutation"]

THEORIES = ("iau2000a", "iau1980")

#: the argument columns of the 2000A tables, in TN36's order F1 … F14
_ARGS_2000A = ("l", "l'", "F", "D", "Om", "L_Me", "L_Ve", "L_E", "L_Ma", "L_J", "L_Sa", "L_U",
               "L_Ne", "p_A")  # fmt: skip
_POLY_2000A = ("l", "l_prime", "f", "d", "omega")
_PLANETARY = ("l_me", "l_ve", "l_e", "l_ma", "l_j", "l_sa", "l_u", "l_ne", "p_a")
_ARGS_1980 = ("l", "l_prime", "f", "d", "omega")


@dataclass(frozen=True, slots=True)
class NutationAngles:
    """Δψ and Δε in radians at one instant, with the identity of the theory instance."""

    dpsi: float
    deps: float
    identity: NutationIdentity


def _instance(*tables: FetchedTable) -> str:
    h = hashlib.sha256()
    for t in tables:
        h.update(t.name.encode())
        h.update(t.instance.encode())
    return h.hexdigest()


@dataclass(frozen=True, slots=True)
class _Block:
    """One block of a series: argument multipliers and the coefficients in radians."""

    mult: NDArray[np.float64]  # (n, k)
    sin: NDArray[np.float64]  # (n,)
    cos: NDArray[np.float64]  # (n,)
    power: int


def _block(
    block: Mapping[str, Any],
    arg_columns: Sequence[str],
    sin_col: str,
    cos_col: str,
    power: int,
    unit: float,
) -> _Block:
    columns = list(block["columns"])
    rows = list(block["rows"])
    if len(rows) != int(block["terms"]):
        raise TableError(f"the block states {block['terms']} terms and holds {len(rows)}")
    try:
        idx = [columns.index(c) for c in arg_columns]
        si, ci = columns.index(sin_col), columns.index(cos_col)
    except ValueError as exc:
        raise TableError(f"a series block lacks a column: {exc}") from None
    mult = np.array([[float(r[i]) for i in idx] for r in rows], dtype=np.float64)
    s = np.array([number(r[si]) * unit for r in rows], dtype=np.float64)
    c = np.array([number(r[ci]) * unit for r in rows], dtype=np.float64)
    return _Block(mult, s, c, power)


class NutationTheory:
    """A loaded nutation theory: Δψ, Δε and the mean node at a time argument t."""

    def __init__(
        self,
        theory_id: str,
        args: Sequence[Polynomial],
        longitude: Sequence[_Block],
        obliquity: Sequence[_Block],
        tables: Sequence[FetchedTable],
        node_index: int,
    ) -> None:
        self.id = theory_id
        self._args = tuple(args)
        self._lon = tuple(longitude)
        self._obl = tuple(obliquity)
        self._node = node_index
        self.tables = tuple(tables)
        self.identity = NutationIdentity(theory_id, _instance(*tables))

    def arguments(self, t: float) -> NDArray[np.float64]:
        """The fundamental arguments in radians at t (not reduced; the sines reduce them)."""
        return np.array([evaluate(p, t) for p in self._args], dtype=np.float64)

    def angles(self, t: float) -> NutationAngles:
        """Δψ and Δε at t (Julian centuries of TT from J2000.0)."""
        f = self.arguments(t)
        dpsi = 0.0
        for b in self._lon:
            arg = b.mult @ f
            dpsi += float(np.sum(b.sin * np.sin(arg) + b.cos * np.cos(arg))) * t**b.power
        deps = 0.0
        for b in self._obl:
            arg = b.mult @ f
            deps += float(np.sum(b.cos * np.cos(arg) + b.sin * np.sin(arg))) * t**b.power
        return NutationAngles(dpsi, deps, self.identity)

    def mean_node(self, t: float) -> float:
        """Ω, the mean longitude of the Moon's ascending node, in radians in [0, 2π)."""
        return float(np.mod(evaluate(self._args[self._node], t), 2 * np.pi))

    def provenance(self) -> dict[str, object]:
        return {
            "nutation": self.id,
            "instance": self.identity.instance,
            "tables": {
                t.name: {"source": t.source, "sha256": t.fetched_sha256} for t in self.tables
            },
            "range": "unstated",
        }


def _iau2000a() -> NutationTheory:
    series = load_table("nutation_iau2000a")
    fund = load_table("precession_iau2006")
    for key in ("tab5_3a", "tab5_3b"):
        heading = " ".join(series["statements"][key])
        if "(unit microarcsecond;" not in heading:
            raise TableError(f"{series.path.name}: {key} does not state its unit as microarcsecond")
    args = [polynomial(fund["delaunay"][k]) for k in _POLY_2000A]
    args += [polynomial(fund["planetary"][k]) for k in _PLANETARY]
    lon = series["longitude"]
    obl = series["obliquity"]
    longitude = [
        _block(lon["j0"], _ARGS_2000A, "A_i", 'A"_i', 0, MICROARCSEC),
        _block(lon["j1"], _ARGS_2000A, "A'_i", "A\"'_i", 1, MICROARCSEC),
    ]
    obliquity = [
        _block(obl["j0"], _ARGS_2000A, 'B"_i', "B_i", 0, MICROARCSEC),
        _block(obl["j1"], _ARGS_2000A, "B\"'_i", "B'_i", 1, MICROARCSEC),
    ]
    return NutationTheory("iau2000a", args, longitude, obliquity, (series, fund), 4)


_UNIT = re.compile(r"^\s*([0-9.]+)\s+arcsec\s*$")


def _iau1980() -> NutationTheory:
    tab = load_table("nutation_iau1980")
    s = tab["series"]
    m = _UNIT.match(str(s["unit"]))
    if m is None:
        raise TableError(f"{tab.path.name}: the series unit {s['unit']!r} is not '<n> arcsec'")
    unit = float(Fraction(m.group(1))) * ARCSEC
    args = [polynomial(tab["fundamental_arguments"][k]) for k in _ARGS_1980]
    columns = list(s["columns"])
    rows = list(s["rows"])
    if len(rows) != int(s["terms"]):
        raise TableError(f"{tab.path.name}: {s['terms']} terms stated, {len(rows)} held")
    idx = [columns.index(c) for c in _ARGS_1980]
    mult = np.array([[float(r[i]) for i in idx] for r in rows], dtype=np.float64)

    def col(name: str) -> NDArray[np.float64]:
        i = columns.index(name)
        return np.array([number(r[i]) * unit for r in rows], dtype=np.float64)

    zero = np.zeros(len(rows), dtype=np.float64)
    longitude = [_Block(mult, col("a"), zero, 0), _Block(mult, col("a_t"), zero, 1)]
    # Δε = Σ (B + B′ t) cos ARG: the cosine coefficients, no sine part
    obliquity = [_Block(mult, zero, col("b"), 0), _Block(mult, zero, col("b_t"), 1)]
    return NutationTheory("iau1980", args, longitude, obliquity, (tab,), 4)


def make_nutation(theory_id: str) -> NutationTheory:
    """The nutation theory ``theory_id`` (one of :data:`THEORIES`; no default)."""
    if theory_id == "iau2000a":
        return _iau2000a()
    if theory_id == "iau1980":
        return _iau1980()
    raise ValueError(f"unknown nutation theory {theory_id!r}; registered: {', '.join(THEORIES)}")
