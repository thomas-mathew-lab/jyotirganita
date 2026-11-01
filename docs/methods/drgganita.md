# `drgganita`: Parameśvara's Dṛggaṇita

**Preset:** `drgganita_kerala`. **Status:** provisional, and expected
to stay so for some time (see [`../verification.md`](../verification.md)
and the end of this page).

## What it is

The Dṛk system that Parameśvara set out in the Dṛggaṇita to
bring computation back into agreement with observation. Its Part II
gives the guṇakāra/hāraka rates, the drifts, the dhruvas at the Kali
epoch, and seventeen jyā tables of the equations with their own
interpolation rule and order of application. The text defers the
sunrise, the carries and the day's inner time to earlier works. For
those the engine uses Parameśvara's Goladīpikā and Grahaṇamaṇḍana and
Nīlakaṇṭha's Golasāra.

## What the engine computes

- **Mean positions.** An element's mean longitude on Kali day *A* is
  the fractional part of *A*·guṇa/hāra revolutions, plus the drift and
  the dhruva, all exactly. The text states no rounding.
- **True positions.** The kendra's correction is read from the jyā
  table of its kind, by the bhujā in the table's steps, with the text's
  second-difference interpolation. The Sun and Moon take the manda
  correction only. Mars, Jupiter and Saturn take half manda, half
  śīghra, whole manda, whole śīghra. Mercury and Venus take their own
  order. The node is applied once, as a circle less the mean Rāhu.
- **Sunrise, the carries, declination, half-day, daily motion and
  endings**, from the Goladīpikā's verses (goladipika_1916), with the Grahaṇamaṇḍana
  (grahanamandana_1965) or the Golasāra (golasara_1970) where goladipika_1916 is silent. The Rsine table the
  cara and declination need is the one grahanamandana_1965 quotes as old mnemonic
  verses; the Dṛggaṇita itself prints none. Every record that uses it
  is flagged.

**Not modelled:** the latitudes of the five planets and eclipses. The
Goladīpikā's latitude rule (goladipika_1916 v. 127–128) divides by the manda and
śīghra hypotenuses, which the Dṛggaṇita's tables do not give. The
Moon's latitude is computed, by the Grahaṇamaṇḍana's rule (grahanamandana_1965 śl.
37–38).

## Sources

| id | edition |
|---|---|
| drgganita_1963 | Parameśvara, *Dṛggaṇita*, ed. K. V. Sarma, Hoshiarpur 1963 |
| grahanamandana_1965 | Parameśvara, *Grahaṇamaṇḍana*, ed. and trans. K. V. Sarma, Hoshiarpur 1965 |
| goladipika_1916 | Parameśvara, *Goladīpikā*, ed. T. Ganapati Sastri, Trivandrum Sanskrit Series 49, 1916 |
| golasara_1970 | Nīlakaṇṭha, *Golasāra*, ed. and trans. K. V. Sarma, Hoshiarpur 1970 |
| billard_1971 | R. Billard, *L'astronomie indienne*, Paris 1971: second witness of the mean rates |

## Why it stays provisional

- Its sources print **no worked example** on the engine's path, so
  criterion 2 can't be met from them.
- It has **the most readings still at `read`**: Devanagari verse and
  table entries that two readers disagreed on and a third look didn't
  settle. Every outside reader tried so far has failed the Devanagari
  control, so these wait for a human reader of the script.
- Several of its parts are **borrowed by design** from the works the
  text defers to (above). Its Part I and Part II state the node's drift
  in different units: Part II is used, and the question is recorded.
- The second-difference interpolation's last step, which has no next
  difference, uses the preceding pair's second difference. This is a
  fallback, flagged on every record.

It runs and its records are complete, but every one of them carries
these flags. Read a Dṛggaṇita result as provisional.
