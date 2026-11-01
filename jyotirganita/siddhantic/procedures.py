"""The procedure registry.

Every procedure name a text's ``procedures.yaml`` or ``corrections.yaml``
may name (the ``procedure:`` field of a procedure datum)
is an entry here: its **slot** (what it is the rule for), the module and
function that implement it, and a docstring citing the text that defines
it. A text names exactly one procedure per slot it uses; the registry
entry of a method (``methods/registry.yaml``, field ``procedures``) maps
each slot to the datum that states the text's rule.

The conformance suite (``tests/conformance/``) asserts that every name in
every ``procedures.yaml`` and ``corrections.yaml`` resolves here, that
every entry is used by a text or marked ``reserved`` with a reason, and
that every entry has an authority test (a fixture in the datum's
``verified_by``), a declaration ``no_printed_example: {second_witness,
external}`` on its datum, or a ``provisional: pending <reason>`` naming what would key its
examples. The ``diagnostic``
entries (the exact root and the full evaluation) are
no text's procedure and are ``reserved``.

Adding a procedure is one function, one entry here and one authority
test or declared gap; nothing else changes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

__all__ = ["DEFERRABLE", "REGISTRY", "SLOTS", "Procedure", "UnknownProcedure", "resolve"]


class UnknownProcedure(LookupError):
    """A procedure name that is not in the registry, or one used in the wrong slot."""


@dataclass(frozen=True, slots=True)
class Procedure:
    """A registry entry: name, slot, implementation (``module:function``) and citation."""

    name: str
    slot: str
    implementation: str
    doc: str
    reserved: str | None = None


SLOTS: Mapping[str, str] = {
    "ahargana": "the text's ahargaṇa rule from a lunar date",
    "time_base": "the passage between a civil day and the text's day count",
    "weekday": "the weekday from the day count",
    "mean_longitude": "mean positions from the text's rates",
    "mean_precision": "the precision (rounding) of a mean position",
    "epoch_additive": "additives to an element's mean position at the epoch",
    "computation_instant": "the instant at which the text's procedure evaluates positions",
    "sunrise": "the text's sunrise at the observer",
    "carry.desantara": "the carry's longitude correction",
    "carry.bhujantara": "the carry's equation-of-time correction",
    "carry.cara": "the carry's ascensional-difference correction",
    "declination": "the Sun's declination from its longitude",
    "declination.argument": "the longitude the declination rule takes",
    "ascensional_difference": "the ascensional difference (cara) at the observer",
    "half_day": "the half-day from the ascensional difference",
    "gati": "the true daily motion",
    "proportional_parts": "the ending time of an element by proportional parts",
    "intraday": "positions inside the civil day",
    "ending_rounding": "the precision (rounding) of an ending time as the text states it",
    "rsine": "the Rsine from the table, with its interpolation",
    "rversine": "the Rversed-sine from the table, with its interpolation",
    "arc": "the arc from a Rsine (the inverse of the table)",
    "bhuja_koti": "bhujā and koṭi of a kendra by quadrant",
    "pulsation": "the corrected (pulsating) epicycle",
    "manda": "the manda correction",
    "sighra": "the śīghra correction",
    "order.superior": "the application order of the corrections, superior planets",
    "order.inferior": "the application order of the corrections, inferior planets",
    "diagnostic": "a diagnostic procedure, never a text's",
    "layer.step": "how a correction layer accumulates over its count",
    "layer.count_reckoning": "how a correction layer's completed years are reckoned",
    "layer.negative_count": "a correction layer's count before its epoch",
    "sighrocca": "which mean is a planet's own and which its śīghrocca",
    "kendra": "the kendra of a tabulated correction and the correction's sign",
    "table_branch": "which table serves a correction (the manda table; the śīghra branches)",
    "interpolation": "the interpolation of a tabulated correction between its entries",
    "interpolation.last_step": "a table's last step, where no next difference follows",
    "order.luminaries": "the application of the corrections to the Sun and the Moon",
    "node_complement": "the node from the computed mean of Rāhu",
    "deferred": "a step the text defers to earlier works, run as a later package keys it",
    "carry.epoch_advance": "the mean places carried from the computation instant to another "
    "time of the day",
    "order.planets": "the application order of the corrections, the five planets alike",
    "latitude": "a body's latitude from its node and extreme latitude",
}

#: the slots a text may defer to earlier works with ``deferred.earlier_tantras`` (drgganita_1963
#: I.ii.7):
#: the carry, the sunrise and the day's inner time
DEFERRABLE = frozenset(
    {
        "sunrise",
        "carry.desantara",
        "carry.bhujantara",
        "carry.cara",
        "declination",
        "declination.argument",
        "ascensional_difference",
        "half_day",
        "gati",
        "proportional_parts",
        "intraday",
        "ending_rounding",
    }
)

_ENTRIES = (
    Procedure(
        "ahargana.lunar_reckoning",
        "ahargana",
        "jyotirganita.siddhantic.ahargana:lunar_reckoning",
        "laghubhaskariya_1963 I.4–8 (Laghubhāskarīya; Āryabhaṭan rule): Śaka years plus the Kali "
        "offset, months, "
        "intercalary months by the yuga ratio, tithis, omitted days by the yuga ratio. "
        "Sūrya-siddhānta i.48–51: the same steps from the years since the end of creation "
        "(the offset nil).",
    ),
    Procedure(
        "ahargana.civil_days_since_kali_epoch",
        "time_base",
        "jyotirganita.siddhantic.ahargana:ahargana_of_day",
        "laghubhaskariya_1963 I.4–8, Shukla's note: the ahargaṇa counts mean civil days at mean "
        "sunrise at Laṅkā "
        "since the beginning of Kaliyuga; the epoch is the Kali era record.",
    ),
    Procedure(
        "weekday.remainder_from_friday",
        "weekday",
        "jyotirganita.siddhantic.ahargana:weekday_of_ahargana",
        "laghubhaskariya_1963 I.8: the remainder of the ahargaṇa divided by 7 counts the days from "
        "Friday.",
    ),
    Procedure(
        "mean.yuga_rate_successive_division",
        "mean_longitude",
        "jyotirganita.siddhantic.mean:mean_longitude",
        "laghubhaskariya_1963 I.15–17(i): revolutions × ahargaṇa ÷ civil days, the remainders by "
        "successive "
        "division into signs, degrees, minutes and seconds.",
    ),
    Procedure(
        "rounding.truncate_at_vikala",
        "mean_precision",
        "jyotirganita.siddhantic.mean:mean_longitude",
        "laghubhaskariya_1963 I.15–17(i): the mean longitudes 'up to seconds of arc'; successive "
        "division keeps "
        "each quotient, so the longitude is truncated at the vikalā.",
    ),
    Procedure(
        "mean.moon_apogee_node_additive",
        "epoch_additive",
        "jyotirganita.siddhantic.mean:node_from_mean",
        "laghubhaskariya_1963 I.17(ii–iv): three signs added to the Moon's apogee; six to its "
        "node, the result "
        "subtracted from a circle.",
    ),
    Procedure(
        "computation_instant.meridian_mean_sunrise",
        "computation_instant",
        "jyotirganita.siddhantic.engine:SiddhanticEngine",
        "aryabhatiya_1976 vol. 1 Kālakriyā 16 with the editors' note; laghubhaskariya_1963 "
        "I.15–17: positions are computed for "
        "mean sunrise at Laṅkā, on the text's meridian.",
    ),
    Procedure(
        "sunrise.mean_meridian_plus_carry",
        "sunrise",
        "jyotirganita.siddhantic.sunrise:sunrise_after_midnight",
        "laghubhaskariya_1963 I.4–8, Shukla's note (a civil day from one sunrise to the next); "
        "laghubhaskariya_1963 II.4(ii) with "
        "its note and II.19–20: the mean sunrise (15 nāḍikās after local mean midnight) "
        "moved by the bhujāntara (the Sun's bhujāphala ÷ 21600 of a day) and the cara (the "
        "ascensional difference in asus ÷ 21600 of a day, earlier while the day is the longer).",
    ),
    Procedure(
        "carry.desantara_ghati",
        "carry.desantara",
        "jyotirganita.siddhantic.engine:SiddhanticEngine",
        "laghubhaskariya_1963 I.31: the mean daily motion times the longitude in ghaṭīs divided by "
        "60, subtracted "
        "east of the prime meridian and added west; acts on the mean longitude for mean sunrise.",
    ),
    Procedure(
        "carry.bhujantara",
        "carry.bhujantara",
        "jyotirganita.siddhantic.engine:SiddhanticEngine",
        "laghubhaskariya_1963 II.4(ii), II.22; mahabhaskariya_1960 IV.29–30: the mean daily motion "
        "times the Sun's bhujāphala "
        "divided by 21600; for the Sun on the true longitude, for the Moon and the planets on "
        "the mean (each statement's acts_on and applies_to).",
    ),
    Procedure(
        "carry.cara",
        "carry.cara",
        "jyotirganita.siddhantic.engine:SiddhanticEngine",
        "laghubhaskariya_1963 II.19–20, II.23–24; mahabhaskariya_1960 IV.26–27: the daily motion "
        "times the asus of the "
        "ascensional difference divided by 21600, on the true longitude; the true motion for "
        "the Sun and the Moon, the mean for the planets.",
    ),
    Procedure(
        "declination.rsine_obliquity",
        "declination",
        "jyotirganita.siddhantic.sunrise:rsine_declination",
        "laghubhaskariya_1963 II.16; mahabhaskariya_1960 III.6–7: the Rsine of the greatest "
        "declination (1397) times the Rsine of "
        "the bhujā of the Sun's longitude divided by the radius is the Rsine of its declination.",
    ),
    Procedure(
        "declination_argument.svaniraksa_true_longitude",
        "declination.argument",
        "jyotirganita.siddhantic.engine:SiddhanticEngine",
        "mahabhaskariya_1960 IV.25: the Sun's longitude corrected for the deśāntara, the bāhuphala "
        "and the "
        "bhujāntara; the text's own longitude, no ayana correction.",
    ),
    Procedure(
        "ascensional_difference.earthsine",
        "ascensional_difference",
        "jyotirganita.siddhantic.sunrise:ascensional_difference",
        "laghubhaskariya_1963 II.17–18; mahabhaskariya_1960 III.6–7: the day-radius the root of R² "
        "− Rsin²δ; the earthsine "
        "Rsin φ × Rsin δ ÷ Rcos φ; times R ÷ the day-radius, reduced to arc, in asus.",
    ),
    Procedure(
        "half_day.quarter_day_plus_cara",
        "half_day",
        "jyotirganita.siddhantic.sunrise:half_day",
        "mahabhaskariya_1960 IV.28; laghubhaskariya_1963 II.21: half the day is a quarter of the "
        "day and night increased (Sun "
        "north) or diminished (Sun south) by the ascensional difference, for an observer north "
        "of the equator; the signed earthsine reverses it south of it.",
    ),
    Procedure(
        "gati.sunrise_difference",
        "gati",
        "jyotirganita.siddhantic.endings:sunrise_difference",
        "laghubhaskariya_1963 II.15(ii); mahabhaskariya_1960 IV.18: the difference of the true "
        "longitudes for two consecutive "
        "days (computed for sunrise) is the true daily motion.",
    ),
    Procedure(
        "ending.proportional_parts",
        "proportional_parts",
        "jyotirganita.siddhantic.endings:proportional_parts",
        "laghubhaskariya_1963 II.25–28; mahabhaskariya_1960 IV.31–34: the portion to be traversed "
        "times 60 divided by the "
        "daily motion (Moon less Sun for tithi and karaṇa, the Moon's for nakṣatra) gives the "
        "ghaṭīs to elapse after sunrise.",
    ),
    Procedure(
        "intraday.linear_gati",
        "intraday",
        "jyotirganita.siddhantic.endings:chord",
        "laghubhaskariya_1963 II.25–26(i), the proportional-parts rule's own assumption: a "
        "position n nāḍikās "
        "after sunrise is the sunrise position plus n/60 of the day's gati, on [0, 60) "
        ".",
    ),
    Procedure(
        "rounding.ending_truncate_at_asu",
        "ending_rounding",
        "jyotirganita.siddhantic.endings:truncate_at_asu",
        "mahabhaskariya_1960 IV.31–32: the ending is obtained in ghaṭīs, vighaṭīs and asus by "
        "successive "
        "division, each quotient kept.",
    ),
    Procedure(
        "diagnostic.root_bisection",
        "diagnostic",
        "jyotirganita.siddhantic.endings:root_bisection",
        "the exact-root ending, bisection in exact arithmetic to "
        "siddhantic.root_resolution on the full evaluation; a diagnostic.",
        reserved="a diagnostic that no text states",
    ),
    Procedure(
        "diagnostic.full_evaluation",
        "diagnostic",
        "jyotirganita.siddhantic.engine:SiddhanticEngine",
        "the text's full procedure evaluated at a fractional day (the mean "
        "elements advanced at mean motion before the equations, the carry as at sunrise); a "
        "diagnostic paired with the root.",
        reserved="a diagnostic that no text states",
    ),
    Procedure(
        "trig.rsine_table_linear",
        "rsine",
        "jyotirganita.siddhantic.tables:RsineTable.rsine",
        "laghubhaskariya_1963 II.2(ii)–3(i); mahabhaskariya_1960 IV.3–4(i): the sum of the "
        "differences and the remainder times "
        "the current difference divided by 225.",
    ),
    Procedure(
        "trig.rversine_table_linear",
        "rversine",
        "jyotirganita.siddhantic.tables:RsineTable.rversine",
        "mahabhaskariya_1960 IV.3–4(i) with Shukla's note: the table of Rsine-differences "
        "reversed.",
    ),
    Procedure(
        "trig.arc_table_linear",
        "arc",
        "jyotirganita.siddhantic.tables:RsineTable.arc",
        "mahabhaskariya_1960 VIII.6: the differences subtracted in order, the residue times 225 "
        "divided by the "
        "current difference.",
    ),
    Procedure(
        "epicycle.bhuja_koti",
        "bhuja_koti",
        "jyotirganita.siddhantic.epicycle:bhuja_koti",
        "laghubhaskariya_1963 II.1–2(i): three signs a quadrant; in an odd quadrant the arc "
        "traversed is the "
        "bhujā, in an even quadrant the arc to be traversed. Sūrya-siddhānta ii.29–30: the "
        "same, the kendra the apsis or the conjunction less the planet.",
    ),
    Procedure(
        "epicycle.pulsating",
        "pulsation",
        "jyotirganita.siddhantic.epicycle:corrected_epicycle",
        "laghubhaskariya_1963 II.31–32; mahabhaskariya_1960 IV.38–39(i): the epicycle at the "
        "beginning of the current quadrant "
        "corrected by the Rsine (odd) or Rversed-sine (even) of the part of the kendra in it.",
    ),
    Procedure(
        "epicycle.manda_bhujaphala",
        "manda",
        "jyotirganita.siddhantic.epicycle:manda_correction",
        "laghubhaskariya_1963 II.3(ii)–4(i): Rsine of the bhujā times the epicycle divided by 80, "
        "subtractive in "
        "the half-orbit from Aries; for the planets reduced to arc (laghubhaskariya_1963 "
        "II.33–37).",
    ),
    Procedure(
        "epicycle.sighra_karna",
        "sighra",
        "jyotirganita.siddhantic.epicycle:sighra_correction",
        "laghubhaskariya_1963 II.33–37(i) with Shukla's note: the bāhuphala times the radius "
        "divided by the "
        "śīghrakarṇa, reduced to arc; the karṇa's root truncated at an engine parameter "
        "(no rule stated).",
    ),
    Procedure(
        "order.superior_four_step",
        "order.superior",
        "jyotirganita.siddhantic.engine:SiddhanticEngine",
        "laghubhaskariya_1963 II.33–37(i): half the manda, half the śīghra, the whole manda on the "
        "mean planet "
        "(the true-mean planet), the whole śīghra on that.",
    ),
    Procedure(
        "order.inferior_three_step",
        "order.inferior",
        "jyotirganita.siddhantic.engine:SiddhanticEngine",
        "laghubhaskariya_1963 II.37(ii)–39: half the śīghra on the mandocca (reverse sign), the "
        "whole manda from "
        "the corrected mandocca on the mean planet, the whole śīghra on that.",
    ),
    Procedure(
        "layer.step_per_completed_year",
        "layer.step",
        "jyotirganita.siddhantic.corrections:Layer",
        "grahacaranibandhana_1954 p. x: the rate for every completed year after the layer's epoch "
        "(a step function).",
    ),
    Procedure(
        "layer.count_by_mean_mesha",
        "layer.count_reckoning",
        "jyotirganita.siddhantic.corrections:Layer",
        "No stated rule (basis fallback_no_stated_rule): the completed years are reckoned at the "
        "mean Meṣa saṅkrānti of the base text's mean Sun.",
    ),
    Procedure(
        "layer.negative_count_floor",
        "layer.negative_count",
        "jyotirganita.siddhantic.corrections:Layer",
        "No stated rule (basis fallback_no_stated_rule): before the epoch the "
        "count is the floor of the elapsed years, the year before the epoch counting −1.",
    ),
)

_ENTRIES_DRGGANITA = (
    Procedure(
        "ahargana.kali_dinagana",
        "time_base",
        "jyotirganita.siddhantic.ahargana:ahargana_of_day",
        "drgganita_1963 II.11 (Dṛggaṇita): 'having set down the day count of Kali' (kaler "
        "dinagaṇaṃ "
        "nyasya): civil days since the Kali epoch, the Kali era record.",
    ),
    Procedure(
        "mean.guna_hara_drift",
        "mean_longitude",
        "jyotirganita.siddhantic.tabular:mean_longitude_rational",
        "drgganita_1963 II.11–12a with II.2–10: the day count times the guṇakāra divided by the "
        "hāraka "
        "gives revolutions and the rest; the drift stated per element (one liptā, viliptā or "
        "kalā in so many days, added or subtracted) is applied as a constant rate.",
    ),
    Procedure(
        "mean.dhruva_signed",
        "epoch_additive",
        "jyotirganita.siddhantic.tabular:mean_longitude_rational",
        "drgganita_1963 II.12a ('kuryān nijadhruvam') with II.12b–15a: each element's dhruva, "
        "added or "
        "subtracted as the verse states, after the drift.",
    ),
    Procedure(
        "computation_instant.dhruva_sunrise",
        "computation_instant",
        "jyotirganita.siddhantic.tabular:TableEngine",
        "drgganita_1963 I.ii.6: the means with these dhruvas are for sunrise (udayāvadhikāḥ); on "
        "the "
        "text's meridian at the equator the carry the text defers (I.ii.7) is nil.",
    ),
    Procedure(
        "sighrocca.sun_mean_or_own",
        "sighrocca",
        "jyotirganita.siddhantic.tabular:TableModel",
        "drgganita_1963 II.18: the mean Sun is the śīghrocca of Mars, Saturn and Jupiter; of Venus "
        "and "
        "Mercury the own mean is the śīghrocca and the mean is the Sun's.",
    ),
    Procedure(
        "table.kendra_body_less_ucca",
        "kendra",
        "jyotirganita.siddhantic.tabular:TableModel.phala",
        "drgganita_1963 II.19: the body less its ucca is the kendra; in the six signs from Meṣa "
        "the "
        "doḥjyāphala is subtracted, from Tulā added; so for the manda and the śīghra.",
    ),
    Procedure(
        "table.manda_one_sighra_two",
        "table_branch",
        "jyotirganita.siddhantic.tabular:TableModel.phala",
        "drgganita_1963 II.25: one table for the manda; for Mars and the others two for the "
        "śīghra, by "
        "the kendra's beginning from Makara (mṛgādi) or from Karka (karkyādi); each at the "
        "bhujā of the kendra.",
    ),
    Procedure(
        "table.second_difference",
        "interpolation",
        "jyotirganita.siddhantic.tabular:JyaTable.value",
        "drgganita_1963 II.44–45 with the editor's note: the product of the kalās gone and to go "
        "in the "
        "step, each divided by bhadra, times the next difference less the current, divided by "
        "nirmogha, taken from the linear interpolation (subtracted where the next difference "
        "is greater).",
    ),
    Procedure(
        "table.last_step_preceding_difference",
        "interpolation.last_step",
        "jyotirganita.siddhantic.tabular:JyaTable.value",
        "No stated rule (basis fallback_no_stated_rule): in the last step of a table, which has "
        "no next difference, the second difference is the preceding pair's.",
    ),
    Procedure(
        "order.manda_only",
        "order.luminaries",
        "jyotirganita.siddhantic.tabular:TableModel.true",
        "drgganita_1963 II.43a: the mean corrected by the manda jyā is true for the Moon and the "
        "Sun. "
        "Sūrya-siddhānta ii.43: the process for the apsis is the only one for the Sun and the "
        "Moon (jyotirganita.siddhantic.surya:SuryaModel.processes).",
    ),
    Procedure(
        "order.superior_drgganita",
        "order.superior",
        "jyotirganita.siddhantic.tabular:TableModel.true",
        "drgganita_1963 II.20–21: half the manda on the mean, half the śīghra on that, the whole "
        "manda "
        "from that on the mean, the whole śīghra from that on the manda-corrected mean; for "
        "Mars, Saturn and Jupiter.",
    ),
    Procedure(
        "order.inferior_drgganita",
        "order.inferior",
        "jyotirganita.siddhantic.tabular:TableModel.true",
        "drgganita_1963 II.22–24: half the śīghra on the mean, from that half the manda on the "
        "mean, "
        "from that the whole śīghra on the mere mean, from that the whole manda on the "
        "śīghra-corrected one; for Mercury and Venus.",
    ),
    Procedure(
        "node.complement_once",
        "node_complement",
        "jyotirganita.siddhantic.tabular:TableEngine",
        "drgganita_1963 II.43b: Rāhu subtracted from a circle is the true node, since it always "
        "moves "
        "backward; applied once, to the output node.",
    ),
    Procedure(
        "deferred.earlier_tantras",
        "deferred",
        "jyotirganita.siddhantic.tabular:TableEngine",
        "drgganita_1963 I.ii.7: the deśāntara and the rest are to be known from earlier works; run "
        "at the "
        "text's meridian on the equator only, where the carry is nil.",
        reserved="no slot names it since the Dṛggaṇita's deferred slots were filled "
        "from the Dṛk-school pages; kept for a text that defers",
    ),
)

_ENTRIES_SURYA = (
    Procedure(
        "ahargana.civil_days_since_creation",
        "time_base",
        "jyotirganita.siddhantic.surya:SuryaEngine",
        "Sūrya-siddhānta i.48–51 (suryasiddhanta_burgess_1860; suryasiddhanta_hall_1859 the "
        "witness): the sum of days is the civil days since "
        "the end of creation at midnight on the meridian of Laṅkā; placed on the Kali era record "
        " by the days to the Kali epoch from i.45–47 and the ages' shares (i.17).",
    ),
    Procedure(
        "weekday.remainder_from_sunday",
        "weekday",
        "jyotirganita.siddhantic.ahargana:weekday_of_ahargana",
        "Sūrya-siddhānta i.51: the sum of days divided by seven, the remainder marks the lord of "
        "the day beginning with the Sun.",
    ),
    Procedure(
        "mean.revolutions_from_creation",
        "mean_longitude",
        "jyotirganita.siddhantic.surya:mean_remainder",
        "Sūrya-siddhānta i.53–54: the sum of days times the revolutions divided by the civil days "
        "(of a mahāyuga, i.29–34; of a kalpa for the apsides and nodes, i.41–44) gives the "
        "revolutions and parts; a node's place is the result subtracted from a whole circle.",
    ),
    Procedure(
        "computation_instant.lanka_midnight",
        "computation_instant",
        "jyotirganita.siddhantic.surya:SuryaEngine",
        "Sūrya-siddhānta i.50–51: the sum of days is 'at midnight, on the meridian of Laṅkā'.",
    ),
    Procedure(
        "carry.epoch_advance_mean",
        "carry.epoch_advance",
        "jyotirganita.siddhantic.surya:SuryaEngine",
        "Sūrya-siddhānta i.67: the mean daily motion times the nāḍīs of the time fixed upon, "
        "divided by sixty, added after midnight and subtracted before it; acts on the mean "
        "place (epoch_advance).",
    ),
    Procedure(
        "trig.sine_table_linear",
        "rsine",
        "jyotirganita.siddhantic.surya:SineTable.rsine",
        "Sūrya-siddhānta ii.31–32: the minutes of the arc divided by the step give the preceding "
        "tabular sine; the remainder times the difference of the preceding and following "
        "tabular sines, divided by the step, added to the preceding.",
    ),
    Procedure(
        "trig.arc_from_sine_table",
        "arc",
        "jyotirganita.siddhantic.surya:SineTable.arc",
        "Sūrya-siddhānta ii.33: the given sine less the next less tabular sine, times the step, "
        "divided by the difference of the next less and next greater, added to the step times "
        "the serial number of the next less.",
    ),
    Procedure(
        "epicycle.base_sine_variation",
        "pulsation",
        "jyotirganita.siddhantic.surya:corrected_epicycle",
        "Sūrya-siddhānta ii.38: the base-sine times the difference of the odd and even "
        "epicycles, divided by the radius, applied to the even epicycle, additive when that is "
        "the less, subtractive when the greater.",
    ),
    Procedure(
        "epicycle.manda_arc",
        "manda",
        "jyotirganita.siddhantic.surya:manda_equation",
        "Sūrya-siddhānta ii.29–30, ii.39, ii.45: the anomaly is the apsis less the planet; the "
        "base-sine times the corrected epicycle divided by the degrees of a circle, its arc the "
        "equation in minutes; additive while the anomaly lies in the half-orbit from Aries.",
    ),
    Procedure(
        "epicycle.sighra_variable_hypotenuse",
        "sighra",
        "jyotirganita.siddhantic.surya:sighra_equation",
        "Sūrya-siddhānta ii.40–42, ii.45: the perpendicular-result added to the radius in the "
        "half-orbit from Capricorn, subtracted in that from Cancer; the variable hypotenuse the "
        "root of its square plus the base-result's (truncated at the engine parameter "
        "siddhantic.karna_root_resolution, no precision stated); the arc of the base-result times "
        "the radius divided by the hypotenuse the equation; additive in the half from Aries.",
    ),
    Procedure(
        "order.four_processes",
        "order.planets",
        "jyotirganita.siddhantic.surya:SuryaModel.processes",
        "Sūrya-siddhānta ii.43–44: for the five planets, half the equation of the conjunction on "
        "the mean, half that of the apsis on that, the whole equation of the apsis on the mean, "
        "the whole equation of the conjunction on that; each equation from the place last found.",
    ),
    Procedure(
        "latitude.node_hypotenuse",
        "latitude",
        "jyotirganita.siddhantic.surya:SuryaModel.latitude",
        "Sūrya-siddhānta ii.56–57 with i.68–70: the node of Mars, Jupiter and Saturn takes the "
        "planet's equation of the conjunction, of Mercury and Venus the third process's equation "
        "of the apsis reversed; the sine of the planet (Mercury, Venus: the conjunction) less "
        "the node, times the extreme latitude, divided by the last hypotenuse (the Moon: by the "
        "radius) is the latitude.",
    ),
    Procedure(
        "deferred.pending_keying",
        "deferred",
        "jyotirganita.siddhantic.surya:SuryaEngine",
        "Sūrya-siddhānta i.60–61, ii.46, ii.61–63: the deśāntara, the bhujāntara, the cara and "
        "the day are stated by the text; run at the text's meridian on the equator only, "
        "where the cara and the deśāntara are nil.",
        reserved="no slot names it since the Sūrya-siddhānta's carry, "
        "sunrise and endings are keyed; kept for a text "
        "that defers",
    ),
)

#: the Dṛk line's carry, latitude and Rsine rule
_ENTRIES_DRK_CARRY = (
    Procedure(
        "carry.desantara_yojana",
        "carry.desantara",
        "jyotirganita.siddhantic.tabular:TableEngine",
        "goladipika_1916 v. 196–198 (Goladīpikā; grahanamandana_1965 śl. 13a–14a the second "
        "witness): the daily motion times "
        "the yojanas between the samarekhā and the place, divided by the place's own circle of "
        "the Earth, added west of the line and subtracted east; on every mean element at mean "
        "motion (a shift of the time of the means; grahanamandana_1965 śl. 22b: the node's "
        "reversed).",
    ),
    Procedure(
        "carry.bhujantara_mean_elements",
        "carry.bhujantara",
        "jyotirganita.siddhantic.tabular:TableEngine",
        "goladipika_1916 v. 202–203 (grahanamandana_1965 śl. 16–17 the second witness): the Sun's "
        "doḥphala in minutes times "
        "the planet's daily motion divided by the minutes of a circle, with the doḥphala's sign; "
        "the true Sun rises before the mean while it is negative; on every mean element at mean "
        "motion.",
    ),
    Procedure(
        "carry.cara_mean_elements",
        "carry.cara",
        "jyotirganita.siddhantic.tabular:TableEngine",
        "goladipika_1916 v. 205–207 (grahanamandana_1965 śl. 20–21 the second witness): the daily "
        "motion times the asus of "
        "the Sun's carārdha divided by the asus of a day, subtracted at sunrise while the Sun is "
        "in the northern hemisphere and added in the southern, the reverse at sunset; on every "
        "mean element at mean motion. goladipika_1916 v. 208's divisor (the day's asus increased "
        "by the "
        "Sun's motion) is recorded as others' and not run.",
    ),
    Procedure(
        "latitude.great_sine_moon",
        "latitude",
        "jyotirganita.siddhantic.tabular:TableEngine",
        "grahanamandana_1965 śl. 37–38: the Great Sine of the Moon less the node, times the "
        "multiplier and "
        "divided by the divisor the verse states, is the Moon's latitude in minutes, north while "
        "Moon less node lies in the six signs from Meṣa; the planets' latitudes are not modelled "
        "(goladipika_1916 v. 127–128 divide by hypotenuses the Dṛggaṇita's tables do not give).",
    ),
    Procedure(
        "trig.rsine_recursion_backward",
        "rsine",
        "jyotirganita.siddhantic.tables:rsines_by_recursion",
        "golasara_1970 III.13b–14a (Nīlakaṇṭha's Golasāra) with Sarma's note: from the radius and "
        "the "
        "Rsine below it (the Rcosine of the first Rsine), each Rsine times twice the last "
        "difference divided by the radius, plus the difference that gave it, is the difference "
        "to the previous Rsine. A cross-check of the table the Dṛk line runs on, never its "
        "table.",
    ),
)

#: the Sūrya-siddhānta's sunrise, carry, cara and gati (docs/methods/
#: suryasiddhanta.md §J)
_ENTRIES_SURYA_DAY = (
    Procedure(
        "sunrise.surya_quarter_day_less_cara",
        "sunrise",
        "jyotirganita.siddhantic.surya:SuryaEngine",
        "Sūrya-siddhānta xiv.18–19 (the civil day from rising to rising; the mean motions by "
        "civil time) with ii.61–63: the sunrise after the observer's midnight is half the night, "
        "a quarter of the day and night less the ascensional difference while the declination "
        "is north (more while south); the sunset is the sunrise plus twice the half-day. The "
        "bhujāntara corrects the place (ii.46), not the time.",
    ),
    Procedure(
        "carry.desantara_corrected_circumference",
        "carry.desantara",
        "jyotirganita.siddhantic.surya:SuryaEngine",
        "Sūrya-siddhānta i.60–61 with i.63–65: the daily motion times the yojanas from the prime "
        "meridian divided by the place's corrected circumference, in minutes, subtracted east "
        "and added west, on every mean element at mean motion; the yojanas are the nāḍīs of "
        "the longitude difference times that circumference over sixty (i.64–65), so the scale "
        "cancels and the carry is the offset's sixtieth of a day.",
    ),
    Procedure(
        "carry.bhujantara_true_place",
        "carry.bhujantara",
        "jyotirganita.siddhantic.surya:SuryaEngine",
        "Sūrya-siddhānta ii.46: the planet's daily motion times the Sun's result from the "
        "base-sine divided by the minutes of a circle, applied to the planet's true place in "
        "the direction the Sun's equation was applied; the daily motion is the true motion of "
        "ii.47–51 (gati.equation_of_motion).",
    ),
    Procedure(
        "carry.cara_sunrise_mean_elements",
        "carry.cara",
        "jyotirganita.siddhantic.surya:SuryaEngine",
        "Composed of two stated rules, applied by none: the ascensional difference moves the "
        "sunrise (ii.61–63), and the places "
        "at that instant are the means carried to it at mean motion (i.67; xiv.19), before the "
        "equations; no verse applies the cara to a place (texts.suryasiddhanta.procedures."
        "cara.application).",
    ),
    Procedure(
        "declination_argument.ayana_corrected_true_longitude",
        "declination.argument",
        "jyotirganita.siddhantic.surya:SuryaModel.ayana",
        "Sūrya-siddhānta iii.9–10: the sum of days times the libration's revolutions in an Age, "
        "divided by the civil days of an Age; the bhujā of the part of a revolution, times the "
        "multiplier and divided by the divisor iii.10 states, is the precession in degrees; the "
        "Sun's true longitude corrected by it gives the declination and the ascensional "
        "difference. The sign is not stated as read: additive in the half-revolution from 180° "
        "(suryasiddhanta_burgess_1860's worked example), subtractive in the other.",
    ),
    Procedure(
        "ascensional_difference.palabha_versine",
        "ascensional_difference",
        "jyotirganita.siddhantic.surya:ascensional_difference_surya",
        "Sūrya-siddhānta ii.60–62 with iii.17b: the day-radius is the radius less the versed "
        "sine of the declination; the earth-sine the sine of declination times the equinoctial "
        "shadow divided by the gnomon of twelve; the sine of the ascensional difference the "
        "earth-sine times the radius divided by the day-radius, its arc the respirations.",
    ),
    Procedure(
        "gati.equation_of_motion",
        "gati",
        "jyotirganita.siddhantic.surya:SuryaModel.gati",
        "Sūrya-siddhānta ii.47–51: the daily motion (the Moon's less its apsis's) times the "
        "difference of tabular sines at the base-sine of the anomaly, divided by the step, "
        "times the corrected epicycle of the apsis, divided by the degrees of a circle, in "
        "minutes, additive in the half-orbit from Cancer; for a planet, the conjunction's "
        "motion less that, times the last hypotenuse less the radius, divided by the hypotenuse, "
        "added (negative when the hypotenuse is the less; retrograde when the result is).",
    ),
)

REGISTRY: Mapping[str, Procedure] = {
    p.name: p
    for p in (
        *_ENTRIES,
        *_ENTRIES_DRGGANITA,
        *_ENTRIES_SURYA,
        *_ENTRIES_DRK_CARRY,
        *_ENTRIES_SURYA_DAY,
    )
}


def resolve(name: str, slot: str | None = None) -> Procedure:
    """The registry entry ``name``; with ``slot``, it must be registered for that slot."""
    p = REGISTRY.get(name)
    if p is None:
        raise UnknownProcedure(f"procedure {name!r} is not in the registry")
    if slot is not None and p.slot == "deferred" and slot in DEFERRABLE:
        return p
    if slot is not None and p.slot != slot:
        raise UnknownProcedure(f"procedure {name!r} is registered for {p.slot!r}, not {slot!r}")
    return p
