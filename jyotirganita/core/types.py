"""Distinct types for angles, frames, time scales, durations and dates.

Tropical and sidereal, mean-of-date and
true-of-date, TT, UT1 and local time, Julian and Gregorian dates, ahargaṇa and
JDN are distinct classes, not aliases. Arithmetic is defined only inside a
type (or between a point type and its own duration type); every passage
between types is a named function in this module whose docstring states its
definition. There is no cast.

**Numeric families.** An angle is an :class:`ExactArc` (a ``Fraction`` in a
unit) or a :class:`FloatArc` (an IEEE double in a unit). Each family's
operators accept only its own family and the scalars of its kind: ``int`` and
``Fraction`` for the exact family, ``float`` (and ``int``) for the float
family. ``ExactArc + FloatArc`` and ``ExactArc * 0.5`` are type errors under
mypy and ``TypeError`` at run time (``tests/unit/mypy_cases/`` tests both).

**The protocol.** :class:`Arc` states what both families provide; it is what
the calendar layer codes against. Generic code is parametrised by the
*constrained* type parameter ``[A: (ExactArc, FloatArc)]``, never by the
bound ``[A: Arc]``: with a protocol bound mypy solves ``A`` to the protocol
and accepts a mixed call, with the constraint it must pick one family
(``tests/unit/mypy_cases/fail_generic_mixed_families.py``).

**Kinds.** ``MeanOfDate`` and ``TrueOfDate`` are the static kinds of
:class:`TropicalLongitude` and :class:`Ayanamsa` (written
``Ayanamsa[Mean]`` and ``Ayanamsa[True]``; ``True`` is a Python keyword, so
the aliases are :data:`Mean` and :data:`True_`). A true-of-date value carries
the identity of the nutation-model instance that produced it, a run-time
field that :func:`sidereal_from_tropical` checks.

**Sidereal frames** are data (a text's own frame, a named ayanāṃśa), so the
frame of a :class:`SiderealLongitude` is a run-time field and arithmetic
between two frames is a ``TypeError``; its numeric family is static.

This module holds no astronomy: conversions that need a model (ΔT, leap
seconds, a text's sunrise) are added by the package that keys the model,
each with a test and a citation. The JDN–calendar
arithmetic is ``core/calendar.py``, which the date classes call to
check the day of the month.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Protocol, Self, final

__all__ = [
    "JDN",
    "NOT_MODELLED",
    "TT",
    "UT1",
    "UTC",
    "Ahargana",
    "AngleUnit",
    "Arc",
    "Ayanamsa",
    "CivilInstant",
    "Days",
    "ExactArc",
    "FloatArc",
    "FloatDays",
    "GregorianDate",
    "JulianDate",
    "Mean",
    "MeanOfDate",
    "ModernCivilInstant",
    "Nadika",
    "NotModelled",
    "NutationIdentity",
    "SiddhanticCivilInstant",
    "SiderealLongitude",
    "TropicalLongitude",
    "TrueOfDate",
    "True_",
    "Vinadika",
    "civil_from_utc",
    "days_from_nadika",
    "gmt_from_ut1",
    "jd_at_midnight",
    "mean_time_from_ut1",
    "nadika_from_days",
    "nadika_from_vinadika",
    "sidereal_from_tropical",
    "sidereal_from_tropical_mean",
    "tt_from_ut1",
    "tt_from_utc",
    "ut1_from_apparent_reckoning",
    "ut1_from_gmt",
    "ut1_from_mean_time",
    "ut1_from_text_local",
    "ut1_from_tt",
    "ut1_from_utc",
    "utc_from_civil",
    "utc_from_tt",
    "vinadika_from_nadika",
]

DEGREES_PER_REVOLUTION = 360
NADIKAS_PER_DAY = 60
VINADIKAS_PER_NADIKA = 60


def _exact_scalar(k: object) -> Fraction:
    if isinstance(k, bool) or not isinstance(k, int | Fraction):
        raise TypeError(f"an exact-family scalar is int or Fraction, not {type(k).__name__}")
    return Fraction(k)


def _float_scalar(k: object) -> float:
    if isinstance(k, bool) or not isinstance(k, int | float):
        raise TypeError(f"a float-family scalar is float or int, not {type(k).__name__}")
    f = float(k)
    if f - f != 0:  # an infinity or a NaN
        raise ValueError(f"a float-family scalar is finite, not {f}")
    return f


def _day_split(f: float) -> tuple[int, float]:
    """``f`` as whole days and a fraction in [0, 1).

    A value a few ulp below a whole day leaves ``f - floor(f)`` rounded up to
    exactly 1.0; that carries into the next day.
    """
    carry = int(f // 1)
    fraction = f - carry
    if fraction >= 1:
        carry += 1
        fraction -= 1
    return carry, fraction


def _same_type[T](a: T, b: object) -> T:
    if type(b) is not type(a):
        raise TypeError(f"{type(a).__name__} cannot be combined with {type(b).__name__}")
    return b


# --- angles -----------------------------------------------------------------


class AngleUnit(Enum):
    """The unit an arc is held in. Conversion is the named method ``to``."""

    DEGREE = "degree"
    REVOLUTION = "revolution"


_DEGREES_IN: dict[AngleUnit, int] = {
    AngleUnit.DEGREE: 1,
    AngleUnit.REVOLUTION: DEGREES_PER_REVOLUTION,
}


class Arc(Protocol):
    """The operations both numeric families provide.

    The calendar layer codes against this protocol, with generic functions
    parametrised by ``[A: (ExactArc, FloatArc)]`` (see the module docstring).
    """

    @property
    def unit(self) -> AngleUnit: ...

    @classmethod
    def of_int(cls, value: int, unit: AngleUnit) -> Self: ...

    def to(self, unit: AngleUnit, /) -> Self: ...

    def __add__(self, other: Self, /) -> Self: ...

    def __sub__(self, other: Self, /) -> Self: ...

    def __neg__(self) -> Self: ...

    def __lt__(self, other: Self, /) -> bool: ...

    def __le__(self, other: Self, /) -> bool: ...

    def __gt__(self, other: Self, /) -> bool: ...

    def __ge__(self, other: Self, /) -> bool: ...

    def scaled(self, n: int, /) -> Self: ...

    def floordiv_arc(self, other: Self, /) -> int: ...

    def mod_arc(self, other: Self, /) -> Self: ...


@final
class ExactArc:
    """An angle held exactly: a ``Fraction`` of ``unit``.

    Operators accept another ``ExactArc`` (of the same unit) and scalars of
    kind ``int`` or ``Fraction`` only.
    """

    __slots__ = ("_unit", "_value")

    def __init__(self, value: Fraction | int, unit: AngleUnit) -> None:
        if not isinstance(unit, AngleUnit):
            raise TypeError(f"unit must be an AngleUnit, not {type(unit).__name__}")
        self._value = _exact_scalar(value)
        self._unit = unit

    @classmethod
    def of_int(cls, value: int, unit: AngleUnit) -> ExactArc:
        """The arc of ``value`` whole units."""
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("of_int takes an int")
        return cls(value, unit)

    @property
    def value(self) -> Fraction:
        """The exact magnitude in :attr:`unit`."""
        return self._value

    @property
    def unit(self) -> AngleUnit:
        return self._unit

    def to(self, unit: AngleUnit, /) -> ExactArc:
        """The same angle in ``unit`` (exact: one revolution is 360 degrees)."""
        degrees = self._value * _DEGREES_IN[self._unit]
        return ExactArc(degrees / _DEGREES_IN[unit], unit)

    def _check(self, other: object) -> ExactArc:
        o = _same_type(self, other)
        if o._unit is not self._unit:
            raise TypeError(f"unit mismatch: {self._unit.value} and {o._unit.value}; use .to()")
        return o

    def __add__(self, other: ExactArc) -> ExactArc:
        return ExactArc(self._value + self._check(other)._value, self._unit)

    def __sub__(self, other: ExactArc) -> ExactArc:
        return ExactArc(self._value - self._check(other)._value, self._unit)

    def __neg__(self) -> ExactArc:
        return ExactArc(-self._value, self._unit)

    def __mul__(self, k: int | Fraction) -> ExactArc:
        return ExactArc(self._value * _exact_scalar(k), self._unit)

    def __rmul__(self, k: int | Fraction) -> ExactArc:
        return ExactArc(self._value * _exact_scalar(k), self._unit)

    def __truediv__(self, k: int | Fraction) -> ExactArc:
        return ExactArc(self._value / _exact_scalar(k), self._unit)

    def scaled(self, n: int, /) -> ExactArc:
        if isinstance(n, bool) or not isinstance(n, int):
            raise TypeError("scaled takes an int")
        return ExactArc(self._value * n, self._unit)

    def ratio(self, other: ExactArc) -> Fraction:
        """``self / other`` as an exact number."""
        return self._value / self._check(other)._value

    def floordiv_arc(self, other: ExactArc, /) -> int:
        """How many whole ``other`` fit in ``self`` (floor)."""
        return self._value // self._check(other)._value

    def mod_arc(self, other: ExactArc, /) -> ExactArc:
        """``self`` reduced into ``[0, other)``."""
        return ExactArc(self._value % self._check(other)._value, self._unit)

    def __lt__(self, other: ExactArc) -> bool:
        return self._value < self._check(other)._value

    def __le__(self, other: ExactArc) -> bool:
        return self._value <= self._check(other)._value

    def __gt__(self, other: ExactArc) -> bool:
        return self._value > self._check(other)._value

    def __ge__(self, other: ExactArc) -> bool:
        return self._value >= self._check(other)._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExactArc):
            return NotImplemented
        return self._unit is other._unit and self._value == other._value

    def __hash__(self) -> int:
        return hash((ExactArc, self._unit, self._value))

    def __repr__(self) -> str:
        return f"ExactArc({self._value!r}, {self._unit})"


@final
class FloatArc:
    """An angle held as an IEEE double of ``unit`` (the modern engine's family).

    Operators accept another ``FloatArc`` (of the same unit) and scalars of
    kind ``float`` (or ``int``) only; a ``Fraction`` is refused.
    """

    __slots__ = ("_unit", "_value")

    def __init__(self, value: float, unit: AngleUnit) -> None:
        if not isinstance(unit, AngleUnit):
            raise TypeError(f"unit must be an AngleUnit, not {type(unit).__name__}")
        self._value = _float_scalar(value)
        self._unit = unit

    @classmethod
    def of_int(cls, value: int, unit: AngleUnit) -> FloatArc:
        """The arc of ``value`` whole units."""
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("of_int takes an int")
        return cls(float(value), unit)

    @property
    def value(self) -> float:
        """The magnitude in :attr:`unit`."""
        return self._value

    @property
    def unit(self) -> AngleUnit:
        return self._unit

    def to(self, unit: AngleUnit, /) -> FloatArc:
        """The same angle in ``unit``."""
        degrees = self._value * _DEGREES_IN[self._unit]
        return FloatArc(degrees / _DEGREES_IN[unit], unit)

    def _check(self, other: object) -> FloatArc:
        o = _same_type(self, other)
        if o._unit is not self._unit:
            raise TypeError(f"unit mismatch: {self._unit.value} and {o._unit.value}; use .to()")
        return o

    def __add__(self, other: FloatArc) -> FloatArc:
        return FloatArc(self._value + self._check(other)._value, self._unit)

    def __sub__(self, other: FloatArc) -> FloatArc:
        return FloatArc(self._value - self._check(other)._value, self._unit)

    def __neg__(self) -> FloatArc:
        return FloatArc(-self._value, self._unit)

    def __mul__(self, k: float) -> FloatArc:
        return FloatArc(self._value * _float_scalar(k), self._unit)

    def __rmul__(self, k: float) -> FloatArc:
        return FloatArc(self._value * _float_scalar(k), self._unit)

    def __truediv__(self, k: float) -> FloatArc:
        return FloatArc(self._value / _float_scalar(k), self._unit)

    def scaled(self, n: int, /) -> FloatArc:
        if isinstance(n, bool) or not isinstance(n, int):
            raise TypeError("scaled takes an int")
        return FloatArc(self._value * n, self._unit)

    def ratio(self, other: FloatArc) -> float:
        """``self / other`` as a float."""
        return self._value / self._check(other)._value

    def floordiv_arc(self, other: FloatArc, /) -> int:
        """How many whole ``other`` fit in ``self`` (floor)."""
        return int(self._value // self._check(other)._value)

    def mod_arc(self, other: FloatArc, /) -> FloatArc:
        """``self`` reduced into ``[0, other)``.

        A value a few ulp below 0 leaves the float remainder at exactly the
        modulus (release review AS5: a tithi 31); it is the largest float below
        the modulus, which keeps it on the side of 0 it came from (item 2: a tithi 30, not 1).
        """
        m = self._check(other)._value
        r = self._value % m
        return FloatArc(math.nextafter(m, 0.0) if r == m else r, self._unit)

    def __lt__(self, other: FloatArc) -> bool:
        return self._value < self._check(other)._value

    def __le__(self, other: FloatArc) -> bool:
        return self._value <= self._check(other)._value

    def __gt__(self, other: FloatArc) -> bool:
        return self._value > self._check(other)._value

    def __ge__(self, other: FloatArc) -> bool:
        return self._value >= self._check(other)._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FloatArc):
            return NotImplemented
        return self._unit is other._unit and self._value == other._value

    def __hash__(self) -> int:
        return hash((FloatArc, self._unit, self._value))

    def __repr__(self) -> str:
        return f"FloatArc({self._value!r}, {self._unit})"


def _full_circle[A: (ExactArc, FloatArc)](arc: A) -> A:
    return type(arc).of_int(DEGREES_PER_REVOLUTION, AngleUnit.DEGREE)


def _normalise[A: (ExactArc, FloatArc)](arc: A) -> A:
    """``arc`` in degrees, reduced into ``[0°, 360°)``."""
    return arc.to(AngleUnit.DEGREE).mod_arc(_full_circle(arc))


# --- kinds and frames ---------------------------------------------------------


@final
class MeanOfDate:
    """Kind marker: referred to the mean equinox of date (no nutation)."""

    def __init__(self) -> None:
        raise TypeError("MeanOfDate is a kind marker and is not instantiated")


@final
class TrueOfDate:
    """Kind marker: referred to the true equinox of date (nutation applied)."""

    def __init__(self) -> None:
        raise TypeError("TrueOfDate is a kind marker and is not instantiated")


Mean = MeanOfDate
"""``Ayanamsa[Mean]``."""

True_ = TrueOfDate
"""``Ayanamsa[True]`` (``True`` is a Python keyword)."""


@dataclass(frozen=True, slots=True)
class NutationIdentity:
    """The identity of the nutation-model instance that produced a value.

    ``model`` names the model (``iau2000b``); ``instance`` identifies the
    loaded coefficient set (its data hash), so that two values computed with
    different coefficient files are not combined.
    """

    model: str
    instance: str


def _check_kind(kind: object, nutation: NutationIdentity | None, what: str) -> None:
    if kind is TrueOfDate:
        if not isinstance(nutation, NutationIdentity):
            raise TypeError(f"a true-of-date {what} carries its NutationIdentity")
    elif kind is MeanOfDate:
        if nutation is not None:
            raise TypeError(f"a mean-of-date {what} carries no nutation identity")
    else:
        raise TypeError(f"{what} kind must be MeanOfDate or TrueOfDate, not {kind!r}")


@final
class TropicalLongitude[K: (MeanOfDate, TrueOfDate)]:
    """A tropical longitude of kind ``K``, reduced into [0°, 360°).

    Tropical longitudes exist only under the modern engine, so the arc is a
    :class:`FloatArc`. Defined operations: ``+ FloatArc`` (a shift, same
    kind) and ``- TropicalLongitude[K]`` (the arc between two longitudes of
    the same kind and nutation instance). Nothing else: in particular no
    operation with a :class:`SiderealLongitude` or an :class:`Ayanamsa`
    exists; use :func:`sidereal_from_tropical`.
    """

    __slots__ = ("_arc", "_kind", "_nutation")

    def __init__(self, arc: FloatArc, kind: type[K], nutation: NutationIdentity | None) -> None:
        if not isinstance(arc, FloatArc):
            raise TypeError("a tropical longitude holds a FloatArc")
        _check_kind(kind, nutation, "tropical longitude")
        self._arc = _normalise(arc)
        self._kind: type[K] = kind
        self._nutation = nutation

    @property
    def arc(self) -> FloatArc:
        return self._arc

    @property
    def kind(self) -> type[K]:
        return self._kind

    @property
    def nutation(self) -> NutationIdentity | None:
        return self._nutation

    def __add__(self, shift: FloatArc) -> TropicalLongitude[K]:
        if not isinstance(shift, FloatArc):
            raise TypeError("a tropical longitude is shifted by a FloatArc only")
        return TropicalLongitude(self._arc + shift.to(AngleUnit.DEGREE), self._kind, self._nutation)

    def __sub__(self, other: TropicalLongitude[K]) -> FloatArc:
        o = _same_type(self, other)
        if o._kind is not self._kind or o._nutation != self._nutation:
            raise TypeError("tropical longitudes of different kinds or nutation instances")
        return self._arc - o._arc

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TropicalLongitude):
            return NotImplemented
        return (self._arc, self._kind, self._nutation) == (other._arc, other._kind, other._nutation)

    def __hash__(self) -> int:
        return hash((TropicalLongitude, self._arc, self._kind, self._nutation))

    def __repr__(self) -> str:
        return f"TropicalLongitude({self._arc!r}, {self._kind.__name__}, {self._nutation!r})"


@final
class Ayanamsa[K: (MeanOfDate, TrueOfDate)]:
    """A named ayanāṃśa value of kind ``K``.

    ``ayanamsa_id`` is the registry id (``iae_lahiri``, ``citra_180``,
    ``crc_1955``); it names the sidereal frame of the result of
    :func:`sidereal_from_tropical`.
    """

    __slots__ = ("_arc", "_ayanamsa_id", "_kind", "_nutation")

    def __init__(
        self,
        arc: FloatArc,
        kind: type[K],
        nutation: NutationIdentity | None,
        ayanamsa_id: str,
    ) -> None:
        if not isinstance(arc, FloatArc):
            raise TypeError("an ayanamsa holds a FloatArc")
        if not isinstance(ayanamsa_id, str) or not ayanamsa_id:
            raise TypeError("an ayanamsa carries its registry id")
        _check_kind(kind, nutation, "ayanamsa")
        self._arc = arc.to(AngleUnit.DEGREE)
        self._kind: type[K] = kind
        self._nutation = nutation
        self._ayanamsa_id = ayanamsa_id

    @property
    def arc(self) -> FloatArc:
        return self._arc

    @property
    def kind(self) -> type[K]:
        return self._kind

    @property
    def nutation(self) -> NutationIdentity | None:
        return self._nutation

    @property
    def ayanamsa_id(self) -> str:
        return self._ayanamsa_id

    def __repr__(self) -> str:
        return (
            f"Ayanamsa({self._arc!r}, {self._kind.__name__}, {self._nutation!r}, "
            f"{self._ayanamsa_id!r})"
        )


@final
class SiderealLongitude[A: (ExactArc, FloatArc)]:
    """A sidereal longitude in the frame ``frame``, reduced into [0°, 360°).

    ``frame`` is a data-defined id: ``text:<text_id>`` for a siddhantic
    method's own frame, ``ayanamsa:<id>`` for a modern one. Defined
    operations: ``+ A`` (a shift) and ``- SiderealLongitude[A]`` in the same
    frame (an arc). Frames are compared at run time; the family ``A`` is
    static.
    """

    __slots__ = ("_arc", "_frame")

    def __init__(self, arc: A, frame: str) -> None:
        if not isinstance(arc, ExactArc | FloatArc):
            raise TypeError("a sidereal longitude holds an ExactArc or a FloatArc")
        if not isinstance(frame, str) or ":" not in frame:
            raise TypeError("a sidereal frame is an id of the form '<kind>:<id>'")
        self._arc: A = _normalise(arc)
        self._frame = frame

    @property
    def arc(self) -> A:
        return self._arc

    @property
    def frame(self) -> str:
        return self._frame

    def __add__(self, shift: A) -> SiderealLongitude[A]:
        return SiderealLongitude(self._arc + shift.to(AngleUnit.DEGREE), self._frame)

    def __sub__(self, other: SiderealLongitude[A]) -> A:
        o = _same_type(self, other)
        if o._frame != self._frame:
            raise TypeError(f"sidereal frames differ: {self._frame} and {o._frame}")
        return self._arc - o._arc

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SiderealLongitude):
            return NotImplemented
        return self._frame == other._frame and self._arc == other._arc

    def __hash__(self) -> int:
        return hash((SiderealLongitude, self._frame, self._arc))

    def __repr__(self) -> str:
        return f"SiderealLongitude({self._arc!r}, {self._frame!r})"


def sidereal_from_tropical(
    lon: TropicalLongitude[TrueOfDate], a: Ayanamsa[TrueOfDate]
) -> SiderealLongitude[FloatArc]:
    """λ_sid = λ_trop − A, both referred to the true equinox of date.

    The two values
    must come from the same nutation-model instance; a pair whose identities
    differ is refused. The result's frame is ``ayanamsa:<id>``.
    """
    if not isinstance(lon, TropicalLongitude) or not isinstance(a, Ayanamsa):
        raise TypeError("sidereal_from_tropical takes a TropicalLongitude and an Ayanamsa")
    if lon.kind is not TrueOfDate or a.kind is not TrueOfDate:
        raise TypeError("sidereal_from_tropical takes a true-of-date longitude and ayanamsa")
    if lon.nutation != a.nutation:
        raise TypeError(
            f"nutation instances differ: longitude {lon.nutation!r}, ayanamsa {a.nutation!r}"
        )
    return SiderealLongitude(lon.arc - a.arc, f"ayanamsa:{a.ayanamsa_id}")


def sidereal_from_tropical_mean(
    lon: TropicalLongitude[MeanOfDate], a: Ayanamsa[MeanOfDate]
) -> SiderealLongitude[FloatArc]:
    """λ_sid = λ_trop − A, both referred to the mean equinox of date (no nutation)."""
    if not isinstance(lon, TropicalLongitude) or not isinstance(a, Ayanamsa):
        raise TypeError("sidereal_from_tropical_mean takes a TropicalLongitude and an Ayanamsa")
    if lon.kind is not MeanOfDate or a.kind is not MeanOfDate:
        raise TypeError("sidereal_from_tropical_mean takes a mean-of-date longitude and ayanamsa")
    return SiderealLongitude(lon.arc - a.arc, f"ayanamsa:{a.ayanamsa_id}")


# --- durations ----------------------------------------------------------------


class _ExactDuration:
    """An exact duration in one unit; arithmetic only within the same class."""

    __slots__ = ("_value",)

    def __init__(self, value: Fraction | int) -> None:
        self._value = _exact_scalar(value)

    @property
    def value(self) -> Fraction:
        return self._value

    def __add__(self, other: Self) -> Self:
        return type(self)(self._value + _same_type(self, other)._value)

    def __sub__(self, other: Self) -> Self:
        return type(self)(self._value - _same_type(self, other)._value)

    def __neg__(self) -> Self:
        return type(self)(-self._value)

    def __mul__(self, k: int | Fraction) -> Self:
        return type(self)(self._value * _exact_scalar(k))

    def __rmul__(self, k: int | Fraction) -> Self:
        return type(self)(self._value * _exact_scalar(k))

    def __lt__(self, other: Self) -> bool:
        return self._value < _same_type(self, other)._value

    def __le__(self, other: Self) -> bool:
        return self._value <= _same_type(self, other)._value

    def __gt__(self, other: Self) -> bool:
        return self._value > _same_type(self, other)._value

    def __ge__(self, other: Self) -> bool:
        return self._value >= _same_type(self, other)._value

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        assert isinstance(other, _ExactDuration)
        return self._value == other._value

    def __hash__(self) -> int:
        return hash((type(self), self._value))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._value!r})"


@final
class Days(_ExactDuration):
    """An exact duration in civil (sāvana) days."""


@final
class Nadika(_ExactDuration):
    """An exact duration in nāḍikās (one sixtieth of a civil day)."""


@final
class Vinadika(_ExactDuration):
    """An exact duration in vināḍikās (one sixtieth of a nāḍikā)."""


def days_from_nadika(n: Nadika) -> Days:
    """Days = nāḍikās / 60: sixty nāḍikās make a civil day."""
    return Days(_same_type(Nadika(0), n).value / NADIKAS_PER_DAY)


def nadika_from_days(d: Days) -> Nadika:
    """Nāḍikās = days × 60."""
    return Nadika(_same_type(Days(0), d).value * NADIKAS_PER_DAY)


def nadika_from_vinadika(v: Vinadika) -> Nadika:
    """Nāḍikās = vināḍikās / 60: sixty vināḍikās make a nāḍikā."""
    return Nadika(_same_type(Vinadika(0), v).value / VINADIKAS_PER_NADIKA)


def vinadika_from_nadika(n: Nadika) -> Vinadika:
    """Vināḍikās = nāḍikās × 60."""
    return Vinadika(_same_type(Nadika(0), n).value * VINADIKAS_PER_NADIKA)


@final
class FloatDays:
    """A duration in days as an IEEE double (the modern engine's durations)."""

    __slots__ = ("_value",)

    def __init__(self, value: float) -> None:
        self._value = _float_scalar(value)

    @property
    def value(self) -> float:
        return self._value

    def __add__(self, other: FloatDays) -> FloatDays:
        return FloatDays(self._value + _same_type(self, other)._value)

    def __sub__(self, other: FloatDays) -> FloatDays:
        return FloatDays(self._value - _same_type(self, other)._value)

    def __neg__(self) -> FloatDays:
        return FloatDays(-self._value)

    def __mul__(self, k: float) -> FloatDays:
        return FloatDays(self._value * _float_scalar(k))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FloatDays):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash((FloatDays, self._value))

    def __repr__(self) -> str:
        return f"FloatDays({self._value!r})"


# --- time scales (modern engine) ------------------------------------------------


class _JulianInstant:
    """A two-part Julian date on one time scale: ``jd_whole + jd_fraction``.

    ``jd_whole`` is an integer Julian date (noon to noon) and ``jd_fraction``
    lies in [0, 1). Arithmetic: ``+ FloatDays`` and ``- <same scale>``; no
    operation crosses scales. Conversions between scales need ΔT and the
    leap-second table and are named functions of ``modern/timescales.py``.
    """

    __slots__ = ("_fraction", "_whole")

    def __init__(self, jd_whole: int, jd_fraction: float) -> None:
        if isinstance(jd_whole, bool) or not isinstance(jd_whole, int):
            raise TypeError("jd_whole is an int")
        carry, self._fraction = _day_split(_float_scalar(jd_fraction))
        self._whole = jd_whole + carry

    @property
    def jd_whole(self) -> int:
        return self._whole

    @property
    def jd_fraction(self) -> float:
        return self._fraction

    def __add__(self, d: FloatDays) -> Self:
        if not isinstance(d, FloatDays):
            raise TypeError(f"{type(self).__name__} is shifted by FloatDays only")
        return type(self)(self._whole, self._fraction + d.value)

    def __sub__(self, other: Self) -> FloatDays:
        o = _same_type(self, other)
        return FloatDays((self._whole - o._whole) + (self._fraction - o._fraction))

    def __lt__(self, other: Self) -> bool:
        o = _same_type(self, other)
        return (self._whole, self._fraction) < (o._whole, o._fraction)

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        assert isinstance(other, _JulianInstant)
        return (self._whole, self._fraction) == (other._whole, other._fraction)

    def __hash__(self) -> int:
        return hash((type(self), self._whole, self._fraction))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._whole!r}, {self._fraction!r})"


