"""Time scales: UTC, TAI, TT, TDB and UT1.

TT is the modern engine's time base. The time argument of every model the
engine evaluates is counted from J2000.0, 2000 January 1d 12h TT (Julian
date 2451545.0 TT, ``modern.timescales.tdb_minus_tt.epoch_jd``), in Julian
centuries of 36525 days: T = (JD − 2451545)/36525, as indian_astronomical_ephemeris states it for
the IAE polynomial (``modern.ayanamsa.iae_lahiri.time_argument``) and vondrak_2011
for Vondrák's series (``modern.precession.vondrak2011.time_argument``).
The decimal year of the ΔT models is 2000 + 100 T, the Julian year of
that century (the decimal-year reading).

- **UTC → TT.** TT = UTC + (TAI − UTC) + (TT − TAI): TAI − UTC from the
  fetched leap-second table (``data/tables/leap_seconds.yaml``, from the
  first day it lists to the expiry date it states, each row in force from
  its day's 0h UTC), TT − TAI the defined 32.184 s
  (``modern.timescales.tt_minus_tai``, indian_astronomical_ephemeris). A UTC instant before the
  table's first row or on or after its expiry is refused: no leap second is
  invented and none is assumed absent.
- **The modified Julian date.** The table pairs each row's MJD with its
  calendar date, so MJD = JD − (JD of the first row's 0h − its MJD), read
  from the table itself.
- **TDB − TT.** The two periodic terms indian_astronomical_ephemeris states
  (``modern.timescales.tdb_minus_tt.*``: 0.001657 s sin g + 0.000022 s
  sin(L − L_J)); the kernels' argument T_eph is TDB
  (``modern.timescales.teph_tdb.statement``).
- **UT1.** From TT through a named ΔT model (``modern/deltat.py``), or from
  UTC through the IERS series' UT1 − UTC; the conversions are the named
  functions of ``core/types.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction

import numpy as np

from jyotirganita.core.calendar import jdn_from_gregorian
from jyotirganita.core.types import (
    TT,
    UTC,
    FloatDays,
    GregorianDate,
    tt_from_utc,
    utc_from_tt,
)
from jyotirganita.data.datum import Record
from jyotirganita.modern.tables import FetchedTable, load_table

__all__ = [
    "DAYS_PER_CENTURY",
    "J2000_YEAR",
    "SECONDS_PER_DAY",
    "LeapSeconds",
    "OutOfRange",
    "TimeScales",
    "datum_value",
]

#: the Julian century of the time argument (module docstring)
DAYS_PER_CENTURY = 36525
#: the Julian epoch of J2000.0 (module docstring)
J2000_YEAR = 2000
SECONDS_PER_DAY = 86400
YEARS_PER_CENTURY = 100


class OutOfRange(ValueError):
    """A request outside the stated range of a model or table; the range is named."""


def datum_value(data: Mapping[str, Record], key: str) -> Fraction:
    """The exact value of a scalar datum the modern engine reads (a hard error otherwise)."""
    rec = data.get(key)
    if rec is None:
        raise KeyError(f"the modern engine needs the datum {key}, which does not load")
    if rec.status == "gap":
        raise ValueError(f"{key} is a recorded gap; the engine never fills it")
    if not isinstance(rec.value, Fraction | int):
        raise TypeError(f"{key} is not a scalar number")
    return Fraction(rec.value)


@dataclass(frozen=True, slots=True)
class LeapSeconds:
    """The leap-second table: TAI − UTC from each row's day, to the stated expiry."""

    table: FetchedTable
    mjd_offset: Fraction
    first_mjd: int
    rows: tuple[tuple[int, int], ...]
    expires_mjd: int

    @classmethod
    def load(cls, table: FetchedTable | None = None) -> LeapSeconds:
        t = table or load_table("leap_seconds")
        if list(t["columns"]) != ["mjd", "day", "month", "year", "tai_minus_utc_s"]:
            raise OutOfRange(f"{t.path.name}: unexpected columns {t['columns']}")
        raw = [tuple(r) for r in t["rows"]]
        mjd0, d0, m0, y0, _ = raw[0]
        jdn0 = jdn_from_gregorian(GregorianDate(y0, m0, d0)).value
        # the JD of a day's 0h is its JDN − 1/2
        offset = Fraction(jdn0) - Fraction(1, 2) - mjd0
        for mjd, d, m, y, _ in raw:
            jdn = jdn_from_gregorian(GregorianDate(y, m, d)).value
            if Fraction(jdn) - Fraction(1, 2) - mjd != offset:
                raise OutOfRange(f"{t.path.name}: row MJD {mjd} disagrees with its date")
        exp = datetime.strptime(str(t["expires"]), "%d %B %Y").date()
        exp_jdn = jdn_from_gregorian(GregorianDate(exp.year, exp.month, exp.day)).value
        expires = int(Fraction(exp_jdn) - Fraction(1, 2) - offset)
        rows = tuple((int(r[0]), int(r[4])) for r in raw)
        return cls(t, offset, int(mjd0), rows, expires)

    def mjd(self, whole: int, fraction: float) -> float:
        """The modified Julian date of a two-part Julian date."""
        return (whole - float(self.mjd_offset)) + fraction

    def day_of(self, whole: int, fraction: float) -> int:
        """The MJD of the UTC day an instant falls in."""
        return int(np.floor(self.mjd(whole, fraction)))

    def tai_minus_utc(self, t: UTC) -> int:
        """TAI − UTC in seconds at ``t`` (refused before the first row and from the expiry on)."""
        day = self.day_of(t.jd_whole, t.jd_fraction)
        if day < self.first_mjd:
            raise OutOfRange(
                f"UTC MJD {day} precedes the leap-second table's first row (MJD "
                f"{self.first_mjd}, 1972-01-01); TAI − UTC is not defined there"
            )
        if day >= self.expires_mjd:
            raise OutOfRange(
                f"UTC MJD {day} is on or after the leap-second table's stated expiry "
                f"(MJD {self.expires_mjd}, {self.table['expires']})"
            )
        value = self.rows[0][1]
        for mjd, v in self.rows:
            if mjd <= day:
                value = v
        return value

    def covers(self, t: UTC) -> bool:
        day = self.day_of(t.jd_whole, t.jd_fraction)
        return self.first_mjd <= day < self.expires_mjd


