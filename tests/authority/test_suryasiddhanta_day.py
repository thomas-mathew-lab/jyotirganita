"""The Sūrya-siddhānta's daily motion, declination, day and endings against the printed examples.

The rules, each through the engine's functions: the
equation of a daily motion for the apsis and for the conjunction (ii.47–51,
``gati.equation_of_motion``: :func:`manda_motion_equation`,
:func:`sighra_motion_equation`), the bhujāntara (ii.46,
``carry.bhujantara_true_place``), the deśāntara (i.60–61, i.65), the
declination and its correction for latitude (ii.28, ii.58,
``declination.rsine_obliquity``), the precession (iii.9–10,
``declination_argument.ayana_corrected_true_longitude``), the day-radius,
earth-sine and ascensional difference (ii.60–62,
``ascensional_difference.palabha_versine``), the equinoctial shadow
(iii.17b), the half-day (ii.62–63, ``half_day.quarter_day_plus_cara``) and
the endings by proportional parts (ii.64–69, ``ending.proportional_parts``).

Whitney (suryasiddhanta_burgess_1860) and Rao (balachandra_rao_2000) are ``editor_computed``.
Whitney works each
step to the whole second (minutes and seconds) or prāṇa and carries the
rounded figure on, so each printed figure is computed from the figures he
prints before it, by the engine's rule, rounded half up as he says (suryasiddhanta_burgess_1860
p. 210); a cell that the rule does not give so is a residual
(:data:`RESIDUAL`). A residual's assertion (``got != want`` in
:func:`compare`) proves that the residual persists, not its size: its size
is stated in the reason string, and asserting the engine's own figure
instead would assert the value the code holds. Rao uses his
continuous corrected periphery: the engine's equation is run on his
periphery (an epicycle pair of that one value) and compared to his printed
decimals. Raṅganātha (suryasiddhanta_hall_1859) is ``text_computed``: the divisor and both
multipliers of i.59 are reproduced exactly, the parts of a multiplier to
the half or quarter part he names them by (the first multiplier's parts
settled by a further blind look). The editors' conversions to
mean solar time, the Nautical Almanac figures and the yojana in English
miles are outside the text's arithmetic and are not compared; nor are the
names of an asterism, a yoga or a karaṇa (the engine reports the 1-based
index).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from fractions import Fraction
from functools import cache
from typing import Any

import pytest
from authority_kit import printed
from surya_kit import EXACT, FX, MINUTES, angle, half_up, integer, model, to_place

from jyotirganita.calendar import elements
from jyotirganita.core.types import AngleUnit, ExactArc
from jyotirganita.siddhantic.endings import proportional_parts
from jyotirganita.siddhantic.epicycle import bhuja_koti
from jyotirganita.siddhantic.sunrise import rsine_declination
from jyotirganita.siddhantic.surya import (
    Epicycles,
    SineTable,
    ascensional_difference_surya,
    corrected_epicycle,
    manda_motion_equation,
    palabha,
    sighra_motion_equation,
)

Record = Callable[..., None]
CIRCLE = 360
SECONDS = MINUTES * MINUTES
WHITNEY = (
    "Whitney's whole second (suryasiddhanta_burgess_1860 p. 210), each step from the figures he "
    "prints before it"
)
RAO = "Rao's printed decimals, each step from the figures he prints before it"
NOT = "NOT reproduced: "

MOON_GATI = FX + "whitney_moon_true_daily_motion"
PLANET_GATI = FX + "whitney_mars_true_daily_motion"
TRUE = FX + "whitney_true_places"
SUN_EQ = FX + "whitney_sun_manda_equation"
RAO_LUMINARIES = FX + "rao_true_daily_motion_sun_moon"
RAO_SATURN = FX + "rao_saturn_true_daily_motion"
RAO_BHUJANTARA = FX + "rao_bhujantara_sun_moon"
RAO_SATURN_BHUJANTARA = FX + "rao_saturn_bhujantara"
PRECESSION = FX + "whitney_precession_example"
DAY_RADIUS = FX + "whitney_sun_day_radius"
WASHINGTON_DAY = FX + "whitney_washington_day_night"
DAY_LENGTH = FX + "whitney_sun_day_length"
EARTH = FX + "whitney_earth_circumference"
WASHINGTON_CIRCLE = FX + "whitney_washington_circumference"
WASHINGTON_DESANTARA = FX + "whitney_washington_desantara"
RANGANATHA = FX + "ranganatha_earth_circumference"
ASTERISM = FX + "whitney_moon_asterism"
TITHI = FX + "whitney_tithi"
YOGA = FX + "whitney_yoga"
KARANA = FX + "whitney_karana"


def table() -> SineTable:
    return model().table


def r() -> int:
    return int(table().radius)


def sec(minutes: Fraction) -> Fraction:
    """Minutes of arc to the whole second, half up (in minutes)."""
    return half_up(minutes * MINUTES) / MINUTES


def raw(fixture: str, name: str) -> Any:
    """A printed value as stored: the parts of a sexagesimal or a one-row table."""
    rec = printed(fixture)._by_name[name]
    v = rec.raw["value"]
    if rec.raw["form"] == "table":
        (v,) = v
    return [Fraction(str(x)) for x in v] if isinstance(v, list) else Fraction(str(v))


def nvp(nadis: Fraction) -> list[Fraction]:
    """Nāḍīs as [nāḍī, vināḍī, prāṇa], the prāṇa truncated (60 vināḍīs, 6 prāṇas, i.11).

    Whitney's endings drop the fraction of a prāṇa (suryasiddhanta_burgess_1860 pp. 234–237: 2.28,
    3.23 and 4.62 prāṇas printed 2, 3 and 4).
    """
    pranas = Fraction(math.floor(nadis * MINUTES * integer("time.vinadi.pranas")))
    per_nadi = MINUTES * integer("time.vinadi.pranas")
    n, rest = divmod(pranas, per_nadi)
    v, p = divmod(rest, integer("time.vinadi.pranas"))
    return [Fraction(n), Fraction(v), Fraction(p)]


def _sexagesimal(x: Fraction, places: int = 2) -> list[Fraction]:
    """``x`` as [units, sixtieths, …] with ``places`` places, the last half up."""
    q = int(half_up(x * MINUTES**places))
    out: list[Fraction] = []
    for _ in range(places):
        q, rem = divmod(q, MINUTES)
        out.append(Fraction(rem))
    return [Fraction(q), *reversed(out)]


def compare(
    fixture: str,
    computed: Mapping[str, Any],
    name: str,
    record: Record,
    reason: str,
    residual: Mapping[str, str] | None = None,
    expected: Callable[[str], Any] | None = None,
) -> None:
    """Record the comparison of ``name`` and assert it, or assert the residual."""
    got = computed[name]
    want = (expected or (lambda n: printed(fixture)[n]))(name)
    why = (residual or {}).get(name)
    record(
        fixture=fixture,
        value=name,
        computed=got,
        tolerance=0,
        tolerance_reason=(NOT + why) if why else reason,
    )
    if why:
        assert got != want
    else:
        assert got == want


def motion_of(element: str) -> Fraction:
    """An element's mean daily motion in minutes, to the whole second (i.29–34)."""
    return sec(model().elements.motion(element) * MINUTES)


