"""The Sūrya-siddhānta's sines, equations and latitudes against the printed examples.

The table of sines and its two rules (ii.15–22, ii.31–33:
``trig.sine_table_linear``, ``trig.arc_from_sine_table``), the corrected
epicycle (ii.38, ``epicycle.base_sine_variation``), the equations of the
apsis and of the conjunction (ii.39–42, ``epicycle.manda_arc``,
``epicycle.sighra_variable_hypotenuse``), the four processes (ii.43–44,
``order.four_processes``) and the latitude (ii.56–57,
``latitude.node_hypotenuse``), each through the engine's functions.

Whitney (suryasiddhanta_burgess_1860, ``editor_computed``) works each step to whole minutes,
counting a fraction above a half as one (suryasiddhanta_burgess_1860 p. 210), and carries the
rounded figure into the next step. Each printed figure is therefore
computed from the figures he prints before it, by the engine's rule,
rounded as he says; six cells of his true-place tables are not given so
and are asserted as residuals. Raṅganātha's
radius and sine differences (suryasiddhanta_hall_1859) are ``text_computed``. Rao
(balachandra_rao_2000)
works with continuous sines and his own reading of the corrected
epicycle, so the engine's tabular equation does not give his seconds;
those tests assert that his route gives his figures, which is the
residual's cause. The deśāntara he and Whitney add before the
equations, and Rao's bhujāntara, are ``test_suryasiddhanta_day.py``'s.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from fractions import Fraction
from functools import cache
from typing import Any

import pytest
from authority_kit import printed
from surya_kit import EXACT, FX, MINUTES, SIGN, angle, half_up, integer, model, to_place

from jyotirganita.siddhantic.epicycle import bhuja_koti
from jyotirganita.siddhantic.surya import (
    Epicycles,
    SineTable,
    corrected_epicycle,
    manda_equation,
    sighra_equation,
)

Record = Callable[..., None]
INTERP = FX + "whitney_sine_interpolation"
RADIUS = FX + "ranganatha_radius"
DIFFS = FX + "ranganatha_sine_differences"
SUN = FX + "whitney_sun_manda_equation"
MOON = FX + "whitney_moon_manda_equation"
MERCURY = FX + "whitney_mercury_sighra_equation"
TRUE = FX + "whitney_true_places"
LATITUDE = FX + "whitney_latitude"
NODE = FX + "whitney_node_distance"
RAO_MANDA = FX + "rao_manda_sun_moon"
RAO_JUPITER = FX + "rao_jupiter_manda"
RAO_SIGHRA = FX + "rao_sighra_mercury_saturn"
RAO_SATURN = FX + "rao_saturn_four_steps"
WHITNEY = (
    "Whitney's whole minute (suryasiddhanta_burgess_1860 p. 210), each step from the figures he "
    "prints before it"
)
I162 = "NOT reproduced: "
CIRCLE = 360
HALF = CIRCLE // 2


def table() -> SineTable:
    return model().table


def r() -> int:
    return table().radius


def minutes(degrees: Fraction) -> Fraction:
    """Degrees to the whole minute, half up (in degrees)."""
    return to_place(degrees, 1)


def sine_of(degrees: Fraction) -> Fraction:
    """The tabular sine of an arc in degrees, to the whole minute (Whitney's figure)."""
    return half_up(table().rsine(degrees * MINUTES))


def arc_of(sine: Fraction | int) -> Fraction:
    """The arc in degrees whose tabular sine is ``sine``, to the whole minute (ii.33)."""
    return minutes(table().arc(sine) / MINUTES)


def root(square: int) -> int:
    """The square root to the whole minute, half up."""
    n = math.isqrt(square)
    return n + 1 if square - n * n > n else n


def epicycles(body: str, kind: str) -> Epicycles:
    p = model().planets[body]
    e = p.manda if kind == "manda" else p.sighra
    assert e is not None
    return e


# --- the sine of an arc by interpolation (ii.31–32), suryasiddhanta_burgess_1860 p. 204
# ---------------------


@cache
def _interpolation() -> dict[str, Any]:
    fx = printed(INTERP)
    t = table()
    arc = fx["input.arc_degrees"] * MINUTES
    q, rem = divmod(arc, t.step)
    q = int(q)
    increment = half_up(Fraction(rem) * (t.rsines[q] - t.rsines[q - 1]) / t.step)
    return {
        "input.arc_minutes": Fraction(arc),
        "input.divisor": Fraction(t.step),
        "input.table_interval": Fraction(t.step, MINUTES),
        "output.quotient": Fraction(q),
        "output.remainder": Fraction(rem),
        "input.sixth_sine": Fraction(t.rsines[q - 1]),
        "input.next_difference": Fraction(t.rsines[q] - t.rsines[q - 1]),
        "output.increment": increment,
        "output.sine": half_up(t.rsine(arc)),
    }


@pytest.mark.parametrize("name", sorted(_interpolation()))
def test_whitney_sine_of_24_degrees(name: str, record_comparison: Record) -> None:
    computed = _interpolation()[name]
    record_comparison(
        fixture=INTERP,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=WHITNEY + " (the table of ii.15–22 against the page's own figures)",
    )
    assert computed == printed(INTERP)[name]


def test_whitney_actual_sine_is_the_modern_value(record_comparison: Record) -> None:
    # Whitney's "actual value" is the modern sine in minutes of the radian (10800/π), not the
    # text's radius, to hundredths (checked with math)
    fx = printed(INTERP)
    radian = 180 * MINUTES / math.pi
    modern = round(radian * math.sin(math.radians(fx["input.arc_degrees"])), 2)
    computed = Fraction(str(modern))
    record_comparison(
        fixture=INTERP,
        value="output.actual_sine",
        computed=computed,
        tolerance=0,
        tolerance_reason="the modern value (10800/π) sin 24° to hundredths (math.sin), as "
        "Whitney gives it",
    )
    assert computed == fx["output.actual_sine"]


# --- Raṅganātha: the radius and the first sine differences (suryasiddhanta_hall_1859 pp. 66–68)
# ---------


def test_ranganatha_last_sine_is_the_table_s(record_comparison: Record) -> None:
    fx = printed(RADIUS)
    computed = Fraction(table().radius)
    record_comparison(
        fixture=RADIUS,
        value="output.last_sine",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (the twenty-fourth tabular sine; text_computed)",
    )
    assert computed == fx["output.last_sine"] == fx["output.diameter"] / 2


def test_ranganatha_radius_product(record_comparison: Record) -> None:
    fx = printed(RADIUS)
    circle = integer("circle.revolution.signs") * integer("circle.sign.degrees") * MINUTES
    computed = Fraction(circle * fx["input.multiplier_word"])
    record_comparison(
        fixture=RADIUS,
        value="output.product",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (the minutes of a circle times the diameter of the ratio)",
    )
    assert computed == fx["output.product"] and circle == fx["input.circle_minutes"]


def test_ranganatha_diameter_is_rounded_up(record_comparison: Record) -> None:
    # NOT reproduced by a stated rule: the quotient's fraction is below a
    # half; Raṅganātha prints the next whole number, whose half is the table's last sine
    fx = printed(RADIUS)
    quotient = Fraction(fx["output.product"], fx["input.divisor"])
    computed = half_up(quotient)
    record_comparison(
        fixture=RADIUS,
        value="output.diameter",
        computed=computed,
        tolerance=0,
        tolerance_reason=I162 + "the quotient to the nearest whole number; the commentary "
        "takes the next (text_computed; its fraction lies below a half)",
    )
    assert quotient - computed < Fraction(1, 2)
    assert computed + 1 == fx["output.diameter"]


@cache
def _differences() -> dict[str, Fraction]:
    """The commentary's chain (suryasiddhanta_hall_1859 p. 66–68): each sine divided by the first,
    the quotient
    to the nearest whole (a fraction above a half counted as one, l. 8); the first less the
    sum of the quotients is the next difference, added to the last sine the next sine."""
    first = table().rsines[0]
    sines = [Fraction(first)]
    quotients: list[Fraction] = []
    diffs: list[Fraction] = []
    for _ in range(4):
        quotients.append(half_up(sines[-1] / first))
        diffs.append(Fraction(first) - sum(quotients, Fraction(0)))
        sines.append(sines[-1] + diffs[-1])
    return {
        "output.quotient_1": quotients[0],
        "output.quotient_2": quotients[1],
        "output.first_less_quotients_sum_2": diffs[1],
        "output.khanda_3": sines[2],
        "output.quotient_3": quotients[2],
        "output.quotients_sum_3": quotients[0] + quotients[1] + quotients[2],
        "output.first_less_quotients_sum_3": diffs[2],
        "output.khanda_4": sines[3],
        "output.quotient_4": quotients[3],
        "output.first_less_prior_quotients_sum_4": diffs[2],
        "output.difference_5": diffs[3],
        "output.khanda_5": sines[4],
    }


@pytest.mark.parametrize("name", sorted(_differences()))
def test_ranganatha_sine_differences(name: str, record_comparison: Record) -> None:
    computed = _differences()[name]
    record_comparison(
        fixture=DIFFS,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (text_computed; the sines also equal the table's, ii.15–22)",
    )
    assert computed == printed(DIFFS)[name]
    sines = [_differences()[f"output.khanda_{n}"] for n in (3, 4, 5)]
    assert sines == [Fraction(s) for s in table().rsines[2:5]]


# --- Whitney: the Sun's and the Moon's equations (suryasiddhanta_burgess_1860 pp. 209–210)
# -----------------


@cache
def _sun() -> dict[str, Fraction]:
    fx = printed(SUN)
    anomaly = (fx["input.sun_apsis_longitude"] - fx["output.sun_mean_longitude"]) % CIRCLE
    _, _, bhuja, _ = bhuja_koti(anomaly)
    base = sine_of(bhuja)
    epicycle = minutes(corrected_epicycle(epicycles("sun", "manda"), base, r()))
    bhujaphala = half_up(base * epicycle / CIRCLE)
    eq = arc_of(bhujaphala)
    sign = 1 if anomaly < HALF else -1
    return {
        "output.sun_mean_anomaly": anomaly,
        "output.bhuja_arc": bhuja * MINUTES,  # printed in minutes and seconds
        "output.base_sine": base,
        "input.epicycle": epicycle,
        "output.bhujaphala": bhujaphala,
        "output.equation": eq * MINUTES,
        "output.sun_true_longitude": minutes(fx["output.sun_mean_longitude"] + sign * eq),
    }


@pytest.mark.parametrize("name", sorted(_sun()))
def test_whitney_sun_equation(name: str, record_comparison: Record) -> None:
    computed = _sun()[name]
    record_comparison(
        fixture=SUN, value=name, computed=computed, tolerance=0, tolerance_reason=WHITNEY
    )
    assert computed == printed(SUN)[name]


@cache
def _moon() -> dict[str, Fraction]:
    fx = printed(MOON)
    e = epicycles("moon", "manda")
    anomaly = (fx["output.apsis_longitude"] - fx["output.moon_mean_longitude"]) % CIRCLE
    quadrant, _, bhuja, koti = bhuja_koti(anomaly)
    base = sine_of(bhuja)
    contraction = abs(e.even - e.odd) * MINUTES
    diminution = half_up(base * contraction / r())
    epicycle = e.even - diminution / MINUTES  # ii.38: the even greater, the change subtracted
    bhujaphala = half_up(base * epicycle / CIRCLE)
    eq = arc_of(bhujaphala)
    sign = 1 if anomaly < HALF else -1
    return {
        "output.mean_anomaly": anomaly,
        "input.three_quadrants": Fraction(3 * (quadrant - 1)),
        "output.arc_md": anomaly - 3 * (quadrant - 1) * SIGN,
        "output.arc_am": bhuja,
        "output.base_sine": base,
        "output.perpendicular_sine": sine_of(koti),
        "input.epicycle_contraction": contraction,
        "output.epicycle_diminution": diminution,
        "output.epicycle_at_m": epicycle,
        "output.bhujaphala": bhujaphala,
        "input.first_tabular_sine_limit": Fraction(table().rsines[0]),
        "output.equation": eq,
        "output.moon_true_longitude": fx["input.moon_mean_longitude_final"] + sign * eq,
    }


MOON_PERP = "output.perpendicular_sine"


@pytest.mark.parametrize("name", [n for n in sorted(_moon()) if n != MOON_PERP])
def test_whitney_moon_equation(name: str, record_comparison: Record) -> None:
    computed = _moon()[name]
    record_comparison(
        fixture=MOON, value=name, computed=computed, tolerance=0, tolerance_reason=WHITNEY
    )
    assert computed == printed(MOON)[name]


def test_whitney_moon_perpendicular_sine_residual(record_comparison: Record) -> None:
    computed = _moon()[MOON_PERP]
    record_comparison(
        fixture=MOON,
        value=MOON_PERP,
        computed=computed,
        tolerance=0,
        tolerance_reason=I162 + "the tabular sine of the printed arc is one minute more than "
        "printed (the figure enters no later step)",
    )
    assert computed - printed(MOON)[MOON_PERP] == 1


# --- Whitney: Mercury's equation of the conjunction (suryasiddhanta_burgess_1860 p. 213)
# -------------------


@cache
def _mercury() -> dict[str, Fraction]:
    fx = printed(MERCURY)
    e = epicycles("mercury", "sighra")
    commutation = (fx["output.conjunction_longitude"] - fx["input.mean_longitude"]) % CIRCLE
    quadrant, _, bhuja, koti = bhuja_koti(commutation)
    # the sines of the arcs as printed, to the minute
    base, perp = sine_of(fx["output.bhuja_arc"]), sine_of(fx["output.koti_arc"])
    diminution = half_up(base * abs(e.even - e.odd) * MINUTES / r())
    epicycle = e.even - diminution / MINUTES
    bhujaphala = half_up(base * epicycle / CIRCLE)
    kotiphala = half_up(perp * epicycle / CIRCLE)
    # ii.40: the perpendicular-result added to the radius in the half-orbit from
    # Capricorn (quadrants 4 and 1), subtracted in that from Cancer
    side = r() + kotiphala if quadrant in (1, 4) else r() - kotiphala
    hyp = root(int(side * side + bhujaphala * bhujaphala))
    eq_sine = half_up(bhujaphala * r() / hyp)
    return {
        "output.mean_commutation": commutation,
        "output.bhuja_arc": minutes(bhuja),
        "output.koti_arc": minutes(koti),
        "output.base_sine": base,
        "output.perpendicular_sine": perp,
        "input.epicycle_difference": abs(e.even - e.odd),
        "output.diminution": diminution,
        "output.epicycle_at_m": epicycle,
        "output.bhujaphala": bhujaphala,
        "output.kotiphala": kotiphala,
        "input.radius": Fraction(r()),
        "output.perpendicular": side,
        "output.square_perpendicular": side * side,
        "output.square_bhujaphala": bhujaphala * bhujaphala,
        "output.sum_of_squares": side * side + bhujaphala * bhujaphala,
        "output.variable_hypotenuse": Fraction(hyp),
        "output.equation_sine": eq_sine,
        "output.equation": arc_of(eq_sine),
    }


@pytest.mark.parametrize("name", sorted(_mercury()))
def test_whitney_mercury_equation_of_the_conjunction(name: str, record_comparison: Record) -> None:
    computed = _mercury()[name]
    record_comparison(
        fixture=MERCURY, value=name, computed=computed, tolerance=0, tolerance_reason=WHITNEY
    )
    assert computed == printed(MERCURY)[name]


# --- Whitney: the four processes for the five planets (suryasiddhanta_burgess_1860 pp. 213–216)
# ------------

MEAN = "mean_longitude [s, deg, min, sec]"
CONJ = "longitude_of_conjunction [s, deg, min, sec]"
APSIS = "longitude_of_apsis [s, deg, min, sec]"
EQ_LONG = "equated_longitude [s, deg, min]"
BASE = "base_sine [min]"
EPI = "corrected_epicycle [deg, min]"
BRES = "result_from_base_sine [min]"
PRES = "result_from_perpendicular_sine [min]"
HYP = "variable_hypotenuse [min]"
SIGHRA_SIGN, SIGHRA_EQ = "equation_of_conjunction_sign", "equation_of_conjunction [sign, deg, min]"
MANDA_SIGN, MANDA_EQ = "equation_of_apsis_sign", "equation_of_apsis [sign, deg, min]"


def _dm(x: Fraction) -> tuple[int, int]:
    """Degrees to (degrees, minutes), the whole minute half up."""
    m = int(minutes(abs(x)) * MINUTES)
    return (m // MINUTES, m % MINUTES)


def _sdm(x: Fraction) -> tuple[int, int, int]:
    m = int(minutes(x % CIRCLE) * MINUTES)
    return (m // (SIGN * MINUTES), m // MINUTES % SIGN, m % MINUTES)


def _sdms(x: Fraction) -> tuple[int, int, int, int]:
    s = int(to_place(x % CIRCLE, 2) * MINUTES * MINUTES)
    return (s // (SIGN * 3600), s // 3600 % SIGN, s // MINUTES % MINUTES, s % MINUTES)


def _side(anomaly: Fraction) -> str:
    """The equation's sign: additive in the half-orbit from Aries (ii.45)."""
    return "+" if anomaly % CIRCLE < HALF else "−"


def _signed(sign: str, parts: tuple[int, ...]) -> Fraction:
    return angle(parts, "d") * (1 if sign == "+" else -1)


def _sighra_cells(body: str, commutation: Fraction, row: dict[str, Any]) -> dict[str, Any]:
    """The conjunction's figures for a printed row, each from the printed ones before it."""
    quadrant, _, bhuja, koti = bhuja_koti(commutation)
    base = sine_of(bhuja)
    printed_base = row[BASE]
    epicycle = corrected_epicycle(epicycles(body, "sighra"), Fraction(printed_base), r())
    ep = angle(row[EPI], "d")
    bres, pres = row[BRES], row[PRES]
    side = r() + pres if quadrant in (1, 4) else r() - pres
    hyp = root(side * side + bres * bres)
    return {
        BASE: int(base),
        EPI: _dm(epicycle),
        BRES: int(half_up(printed_base * ep / CIRCLE)),
        PRES: int(half_up(sine_of(koti) * ep / CIRCLE)),
        HYP: hyp,
        SIGHRA_SIGN: _side(commutation),
        SIGHRA_EQ: _dm(arc_of(half_up(Fraction(bres * r(), row[HYP])))),
    }


def _manda_cells(body: str, anomaly: Fraction, row: dict[str, Any]) -> dict[str, Any]:
    _, _, bhuja, _ = bhuja_koti(anomaly)
    printed_base = row[BASE]
    epicycle = corrected_epicycle(epicycles(body, "manda"), Fraction(printed_base), r())
    ep = angle(row[EPI], "d")
    return {
        BASE: int(sine_of(bhuja)),
        EPI: _dm(epicycle),
        MANDA_SIGN: _side(anomaly),
        MANDA_EQ: _dm(arc_of(half_up(printed_base * ep / CIRCLE))),
    }


def _rows(fixture: str, name: str) -> dict[str, dict[str, Any]]:
    return {row["planet"]: row for row in printed(fixture).rows(name)}


@cache
def _tables() -> dict[str, list[dict[str, Any]]]:
    """Every printed table of the four processes recomputed row by row."""
    first, second = (
        _rows(MERCURY, "output.first_process_table"),
        _rows(TRUE, "output.second_process_table"),
    )
    third, fourth = (
        _rows(TRUE, "output.third_process_table"),
        _rows(TRUE, "output.fourth_process_table"),
    )
    out: dict[str, list[dict[str, Any]]] = {"first": [], "second": [], "third": [], "fourth": []}
    for planet, row in first.items():
        body = planet.lower()
        mean, conj = angle(row[MEAN]), angle(row[CONJ])
        com = (conj - mean) % CIRCLE
        out["first"].append(
            {
                **row,
                "mean_commutation [s, deg, min, sec]": _sdms(com),
                **_sighra_cells(body, com, row),
            }
        )
        # ii.44: half the equation of the conjunction on the mean
        r2 = second[planet]
        p1 = mean + _signed(row[SIGHRA_SIGN], row[SIGHRA_EQ]) / 2
        an2 = (angle(r2[APSIS]) - angle(r2[EQ_LONG])) % CIRCLE
        out["second"].append(
            {
                **r2,
                EQ_LONG: _sdm(p1),
                "equated_anomaly [s, deg, min]": _sdm(an2),
                **_manda_cells(body, angle(r2["equated_anomaly [s, deg, min]"]), r2),
            }
        )
        # half the equation of the apsis on that
        r3 = third[planet]
        p2 = angle(r2[EQ_LONG]) + _signed(r2[MANDA_SIGN], r2[MANDA_EQ]) / 2
        an3 = (angle(r2[APSIS]) - angle(r3[EQ_LONG])) % CIRCLE
        out["third"].append(
            {
                **r3,
                EQ_LONG: _sdm(p2),
                "equated_anomaly [s, deg, min]": _sdm(an3),
                **_manda_cells(body, angle(r3["equated_anomaly [s, deg, min]"]), r3),
            }
        )
        # the whole equation of the apsis on the mean; the whole of the conjunction on that
        r4 = fourth[planet]
        p3 = mean + _signed(r3[MANDA_SIGN], r3[MANDA_EQ])
        com4 = (conj - angle(r4[EQ_LONG])) % CIRCLE
        cells = _sighra_cells(body, angle(r4["equated_commutation [s, deg, min]"]), r4)
        true = angle(r4[EQ_LONG]) + _signed(r4[SIGHRA_SIGN], r4[SIGHRA_EQ])
        out["fourth"].append(
            {
                **r4,
                EQ_LONG: _sdm(p3),
                "equated_commutation [s, deg, min]": _sdm(com4),
                **cells,
                "true_longitude [s, deg, min]": _sdm(true),
            }
        )
    return out


# (table, planet, column) where Whitney prints another figure than the rule gives from
# his preceding figures
RESIDUAL: set[tuple[str, str, str]] = {
    ("first", "Venus", EPI),
    ("first", "Mars", PRES),
    ("second", "Saturn", EQ_LONG),
    ("second", "Jupiter", MANDA_EQ),
    ("third", "Jupiter", EQ_LONG),
    ("third", "Jupiter", MANDA_EQ),
}
TABLES = {
    "first": (MERCURY, "output.first_process_table"),
    "second": (TRUE, "output.second_process_table"),
    "third": (TRUE, "output.third_process_table"),
    "fourth": (TRUE, "output.fourth_process_table"),
}


@pytest.mark.parametrize("which", sorted(TABLES))
def test_whitney_four_processes(which: str, record_comparison: Record) -> None:
    fixture, name = TABLES[which]
    computed = _tables()[which]
    residual = {k[1:] for k in RESIDUAL if k[0] == which}
    record_comparison(
        fixture=fixture,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=WHITNEY
        + (f"; {I162}{len(residual)} cells (listed in RESIDUAL)" if residual else ""),
    )
    for row, comp in zip(printed(fixture).rows(name), computed, strict=True):
        for col, value in row.items():
            key = (row["planet"], col)
            if key in residual:
                assert comp[col] != value, key
            else:
                assert comp[col] == value, key


# --- Whitney: the latitudes (suryasiddhanta_burgess_1860 pp. 229–230)
# --------------------------------------

LAT_NODE = "longitude_of_node [s, deg, min, sec]"
LAT_CNODE = "node_corrected [s, deg, min]"
LAT_DIST = "distance_from_node [s, deg, min]"


@cache
def _latitudes() -> list[dict[str, Any]]:
    """ii.56–57: the node corrected (Mars, Jupiter, Saturn: by the equation of the
    conjunction, as the planet; Mercury, Venus: by the third process's equation of the
    apsis, reversed), the distance from it (Mercury, Venus: of the conjunction), its sine
    times the extreme latitude over the last hypotenuse (the Moon: over the radius)."""
    third, fourth = (
        _rows(TRUE, "output.third_process_table"),
        _rows(TRUE, "output.fourth_process_table"),
    )
    first = _rows(MERCURY, "output.first_process_table")
    out = []
    for row in printed(LATITUDE).rows("output.latitude_table"):
        planet = row["planet"]
        p = model().planets[planet.lower()]
        cells: dict[str, Any] = {}
        divisor: Fraction | int = r()
        if planet != "Moon":
            r3, r4 = third[planet], fourth[planet]
            divisor = r4[HYP]
            node = angle(row[LAT_NODE])
            if p.mean == p.body:
                corrected = node + _signed(r4[SIGHRA_SIGN], r4[SIGHRA_EQ])
                place = angle(r4["true_longitude [s, deg, min]"])
            else:
                corrected = node - _signed(r3[MANDA_SIGN], r3[MANDA_EQ])
                place = angle(first[planet][CONJ])
            cells[LAT_CNODE] = _sdm(corrected)
            cells[LAT_DIST] = _sdm(place - angle(row[LAT_CNODE]))
        distance = angle(row[LAT_DIST])
        _, _, bhuja, _ = bhuja_koti(distance)
        cells["sine [min]"] = int(sine_of(bhuja))
        assert p.extreme_latitude is not None
        cells["latitude [deg, min, direction]"] = _dm(
            Fraction(row["sine [min]"]) * p.extreme_latitude / divisor / MINUTES
        )
        cells["latitude_direction"] = "N" if distance < HALF else "S"
        out.append({**row, **cells})
    return out


def test_whitney_latitudes(record_comparison: Record) -> None:
    name = "output.latitude_table"
    computed = _latitudes()
    record_comparison(
        fixture=LATITUDE, value=name, computed=computed, tolerance=0, tolerance_reason=WHITNEY
    )
    assert computed == printed(LATITUDE).rows(name)


@cache
def _node_distance() -> dict[str, Fraction]:
    fx = printed(NODE)
    eq = fx["input.mercury_apsis_equation"]
    node, conj = fx["input.mercury_node_longitude"], fx["input.mercury_conjunction_longitude"]
    return {
        "output.jupiter_heliocentric_node_distance": fx["input.jupiter_heliocentric_longitude"]
        - fx["input.jupiter_node_longitude"],
        "output.jupiter_node_distance_hindu": fx["input.jupiter_geocentric_longitude"]
        - fx["input.jupiter_corrected_node_longitude"],
        "output.mercury_equated_conjunction": conj - eq,
        "output.mercury_node_distance": conj - eq - node,
        "output.mercury_equated_node": node + eq,
        "output.mercury_node_distance_hindu": conj - (node + eq),
    }


@pytest.mark.parametrize("name", sorted(_node_distance()))
def test_whitney_distance_from_the_node(name: str, record_comparison: Record) -> None:
    computed = _node_distance()[name]
    record_comparison(
        fixture=NODE,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (whole minutes; ii.56–57: the equation applied to the node "
        "reversed, or to the conjunction directly)",
    )
    assert computed == printed(NODE)[name]


# --- Rao: equations by continuous sines (balachandra_rao_2000 pp. 93–127)
# --------------------------


def _rao_manda(anomaly_deg: Fraction, even: int, odd: Fraction) -> Fraction:
    """Rao's route (balachandra_rao_2000 pp. 91–92): periphery p_e − (p_e − p_o)|sin m|, equation
    R (p / 360) sin m in minutes, by math.sin."""
    m = math.radians(float(anomaly_deg))
    p = even - float(even - odd) * abs(math.sin(m))
    return Fraction(r() * p / CIRCLE * math.sin(m))


def _seconds(minutes_value: Fraction | float) -> Fraction:
    return half_up(Fraction(minutes_value) * MINUTES) / (MINUTES * MINUTES)


def _decimal_at(fixture: str, name: str) -> Fraction:
    """Half a unit of the last decimal printed in a decimal value."""
    raw = str(printed(fixture)._by_name[name].raw["value"])
    places = len(raw.split(".")[1]) if "." in raw else 0
    return Fraction(1, 2 * 10**places)


@pytest.mark.parametrize("body", ["sun", "moon"])
def test_rao_manda_equations(body: str, record_comparison: Record) -> None:
    # NOT reproduced: the engine's tabular equation at Rao's anomaly differs from
    # his; his equation is the difference of his two terms (continuous sines; for the Sun
    # his sine is not the sine of his printed anomaly), to the second
    fx = printed(RAO_MANDA)
    anomaly = fx[f"output.{body}.anomaly"]
    computed = manda_equation(epicycles(body, "manda"), anomaly, table(), CIRCLE).degrees
    name = f"output.{body}.equation"
    record_comparison(
        fixture=RAO_MANDA,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=I162 + "the engine's tabular equation at Rao's anomaly; his seconds "
        "come from his continuous sines",
    )
    t1, t2 = abs(fx[f"output.{body}.term_1"]), abs(fx[f"output.{body}.term_2"])
    eq_min = abs(fx[f"output.{body}.equation_min"])
    assert abs(t1 - t2 - eq_min) <= _decimal_at(RAO_MANDA, f"output.{body}.equation_min")
    assert _seconds(eq_min) == abs(fx[name])
    assert to_place(abs(computed), 2) != abs(fx[name])


def test_rao_jupiter_manda(record_comparison: Record) -> None:
    fx = printed(RAO_JUPITER)
    anomaly = fx["output.jupiter.anomaly"]
    e = epicycles("jupiter", "manda")
    computed = manda_equation(e, anomaly, table(), CIRCLE).degrees
    name = "output.jupiter.mandaphala"
    record_comparison(
        fixture=RAO_JUPITER,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=I162 + "the engine's tabular equation at Rao's anomaly; his seconds "
        "come from continuous sines",
    )
    his = _rao_manda(anomaly, int(e.even), e.odd)
    assert _seconds(abs(his)) == fx[name]
    assert to_place(abs(computed), 2) != fx[name]


def _rao_sighra(anomaly_deg: Fraction, even: int, odd: int) -> Fraction:
    m = math.radians(float(anomaly_deg))
    p = even - (even - odd) * abs(math.sin(m))
    dohphala = r() * p / CIRCLE * math.sin(m)
    kotiphala = r() * p / CIRCLE * math.cos(m)
    karna = math.hypot(r() + kotiphala, dohphala)
    return Fraction(math.degrees(math.asin(dohphala / karna)))


@pytest.mark.parametrize("body", ["mercury", "saturn"])
def test_rao_sighra_equations(body: str, record_comparison: Record) -> None:
    fx = printed(RAO_SIGHRA)
    anomaly = fx[f"output.{body}.sighra_anomaly"]
    e = epicycles(body, "sighra")
    computed = sighra_equation(e, anomaly, table(), CIRCLE, model().karna_resolution).degrees
    name = f"output.{body}.sighraphala"
    record_comparison(
        fixture=RAO_SIGHRA,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=I162 + "the engine's tabular equation at Rao's anomaly; his seconds "
        "come from continuous sines",
    )
    his = _rao_sighra(anomaly, int(e.even), int(e.odd))
    assert abs(to_place(abs(his), 2) - fx[name]) <= Fraction(1, 3600)
    assert to_place(abs(computed), 2) != fx[name]


def test_rao_saturn_four_steps(record_comparison: Record) -> None:
    fx = printed(RAO_SATURN)
    name = "output.saturn.p4"
    computed = (
        fx["output.saturn.p3"]
        + sighra_equation(
            epicycles("saturn", "sighra"),
            fx["output.saturn.sighra_anomaly_2"],
            table(),
            CIRCLE,
            model().karna_resolution,
        ).degrees
    )
    record_comparison(
        fixture=RAO_SATURN,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=I162 + "the last step by the engine's tabular equation from Rao's "
        "third place; his seconds come from continuous sines",
    )
    e = epicycles("saturn", "sighra")
    anomaly = fx["output.saturn.sighra_anomaly_2"]
    his = fx["output.saturn.p3"] + _rao_sighra(anomaly, int(e.even), int(e.odd))
    assert abs(to_place(his, 2) - fx[name]) <= Fraction(1, 3600)
    assert to_place(computed, 2) != fx[name]
