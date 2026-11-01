# `suryasiddhanta`: the Sūrya-siddhānta

**Presets:** `suryasiddhanta_text` (the text's own conventions; name
its meridian on the equator with `--observer
meridians/suryasiddhanta_lanka`) and `suryasiddhanta_kerala` (the Kerala
calendar conventions, at a Kerala place). **Status:** validated, not corroborated (see
[`../verification.md`](../verification.md)).

## What it is

The Sūrya-siddhānta in the vulgate text that Burgess and Whitney
translate, read against Hall and Bāpū Deva's edition with Raṅganātha's
commentary, element by element. Where Shukla's edition with Parameśvara's
commentary differs, the difference is recorded. The two readings it
gives for the Moon's apogee and node are a method of their own,
[`suryasiddhanta_paramesvara_recension`](suryasiddhanta_paramesvara_recension.md).

## What the engine computes

- **The day count** runs from the end of creation, built from the
  text's own yuga structure and placed on the Kali era record. The
  weekday is counted from Sunday.
- **Mean positions.** The count times each element's revolutions over
  the civil days of its period. Mercury and Venus take the Sun's mean.
- **True positions.** The epicycle varies with the base-sine between
  its even and odd values. The equation of the apsis and that of the
  conjunction follow ii.29–45. The Sun and Moon take the equation of
  the apsis alone, and the five planets the four processes, as
  Whitney's note on ii.43–45 reads them.
- **Latitude** of the Moon and the five planets at sunrise.
- **Sunrise, sunset and the carries.** The deśāntara, the cara and the
  bhujāntara, the half-day from the cara, the daily motion corrected by
  the equations, and ending times by proportional parts on the text's
  daily motion.

## Sources

| id | edition |
|---|---|
| suryasiddhanta_burgess_1860 | E. Burgess (trans.) and W. D. Whitney (notes), *Translation of the Sûrya-Siddhânta*, JAOS 6, 1860 |
| suryasiddhanta_hall_1859 | *The Sûrya Siddhânta* with Raṅganātha's *Gūḍhârtha-prakâśaka*, ed. F.-E. Hall and Bāpū Deva Śāstrin, Calcutta 1859 |
| suryasiddhanta_bapudeva_1861 | Bāpū Deva Śāstrin and L. Wilkinson (trans.), *Translation of the Surya Siddhanta*, Calcutta 1861 |
| suryasiddhanta_paramesvara_1957 | *The Sūrya-siddhānta with the Commentary of Parameśvara*, ed. K. S. Shukla, Lucknow 1957 |

Worked examples also come from S. Balachandra Rao, *Indian Astronomy: An
Introduction* (balachandra_rao_2000, 2000), and A. K. Bag's two papers on the ahargaṇa
(bag_2001, bag_2003_weekdays), as cited test values.

## What is checked

- Raṅganātha's and Parameśvara's own computations (worked in the text's
  units) reproduce exactly.
- Whitney's, Rao's and Bag's decimal recomputations are compared to
  their stated precision. Where one of their figures does not follow
  from the rule applied to the figures they print before it, the test
  records it as a residual of their arithmetic. It is not absorbed by a
  wider tolerance.

## What is open

- Several conventions the text does not spell out are flagged
  provisional on every record they touch: how the cara acts on the mean
  positions, the sign of the precession in the declination, and the
  Kerala meridian (Whitney's identification, with Shukla's modern
  longitude for Ujjain).
- A few readings are still at `read`, mostly Devanagari statements
  where the two readers disagreed; the data files mark them.
- No almanac computed by this method is known in Kerala. Its outside
  comparisons are Swamikannu Pillai's *Indian Ephemeris*, Sewell and
  Dīkṣita's tables and Gislén and Eade's HIC program (see "Outside
  comparisons" in [`../verification.md`](../verification.md)).
