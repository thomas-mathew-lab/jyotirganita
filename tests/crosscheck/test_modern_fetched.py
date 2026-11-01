"""The fetched catalogue and series as the engine reads them.

Three Stage A items internal to the method's own sources:

- **Hipparcos**: the engine's Spica (``citra_180``; ``modern/ayanamsa.py``)
  read back at the catalogue epoch and a year later agrees with the
  committed extract (``data/tables/hipparcos.yaml``) to the milliarcsecond
  in position and to the printed unit (0.01 mas/yr) in proper motion;
- **the citra_180 invariant**: Spica, carried from the
  extract to the date in this test and referred to the engine's true
  ecliptic and equinox of date, stands at 180° of sidereal longitude
  under ``citra_180``, with and without annual aberration, on seeded days;
- **IERS**: the engine's UT1 − UTC and ΔT at 0h UTC of seeded days are the
  extract's printed values (``data/tables/iers_eop_c04.yaml``,
  ``leap_seconds.yaml``) and ``modern.timescales.tt_minus_tai``.

The extracts were checked against the fetched files themselves (not
committed; the IERS file changes daily at its host) in the development
tree, by a second and independent parse.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from fractions import Fraction
from functools import cache

import numpy as np
import pytest
from modern_kit import data, engine

from jyotirganita.core.exact import parse_fraction
from jyotirganita.core.types import (
    TT,
    UTC,
    AngleUnit,
    FloatArc,
    TropicalLongitude,
    TrueOfDate,
    sidereal_from_tropical,
)
from jyotirganita.data.engine_parameters import seed
from jyotirganita.modern.ayanamsa import Citra180
from jyotirganita.modern.deltat import IersDeltaT
from jyotirganita.modern.tables import load_table
from jyotirganita.modern.timescales import TimeScales

Recorder = Callable[..., None]

MAS_PER_DEGREE = 3600 * 1000
POSITION_MAS = Fraction(1)
MOTION_MAS_YR = Fraction(1, 100)
SAMPLE_DAYS = 50
INVARIANT_DAYS = 6
#: float rounding of an angle near 180° in degrees (a few units in the last place)
ANGLE_ROUNDING_DEG = Fraction(1, 10**9)
#: float rounding of a seconds value of order one (a few units in the last place)
SECONDS_ROUNDING = Fraction(1, 10**9)


def _star() -> dict[str, Fraction]:
    s = load_table("hipparcos")["stars"]["spica"]
    return {k: parse_fraction(str(s[k]["value"])) for k in ("RAICRS", "DEICRS", "pmRA", "pmDE")}


@cache
def _citra(aberration: bool) -> Citra180:
    eng = engine(ayanamsa="citra_180", ayanamsa_equinox="true", ayanamsa_aberration=aberration)
    assert isinstance(eng.ayanamsa, Citra180)
    return eng.ayanamsa


def _radec(u: np.ndarray) -> tuple[float, float]:
    return float(np.degrees(np.arctan2(u[1], u[0])) % 360), float(np.degrees(np.arcsin(u[2])))


def test_the_engine_reads_spica_from_the_extract(record_comparison: Recorder) -> None:
    star = _star()
    c = _citra(False)
    scales = c.frame.scales
    t0 = scales.tt_of_decimal_year(c.epoch_year)
    t1 = scales.tt_of_decimal_year(c.epoch_year + 1)
    ra0, de0 = _radec(c.direction(t0))
    ra1, de1 = _radec(c.direction(t1))
    pm_ra = (ra1 - ra0) * MAS_PER_DEGREE * np.cos(np.radians(de0))
    pm_de = (de1 - de0) * MAS_PER_DEGREE
    got = {"RAICRS": ra0, "DEICRS": de0, "pmRA": float(pm_ra), "pmDE": float(pm_de)}
    record_comparison(
        id="hipparcos/spica/read_back",
        source="hipparcos (VizieR I/239/hip_main, HIP 65474), the committed extract",
        methods=["modern_de"],
        datum_keys=["modern.ayanamsa.citra_180.calendar_reform_committee_1955_statement"],
        printed={k: str(v) for k, v in star.items()},
        computed={k: f"{v:.10f}" for k, v in got.items()},
        tolerance={"position_mas": POSITION_MAS, "motion_mas_per_yr": MOTION_MAS_YR},
        tolerance_reason=(
            "one milliarcsecond in position; the printed unit, 0.01 mas/yr, in proper motion"
        ),
    )
    assert abs(Fraction(ra0) - star["RAICRS"]) * MAS_PER_DEGREE <= POSITION_MAS
    assert abs(Fraction(de0) - star["DEICRS"]) * MAS_PER_DEGREE <= POSITION_MAS
    assert abs(Fraction(float(pm_ra)) - star["pmRA"]) <= MOTION_MAS_YR
    assert abs(Fraction(float(pm_de)) - star["pmDE"]) <= MOTION_MAS_YR


def _spica_independently(c: Citra180, t: TT, aberration: bool) -> np.ndarray:
    """Spica at ``t`` from the extract: linear space motion from the epoch, zero radial velocity,
    annual aberration to first order in v/c when named."""
    star = _star()
    a, d = np.radians(float(star["RAICRS"])), np.radians(float(star["DEICRS"]))
    p = np.array([np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d)])
    e_a = np.array([-np.sin(a), np.cos(a), 0.0])
    e_d = np.array([-np.sin(d) * np.cos(a), -np.sin(d) * np.sin(a), np.cos(d)])
    rad_per_mas = np.radians(1.0) / MAS_PER_DEGREE
    years = c.frame.scales.decimal_year(t) - c.epoch_year
    u = p + (float(star["pmRA"]) * e_a + float(star["pmDE"]) * e_d) * rad_per_mas * years
    u = u / np.linalg.norm(u)
    if aberration:
        beta = c.apparent.earth(t)[1] / c.apparent.c_km_per_day
        u = u + beta - float(u @ beta) * u
        u = u / np.linalg.norm(u)
    return np.asarray(u, dtype=np.float64)


def _invariant_days() -> list[TT]:
    rng = random.Random(seed("seeds.modern_sample"))
    lo, hi = 2415021, 2488070  # JD of 1900-01-01 and 2100-01-01
    return [TT(rng.randrange(lo, hi), 0.0) for _ in range(INVARIANT_DAYS)]


@pytest.mark.parametrize("aberration", [False, True])
def test_citra_180_puts_spica_at_180_degrees(aberration: bool, record_comparison: Recorder) -> None:
    c = _citra(aberration)
    out = []
    for t in _invariant_days():
        u = _spica_independently(c, t, aberration)
        lon, _lat, nut = c.frame.true_ecliptic(u, c.frame.scales.centuries(t))
        trop = TropicalLongitude(FloatArc(float(np.degrees(lon)), AngleUnit.DEGREE), TrueOfDate,
                                 nut.identity)  # fmt: skip
        sid = sidereal_from_tropical(trop, c.at(t, nut))
        out.append(sid.arc.to(AngleUnit.DEGREE).value % 360)
    record_comparison(
        id=f"citra_180/spica_at_180/aberration_{str(aberration).lower()}",
        source="the citra_180 definition (calendar_reform_committee_1955); hipparcos extract",
        methods=["modern_de"],
        datum_keys=["modern.ayanamsa.citra_180.calendar_reform_committee_1955_statement"],
        printed="180",
        computed=[f"{x:.12f}" for x in out],
        tolerance=ANGLE_ROUNDING_DEG,
        tolerance_reason="float rounding of an angle near 180° (a definitional invariant)",
    )
    assert all(abs(Fraction(x) - 180) <= ANGLE_ROUNDING_DEG for x in out)


def test_the_engine_reads_the_iers_series_on_seeded_days(record_comparison: Recorder) -> None:
    d = data()
    scales = TimeScales(d)
    iers = IersDeltaT(scales)
    ext = load_table("iers_eop_c04")
    values = [parse_fraction(str(v)) for v in ext["ut1_minus_utc"]]
    first = int(ext["first_mjd"])
    rng = random.Random(seed("seeds.modern_sample"))
    days = sorted(rng.sample(range(len(values)), SAMPLE_DAYS))
    off = scales.leap.mjd_offset
    whole = int(off)
    got: list[tuple[Fraction, Fraction]] = []
    for i in days:
        utc = UTC(whole, float(off - whole) + first + i)
        tt = scales.tt_from_utc(utc)
        tai_utc = scales.leap.tai_minus_utc(utc)
        want_dt = scales.tt_minus_tai_s + tai_utc - values[i]
        got.append((Fraction(iers.ut1_minus_utc(utc)) - values[i],
                    Fraction(iers.delta_t(tt)) - want_dt))  # fmt: skip
    record_comparison(
        id="iers_eop_c04/read_back",
        source="iers_eop (EOP 20 C04, Leap_Second.dat), the committed extracts",
        methods=["modern_de"],
        datum_keys=["modern.timescales.tt_minus_tai"],
        printed=[f"MJD {first + i}: {values[i]}" for i in days],
        computed=[f"ΔUT1 {float(a):+.2e}, ΔΔT {float(b):+.2e}" for a, b in got],
        tolerance=SECONDS_ROUNDING,
        tolerance_reason="float rounding of a seconds value (the extract prints 1e-7 s)",
    )
    assert all(abs(a) <= SECONDS_ROUNDING and abs(b) <= SECONDS_ROUNDING for a, b in got)
