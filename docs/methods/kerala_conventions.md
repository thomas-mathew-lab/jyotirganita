# The Kerala calendar conventions

The `_kerala` and `modern_*` presets run under the Kerala regional
profile (`jyotirganita/regions/kerala/`). It is not a method of its own.
It sets how a method's astronomy becomes a Kerala calendar day, and each
setting cites the statement it rests on.

## The conventions

| part | default | other choices |
|---|---|---|
| civil day | begins at sunrise | |
| assignment of an element to a day | the element current at sunrise | |
| solar month: the day a month begins | `aparahna_parts`, the rule as Sewell and Dīkṣita state it | `following_day`, the practice of the Basel Mission's almanac of 1868; `sunset`, the rule the same book gives for the Tamil and Tinnevelly countries |
| Kali year | begins with the true Sun's entry into Meṣa | the mean Sun's |
| Śaka year | begins at Meṣa | |
| Kollam year | begins at Siṃha | Kanyā |
| ending times | elapsed nāḍikās from sunrise | |

Change a choice with `--set conventions.month_rule=<rule>` or
`--set conventions.era.<era>.year_start=<start>`.

All three month rules are flagged provisional on every record they
touch, each for its own reason: the default rests on Sewell and
Dīkṣita's statement alone; no printed statement of `following_day` is
held, and the 1868 almanac's pages are not yet read twice for it; and
`sunset` is stated for the Tamil country, not for Kerala, with no
printed example to test it. The rules differ in the civil day they
take as a month's first, when the saṅkrānti falls near the boundary
they draw; when they differ, the day of the month differs for the
whole month that follows, and a year's first day can move too
([`../../KNOWN_ISSUES.md`](../../KNOWN_ISSUES.md)).

The names of the months, nakṣatras, yogas, tithis, karaṇas and weekdays
are given in Latin script, and in Malayalam as well when
`output.scripts` asks for it (flagged provisional until signed off).
The Malayalam forms are from the Travancore Government Pañcāṅga; the
Latin forms from Sewell and Dīkṣita and, for the months, the Calendar
Reform Committee's report.

## Places

Kozhikode, Thiruvananthapuram and Thrissur are tabled with their
printed coordinates. Thalassery and Kochi have no printed coordinates
in the held sources, so no method serves them. Any other place can be
given by its coordinates (`kerala/@<lat>,<lon>`), and every record of
such a run is flagged.

## Sources

| id | edition |
|---|---|
| sewell_dikshit_1896 | R. Sewell and Ś. B. Dīkṣita, *The Indian Calendar*, London 1896 |
| calendar_reform_committee_1955 | *Report of the Calendar Reform Committee*, CSIR, New Delhi 1955 |
| travancore_panchangam_1921 | the Travancore Government Pañcāṅga for Kollam year 1097 (1921–22) |
| gopala_varyar_1954 | Gopala Varyar's almanac-maker's manual, 1954 (Malayalam) |

## What is open

- The month rule rests on Sewell and Dīkṣita's statement alone: no
  Malayalam statement of it has been read, and every record flags it.
  The comparison with printed Kerala almanacs is made outside this
  package.
- The sunrise event a Kerala almanac uses under the modern presets, and
  any almanac-specific time standard, are not stated in the held
  sources, so both are recorded as gaps.
- The names have no Devanagari forms.