def element_motion(body: str) -> Fraction:
    """A body's mean daily motion in minutes, to the whole second."""
    return motion_of(model().planets[body].mean)


# --- the daily motion of the luminaries (ii.47–49), suryasiddhanta_burgess_1860 pp. 223–224
# ---------------------


@cache
def _moon_gati() -> dict[str, Any]:
    fx = printed(MOON_GATI)
    m = model()
    moon = m.planets["moon"]
    anomalistic = fx["input.moon.mean_daily_motion"] - fx["input.moon.apsis_daily_motion"]
    # the engine's anomaly is the apsis less the Moon: the circle less Whitney's
    kendra = CIRCLE - fx["input.moon.mean_anomaly"]
    _, _, bhuja, _ = bhuja_koti(kendra)
    arc = bhuja * MINUTES
    increase = sec(anomalistic * table().difference(arc) / table().step)
    equation = sec(
        manda_motion_equation(moon.manda, kendra, table(), CIRCLE, anomalistic / MINUTES) * MINUTES
    )
    sun = printed(SUN_EQ)
    sun_kendra = (sun["input.sun_apsis_longitude"] - sun["output.sun_mean_longitude"]) % CIRCLE
    sun_motion = element_motion("sun")
    sun_eq = sec(
        manda_motion_equation(
            m.planets["sun"].manda, sun_kendra, table(), CIRCLE, sun_motion / MINUTES
        )
        * MINUTES
    )
    return {
        "input.moon.mean_daily_motion": element_motion("moon"),
        "input.moon.apsis_daily_motion": motion_of(moon.apsis),
        "output.moon.mean_anomalistic_motion": anomalistic,
        "input.moon.sine_of_anomaly": half_up(table().rsine(arc)),
        "input.moon.difference_of_tabular_sines": Fraction(table().difference(arc)),
        "input.sine_table_interval": Fraction(table().step),
        "output.moon.daily_increase_of_sine": increase,
        "input.moon.epicycle_of_apsis": to_place(
            corrected_epicycle(moon.manda, table().rsine(arc), r()), 1
        ),
        "input.degrees_in_circle": Fraction(m.circle),
        # printed as a magnitude, "subtractive" in words: the engine's is negative here
        "output.moon.equation_of_motion": -equation,
        "output.moon.true_daily_motion": fx["input.moon.mean_daily_motion"] + equation,
        "output.sun.equation_of_motion": sun_eq,
        "output.sun.true_daily_motion": sun_motion + fx["output.sun.equation_of_motion"],
    }


@pytest.mark.parametrize("name", sorted(_moon_gati()))
def test_whitney_daily_motion_of_the_luminaries(name: str, record_comparison: Record) -> None:
    compare(MOON_GATI, _moon_gati(), name, record_comparison, WHITNEY)


# --- the daily motion of the planets (ii.48–51), suryasiddhanta_burgess_1860 pp. 224–225
# ------------------------

PLANETS = ("mercury", "venus", "mars", "jupiter", "saturn")
EPI = "corrected_epicycle [deg, min]"
HYP = "variable_hypotenuse [min]"
ANOMALY = "equated_anomaly [s, deg, min]"
#: Saturn's equation of the conjunction: the rule on Whitney's printed synodical motion
#: and last hypotenuse gives one second more than he prints (his true motion follows his
#: own figure and is reproduced from it)
PLANET_RESIDUAL = {
    "output.table.saturn.equation_of_conjunction": "the rule on Whitney's printed synodical "
    "motion and hypotenuse gives one second more than he prints",
}


def _rows(name: str) -> dict[str, dict[str, Any]]:
    return {row["planet"].lower(): row for row in printed(TRUE).rows(name)}


