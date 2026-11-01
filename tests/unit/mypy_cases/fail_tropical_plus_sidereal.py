"""Adding a TropicalLongitude to a SiderealLongitude is a type error."""

from ._setup import sidereal, tropical_true

tropical_true + sidereal  # expect-error: operator
