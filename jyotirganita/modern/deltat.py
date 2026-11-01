"""ΔT = TT − UT1 models, each refused outside its stated range.

Registered models (:data:`MODELS`), each selectable by id and none a
default:

- ``iers``: the IERS EOP 20 C04 daily series of UT1 − UTC
  (``data/tables/iers_eop_c04.yaml``, sampled at 0h UTC) with the
  leap-second table: ΔT = (TT − TAI) + (TAI − UTC) − (UT1 − UTC).
  UT1 − TAI is interpolated linearly between the daily values (it is
  continuous across a leap second, where UT1 − UTC is not). Range: the
  series' first day to its cut-off, both at 0h UTC; a later instant is
  refused naming the cut-off (the series is frozen within a major line).
- ``smh2016``: the Stephenson–Morrison–Hohenkerk 2016 spline, Table S15
  of the paper's supplement (``data/tables/deltat_smh2016.yaml``),
  evaluated as the supplement's §S5 states (the row with K_i ≤ Y ≤ K_i+1,
  equality at the top only for the table's last year; t = (Y − K_i)/
  (K_i+1 − K_i); ΔT = a0 + a1 t + a2 t² + a3 t³). Range: the table's own
  interval, from the first row's K_i to the last row's K_i+1, which its
  title states; the paper's title (``modern.deltat.smh2016.range``) names
  the same span in historical years.
- ``em2006``: the Espenak–Meeus 2006 polynomials
  (``data/tables/deltat_em2006.yaml``), each segment over the years its
  heading states, on the interval the page states (−1999 to +3000).
- ``constant`` (a number of seconds named by the caller) and ``zero``:
  for sensitivity studies; they state no range and
  serve every date, and provenance says which was used.

The decimal year Y of ``smh2016`` and ``em2006`` is the engine's
continuous argument 2000 + (JD_TT − 2451545)/365.25 (``modern/
timescales.py``): E–M's own y = year + (month − 0.5)/12
steps monthly, and SMH states none. There is no
composite model, no fallback and no extrapolation: a request outside a
model's range is :class:`~jyotirganita.modern.timescales.OutOfRange`,
naming the model and its range.

**Tidal acceleration**. Each model reports the lunar
tidal acceleration its source states (``smh2016``: the datum
``modern.deltat.smh2016.tidal_acceleration``; ``em2006``: the page's
statement, copied into its extract), and the kernel's is a recorded gap
(``modern.kernel.de440.tidal_acceleration``): the correction a source
gives for a different value is therefore not applied, and provenance
says so (:meth:`DeltaTModel.provenance`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Protocol

import numpy as np

from jyotirganita.core.types import TT, UT1, UTC, FloatDays, tt_from_ut1
from jyotirganita.data.datum import Record
from jyotirganita.modern.tables import FetchedTable, load_table, number
from jyotirganita.modern.timescales import SECONDS_PER_DAY, OutOfRange, TimeScales

__all__ = [
    "MODELS",
    "ConstantDeltaT",
    "DeltaTModel",
    "EspenakMeeus2006",
    "IersDeltaT",
    "Smh2016",
    "make_model",
    "tt_of_ut1",
]

MODELS = ("iers", "smh2016", "em2006", "constant", "zero")
KERNEL_TIDAL_GAP = "modern.kernel.{kernel}.tidal_acceleration"


class DeltaTModel(Protocol):
    """A ΔT model: its id, its stated range, and ΔT in seconds at a TT instant."""

    @property
    def id(self) -> str: ...

    @property
    def range_text(self) -> str:
        """The range as the source states it, for messages and provenance."""
        ...

    def range_tt(self) -> tuple[TT | None, TT | None]:
        """The range's ends as TT instants (``None``: no end stated)."""
        ...

    def delta_t(self, t: TT) -> float:
        """ΔT in seconds at ``t`` (:class:`OutOfRange` outside the range)."""
        ...

    def provenance(self, kernel: str) -> dict[str, Any]:
        """The model's id, range, table and tidal-acceleration record for a run's provenance."""
        ...


