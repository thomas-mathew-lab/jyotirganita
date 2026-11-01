"""An Ayanamsa[Mean] where Ayanamsa[True] is required is a type error."""

from jyotirganita.core.types import sidereal_from_tropical

from ._setup import ayanamsa_mean, tropical_true

sidereal_from_tropical(tropical_true, ayanamsa_mean)  # expect-error: arg-type
