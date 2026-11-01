"""The Sūrya-siddhānta's mean places against the printed examples.

The rule ``mean.revolutions_from_creation`` (i.53–54): the count of days
from creation times the revolutions, divided by the civil days of the
period the revolutions are stated for; a node's place the remainder
subtracted from a circle. The engine's places (``SuryaModel.elements``) at
the counts the editors print, rounded half up at the place they print
(Whitney says so of his figures, suryasiddhanta_burgess_1860 p. 210; Rao and Raṅganātha state no
rule), against Whitney's tables (suryasiddhanta_burgess_1860), Raṅganātha's places at the end of
the Kṛta (suryasiddhanta_hall_1859, ``text_computed``), Parameśvara's at the Kali epoch
(suryasiddhanta_paramesvara_1957,
``text_computed``) and Rao's (balachandra_rao_2000). Every cell an editor prints that the
rule does not give is a residual, asserted as such; none is absorbed by a tolerance.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction
from functools import cache

import pytest
from authority_kit import printed
from surya_kit import (
    CIRCLE,
    EXACT,
    FX,
    METHODS,
    MINUTES,
    SIGN,
    day,
    half_up,
    integer,
    model,
    to_place,
    value,
)

from jyotirganita.core.calendar import jdn_from_gregorian
from jyotirganita.core.types import GregorianDate

Record = Callable[..., None]
MEAN_SUN = FX + "whitney_mean_sun"
PLACES = FX + "whitney_mean_places"
PERIODS = FX + "whitney_periods_mean_motions"
EPOCH = FX + "whitney_apsides_nodes_kali_epoch"
AEON = FX + "whitney_apsides_nodes_periods"
WASHINGTON = FX + "whitney_mean_places_washington_interval"
KRTA = FX + "ranganatha_krta_end_apsides_nodes"
KALI_START = FX + "paramesvara_kali_start_positions"
RAO = FX + "rao_mean_sun_moon_apogee_node"
RAO_PLANETS = FX + "rao_mean_planets"
SECONDS = "the printed whole second, the exact place rounded half up"
I162 = "NOT reproduced: "

# Whitney's row names and the engine's elements
WHITNEY = {
    "sun": "sun",
    "mercury": "mercury_sighrocca",
    "venus": "venus_sighrocca",
    "mars": "mars",
    "jupiter": "jupiter",
    "saturn": "saturn",
    "moon": "moon",
    "moon_apsis": "moon_apogee",
    "moon_node": "moon_node",
}


NODES = {"moon_node"}


def mean(element: str, days: Fraction | int, method: str = "suryasiddhanta") -> Fraction:
    return model(method).elements.mean(element, Fraction(days))


def revolutions(element: str, days: Fraction | int) -> Fraction:
    e = model().elements
    return Fraction(e.revolutions[element]) * days / e.civil_days[element]


@cache
def count_1860() -> int:
    """The engine's count from creation at Laṅkā's midnight beginning 1860 Jan 1."""
    return day(jdn_from_gregorian(GregorianDate(1860, 1, 1))).creation_count


def krta_end() -> int:
    """The count from creation to the end of the Kṛta: the Kali epoch's less two quarters."""
    shares = integer("yuga.quarters.share.treta") + integer("yuga.quarters.share.dvapara")
    days = shares * value("yuga.quarters.part") * integer("yuga.civil_days")
    assert days.denominator == 1
    return model().days_to_epoch - int(days)


# --- Whitney's mean Sun and mean places at 1860 Jan 1 (suryasiddhanta_burgess_1860 p. 178)
# -----------------


def _mean_sun() -> dict[str, Fraction]:
    days = printed(MEAN_SUN)["input.sum_of_days"]
    sun = to_place(mean("sun", days), 2)
    return {
        "output.sun_revolutions": Fraction(int(revolutions("sun", days))),
        "output.sun_mean_longitude_rdms": sun,
        "output.sun_mean_longitude_degrees": sun,
    }


@pytest.mark.parametrize("name", sorted(_mean_sun()))
def test_whitney_mean_sun(name: str, record_comparison: Record) -> None:
    computed = _mean_sun()[name]
    record_comparison(
        fixture=MEAN_SUN, value=name, computed=computed, tolerance=0, tolerance_reason=SECONDS
    )
    assert computed == printed(MEAN_SUN)[name]


