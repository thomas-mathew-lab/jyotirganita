"""The equation of time from the modern engine, for the derived UT chain.

The equation of time E is apparent solar time less mean solar time. At a
UT1 instant *u*, Greenwich mean solar time counted from midnight is
UT1's own day fraction from midnight (the JD fraction plus half a day);
Greenwich apparent solar time is the hour angle of the true Sun plus
half a day, the hour angle being the Greenwich apparent sidereal time
less the Sun's apparent right ascension in the true equator and equinox
of date (``Frame.gst``, ``Frame.true_equator``, the engine's apparent
place). E is the difference, reduced into [−½, ½) day.

The argument needs TT, hence ΔT: the engine's own model gives it
(``tt_of_ut1`` of ``modern/deltat.py``) and the ΔT used is returned, so
the caller records it. At a fixed UT1 a ΔT error moves the TT of the
Sun's right ascension, not the Earth rotation angle, so the error it
makes in E is the Sun's right-ascension rate (about 4 minutes of time a
day) times that error: about 10 s for a ΔT error of an hour (the earlier text used the slope of
E). It is recorded, not iterated.
"""

from __future__ import annotations

from math import atan2, tau

from jyotirganita.core.types import UT1, FloatDays
from jyotirganita.modern.deltat import tt_of_ut1
from jyotirganita.modern.engine import ModernEngine

__all__ = ["equation_of_time"]


def equation_of_time(engine: ModernEngine, ut1: UT1) -> tuple[FloatDays, float]:
    """E = apparent − mean solar time at ``ut1``, in days, and the ΔT (s) of its argument."""
    tt, delta_t = tt_of_ut1(engine.delta_t, ut1)
    engine.check(tt)
    u = engine.place("sun", tt).direction
    v = engine.frame.true_equator(u, engine.scales.centuries(tt))
    alpha = atan2(float(v[1]), float(v[0]))
    apparent = (engine.frame.gst(ut1, tt) - alpha) / tau + 0.5
    mean = ut1.jd_fraction + 0.5
    e = (apparent - mean + 0.5) % 1 - 0.5
    return FloatDays(e), delta_t