def _tidal_note(kernel: str) -> str:
    return (
        f"the kernel's lunar tidal acceleration is a recorded gap "
        f"({KERNEL_TIDAL_GAP.format(kernel=kernel)}); no correction for a different "
        "value is applied"
    )


class IersDeltaT:
    """ΔT from the IERS series and the leap-second table (module docstring)."""

    id = "iers"

    def __init__(self, scales: TimeScales, table: FetchedTable | None = None) -> None:
        self.scales = scales
        self.table = table or load_table("iers_eop_c04")
        t = self.table
        self.first_mjd = int(t["first_mjd"])
        self.last_mjd = int(t["last_mjd"])
        self.cutoff_mjd = int(t["cutoff_mjd"])
        if not self.first_mjd <= self.cutoff_mjd <= self.last_mjd:
            # the cut-off lies in the series, or _interp would extrapolate
            raise OutOfRange(f"{t.path.name}: the cut-off MJD lies outside the series")
        values = [number(v) for v in t["ut1_minus_utc"]]
        if len(values) != self.last_mjd - self.first_mjd + 1:
            raise OutOfRange(f"{t.path.name}: {len(values)} values for its MJD span")
        leap = scales.leap
        # UT1 − TAI at each day's 0h UTC, continuous across a leap second
        self._ut1_tai = np.array(
            [
                v - leap.tai_minus_utc(self._utc_of_mjd(self.first_mjd + i))
                for i, v in enumerate(values)
            ]
        )
        self._ut1_utc = np.array(values)
        self._tt_lo, self._tt_hi = self.range_tt()

    def _utc_of_mjd(self, mjd: float) -> UTC:
        off = self.scales.leap.mjd_offset
        whole = int(off)
        return UTC(whole, float(off - whole) + mjd)

    @property
    def range_text(self) -> str:
        return (
            f"IERS EOP 20 C04 from MJD {self.first_mjd} to the cut-off MJD {self.cutoff_mjd} "
            "(0h UTC)"
        )

    def range_tt(self) -> tuple[TT | None, TT | None]:
        s = self.scales
        return (
            s.tt_from_utc(self._utc_of_mjd(self.first_mjd)),
            s.tt_from_utc(self._utc_of_mjd(self.cutoff_mjd)),
        )

    def _mjd_of(self, t: UTC) -> float:
        mjd = self.scales.leap.mjd(t.jd_whole, t.jd_fraction)
        if mjd < self.first_mjd or mjd > self.cutoff_mjd:
            raise OutOfRange(
                f"ΔT model iers: UTC MJD {mjd:.5f} is outside {self.range_text}; the series is "
                "not extrapolated"
            )
        return mjd

    def _interp(self, arr: np.ndarray, mjd: float) -> float:
        x = mjd - self.first_mjd
        i = min(int(np.floor(x)), len(arr) - 1)
        f = x - i
        if f == 0.0 or i == len(arr) - 1:
            return float(arr[i])
        return float(arr[i] + (arr[i + 1] - arr[i]) * f)

    def ut1_minus_utc(self, t: UTC) -> float:
        """UT1 − UTC in seconds at ``t`` (UT1 − TAI interpolated, then TAI − UTC added)."""
        mjd = self._mjd_of(t)
        return self._interp(self._ut1_tai, mjd) + self.scales.leap.tai_minus_utc(t)

    def delta_t(self, t: TT) -> float:
        lo, hi = self._tt_lo, self._tt_hi
        assert lo is not None and hi is not None
        if t < lo or hi < t:
            raise OutOfRange(
                f"ΔT model iers: TT JD {t.jd_whole + t.jd_fraction:.5f} is outside "
                f"{self.range_text}; the series is not extrapolated"
            )
        utc = self.scales.utc_from_tt(t)
        mjd = self._mjd_of(utc)
        return float(self.scales.tt_minus_tai_s) - self._interp(self._ut1_tai, mjd)

    def daily_ut1_minus_utc(self) -> tuple[tuple[int, float], ...]:
        """The series as shipped: (MJD, UT1 − UTC in seconds) per day."""
        return tuple((self.first_mjd + i, float(v)) for i, v in enumerate(self._ut1_utc))

    def provenance(self, kernel: str) -> dict[str, Any]:
        return {
            "model": self.id,
            "range": self.range_text,
            "table": {"source": self.table.source, "sha256": self.table.fetched_sha256},
            "series": str(self.table["series"]),
            "cutoff_mjd": self.cutoff_mjd,
            "tidal_acceleration": "observed series (no lunar ephemeris assumed)",
        }


