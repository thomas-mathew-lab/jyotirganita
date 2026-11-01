"""The Dṛk line's Rsines: golasara_1970's recursion against Sarma's example, and
grahanamandana_1965's table.

golasara_1970 III.13b–14a (Nīlakaṇṭha's Golasāra; Sarma's footnote 3 on p. 18,
``editor_computed``): from the radius and the Rsine below it, each Rsine
times twice the last difference divided by the radius, plus the difference
that gave it, is the difference to the Rsine before it (procedure
``trig.rsine_recursion_backward``). Sarma works it in decimals and rounds
each difference to whole minutes, carrying his rounded figures on; each
step is therefore computed here from his printed figures of the step
before, and compared to his whole minutes within one print quantum (he
states neither rounding nor truncation). The Rsine below the radius is the
Rcosine of the first Rsine (golasara_1970's seed note), computed as the day-radius
rule's root of R² − Rsin² (goladipika_1916 v. 73's form; the root's resolution the
engine parameter's) and compared to his one decimal. The residuals are the
editor's arithmetic, not the rule's: the differences 23–22 and 22–21 come
out as Sarma's on rounding to the nearest minute, the difference 21–20 only
on truncation (``docs/methods/drgganita.md`` §I).

The precondition of the adoption of grahanamandana_1965 śl. 25A–B's table is checked in
``tests/invariants/test_drgganita_invariants.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction

import pytest
from authority_kit import printed, records

from jyotirganita.data.engine_parameters import load as load_parameters
from jyotirganita.methods.compose import DAY_RADIUS_RESOLUTION, REPO, load_method
from jyotirganita.siddhantic.epicycle import karna
from jyotirganita.siddhantic.tables import recursion_difference
from jyotirganita.siddhantic.tabular import TableModel

Record = Callable[..., None]
FX = "authority/drgganita/golasara_1970_iii_13_rsine_recursion"
GREAT_SINE = "trig.great_sine.editor_note.grahanamandana_1965"
TWICE = 2  # "twice the last difference" (golasara_1970 III.13b, the rule's own word)
WHOLE_MINUTE = Fraction(1)
WHOLE = "one whole minute: Sarma prints whole minutes and states neither rounding nor truncation"
TENTH = Fraction(1, 20)
DECIMAL = "half of Sarma's one decimal (his rounding to it)"


def _resolution() -> Fraction:
    params = load_parameters(REPO / "jyotirganita" / "data" / "engine_parameters.yaml")
    return Fraction(params[DAY_RADIUS_RESOLUTION].value)


def _model() -> TableModel:
    m = load_method("drgganita", REPO, records=records()).model
    assert isinstance(m, TableModel)
    return m


# --- golasara_1970 III.13b–14a: Sarma's example ---------------------------------------------------


def _steps() -> dict[str, Fraction]:
    fx = printed(FX)
    radius, first = Fraction(fx["input.radius"]), Fraction(fx["input.first_sine"])
    out = {"output.sine_23": karna(radius * radius - first * first, _resolution())}
    out["output.last_difference"] = radius - fx["output.sine_23"]
    out["output.twice_last_difference"] = TWICE * fx["output.last_difference"]
    last = Fraction(fx["output.last_difference"])
    sine, difference = Fraction(fx["output.sine_23_as_used"]), last
    for here, below in (("23", "22"), ("22", "21"), ("21", "20")):
        name = f"output.difference_{here}_{below}"
        out[name] = recursion_difference(sine, last, radius, difference, TWICE)
        difference = Fraction(fx[name])
        out[f"output.sine_{below}"] = sine - difference
        sine = Fraction(fx[f"output.sine_{below}"])
    return out


TOLERANCE = {
    "output.sine_23": (TENTH, DECIMAL),
    "output.last_difference": (Fraction(0), "exact: the radius less the printed Rsine"),
    "output.twice_last_difference": (Fraction(0), "exact: twice the printed difference"),
    "output.difference_23_22": (WHOLE_MINUTE, WHOLE),
    "output.sine_22": (Fraction(0), "exact: the printed Rsine less the printed difference"),
    "output.difference_22_21": (WHOLE_MINUTE, WHOLE),
    "output.sine_21": (Fraction(0), "exact: the printed Rsine less the printed difference"),
    "output.difference_21_20": (WHOLE_MINUTE, WHOLE),
    "output.sine_20": (Fraction(0), "exact: the printed Rsine less the printed difference"),
}


@pytest.mark.parametrize("value", sorted(TOLERANCE))
def test_golasara_1970_recursion_reproduces_sarma_s_example(
    value: str, record_comparison: Record
) -> None:
    computed = _steps()[value]
    tolerance, reason = TOLERANCE[value]
    record_comparison(
        fixture=FX, value=value, computed=computed, tolerance=tolerance, tolerance_reason=reason
    )
    residual = abs(computed - printed(FX)[value])
    # a whole minute bounds a truncation as well as a rounding: strictly inside it
    assert residual < tolerance if tolerance == WHOLE_MINUTE else residual <= tolerance
