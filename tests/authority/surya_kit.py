"""Shared helpers of the Sūrya-siddhānta's authority tests.

The model and the run are built once per registry entry (``suryasiddhanta``, and for the fixtures
that name it ``suryasiddhanta_paramesvara_recension``; :data:`METHODS`) at the text's own place
(``meridians:
suryasiddhanta_lanka``, Laṅkā's midnight). Angles from the fixtures arrive
parsed in degrees (``rdms``) or in the printed leading unit
(``sexagesimal``); table cells arrive as tuples of the printed parts and
are read here by the column's stated parts.
"""

from __future__ import annotations

from fractions import Fraction
from functools import cache
from typing import Any

from authority_kit import REPO, text_value

from jyotirganita.core.exact import Rounding, round_to
from jyotirganita.core.types import JDN
from jyotirganita.methods.compose import MethodRun, ResolvedMethod, build, load_method
from jyotirganita.regions.places import load_place
from jyotirganita.siddhantic.ahargana import LunarReckoning
from jyotirganita.siddhantic.surya import SuryaDay, SuryaModel

TEXT = "suryasiddhanta"
#: the methods a fixture naming both runs under
METHODS = (TEXT, "suryasiddhanta_paramesvara_recension")
FX = "authority/suryasiddhanta/"
SIGN = 30
CIRCLE = 360
MINUTES = 60
EXACT = "integers in the text's units: exact"


@cache
def resolved(method: str = TEXT) -> ResolvedMethod:
    return load_method(method, REPO)


def model(method: str = TEXT) -> SuryaModel:
    m = resolved(method).model
    assert isinstance(m, SuryaModel)
    return m


@cache
def run(method: str = TEXT) -> MethodRun:
    r = resolved(method)
    return build(r, load_place(REPO, "meridians", "suryasiddhanta_lanka", r.records.data))


def day(jdn: JDN, method: str = TEXT) -> SuryaDay:
    """The engine's day at the text's place."""
    d = run(method).engine.day(jdn)
    assert isinstance(d, SuryaDay)
    return d


def value(suffix: str) -> Any:
    """A datum of the text, parsed by its form."""
    return text_value(TEXT, suffix)


def integer(suffix: str) -> int:
    return int(value(suffix))


def reckoning() -> LunarReckoning:
    """The lunar-date rule's constants (i.48–51), the years counted from creation."""
    return LunarReckoning(
        0,
        integer("time.year.months"),
        integer("yuga.intercalary_months"),
        integer("yuga.solar_months"),
        integer("time.month.days"),
        integer("yuga.omitted_days"),
        integer("yuga.lunar_days"),
    )


def angle(parts: tuple[Any, ...], heads: str = "s") -> Fraction:
    """Degrees from a table cell: ``[s, deg, min(, sec)]``, or ``[deg, min]`` (``heads="d"``)."""
    p = [Fraction(x) for x in parts]
    if heads == "s":
        p = [p[0] * SIGN + p[1], *p[2:]]
    return sum((x / MINUTES**i for i, x in enumerate(p)), Fraction(0))


def half_up(x: Fraction, quantum: Fraction | int = 1) -> Fraction:
    """Whitney's rounding (suryasiddhanta_burgess_1860 p. 210): a fraction above a half counts as
    one."""
    return Fraction(round_to(x, quantum, Rounding.HALF_UP))


def to_place(degrees: Fraction, places: int) -> Fraction:
    """``degrees`` rounded half up at the ``places``-th sexagesimal place (1: minutes)."""
    return half_up(degrees, Fraction(1, MINUTES**places))
