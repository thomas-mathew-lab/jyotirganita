# Using jyotirganita

## The command line

`jyotirganita <command>`, or `python -m jyotirganita.io.cli` without the
console script. One example per computing command (`fetch-kernel`, which
fetches a JPL kernel, is in [installation.md](installation.md)):

```
# the day records of a window
jyotirganita generate --preset parahita_kerala --observer kerala/kozhikode \
    --from gregorian:1954-08-17 --to gregorian:1955-08-16 --jsonl year.jsonl

# the record of one day, with the derived UT and TT of its start
jyotirganita day --preset parahita_kerala --observer kerala/kozhikode \
    --date julian:1000-03-15 --derived-ut mean --derived-tt smh2016

# the planets at an instant
jyotirganita positions --preset modern_iers --observer kerala/kozhikode \
    --at gregorian:2022-08-17T06:30:00/ist --bodies sun,moon

# the saṅkrānti instants of a window
jyotirganita sankrantis --preset parahita_kerala --observer kerala/kozhikode \
    --from gregorian:1954-01-01 --to gregorian:1954-12-31

# the lunar eclipses of a window, and the solar eclipses seen at the observer
# (modern presets only)
jyotirganita eclipses --preset modern_iers --observer kerala/kozhikode \
    --from gregorian:2022-01-01 --to gregorian:2022-12-31

# the inverse search (q.yaml below)
jyotirganita search --preset parahita_kerala --observer kerala/kozhikode \
    --query q.yaml --jsonl out.jsonl
```

A minimal `q.yaml`: the Wednesdays of an eleven-day window, with
Jupiter's rāśi reported but not required (the search section below
describes every part). The `kerala_default` profile reads Jupiter's
rāśi by its mean place; under a modern preset, add `position: true` to
the Jupiter constraint, since the modern engine computes no mean place.

```yaml
reading_profile: kerala_default
window:
  from: {jdn: 2167030}
  to: {jdn: 2167040}
constraints:
  - {element: weekday, value: Wednesday}
  - {element: planet_rasi, body: jupiter, value: Makara, mode: report}
```

- **Common options.** The six commands above take `--preset`,
  `--observer` (required: no preset names a place of its own),
  `--jsonl` (an output path; `-`, the default, is standard output),
  `--set key=value`, which can be repeated, and `--repo` (the directory
  that holds the `jyotirganita` package; by default, the one the
  command runs from).
  `search` also takes `--query`, `--brute`, and `--month-rule`,
  `--intraday` and `--procedure <slot>=<id>` as short forms of their
  `--set` keys. Each command writes a count to standard error
  (`<command>: N line(s)`; `search: N match, M near_miss`). `jyotirganita <command>
  --help` lists the options.
- **Observers** are `<region>/<place>`: a Kerala place of
  `jyotirganita/regions/kerala/places.yaml` (Kozhikode,
  Thiruvananthapuram, Thrissur), a text's own meridian such as
  `meridians/suryasiddhanta_lanka`, or a place you give by its modern
  coordinates as `kerala/@<latitude>,<longitude>` (degrees, north and
  east positive). Your coordinates are converted to each text's own
  terms by the same rules as the tabled places. A run at them records
  them in its provenance, and every record carries the flags
  `user_place` and `modern_coordinates`.
- **Dates** are tagged `julian:`, `gregorian:` or `jdn:`. Years are
  astronomical: `julian:-3101-02-18` is 3102 BC. The instant
  of `positions --at` names its reckoning: `<date>+<n>nadika` under a
  siddhantic preset, `<date>T<hh>:<mm>[:<ss>]/<standard>` under a
  modern one.