# Whitney reckons from the Kali epoch with the revolutions of the lesser period
# (1,080,000 years), the Moon's apsis and node with their places at the epoch added;
# three of his seconds differ from the rule's by one
PLACE_RESIDUAL = {"venus": -1, "moon_apsis": -1, "moon_node": 1}


def _places() -> dict[str, Fraction]:
    out: dict[str, Fraction] = {}
    c, k = count_1860(), model().days_to_epoch
    for row, element in WHITNEY.items():
        out[f"output.{row}.mean_place"] = to_place(mean(element, c), 2)
        whole = int(revolutions(element, c)) - int(revolutions(element, k))
        # a node's revolutions are printed with a minus sign (i.54: retrograde)
        out[f"output.{row}.revolutions"] = Fraction(-whole if element in NODES else whole)
    return out


@pytest.mark.parametrize(
    "name", [n for n in sorted(_places()) if n.split(".")[1] not in PLACE_RESIDUAL]
)
def test_whitney_mean_places_1860(name: str, record_comparison: Record) -> None:
    computed = _places()[name]
    record_comparison(
        fixture=PLACES, value=name, computed=computed, tolerance=0, tolerance_reason=SECONDS
    )
    assert computed == printed(PLACES)[name]


@pytest.mark.parametrize("row", sorted(PLACE_RESIDUAL))
def test_whitney_mean_places_1860_residual(row: str, record_comparison: Record) -> None:
    name = f"output.{row}.mean_place"
    computed = _places()[name]
    record_comparison(
        fixture=PLACES,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=I162 + "the rule's place to the second differs from Whitney's by one "
        "second (his lesser-period route, suryasiddhanta_burgess_1860 p. 178)",
    )
    diff = (printed(PLACES)[name] - computed) * MINUTES * MINUTES
    assert diff == PLACE_RESIDUAL[row]


