# jyotirganita

**A Python library for traditional and modern Indian calendrical astronomy.**

jyotirganita computes the elements of the Indian calendar day by day:
tithi, nakṣatra, yoga, karaṇa, weekday, the solar month and its day, the
saṅkrānti, the Kali, Śaka and Kollam years, sunrise and sunset, and the
planets. It computes them by the rules of the traditional astronomical
texts, each as its own text states them, and by modern astronomy from
NASA's JPL ephemerides. Where a text leaves a point open or defers to
another work, the reading followed is named in the method's
documentation. The texts' constants are read from cited pages of
printed editions, and the modern engine's tables are taken from
published sources recorded with their checksums. The text methods
compute in exact arithmetic, and the tests check them against the
worked examples printed in the texts and their commentaries, and
against published tables. It is meant for the study of inscriptions and
historical almanacs (pañcāṅgas).

Regional conventions (how a day is named, when a month begins, the eras
and the names) are kept apart from the astronomy in regional profiles.
Version 1.0.0 carries Kerala's.

## Design principles

- **The text's own arithmetic.** Each method computes as its text does,
  in whole numbers and exact fractions, so its computed fields are the
  same on any computer (a record's `environment` block, which names the
  computer it ran on, is not). The modern engine computes in standard double-precision
  floating point: its calendar times are given to the second, and its
  Julian dates and planetary positions in full double precision, whose
  last digits lie far below the accuracy of the models themselves.
- **Every value traced to its source.** The engine code holds no
  constant taken from a source; each is loaded from a data file that
  names the edition, the printed page and the place on the page, or, for
  a table fetched from its publisher, the file's address and SHA-256.
  The code itself holds only structural numbers (the 60 nāḍikās of a
  day, the 360 degrees of a circle) and a short list of others, each
  allowed with its reason.
  [`docs/references.md`](docs/references.md) lists every source and
  where it is used.
- **Read twice, blind.** Every value taken from a printed page was read
  from a page image by two readers who did not see each other's reading.
  The few on which they disagreed, and which a third look did not
  settle, stay at `read`, marked `disputed`. Disagreements and misprints
  are kept on the data, never quietly resolved.
- **Several methods side by side**, with a modern reference, so that a
  date can be computed by each and compared.
- **Results that say how far to trust them.** Every record names its
  method's status and flags the provisional data and conventions behind
  it. Its provenance records the engine version, the configuration and
  its hash, and the fingerprints of the method's data files; the same
  version and configuration give the same computed fields, up to the
  modern engine's last digits.

## Methods

| method | what it computes | presets |
|---|---|---|
| `aryabhatiya` | the Āryabhaṭīya (the sunrise system), with Bhāskara I's procedures | `aryabhatiya_text`, `aryabhatiya_kerala` |
| `parahita` | the Āryabhaṭīya with Haridatta's śakābda-saṃskāra (the Parahita system of Kerala) | `parahita_kerala` |
| `drgganita` | Parameśvara's Dṛggaṇita | `drgganita_kerala` |
| `suryasiddhanta` | the Sūrya-siddhānta as Burgess and Whitney translate it | `suryasiddhanta_text`, `suryasiddhanta_kerala` |
| `suryasiddhanta_paramesvara_recension` | the Sūrya-siddhānta as Shukla's edition with Parameśvara's commentary gives it | `suryasiddhanta_paramesvara_recension_text`, `suryasiddhanta_paramesvara_recension_kerala` |
| `modern_de` | a modern reference on the JPL DE440 and DE441 ephemerides | `modern_iers`, `modern_smh`, `modern_antiquity` |