@final
class TT(_JulianInstant):
    """Terrestrial Time, as a two-part Julian date."""


@final
class UT1(_JulianInstant):
    """Universal Time UT1, as a two-part Julian date."""


@final
class UTC(_JulianInstant):
    """Coordinated Universal Time, as a two-part quasi-Julian date."""


# --- day counts and dates ---------------------------------------------------------


@final
@dataclass(frozen=True, slots=True, order=True)
class JDN:
    """A Julian Day Number: the integer label of a civil day."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("a JDN is an int")

    def plus_days(self, n: int) -> JDN:
        """The JDN ``n`` civil days later."""
        if isinstance(n, bool) or not isinstance(n, int):
            raise TypeError("plus_days takes an int")
        return JDN(self.value + n)

    def days_since(self, other: JDN) -> int:
        """The number of civil days from ``other`` to ``self``."""
        return self.value - _same_type(self, other).value


@final
@dataclass(frozen=True, slots=True)
class Ahargana:
    """A text's day count: civil days ``day`` from the text's epoch plus ``fraction``.

    ``text`` is the text id (``aryabhatiya``); ``fraction`` lies in [0, 1)
    and is a fraction of the text's civil day. Arithmetic
    only within one text; the passage to a JDN is the text's ahargaṇa rule,
    a procedure of the package that keys it.
    """

    text: str
    day: int
    fraction: Fraction

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text:
            raise TypeError("an ahargana names its text")
        if isinstance(self.day, bool) or not isinstance(self.day, int):
            raise TypeError("the ahargana day count is an int")
        f = _exact_scalar(self.fraction)
        if not (0 <= f < 1):
            raise ValueError(f"ahargana fraction {f} is not in [0, 1)")
        object.__setattr__(self, "fraction", f)

    def plus(self, d: Days) -> Ahargana:
        """The ahargaṇa ``d`` days later, in the same text's count."""
        total = self.fraction + _same_type(Days(0), d).value
        carry = total // 1
        return Ahargana(self.text, self.day + carry, total - carry)

    def minus(self, other: Ahargana) -> Days:
        """The days from ``other`` to ``self``; both must be of the same text."""
        o = _same_type(self, other)
        if o.text != self.text:
            raise TypeError(f"ahargana of different texts: {self.text} and {o.text}")
        return Days((self.day - o.day) + (self.fraction - o.fraction))


