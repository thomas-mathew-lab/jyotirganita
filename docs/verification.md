# How far each result can be trusted

This page explains what the statuses on the data and the methods
mean, where each method stands in 1.0.0, and what was and was not
checked.

## A value's status

Every constant, table entry, epoch, name and rule statement is a
*datum* in a data file. It records the edition it was read from, the
printed page and the page of the scan, the place on the page, and every
reading made of it, with the reader, the date and the image resolution.

| status | meaning |
|---|---|
| `read` | one reader has read it from the page image |
| `double_read` | a second reader read it again, without seeing the first reading, and the two agree |
| `verified` | it also takes part in a printed worked example the engine reproduces, or agrees with a second printed witness (another edition, a published tabulation, the text's own check rule) |
| `gap` | the source doesn't give it, or the page can't be read. The engine doesn't fill it, and the elements that need it are `not_modelled` |

The data files store `read`, `double_read` or `gap`. `verified` is not
written on a datum (the loader refuses it): it was computed by the
development ledger from the datum's `verified_by` list and the worked
examples the engine reproduces (see the last section).

When two readings disagreed, a third reader looked blind at a tighter
crop of the page. A disagreement it did not settle stays at `read`, and
the datum is marked `disputed`. Some disputed readings had further blind
looks (`further_look`), and for some the author chose among the
recorded readings, shown without their readers' names (reader
`person/…`); such a choice is recorded like a look but is not a blind
re-read. For a value printed in an Indian script (Devanagari,
Malayalam), the two agreeing readers had to be different
models. A value that is a misprint keeps its printed form beside the
adopted value, with the evidence for the change.

## A method's status

A method has one of three grades, computed from its data, its tests and
its reviews: `provisional`, `validated` or `corroborated`. The grades on
this page and in the package's method registry are the ones recorded
for this release: they were computed in the development tree, and this
copy reads them as written and cannot compute them again (see the last
section).

It is **`corroborated`** when all of these hold:

1. every datum it uses is at least `double_read` (or a declared gap),
   and its Indian-script data are signed off by the author;
2. the engine reproduces the worked examples its sources print: exactly,
   for an example worked in the text's own units by its author or a
   pre-modern commentator; to the editor's stated precision, for a
   modern editor's decimal recomputation;
3. every element with no printed worked example rests on (a) a second
   printed witness and (b) at least one comparison with an outside
   computation, such as a printed almanac or an independent program;
4. where a printed almanac computed by the method exists, the engine
   has been compared with it;
5. the work has been reviewed: (a) by a reviewer inside the project,
   and (b) by a reader from outside the model family that made the
   readings, who re-reads a sample of the values blind.

It is **`validated`** when these looser conditions hold:

- **V1.** No open reading among the data the engine uses would change a
  computed number. A reading still at `read` or `disputed` that changes
  only a statement's wording, a witness, or something the engine does
  not compute with, does not hold the method back. The author's
  sign-off of the Indian-script data waits for `corroborated`.
- **V2.** As 2, except that examples of a feature the engine does not
  build (the ascendant, *lagna*) are listed and not counted.
- **V3.** Every datum the engine computes with and no reproduced example
  tests has *either* a second printed witness *or* an outside comparison
  that tests it: a printed almanac (the Basel Mission's Malayalam almanac
  for 1868), a published table (Swamikannu Pillai's *Indian Ephemeris*,
  Nair's 150-year calendar) or an independent program (the Swiss
  Ephemeris, the IAU's ERFA routines, Gislén and Eade's HIC calendar
  program). The comparisons are listed under
  "Outside comparisons" below.
- **V4, V5a.** As 4 and 5a.
- **V5b.** A model from outside the Claude family has reviewed the code
  (an OpenAI model made a partial independent review of selected
  sections of the code in October 2026, which covered every method; it
  re-read no page). **No reader outside the Claude family has checked
  the Devanagari readings.**

Otherwise the method is `provisional`, and every record it produces
carries the flag `provisional_method`. **No method is `corroborated` in
1.0.0.** The table below gives each method's grade and the first
condition of the next grade it does not yet meet, with the counts of
the development ledger run on the release commit.

## The methods in 1.0.0