@cache
def _planet_gati() -> dict[str, Any]:
    """Each planet's row from Whitney's third and fourth processes (suryasiddhanta_burgess_1860 pp.
    214–216).

    The apsis's equation is taken at the anomaly of the third process, the
    place the whole equation of the apsis is applied from (ii.44), with the
    epicycle the engine corrects; the conjunction's with his last
    hypotenuse (ii.51).
    """
    m = model()
    third, fourth = _rows("output.third_process_table"), _rows("output.fourth_process_table")
    fx = printed(PLANET_GATI)
    out: dict[str, Any] = {}
    for body in PLANETS:
        p = m.planets[body]
        assert p.conjunction is not None
        anomaly = angle(third[body][ANOMALY])
        _, _, bhuja, _ = bhuja_koti(anomaly)
        motion = element_motion(body)
        apsis = sec(
            manda_motion_equation(p.manda, anomaly, table(), CIRCLE, motion / MINUTES) * MINUTES
        )
        row = f"output.table.{body}."
        equated = motion + fx[row + "equation_of_apsis"]
        synodic = motion_of(p.conjunction) - fx[row + "equated_motion"]
        hyp = Fraction(fourth[body][HYP])
        conj = sec(
            sighra_motion_equation(
                motion_of(p.conjunction) / MINUTES,
                fx[row + "equated_motion"] / MINUTES,
                hyp,
                r(),
            )
            * MINUTES
        )
        out |= {
            row + "diff_of_sines": Fraction(table().difference(bhuja * MINUTES)),
            row + "equation_of_apsis": apsis,
            row + "equated_motion": equated,
            row + "equated_synod_motion": synodic,
            row + "equation_of_conjunction": conj,
            row + "true_motion": fx[row + "equated_motion"] + fx[row + "equation_of_conjunction"],
        }
    mars = "output.table.mars."
    out |= {
        "input.mars.equation_of_apsis": out[mars + "equation_of_apsis"],
        "input.mars.difference_of_tabular_sines": out[mars + "diff_of_sines"],
        "input.mars.mean_daily_motion": element_motion("mars"),
        "output.mars.equated_daily_motion": out[mars + "equated_motion"],
        "input.sun.daily_motion": element_motion("sun"),
        "output.mars.equated_synodical_motion": out[mars + "equated_synod_motion"],
        "input.mars.variable_hypothenuse": Fraction(fourth["mars"][HYP]),
        "input.mars.hypothenuse_excess_over_radius": Fraction(fourth["mars"][HYP] - r()),
        "output.mars.equation_of_conjunction": out[mars + "equation_of_conjunction"],
        "output.mars.true_daily_motion": out[mars + "true_motion"],
    }
    return out


@pytest.mark.parametrize("name", sorted(_planet_gati()))
def test_whitney_daily_motion_of_the_planets(name: str, record_comparison: Record) -> None:
    compare(PLANET_GATI, _planet_gati(), name, record_comparison, WHITNEY, PLANET_RESIDUAL)


# --- Rao: the true daily motions (balachandra_rao_2000 pp. 96–97, 118–119)
# ----------------------------


def _rao_epicycle(periphery: Fraction) -> Epicycles:
    """Rao's corrected periphery as an epicycle pair of that one value (ii.38 leaves it)."""
    return Epicycles(periphery, periphery)


def _decimals(fixture: str, name: str) -> int:
    v = str(printed(fixture)._by_name[name].raw["value"])
    return len(v.split(".")[1]) if "." in v else 0


def _at(fixture: str, name: str, x: Fraction) -> Fraction:
    """``x`` to the decimals Rao prints for ``name``, half up."""
    return half_up(x, Fraction(1, 10 ** _decimals(fixture, name)))


@cache
def _rao_luminaries() -> dict[str, Any]:
    fx = printed(RAO_LUMINARIES)
    out: dict[str, Any] = {}
    for body, motion_name in (("sun", "mean_daily_motion_decimal"), ("moon", None)):
        kendra = CIRCLE - fx[f"input.{body}.mean_anomaly"]
        _, _, bhuja, _ = bhuja_koti(kendra)
        diff = table().difference(bhuja * MINUTES)
        periphery = fx[f"input.{body}.corrected_periphery"]
        if motion_name:
            motion = fx[f"input.{body}.{motion_name}"]
        else:  # ii.47: the Moon's motion less its apsis's
            motion = (
                fx["input.moon.mean_daily_motion_decimal"]
                - fx["input.moon.apogee_mean_daily_motion"]
            )
        eq = (
            manda_motion_equation(
                _rao_epicycle(periphery), kendra, table(), CIRCLE, motion / MINUTES
            )
            * MINUTES
        )
        name = f"output.{body}.correction_decimal"
        out |= {
            f"input.{body}.tabular_sine_difference": Fraction(diff),
            name: _at(RAO_LUMINARIES, name, abs(eq)),
            f"output.{body}.correction": sec(abs(eq)),
            f"input.{body}.mean_daily_motion": element_motion(body),
        }
        out[f"output.{body}.true_daily_motion"] = (
            fx[f"input.{body}.mean_daily_motion"] + fx[f"output.{body}.correction"]
        )
        assert eq > 0  # additive: both anomalies in the half from Cancer
    out["output.moon.true_daily_motion_minutes"] = out.pop("output.moon.true_daily_motion")
    out["input.formula.divisor_circle"] = Fraction(CIRCLE)
    out["input.formula.divisor_sine_step"] = Fraction(table().step)
    return out


@pytest.mark.parametrize("name", sorted(_rao_luminaries()))
def test_rao_true_daily_motion_of_the_luminaries(name: str, record_comparison: Record) -> None:
    compare(RAO_LUMINARIES, _rao_luminaries(), name, record_comparison, RAO)