class TimeScales:
    """UTC, TT and TDB under the leap-second table and indian_astronomical_ephemeris's definitions
    (module docstring)."""

    def __init__(self, data: Mapping[str, Record], leap: LeapSeconds | None = None) -> None:
        self.leap = leap or LeapSeconds.load()
        self.tt_minus_tai_s = datum_value(data, "modern.timescales.tt_minus_tai")
        self.epoch_jd = datum_value(data, "modern.timescales.tdb_minus_tt.epoch_jd")
        p = "modern.timescales.tdb_minus_tt."
        self._tdb = tuple(
            float(datum_value(data, p + k)) for k in ("a_g", "a_lj", "g0", "g1", "lj0", "lj1")
        )

    @property
    def tt_minus_tai(self) -> FloatDays:
        return FloatDays(float(self.tt_minus_tai_s) / SECONDS_PER_DAY)

    def tt_from_utc(self, t: UTC) -> TT:
        """TT of a UTC instant in the leap-second table's span."""
        tai_utc = FloatDays(self.leap.tai_minus_utc(t) / SECONDS_PER_DAY)
        return tt_from_utc(t, tai_utc, self.tt_minus_tai)

    def utc_from_tt(self, t: TT) -> UTC:
        """UTC of a TT instant (the leap-second step found by iteration)."""
        guess = utc_from_tt(t, FloatDays(0.0), self.tt_minus_tai)
        for _ in range(3):
            tai_utc = FloatDays(self.leap.tai_minus_utc(guess) / SECONDS_PER_DAY)
            nxt = utc_from_tt(t, tai_utc, self.tt_minus_tai)
            if nxt == guess:
                break
            guess = nxt
        return guess

    def centuries(self, t: TT) -> float:
        """T = (JD_TT − 2451545)/36525 (module docstring)."""
        return ((t.jd_whole - float(self.epoch_jd)) + t.jd_fraction) / DAYS_PER_CENTURY

    def days_since_epoch(self, t: TT) -> float:
        """JD_TT − 2451545.0."""
        return (t.jd_whole - float(self.epoch_jd)) + t.jd_fraction

    def decimal_year(self, t: TT) -> float:
        """The decimal year of the ΔT models: 2000 + 100 T."""
        return J2000_YEAR + YEARS_PER_CENTURY * self.centuries(t)

    def tt_of_decimal_year(self, year: float) -> TT:
        """The TT instant of a decimal year (the inverse of :meth:`decimal_year`)."""
        days = (year - J2000_YEAR) / YEARS_PER_CENTURY * DAYS_PER_CENTURY
        whole = int(self.epoch_jd)
        return TT(whole, float(self.epoch_jd - whole) + days)

    def tdb_minus_tt_seconds(self, t: TT) -> float:
        """TDB − TT in seconds by indian_astronomical_ephemeris's two terms (module docstring)."""
        a_g, a_lj, g0, g1, lj0, lj1 = self._tdb
        d = self.days_since_epoch(t)
        g = np.radians(g0 + g1 * d)
        l_lj = np.radians(lj0 + lj1 * d)
        return float(a_g * np.sin(g) + a_lj * np.sin(l_lj))

    def tdb_parts(self, t: TT) -> tuple[float, float]:
        """The kernel argument (TDB, taken as T_eph) as a two-part Julian date."""
        return float(t.jd_whole), t.jd_fraction + self.tdb_minus_tt_seconds(t) / SECONDS_PER_DAY