class Smh2016:
    """The SMH 2016 spline (module docstring)."""

    id = "smh2016"

    def __init__(
        self,
        scales: TimeScales,
        data: Mapping[str, Record],
        table: FetchedTable | None = None,
    ) -> None:
        self.scales = scales
        self.table = table or load_table("deltat_smh2016")
        if list(self.table["columns"]) != ["i", "K_i", "K_i1", "a0", "a1", "a2", "a3"]:
            raise OutOfRange(f"{self.table.path.name}: unexpected columns")
        self.rows = tuple(tuple(number(c) for c in r[1:]) for r in self.table["rows"])
        for a, b in zip(self.rows, self.rows[1:], strict=False):
            if a[1] != b[0]:
                raise OutOfRange(f"{self.table.path.name}: rows do not join at {a[1]}")
        self.lo, self.hi = self.rows[0][0], self.rows[-1][1]
        rec = data["modern.deltat.smh2016.tidal_acceleration"]
        self.tidal = Fraction(str(rec.value))
        self.range_key = "modern.deltat.smh2016.range"
        if self.range_key not in data:
            raise KeyError(f"{self.range_key} does not load")

    @property
    def range_text(self) -> str:
        return f"{self.table['title']} (decimal years {self.lo} to {self.hi})"

    def range_tt(self) -> tuple[TT | None, TT | None]:
        return self.scales.tt_of_decimal_year(self.lo), self.scales.tt_of_decimal_year(self.hi)

    def at_year(self, y: float) -> float:
        """ΔT in seconds at decimal year ``y`` by §S5 (module docstring)."""
        if not (self.lo <= y <= self.hi):
            raise OutOfRange(
                f"ΔT model smh2016: decimal year {y:.4f} is outside {self.range_text}; no "
                "extrapolation"
            )
        for k0, k1, a0, a1, a2, a3 in self.rows:
            if k0 <= y < k1 or (y == k1 == self.hi):
                t = (y - k0) / (k1 - k0)
                return a0 + t * (a1 + t * (a2 + t * a3))
        raise OutOfRange(f"ΔT model smh2016: no row for {y}")

    def delta_t(self, t: TT) -> float:
        return self.at_year(self.scales.decimal_year(t))

    def provenance(self, kernel: str) -> dict[str, Any]:
        return {
            "model": self.id,
            "range": self.range_text,
            "range_datum": self.range_key,
            "table": {"source": self.table.source, "sha256": self.table.fetched_sha256},
            "tidal_acceleration": {
                "datum": "modern.deltat.smh2016.tidal_acceleration",
                "arcsec_per_cy2": str(self.tidal),
            },
            "tidal_correction": _tidal_note(kernel),
        }


@dataclass(frozen=True, slots=True)
class _Segment:
    lo: float | None
    hi: float | None
    polys: tuple[tuple[float, float, tuple[tuple[float, int], ...]], ...]