@cache
def _rao_saturn() -> dict[str, Any]:
    fx = printed(RAO_SATURN)
    # Rao's m is the apsis less the planet, the engine's anomaly (ii.29)
    engine_kendra = kendra = fx["output.saturn.manda_anomaly"]
    _, _, bhuja, _ = bhuja_koti(engine_kendra)
    periphery = fx["output.saturn.corrected_periphery"]
    motion = Fraction(fx["input.saturn.mean_daily_motion_minutes"])
    eq = (
        manda_motion_equation(
            _rao_epicycle(periphery), engine_kendra, table(), CIRCLE, motion / MINUTES
        )
        * MINUTES
    )
    n1 = fx["input.saturn.mean_daily_motion"] + Fraction(
        fx["output.saturn.manda_correction_signed"], SECONDS
    )
    # n1 is printed in degrees, n2 and the synodic motion in minutes
    n1_printed = fx["output.saturn.manda_corrected_daily_motion_n1"] * MINUTES
    synodic = fx["input.sighrocca.mean_daily_motion_n2"] - n1_printed
    hyp = fx["input.saturn.variable_hypotenuse_k"]
    conj = sighra_motion_equation(
        fx["input.saturn.synodic_motion_decimal"] / MINUTES, Fraction(0), hyp, r()
    )
    name = "output.saturn.sighra_correction_decimal"
    return {
        "output.saturn.manda_anomaly": (
            fx["input.saturn.mandocca"] - fx["input.saturn.equated_longitude_p2"]
        )
        % CIRCLE,
        "output.saturn.anomaly_from_circle": CIRCLE - kendra,
        "input.saturn.tabular_sine_difference": Fraction(table().difference(bhuja * MINUTES)),
        "output.saturn.manda_correction_decimal": _at(
            RAO_SATURN, "output.saturn.manda_correction_decimal", abs(eq)
        ),
        "output.saturn.manda_correction": half_up(abs(eq) * MINUTES),
        "output.saturn.manda_correction_signed": half_up(abs(eq) * MINUTES) * (-1 if eq < 0 else 1),
        "output.saturn.manda_corrected_daily_motion_n1": n1,
        "output.saturn.synodic_motion_n2_minus_n1": synodic,
        "input.deferent_radius": Fraction(r()),
        "output.saturn.hypotenuse_excess": hyp - r(),
        # the conjunction's motion less the planet's is Rao's synodic motion (ii.50)
        name: _at(RAO_SATURN, name, conj * MINUTES),
        "output.saturn.sighra_correction": sec(conj * MINUTES),
        "output.saturn.true_daily_motion": n1_printed + fx["output.saturn.sighra_correction"],
        "input.formula.divisor_sine_step": Fraction(table().step),
        "input.circle_degrees": Fraction(CIRCLE),
        # "k − R": R is the radius (ii.38–39)
        "input.k_minus_r.subtrahend_as_printed": Fraction(r()),
    }


#: Rao's śīghra correction 2.6753493′ is 40.52″; he prints 40″ (his Sun's 0.5091′, 30.55″,
#: he prints as 31″): the second half up is one more
RAO_SATURN_RESIDUAL = {
    "output.saturn.sighra_correction": "Rao's 2.6753493′ to the second half up is 41″; he "
    "prints 40″ (his 0.5091′ of the Sun he rounds to 31″)",
    "input.k_minus_r.subtrahend_as_printed": "the radius R is 3438; the subtrahend is "
    "printed with a doubled digit, a misprint carried as printed",
}


@pytest.mark.parametrize("name", sorted(_rao_saturn()))
def test_rao_true_daily_motion_of_saturn(name: str, record_comparison: Record) -> None:
    compare(RAO_SATURN, _rao_saturn(), name, record_comparison, RAO, RAO_SATURN_RESIDUAL)


# --- Rao: the bhujāntara (ii.46), balachandra_rao_2000 pp. 99–100, 121
# ---------------------------------


def _bhujantara(gati_minutes: Fraction, bhujaphala_minutes: Fraction) -> Fraction:
    """The engine's bhujāntara in minutes: gati × the Sun's bāhuphala ÷ the circle's minutes."""
    return gati_minutes * bhujaphala_minutes / model().circle_minutes


@cache
def _rao_bhujantara() -> dict[str, Any]:
    fx = printed(RAO_BHUJANTARA)
    eq = fx["input.sun.equation_min"]
    out: dict[str, Any] = {"input.circle_minutes": Fraction(model().circle_minutes)}
    for body in ("sun", "moon"):
        b = _bhujantara(fx[f"input.{body}.true_daily_motion"], eq)
        name = f"output.{body}.bhujantara_min"
        out[name] = _at(RAO_BHUJANTARA, name, b)
        out[f"output.{body}.bhujantara"] = sec(b)
    out["output.sun.true_longitude"] = fx["input.sun.longitude"] + fx["output.sun.bhujantara"] / 60
    out["output.moon.longitude"] = (
        fx["input.moon.true_longitude"] + fx["output.moon.bhujantara"] / 60
    )
    return out


@pytest.mark.parametrize("name", sorted(_rao_bhujantara()))
def test_rao_bhujantara_of_the_luminaries(name: str, record_comparison: Record) -> None:
    compare(RAO_BHUJANTARA, _rao_bhujantara(), name, record_comparison, RAO)


@cache
def _rao_saturn_bhujantara() -> dict[str, Any]:
    fx = printed(RAO_SATURN_BHUJANTARA)
    eq = fx["input.sun.equation_min"]
    b = _bhujantara(fx["input.saturn.true_daily_motion_min"], eq)
    mean = _bhujantara(fx["input.saturn.mean_daily_motion"], eq)
    out = {"input.circle_minutes": Fraction(model().circle_minutes)}
    for name, x in (
        ("output.saturn.bhujantara_min", b),
        ("output.saturn.bhujantara_sec", b * MINUTES),
        ("output.saturn.bhujantara_mean_sec", mean * MINUTES),
    ):
        out[name] = _at(RAO_SATURN_BHUJANTARA, name, x)
    return out


@pytest.mark.parametrize("name", sorted(_rao_saturn_bhujantara()))
def test_rao_bhujantara_of_saturn(name: str, record_comparison: Record) -> None:
    compare(RAO_SATURN_BHUJANTARA, _rao_saturn_bhujantara(), name, record_comparison, RAO)


# --- the precession (iii.9–10), suryasiddhanta_burgess_1860 pp. 242–245
# ----------------------------------------


