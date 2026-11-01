# `modern_de`: the modern reference

**Presets:** `modern_iers`, `modern_smh`, `modern_antiquity`.
**Status:** validated, not corroborated (see [`../verification.md`](../verification.md)):
its models are compared with independent software (the Swiss Ephemeris and ERFA), and the
refraction the Indian Astronomical Ephemeris uses for Indian stations, which every modern
preset's sunrise uses, is confirmed by a second volume of the Ephemeris (2021) and by the
Rāṣṭrīya Pañcāṅga of 1959. Most of its constants have no printed worked example, which the
stricter grade asks for.

## What it is

A modern astronomical computation of the same calendar elements, on the
JPL planetary ephemerides, with each model it uses cited to its
publication. It serves as a reference against which the siddhantic
methods' results can be compared, and for residual studies of
historical records. It is not a reconstruction of any calendar-maker's
practice.

## The presets

| preset | kernel | ΔT | precession / nutation | ayanāṃśa | time | represents |
|---|---|---|---|---|---|---|
| `modern_iers` | DE440 | IERS series | IAU 2006 / IAU 2000A | Lahiri (IAE), true | IST | the Indian Astronomical Ephemeris's calendar computation |
| `modern_smh` | DE440 | Stephenson, Morrison and Hohenkerk 2016 | IAU 2006 / IAU 2000A | Lahiri (IAE), true | local mean time | the same, carried back before the IERS series |
| `modern_antiquity` | DE441 | Stephenson, Morrison and Hohenkerk 2016 | Vondrák, Capitaine and Wallace 2011 / IAU 2000A | Citrā (Spica) at 180° | local mean time | sidereal positions far from the present |

All three are geocentric, take the mean node as Rāhu, and use the
Indian Astronomical Ephemeris's calendar sunrise (the Sun's upper limb,
with refraction). Each preset file states what is a hypothesis: for
example, that a Kerala almanac's sunrise, frame and node are the
Ephemeris's. Each preset refuses an instant outside the stated range of
any model it uses; [verification.md](../verification.md) gives the
resulting date ranges.

## Switches

The modern engine's choices can be changed per run with `--set`. Each
defaults to the preset's value, and a changed one is recorded in the
provenance and flagged on the records:

- `modern.sunrise_event`: the Sun's centre or upper limb; refraction
  none, general or the IAE's Indian value; the dip and the observer's
  height.
- `modern.ayanamsa`: the IAE's Lahiri, Citrā at 180° (with or without
  aberration, true or mean equinox), or a custom linear or polynomial
  one.
- `modern.delta_t`: the IERS series, SMH 2016, Espenak and Meeus 2006,
  a constant, or zero.
- `modern.node`: mean or osculating.

The kernel, precession and nutation stay fixed by the preset.

## What the engine computes

Positions are reduced from the kernel's barycentric states to apparent
geocentric places of date, then to the sidereal frame by the
ayanāṃśa. Ending times are roots found by scanning an absolute grid and
then refining by Brent's method. Day boundaries come from the sunrise
event. Under the Kerala presets, the calendar is assigned by the Kerala
profile's rules.

**Eclipses**, lunar and local solar, are computed by the modern presets
only. Every eclipse result is flagged `provisional:eclipse` until its
comparison with published canons is made.

## Sources

| id | publication |
|---|---|
| indian_astronomical_ephemeris | *The Indian Astronomical Ephemeris* (Positional Astronomy Centre, India Meteorological Department), 2022 |
| vondrak_2011 | J. Vondrák, N. Capitaine and P. Wallace, "New precession expressions, valid for long time intervals", *A&A* 534, A22 (2011), with its corrigendum |
| stephenson_2016 | F. R. Stephenson, L. V. Morrison and C. Y. Hohenkerk, "Measurement of the Earth's rotation: 720 BC to AD 2015", *Proc. R. Soc. A* 472, 20160404 (2016) |
| iau1980_nutation | the IAU 1980 nutation series (IERS Technical Note 21, 1996) |
| calendar_reform_committee_1955 | *Report of the Calendar Reform Committee*, CSIR, New Delhi 1955 |
| rashtriya_panchanga_1959 | *Rāṣṭrīya Pañcāṅga* for 1959, Government of India |

The machine-readable tables (the IERS series, the IAU 2000A and 2006
coefficients, the Espenak–Meeus ΔT polynomials, the SMH 2016 spline and
the Hipparcos extract) are listed with their terms in
[`../../NOTICE`](../../NOTICE).

## What is checked

- The Indian Astronomical Ephemeris's table of the true ayanāṃśa is
  reproduced row by row: 161 of its 164 rows within 0.05″, and 3
  beyond by at most 0.002″, attributed (an inference) to the quantum
  of a printed constant (`tests/authority/test_modern_iae_table.py`).
  The other calendar quantities the preset represents are not compared
  with a printed table here.
- The Vondrák–Capitaine–Wallace paper's test case reproduces with its
  printed coefficients and corrigendum.
- No comparison with independent software is in the test suite in
  1.0.0: the comparisons with the Swiss Ephemeris and ERFA named above
  were made outside it (see "Outside comparisons" in
  [`../verification.md`](../verification.md)).
- Many of the model data have no printed worked example. They rest on
  the published tables they were extracted from, which
  `jyotirganita/data/sources.yaml` lists.
