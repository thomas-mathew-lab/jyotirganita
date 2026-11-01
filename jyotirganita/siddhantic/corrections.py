"""Correction layers and year data.

A **layer** is an entry of the base text's ``corrections.yaml``: a rate per
element for every completed year after the layer's ``epoch``, and the
``defined`` date of the text that states it. Haridatta's śakābda-saṃskāra
(``texts.aryabhatiya.sakabda_samskara.*``, grahacaranibandhana_1954 p. x) is the first:

- procedure ``layer.step_per_completed_year``: the correction is the count
  of completed years times the rate, a step function (grahacaranibandhana_1954 p. x, "for every
  completed year after śaka 444"; ``...sakabda_samskara.step_count``);
- procedure ``layer.count_by_mean_mesha``: the completed years are reckoned
  at the mean Meṣa saṅkrānti of the base text's own mean Sun, a fallback
  (``...step_count.reckoning``, basis ``fallback_no_stated_rule``);
- procedure ``layer.negative_count_floor``: before the epoch the count is
  the floor of the elapsed years, so the year before the epoch counts −1
  (``...negative_count_floor``, basis ``fallback_no_stated_rule``).

The completed Kali years at a day are the whole revolutions of the base
text's mean Sun at that day's sunrise, so the count is ``K − t``, ``t``
being the completed Kali years at which the epoch's year begins
(:meth:`YearDatum.kali_threshold`). For a negative ``K − t`` this is the
floor of the elapsed years, which the fallback asks for.

A **year datum** (a method's ``composed``, a layer's ``epoch`` and
``defined``) is a year in an era, counted elapsed or current, as its
datum's ``unit`` states (``kali_years_elapsed``, ``saka_years_elapsed``,
...). The year meant by an elapsed count *N* begins when *N*
years have elapsed; by a current count *N*, when *N* − 1 have. A day is
before the year when fewer completed years than that have elapsed at its
sunrise. Nothing refuses on a year datum; it drives flags.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction

__all__ = ["Layer", "YearDatum"]

MINUTES_PER_DEGREE = 60


@dataclass(frozen=True, slots=True)
class YearDatum:
    """A year of an era, elapsed or current, with the key of the datum stating it."""

    key: str
    era: str
    year: int
    counting: str
    convention: str

    @classmethod
    def of(cls, key: str, year: int, unit: str, convention: str) -> YearDatum:
        """From a datum's value and unit ``<era>_years_<elapsed|current>``.

        ``ce`` is the Christian era, for an edition that dates a text only so
        (the Sūrya-siddhānta's); its year is placed on the
        Kali count by the arithmetic of the ``before_composition`` flag.
        """
        era, sep, counting = unit.partition("_years_")
        eras = ("kali", "saka", "ce")
        if not sep or counting not in ("elapsed", "current") or era not in eras:
            raise ValueError(
                f"{key}: unit {unit!r} does not name an era and a counting "
                "(<kali|saka|ce>_years_<elapsed|current>); a bare year is a gap"
            )
        return cls(key, era, year, counting, convention)

    def kali_threshold(
        self, saka_to_kali_years: int | None, ce_to_kali_years: int | None = None
    ) -> int:
        """The completed Kali years at which this year begins.

        A Śaka year needs the text's Śaka offset, a CE year the years from CE 1
        to the Kali epoch's year (the era record's); either absent is a hard error.
        """
        elapsed = self.year if self.counting == "elapsed" else self.year - 1
        offset = {"kali": 0, "saka": saka_to_kali_years, "ce": ce_to_kali_years}[self.era]
        if offset is None:
            raise ValueError(f"{self.key}: a {self.era} year needs its offset to the Kali count")
        return elapsed + offset


@dataclass(frozen=True, slots=True)
class Layer:
    """A correction layer: its id, two year data and its signed rates in minutes per year."""

    id: str
    epoch: YearDatum
    defined: YearDatum
    rates: Mapping[str, Fraction]

    def count(self, completed_kali_years: int, saka_to_kali_years: int) -> int:
        """The completed years after the epoch (negative before it, the floor)."""
        return completed_kali_years - self.epoch.kali_threshold(saka_to_kali_years)

    def correction(self, element: str, count: int) -> Fraction:
        """The correction to ``element``'s mean position, in degrees, after ``count`` years."""
        return count * self.rates.get(element, Fraction(0)) / MINUTES_PER_DEGREE

    def zeroed(self) -> Layer:
        """The same layer with every rate zero (the zero-layer identity)."""
        return replace(self, rates={k: Fraction(0) for k in self.rates})
