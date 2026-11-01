"""Generic code over the families cannot be called with one of each.

The calendar layer's generic functions are parametrised by the constrained
type parameter ``[A: (ExactArc, FloatArc)]`` (core/types.py docstring).
"""

from jyotirganita.core.types import ExactArc, FloatArc

from ._setup import exact, floating


def twice[A: (ExactArc, FloatArc)](x: A, y: A) -> A:
    return x + y


twice(exact, floating)  # expect-error: type-var