@cache
def _precession() -> dict[str, Any]:
    fx = printed(PRECESSION)
    m = model()
    revs, yuga_days = m.ayana_rate
    since = fx["input.days_since_age_began"]
    # the count from creation holds whole revolutions of the libration to the Kali epoch
    days = m.days_to_epoch + since
    part = Fraction(days * revs * CIRCLE, yuga_days) % CIRCLE
    _, _, bhuja, _ = bhuja_koti(part)
    return {
        "input.days_in_age": Fraction(yuga_days),
        "input.revolutions_in_age": Fraction(revs),
        "output.portion_of_revolution": [Fraction(0), *_dms(part)],  # no whole revolution
        "output.bhuja": _dms(bhuja),
        # the greatest libration: the multiplier over the divisor of a quadrant (iii.10)
        "input.libration_arc": m.ayana_factor * 90,
        "input.multiplier": Fraction(m.ayana_factor.numerator),
        "input.divisor": Fraction(m.ayana_factor.denominator),
        "output.precession": _dms(m.ayana(Fraction(days)), places=2),
    }


def _dms(degrees: Fraction, places: int = 1) -> list[Fraction]:
    """[degrees, minutes, seconds], the seconds to ``places`` decimals, half up."""
    s = half_up(abs(degrees) * SECONDS, Fraction(1, 10**places))
    d, rest = divmod(s, SECONDS)
    mm, ss = divmod(rest, MINUTES)
    return [Fraction(d), Fraction(mm), ss]


def _raw_or_value(fixture: str) -> Callable[[str], Any]:
    def get(name: str) -> Any:
        rec = printed(fixture)._by_name[name]
        return raw(fixture, name) if rec.raw["form"] in ("table", "sexagesimal") else rec.value

    return get


@pytest.mark.parametrize("name", sorted(_precession()))
def test_whitney_precession(name: str, record_comparison: Record) -> None:
    compare(
        PRECESSION, _precession(), name, record_comparison, WHITNEY, None, _raw_or_value(PRECESSION)
    )


# --- the declination (ii.28) at the true place and the precession, suryasiddhanta_burgess_1860 pp.
# 228–229 ------

BODIES = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")
#: Whitney's declinations the rule does not give from his true longitudes and his
#: precession (each at his whole minute); his corrected declinations follow his own figures
DECLINATION_RESIDUAL = {
    "output.table.moon.declination": "the rule at Whitney's Moon (11s 17° 39′, ASTERISM) and "
    "his precession gives 3° 16′ N; he prints 4° 56′ N",
    "output.table.venus.declination": "the rule at Whitney's Venus (fourth process) and his "
    "precession gives 19° 27′ S; he prints 20° 27′ S",
    "output.table.saturn.declination": "the rule gives 14° 39′ N at Whitney's whole minute "
    "(14° 40′ N without rounding the sine of the longitude); he prints 14° 40′ N",
}


def _true_longitudes() -> dict[str, Fraction]:
    fourth = printed(TRUE).rows("output.fourth_process_table")
    out = {row["planet"].lower(): angle(row["true_longitude [s, deg, min]"]) for row in fourth}
    out["sun"] = printed(SUN_EQ)["output.sun_true_longitude"]
    out["moon"] = printed(ASTERISM)["input.moon.true_longitude"]
    return out


@cache
def _declinations() -> dict[str, Any]:
    m = model()
    precession = to_place(_precession_degrees(), 1)
    out: dict[str, Any] = {}
    for body, longitude in _true_longitudes().items():
        at = (longitude + precession) % CIRCLE
        _, _, bhuja, _ = bhuja_koti(at)
        # Whitney's whole minute: the sine of the longitude, then that of the declination
        base = half_up(table().rsine(to_place(bhuja, 1) * MINUTES))
        sine = half_up(base * m.rsin_obliquity / r())
        assert abs(sine - abs(rsine_declination(table(), m.rsin_obliquity, at))) <= 1
        north = at < CIRCLE // 2
        out[f"output.table.{body}.declination"] = to_place(table().arc(sine) / MINUTES, 1) * (
            1 if north else -1
        )
    return out


def _precession_degrees() -> Fraction:
    m = model()
    return m.ayana(Fraction(m.days_to_epoch + printed(PRECESSION)["input.days_since_age_began"]))


@pytest.mark.parametrize("name", sorted(_declinations()))
def test_whitney_declinations(name: str, record_comparison: Record) -> None:
    compare(
        FX + "whitney_declination",
        _declinations(),
        name,
        record_comparison,
        WHITNEY,
        DECLINATION_RESIDUAL,
    )


# --- the day-radius, the equinoctial shadow and the ascensional difference (ii.60–63,
# iii.17b), suryasiddhanta_burgess_1860 pp. 229–232
# --------------------------------------------------------------


@cache
def _day_radius() -> dict[str, Any]:
    fx = printed(DAY_RADIUS)
    arc = abs(fx["input.sun.declination"]) * MINUTES
    sine = half_up(table().rsine(arc))
    cara = ascensional_difference_surya(table(), -sine, Fraction(0), model().gnomon)
    return {
        "input.sun.versed_sine_of_declination": half_up(table().rversine(arc)),
        "input.radius": Fraction(r()),
        "output.sun.day_radius": half_up(cara.day_radius),
    }


@pytest.mark.parametrize("name", sorted(_day_radius()))
def test_whitney_day_radius(name: str, record_comparison: Record) -> None:
    compare(DAY_RADIUS, _day_radius(), name, record_comparison, WHITNEY)


