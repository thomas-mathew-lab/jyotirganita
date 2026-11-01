"""Scan-and-Brent on an absolute grid (the modern engine's ``root``).

The modern engine finds every instant it reports (a rise or set, an
element's ending, a saṅkrānti) as a sign change of a continuous function
of time: the function is sampled on a grid fixed in absolute time (the
multiples of the scan step counted from the Julian date's zero, so that
a result never depends on where a search window began) and each bracketed
change is refined by Brent's method (Brent 1973, *Algorithms for
Minimization without Derivatives*, ch. 4: inverse quadratic interpolation
and the secant step, falling back to bisection) until the bracket is
narrower than the tolerance. The step, the tolerance and the iteration
cap are engine parameters (``modern.root.*``,
``data/engine_parameters.yaml``) whose justifications state why each is
fine enough; a bracket that does not close within the cap is a hard
error, never a silent best guess.

Times are TT Julian dates held as a whole day and a fraction (the
:class:`~jyotirganita.core.types.TT` form); the grid and the refinement
work in days from the window's whole day so that no precision is lost.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import ceil, floor

from jyotirganita.core.types import TT
from jyotirganita.data.engine_parameters import EngineParameter

__all__ = ["RootError", "RootFinder"]


class RootError(RuntimeError):
    """A bracket that did not close within the iteration cap."""


@dataclass(frozen=True, slots=True)
class RootFinder:
    """The scan step and Brent's tolerance and cap, each an engine parameter."""

    step: float
    tolerance: float
    cap: int

    @classmethod
    def of(
        cls, step: EngineParameter, tolerance: EngineParameter, cap: EngineParameter
    ) -> RootFinder:
        if (step.kind, tolerance.kind, cap.kind) != ("scan_step", "tolerance", "iteration_cap"):
            raise ValueError("a root finder takes a scan_step, a tolerance and an iteration_cap")
        if step.unit != "days" or tolerance.unit != "days":
            raise ValueError("the root finder's step and tolerance are in days")
        if cap.value.denominator != 1 or cap.value < 1:
            raise ValueError(f"{cap.key} is a positive integer")
        return cls(float(step.value), float(tolerance.value), int(cap.value))

    def crossings(self, f: Callable[[TT], float], start: TT, end: TT) -> list[tuple[TT, int]]:
        """Every sign change of ``f`` in [start, end): the instant and its direction (+1 rising).

        A change is bracketed between two grid points, the window's own ends
        included as points of the scan; a zero on a grid point counts as a
        change into the sign that follows it.
        """
        base = start.jd_whole
        lo = start.jd_fraction
        hi = (end.jd_whole - base) + end.jd_fraction
        if not hi > lo:
            raise ValueError("a scan window ends after it starts")
        k0, k1 = ceil((base + lo) / self.step), floor((base + hi) / self.step)
        xs = [lo] + [k * self.step - base for k in range(k0, k1 + 1)] + [hi]
        xs = sorted(set(x for x in xs if lo <= x <= hi))

        def g(x: float) -> float:
            return f(TT(base, x))

        out: list[tuple[TT, int]] = []
        xa, fa = xs[0], g(xs[0])
        for xb in xs[1:]:
            fb = g(xb)
            if (fa < 0 <= fb) or (fa >= 0 > fb):
                x = self._brent(g, xa, xb, fa, fb)
                if x < hi:
                    out.append((TT(base, x), 1 if fb >= 0 else -1))
            xa, fa = xb, fb
        return out

    def crossing_after(
        self, g: Callable[[TT], float], after: TT, estimate_days: float, limit_days: float
    ) -> TT:
        """The upward zero of an increasing ``g`` after ``after``, where g(after) < 0.

        The bracket is sought on the absolute grid, from the grid cell that
        holds the estimate outward (right while g < 0, left while g ≥ 0, never
        before ``after``), then refined by Brent's method. A walk of more than
        ``limit_days`` of grid steps from the estimate's cell is an error: the
        limit bounds the walk, not the root's distance from ``after``.
        """
        base = after.jd_whole
        lo = after.jd_fraction

        def h(x: float) -> float:
            return g(TT(base, x))

        f_lo = h(lo)
        if not f_lo < 0:
            raise RootError("crossing_after needs g(after) < 0")
        # the walk counts grid indices: re-deriving the index from x stalls on a grid
        # point when the step is not a binary fraction
        j = floor((base + lo + max(estimate_days, 0.0)) / self.step)
        x = max(j * self.step - base, lo)
        fx = f_lo if x == lo else h(x)
        steps = 0
        cap = ceil(limit_days / self.step) + 1
        a, fa, b, fb = lo, f_lo, x, fx
        if fx < 0:
            while fx < 0:
                a, fa = x, fx
                j += 1
                x = j * self.step - base
                fx = h(x)
                steps += 1
                if steps > cap:
                    raise RootError(f"no crossing within {limit_days} days")
            b, fb = x, fx
        else:
            while fx >= 0:
                b, fb = x, fx
                j -= 1
                x = max(j * self.step - base, lo)
                fx = f_lo if x == lo else h(x)
                steps += 1
                if steps > cap:
                    raise RootError(f"no crossing within {limit_days} days")
            a, fa = x, fx
        return TT(base, self._brent(h, a, b, fa, fb))

    def _brent(
        self, g: Callable[[float], float], a: float, b: float, fa: float, fb: float
    ) -> float:
        """Brent's method on a bracket [a, b] with g(a), g(b) of opposite signs (or g(b) = 0)."""
        if fb == 0:
            return b
        c, fc = a, fa
        d = e = b - a
        tol = self.tolerance / 2
        for _ in range(self.cap):
            if (fb > 0) == (fc > 0):
                c, fc = a, fa
                d = e = b - a
            if abs(fc) < abs(fb):
                a, b, c = b, c, b
                fa, fb, fc = fb, fc, fb
            m = (c - b) / 2
            if abs(m) <= tol or fb == 0:
                return b
            if abs(e) >= tol and abs(fa) > abs(fb):
                s = fb / fa
                if a == c:
                    p, q = 2 * m * s, 1 - s
                else:
                    q, r = fa / fc, fb / fc
                    p = s * (2 * m * q * (q - r) - (b - a) * (r - 1))
                    q = (q - 1) * (r - 1) * (s - 1)
                if p > 0:
                    q = -q
                else:
                    p = -p
                if 2 * p < min(3 * m * q - abs(tol * q), abs(e * q)):
                    e, d = d, p / q
                else:
                    d = e = m
            else:
                d = e = m
            a, fa = b, fb
            b = b + d if abs(d) > tol else b + (tol if m > 0 else -tol)
            fb = g(b)
        raise RootError(f"the bracket did not close in {self.cap} iterations")