def _check_ymd(y: object, m: object, d: object) -> None:
    for name, v in (("year", y), ("month", m), ("day", d)):
        if isinstance(v, bool) or not isinstance(v, int):
            raise TypeError(f"{name} is an int (astronomical year numbering)")
    assert isinstance(m, int) and isinstance(d, int)
    if not (1 <= m <= 12):
        raise ValueError(f"month {m} is not in 1..12")
    if d < 1:
        raise ValueError(f"day {d} is not positive")


@final
@dataclass(frozen=True, slots=True)
class JulianDate:
    """A date of the Julian calendar, astronomical year numbering (year 0 = 1 BCE).

    The day of the month is checked against the Julian leap rule, and the
    passage to a JDN is ``core/calendar.py``'s ``jdn_from_julian``.
    """

    y: int
    m: int
    d: int

    def __post_init__(self) -> None:
        _check_ymd(self.y, self.m, self.d)
        from jyotirganita.core.calendar import check_day_of_month

        check_day_of_month(self)


@final
@dataclass(frozen=True, slots=True)
class GregorianDate:
    """A date of the (proleptic) Gregorian calendar, astronomical year numbering.

    The day of the month is checked against the Gregorian leap rule, and the
    passage to a JDN is ``core/calendar.py``'s ``jdn_from_gregorian``.
    """

    y: int
    m: int
    d: int

    def __post_init__(self) -> None:
        _check_ymd(self.y, self.m, self.d)
        from jyotirganita.core.calendar import check_day_of_month

        check_day_of_month(self)


