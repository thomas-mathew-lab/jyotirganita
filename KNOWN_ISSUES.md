# Known issues

What version 1.0.0 does not yet do, and where its results rest on
thinner evidence than the rest. Each entry says what it affects and what
would settle it. A record names these itself: its method's status, and
in its `flags` every provisional datum or convention behind it.
[`docs/verification.md`](docs/verification.md) gives each method's
grade and the first condition it does not yet meet.

To report a problem, open an issue at
<https://github.com/thomas-mathew-lab/jyotirganita/issues>, with the
command or call and the record's `provenance` block.

## Methods

- **`drgganita` is provisional.** Its sources print no worked example
  on the engine's path, and it holds the most readings that two readers
  disagreed on and a third look did not settle, nearly all Devanagari
  verse and table entries; some of them would change a computed number.
  Parts of it are taken by design from the works the text defers to,
  and the last step of its second-difference interpolation uses a
  fallback. *Affects:* every `drgganita_kerala` record, each flagged
  `provisional_method`. *Would settle it:* a reader of Devanagari for
  the disputed readings, and a worked example or a published table
  computed by the method.
- **`suryasiddhanta_paramesvara_recension` is provisional.** It differs
  from `suryasiddhanta` only in two numbers, the revolutions of the
  Moon's apogee and node, read from one edition. No worked example
  separates the two recensions, and no second printing has been read.
  *Affects:* the Moon's and its node's results under this method: the
  Moon's true longitude and latitude, Rāhu and Ketu, and so the tithi,
  karaṇa, nakṣatra and yoga that depend on them. The list is not
  exhaustive: anything computed from the Moon or its node can move.
  *Would settle it:* a second witness of the two numbers, or a worked
  example that tells the recensions apart.
- **Open readings in the validated methods.** `aryabhatiya`,
  `parahita` and `suryasiddhanta` each keep a few readings at `read`,
  marked `disputed` in the data files. None of them changes a computed
  number (that is a condition of the `validated` grade); they are
  wordings of statements and witnesses, or figures whose open question
  cannot change the value used.
- **Many flags on a validated method's records.** A procedure that no
  printed worked example tests carries a `provisional:<key>` flag on
  every record it touches until an outside comparison is named on that
  procedure's datum. The `validated` grade counts the comparisons made
  for the method as a whole (for `parahita`, the Basel Mission almanac
  of 1868), so a validated record can list dozens of them. Method-level
  comparisons and second witnesses do not test every procedure on its
  own; these flags mark that remaining limitation. They are not
  evidence that a result is wrong, and they do not show it is right.

## The readings

- **No reader outside the Claude family.** Every value was read by AI
  models of one family (Anthropic's Claude), in separate contexts and,
  for the Indian scripts, by two different models. For some disputed
  readings the author chose among the recorded readings, shown without
  their readers' names (`further_look`, reader `person/…`); those
  choices are not a blind re-read. Readers of one
  family can share an error, and only an outside reader can measure how
  often they do. Every outside model tried failed the Devanagari
  control page, and no outside re-read of the Latin values has been
  made. *Would settle it:* a human or outside reader re-reading a
  sample blind. This is what keeps every method below `corroborated`.
- **The Indian-script data await the author's sign-off**, which the
  `corroborated` grade asks for; six readings that decide a procedure or
  an emendation are signed off one by one. The Malayalam names are printed only
  when asked for (`output.scripts`), and those records carry a
  provisional flag until the names are signed off. They are spelled as
  the Travancore Government Pañcāṅga of 1921–22 prints them, which may
  differ from today's spelling.
- **Two readings a stricter standard would want checked first:** the Latin control
  page every reader was measured against (Sewell and Dīkṣita, *The
  Indian Calendar*, p. 10), and one worked example in Swamikannu
  Pillai's *Indian Chronology* (1911, §240), which finds the weekday of
  a date step by step. The engine reaches his answer only if one figure
  in his working is taken as a misprint and corrected; the correction
  is inferred from the book's own numbering of the weekdays, and no
  second printing confirms it.

## Faults found before release, still open

The reviews of the release code found these; the other faults they
found are fixed in 1.0.0. Each is small in effect.

- **The modern sunset's last second.** A modern record's
  `sunset.local` is its sunrise, rounded to the second, plus the time
  from sunrise to sunset, rounded again; on about a quarter of the days
  it is one second from the sunset's own instant rounded once (its `tt`
  field, the computed instant in double precision, is not affected).
  The same construction prints the sunset one second late on a
  leap-second day at a place whose sunrise comes before the
  leap second (05:29:60 IST): a place given by its coordinates east of
  Kerala under `modern_iers`, on the 1 July leap-second days (eleven
  since 1972); never at a Kerala place. *Affects:* the printed sunset of
  the modern presets, by one second from either cause (whether the two
  can add on one day has not been measured). The sunrise is already
  read on the clock; the sunset is not.
- **What a sign-off fingerprints.** The author's sign-off of a datum
  records a hash of its value, adopted emendation and word, not of its
  other fields (its sign, form or unit), so a change to those would not
  void the sign-off. Six sign-offs are held in 1.0.0, four on data and
  two on emendations.

## Kerala conventions