- **`--set` keys** change one stated choice of the preset:
  `conventions.month_rule`, `conventions.era.<era>.year_start`,
  `procedure.sunrise=modern_geometric:<modern preset>` (a modern
  geometric sunrise and sunset under a siddhantic preset; it reads local
  mean time, so only `modern_smh` and `modern_antiquity` serve it, and
  both end at the start of 2016), `intraday`,
  `time_standard`, `output.elements`, `output.scripts`, and the modern
  engine's `modern.sunrise_event`, `modern.ayanamsa`, `modern.delta_t`
  and `modern.node` (`modern.delta_t=constant:<seconds>` serves days
  after a preset's ΔT model ends, flagged `diagnostic:modern.delta_t`).
  The values each key accepts are listed in `jyotirganita/config.py`;
  for example `--set conventions.month_rule=following_day`,
  `--set conventions.era.kollam.year_start=kanya`,
  `--set intraday=full_evaluation` (siddhantic presets),
  `--set output.elements=tithi,nakshatra`,
  `--set output.scripts=latin,malayalam`, and under a modern preset
  `--set time_standard=lmt`, `--set modern.delta_t=constant:69` or
  `--set modern.node=osculating`.
  The method, the data and the date of composition
  can't be overridden. An override enters the configuration hash, and
  the records flag every override that changes the method's own
  arithmetic.
- **`--derived-ut mean | apparent:<source>`** and **`--derived-tt
  <ΔT model>`** add, under a siddhantic preset, the UT1 and TT of the
  day's start (`generate`, `day`) or of the requested instant
  (`positions`). `--derived-tt` needs `--derived-ut`. A modern record
  carries its own UT1 and TT on its sunrise and sunset instead, and a
  modern `positions` refuses these options. They are never part of the
  configuration hash, and every record carrying them is flagged
  provisional.
- **Refusals.** An unknown preset, place or `--set` key, an untagged
  date, a window the run doesn't serve or a malformed query is refused
  before any day is computed. The refusal is written to standard error
  as `jyotirganita <command>: <field>: <message>`, with exit status 2.
  An empty result exits with status 0. A failure of the engine's own
  numerics is written as `jyotirganita <command>: internal: <message>`,
  with exit status 3: it is a fault to report. `fetch-kernel` exits
  with status 1 when it refuses.

Output is one JSON object per line, in a canonical form: the keys in
the order of the record's schema, any key the schema does not list
after them in sorted order, and exact numbers as fraction strings.

## The Python API

```python
from pathlib import Path

import jyotirganita
from jyotirganita import day, generate, open_config
from jyotirganita.io.dates import parse_cli_date
from jyotirganita.search import open_search, search

# the directory that holds the jyotirganita package (site-packages, in a wheel install)
repo = Path(jyotirganita.__file__).resolve().parent.parent
config = open_config(repo, "parahita_kerala", "kerala/kozhikode")
record = day(config, parse_cli_date("julian:1000-03-15"))
for rec in generate(
    config, parse_cli_date("gregorian:1954-08-17"), parse_cli_date("gregorian:1955-08-16")
):
    ...
```

`open_config` takes the `--set` overrides as keyword arguments, for
example `**{"conventions.month_rule": "following_day"}`. `generate`
streams its records in day order.

The inverse search is imported from its subpackage, not from the top
level (`jyotirganita.search` is the subpackage's name):
`search(open_search(repo, "parahita_kerala", "kerala/kozhikode"), query)`
takes a query as a mapping (read from the YAML or JSON file) and yields
its candidates in day order. `open_search` takes the `--set` overrides
as a mapping, `sets={"conventions.month_rule": "following_day"}`.

The other commands, and writing results as the command line does:

```python
from jyotirganita import eclipses, positions, sankrantis
from jyotirganita.api import dumps
from jyotirganita.io.dates import parse_cli_instant
from jyotirganita.search.results import dumps as dump_candidate

# the planets at an instant; the instant's form follows the preset's kind
at = parse_cli_instant("julian:1000-03-15+7nadika", config.kind, config.time_standard)
print(dumps(positions(config, at, ["sun", "moon"])))

# the saṅkrāntis of a window; eclipses(config, window) under a modern preset
window = (parse_cli_date("gregorian:1954-01-01"), parse_cli_date("gregorian:1954-12-31"))
for rec in sankrantis(config, window):
    print(dumps(rec))

# a search yields candidate objects; dump_candidate writes each one's JSON line
query = {
    "reading_profile": "kerala_default",
    "window": {"from": {"jdn": 2167030}, "to": {"jdn": 2167040}},
    "constraints": [{"element": "weekday", "value": "Wednesday"}],
}
for cand in search(open_search(repo, "parahita_kerala", "kerala/kozhikode"), query):
    print(dump_candidate(cand))
```

`generate` takes the window's two dates as two arguments, `sankrantis`
and `eclipses` as one pair. A record is a mapping whose exact numbers
are `Fraction`s; `dumps` writes it in the command line's canonical
form.

## The record

One civil day's record follows `jyotirganita/io/record.schema.json`.
Its keys are: `method_id`, `method_status`, `config_hash`,
`parameters_sha256`, `numeric`, `conventions`, `dates`, `weekday`,
`eras` (Kali, Śaka and Kollam, where the conventions carry them),
`sunrise`, `sunset`, `day_length_nadika` (the civil day's length, from
its start to the next day's start, not the daylight), `tithi`,
`nakshatra`, `yoga`, `karana` (with the instants each begins and ends;
each present only when selected by `output.elements`, which selects all
four by default), `masa`, `sankranti`, `planets` (sidereal longitude,
latitude, daily motion and retrograde for every body), `flags` and
`provenance`, plus `derived_ut` and `derived_tt` when asked for.

- **Numbers.** Under the siddhantic presets every angle, motion and
  instant is exact: `{"exact": "num/den"}`. The text's own rounded form
  stands beside it only where the text states a rounding rule. Under
  the modern presets, numbers are doubles in shortest round-trip form.
- **Empty values.** A value the run can't fill, within the selected
  output, is one of three strings, never zero or a missing key: `not_modelled` (the method doesn't model
  it), `not_in_preset` (the conventions don't define it) or
  `not_in_range` (outside an era's range). `null` has its own meanings
  and is not one of them: `sankranti` is `null` on a day without one,
  its `assigned_day1` can be `null`, and an occurrence's `start` is
  `null` when it began before the civil day and its `end` is `null` when
  it runs past the day's end (`ends_nadika_after_sunrise` still gives
  its ending).
- **Provenance.** The engine and its version, the method and its
  status, the observer, the method's data files with their SHA-256 and
  their combined digest `parameters_sha256`, the calendar's files (the
  preset, the regional names, conventions and places, the era records,
  the time standards) with theirs under `calendar_files`, the engine
  parameters, the sunrise provider, and the resolved configuration with
  every override.
  Two runs with the same provenance produce the same computed fields;
  the `environment` block names the computer and can differ.

## Flags

A flag is information for the person dating a record, never a refusal.
The list gives the families of flags, not every flag:

- `before_composition:<id>` and `before_epoch:<layer>`: the day is
  earlier than the text's cited date of composition, or than the epoch
  of a correction layered on the method (Parahita's śakābda-saṃskāra,
  for example). A siddhantic method computes every day from its own
  epoch, its one hard limit.
- `kshaya:<element>.<n>` and `vriddhi:<element>.<n>`: the element's
  occurrence *n* is skipped between this day and the next (kṣaya), or
  this day repeats the previous day's (vṛddhi), under the day's
  assignment rule. Many records carry one.
- `provisional:<datum key>` and `provisional_method`: a datum, a
  convention or the method itself is still provisional. Among them
  `provisional:eclipse` (every eclipse result),
  `provisional:derived_ut.time_reckoning` (with `--derived-ut`),
  `provisional:regions.kerala.user` (a place given by its coordinates)
  and `provisional:regions.kerala.names.malayalam` (Malayalam names).
  See [verification.md](verification.md).
- `modern_coordinates`: the place was reached from modern latitude and
  longitude and converted to the text's terms, whether it is a tabled
  place given by its modern coordinates (Kozhikode, for example) or one
  the user gave.
- `user_place`: the coordinates were the user's, not a tabled place's.
- `hybrid_sunrise:modern_geometric` and `diagnostic:<id>`: an override
  replaced part of the method's own arithmetic (for example
  `diagnostic:modern.delta_t` for a constant ΔT, and
  `diagnostic:era_years.text_sunrise` under the hybrid sunrise). The
  hybrid sunrise also writes `jyotirganita <command>: note: …` lines
  to standard error.

The modern presets run only within their kernel's and their models'
stated ranges, and they refuse days outside them.

## The search

Given a window, a preset at an observer and the elements an inscription
records, `jyotirganita search` returns every civil day in the window on
which those elements hold. The query is a YAML or JSON file validated
against `jyotirganita/search/query.schema.json`. It has three parts:

- a reading profile, which says how a recorded element is read
  (`kerala_default` or `strict_sunrise`, in
  `jyotirganita/search/reading_profiles/`). None is implied;
- the window;
- constraints, each named by its `element` as the schema names it:
  `era_year`, `era_day`, `masa`, `sankranti_day`, `day_of_month`,
  `weekday`, `tithi`, `nakshatra`, `yoga`, `karana`, `at_time`,
  `sun_rasi`, `moon_rasi`, `planet_rasi` and `planet_nakshatra` (a
  `body` of Mercury to Saturn, Rāhu or Ketu; there is no constraint on
  the Sun's nakṣatra, and the Moon's is `nakshatra`), `ayana`,
  `eclipse` and `overlap`. The schema gives each one's fields. A tithi
  is written `{paksha: sukla | krishna, n: <number>}` (or with `name`),
  a spelling that differs from the records' `"paksa": "shukla"`.

Each constraint either filters (`require`) or is only reported
(`report`). An occurrence element (tithi, nakṣatra, yoga, karaṇa) is
matched `assigned` (the day's label), `any_occurrence` (in force at
some instant of the civil day) or `at_time` (at a stated nāḍikā). A
position constraint (a body's rāśi or nakṣatra) is matched
`at_sunrise` (the body's place at the day's start) or, when the query
says `match: any_time_in_day`, on the places the body takes through
the civil day on the engine's own motion, the same places `positions`
returns; the next day's start belongs to the next day. Under a
siddhantic preset that motion is, by default (`intraday`), the day's chord, linear in time, over
the first sixty nāḍikās of the day (the sliver of a longer day beyond
them is not swept); under a modern preset the place is sampled at four
equal steps of the day and a station between samples is refined to the
engine's root tolerance. A reading profile sets these defaults:
`kerala_default` matches occurrence elements at any occurrence during
the day and reads Jupiter's rāśi by its mean place (the mean-sign
system); `strict_sunrise` uses the labels assigned at sunrise and true
places. A constraint's own `match` or `position` overrides its
profile.

Each candidate is a day of class `match`, where every `require`
constraint holds. With `near_miss: {max_misses: n}` it can also be of
class `near_miss`, where all but at most *n* hold. A candidate carries
the evidence for each constraint and, where one fails, the margin by
which it fails, plus the day's flags and the provenance. `--brute` runs
the unpruned reference path, which serves as a check on the fast one.