# --- civil instants -----------------------------------------------------------------


@final
@dataclass(frozen=True, slots=True)
class SiddhanticCivilInstant:
    """An instant on civil day ``jdn``: ``nadika_after_sunrise`` after the text's sunrise.

    ``standard`` is ``text_local:<text_id>``.
    """

    jdn: JDN
    nadika_after_sunrise: Nadika
    standard: str

    def __post_init__(self) -> None:
        if not isinstance(self.jdn, JDN) or not isinstance(self.nadika_after_sunrise, Nadika):
            raise TypeError("a siddhantic instant is (JDN, Nadika, standard)")
        if not self.standard.startswith("text_local:") or self.standard == "text_local:":
            raise ValueError("a siddhantic instant's standard is text_local:<text_id>")


@final
@dataclass(frozen=True, slots=True)
class ModernCivilInstant:
    """An instant on civil day ``jdn`` at ``local_fraction`` of the day, under ``standard``."""

    jdn: JDN
    local_fraction: float
    standard: str

    def __post_init__(self) -> None:
        if not isinstance(self.jdn, JDN):
            raise TypeError("a modern instant is (JDN, float, standard)")
        f = _float_scalar(self.local_fraction)
        if not (0 <= f < 1):
            raise ValueError(f"local fraction {f} is not in [0, 1)")
        if not isinstance(self.standard, str) or not self.standard:
            raise TypeError("a modern instant names its time standard")