@cache
def _washington_day() -> dict[str, Any]:
    fx = printed(WASHINGTON_DAY)
    m = model()
    shadow = palabha(table(), fx["input.washington.latitude"], m.gnomon)
    sine = half_up(table().rsine(abs(fx["input.sun.declination"]) * MINUTES))
    # from Whitney's printed shadow and sine, south (negative), as he carries them on
    cara = ascensional_difference_surya(
        table(),
        -fx["input.sun.sine_of_declination"],
        fx["output.washington.equinoctial_shadow"],
        m.gnomon,
    )
    rsin_cara = half_up(Fraction(fx["output.sun.earth_sine"] * r(), fx["input.sun.day_radius"]))
    cara_arc = _sexagesimal(table().arc(fx["output.sun.sine_of_ascensional_difference"]) / 60, 1)
    asus = fx["output.sun.ascensional_difference_minutes"]  # a minute of arc is an asu (ii.62)
    planet_day = sum(
        (x / MINUTES**i for i, x in enumerate(raw(WASHINGTON_DAY, "input.sun.day_length_total"))),
        Fraction(0),
    )
    quarter = planet_day / 4
    cara_nadis = Fraction(asus, MINUTES * integer("time.vinadi.pranas"))
    return {
        "output.washington.equinoctial_shadow": half_up(shadow, Fraction(1, 100)),
        "input.sun.sine_of_declination": sine,
        "input.gnomon_length": Fraction(m.gnomon),
        "output.sun.earth_sine": half_up(abs(cara.earthsine)),
        "input.radius": Fraction(r()),
        "output.sun.sine_of_ascensional_difference": rsin_cara,
        "output.sun.ascensional_difference_arc": cara_arc,
        "output.sun.ascensional_difference_minutes": half_up(abs(cara.cara_asus)),
        "output.sun.ascensional_difference_time": nvp(cara_nadis),
        # ii.62–63: the half-night a quarter of the planet's day (ii.59) increased by the
        # ascensional difference, the half-day decreased, in the south
        "output.sun.night_length": nvp(2 * (quarter + cara_nadis)),
        "output.sun.day_length": nvp(2 * (quarter - cara_nadis)),
    }


@pytest.mark.parametrize("name", sorted(_washington_day()))
def test_whitney_day_and_night_at_washington(name: str, record_comparison: Record) -> None:
    compare(
        WASHINGTON_DAY,
        _washington_day(),
        name,
        record_comparison,
        WHITNEY,
        None,
        _raw_or_value(WASHINGTON_DAY),
    )


@cache
def _day_length() -> dict[str, Any]:
    fx = printed(DAY_LENGTH)
    per_sign = integer("procedures.half_day.planet_day.ii59.n1.suryasiddhanta_burgess_1860")
    rising = fx["input.sun.rising_time_of_sign"] * fx["input.sun.true_daily_motion"] / per_sign
    pranas = half_up(rising, Fraction(1, 100))
    per_vinadi = integer("time.vinadi.pranas")
    v, p = divmod(pranas, per_vinadi)
    return {
        "input.minutes_in_sign": Fraction(per_sign),
        "output.sun.rising_time_of_daily_motion": pranas,
        "output.sun.excess_over_sidereal_day": [Fraction(v), p],
        "output.sun.apparent_day_length": [Fraction(integer("time.day.nadis")), Fraction(v), p],
    }


@pytest.mark.parametrize("name", sorted(_day_length()))
def test_whitney_day_of_the_sun(name: str, record_comparison: Record) -> None:
    compare(
        DAY_LENGTH, _day_length(), name, record_comparison, WHITNEY, None, _raw_or_value(DAY_LENGTH)
    )


# --- the earth and the deśāntara (i.59–61), suryasiddhanta_burgess_1860 pp. 39–44; Raṅganātha on
# i.59 -----------


def _root(square: Fraction, places: int) -> Fraction:
    """The square root truncated at ``places`` decimals."""
    q = 10**places
    return Fraction(math.isqrt(math.floor(square * q * q)), q)


@cache
def _earth() -> dict[str, Any]:
    diameter = integer("yojana_scale.i59.n1.suryasiddhanta_burgess_1860") * integer(
        "yojana_scale.i59.n2.suryasiddhanta_burgess_1860"
    )
    circumference = _root(
        Fraction(diameter * diameter * integer("yojana_scale.i59.n3.suryasiddhanta_burgess_1860")),
        3,
    )
    return {"output.earth.circumference": circumference}


EARTH_RESIDUAL = {
    "output.earth.circumference": "the root of ten times the square of the diameter is "
    "5059.644; suryasiddhanta_burgess_1860 prints 5059.556, and its errata "
    "(suryasiddhanta_burgess_1860_reprint p. 364) read 5059.64",
}


@pytest.mark.parametrize("name", sorted(_earth()))
def test_whitney_circumference_of_the_earth(name: str, record_comparison: Record) -> None:
    compare(EARTH, _earth(), name, record_comparison, WHITNEY, EARTH_RESIDUAL)


@cache
def _washington_circle() -> dict[str, Any]:
    fx = printed(WASHINGTON_CIRCLE)
    colatitude = (90 - fx["input.washington.latitude"]) * MINUTES
    sine = half_up(table().rsine(colatitude))
    return {
        "input.washington.sine_colatitude": sine,
        "input.radius": Fraction(r()),
        "input.earth.circumference": _root(
            Fraction(
                (
                    integer("yojana_scale.i59.n1.suryasiddhanta_burgess_1860")
                    * integer("yojana_scale.i59.n2.suryasiddhanta_burgess_1860")
                )
                ** 2
                * integer("yojana_scale.i59.n3.suryasiddhanta_burgess_1860")
            ),
            2,
        ),
        # i.60: the circumference times the sine of the co-latitude, divided by the radius
        "output.washington.circumference": half_up(
            fx["input.earth.circumference"] * fx["input.washington.sine_colatitude"] / r(),
            Fraction(1, 100),
        ),
    }


@pytest.mark.parametrize("name", sorted(_washington_circle()))
def test_whitney_circle_of_washington(name: str, record_comparison: Record) -> None:
    compare(WASHINGTON_CIRCLE, _washington_circle(), name, record_comparison, WHITNEY)


def _hms(parts: list[Fraction]) -> Fraction:
    return sum((Fraction(x) / MINUTES**i for i, x in enumerate(parts)), Fraction(0))


