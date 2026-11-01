"""ExactArc + FloatArc is a type error."""

from ._setup import exact, floating

exact + floating  # expect-error: operator