def utc_from_civil(instant: ModernCivilInstant, offset: Fraction) -> UTC:
    """The UTC of a civil instant under a standard ``offset`` days east of Greenwich.

    Definition: a civil day *jdn* begins at its local
    midnight, the Julian date *jdn* − 1/2 on the standard's clock; the
    instant is ``local_fraction`` of a day after it, and Universal Time is
    the standard's clock less its offset (rashtriya_panchanga_1959 p. xvi: I.S.T. is 5 h 30 m
    ahead of Universal Time; calendar_reform_committee_1955 p. [40] item (4): 5-30 A.M. I.S.T. is
    0 h U.T.). ``offset`` is the standard's offset in force on that day
    (``jyotirganita/data/time_standards.py``). Before 1972 the result is
    Greenwich mean time on the UTC scale's two-part form, as the standards
    of that time were defined.
    """
    if not isinstance(instant, ModernCivilInstant):
        raise TypeError("utc_from_civil takes a ModernCivilInstant")
    off = _exact_scalar(offset)
    return UTC(instant.jdn.value - 1, instant.local_fraction + 0.5 - float(off))


def civil_from_utc(t: UTC, offset: Fraction, standard: str) -> ModernCivilInstant:
    """The civil instant under ``standard`` (``offset`` days east) of UTC ``t``.

    The inverse of :func:`utc_from_civil`: the standard's clock is UT plus
    its offset, and the civil day is the one whose local midnight precedes
    the instant.
    """
    if not isinstance(t, UTC):
        raise TypeError("civil_from_utc takes a UTC instant")
    local = t.jd_fraction + float(_exact_scalar(offset)) - 0.5
    carry, fraction = _day_split(local)
    return ModernCivilInstant(JDN(t.jd_whole + 1 + carry), fraction, standard)


