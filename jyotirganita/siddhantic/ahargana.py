"""The ahargaṇa: the text's day count and its passage to and from a JDN.

Two procedures, each a registry entry of :mod:`jyotirganita.siddhantic.procedures`:

- ``ahargana.lunar_reckoning`` (:func:`lunar_reckoning`): the text's own
  rule from a lunar date, laghubhaskariya_1963 I.4–8
  (``texts.aryabhatiya.procedures.ahargana.rule``;
  mahabhaskariya_1960 I.4–6 the second witness). Add the Śaka-to-Kali offset to the
  elapsed Śaka years, multiply by the months of a year, add the lunar
  months elapsed since Caitra; the complete intercalary months are the
  product with the intercalary months of a yuga divided by its solar
  months; the tithis are the lunar months times the days of a month plus
  the tithis elapsed; the complete omitted days are the product with the
  omitted days of a yuga divided by its lunar days; the ahargaṇa is the
  tithis less the omitted days. "Complete" is the integer quotient (the
  rule's own word, ``...ahargana.complete_intercalary_months``,
  ``...ahargana.complete_omitted_days``).
- ``ahargana.civil_days_since_kali_epoch`` (:func:`ahargana_of_day`,
  :func:`day_of_ahargana`): the time base. The ahargaṇa is "the number of
  mean civil days elapsed at mean sunrise at Laṅkā ... since the beginning
  of Kaliyuga" (``texts.aryabhatiya.procedures.ahargana.count_note``), so
  the civil day ``d`` has ahargaṇa ``d − e`` at its sunrise, ``e`` being
  the JDN of the Kali epoch's civil day in the era record
  (``jyotirganita/data/eras/kali.yaml``), whose day begins at mean
  sunrise at the Ujjain meridian (``eras.kali.epoch.day_start.vakyakarana_1962``). The
  epoch day's sunrise is the count's zero, so the first civil day on which
  the count exists, ``runs_from``, is ``e``.

The weekday rule (``weekday.remainder_from_friday``, laghubhaskariya_1963 I.8): the remainder
of the ahargaṇa divided by seven counts the days from Friday.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from jyotirganita.core.calendar import Weekday
from jyotirganita.core.types import JDN, Ahargana

__all__ = [
    "LunarReckoning",
    "LunarSteps",
    "ahargana_of_day",
    "day_of_ahargana",
    "lunar_reckoning",
    "weekday_of_ahargana",
]

DAYS_PER_WEEK = 7


@dataclass(frozen=True, slots=True)
class LunarReckoning:
    """The constants of the lunar-date rule, each a datum of the text."""

    saka_to_kali_years: int
    months_per_year: int
    intercalary_months_per_yuga: int
    solar_months_per_yuga: int
    days_per_month: int
    omitted_days_per_yuga: int
    lunar_days_per_yuga: int


@dataclass(frozen=True, slots=True)
class LunarSteps:
    """Each step of the rule as laghubhaskariya_1963 I.4–8 orders it."""

    kali_years: int
    solar_months: int
    intercalary_months: int
    lunar_months: int
    tithis: int
    omitted_days: int
    ahargana: int


def lunar_reckoning(
    c: LunarReckoning, saka_years_elapsed: int, months_elapsed: int, tithis_elapsed: int
) -> LunarSteps:
    """The ahargaṇa from a lunar date by laghubhaskariya_1963 I.4–8, with every intermediate
    step."""
    kali = saka_years_elapsed + c.saka_to_kali_years
    solar = kali * c.months_per_year + months_elapsed
    intercalary = solar * c.intercalary_months_per_yuga // c.solar_months_per_yuga
    lunar = solar + intercalary
    tithis = lunar * c.days_per_month + tithis_elapsed
    omitted = tithis * c.omitted_days_per_yuga // c.lunar_days_per_yuga
    return LunarSteps(kali, solar, intercalary, lunar, tithis, omitted, tithis - omitted)


def ahargana_of_day(text: str, epoch: JDN, day: JDN) -> Ahargana:
    """The ahargaṇa at the sunrise of civil day ``day``: ``day − epoch`` whole days."""
    return Ahargana(text, day.days_since(epoch), Fraction(0))


def day_of_ahargana(epoch: JDN, ahargana: Ahargana) -> JDN:
    """The civil day whose sunrise the whole ahargaṇa ``ahargana`` counts to."""
    if ahargana.fraction:
        raise ValueError("a civil day is named by a whole ahargaṇa (its sunrise)")
    return epoch.plus_days(ahargana.day)


def weekday_of_ahargana(days: int, first: Weekday) -> Weekday:
    """The weekday ``days mod 7`` days after ``first`` (laghubhaskariya_1963 I.8: ``first`` is
    Friday)."""
    order = list(Weekday)
    return order[(order.index(first) + days) % DAYS_PER_WEEK]