@cache
def _washington_desantara() -> dict[str, Any]:
    fx = printed(WASHINGTON_DESANTARA)
    hours = _hms(raw(WASHINGTON_DESANTARA, "input.ujjayini.longitude_from_greenwich_time")) + _hms(
        raw(WASHINGTON_DESANTARA, "input.washington.longitude_from_greenwich_time")
    )
    s = half_up(hours * SECONDS)
    nadis_per_day = integer("time.day.nadis")
    hours_per_day = 24  # the editor's mean solar hours, not the text's unit
    nadis = hours * nadis_per_day / hours_per_day
    in_nadis = half_up(nadis, Fraction(1, 10**4))
    vinadis = (nadis - math.floor(nadis)) * MINUTES
    pranas = half_up(
        (vinadis - math.floor(vinadis)) * integer("time.vinadi.pranas"), Fraction(1, 10)
    )
    return {
        "input.nadis_per_day": Fraction(nadis_per_day),
        "output.ujjayini_from_washington.time": [s // SECONDS, s // MINUTES % MINUTES, s % MINUTES],
        "output.ujjayini_from_washington.nadis_decimal": in_nadis,
        "output.ujjayini_from_washington.nadis_vinadis_pranas": [
            Fraction(math.floor(nadis)),
            Fraction(math.floor(vinadis)),
            pranas,
        ],
        # i.61, i.65: the yojanas of the circle of the place, as the nāḍīs are of a day
        "output.washington.desantara_yojanas": half_up(
            fx["input.washington.circumference"]
            * fx["output.ujjayini_from_washington.nadis_decimal"]
            / nadis_per_day,
            Fraction(1, 100),
        ),
    }


#: Whitney's decimals the rule does not give from his figures before them
DESANTARA_RESIDUAL = {
    "output.ujjayini_from_washington.nadis_decimal": "10 h 11 m 19 s is 25.47153 nāḍīs "
    "(25.4715 to four places); the printed decimal is 25.4718, and his own nāḍīs, vināḍīs "
    "and prāṇas are 25.47167",
    "output.washington.desantara_yojanas": "3936.75 × 25.4718 ÷ 60 is 1671.272 yojanas; "
    "the printed figure is 1671.28",
}


@pytest.mark.parametrize("name", sorted(_washington_desantara()))
def test_whitney_desantara_of_washington(name: str, record_comparison: Record) -> None:
    compare(
        WASHINGTON_DESANTARA,
        _washington_desantara(),
        name,
        record_comparison,
        WHITNEY,
        DESANTARA_RESIDUAL,
        _raw_or_value(WASHINGTON_DESANTARA),
    )


@cache
def _ranganatha() -> dict[str, Any]:
    """Raṅganātha's two multipliers (text_computed), from the figures he states."""
    fx = printed(RANGANATHA)
    m = model()
    divisor = 2 * r()
    first = Fraction(m.circle_minutes, divisor)
    whole = math.floor(first)
    # "three with eight and a half parts": the parts of sixty, to the half part he names
    parts = half_up((first - whole) * MINUTES, Fraction(1, 2))
    lord = Fraction(fx["output.lord_circumference.digits"], fx["input.lord_diameter.digits"])
    lord_sx = _sexagesimal(lord)
    square = _hms(lord_sx) ** 2
    return {
        "input.radius.word": Fraction(r()),
        "input.radius.digits": Fraction(r()),
        "input.diameter_multiplier": Fraction(divisor, r()),
        "input.circle_minutes": Fraction(m.circle_minutes),
        "input.proportion_multiplier": Fraction(m.circle_minutes),
        "output.diameter_divisor": Fraction(divisor),
        "output.reduced_divisor": Fraction(divisor, divisor),
        "output.multiplier_whole": Fraction(whole),
        "output.multiplier_parts": parts,
        "output.multiplier_square": _sexagesimal((whole + parts / MINUTES) ** 2),
        # i.59: the root of ten times the square: the square of the multiplier taken as ten
        "output.square_taken": Fraction(integer("yojana_scale.i59.n3.suryasiddhanta_burgess_1860")),
        "output.lord_square_taken": Fraction(
            integer("yojana_scale.i59.n3.suryasiddhanta_burgess_1860")
        ),
        "output.lord_multiplier": lord_sx,
        "output.lord_multiplier_whole": lord_sx[0],
        # "ten less a quarter" parts: the sexagesimal part to the quarter he names
        "output.lord_multiplier_parts": half_up((lord - lord_sx[0]) * MINUTES, Fraction(1, 4)),
        "output.lord_multiplier_square": _sexagesimal(square),
    }


@pytest.mark.parametrize("name", sorted(_ranganatha()))
def test_ranganatha_multipliers_of_the_circumference(name: str, record_comparison: Record) -> None:
    compare(
        RANGANATHA, _ranganatha(), name, record_comparison, EXACT, None, _raw_or_value(RANGANATHA)
    )


# --- the endings (ii.64–69), suryasiddhanta_burgess_1860 pp. 233–237
# -------------------------------------------

#: Whitney's figures the proportion does not give from the figures he prints before them
ENDING_RESIDUAL = {
    "output.moon.asterism.time_spent": "the proportion 59′ of 737′ in sixty nāḍīs gives "
    "4 n 48 v 1 p; the value as keyed is two parts that do not equal it",
    "output.tithi.time_to_run": "the proportion 396′ of 675′ 38″ in sixty nāḍīs gives "
    "35 n 10 v 0 p (0.12 p); the prāṇas as printed differ",
}


def _arc(minutes: Fraction) -> ExactArc:
    return ExactArc(minutes / MINUTES, AngleUnit.DEGREE)


def _ending(
    fixture: str,
    element: elements.Element,
    sun: Fraction,
    moon: Fraction,
    motion: Fraction,
    prefix: str,
    past: str,
    to_come: str,
) -> dict[str, Any]:
    s, mo = ExactArc(sun, AngleUnit.DEGREE), ExactArc(moon, AngleUnit.DEGREE)
    arc_minutes = elements.arc(element, s, mo).value * MINUTES
    span = elements.span(element, s).value * MINUTES
    remaining = elements.remaining(element, s, mo).value * MINUTES
    n = elements.index(element, s, mo)
    nadis = integer("time.day.nadis")
    return {
        f"{prefix}.number": Fraction(n),
        f"{prefix}.{past}": span - remaining,
        f"{prefix}.{to_come}": remaining,
        f"{prefix}.time_past": proportional_parts(span - remaining, motion, nadis).value,
        f"{prefix}.time_to_come": proportional_parts(remaining, motion, nadis).value,
        "arc_minutes": arc_minutes,
        "span": span,
    }


def _nv(nadis: Fraction) -> list[Fraction]:
    """Nāḍīs as [nāḍī, vināḍī], the vināḍī half up (suryasiddhanta_burgess_1860 p. 236 prints the
    yoga's start so)."""
    n, v = divmod(half_up(nadis * MINUTES), MINUTES)
    return [Fraction(n), Fraction(v)]


@cache
def _asterism() -> dict[str, Any]:
    fx = printed(ASTERISM)
    e = _ending(
        ASTERISM,
        elements.NAKSATRA,
        Fraction(0),
        fx["input.moon.true_longitude"],
        fx["input.moon.true_daily_motion"],
        "output.moon.asterism",
        "part_traversed",
        "part_to_traverse",
    )
    days, rest = divmod(e["output.moon.asterism.time_to_come"], integer("time.day.nadis"))
    return {
        "input.moon.true_longitude_minutes": e["arc_minutes"],
        "input.asterism_portion": e["span"],
        "output.moon.asterism.number": e["output.moon.asterism.number"],
        "output.moon.asterism.part_traversed": e["output.moon.asterism.part_traversed"],
        "output.moon.asterism.part_to_traverse": e["output.moon.asterism.part_to_traverse"],
        "output.moon.asterism.time_spent": nvp(e["output.moon.asterism.time_past"]),
        "output.moon.asterism.time_to_run": [Fraction(days), *nvp(rest)],
    }


@pytest.mark.parametrize("name", sorted(_asterism()))
def test_whitney_moon_in_its_asterism(name: str, record_comparison: Record) -> None:
    compare(
        ASTERISM,
        _asterism(),
        name,
        record_comparison,
        WHITNEY,
        ENDING_RESIDUAL,
        _raw_or_value(ASTERISM),
    )


@cache
def _tithi() -> dict[str, Any]:
    fx = printed(TITHI)
    e = _ending(
        TITHI,
        elements.TITHI,
        Fraction(0),
        fx["output.elongation"],
        fx["input.difference_of_daily_motions"],
        "output.tithi",
        "part_traversed",
        "part_to_traverse",
    )
    return {
        "output.elongation_minutes": e["arc_minutes"],
        "input.tithi_portion": e["span"],
        "output.tithi.number": e["output.tithi.number"],
        "output.tithi.part_traversed": e["output.tithi.part_traversed"],
        "output.tithi.part_to_traverse": e["output.tithi.part_to_traverse"],
        "input.multiplier_sixty": Fraction(integer("time.day.nadis")),
        "output.tithi.time_passed": nvp(e["output.tithi.time_past"]),
        "output.tithi.time_to_run": nvp(e["output.tithi.time_to_come"]),
    }


@pytest.mark.parametrize("name", sorted(_tithi()))
def test_whitney_tithi(name: str, record_comparison: Record) -> None:
    compare(
        TITHI, _tithi(), name, record_comparison, WHITNEY, ENDING_RESIDUAL, _raw_or_value(TITHI)
    )


@cache
def _yoga() -> dict[str, Any]:
    fx = printed(YOGA)
    whole, part = raw(YOGA, "input.sum_of_daily_motions")
    e = _ending(
        YOGA,
        elements.YOGA,
        fx["input.sun.longitude"],
        fx["input.moon.longitude"],
        whole + part,
        "output.yoga",
        "part_past",
        "part_to_come",
    )
    return {
        "output.sum_of_longitudes_minutes": e["arc_minutes"],
        "input.yoga_portion": e["span"],
        "output.yoga.count_past": e["output.yoga.number"] - 1,
        "output.yoga.number": e["output.yoga.number"],
        "output.yoga.part_past": e["output.yoga.part_past"],
        "output.yoga.part_to_come": e["output.yoga.part_to_come"],
        "input.nadis_per_day": Fraction(integer("time.day.nadis")),
        "output.yoga.began_before": _nv(e["output.yoga.time_past"]),
        "output.yoga.ends_after": nvp(e["output.yoga.time_to_come"]),
    }


@pytest.mark.parametrize("name", sorted(_yoga()))
def test_whitney_yoga(name: str, record_comparison: Record) -> None:
    compare(YOGA, _yoga(), name, record_comparison, WHITNEY, None, _raw_or_value(YOGA))


@cache
def _karana() -> dict[str, Any]:
    """The karaṇa of a half-tithi: the elongation at the middle of that half (ii.67–69)."""
    fx = printed(KARANA)
    halves = elements.KARANA.count // elements.TITHI.count
    nth = (fx["input.tithi.number"] - 1) * halves + fx["input.tithi.half"]
    width = elements.span(elements.KARANA, ExactArc(Fraction(0), AngleUnit.DEGREE)).value
    middle = ExactArc((nth - Fraction(1, 2)) * width, AngleUnit.DEGREE)
    zero = ExactArc(Fraction(0), AngleUnit.DEGREE)
    return {"output.karana.number": Fraction(elements.index(elements.KARANA, zero, middle))}


def test_whitney_karana(record_comparison: Record) -> None:
    compare(KARANA, _karana(), "output.karana.number", record_comparison, EXACT)