def ut1_from_mean_time(instant: ModernCivilInstant, offset: Fraction) -> UT1:
    """The UT1 of a civil instant under a local mean time ``offset`` days east of Greenwich.

    Definition (``time_standards.lmt.definition.sewell_dikshit_1896``): the
    mean time of a place is counted from its mean midnight, and Greenwich
    mean solar time is Universal Time (UT1); the place's clock is UT1 plus
    its longitude east as a fraction of the day. The civil day *jdn* begins
    at the Julian date *jdn* − 1/2 on that clock, as in :func:`utc_from_civil`.
    """
    if not isinstance(instant, ModernCivilInstant):
        raise TypeError("ut1_from_mean_time takes a ModernCivilInstant")
    off = _exact_scalar(offset)
    return UT1(instant.jdn.value - 1, instant.local_fraction + 0.5 - float(off))


def mean_time_from_ut1(t: UT1, offset: Fraction, standard: str) -> ModernCivilInstant:
    """The civil instant under a local mean time ``offset`` days east of UT1 ``t``.

    The inverse of :func:`ut1_from_mean_time`.
    """
    if not isinstance(t, UT1):
        raise TypeError("mean_time_from_ut1 takes a UT1 instant")
    local = t.jd_fraction + float(_exact_scalar(offset)) - 0.5
    carry, fraction = _day_split(local)
    return ModernCivilInstant(JDN(t.jd_whole + 1 + carry), fraction, standard)


