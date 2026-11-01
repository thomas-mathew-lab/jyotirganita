"""Shared values for the mypy mixing cases.

Not collected by pytest and excluded from the project's own mypy run; the
cases are type-checked by ``tests/unit/test_mypy_mixing.py``.
"""

from fractions import Fraction

from jyotirganita.core.types import (
    AngleUnit,
    Ayanamsa,
    ExactArc,
    FloatArc,
    MeanOfDate,
    NutationIdentity,
    SiderealLongitude,
    TropicalLongitude,
    TrueOfDate,
)

NUT = NutationIdentity("iau2000b", "test-instance")
exact = ExactArc(Fraction(1, 3), AngleUnit.DEGREE)
floating = FloatArc(1.0, AngleUnit.DEGREE)
tropical_true = TropicalLongitude(floating, TrueOfDate, NUT)
tropical_mean = TropicalLongitude(floating, MeanOfDate, None)
sidereal = SiderealLongitude(floating, "ayanamsa:test")
ayanamsa_true = Ayanamsa(floating, TrueOfDate, NUT, "test")
ayanamsa_mean = Ayanamsa(floating, MeanOfDate, None, "test")