- **The day a solar month begins.** All three month rules are flagged
  provisional, each for its own reason:
  - `aparahna_parts`, the default: one printed statement of it is held,
    Sewell and Dīkṣita's description of the practice, and no second
    source states it.
  - `following_day`: the Basel Mission's Malayalam almanac of 1868
    begins every month on the day after the saṅkrānti, but no printed
    statement of the rule is held, and those almanac pages are not yet
    read twice for it.
  - `sunset`: Sewell and Dīkṣita give it for the Tamil and Tinnevelly
    countries, not for Kerala, and no printed example tests it.

  *Affects:* the day taken as the first of a solar month, when the
  saṅkrānti falls near the boundary the rule draws. A start one day
  apart changes the month named on that day and moves the numbered day
  of the month, and so the Kollam date, for the whole of the month that
  follows; where a year begins with that month, it moves the year's
  first day too. *Would settle it:* a second printed statement, and the
  1868 month headings read twice.
- **The day's nakṣatra.** Each element is named as it stands at
  sunrise, the rule Sewell and Dīkṣita state. A Kerala practice of
  naming the day by the nakṣatra that runs for some nāḻikas after
  sunrise is reported, but no printed statement of it has been found,
  so it is not modelled.
- **Ending times.** How the 1921–22 Travancore pañcāṅga writes its
  ending times (elapsed nāḍikās from sunrise) rests on a reading that
  is still open.
- **Places.** Kozhikode, Thiruvananthapuram and Thrissur use printed
  modern coordinates, with an editor's modern longitude for Ujjain; no
  text states a Kerala place in its own units. Two editors' longitudes
  for Ujjain differ, which moves every Kerala place's offset by about
  4.4 vināḍikās; the one used is recorded on the data. Thalassery and
  Kochi have no printed coordinates and are not served; any place can
  be given by its coordinates, and such records are flagged
  `user_place`.

## Questions of interpretation

The texts leave a few points open that change computed numbers. The
engine follows one reading, named in the code and on the data, and the
question stays recorded:

- which end of the quadrant the stated manda epicycles belong to, under
  the Āryabhaṭan methods;
- whether the Āryabhaṭan bhujāntara also moves the śīghroccas of the
  planets;
- whether the Sūrya-siddhānta's latitude is taken from the place before
  or after its bhujāntara.

## The modern engine

- **Last digits across computers.** The text methods compute in exact
  arithmetic, so their computed fields are the same on any computer
  (every record also carries an `environment` block naming the computer,
  which differs). The modern engine
  computes in double-precision floating point. On one machine with the
  pinned versions it gives the same bytes every time. Between computers,
  the last digits of its Julian dates and planetary positions can
  differ, far below the accuracy of the models; its calendar times are
  rounded to the second, so they could differ only when a time falls
  within a hair of a second's boundary. The size of such differences
  has not been measured.
- **Eclipses** are computed by the modern presets only, and every
  eclipse result is flagged `provisional:eclipse`: no comparison with a
  published eclipse canon has been made.
- **Gaps.** The sunrise event a Kerala almanac used under the modern
  presets, any almanac's own time standard, and the offset of Madras
  time beyond the fetched time-zone table are not stated in the held
  sources and are recorded as gaps.
- **Ranges.** Each modern preset runs only over the range its kernel,
  ΔT model and precession model state; a day outside is refused, and so
  is a day whose record needs an instant outside (its year's or month's
  start, the next saṅkrānti). In 1.0.0 no modern preset serves a day
  after 1 September 2026: the fetched IERS series ends on 8 September
  2026, and the days after 1 September need the next saṅkrānti, which
  lies beyond it. `modern_smh` and `modern_antiquity` end at the start
  of 2016. At the start of a range the first months are lost the same
  way: `modern_iers` serves Kerala days from 16 August 1972, the first
  Kollam year start inside its range
  ([`docs/verification.md`](docs/verification.md) gives each preset's
  served days). A later day can be computed with a constant ΔT
  (`--set modern.delta_t=constant:<seconds>`), and such records are
  flagged `diagnostic:modern.delta_t`; the kernel's and the other
  models' ranges still apply. The modern geometric sunrise
  under a text preset (`--set procedure.sunrise=modern_geometric:<preset>`)
  needs a preset on local mean time, so only `modern_smh` and
  `modern_antiquity` serve it, to 2016.
- **Where kernels go.** `jyotirganita fetch-kernel` writes the kernel
  into the installed package's data directory unless
  `JYOTIRGANITA_KERNEL_DIR` names another folder, and the engine looks
  in the same place. The variable has to be set for the fetch and for
  every run alike; it is read from the environment, not from a preset,
  so a run's record does not name the folder (the kernel's SHA-256 is
  checked wherever it lies).

## The tests

A test that changed each data value in turn (an experiment made at
1.0.0b3, not a measure of the final release's coverage) found that of
the 651 values the engine computes with, 262 made a test fail and 389
made none fail, 282 of those in the Dṛggaṇita. A value no test catches
is not known to be wrong, but a misreading of it would go unnoticed by
the tests. The search's tests compare its fast path with its reference
path and with the forward computation; no independent table of search
results tests it.

## Not built yet

- The ārdharātrika (midnight) system of Āryabhaṭa, the vākya system and
  Nīlakaṇṭha's Tantrasaṅgraha.
- Lunar months (the amānta and pūrṇimānta month names) and the
  ascendant (lagna).
- Regional profiles other than Kerala's, such as Tamil or Bengali, and
  Devanagari forms of the names.
- Siddhāntic eclipses.
- Ranking: the search lists every day that matches and how it matched,
  but does not rank them.