def ut1_from_gmt(t: UTC) -> UT1:
    """Greenwich mean time on a clock standard before UTC's leap-second era, as UT1.

    Before 1972 a standard defined as an offset from Universal Time (calendar_reform_committee_1955
    p. [40] item (4): 5-30 A.M. I.S.T. is 0 h U.T.) is read on Greenwich
    mean time, which is mean solar time at Greenwich, UT1; the two-part
    instant :func:`utc_from_civil` returns for such a day is that time. The
    engine records the reading in provenance (``docs/methods/modern_de.md``).
    """
    if not isinstance(t, UTC):
        raise TypeError("ut1_from_gmt takes a UTC instant")
    return UT1(t.jd_whole, t.jd_fraction)


def gmt_from_ut1(t: UT1) -> UTC:
    """The inverse of :func:`ut1_from_gmt`: UT1 read as Greenwich mean time before 1972.

    Same definition and citation as :func:`ut1_from_gmt`; it serves only a
    day outside the leap-second table, where the clock standard's offset is
    counted from Greenwich mean time.
    """
    if not isinstance(t, UT1):
        raise TypeError("gmt_from_ut1 takes a UT1 instant")
    return UTC(t.jd_whole, t.jd_fraction)


def tt_from_ut1(t: UT1, delta_t: FloatDays) -> TT:
    """TT = UT1 + ΔT; ``delta_t`` is the named ΔT model's value at the instant."""
    if not isinstance(t, UT1) or not isinstance(delta_t, FloatDays):
        raise TypeError("tt_from_ut1 takes a UT1 instant and a FloatDays ΔT")
    return TT(t.jd_whole, t.jd_fraction + delta_t.value)


def ut1_from_tt(t: TT, delta_t: FloatDays) -> UT1:
    """UT1 = TT − ΔT, the inverse of :func:`tt_from_ut1`."""
    if not isinstance(t, TT) or not isinstance(delta_t, FloatDays):
        raise TypeError("ut1_from_tt takes a TT instant and a FloatDays ΔT")
    return UT1(t.jd_whole, t.jd_fraction - delta_t.value)


