"""Pinning tests of the Kerala month rule and the ending encodings.

Every expected value is a printed value of a fixture under
``tests/authority/calendar/`` (all three ``editor_computed``: the editors'
statement of practice and their arithmetic, compared at their print
quantum, the minute); every parameter is the profile's datum. One test per encoding option from a
printed example.

- sewell_dikshit_1896 Art. 28 (``sewell_dikshit_1896_art28_month_rule``): the aparāhna month rule,
  its
  fifth part and three parts of the daytime, and the day the month begins
  for both of the editors' saṅkrānti times; the registered rule
  ``aparahna_parts`` run with the profile's ``parts`` and ``within``.
- sewell_dikshit_1896 Art. 31 (``sewell_dikshit_1896_art31_ending_two_encodings``): one ending in
  ghaṭikās and palas after sunrise, re-encoded in hours after sunrise and
  as a clock time under sewell_dikshit_1896's mean sunrise
  (``time_standards.lmt.definition.sewell_dikshit_1896``):
  the fixed-unit nāḍikā elapsed after sunrise.
- rashtriya_panchanga_1959 1 Caitra 1881 (``rashtriya_panchanga_1959_1_chaitra_1881``): the IST
  columns, hours and
  minutes after the civil day's midnight, carried past 24 for an ending
  after midnight: each printed ending re-encoded from its time after the
  printed sunrise with the midnight reference.

travancore_panchangam_1921's column statement
(``regions.kerala.conventions.encoding.column_sense.travancore_panchangam_1921``)
is the profile's cited sense of its endings; it prints no worked example, and its pin is the
conformance check that the
profile's ending encoding names it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from fractions import Fraction

from authority_kit import REPO, printed, records

from jyotirganita.calendar.encodings import clock, encode_ending, sexagesimal
from jyotirganita.calendar.months import MONTH_RULES, Sankranti
from jyotirganita.core.calendar import Weekday, weekday
from jyotirganita.core.types import JDN, Nadika
from jyotirganita.data.datum import context_for
from jyotirganita.data.eras import load_eras
from jyotirganita.regions.base import load_profile

Record = Callable[..., None]
MINUTE = "the editors print hours and minutes ('about'): compared at the minute, rounded"
EXACT = "a day and a weekday: exact"

NADIKAS_PER_DAY = 60
HOURS_PER_DAY = 24
MINUTES_PER_HOUR = 60

ART28 = "authority/calendar/sewell_dikshit_1896_art28_month_rule"
ART31 = "authority/calendar/sewell_dikshit_1896_art31_ending_two_encodings"
rashtriya_panchanga_1959 = "authority/calendar/rashtriya_panchanga_1959_1_chaitra_1881"


# --- parsing the printed forms (text values keyed as printed) ------------------------------


def _hours(text: str) -> Fraction:
    """'12 hours and 30 minutes', '2 hours 30 minutes', '8 hours after sunrise' as hours."""
    m = re.fullmatch(r"(\d+) hours?(?: and| after sunrise)?(?: (\d+) minutes)?", text)
    assert m is not None, text
    return Fraction(int(m[1])) + Fraction(int(m[2] or 0), MINUTES_PER_HOUR)


def _nadika_of_hours(h: Fraction) -> Nadika:
    return Nadika(h * NADIKAS_PER_DAY / HOURS_PER_DAY)


def _hours_of_nadika(n: Nadika) -> Fraction:
    return n.value * HOURS_PER_DAY / NADIKAS_PER_DAY


def _hm(h: Fraction) -> str:
    whole, minutes = sexagesimal(h)
    return f"{whole} hours {round(minutes)} minutes"


def _weekday(name: str) -> Weekday:
    return Weekday[name.upper()]


# --- sewell_dikshit_1896 Art. 28
# ----------------------------------------------------------------------------


def _profile_parameters() -> dict[str, Fraction]:
    ctx = context_for(REPO)
    eras = load_eras(REPO / "jyotirganita" / "data", ctx, REPO)
    return dict(load_profile(REPO, "kerala", records().data, eras).month_rule.parameters)


class _Stream:
    """A month stream whose saṅkrānti is the editors' (the rule reads nothing else)."""

    def __init__(self, s: Sankranti) -> None:
        self.s = s

    def sankranti(self, rasi: int, near: JDN) -> Sankranti:
        return self.s


def _a_day_named(name: str) -> JDN:
    day = JDN(0)
    while weekday(day) is not _weekday(name):
        day = day.plus_days(1)
    return day


def _month_begins(after_sunrise: Fraction) -> str:
    fx = printed(ART28)
    day = _a_day_named(fx["input.sankranti_weekday"])
    daytime = _nadika_of_hours(_hours(fx["input.day_length"]))
    s = Sankranti(1, day, _nadika_of_hours(after_sunrise), Nadika(0), daytime, Nadika(60))
    rule = MONTH_RULES["aparahna_parts"]
    first = rule.fn(_Stream(s), 1, day, _profile_parameters())  # type: ignore[arg-type]
    return weekday(first).name.title()


def test_sewell_dikshit_1896_art28_fifth_part(record_comparison: Record) -> None:
    fx = printed(ART28)
    computed = _hm(_hours(fx["input.day_length"]) / _profile_parameters()["parts"])
    record_comparison(
        fixture=ART28,
        value="output.fifth_part",
        computed=computed,
        tolerance=0,
        tolerance_reason=MINUTE,
    )
    assert computed == fx["output.fifth_part"]


def test_sewell_dikshit_1896_art28_three_parts(record_comparison: Record) -> None:
    fx = printed(ART28)
    p = _profile_parameters()
    computed = _hm(_hours(fx["input.day_length"]) * p["within"] / p["parts"])
    record_comparison(
        fixture=ART28,
        value="output.three_parts",
        computed=computed,
        tolerance=0,
        tolerance_reason=MINUTE,
    )
    assert computed == fx["output.three_parts"]