class EspenakMeeus2006:
    """The Espenak–Meeus 2006 polynomials (module docstring)."""

    id = "em2006"

    def __init__(self, scales: TimeScales, table: FetchedTable | None = None) -> None:
        self.scales = scales
        self.table = table or load_table("deltat_em2006")
        iv = self.table["interval"]
        self.lo, self.hi = number(iv["from_year"]), number(iv["to_year"])
        segs = []
        for s in self.table["segments"]:
            polys = tuple(
                (
                    number(p["variable"]["offset"]),
                    number(p["variable"]["scale"]),
                    tuple((number(c), int(k)) for c, k in p["terms"]),
                )
                for p in s["polynomials"]
            )
            lo = None if s["from_year"] is None else number(s["from_year"])
            hi = None if s["to_year"] is None else number(s["to_year"])
            segs.append(_Segment(lo, hi, polys))
        self.segments = tuple(segs)

    @property
    def range_text(self) -> str:
        return f"Espenak–Meeus 2006, the interval {self.lo:g} to {self.hi:+g} the page states"

    def range_tt(self) -> tuple[TT | None, TT | None]:
        return self.scales.tt_of_decimal_year(self.lo), self.scales.tt_of_decimal_year(self.hi)

    def at_year(self, y: float) -> float:
        """ΔT in seconds at decimal year ``y`` (the segment whose heading covers it)."""
        if not (self.lo <= y <= self.hi):
            raise OutOfRange(
                f"ΔT model em2006: decimal year {y:.4f} is outside {self.range_text}; no "
                "extrapolation"
            )
        for seg in self.segments:
            above = seg.lo is None or y >= seg.lo
            below = seg.hi is None or y < seg.hi
            if above and below:
                total = 0.0
                for offset, scale, terms in seg.polys:
                    u = (y - offset) / scale
                    total += sum(c * u**k for c, k in terms)
                return total
        raise OutOfRange(f"ΔT model em2006: no segment for {y}")

    def delta_t(self, t: TT) -> float:
        return self.at_year(self.scales.decimal_year(t))

    def provenance(self, kernel: str) -> dict[str, Any]:
        return {
            "model": self.id,
            "range": self.range_text,
            "table": {"source": self.table.source, "sha256": self.table.fetched_sha256},
            "tidal_acceleration": " ".join(self.table["tidal_statement"][:2]),
            "tidal_correction": _tidal_note(kernel),
        }


class ConstantDeltaT:
    """A constant ΔT named by the caller (``zero``: 0 s), for sensitivity studies."""

    def __init__(self, seconds: Fraction, model_id: str) -> None:
        self.seconds = Fraction(seconds)
        self._id = model_id

    @property
    def id(self) -> str:
        return self._id

    @property
    def range_text(self) -> str:
        return "no range stated (a sensitivity setting)"

    def range_tt(self) -> tuple[TT | None, TT | None]:
        return None, None

    def delta_t(self, t: TT) -> float:
        return float(self.seconds)

    def provenance(self, kernel: str) -> dict[str, Any]:
        return {"model": self._id, "seconds": str(self.seconds), "range": self.range_text}


def make_model(
    model_id: str,
    scales: TimeScales,
    data: Mapping[str, Record],
    *,
    constant_seconds: Fraction | None = None,
) -> DeltaTModel:
    """The ΔT model ``model_id`` (one of :data:`MODELS`; nothing is defaulted)."""
    if model_id not in MODELS:
        raise ValueError(f"no ΔT model {model_id!r} (registered: {', '.join(MODELS)})")
    if (model_id == "constant") != (constant_seconds is not None):
        raise ValueError("ΔT model constant takes its seconds, and only it does")
    if model_id == "iers":
        return IersDeltaT(scales)
    if model_id == "smh2016":
        return Smh2016(scales, data)
    if model_id == "em2006":
        return EspenakMeeus2006(scales)
    if model_id == "zero":
        return ConstantDeltaT(Fraction(0), "zero")
    assert constant_seconds is not None
    return ConstantDeltaT(constant_seconds, "constant")


def tt_of_ut1(model: DeltaTModel, t: UT1) -> tuple[TT, float]:
    """TT of a UT1 instant under ``model``, with the ΔT used (evaluated at the TT found)."""
    approx = tt_from_ut1(t, FloatDays(0.0))
    dt = model.delta_t(approx)
    for _ in range(3):
        tt = tt_from_ut1(t, FloatDays(dt / SECONDS_PER_DAY))
        nxt = model.delta_t(tt)
        if nxt == dt:
            break
        dt = nxt
    return tt_from_ut1(t, FloatDays(dt / SECONDS_PER_DAY)), dt