def tt_from_utc(t: UTC, tai_minus_utc: FloatDays, tt_minus_tai: FloatDays) -> TT:
    """TT = UTC + (TAI − UTC) + (TT − TAI).

    ``tai_minus_utc`` is the leap-second table's value in force at ``t``;
    ``tt_minus_tai`` is the defined offset (``modern.timescales.tt_minus_tai``).
    """
    if not isinstance(t, UTC):
        raise TypeError("tt_from_utc takes a UTC instant")
    if not isinstance(tai_minus_utc, FloatDays) or not isinstance(tt_minus_tai, FloatDays):
        raise TypeError("tt_from_utc takes its offsets as FloatDays")
    return TT(t.jd_whole, t.jd_fraction + tai_minus_utc.value + tt_minus_tai.value)


def utc_from_tt(t: TT, tai_minus_utc: FloatDays, tt_minus_tai: FloatDays) -> UTC:
    """UTC = TT − (TT − TAI) − (TAI − UTC), the inverse of :func:`tt_from_utc`."""
    if not isinstance(t, TT):
        raise TypeError("utc_from_tt takes a TT instant")
    if not isinstance(tai_minus_utc, FloatDays) or not isinstance(tt_minus_tai, FloatDays):
        raise TypeError("utc_from_tt takes its offsets as FloatDays")
    return UTC(t.jd_whole, t.jd_fraction - tai_minus_utc.value - tt_minus_tai.value)


def ut1_from_utc(t: UTC, ut1_minus_utc: FloatDays) -> UT1:
    """UT1 = UTC + (UT1 − UTC), the observed difference the IERS series gives."""
    if not isinstance(t, UTC) or not isinstance(ut1_minus_utc, FloatDays):
        raise TypeError("ut1_from_utc takes a UTC instant and a FloatDays difference")
    return UT1(t.jd_whole, t.jd_fraction + ut1_minus_utc.value)


def jd_at_midnight(jdn: JDN) -> Fraction:
    """The Julian date, exact, of the midnight that opens civil day ``jdn``.

    Definition: a Julian date counts days from noon, and
    civil day ``jdn`` is the day whose noon is Julian date ``jdn``, so the
    midnight that opens it is half a day earlier on the same clock,
    ``jdn − 1/2`` (:func:`ut1_from_text_local` places local mean midnight
    by it).
    """
    if not isinstance(jdn, JDN):
        raise TypeError("jd_at_midnight takes a JDN")
    return Fraction(jdn.value) - Fraction(1, 2)


def ut1_from_text_local(
    instant: SiddhanticCivilInstant, sunrise_after_midnight: Nadika, longitude_east: Fraction
) -> UT1:
    """The UT1 of a text's instant, its day fractions read as local mean time (``derived_ut``).

    Definition (stated once there): the text's mean
    sunrise is taken as 6h local mean time at the text's meridian (a
    modelling convention), so the text's computed sunrise of civil day
    *jdn* lies ``sunrise_after_midnight`` nāḍikās after local mean midnight
    at the observer (the record's ``sunrise`` leaf: 15 − cara ∓ bhujāntara
    where the text applies it). Local mean midnight of civil day *jdn* at
    a place ``longitude_east`` degrees east of Greenwich is the Julian date
    *jdn* − 1/2 on the place's mean-time clock, which is UT1 plus the
    longitude as a fraction of the day (:func:`ut1_from_mean_time`;
    ``time_standards.lmt.definition.sewell_dikshit_1896``). The instant then lies the
    sunrise's nāḍikās plus its own ``nadika_after_sunrise`` after that
    midnight, 60 nāḍikās to the day. No ΔT enters. The sum is exact until
    the one conversion to the two-part float of :class:`UT1`. For a text
    whose day fractions are apparent time, :func:`ut1_from_apparent_reckoning`
    applies the equation of time to the result.
    """
    if not isinstance(instant, SiddhanticCivilInstant) or not isinstance(
        sunrise_after_midnight, Nadika
    ):
        raise TypeError("ut1_from_text_local takes a SiddhanticCivilInstant and a Nadika")
    after = days_from_nadika(sunrise_after_midnight).value + (
        days_from_nadika(instant.nadika_after_sunrise).value
    )
    off = _exact_scalar(longitude_east) / DEGREES_PER_REVOLUTION
    whole = instant.jdn.value - 1
    return UT1(whole, float(jd_at_midnight(instant.jdn) - whole + after - off))


def ut1_from_apparent_reckoning(t: UT1, apparent_minus_mean: FloatDays) -> UT1:
    """UT1 of an instant counted in local apparent time, from its mean-time reading ``t``.

    Definition: ``t`` is the UT1 the instant would have if
    its clock were local mean time (:func:`ut1_from_text_local`); apparent
    solar time exceeds mean solar time by the equation of time E =
    apparent − mean (``apparent_minus_mean``), so the instant's mean time,
    and its UT1, is the reading less E.
    """
    if not isinstance(t, UT1) or not isinstance(apparent_minus_mean, FloatDays):
        raise TypeError("ut1_from_apparent_reckoning takes a UT1 and a FloatDays equation of time")
    return UT1(t.jd_whole, t.jd_fraction - apparent_minus_mean.value)


type CivilInstant = SiddhanticCivilInstant | ModernCivilInstant
"""The one instant type the record and the API carry, in its two forms."""


@final
class NotModelled:
    """The value of a quantity a method does not model.

    One spelling, ``not_modelled``, per leaf; a singleton, compared by identity.
    """

    _instance: NotModelled | None = None

    def __new__(cls) -> NotModelled:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "not_modelled"


NOT_MODELLED = NotModelled()