def test_sewell_dikshit_1896_art28_month_begins_the_same_day(record_comparison: Record) -> None:
    fx = printed(ART28)
    computed = _month_begins(Fraction(fx["input.sankranti_hours_after_sunrise"]))
    record_comparison(
        fixture=ART28,
        value="output.month_begins",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == fx["output.month_begins"]


def test_sewell_dikshit_1896_art28_month_begins_the_next_day(record_comparison: Record) -> None:
    fx = printed(ART28)
    computed = _month_begins(_hours(fx["input.alternative_after_sunrise"]))
    record_comparison(
        fixture=ART28,
        value="output.alternative_month_begins",
        computed=computed,
        tolerance=0,
        tolerance_reason=EXACT,
    )
    assert computed == fx["output.alternative_month_begins"]


# --- sewell_dikshit_1896 Art. 31
# ----------------------------------------------------------------------------


def _ending_nadika() -> Nadika:
    m = re.fullmatch(r"(\d+) gh\. (\d+) p\.", printed(ART31)["input.ending_ghatika"])
    assert m is not None
    return Nadika(Fraction(int(m[1])) + Fraction(int(m[2]), NADIKAS_PER_DAY))


def test_sewell_dikshit_1896_art31_ending_in_hours_after_sunrise(record_comparison: Record) -> None:
    hours = encode_ending(
        _ending_nadika(),
        unit="hours",
        direction="elapsed",
        reference="sunrise",
        day_length=Nadika(NADIKAS_PER_DAY),
    )
    whole, minutes = sexagesimal(hours)
    computed = f"about {whole} h. {round(minutes)} m."
    record_comparison(
        fixture=ART31,
        value="output.ending_hours",
        computed=computed,
        tolerance=0,
        tolerance_reason=MINUTE,
    )
    assert computed == printed(ART31)["output.ending_hours"]


def test_sewell_dikshit_1896_art31_ending_as_a_clock_time(record_comparison: Record) -> None:
    statement = records().data["time_standards.lmt.definition.sewell_dikshit_1896"].value
    m = re.search(r"roughly (\d+) a\.m\.", str(statement))
    assert m is not None
    sunrise_hours = Fraction(int(m[1]))
    hours = sunrise_hours + encode_ending(
        _ending_nadika(),
        unit="hours",
        direction="elapsed",
        reference="sunrise",
        day_length=Nadika(NADIKAS_PER_DAY),
    )
    hour, minutes, half = clock(hours)
    computed = f"about {hour}.{round(minutes)} {half.rstrip('.')}"
    record_comparison(
        fixture=ART31,
        value="output.ending_clock",
        computed=computed,
        tolerance=0,
        tolerance_reason=MINUTE,
    )
    assert computed == printed(ART31)["output.ending_clock"]


# --- rashtriya_panchanga_1959, 1 Caitra 1881
# --------------------------------------------------------------------

MINUS = "−"


def _ist_hours(text: str) -> Fraction:
    h, _, m = text.partition(MINUS)
    return Fraction(int(h)) + Fraction(int(m), MINUTES_PER_HOUR)


def _rashtriya_panchanga_1959_reencoded(name: str) -> str:
    """rashtriya_panchanga_1959's printed ending, taken to nāḍikās after its printed sunrise and
    encoded back.

    A round trip of the encoding, not a computation of the ending: it pins
    the midnight reference (hours elapsed from the civil day's midnight) and,
    for an ending after midnight, the carry past 24 h.
    """
    fx = printed(rashtriya_panchanga_1959)
    sunrise = _nadika_of_hours(_ist_hours(fx["output.sunrise"]))
    after_sunrise = _nadika_of_hours(_ist_hours(fx[name])) - sunrise
    hours = encode_ending(
        after_sunrise,
        unit="hours",
        direction="elapsed",
        reference="midnight",
        day_length=Nadika(NADIKAS_PER_DAY),
        sunrise_after_midnight=sunrise,
    )
    whole, minutes = sexagesimal(hours)
    return f"{whole}{MINUS}{round(minutes):02d}"


def test_rashtriya_panchanga_1959_tithi_end_in_ist_hours_after_midnight(
    record_comparison: Record,
) -> None:
    """A round trip of the encoding (``_rashtriya_panchanga_1959_reencoded``): pins the midnight
    reference."""
    computed = _rashtriya_panchanga_1959_reencoded("output.tithi_end")
    record_comparison(
        fixture=rashtriya_panchanga_1959,
        value="output.tithi_end",
        computed=computed,
        tolerance=0,
        tolerance_reason=MINUTE,
    )
    assert computed == printed(rashtriya_panchanga_1959)["output.tithi_end"]


def test_rashtriya_panchanga_1959_an_ending_after_midnight_is_carried_past_24(
    record_comparison: Record,
) -> None:
    """A round trip of the encoding (``_rashtriya_panchanga_1959_reencoded``): pins the carry past
    24 h."""
    fx = printed(rashtriya_panchanga_1959)
    computed = _rashtriya_panchanga_1959_reencoded("output.nakshatra_end_2")
    record_comparison(
        fixture=rashtriya_panchanga_1959,
        value="output.nakshatra_end_2",
        computed=computed,
        tolerance=0,
        tolerance_reason=MINUTE,
    )
    assert computed == fx["output.nakshatra_end_2"]
    # the second ending falls after midnight and before the next sunrise of the same civil day
    assert HOURS_PER_DAY < _ist_hours(computed) < HOURS_PER_DAY + _ist_hours(fx["output.sunrise"])
