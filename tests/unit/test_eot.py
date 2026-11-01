"""The sign and scale of the equation of time (``modern/eot.py``).

E = apparent − mean solar time. Local apparent noon falls midway between
the Sun's rising and setting, and on a clock that keeps local mean time
apparent noon reads 12h − E. So under a modern preset whose standard is
local mean time (``modern_smh`` at Kozhikode), the midpoint of the
record's sunrise and sunset clock readings, less 12h, is −E evaluated at
that midpoint. Both sides come from the same engine, so the test pins
the sign and the unit of E and its argument, not its accuracy.

Tolerance, 30 s: the midpoint of rise and set departs from transit by
half the change of the semidiurnal arc over the day; at latitude 11° the
arc's sensitivity to declination is about tan φ ≈ 0.2 and the
declination changes by at most about 0.4° a day, so the shift is under
about 0.04° of hour angle, some 10 s; the clock readings are written to
the second, and E itself drifts under 30 s a day, evaluated here at the
midpoint. A sign error is several minutes on each day sampled.
"""

from __future__ import annotations

import pytest
from record_kit import DAY, config, record

from jyotirganita.core.types import JDN, UT1
from jyotirganita.modern.eot import equation_of_time

TOLERANCE_S = 30.0


def _seconds(hms: str) -> int:
    h, m, s = (int(x) for x in hms.split(":"))
    return h * 3600 + m * 60 + s


@pytest.mark.parametrize("offset", [0, 60, 150, 250])  # days through the year from DAY
def test_rise_set_midpoint_gives_minus_e(offset: int) -> None:
    cfg = config("modern_smh")
    assert cfg.time_standard == "lmt"
    rec = record(cfg, JDN(DAY.value + offset))
    mid_clock = (_seconds(rec["sunrise"]["local"]) + _seconds(rec["sunset"]["local"])) / 2
    mid_ut1 = (rec["sunrise"]["ut1"] + rec["sunset"]["ut1"]) / 2
    whole = int(mid_ut1)
    e, _ = equation_of_time(cfg.engine, UT1(whole, mid_ut1 - whole))
    minus_e_s = mid_clock - 43200
    assert abs(minus_e_s + e.value * 86400) < TOLERANCE_S
