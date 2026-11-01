# The data files

Every number the engine takes from a source comes from a data file. A
check run over the code (`jyotirganita/data/firewall.py`) refuses any
numeric literal except a short list of structural numbers (the 60
nāḍikās of a day, the 360 degrees of a circle), the entries of
`jyotirganita/data/firewall_allow.yaml`, each with its reason, and a
literal tagged with the datum, engine parameter or derived record it
equals.

| where | what |
|---|---|
| `jyotirganita/data/texts/<text>/` | each text's elements, tables, epicycles, procedures and corrections |
| `jyotirganita/data/eras/` | the Kali, Śaka and Kollam era records |
| `jyotirganita/data/modern/`, `data/tables/` | the modern engine's page-read data and its fetched tables |
| `jyotirganita/data/time_standards/` | local mean time, Madras time, IST |
| `jyotirganita/data/sources.yaml` | every edition and publication cited, with its file hash and copyright status |
| `jyotirganita/data/engine_parameters.yaml` | the engine's own numerical settings (search steps, tolerances, seeds), each with its reason |
| `jyotirganita/methods/` | the method registry and the presets |
| `jyotirganita/regions/` | the Kerala profile and the places |

## A datum

```yaml
- key: texts.aryabhatiya.sun.revolutions   # a dotted name
  value: …                       # the value in its printed form (here the editor's decode)
  word: {text: …, script: devanagari, system: aryabhata_alphabetic, decode: …}
  form: numeral_word             # integer, fraction, sexagesimal, table, numeral_word, text…
  unit: revolutions_per_yuga
  source: aryabhatiya_1976                    # an id of sources.yaml
  edition_page: 6                # the printed page
  pdf_page: 34                   # the page of the held scan
  locus: Gītikā 3, …             # where on the page
  read:                          # the first reading
  - by: <model>/<date>-r<n>
    on: 2026-10-03
    dpi: 600
    clip: [x0, y0, x1, y1]       # the region of the page that was read
    delivered_ppi: 600
  second_read: [ … ]             # the independent second reading
  status: double_read            # read, double_read or gap
```

The example is a schematic excerpt, not loadable YAML, and its page
numbers are illustrative. A complete record is the first entry of
`jyotirganita/data/texts/aryabhatiya/elements.yaml`; the schema
(`jyotirganita/data/schema/`) gives every field, among them
`value_form` for a numeral-word, `file` for a source held in several
files, `verified_by`, `emendation` and `notes`. `status` is never
`verified`: that status was computed by the development ledger
([verification.md](verification.md)).

- **Printed form.** A value is kept as printed: `[rāśi, degree, kalā,
  vikalā]`, a fraction, or a table as laid out. The code converts it.
- **Numeral-words.** A number written as a word (kaṭapayādi,
  bhūtasaṅkhyā, or Āryabhaṭa's alphabetic numerals) is stored twice:
  the editor's printed decode as `value`, and the word itself with an
  independent decode under `word`. Where the two disagree the datum
  is marked `mismatch_issue: disputed`, and the method is provisional
  on it.
- **Disagreements.** Where two readers disagreed and a third look did
  not settle it, the datum stays at `read` and is marked
  `read_issue: disputed`; where a third look settled it, the look is
  recorded under `third_look`, and any later look under `further_look`.
  A second reading that disagreed and was not adopted is kept in the
  development record, not on the datum. A `further_look` by a reader
  `person/…` is the author's choice among the recorded readings, shown
  without their readers' names, not a blind re-read. Two printed statements of one thing
  that disagree are both kept, each with a `contradiction` naming the
  other.
- **Misprints.** A printed value found wrong keeps its printed form
  under `emendation.printed`. The adopted value is beside it, with the
  evidence: a second witness, the text's own check rule, or an erratum
  page.
- **Gaps.** A value no source gives is a record with `status: gap`, the
  reason, the sources searched and the effect. The elements that need
  it are `not_modelled`.
- **Procedures.** Each procedure the engine runs is named by a datum
  that quotes or cites the rule's statement, with the verse or
  paragraph. `basis` says whether the rule is stated, inferred from a
  worked example, or a fallback where no rule is stated. A fallback
  flags every record it touches.
- **Readers.** `by` names the reading context: a model id, a date and a
  number that tells apart the contexts of one model on one day, or
  `person/<date>-r<n>` for the author. Readers worked from page images rendered at the scan's native
  resolution. The text layers and OCR of the scans were used only to
  find pages, never to read a value. For a born-digital source, a
  named tool's extraction of the text layer may serve as one of the
  two reads.

## Worked examples

The printed worked examples are fixtures under `tests/authority/`, with
their inputs and outputs in the text's own units. Each records whether
it was computed by the text's author or a pre-modern commentator
(`text_computed`, which must reproduce exactly) or by a modern editor
(`editor_computed`, which is compared to the editor's precision). Their
printed values carry reading records like a datum's.
