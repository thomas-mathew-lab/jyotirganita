"""Mean longitudes by the yuga rule against Bhāskara I's problems as Shukla solves them.

mahabhaskariya_1960 (Mahābhāskarīya I and VIII) and laghubhaskariya_1963's appendix pose the inverse
problem: from a residue or a longitude, find the ahargaṇa (the kuṭṭaka,
the pulveriser). The inverse search is ``search/``'s; what these examples
witness here is the forward rule ``mean.yuga_rate_successive_division``
(laghubhaskariya_1963 I.15–17): the printed answer's ahargaṇa, run forward through the
text's revolutions and civil days, gives back the printed longitude,
residue or revolutions. Every one is ``editor_computed``: the printed
longitude is the problem's, stated to its last printed place, so the
exact longitude is compared after rounding to that place (the
editor's stated precision); residues and revolutions are integers and
exact. The abraded divisors (the yuga numbers divided by their highest
common factor) are recomputed from the text's data.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction
from math import gcd

import pytest
from authority_kit import printed, records, text_value

from jyotirganita.core.calendar import Weekday
from jyotirganita.core.exact import Rounding, round_to
from jyotirganita.siddhantic.ahargana import DAYS_PER_WEEK
from jyotirganita.siddhantic.mean import mean_longitude

Record = Callable[..., None]
FX = "authority/aryabhatiya/"
EXACT = "integers in the text's units: exact"
CIRCLE = 360


def rev(element: str) -> int:
    return int(text_value("aryabhatiya", f"{element}.revolutions"))


def signs_per_circle() -> int:
    """Signs in a circle: as the year into months (``time_units.circle_division``,
    aryabhatiya_1976)."""
    return int(text_value("aryabhatiya", "time_units.months_per_year"))


def civil() -> int:
    return int(text_value("aryabhatiya", "earth.rotations")) - rev("sun")


def places(fixture: str, name: str) -> int:
    """The number of sexagesimal places printed after the degrees of an rdms value."""
    v = next(r for r in records().fixtures[fixture].values if r.key.endswith("#" + name))
    return len(v.raw["value"]) - 2


def at_printed_place(longitude: Fraction, fixture: str, name: str) -> Fraction:
    """``longitude`` (degrees) rounded to the last place the fixture prints."""
    return round_to(longitude, Fraction(1, 60 ** places(fixture, name)), Rounding.HALF_UP)


def exact_longitude(element: str, ahargana: Fraction) -> Fraction:
    """The exact mean longitude in degrees at ``ahargana`` days (a fraction of a day allowed)."""
    return Fraction(rev(element) * ahargana * CIRCLE, civil()) % CIRCLE


# --- the printed answer gives back the printed longitude ---------------------------

# (fixture, ahargana value, [(sign, element)], longitude value, day fraction value or None)
FORWARD = [
    (
        "mahabhaskariya_1960_ch8_13_sun",
        "output.ahargana",
        [(1, "sun")],
        "output.sun_longitude",
        None,
    ),
    (
        "mahabhaskariya_1960_ch8_14_moon",
        "output.ahargana",
        [(1, "moon")],
        "output.moon_longitude",
        None,
    ),
    (
        "mahabhaskariya_1960_ch8_15_mars",
        "output.ahargana",
        [(1, "mars")],
        "output.mars_longitude",
        None,
    ),
    (
        "mahabhaskariya_1960_ch8_16_mercury",
        "output.ahargana",
        [(1, "mercury_sighrocca")],
        "input.mercury_longitude",
        None,
    ),
    (
        "mahabhaskariya_1960_ch8_17_jupiter",
        "output.ahargana",
        [(1, "jupiter")],
        "output.jupiter_longitude",
        None,
    ),
    (
        "mahabhaskariya_1960_ch8_18_venus_saturn",
        "venus.output.ahargana",
        [(1, "venus_sighrocca")],
        "venus.output.longitude",
        None,
    ),
    (
        "mahabhaskariya_1960_ch8_18_venus_saturn",
        "saturn.output.ahargana",
        [(1, "saturn")],
        "saturn.output.longitude",
        None,
    ),
    (
        "mahabhaskariya_1960_ch8_19_mars_moon_sum",
        "output.ahargana",
        [(1, "mars"), (1, "moon")],
        "input.sum_longitude",
        None,
    ),
    (
        "mahabhaskariya_1960_ch1_mars_moon_sum_govinda",
        "output.ahargana",
        [(1, "mars"), (1, "moon")],
        "input.sum_longitude",
        None,
    ),
    (
        "mahabhaskariya_1960_ch8_23_sun_nadis",
        "output.ahargana",
        [(1, "sun")],
        "output.sun_longitude",
        "nadis",
    ),
    (
        "mahabhaskariya_1960_ch1_sun_observed",
        "output.ahargana",
        [(1, "sun")],
        "input.sun_longitude",
        None,
    ),
    *[
        (
            "mahabhaskariya_1960_ch1_sun_sunrise_weekday",
            a,
            [(1, "sun")],
            "input.sun_longitude",
            None,
        )
        for a in (
            "output.ahargana_wednesday",
            "output.ahargana_thursday",
            "output.ahargana_friday",
            "output.ahargana_wednesday_again",
        )
    ],
    *[
        (
            "mahabhaskariya_1960_ch8_21_22_sun_moon_weekdays",
            a,
            [(1, body)],
            f"input.{body}_longitude",
            None,
        )
        for a in (
            "output.ahargana_sunday",
            "output.ahargana_thursday",
            "output.ahargana_friday",
            "output.ahargana_saturday",
        )
        for body in ("sun", "moon")
    ],
]


@pytest.mark.parametrize(
    ("fixture", "ahargana", "terms", "longitude", "fraction"),
    FORWARD,
    ids=[f"{f[0]}:{f[1]}:{'+'.join(e for _, e in f[2])}" for f in FORWARD],
)
def test_the_answer_gives_back_the_longitude(
    fixture: str,
    ahargana: str,
    terms: list[tuple[int, str]],
    longitude: str,
    fraction: str | None,
    record_comparison: Record,
) -> None:
    fid = FX + fixture
    fx = printed(fid)
    days = Fraction(fx[ahargana])
    if fraction == "nadis":
        # the answer is the ahargaṇa and the nāḍīs elapsed after it (60 to a day)
        days += Fraction(
            fx["output.nadis"], int(text_value("aryabhatiya", "time_units.nadis_per_day"))
        )
    exact = sum((sign * exact_longitude(element, days) for sign, element in terms), Fraction(0))
    computed = at_printed_place(exact % CIRCLE, fid, longitude)
    record_comparison(
        fixture=fid,
        value=longitude,
        computed=computed,
        tolerance=0,
        tolerance_reason="the exact longitude rounded to the last place printed (editor_computed)",
    )
    assert computed == fx[longitude]


def test_mahabhaskariya_1960_ch8_20_difference_in_whole_signs(record_comparison: Record) -> None:
    fid = FX + "mahabhaskariya_1960_ch8_20_mars_jupiter_difference"
    fx = printed(fid)
    days = Fraction(fx["output.ahargana"])
    diff = (exact_longitude("mars", days) - exact_longitude("jupiter", days)) % CIRCLE
    sign = Fraction(signs_per_circle(), 1)
    computed = round_to(diff / (CIRCLE / sign), Fraction(1), Rounding.HALF_UP)
    record_comparison(
        fixture=fid,
        value="input.difference_signs",
        computed=computed,
        tolerance=0,
        tolerance_reason="the exact difference in signs, rounded to the whole sign printed",
    )
    assert computed == fx["input.difference_signs"]


@pytest.mark.parametrize(
    ("fixture", "ahargana", "part"),
    [
        ("mahabhaskariya_1960_ch1_eighth_sign", "bhaskara.ahargana", "bhaskara.part_to_traverse"),
        ("mahabhaskariya_1960_ch1_eighth_sign", "govinda.ahargana", "govinda.part_to_traverse"),
    ],
)
def test_mahabhaskariya_1960_ch1_part_to_traverse(
    fixture: str, ahargana: str, part: str, record_comparison: Record
) -> None:
    """The Sun's arc still to traverse in its revolution at the answer's sunrise."""
    fid = FX + fixture
    fx = printed(fid)
    to_go = CIRCLE - exact_longitude("sun", Fraction(fx[ahargana]))
    if part == "bhaskara.part_to_traverse":
        # printed as signs and minutes in two values: compare the minutes beyond the signs
        sign = CIRCLE // signs_per_circle()
        minutes = round_to(
            (to_go - fx["bhaskara.part_to_traverse.signs"] * sign) * 60,
            Fraction(1),
            Rounding.HALF_UP,
        )
        record_comparison(
            fixture=fid,
            value="bhaskara.part_to_traverse.minutes",
            computed=minutes,
            tolerance=0,
            tolerance_reason="the exact arc rounded to the whole minute printed",
        )
        assert minutes == fx["bhaskara.part_to_traverse.minutes"]
        return
    computed = at_printed_place(to_go, fid, part)
    record_comparison(
        fixture=fid,
        value=part,
        computed=computed,
        tolerance=0,
        tolerance_reason="the exact arc rounded to the last place printed",
    )
    assert computed == fx[part]


# --- revolutions and residues are integers: exact ------------------------------------

REVOLUTIONS = [
    ("mahabhaskariya_1960_ch8_15_mars", "output.ahargana", "mars", "output.revolutions"),
    (
        "mahabhaskariya_1960_ch8_16_mercury",
        "output.ahargana",
        "mercury_sighrocca",
        "output.revolutions",
    ),
    ("mahabhaskariya_1960_ch8_17_jupiter", "output.ahargana", "jupiter", "output.revolutions"),
    ("mahabhaskariya_1960_ch1_sun_observed", "output.ahargana", "sun", "output.revolutions"),
    ("mahabhaskariya_1960_ch1_eighth_sign", "bhaskara.ahargana", "sun", "bhaskara.years"),
    ("mahabhaskariya_1960_ch1_eighth_sign", "govinda.ahargana", "sun", "govinda.years"),
    ("mahabhaskariya_1960_ch1_saturn_residue", "output.ahargana", "saturn", "output.revolutions"),
    ("laghubhaskariya_1963_app_ex3_saturn", "output.ahargana", "saturn", "output.revolutions"),
]


@pytest.mark.parametrize(("fixture", "ahargana", "element", "value"), REVOLUTIONS)
def test_the_answer_gives_back_the_revolutions(
    fixture: str, ahargana: str, element: str, value: str, record_comparison: Record
) -> None:
    fid = FX + fixture
    fx = printed(fid)
    computed = mean_longitude(rev(element), civil(), fx[ahargana]).revolutions
    record_comparison(
        fixture=fid, value=value, computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == fx[value]


# (fixture, multiplier name, divisor name, ahargana name, residue name)
RESIDUES = [
    (
        "mahabhaskariya_1960_ch1_sun_observed",
        "input.abraded_sun_revolutions",
        "input.abraded_civil_days",
        "output.ahargana",
        "output.residue",
    ),
    (
        "mahabhaskariya_1960_ch1_sun_sunrise_weekday",
        "output.abraded_sun_revolutions",
        "output.abraded_civil_days",
        "output.ahargana_wednesday",
        "output.residue",
    ),
    (
        "mahabhaskariya_1960_ch1_saturn_residue",
        "output.abraded_dividend",
        "output.abraded_divisor",
        "output.ahargana",
        "input.residue",
    ),
    (
        "laghubhaskariya_1963_app_ex3_saturn",
        "input.abraded_revolutions",
        "input.abraded_civil_days",
        "output.ahargana",
        "input.residue",
    ),
    (
        "mahabhaskariya_1960_ch8_24_sun_mars_residues",
        "output.abraded_sun_revolutions",
        "output.abraded_sun_civil_days",
        "output.ahargana",
        "input.sun_remainder",
    ),
    (
        "mahabhaskariya_1960_ch8_24_sun_mars_residues",
        "output.abraded_mars_revolutions",
        "output.abraded_mars_civil_days",
        "output.ahargana",
        "input.mars_remainder",
    ),
]


@pytest.mark.parametrize(("fixture", "mult", "div", "ahargana", "residue"), RESIDUES)
def test_the_answer_leaves_the_residue(
    fixture: str, mult: str, div: str, ahargana: str, residue: str, record_comparison: Record
) -> None:
    fid = FX + fixture
    fx = printed(fid)
    computed = fx[mult] * fx[ahargana] % fx[div]
    record_comparison(
        fixture=fid, value=residue, computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == fx[residue]


def test_laghubhaskariya_1963_app_ex5_residue_of_the_sign(record_comparison: Record) -> None:
    """The residue of the sign: the part of a sign beyond whole signs, in abraded days."""
    fid = FX + "laghubhaskariya_1963_app_ex5_sun_sign_residue"
    fx = printed(fid)
    g = gcd(rev("sun"), civil())
    signs = signs_per_circle()
    computed = rev("sun") // g * signs * fx["output.ahargana"] % (civil() // g)
    record_comparison(
        fixture=fid,
        value="input.residue_of_sign",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == fx["input.residue_of_sign"]


# --- the abraded numbers: the yuga numbers over their highest common factor -------------

ABRADED = [
    (
        "mahabhaskariya_1960_ch8_13_sun",
        "input.abraded_sun_revolutions",
        "input.abraded_civil_days",
        ["sun"],
        1,
    ),
    (
        "mahabhaskariya_1960_ch8_14_moon",
        "input.abraded_moon_revolution_minutes",
        "input.abraded_civil_days",
        ["moon"],
        21600,
    ),
    (
        "mahabhaskariya_1960_ch8_15_mars",
        "input.abraded_mars_revolution_degrees",
        "input.abraded_civil_days",
        ["mars"],
        360,
    ),
    (
        "mahabhaskariya_1960_ch8_16_mercury",
        "input.abraded_mercury_revolutions",
        "input.abraded_civil_days",
        ["mercury_sighrocca"],
        1,
    ),
    (
        "mahabhaskariya_1960_ch8_17_jupiter",
        "input.abraded_jupiter_revolution_minutes",
        "input.abraded_civil_days",
        ["jupiter"],
        21600,
    ),
    (
        "mahabhaskariya_1960_ch8_18_venus_saturn",
        "venus.input.abraded_revolution_minutes",
        "venus.input.abraded_civil_days",
        ["venus_sighrocca"],
        21600,
    ),
    (
        "mahabhaskariya_1960_ch8_18_venus_saturn",
        "saturn.input.abraded_revolution_minutes",
        "saturn.input.abraded_civil_days",
        ["saturn"],
        21600,
    ),
    (
        "mahabhaskariya_1960_ch8_19_mars_moon_sum",
        "input.abraded_revolution_sum",
        "input.abraded_civil_days",
        ["mars", "moon"],
        1,
    ),
    (
        "mahabhaskariya_1960_ch1_mars_moon_sum_govinda",
        "output.abraded_sum",
        "output.abraded_civil_days",
        ["mars", "moon"],
        1,
    ),
    (
        "mahabhaskariya_1960_ch8_20_mars_jupiter_difference",
        "output.abraded_difference",
        "output.abraded_civil_days",
        ["mars", "-jupiter"],
        1,
    ),
    (
        "mahabhaskariya_1960_ch1_saturn_residue",
        "output.abraded_dividend",
        "output.abraded_divisor",
        ["saturn"],
        1,
    ),
    (
        "laghubhaskariya_1963_app_ex3_saturn",
        "input.abraded_revolutions",
        "input.abraded_civil_days",
        ["saturn"],
        1,
    ),
    (
        "mahabhaskariya_1960_ch8_21_22_sun_moon_weekdays",
        "output.abraded_moon_revolutions",
        "output.abraded_moon_civil_days",
        ["moon"],
        1,
    ),
    (
        "mahabhaskariya_1960_ch8_24_sun_mars_residues",
        "output.abraded_mars_revolutions",
        "output.abraded_mars_civil_days",
        ["mars"],
        1,
    ),
    *[
        (
            f,
            "output.abraded_sun_revolutions"
            if f != "mahabhaskariya_1960_ch1_sun_observed"
            else "input.abraded_sun_revolutions",
            "output.abraded_civil_days"
            if f != "mahabhaskariya_1960_ch1_sun_observed"
            else "input.abraded_civil_days",
            ["sun"],
            1,
        )
        for f in (
            "mahabhaskariya_1960_ch1_sun_midnight",
            "mahabhaskariya_1960_ch1_sun_sunrise_weekday",
            "mahabhaskariya_1960_ch1_sun_observed",
            "mahabhaskariya_1960_ch8_23_sun_nadis",
        )
    ],
]


@pytest.mark.parametrize(("fixture", "num", "den", "elements", "unit"), ABRADED)
@pytest.mark.parametrize("part", ["num", "den"])
def test_abraded_numbers(
    fixture: str,
    num: str,
    den: str,
    elements: list[str],
    unit: int,
    part: str,
    record_comparison: Record,
) -> None:
    """``revolutions × unit ÷ civil days`` in lowest terms (unit: 1, 360° or 21600′)."""
    fid = FX + fixture
    fx = printed(fid)
    total = sum(-rev(e[1:]) if e.startswith("-") else rev(e) for e in elements)
    ratio = Fraction(total * unit, civil())
    computed = ratio.numerator if part == "num" else ratio.denominator
    name = num if part == "num" else den
    record_comparison(
        fixture=fid, value=name, computed=computed, tolerance=0, tolerance_reason=EXACT
    )
    assert computed == fx[name]


# --- mahabhaskariya_1960's weekday answers: their differences --------------------------


@pytest.mark.parametrize(
    ("fixture", "first", "later"),
    [
        (
            "mahabhaskariya_1960_ch1_sun_sunrise_weekday",
            "output.ahargana_wednesday",
            "output.ahargana_thursday",
        ),
        (
            "mahabhaskariya_1960_ch1_sun_sunrise_weekday",
            "output.ahargana_wednesday",
            "output.ahargana_friday",
        ),
        (
            "mahabhaskariya_1960_ch1_sun_sunrise_weekday",
            "output.ahargana_wednesday",
            "output.ahargana_wednesday_again",
        ),
        (
            "mahabhaskariya_1960_ch8_21_22_sun_moon_weekdays",
            "output.ahargana_thursday",
            "output.ahargana_friday",
        ),
        (
            "mahabhaskariya_1960_ch8_21_22_sun_moon_weekdays",
            "output.ahargana_thursday",
            "output.ahargana_saturday",
        ),
        (
            "mahabhaskariya_1960_ch8_21_22_sun_moon_weekdays",
            "output.ahargana_thursday",
            "output.ahargana_sunday",
        ),
    ],
)
def test_mahabhaskariya_1960_weekday_answers_differ_by_their_names(
    fixture: str, first: str, later: str, record_comparison: Record
) -> None:
    """The answers named for successive weekdays differ by as many days, modulo 7.

    Their absolute weekday is not tested: under laghubhaskariya_1963 I.8 (remainder counted
    from Friday) remainder 0 is a Friday, while mahabhaskariya_1960's answers name the
    remainder-0 day Thursday. The difference, which both
    readings share, is what the answers witness.
    """
    fid = FX + fixture
    fx = printed(fid)
    computed = (fx[later] - fx[first]) % DAYS_PER_WEEK
    # the weekdays the printed answers are named for (the value names say which)
    named = [Weekday[n.split("ahargana_")[1].split("_")[0].upper()] for n in (first, later)]
    expected_days = (named[1].value - named[0].value) % DAYS_PER_WEEK
    record_comparison(
        fixture=fid,
        value=later,
        computed=computed,
        tolerance=0,
        tolerance_reason="whole days modulo 7: exact (the names' order, not their anchor)",
    )
    assert computed == expected_days


# --- a longitude as a residue: the part of a revolution in abraded days ------------------

# the whole residue the editor takes: below the exact quotient (floor) or above it (ceiling)
FLOOR, CEILING = Rounding.FLOOR, Rounding.CEIL
CONVERSIONS = [
    (
        "laghubhaskariya_1963_app_sun_residue_conversion",
        "input.residue",
        "input.divisor",
        "output.residue_of_revolution",
        FLOOR,
    ),
    (
        "mahabhaskariya_1960_ch1_sun_observed",
        "input.sun_longitude",
        "input.abraded_civil_days",
        "output.residue",
        FLOOR,
    ),
    (
        "mahabhaskariya_1960_ch1_sun_midnight",
        "input.sun_longitude",
        "output.abraded_civil_days",
        "output.residue",
        FLOOR,
    ),
    (
        "mahabhaskariya_1960_ch1_sun_sunrise_weekday",
        "input.sun_longitude",
        "output.abraded_civil_days",
        "output.residue",
        CEILING,
    ),
]


@pytest.mark.parametrize(("fixture", "longitude", "divisor", "residue", "taken"), CONVERSIONS)
def test_longitude_to_residue(
    fixture: str,
    longitude: str,
    divisor: str,
    residue: str,
    taken: Rounding,
    record_comparison: Record,
) -> None:
    """The residue is longitude ÷ 360° × the abraded civil days, taken whole.

    The printed longitude is generally not a whole residue. Shukla takes
    the whole residue below it in three examples and the one above it in
    ``mahabhaskariya_1960_ch1_sun_sunrise_weekday`` (the residue the answer leaves, tested
    with :func:`test_the_answer_leaves_the_residue`); each fixture records
    which, so the editor's choice is on the record and the comparison is exact under it; the
    remainder
    dropped is why an answer's longitude can differ from the problem's in
    its last place (``mahabhaskariya_1960_ch1_sun_midnight``: 39.1″ against 40″ printed).
    """
    fid = FX + fixture
    fx = printed(fid)
    computed = round_to(fx[longitude] / CIRCLE * fx[divisor], Fraction(1), taken)
    record_comparison(
        fixture=fid,
        value=residue,
        computed=computed,
        tolerance=0,
        tolerance_reason=(
            f"the exact quotient taken whole by {taken.name.lower()}, the editor's choice in this "
            "example (editor_computed)"
        ),
    )
    assert computed == fx[residue]


def test_mahabhaskariya_1960_ch1_sun_midnight_answer_leaves_the_residue(
    record_comparison: Record,
) -> None:
    """At midnight, a quarter day before sunrise: the answer in quarter days leaves the residue."""
    fid = FX + "mahabhaskariya_1960_ch1_sun_midnight"
    fx = printed(fid)
    quarters = fx["output.day_fraction"].denominator
    computed = (
        fx["output.abraded_sun_revolutions"]
        * fx["output.x_reduced"]
        % (quarters * fx["output.abraded_civil_days"])
        // quarters
    )
    record_comparison(
        fixture=fid,
        value="output.residue",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == fx["output.residue"]
