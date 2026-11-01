"""Vondrák, Capitaine and Wallace 2011, Appendix A.5: the authors' test case (vondrak_2011).

The authors evaluate their subroutines at one date and print the poles of
the ecliptic and the equator (``ltp_PECL``, ``ltp_PEQU``) and the matrices
``ltp_PMAT`` and ``ltp_PBMAT`` (fixture ``authority/modern/vondrak_2011_
test_case``; class ``text_computed``). The paper states that double
precision carries 15–16 decimal places and that a comparison must allow
for it: the tolerance is 10⁻¹⁵ on every component.

The engine's datum ``modern.precession.vondrak2011.ecliptic_periodic``
carries the corrigendum's C7 Q_A coefficient as its adopted value, with
Table 1's printed coefficient in ``emendation.printed``. The authors'
test case was computed with the coefficient as printed (the corrigendum
says the listing carried the same error), so this test evaluates the
theory on the printed table, as the Vondrák test case is read. The adopted coefficient moves the
ecliptic pole by about 3·10⁻⁹
at this date (4·10⁻⁹ in the matrices), measured 2026-10-09.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from fractions import Fraction

import numpy as np
import pytest
from authority_kit import printed, records

from jyotirganita.core.exact import parse_fraction
from jyotirganita.core.types import TT
from jyotirganita.modern.precession import Vondrak2011
from jyotirganita.modern.timescales import TimeScales

Recorder = Callable[..., None]

FIXTURE = "authority/modern/vondrak_2011_test_case"
EMENDED = "modern.precession.vondrak2011.ecliptic_periodic"
TOLERANCE = Fraction(1, 10**15)


def _theory_as_printed() -> Vondrak2011:
    data = dict(records().data)
    rec = data[EMENDED]
    table = tuple(tuple(row) for row in rec.raw["emendation"]["printed"])
    data[EMENDED] = dataclasses.replace(rec, value=table)
    return Vondrak2011(data, TimeScales(data))


def _t() -> float:
    """The printed Julian date (TT) in the theory's time argument, by ``TimeScales``."""
    jd = parse_fraction(str(printed(FIXTURE)["input.julian_date"]))
    whole = jd.numerator // jd.denominator
    return TimeScales(records().data).centuries(TT(whole, float(jd - whole)))


def _matrix(name: str) -> np.ndarray:
    rows = printed(FIXTURE)[name]
    return np.array([[float(parse_fraction(str(c))) for c in row] for row in rows])


OUTPUTS: dict[str, Callable[[Vondrak2011, float], np.ndarray]] = {
    "output.p_ecl": lambda v, t: np.atleast_2d(v.ecliptic_pole(t)),
    "output.p_equ": lambda v, t: np.atleast_2d(v.equator_pole(t)),
    "output.r_p": lambda v, t: v.precession(t),
    "output.r_pb": lambda v, t: v.bias_precession(t),
}


@pytest.mark.parametrize("name", sorted(OUTPUTS))
def test_the_authors_test_case_reproduces(name: str, record_comparison: Recorder) -> None:
    computed = OUTPUTS[name](_theory_as_printed(), _t())
    expected = _matrix(name)
    record_comparison(
        fixture=FIXTURE,
        value=name,
        computed=[[f"{x:.17g}" for x in row] for row in computed],
        tolerance=TOLERANCE,
        tolerance_reason=(
            "double precision: the paper states 15–16 decimal places and asks that a "
            "comparison allow for it; Table 1's C7 Q_A as printed"
        ),
    )
    assert computed.shape == expected.shape
    assert float(np.max(np.abs(computed - expected))) <= TOLERANCE
