"""The sunrise rules against the printed examples.

All five examples are ``editor_computed`` (Shukla's and the INSA editors'
notes), so each is compared to the editor's stated precision and every
residual is attributed, never absorbed.

- mahabhaskariya_1960 III.8, Shukla's note (``mahabhaskariya_1960_ch3_ascensional_differences``):
  the
  Rsine of the declination (laghubhaskariya_1963 II.16, the table's Rsine of the text's
  obliquity), the day-radius (its root), and the ascensional difference
  by the earthsine (laghubhaskariya_1963 II.17–18), for a place whose equinoctial midday
  shadow is one aṅgula (a word on the page, not keyed). Compared: every
  intermediate the rule fixes, the numerator and denominator of the
  quotient from the editor's own intermediates, the body's "approx."
  whole asus, fn 1's Aries value and the footnote's own arithmetic. Not
  compared, recorded as residuals: the editor's Rsine of 60°
  (the modern value, not the table's), and fn 1's "better values" for
  Aries + Taurus and Aries + Taurus + Gemini, which the rule reproduces
  neither from the table nor from the editor's printed intermediates to
  the footnote's hundredths.
- aryabhatiya_1976 Gola 25 and laghubhaskariya_1963 III
  (``aryabhatiya_1976_gola25_right_ascensions``,
  ``laghubhaskariya_1963_ch3_rising_times_lanka``): the day-radii, and the right
  ascensions by the editors' formula with the text's Rsines, the
  Rsine of the colatitude of the greatest declination taken as the
  day-radius at the solstice (laghubhaskariya_1963 II.17) rather than the editors' rounded
  multiplier; whole asus as printed, so within one unit.
- laghubhaskariya_1963 III (``laghubhaskariya_1963_ch3_lucknow_rising_times``): the table's own
  arithmetic
  (the rising at Laṅkā less, then plus, the ascensional difference). The
  latitude of Lucknow is not printed on the page, so the engine's
  ascensional differences are not compared.
- mahabhaskariya_1960 VIII.25, Shukla's fn 2 (``mahabhaskariya_1960_ch8_25_latitude_from_night``):
  the
  half-day rule (mahabhaskariya_1960 IV.28) and the earthsine rule, inverted, give the
  latitude of a place with a night of the printed length; the editor's
  answer is reproduced only with twice the rule's ascensional difference, which the test asserts as
  the residual's characterization.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from fractions import Fraction
from functools import cache

import pytest
from authority_kit import printed

from jyotirganita.core.exact import Rounding, round_to
from jyotirganita.methods.compose import REPO, load_method
from jyotirganita.siddhantic.engine import TextModel
from jyotirganita.siddhantic.epicycle import karna
from jyotirganita.siddhantic.sunrise import (
    ascensional_difference,
    day_radius,
    earthsine,
    half_day,
    rsine_declination,
)

Record = Callable[..., None]
FX = "authority/aryabhatiya/"
CH3 = FX + "mahabhaskariya_1960_ch3_ascensional_differences"
GOLA = FX + "aryabhatiya_1976_gola25_right_ascensions"
LANKA = FX + "laghubhaskariya_1963_ch3_rising_times_lanka"
LUCKNOW = FX + "laghubhaskariya_1963_ch3_lucknow_rising_times"
NIGHT = FX + "mahabhaskariya_1960_ch8_25_latitude_from_night"
MINUTES = 60
WHOLE = Fraction(1)
HUNDREDTH = Fraction(1, 100)
EXACT = "exact fractions (the rule's own arithmetic)"
ROUNDED = "the exact value rounded to the whole minute printed"
APPROX = "'approx.' whole asus (editor_computed): within one unit, the print quantum"


@cache
def model() -> TextModel:
    return load_method("aryabhatiya", REPO).text_model


def _rounded(x: Fraction, quantum: Fraction = WHOLE) -> Fraction:
    return round_to(x, quantum, Rounding.HALF_UP)


def _rsin_decl(longitude: int) -> Fraction:
    m = model()
    return rsine_declination(m.table, m.rsin_obliquity, Fraction(longitude))


def _day_radius(rsin_d: Fraction) -> Fraction:
    m = model()
    return day_radius(m.table, rsin_d, m.day_radius_resolution)


# --- mahabhaskariya_1960 III.8: the ascensional differences of Aries, Taurus and Gemini
# -----------------


def _shadow() -> Fraction:
    # the place's equinoctial midday shadow in aṅgulas (mahabhaskariya_1960 p. 66, keyed as a
    # printed input)
    return Fraction(printed(CH3)["input.equinoctial_shadow"])


def _cara(longitude: int) -> Fraction:
    m, fx = model(), printed(CH3)
    s = _rsin_decl(longitude)
    e = earthsine(_shadow(), Fraction(fx["input.aries.f.gnomon"]), s)
    return ascensional_difference(m.table, e, _day_radius(s))


SIGNS = {"aries": 30, "taurus": 60, "gemini": 90}


def _ch3_exact() -> dict[str, tuple[Fraction, str]]:
    fx = printed(CH3)
    out: dict[str, tuple[Fraction, str]] = {}
    for sign, lam in SIGNS.items():
        assert fx[f"input.{sign}.lambda"] == lam
        s = _rsin_decl(lam)
        # the editor prints the exact Rsine where it is a whole or half minute, else rounds it
        rs = s if s.denominator <= 2 else _rounded(s)
        for name in (f"output.{sign}.rsin_declination", f"output.{sign}.f.rsin_declination"):
            out[name] = (rs, EXACT if rs == s else ROUNDED)
        for name in (f"output.{sign}.rcos_declination", f"output.{sign}.f.rcos_declination"):
            out[name] = (
                _rounded(_day_radius(s)),
                ROUNDED + " (the day-radius, laghubhaskariya_1963 II.17)",
            )
    return out


CH3_EXACT = sorted(_ch3_exact())


@pytest.mark.parametrize("value", CH3_EXACT)
def test_mahabhaskariya_1960_ch3_declination_and_day_radius(
    value: str, record_comparison: Record
) -> None:
    computed, reason = _ch3_exact()[value]
    record_comparison(
        fixture=CH3, value=value, computed=computed, tolerance=0, tolerance_reason=reason
    )
    assert computed == printed(CH3)[value]


@pytest.mark.parametrize("sign", ["aries", "gemini"])
@pytest.mark.parametrize("part", ["numerator", "denominator"])
def test_mahabhaskariya_1960_ch3_quotient_from_the_editor_s_intermediates(
    sign: str, part: str, record_comparison: Record
) -> None:
    # earthsine × R ÷ day-radius = (Rsin δ × shadow ÷ gnomon) × R ÷ Rcos δ, written as one quotient
    m, fx = model(), printed(CH3)
    rsin_d = Fraction(fx[f"output.{sign}.f.rsin_declination"])
    rcos_d = Fraction(fx[f"output.{sign}.f.rcos_declination"])
    gnomon = Fraction(fx[f"input.{sign}.f.gnomon"])
    numerator = rsin_d * m.table.radius * _shadow()
    denominator = gnomon * rcos_d
    computed = numerator if part == "numerator" else denominator
    record_comparison(
        fixture=CH3,
        value=f"output.{sign}.{part}",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " from the editor's printed Rsin δ and Rcos δ",
    )
    assert computed == fx[f"output.{sign}.{part}"]
    e = earthsine(_shadow(), gnomon, rsin_d)
    assert e * m.table.radius / rcos_d == numerator / denominator


CUMULATIVE = {"aries": "aries", "aries_taurus": "taurus", "aries_taurus_gemini": "gemini"}


@pytest.mark.parametrize("kind", ["rsin_asc_diff", "asc_diff"])
@pytest.mark.parametrize("span", sorted(CUMULATIVE))
def test_mahabhaskariya_1960_ch3_ascensional_difference_approx(
    span: str, kind: str, record_comparison: Record
) -> None:
    # in the table's first interval the arc equals its Rsine, so both figures are the cara
    computed = _cara(SIGNS[CUMULATIVE[span]])
    value = f"output.{span}.{kind}"
    record_comparison(
        fixture=CH3, value=value, computed=computed, tolerance=1, tolerance_reason=APPROX
    )
    assert abs(computed - printed(CH3)[value]) < 1


@pytest.mark.parametrize(("sign", "previous"), [("taurus", "aries"), ("gemini", "taurus")])
def test_mahabhaskariya_1960_ch3_a_sign_s_share(
    sign: str, previous: str, record_comparison: Record
) -> None:
    computed = _cara(SIGNS[sign]) - _cara(SIGNS[previous])
    value = f"output.{sign}.asc_diff"
    record_comparison(
        fixture=CH3, value=value, computed=computed, tolerance=1, tolerance_reason=APPROX
    )
    assert abs(computed - printed(CH3)[value]) < 1


@pytest.mark.parametrize("value", ["output.fn1.better.aries", "output.fn1.asc_diff.aries"])
def test_mahabhaskariya_1960_ch3_footnote_aries(value: str, record_comparison: Record) -> None:
    computed = _rounded(_cara(SIGNS["aries"]), HUNDREDTH)
    record_comparison(
        fixture=CH3,
        value=value,
        computed=computed,
        tolerance=0,
        tolerance_reason="the exact cara rounded to the hundredth of an asu printed in fn 1",
    )
    assert computed == printed(CH3)[value]


def _footnote_arithmetic() -> dict[str, Fraction]:
    fx = printed(CH3)
    better = [
        Fraction(fx[f"output.fn1.better.{s}"])
        for s in ("aries", "aries_taurus", "aries_taurus_gemini")
    ]
    shares = {"aries": better[0], "taurus": better[1] - better[0], "gemini": better[2] - better[1]}
    out = {f"output.fn1.asc_diff.{s}": v for s, v in shares.items() if s != "aries"}
    out |= {f"output.fn1.four_times.{s}": _rounded(4 * v) for s, v in shares.items()}
    return out


@pytest.mark.parametrize("value", sorted(_footnote_arithmetic()))
def test_mahabhaskariya_1960_ch3_footnote_s_own_arithmetic(
    value: str, record_comparison: Record
) -> None:
    computed = _footnote_arithmetic()[value]
    record_comparison(
        fixture=CH3,
        value=value,
        computed=computed,
        tolerance=0,
        tolerance_reason=(
            "the footnote's own arithmetic from its printed better values (differences; four "
            "times, to the whole asu): an internal check, not the engine"
        ),
    )
    assert computed == printed(CH3)[value]


def test_mahabhaskariya_1960_ch3_the_editor_s_rsine_of_60_is_not_the_table_s(
    record_comparison: Record,
) -> None:
    # a residual, recorded: the table of Gītikā 12 is the text's authority
    fx, t = printed(CH3), model().table
    computed = t.rsine(fx["input.taurus.lambda"] * MINUTES)
    record_comparison(
        fixture=CH3,
        value="output.taurus.rsin_lambda",
        computed=computed,
        tolerance=0,
        tolerance_reason=(
            "NOT reproduced: the table's Rsine of 60°; the editor prints the "
            "modern value, 3438 sin 60° to the whole minute (checked here with math.sin)"
        ),
    )
    assert computed != fx["output.taurus.rsin_lambda"]
    modern = round(int(t.radius) * math.sin(math.radians(fx["input.taurus.lambda"])))
    assert modern == fx["output.taurus.rsin_lambda"]


# --- aryabhatiya_1976 Gola 25 and laghubhaskariya_1963 III: day-radii and right ascensions at Laṅkā
# -------------------


def _right_ascension(longitude: int) -> Fraction:
    """The editors' formula, Rsin α = Rsin λ × Rcos ε ÷ Rcos δ, with the text's Rsines."""
    t = model().table
    rcos_eps = _day_radius(_rsin_decl(90))
    rsin_a = t.rsine(longitude * MINUTES) * rcos_eps / _day_radius(_rsin_decl(longitude))
    return t.arc(rsin_a)


def _gola() -> dict[str, tuple[Fraction, Fraction, str]]:
    fx = printed(GOLA)
    out: dict[str, tuple[Fraction, Fraction, str]] = {}
    lams = []
    for i in (1, 2, 3):
        lam = fx[f"input.f{i}.lambda"]
        t = model().table
        assert t.rsine(fx[f"input.f{i}.greatest_declination"] * MINUTES) == model().rsin_obliquity
        lams.append(lam)
        out[f"output.rcos_declination{i}"] = (
            _rounded(_day_radius(_rsin_decl(lam))),
            Fraction(0),
            ROUNDED + " (the day-radius, laghubhaskariya_1963 II.17)",
        )
    a = [_right_ascension(lam) for lam in lams]
    for name, v in zip(("alpha", "beta", "gamma"), a, strict=True):
        out[f"output.{name}"] = (v, WHOLE, APPROX.replace("'approx.' ", "printed "))
    risings = {"aries": a[0], "taurus": a[1] - a[0], "gemini": a[2] - a[1]}
    for sign, v in risings.items():
        out[f"output.ra_{sign}"] = (v, WHOLE, APPROX.replace("'approx.' ", "printed "))
    for sign, mirror in (
        ("aries", "aries"),
        ("taurus", "taurus"),
        ("gemini", "gemini"),
        ("cancer", "gemini"),
        ("leo", "taurus"),
        ("virgo", "aries"),
    ):
        out[f"output.table22.{sign}"] = (
            risings[mirror],
            WHOLE,
            APPROX.replace("'approx.' ", "printed ") + "; the quadrant's mirror",
        )
    return out


@pytest.mark.parametrize("value", sorted(_gola()))
def test_aryabhatiya_1976_gola25(value: str, record_comparison: Record) -> None:
    computed, tolerance, reason = _gola()[value]
    record_comparison(
        fixture=GOLA, value=value, computed=computed, tolerance=tolerance, tolerance_reason=reason
    )
    if tolerance == 0:
        assert computed == printed(GOLA)[value]
    else:
        assert abs(computed - printed(GOLA)[value]) < tolerance


def _lanka() -> dict[str, Fraction]:
    fx = printed(LANKA)
    a = {s: _right_ascension(fx[f"input.{s}.lambda"]) for s in ("aries", "taurus", "gemini")}
    return {
        "output.aries.alpha": a["aries"],
        "output.taurus.alpha": a["taurus"],
        "output.gemini.alpha": a["gemini"],
        "output.aries.rising": a["aries"],
        "output.taurus.rising": a["taurus"] - a["aries"],
        "output.gemini.rising": a["gemini"] - a["taurus"],
    }


@pytest.mark.parametrize("value", sorted(_lanka()))
def test_laghubhaskariya_1963_rising_times_at_lanka(value: str, record_comparison: Record) -> None:
    computed = _lanka()[value]
    record_comparison(
        fixture=LANKA, value=value, computed=computed, tolerance=1, tolerance_reason=APPROX
    )
    assert abs(computed - printed(LANKA)[value]) < 1


def _multipliers() -> dict[str, tuple[Fraction, str]]:
    rcos_eps = (
        _rounded(_day_radius(_rsin_decl(90))),
        ROUNDED + " (the day-radius at the solstice)",
    )
    rsin_eps = (model().rsin_obliquity, EXACT + " (the table's Rsine of the text's obliquity)")
    return {
        "input.f1.multiplier": rcos_eps,
        "input.f3.multiplier": rcos_eps,
        "input.f2.rsin_greatest_declination": rsin_eps,
        "input.f3.rsin_greatest_declination": rsin_eps,
    }


@pytest.mark.parametrize("value", sorted(_multipliers()))
def test_laghubhaskariya_1963_the_editor_s_multipliers_are_the_text_s(
    value: str, record_comparison: Record
) -> None:
    computed, reason = _multipliers()[value]
    record_comparison(
        fixture=LANKA, value=value, computed=computed, tolerance=0, tolerance_reason=reason
    )
    assert computed == printed(LANKA)[value]


# --- laghubhaskariya_1963 III: rising times at Lucknow, the table's own arithmetic
# -----------------------

LUCKNOW_SIGNS = ["aries", "taurus", "gemini", "cancer", "leo", "virgo"]


@pytest.mark.parametrize("sign", LUCKNOW_SIGNS)
def test_laghubhaskariya_1963_lucknow_rising_times(sign: str, record_comparison: Record) -> None:
    # the first quadrant's signs rise in less time than at Laṅkā, the second's in more
    fx = printed(LUCKNOW)
    sign_of = -1 if LUCKNOW_SIGNS.index(sign) < 3 else 1
    computed = fx[f"input.{sign}.rising_lanka"] + sign_of * fx[f"input.{sign}.asc_diff"]
    record_comparison(
        fixture=LUCKNOW,
        value=f"output.{sign}.rising_lucknow",
        computed=Fraction(computed),
        tolerance=0,
        tolerance_reason=(
            "the table's own arithmetic (laghubhaskariya_1963 II.19–20's sign of the cara): the "
            "latitude is not "
            "printed, so the ascensional differences are not recomputed"
        ),
    )
    assert computed == fx[f"output.{sign}.rising_lucknow"]


# --- mahabhaskariya_1960 VIII.25: the latitude from the length of the night
# -----------------------------


def _latitude_minutes(cara_asus: Fraction, obliquity_minutes: Fraction) -> Fraction:
    """The latitude whose ascensional difference at the solstice is ``cara_asus``.

    laghubhaskariya_1963 II.18 inverted: the earthsine is Rsin c × D ÷ R; Rsin φ ÷ Rcos φ is
    the earthsine ÷ Rsin δ, so Rsin φ = R × e ÷ √(e² + Rsin²δ).
    """
    m = model()
    t = m.table
    rsin_d = t.rsine(obliquity_minutes)
    e = t.rsine(cara_asus) * _day_radius(rsin_d) / t.radius
    hyp = karna(e * e + rsin_d * rsin_d, m.day_radius_resolution)
    return t.arc(t.radius * e / hyp)


def _night() -> tuple[Fraction, Fraction]:
    m, fx = model(), printed(NIGHT)
    units = m.units
    night = Fraction(fx["input.night_ghatis"])
    half = (units.nadis_per_day - night) / 2
    cara = (half - Fraction(units.nadis_per_day, 4)) * units.asus_per_nadi
    assert half_day(cara, units).value == half  # mahabhaskariya_1960 IV.28
    return cara, Fraction(fx["input.obliquity"]) * MINUTES


def _modern_latitude_minutes(cara_asus: Fraction, obliquity_minutes: Fraction) -> int:
    """The same inversion in modern trigonometry (math), to the whole minute."""
    c, eps = (math.radians(float(x) / MINUTES) for x in (cara_asus, obliquity_minutes))
    return round(math.degrees(math.atan(math.sin(c) * math.cos(eps) / math.sin(eps))) * MINUTES)


def test_mahabhaskariya_1960_ch8_25_latitude_residual(record_comparison: Record) -> None:
    cara, obliquity = _night()
    computed = _rounded(_latitude_minutes(cara, obliquity)) / MINUTES
    record_comparison(
        fixture=NIGHT,
        value="output.latitude",
        computed=computed,
        tolerance=0,
        tolerance_reason=(
            "NOT reproduced: the rule with the text's Rsines gives this "
            "latitude; the editor's answer is reproduced to the minute only by modern "
            "trigonometry with twice the rule's ascensional difference, attributed to the "
            "editor's arithmetic"
        ),
    )
    fx = printed(NIGHT)
    assert computed != fx["output.latitude"]
    assert Fraction(_modern_latitude_minutes(2 * cara, obliquity), MINUTES) == fx["output.latitude"]
