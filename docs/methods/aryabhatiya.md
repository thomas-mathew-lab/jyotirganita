# `aryabhatiya`: the Āryabhaṭīya (sunrise system)

**Presets:** `aryabhatiya_text` (the text's own conventions; name its
meridian on the equator, Laṅkā, with `--observer meridians/lanka`, or
any place, as every preset needs an observer) and `aryabhatiya_kerala` (the Kerala
calendar conventions, at a Kerala place). **Status:** validated, not corroborated (see
[`../verification.md`](../verification.md)).

## What it is

The element set of Āryabhaṭa's Āryabhaṭīya (499 CE), with the
procedures that Bhāskara I gives in the Mahābhāskarīya and the
Laghubhāskarīya, as K. S. Shukla edits them. The Parahita method of
Kerala (`parahita`) is this method with a correction layer added.

## What the engine computes

- **The day count.** Civil days from the Kali epoch (the era record in
  `jyotirganita/data/eras/kali.yaml`), which is also the first day the
  method runs. The weekday is counted from Friday, as the text says.
- **Mean positions** by the yuga revolution numbers, truncated at the
  vikalā, with the epoch additives of the Moon's apogee and node.
- **True positions.** The Sun and Moon take the manda equation. Mars,
  Jupiter and Saturn take four steps and Mercury and Venus three, with
  the pulsating epicycles and the Rsine table of Gītikā 12.
- **Sunrise, the carries and endings.** Sunrise is 15 nāḍikās after
  local mean midnight, moved by the bhujāntara and the cara. The
  deśāntara moves the mean elements to the observer's place. The
  ending times of tithi, nakṣatra and the rest are proportional parts
  on the daily motion, as the text states, truncated at the asu.
- **Kerala places** (Kozhikode, Thiruvananthapuram, Thrissur) are
  reached through their printed modern coordinates, converted by the
  text's own rules, or through coordinates you supply.

**Not modelled** (the record says `not_modelled`): planetary latitude,
distances, eclipses and a tropical frame.

## Sources

| id | edition |
|---|---|
| aryabhatiya_1976 | *Āryabhaṭīya*, ed. and trans. K. S. Shukla and K. V. Sarma, with the commentaries of Bhāskara I and Sūryadeva, INSA, New Delhi 1976 |
| mahabhaskariya_1960 | Bhāskara I, *Mahābhāskarīya*, ed. and trans. K. S. Shukla, Lucknow 1960 |
| laghubhaskariya_1963 | Bhāskara I, *Laghubhāskarīya*, ed. and trans. K. S. Shukla, Lucknow 1963 |

Consulted, with no value read from them: *The Āryabhaṭīya of
Āryabhaṭa*, trans. W. E. Clark, Chicago 1930 (quoted in one datum's
note), and the *Mahābhāskarīya* with Govindasvāmin's bhāṣya and
Parameśvara's Siddhāntadīpikā, ed. T. S. Kuppanna Sastri, Madras.
Studies used as leads, from which no value is taken: Anil Narayanan,
"The Pulsating Indian Epicycle of the Sun", *Indian Journal of History of
Science* 46.3 (2011); K. V. Sarma, "Āryabhaṭa: His Name, Time and
Provenance", *IJHS* 36.3–4 (2001); B. N. Narahari Achar, "Āryabhaṭa and
the Table of Rsines", *IJHS* 37.2 (2002).

## What is checked

- The worked examples in mahabhaskariya_1960, laghubhaskariya_1963 and aryabhatiya_1976 for the day count, mean
  longitudes, the Rsine and Rversine tables, ascensional differences
  and rising times reproduce, each in its class. The editors' decimal
  recomputations are matched to their stated precision.
- Where a page's own figures show a misprint (for example a sum in
  laghubhaskariya_1963's Rsine example), the printed figure is kept beside the adopted
  one with the evidence.
- mahabhaskariya_1960's example weekdays run one day behind both the text's rule and
  laghubhaskariya_1963. The engine follows the rule, and only the differences between
  the examples are tested.

## What is open

- Every procedure without a printed example rests on a second witness
  in the editions. Its outside comparisons are Swamikannu Pillai's
  *Indian Ephemeris* (the Sun) and Gislén and Eade's HIC program (see
  "Outside comparisons" in [`../verification.md`](../verification.md));
  no almanac computed by the pure Āryabhaṭīya is known.
- A few readings are still at `read`; the data files mark them.
- The Ujjain meridian's modern longitude differs between two editors.
  Shukla's value in laghubhaskariya_1963 is used, and the other is kept on record. It
  moves every Kerala place's offset by about 4.4 vināḍikās.