A *method* is a text's arithmetic. A *preset* is a method plus the
other choices a run needs (the calendar conventions, the time standard,
the computation's options), each stated in the preset file
(`jyotirganita/methods/presets/`); every preset asks the caller to name
the place (`--observer`). The `_text` presets follow the text's own
conventions only, and give the month, the weekday and the day's
elements as indices, without names; the `_kerala` and `modern_*` presets add the Kerala
profile. Each method has a page in [`docs/methods/`](docs/methods/)
giving its sources, what it reproduces and what is still open.

## Status

**Four methods are `validated` in 1.0.0: `aryabhatiya`, `parahita`,
`suryasiddhanta` and `modern_de`. `drgganita` and
`suryasiddhanta_paramesvara_recension` are `provisional`, and no method
is `corroborated`.** `validated` means that no open reading changes a
computed number and that each method has been compared with an outside
almanac, table or program; `corroborated`, the higher grade, also asks
for a blind re-read by a reader from outside the model family and the
sign-off of the Indian-script data. The grades are the ones recorded for
this release. All values were read by AI models of one family
(Anthropic's Claude); no reader from outside that family has re-read
them blind, and some readings, mostly in Devanagari, are still open.
[`docs/verification.md`](docs/verification.md) explains the grades and
where each method stands; [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) lists
what is not yet done or rests on thin evidence.

## Quick start

Python 3.12 or later.

```
pip install jyotirganita
jyotirganita day --preset parahita_kerala --observer kerala/kozhikode \
    --date julian:1000-03-15
```

The record is one line of JSON. Abridged, and laid out for reading:

```
{"method_id": "parahita", "method_status": "validated",
 "dates": {"jdn": 2086382, "julian": {"y": 1000, "m": 3, "d": 15}, ...},
 "weekday": {"name": {"id": "shukra", ...}},
 "eras": {"kollam": {"year": 175, "masa": {"id": "mina", ...}, "day": 23, ...}, ...},
 "tithi": [{"name": {"paksa": "shukla", "name": {"id": "saptami", ...}},
            "ends_nadika_after_sunrise": {"exact": "2297…/1123…", "nadika": [20, 26, 3], ...}}, ...],
 "nakshatra": [{"name": {"id": "ardra", ...}, ...}, ...],
 "flags": ["modern_coordinates", "provisional:regions.kerala.month_rule", ...],
 "provenance": {"version": ..., "config_hash": ..., "data_files": ..., ...}}
```

Each ending time is given exactly, in nāḍikās as an exact fraction, and in
the text's own units (nāḍikā, vināḍikā and asu), cut as the text cuts
them; the `rounding` field names the rule. The command runs offline.
The modern presets need a JPL kernel, fetched once and checked against
its recorded SHA-256. It goes into the installed package's data
directory (so the environment must be writable), or into the folder
the environment variable `JYOTIRGANITA_KERNEL_DIR` names
([`docs/installation.md`](docs/installation.md)):

```
jyotirganita fetch-kernel de440    # modern_iers, modern_smh (about 120 MB)
jyotirganita fetch-kernel de441    # modern_antiquity (about 3.3 GB)
```

In 1.0.0 no modern preset serves a day after 1 September 2026:
`modern_iers` ends near where the fetched IERS series ends (8 September
2026), and the last days before that cut-off are refused because their
records need the next saṅkrānti, which lies beyond it; `modern_smh` and
`modern_antiquity` end at the start of 2016. A later day can be
computed with a constant ΔT, `--set modern.delta_t=constant:<seconds>`,
and every such record is flagged `diagnostic:modern.delta_t`; the
kernel's and the other models' ranges still apply.
[`docs/verification.md`](docs/verification.md) gives the first and last
days each modern preset serves.

[`docs/usage.md`](docs/usage.md) covers the other commands (a window of
days, the planets at an instant, the saṅkrāntis, eclipses, and the
inverse search for the days on which a set of recorded elements holds),
the Python API and the record.
[`docs/installation.md`](docs/installation.md) covers installing from a
checkout and running the tests.

## What it does not do

- **No interpretation or ranking.** It isn't an astrology or muhūrta
  tool. The search lists every day that matches and how each matched,
  but doesn't rank them.
- **No rules borrowed from outside a text's tradition.** Where a text
  gives no rule for a quantity, the record says `not_modelled`. Where
  the text itself defers to another work (the Dṛggaṇita, for sunrise),
  that work is named and the record flags it; where a method needs a
  convention its text leaves open, the convention is named and the
  record carries its flag.
- **Not yet built:** the ārdharātrika system of Āryabhaṭa, the vākya
  system, Nīlakaṇṭha's Tantrasaṅgraha, lunar months, siddhāntic
  eclipses and regional profiles other than Kerala's.

## How the data were made

Each constant, table entry, epoch and rule statement taken from a text
was read from a page image of a held edition and recorded with its
source, printed page and place on the page; the modern engine's tables
were instead fetched from their publishers and recorded with their
checksums. Every value read from a page was read again by a second
reader who had not seen the first reading. A disagreement went to a
third blind look, never to whichever value made a test pass; one it did
not settle stays at `read`, marked `disputed`. Misprints are kept as
printed, beside the adopted value and the evidence for adopting it. A value no source gives is recorded as a
gap, not filled in.

The code, data files and tests were written by Claude Opus 5.5
(Anthropic), working package by package under the supervision of Claude
Fable 5.1, which wrote each package's brief and reviewed its work, all
under the author's direction. The page readings were made by the same
two models: Claude Opus 5.5 read first, and Claude Fable 5.1 was the
second reader for numeral words and the Indian scripts. For some
disputed readings the author also chose among the recorded readings,
shown without their readers' names (`further_look`, reader
`person/…`); these choices are not a blind re-read. Before release,
OpenAI's GPT-6 Astra made a partial independent review of selected
sections of the code. Apart from six readings the author signed
off one by one, the Indian-script readings still await a person's
check.
[`docs/data.md`](docs/data.md) describes the data files and how to read
one; [`docs/references.md`](docs/references.md) lists the sources.

## Citing

Please cite the software with the metadata in [`CITATION.cff`](CITATION.cff).
A result can be reproduced from its record's `provenance` block, which
holds the engine version, the resolved configuration with every
override, its hash, and the hashes of the data files: the same version
and configuration give the same computed fields, up to the modern
engine's last digits. Please quote the version and the configuration
hash with any result you publish, and keep the whole record, since the
hash identifies a configuration but cannot rebuild it. Within one
minor line (1.0.x) computed dates do not change; see
[How versions are numbered](CHANGELOG.md#how-versions-are-numbered).

## Licence

Apache License 2.0 ([`LICENSE`](LICENSE)). [`NOTICE`](NOTICE) lists the
published tables shipped with the package and their terms. It also
covers the passages quoted from copyrighted editions, which remain
their publishers' and are not licensed by this project. The optional
`swisseph` extra (Swiss Ephemeris, AGPL-3.0) is reserved for
cross-check tests; the 1.0.0 suite holds none, and nothing in the
package imports it.
