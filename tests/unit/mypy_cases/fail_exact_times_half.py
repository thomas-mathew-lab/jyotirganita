"""ExactArc * 0.5 is a type error: the exact family takes int and Fraction scalars only."""

from ._setup import exact

exact * 0.5  # expect-error: operator
