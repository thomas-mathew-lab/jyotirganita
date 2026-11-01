"""Control: the same API used correctly type-checks with no error."""

from fractions import Fraction

from jyotirganita.core.types import (
    Arc,
    ExactArc,
    FloatArc,
    SiderealLongitude,
    sidereal_from_tropical,
    sidereal_from_tropical_mean,
)

from ._setup import (
    ayanamsa_mean,
    ayanamsa_true,
    exact,
    floating,
    sidereal,
    tropical_mean,
    tropical_true,
)


def twice[A: (ExactArc, FloatArc)](x: A, y: A) -> A:
    return x + y


a: ExactArc = exact + exact
b: ExactArc = exact * Fraction(1, 2)
c: ExactArc = exact * 2
d: FloatArc = floating * 0.5
e: FloatArc = tropical_true - tropical_true
f: SiderealLongitude[FloatArc] = sidereal_from_tropical(tropical_true, ayanamsa_true)
g: SiderealLongitude[FloatArc] = sidereal_from_tropical_mean(tropical_mean, ayanamsa_mean)
h: SiderealLongitude[FloatArc] = sidereal + floating
i: ExactArc = twice(exact, exact)
j: FloatArc = twice(floating, floating)
k: Arc = exact
m: Arc = floating