| method | status | first condition of the next grade not met | runs from (the engine's lower bound) | composed (a day before is flagged, never refused) |
|---|---|---|---|---|
| `aryabhatiya` | validated | 1: 3 data at `read` | JDN 588466 (Julian −3101-02-18), no upper end | Kali 3600 elapsed, JDN 1903398 (Julian 499-03-22) |
| `parahita` | validated | 1: 5 data at `read` | JDN 588466, no upper end | Kali 3785 elapsed, JDN 1970971 (Julian 684-03-23) |
| `drgganita` | provisional | V1: 9 open readings that would change a number | JDN 588466, no upper end | Śaka 1353 elapsed, JDN 2243819 (Julian 1431-03-30) |
| `suryasiddhanta` | validated | 1: 17 data at `read` | JDN 588466, no upper end | 570 CE current, JDN 1929331 (Julian 570-03-22) |
| `suryasiddhanta_paramesvara_recension` | provisional | V3: 2 data with no example, second witness or outside comparison (its own Moon apogee and node revolutions) | JDN 588466, no upper end | as `suryasiddhanta` (the recension's own date is a gap) |
| `modern_de` | validated | 3a: 42 data with no printed example and no second witness | the preset's components' common range (below) | not applicable |

A day record can need instants before or after its own day (its
month's start, its era year's start, the next saṅkrānti), so near a
range's lower bound a calendar day is refused until its month and
year starts lie inside the range: a Kerala record under a siddhantic
preset is refused for the first days after `runs_from`, until a month
start is found.

A modern preset runs over the range its kernel, its ΔT model and its
precession model all state: `modern_iers` from Gregorian 1972-01-01 to
2026-09-08 (the IERS series' cut-off), `modern_smh` from Gregorian
1550-01-01 to 2016-01-01, and `modern_antiquity` (on the DE441 kernel)
from Gregorian −721-12-11 to 2016-01-01. These are the models'
ranges. The days a run serves lie inside them: two days are kept back
at each end for the next day's start and the time standard's offset; a
day whose elements look ahead (a month's end to its next saṅkrānti, for
example) is served only while that look ahead stays in range; and a
day whose era year or month began before the range is refused, so
under the Kerala conventions the first day served is the first day of
the first Kollam year that begins inside the range. Measured at the
three Kerala places for 1.0.0, under each preset's own conventions,
`modern_iers` serves Gregorian 1972-08-16 to 2026-09-01, and
`modern_smh` serves Gregorian 1550-08-11 to 2015-12-29; `modern_antiquity`'s served days
were not measured. A day outside is refused with the range named.

## What 1.0.0 has not checked

- **No outside re-read.** Every reading was made by AI models of a
  single family (Anthropic's Claude), in separate contexts, two models
  where the script was Indian. Readers of the same family can share an
  error, and only a reader from outside the family can measure how
  often they do. Every outside model tried so far failed the Devanagari
  control page, and no outside re-read of the Latin values has been
  made. Criterion 5b is therefore unmet for every method, and no method
  is `corroborated`; the `validated` grade counts an outside model's
  review of the code instead (V5b).
- **Two items checked by no one outside the family:**
  - **The Latin control page** (Sewell and Dīkṣita's *The Indian
    Calendar*, 1896, p. 10), which every reader's accuracy was measured
    against. Its answers rest on Claude reads alone.
  - **A worked weekday example** in Pillai's *Indian Chronology*
    (1911, §240), which reproduces only under an emendation inferred
    from the book's own weekday numbering.
- **Open Indian-script readings.** The readings two readers disagreed
  on and a third look did not settle stay at `read`. A validated
  method may still use such a reading where it changes no computed
  number (V1). Most belong to the Dṛggaṇita, whose sources also print
  no worked example on the engine's path; the Dṛggaṇita stays
  provisional.
- **Author's sign-off** of the Indian-script data, which criterion 1 asks
  for, is still pending.
- **Outside comparisons** (below) are leads, not proofs: each looks at
  a sample, and a comparison with an independent program shows
  agreement, not correctness.

## Outside comparisons

These are not exhaustive studies, only leads: each looks at a sample of years, days or
values. They were done with Claude Opus 5.5 alone: an AI model wrote the scripts, made the
runs and read the printed pages, and no person re-read those pages. The Basel almanacs' values come
from existing transcriptions instead of a page read. They were made outside this package, in a
separate study that runs a tagged version of the engine against printed tables, almanacs and
other programs. Every row was run again on the 1.0.0 code just before release, with the same
results as the earlier runs. They are not tests of this code: none is in the test suite, and no
data value was changed because of one. The study's data and scripts are not part of this package.

| compared with | method | what was compared | result | engine |
| --- | --- | --- | --- | --- |
| Swamikannu Pillai, *An Indian Ephemeris* (1922); 9 years, 706–1790 | Sūrya-siddhānta, Āryabhaṭa, at Laṅkā as Pillai computes | Meṣa saṅkrānti, the first day of Meṣa, 548 tithi and nakṣatra endings | saṅkrānti 18 of 18 within his two decimals of a day; first of Meṣa 9 of 9; endings within ±0.02 day in 329 of the 355 clearly printed values, his mean +0.007 day later. One reader, no second read | 1.0.0 |
| Sewell and Dīkṣita, *The Indian Calendar* (1896), Table I; 71 years, 462–1531 | Sūrya-siddhānta, Āryabhaṭa | added and suppressed months, Meṣa saṅkrānti, the first day of Caitra, weekdays | added and suppressed months 65 of 65; Meṣa saṅkrānti on the same day 71 of 71 (Ārya) and 31 of 31 (SS), the time a constant 18 palas apart; first of Caitra 70 of 71; weekdays 142 of 142. One reader | 1.0.0 |
| HIC, Gislén and Eade's program of Indian calendars (in SEATools, from Lars Gislén's Lund University page) | Sūrya-siddhānta, Āryabhaṭa | 8 mean elements and 7 true positions at 1,000 sunrises, 500–1900; 1,200 saṅkrānti, tithi and nakṣatra ends for each method; 30 years of HIC's own calendar at Kozhikode | mean elements equal (SS) or within 1″ (Ārya); true Sun within 7″, Moon within 15″ (SS) and 32″ (Ārya), planets within 3′; ends within 2.3 min, and 1 of the 2,400 on another day; tithi and nakṣatra of the day agree on all but 1–2 of about 11,500 days at the same instant | 1.0.0 |
| Basel Mission almanac, 1868 (the author's transcription; no page read) | Parahita, which the almanac names | the tithi and nakṣatra at sunrise and their endings, every day of the year; the planets and Rāhu on the first of each month | tithi at sunrise differs on 1 day of 366, nakṣatra on 2; endings a median 1.5 nāḻikā apart; planets and Rāhu within 0.25° in 63 of 72 rows, most within a few arcminutes. The same base without Parahita's correction misses on about a sixth of the days | 1.0.0 |
| Basel Mission almanac, 1874 and 1875, planet tables (Tübingen University's transcription; no page read) | Dṛggaṇita | five planets and Rāhu on the first day of each month, 144 values | **does not reproduce**: 6 of 144 within 5′; Jupiter about 1.5° and Rāhu 2.4° off on every row | 1.0.0 |
| Swiss Ephemeris 2.10.03 | modern | tithi and nakṣatra endings and the Sun's entries, 2022 – August 2026 | within about 1 second of time against its ephemeris files, 5 seconds against its own analytic theory | 1.0.0 |
| ERFA (the IAU's SOFA routines) and the Swiss Ephemeris | modern | ΔT, TDB − TT, the precession model, the Moon's mean node, sunrise and sunset | ΔT within 0.014 s once the year argument is matched; precession matrices to rounding; mean node within 1.6″ back to AD 500; sunrise within 0.03 s without refraction and a constant 1.7 s with the refraction each uses. No outside code holds the Indian Astronomical Ephemeris's refraction for Indian stations; that value is confirmed instead by the Ephemeris's 2021 volume and the Rāṣṭrīya Pañcāṅga of 1959, as printed witnesses | 1.0.0 |
| Manorama and Mathrubhumi calendar apps; Nair's 150-year calendar (2025) | modern | daily tithi and nakṣatra endings, the Sun's entries, sunrise | Manorama within its printed minute for 97 % of 1,174 endings; Nair's endings −7 to +11 minutes off; Mathrubhumi's endings a median 2 to 4 minutes early, 87 to 92 % within 6 minutes of that | 1.0.0 |

## What the tests show, and what they don't

A passing test proves a claim only where its expected value comes from
outside the engine: a printed worked example, a published table, an
independent program, or a redundancy within the source itself. The
regression files under `tests/regression/` only detect changes, and
nothing is claimed from them. A worked example the engine does not
reproduce stays in the suite, marked as not reproduced, with the reason
recorded. It is never deleted or loosened.

## Sources, readers and the development record

Each edition, paper, program and fetched table is named by a short
name of its work and year, such as `aryabhatiya_1976` or
`travancore_panchangam_1921`, listed with its full title, its files
and their SHA-256 in `jyotirganita/data/sources.yaml`. A reading names
its reader by model and date, with a number that tells apart the
separate contexts of one model on one day (for example
`claude-opus-5-5/2026-10-08-r2`); the image resolution and the crop of
the page it was read from are recorded beside it.

The project's development record (its decisions, its issue list and
the reading files of each context) is not part of this repository. A
datum marked `disputed`, a sign-off whose reference is
`development-record`, and a note that cites a `development-record:`
file point to it; ask the maintainer if you need an entry. So the
status counts on this page cannot be rebuilt from this repository
alone: what can be checked here is each datum's recorded readings
(reader, page, crop, resolution), the worked examples the tests
reproduce, and the hashes. The statuses
of the data and the methods, and the date ranges on this page, were
computed there by a tool the code calls *the ledger*; the comments and
data notes also name the development tools that made some files (the
`tools/extract_*.py` scripts that extracted the fetched tables, a
collation script, a seed check). Neither is shipped. An extract records
the URL and SHA-256 of the file it was taken from
(`jyotirganita/data/sources.yaml`), so it can be checked against a
fresh fetch of that file; a derived record is checked here by its
input hashes and its tests. A derived record names the engine version
that computed it and is accepted while the hashes of its inputs match.
In the readers' notes, *the predecessor* is an earlier project whose
readings were never keyed from, and a *frozen* reading is one written to
a file and sealed before it was compared with any other.