@pytest.mark.parametrize("row", sorted(PLACE_RESIDUAL))
def test_whitney_mean_places_1860_residual_revolutions(row: str, record_comparison: Record) -> None:
    name = f"output.{row}.revolutions"
    computed = _places()[name]
    record_comparison(
        fixture=PLACES, value=name, computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == printed(PLACES)[name]


# --- Whitney's periods and mean daily motions (suryasiddhanta_burgess_1860 p. 161)
# ---------------------------

PERIOD_ROWS = {**{k: v for k, v in WHITNEY.items() if k != "moon"}, "moon_sidereal": "moon"}
PARTS = ("degrees", "minutes", "seconds", "thirds", "fourths")


def _rate(row: str) -> tuple[int, int]:
    """(revolutions in the age, civil days in the age) of a row of the table."""
    e = model().elements
    if row == "moon_synodic":
        # i.35: the lunar months are the Moon's revolutions less the Sun's
        return e.revolutions["moon"] - e.revolutions["sun"], e.civil_days["moon"]
    element = PERIOD_ROWS[row]
    return e.revolutions[element], e.civil_days[element]


def _period_days(row: dict[str, object]) -> Fraction:
    """A printed period in days: days, nāḍīs, vināḍīs and respirations (i.11)."""
    pranas = integer("time.vinadi.pranas")
    return (
        Fraction(str(row["days"]))
        + Fraction(str(row["nadis"])) / MINUTES
        + Fraction(str(row["vinadis"])) / MINUTES**2
        + Fraction(str(row["respirations"])) / (MINUTES**2 * pranas)
    )


def _motion_degrees(row: dict[str, object]) -> Fraction:
    return sum((Fraction(str(row[h] or 0)) / MINUTES**i for i, h in enumerate(PARTS)), Fraction(0))


@cache
def _periods() -> dict[str, tuple[Fraction, Fraction]]:
    """Per printed value: (computed, printed), each in days or degrees at the printed place:
    hundredths of a respiration, tenths of a fourth (half up)."""
    fx = printed(PERIODS)
    respiration = Fraction(1, MINUTES**2 * integer("time.vinadi.pranas"))
    fourth = Fraction(1, MINUTES**4)
    part = Fraction(printed(FX + "whitney_yuga_days")["input.sidereal_solar_years.part_1080000"])
    part /= integer("mahayuga.solar_years")
    out: dict[str, tuple[Fraction, Fraction]] = {}
    for row in [*PERIOD_ROWS, "moon_synodic"]:
        rev, days = _rate(row)
        period = Fraction(days, rev)
        motion = Fraction(rev * CIRCLE, days)
        (p,) = fx.rows(f"output.{row}.length_of_revolution")
        (m,) = fx.rows(f"output.{row}.mean_daily_motion")
        out[f"output.{row}.length_of_revolution"] = (
            half_up(period, respiration / 100),
            _period_days(p),
        )
        out[f"output.{row}.mean_daily_motion"] = (half_up(motion, fourth / 10), _motion_degrees(m))
        lesser = f"output.{row}.revolutions_1080000_years"
        printed_lesser = fx[lesser]
        if isinstance(printed_lesser, int):
            out[lesser] = (rev * part, Fraction(printed_lesser))
        else:
            (w,) = fx.rows(lesser)
            out[lesser] = (rev * part, w["whole"] + Fraction(str(w["fraction"])))
    return out


# the fraction of the Moon's apsis in 1,080,000 years: both reads after the third look
# give a numerator the quarter of the 4,320,000-year column does not
PERIOD_RESIDUAL = "output.moon_apsis.revolutions_1080000_years"


@pytest.mark.parametrize("name", [n for n in sorted(_periods()) if n != PERIOD_RESIDUAL])
def test_whitney_periods_and_daily_motions(name: str, record_comparison: Record) -> None:
    computed, expected = _periods()[name]
    record_comparison(
        fixture=PERIODS,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason="at the printed place (hundredths of a respiration, tenths of a "
        "fourth, the lesser period's quarter exact), half up",
    )
    assert computed == expected


def test_whitney_moon_apsis_quarter_residual(record_comparison: Record) -> None:
    computed, expected = _periods()[PERIOD_RESIDUAL]
    record_comparison(
        fixture=PERIODS,
        value=PERIOD_RESIDUAL,
        computed=computed,
        tolerance=0,
        tolerance_reason=I162 + "the quarter of the 4,320,000-year revolutions gives a "
        "numerator 5 less than the one read in print; the whole part agrees",
    )
    assert expected - computed == Fraction(5, 4)
    (row,) = printed(PERIODS).rows(PERIOD_RESIDUAL)
    assert int(computed) == row["whole"]


# --- the apsides and nodes at the Kali epoch and their periods (suryasiddhanta_burgess_1860 p. 171)
# ----------

APSIDES_NODES = [
    *(f"{b}_apsis" for b in ("sun", "mercury", "venus", "mars", "jupiter", "saturn")),
    *(f"{b}_node" for b in ("mercury", "venus", "mars", "jupiter", "saturn")),
]


@cache
def _kali_epoch() -> dict[str, Fraction]:
    n = model().days_to_epoch
    out: dict[str, Fraction] = {}
    for e in APSIDES_NODES:
        out[f"output.{e}.position"] = to_place(mean(e, n), 2)
        r = revolutions(e, n)
        # a node's revolutions are printed with a minus sign, counted to the place
        # subtracted from the circle (i.54)
        whole = int(r) if e.endswith("_apsis") else int(-r // 1)
        out[f"output.{e}.revolutions"] = Fraction(whole)
    return out


@pytest.mark.parametrize("name", sorted(_kali_epoch()))
def test_whitney_apsides_and_nodes_at_the_kali_epoch(name: str, record_comparison: Record) -> None:
    computed = _kali_epoch()[name]
    record_comparison(
        fixture=EPOCH, value=name, computed=computed, tolerance=0, tolerance_reason=SECONDS
    )
    assert computed == printed(EPOCH)[name]


@cache
def _aeon() -> dict[str, Fraction]:
    years = integer("mahayuga.solar_years") * integer("kalpa.multiplier")
    tenth = Fraction(1, 10)
    minutes_in_circle = CIRCLE * MINUTES
    out: dict[str, Fraction] = {}
    for e in APSIDES_NODES:
        r = model().elements.revolutions[e]
        out[f"output.{e}.time_of_revolution"] = half_up(Fraction(years, r), tenth)
        out[f"output.{e}.years_to_one_minute"] = half_up(
            Fraction(years, r * minutes_in_circle), tenth
        )
    return out


AEON_RESIDUAL = "output.saturn_node.time_of_revolution"


@pytest.mark.parametrize("name", [n for n in sorted(_aeon()) if n != AEON_RESIDUAL])
def test_whitney_apsides_and_nodes_periods(name: str, record_comparison: Record) -> None:
    computed = _aeon()[name]
    record_comparison(
        fixture=AEON,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason="the aeon's years over the text's revolutions, to the printed tenth",
    )
    assert computed == printed(AEON)[name]


def test_whitney_saturn_node_period_residual(record_comparison: Record) -> None:
    computed = _aeon()[AEON_RESIDUAL]
    record_comparison(
        fixture=AEON,
        value=AEON_RESIDUAL,
        computed=computed,
        tolerance=0,
        tolerance_reason=I162 + "the aeon's years over the node's revolutions give 1.6 years "
        "more than printed; the same row's years to one minute agree (both reads agree on it)",
    )
    fx = printed(AEON)
    assert computed - fx[AEON_RESIDUAL] == Fraction(16, 10)
    assert (
        _aeon()["output.saturn_node.years_to_one_minute"]
        == fx["output.saturn_node.years_to_one_minute"]
    )


# --- the epoch advance (i.67): Whitney's means for Washington's time ---------------


def _interval_days() -> Fraction:
    (row,) = printed(WASHINGTON).rows("input.interval_nadis_vinadis_pranas")
    pranas = integer("time.vinadi.pranas")
    return (
        Fraction(row["nadis"]) / MINUTES
        + Fraction(row["vinadis"]) / MINUTES**2
        + Fraction(str(row["respirations"])) / (MINUTES**2 * pranas)
    )


def _equinox() -> Fraction:
    (row,) = printed(WASHINGTON).rows("input.equinox_from_initial_point")
    return (
        Fraction(row["degrees"])
        + Fraction(row["minutes"]) / MINUTES
        + Fraction(str(row["seconds"])) / MINUTES**2
    )


@cache
def _washington() -> dict[str, Fraction]:
    """Whitney's mean places at Ujjayinī's midnight (suryasiddhanta_burgess_1860 p. 178, his
    figures) carried by the
    mean motion for the interval (i.67, ``carry.epoch_advance_mean``) and reckoned from the
    equinox of the date (suryasiddhanta_burgess_1860 p. 187); the seconds' fraction dropped, as
    every printed figure
    shows (inferred: each body's fraction lies between a tenth and nine tenths)."""
    iv = _interval_days()
    places = printed(PLACES)
    out: dict[str, Fraction] = {}
    for row, e in WHITNEY.items():
        carried = places[f"output.{row}.mean_place"] + model().elements.motion(e) * iv
        seconds = ((carried + _equinox()) % CIRCLE) * MINUTES * MINUTES
        out[f"output.{row}.mean_longitude_washington"] = Fraction(
            seconds.numerator // seconds.denominator, MINUTES * MINUTES
        )
    return out


WASHINGTON_SUN = "output.sun.mean_longitude_washington"


@pytest.mark.parametrize("name", [n for n in sorted(_washington()) if n != WASHINGTON_SUN])
def test_whitney_mean_places_for_washington(name: str, record_comparison: Record) -> None:
    computed = _washington()[name]
    record_comparison(
        fixture=WASHINGTON,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason="the printed whole second, the carried place's fraction dropped",
    )
    assert computed == printed(WASHINGTON)[name]


def test_whitney_sun_for_washington_residual(record_comparison: Record) -> None:
    computed = _washington()[WASHINGTON_SUN]
    record_comparison(
        fixture=WASHINGTON,
        value=WASHINGTON_SUN,
        computed=computed,
        tolerance=0,
        tolerance_reason=I162 + "the carried Sun differs from the printed by exactly half a "
        "circle (a misprint or Whitney's slip; both reads agree on the printed figure)",
    )
    assert computed - printed(WASHINGTON)[WASHINGTON_SUN] == CIRCLE // 2


# --- Raṅganātha's apsides and nodes at the end of the Kṛta (suryasiddhanta_hall_1859 p. 43)
# --------------

KRTA_ROWS = [
    *(f"output.{b}.apsis" for b in ("sun", "mars", "mercury", "jupiter", "venus", "saturn")),
    *(f"output.{b}.node" for b in ("mars", "mercury", "jupiter", "venus", "saturn")),
]


@cache
def _krta() -> dict[str, Fraction]:
    k = krta_end()
    out: dict[str, Fraction] = {}
    for name in KRTA_ROWS:
        _, body, kind = name.split(".")
        e = f"{body}_{kind}"
        r = revolutions(e, k)
        # the node as Raṅganātha prints it: the remainder of its revolutions, before the
        # subtraction from the circle (i.54); inferred from the reproduction
        place = mean(e, k) if kind == "apsis" else (r - int(r)) * CIRCLE
        out[name] = to_place(place, 2)
    return out


KRTA_RESIDUAL = {"output.mars.node", "output.saturn.apsis"}


@pytest.mark.parametrize("name", [n for n in KRTA_ROWS if n not in KRTA_RESIDUAL])
def test_ranganatha_apsides_and_nodes_at_the_end_of_the_krta(
    name: str, record_comparison: Record
) -> None:
    computed = _krta()[name]
    record_comparison(
        fixture=KRTA,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=SECONDS + " (text_computed; the Venus node as the edition's errata "
        "correct it)",
    )
    assert computed == printed(KRTA)[name]


def test_ranganatha_mars_node_residual(record_comparison: Record) -> None:
    name = "output.mars.node"
    computed = _krta()[name]
    record_comparison(
        fixture=KRTA,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=I162 + "the rule gives the printed degrees and minutes; the seconds "
        "differ by twelve (text_computed: a misprint, a slip or the reading; second read pending)",
    )
    assert (computed - printed(KRTA)[name]) * MINUTES * MINUTES == 12


def test_ranganatha_saturn_apsis_residual(record_comparison: Record) -> None:
    name = "output.saturn.apsis"
    computed = _krta()[name]
    record_comparison(
        fixture=KRTA,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=I162 + "the printed apsis repeats the printed Saturn node to the "
        "second; the rule's apsis is far from it (a misprint or the reading; second read pending)",
    )
    fx = printed(KRTA)
    assert fx[name] == fx["output.saturn.node"] != computed


@pytest.mark.parametrize(
    ("name", "element"),
    [("input.moon_apogee_signs_word", "moon_apogee"), ("input.moon_node_signs_word", "moon_node")],
)
def test_ranganatha_moon_at_the_end_of_the_krta(
    name: str, element: str, record_comparison: Record
) -> None:
    computed = mean(element, krta_end()) / SIGN
    record_comparison(
        fixture=KRTA,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (whole signs)",
    )
    assert computed == printed(KRTA)[name]


# --- Parameśvara: the places at the Kali epoch (suryasiddhanta_paramesvara_1957 p. 6)
# ----------------------------
# Run under both methods the fixture names: the places at the
# Kali epoch depend on the fractional part of the elapsed count times each revolution
# number, so whether suryasiddhanta_paramesvara_1957's two numbers leave the Moon's apogee and node
# where the
# commentary puts them is this test's result, not an assumption.


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(
    ("name", "element"),
    [
        ("output.p6.moon_apogee_additive", "moon_apogee"),
        ("output.p6.moon_node_additive", "moon_node"),
    ],
)
def test_paramesvara_moon_at_the_kali_epoch(
    name: str, element: str, method: str, record_comparison: Record
) -> None:
    computed = mean(element, model(method).days_to_epoch, method) / SIGN
    record_comparison(
        fixture=KALI_START,
        value=name,
        method=method,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (whole signs; text_computed)",
    )
    assert computed == printed(KALI_START)[name]


@pytest.mark.parametrize("method", METHODS)
def test_paramesvara_planets_at_the_end_of_mina(method: str, record_comparison: Record) -> None:
    # "all the planets at the end of Mīna": every planet's place, and the Sun's and
    # Moon's, at the Kali epoch is the whole circle (nought)
    n = model(method).days_to_epoch
    planets = ("sun", "moon", "mars", "mercury_sighrocca", "jupiter", "venus_sighrocca", "saturn")
    computed = max(mean(e, n, method) for e in planets)
    record_comparison(
        fixture=KALI_START,
        value="output.p6.planets",
        method=method,
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT + " (the end of the last sign is nought; text_computed)",
    )
    assert computed == 0


# --- Rao: the mean Sun, Moon, apogee and node for 1991 March 22 (balachandra_rao_2000 p. 78) ------


@cache
def _rao() -> dict[str, Fraction]:
    fx = printed(RAO)
    a = fx["input.kali_ahargana"]
    n = model().days_to_epoch + a
    out: dict[str, Fraction] = {}
    for body in ("sun", "moon", "moon_apogee", "moon_node"):
        out[f"output.{body}.mean_longitude"] = to_place(mean(body, n), 2)
    for body in ("sun", "moon", "moon_apogee", "moon_node"):
        out[f"output.{body}.revolutions"] = Fraction(int(revolutions(body, a)))
    for body in ("moon_apogee", "moon_node"):
        r = revolutions(body, a)
        out[f"output.{body}.motion"] = to_place((r - int(r)) * CIRCLE, 2)
    half = CIRCLE // 2
    out["output.ketu.mean_longitude"] = to_place((mean("moon_node", n) + half) % CIRCLE, 2)
    return out


# Rao's decimal arithmetic (products to six figures) leaves these one second above
# the rule's place
RAO_RESIDUAL = {
    "output.moon.mean_longitude",
    "output.moon_apogee.mean_longitude",
    "output.moon_apogee.motion",
}


@pytest.mark.parametrize("name", [n for n in sorted(_rao()) if n not in RAO_RESIDUAL])
def test_rao_mean_sun_moon_apogee_node(name: str, record_comparison: Record) -> None:
    computed = _rao()[name]
    record_comparison(
        fixture=RAO, value=name, computed=computed, tolerance=0, tolerance_reason=SECONDS
    )
    assert computed == printed(RAO)[name]


@pytest.mark.parametrize("name", sorted(RAO_RESIDUAL))
def test_rao_mean_moon_and_apogee_residual(name: str, record_comparison: Record) -> None:
    computed = _rao()[name]
    record_comparison(
        fixture=RAO,
        value=name,
        computed=computed,
        tolerance=0,
        tolerance_reason=I162 + "one second from the rule's place (Rao's six-figure products)",
    )
    assert (computed - printed(RAO)[name]) * MINUTES * MINUTES == 1


RAO_ELEMENTS = ("mars", "mercury_sighrocca", "jupiter", "venus_sighrocca", "saturn")


def _decimals(fixture: str, name: str) -> int:
    raw = str(printed(fixture)._by_name[name].raw["value"])
    return len(raw.split(".")[1]) if "." in raw else 0


@pytest.mark.parametrize("element", RAO_ELEMENTS)
def test_rao_mean_planets_rest_on_his_decimal_motions(
    element: str, record_comparison: Record
) -> None:
    # NOT reproduced: Rao multiplies the days by daily motions cut at the
    # seventh decimal of a degree and rounds the product before reducing it by whole
    # circles; the rule's place differs from the days times his motion by no more than
    # the days times a unit of that decimal, and his rounded product gives his place
    fx = printed(RAO_PLANETS)
    a = fx["input.kali_ahargana"]
    name = f"output.{element}.mean_longitude"
    exact = mean(element, model().days_to_epoch + a)
    record_comparison(
        fixture=RAO_PLANETS,
        value=name,
        computed=exact,
        tolerance=0,
        tolerance_reason=I162 + "the rule's exact place; Rao's rests on his truncated decimal "
        "motions and rounded products",
    )
    motion = fx[f"input.{element}.daily_motion"]
    assert motion * 10**7 == int(motion * 10**7)
    gap = (exact - a * motion + CIRCLE / 2) % CIRCLE - CIRCLE / 2
    assert 0 < abs(gap) <= a * Fraction(1, 10**7)
    product_name = f"output.{element}.motion_deg"
    product = fx[product_name]
    assert abs(a * motion - product) <= Fraction(1, 2 * 10 ** _decimals(RAO_PLANETS, product_name))
    places = 1 if element.endswith("sighrocca") else 2
    assert to_place(product % CIRCLE, places) == fx[name] != to_place(exact, places)
