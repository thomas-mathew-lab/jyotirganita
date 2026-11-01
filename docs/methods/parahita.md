# `parahita`: the Parahita system of Kerala

**Preset:** `parahita_kerala`. **Status:** validated, not corroborated (see
[`../verification.md`](../verification.md)); the tithi and nakṣatra it gives at sunrise agree
with a transcription of the Basel Mission's Malayalam almanac for 1868 on all but one day
(tithi) and two days (nakṣatra) of the 366.

## What it is

The Āryabhaṭīya (method `aryabhatiya`) with Haridatta's śakābda-saṃskāra:
a correction to each element's mean position, proportional to the
completed years counted from the correction's epoch. Haridatta's
Grahacāranibandhana states it. This is the system of the Kerala
almanacs and of many Kerala inscriptions.

## What the engine computes

Everything `aryabhatiya` computes, with one layer added: for each
element, the count of completed years after the layer's epoch times its
rate. Mercury's and Venus's rates apply to their śīghroccas, and the
node's to its longitude.

- The completed years are counted by the method's own mean Sun at the
  day's sunrise. The text doesn't say whether the year is the mean or
  the true one, so this is a recorded fallback, flagged provisional.
- Before the epoch the count is negative. No source states this case,
  so it is also a fallback, flagged provisional.
- A day before the layer's promulgation date carries
  `before_composition:parahita`, and a day before its epoch
  `before_epoch:sakabda_samskara`. Neither is refused.
- With its rates set to zero, the method gives exactly `aryabhatiya`'s
  results. A test checks this.

## Sources

| id | edition |
|---|---|
| grahacaranibandhana_1954 | Haridatta, *Grahacāranibandhana*, ed. K. V. Sarma, Madras 1954: the rates, the epoch and the promulgation date |
| sarma_1972_kerala_school | K. V. Sarma, *A History of the Kerala School of Hindu Astronomy*, Hoshiarpur 1972: second witness of the rates and dates |

Plus every source of `aryabhatiya`.

## What is checked, and what is open

- The rates, the epoch and the promulgation date are read in two
  witnesses. Their Kali–Śaka year pairs disagree in print, and both are
  kept on the data, not resolved privately.
- No source prints a worked example of the correction. The layer rests
  on its second witness, and the comparison with the printed Kerala
  almanacs is made outside this package.
- The node's sign in a variant of the correction (the Saṅgraha) and the
  rate for the Moon's apsis are open questions, recorded on the data.
