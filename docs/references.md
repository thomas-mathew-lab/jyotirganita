# References

Every printed edition, paper, almanac and published table that the
shipped data files and worked-example tests cite, grouped by kind. The
page was generated from the data files of this release (the generator is
a development tool and is not shipped), so it lists what the data cite;
it does not check the bibliographic details themselves. A value's own
record in its data file gives the printed page, the page of the scan and
the place on the page. Each source is named by the key the data files
use for it, and a summary table closes the page; an empty cell there
means none.

- **Used by:** the methods and parts of the package whose data or tests
  cite the source. This includes second witnesses, so not every value
  counted takes part in a computation.
- **Values:** constants, table entries, epochs, names and rule
  statements read from it, counted per data file (paths under
  `jyotirganita/data/`, or under `jyotirganita/` for the regional
  profiles).
- **Tables:** published tables taken from it as machine-readable files.
- **Worked examples:** its printed worked examples kept as test fixtures
  under `tests/authority/`, with the number of printed values read from
  them; the tests say which are reproduced.

## Texts and their editions

### `aryabhatiya_1976`

Āryabhaṭa, *Āryabhaṭīya of Āryabhaṭa — 3 volumes*. vol. 1 crit. ed. with English translation and notes by K. S. Shukla & K. V. Sarma; vol. 2 with the commentary of Bhāskara I and Someśvara, ed. K. S. Shukla; vol. 3 with the commentary of Sūryadeva Yajvan, ed. K. V. Sarma. Indian National Science Academy, New Delhi 1976.

- **Used by:** aryabhatiya, eras, parahita
- **Values:** 150, in `eras/kali.yaml` (3), `texts/aryabhatiya/elements.yaml` (63), `texts/aryabhatiya/epicycles.yaml` (25), `texts/aryabhatiya/procedures.yaml` (34), `texts/aryabhatiya/trig.yaml` (25)
- **Worked examples:** 7 examples (119 printed values), in `tests/authority/aryabhatiya/`

### `grahacaranibandhana_1954`

Haridatta, *Grahacāranibandhana — a karaṇa manual*. ed. K. V. Sarma, Kuppuswami Sastri Research Institute, Madras 1954 (KSRI Series).

- **Used by:** parahita
- **Values:** 95, in `texts/aryabhatiya/corrections.yaml` (69), `texts/aryabhatiya/procedures.yaml` (26)

### `drgganita_1963`

Parameśvara, *Dṛggaṇita*. ed. K. V. Sarma, Vishveshvaranand Institute Publications, Vishveshvaranand Vedic Research Institute, Hoshiarpur 1963.

- **Used by:** drgganita
- **Values:** 563, in `texts/drgganita/elements.yaml` (263), `texts/drgganita/jya.yaml` (273), `texts/drgganita/procedures.yaml` (22), `texts/drgganita/upari_samskara.yaml` (5)

### `vakyakarana_1962`

anonymous (Tamil Nadu, c. 1300); Sundararāja (comm.), *Vākyakaraṇa, with the commentary Laghuprakāśikā of Sundararāja*. ed. T. S. Kuppanna Sastri & K. V. Sarma, Kuppuswami Sastri Research Institute, Madras 1962 (KSRI Series no. 8).

- **Used by:** eras
- **Values:** 7, in `eras/kali.yaml` (4), `eras/saka.yaml` (3)
- **Worked examples:** 2 examples (17 printed values), in `tests/authority/kali/`

### `suryasiddhanta_burgess_1860`

Ebenezer Burgess (trans.); William D. Whitney (notes), *Translation of the Sûrya-Siddhânta, a Text-Book of Hindu Astronomy; with Notes and an Appendix*. Journal of the American Oriental Society 6 (1858/1860), pp. 141–498.

- **Used by:** suryasiddhanta, suryasiddhanta_paramesvara_recension
- **Values:** 302, in `texts/suryasiddhanta/composed.yaml` (43), `texts/suryasiddhanta/elements.yaml` (107), `texts/suryasiddhanta/epicycles.yaml` (23), `texts/suryasiddhanta/procedures.yaml` (66), `texts/suryasiddhanta/trig.yaml` (51), `texts/suryasiddhanta/whitney_notes.yaml` (12)
- **Worked examples:** 33 examples (612 printed values), in `tests/authority/suryasiddhanta/`

### `suryasiddhanta_paramesvara_1957`

Parameśvara (comm.), *The Sūrya-siddhānta with the Commentary of Parameśvara*. ed. Kripa Shankar Shukla, Hindu Astronomical and Mathematical Texts Series no. 1, Department of Mathematics and Astronomy, Lucknow University, 1957.

- **Used by:** suryasiddhanta, suryasiddhanta_paramesvara_recension
- **Values:** 135, in `texts/suryasiddhanta/witness_suryasiddhanta_paramesvara_1957.yaml` (135)
- **Worked examples:** 2 examples (13 printed values), in `tests/authority/suryasiddhanta/`

### `suryasiddhanta_hall_1859`

Raṅganātha (comm.), *The Sûrya Siddhânta, an Ancient System of Hindu Astronomy, with Raṅganātha's exposition the Gūḍhârtha-prakâśaka*. ed. Fitz-Edward Hall & Bāpū Deva Śāstrin, Bibliotheca Indica, Asiatic Society of Bengal, Calcutta 1859.

- **Used by:** suryasiddhanta, suryasiddhanta_paramesvara_recension
- **Values:** 226, in `texts/suryasiddhanta/composed.yaml` (4), `texts/suryasiddhanta/witness_suryasiddhanta_hall_1859.yaml` (222)
- **Worked examples:** 6 examples (144 printed values), in `tests/authority/suryasiddhanta/`

### `suryasiddhanta_bapudeva_1861`

Bāpū Deva Śāstrin and Lancelot Wilkinson (trans.), *Translation of the Surya Siddhanta (and of the Siddhanta Siromani)*. Bibliotheca Indica, Calcutta 1861.

- **Used by:** suryasiddhanta, suryasiddhanta_paramesvara_recension
- **Values:** 3, in `texts/suryasiddhanta/composed.yaml` (3)

### `grahanamandana_1965`

Parameśvara, *Grahaṇamaṇḍana*. ed. and trans. K. V. Sarma, Vishveshvaranand Institute, Hoshiarpur 1965.

- **Used by:** drgganita
- **Values:** 83, in `texts/drgganita/drk_school.yaml` (72), `texts/drgganita/procedures.yaml` (5), `texts/drgganita/upari_samskara.yaml` (6)

### `goladipika_1916`

Parameśvara, *Goladīpikā*. ed. T. Ganapati Sastri, Trivandrum Sanskrit Series no. 49, Government of Travancore, Trivandrum 1916.

- **Used by:** drgganita
- **Values:** 106, in `texts/drgganita/drk_school.yaml` (97), `texts/drgganita/procedures.yaml` (9)

### `sarma_1972_kerala_school`

K. V. Sarma, *A History of the Kerala School of Hindu Astronomy (in perspective)*. Vishveshvaranand Institute Publications 55, VVRI Hoshiarpur 1972.

- **Used by:** parahita
- **Values:** 6, in `texts/aryabhatiya/corrections.yaml` (6)

### `mahabhaskariya_1960`

Bhāskara I, *Mahābhāskarīya*. ed. and trans. with notes by K. S. Shukla, Hindu Astronomical and Mathematical Texts Series no. 3, Lucknow University, 1960.

- **Used by:** aryabhatiya, parahita
- **Values:** 69, in `texts/aryabhatiya/procedures.yaml` (69)
- **Worked examples:** 21 examples (282 printed values), in `tests/authority/aryabhatiya/`

### `laghubhaskariya_1963`

Bhāskara I, *Laghubhāskarīya*. ed. and trans. with notes by K. S. Shukla, Hindu Astronomical and Mathematical Texts Series no. 4, Lucknow University, 1963.

- **Used by:** aryabhatiya, parahita
- **Values:** 126, in `texts/aryabhatiya/elements.yaml` (16), `texts/aryabhatiya/epicycles.yaml` (21), `texts/aryabhatiya/procedures.yaml` (89)
- **Worked examples:** 10 examples (145 printed values), in `tests/authority/aryabhatiya/`

### `sewell_dikshit_1896`

Robert Sewell & Śaṅkara Bālakṛṣṇa Dīkṣita, *The Indian Calendar, with tables for the conversion of Hindu and Muhammadan into A.D. dates and vice versa*. Swan Sonnenschein, London 1896.

- **Used by:** Kerala profile, calendar, eras, search, time standards
- **Values:** 141, in `calendar/karana_cycle.yaml` (1), `eras/kali.yaml` (4), `eras/kollam.yaml` (3), `search/reading_rules.yaml` (10), `time_standards/lmt.yaml` (2), `regions/kerala/conventions.yaml` (11), `regions/kerala/names.yaml` (110)
- **Worked examples:** 8 examples (32 printed values), in `tests/authority/calendar/`

### `pillai_1911_chronology`

L. D. Swamikannu Pillai, *Indian Chronology (solar, lunar and planetary)*. Grames & Co., Madras 1911.

- **Used by:** calendar, eras, search
- **Values:** 6, in `eras/kali.yaml` (1), `eras/saka.yaml` (1), `search/reading_rules.yaml` (4)
- **Worked examples:** 4 examples (20 printed values), in `tests/authority/calendar/`

### `pillai_1922_ephemeris`

L. D. Swamikannu Pillai, *An Indian Ephemeris, A.D. 700 to A.D. 1799*. Government Press, Madras 1922, 7 vols.

- **Used by:** eras
- **Values:** 2, in `eras/kali.yaml` (1), `eras/kollam.yaml` (1)

### `calendar_reform_committee_1955`

Government of India, Council of Scientific & Industrial Research (chair: M. N. Saha), *Report of the Calendar Reform Committee*. CSIR, New Delhi 1955.

- **Used by:** Kerala profile, calendar, eras, modern_de, time standards
- **Values:** 34, in `eras/kali.yaml` (2), `eras/kollam.yaml` (1), `eras/saka.yaml` (2), `modern/calendar_reform.yaml` (2), `time_standards/ist.yaml` (1), `regions/kerala/conventions.yaml` (2), `regions/kerala/names.yaml` (24)
- **Worked examples:** 1 example (6 printed values), in `tests/authority/calendar/`

### `billard_1971`

Roger Billard, *L'astronomie indienne: investigation des textes sanskrits et des données numériques*. Publications de l'École française d'Extrême-Orient vol. 83, Paris 1971.

- **Used by:** drgganita
- **Values:** 4, in `texts/drgganita/witness_billard_1971.yaml` (4)

### `rashtriya_panchanga_1959`

Director General of Observatories, India Meteorological Department, *Rāṣṭrīya Pañcāṅga (Indian National Calendar) for 1959*. Government of India, 1959.

- **Used by:** calendar, modern_de, time standards
- **Values:** 3, in `modern/witnesses/refraction.yaml` (1), `time_standards/ist.yaml` (2)
- **Worked examples:** 2 examples (9 printed values), in `tests/authority/calendar/`

### `indian_astronomical_ephemeris`

Positional Astronomy Centre, India Meteorological Department, *The Indian Astronomical Ephemeris*. Government of India, annual.

- **Used by:** modern_de
- **Values:** 45, in `modern/iae_2022.yaml` (44), `modern/witnesses/refraction.yaml` (1)
- **Worked examples:** 1 example (10 printed values), in `tests/authority/modern/`

### `golasara_1970`

Nīlakaṇṭha Somayājī, *Golasāra of Nīlakaṇṭha Somayājī*. ed. and trans. K. V. Sarma, Vishveshvaranand Institute Series 47, Hoshiarpur 1970.

- **Used by:** drgganita
- **Values:** 34, in `texts/drgganita/drk_school.yaml` (33), `texts/drgganita/procedures.yaml` (1)
- **Worked examples:** 1 example (13 printed values), in `tests/authority/drgganita/`

### `suryasiddhanta_ranganatha_1871`

Raṅganātha (comm.), *The Sūrya Siddhānta, an Ancient System of Hindu Astronomy, with Raṅganātha's exposition*. Calcutta: Bābu Bhuvana Chandra Vasāka, Saṃvāda Jñānaratnākara Press, 1871; a separate setting under the English title of the Bibliotheca Indica edition of 1859, not a reissue of its text.

- **Used by:** suryasiddhanta, suryasiddhanta_paramesvara_recension
- **Values:** 2, in `texts/suryasiddhanta/witness_suryasiddhanta_ranganatha_1871.yaml` (2)

### `suryasiddhanta_ranganatha_1891`

Raṅganātha (comm.), *Sūryasiddhānta with Raṅganātha's Gūḍhārthaprakāśaka*. ed. Jīvānanda Vidyāsāgara Bhaṭṭācārya, second edition, Siddheśvara Press, Calcutta 1891.

- **Used by:** suryasiddhanta, suryasiddhanta_paramesvara_recension
- **Values:** 2, in `texts/suryasiddhanta/witness_suryasiddhanta_ranganatha_1871.yaml` (2)

## Almanacs

### `travancore_almanac_1876`

Government of Travancore, *Trevandrum Almanac for 1876*, 1876.

- **Used by:** Kerala profile
- **Values:** 3, in `regions/kerala/coordinates.yaml` (3)

### `travancore_almanac_1900`

Government of Travancore, *Travancore Almanac 1900 (1075-76)*, 1900.

- **Used by:** Kerala profile
- **Values:** 3, in `regions/kerala/coordinates.yaml` (3)

### `travancore_almanac_1907`

Government of Travancore, *Travancore Almanac 1907*, 1907.

- **Used by:** Kerala profile
- **Values:** 3, in `regions/kerala/coordinates.yaml` (3)

### `travancore_panchangam_1921`

Government of Travancore, *കൊല്ലവർഷം 1097-മാണ്ടത്തെ പഞ്ചാംഗം (Travancore Government Pañcāṅga, ME 1097 = 1921-22)*, 1921.

- **Used by:** Kerala profile
- **Values:** 101, in `regions/kerala/conventions.yaml` (1), `regions/kerala/names.yaml` (100)

## Modern works

### `balachandra_rao_2000`

S. Balachandra Rao, *Indian Astronomy: An Introduction*. Universities Press, Hyderabad 2000.

- **Used by:** suryasiddhanta
- **Worked examples:** 10 examples (298 printed values), in `tests/authority/suryasiddhanta/`

### `gopala_varyar_1954`

പാണ്ടനാട്ടിൽ പി. ആർ. ഗോപാലവാര്യർ (ശാസ്ത്രി) — P. R. Gopala Varyar (Śāstri) of Pandanad, *നിത്യപഞ്ചാംഗഗണിതം: ലളിതമായ വിവരണവും ഉദാഹരണക്രിയകളും അടങ്ങിയത്*, 1954.

- **Used by:** Kerala profile
- **Values:** 33, in `regions/kerala/coordinates.yaml` (9), `regions/kerala/practice.yaml` (24)

### `sarma_2009_facets`

K. V. Sarma; ed. Siniruddha Dash, *Facets of Indian Astronomy: A Collection of Articles of Prof. K. V. Sarma*. Rashtriya Sanskrit University Publication Series 200, Rashtriya Sanskrit University, Tirupati, 2009.

- **Used by:** eras
- **Values:** 2, in `eras/kollam.yaml` (2)

### `gislen_2018`

Lars Gislén, *On the Epoch of the Kollam Era*. Journal of Astronomical History and Heritage 21(2 & 3), p. 134 (2018), doi 10.3724/SP.J.1440-2807.2018.02.03.

- **Used by:** eras
- **Values:** 2, in `eras/kollam.yaml` (2)

## Astronomy: papers, theories and kernels

### `iau1980_nutation`

J. M. Wahr / IAU, *IAU 1980 nutation theory — the 106-term series*. Table 5.1 of IERS Conventions (1996), IERS Technical Note 21, ed. Dennis D. McCarthy, U.S. Naval Observatory, July 1996 — chapter 5, distributed as TeX source. Originally Seidelmann (1982) after Wahr.

- **Used by:** modern_de
- **Values:** 1, in `modern/iau1980.yaml` (1)
- **Tables:** `tables/nutation_iau1980.yaml`

### `vondrak_2011`

J. Vondrák, N. Capitaine & P. Wallace, *New precession expressions, valid for long time intervals*. Astronomy & Astrophysics 534, A22 (2011), with its corrigendum.

- **Used by:** modern_de
- **Values:** 10, in `modern/vondrak_2011.yaml` (10)
- **Worked examples:** 1 example (7 printed values), in `tests/authority/modern/`

### `stephenson_2016`

F. R. Stephenson, L. V. Morrison & C. Y. Hohenkerk, *Measurement of the Earth's rotation: 720 BC to AD 2015*. Proceedings of the Royal Society A 472, 20160404 (2016).

- **Used by:** modern_de
- **Values:** 3, in `modern/smh_2016.yaml` (3)

### `jpl_de441`

Jet Propulsion Laboratory, *JPL DE441 planetary and lunar ephemeris*. JPL SSD, DE441 (long-span, −13200 to +17191).

- **Used by:** modern_de
- **Tables:** `tables/kernels.yaml`

## Papers in the Indian Journal of History of Science

### `bag_2001`

A K Bag, *Ahargana and Weekdays As Per Modern Suryasiddhanta*. Indian Journal of History of Science 36.1&2 (2001).

- **Used by:** suryasiddhanta, suryasiddhanta_paramesvara_recension
- **Worked examples:** 2 examples (66 printed values), in `tests/authority/suryasiddhanta/`

### `bag_2003_julian_days`

A K Bag, *Luni–Solar Calender‚ Kali Ahargana and Julian Days*. Indian Journal of History of Science 38.1 (2003).

- **Used by:** calendar, eras
- **Values:** 2, in `eras/kali.yaml` (2)
- **Worked examples:** 3 examples (24 printed values), in `tests/authority/calendar/`

### `bag_2003_weekdays`

A K Bag, *A Note on the Ahargana and the Weekdays as per Modern Suryasiddhanta*. Indian Journal of History of Science 38.1 (2003).

- **Used by:** suryasiddhanta, suryasiddhanta_paramesvara_recension
- **Worked examples:** 1 example (33 printed values), in `tests/authority/suryasiddhanta/`

### `sarma_1996_kollam_era`

K V Sarma, *Kollam Era*. Indian Journal of History of Science 31.1 (1996).

- **Used by:** eras
- **Values:** 10, in `eras/kollam.yaml` (10)

## Fetched tables

### `jpl_kernels`

*JPL planetary and lunar ephemeris kernels (DE440; DE441 is jpl_de441)*, <https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de440.bsp> (fetched 2026-10-09).

- **Used by:** modern_de
- **Tables:** `tables/kernels.yaml`

### `iers_eop`

*IERS Earth orientation series (UT1−UTC, ΔT)*, <https://hpiers.obspm.fr/iers/eop/eopc04/eopc04.1962-now>, <https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second.dat> (fetched 2026-10-09).

- **Used by:** modern_de
- **Tables:** `tables/iers_eop_c04.yaml`, `tables/leap_seconds.yaml`

### `hipparcos`

*Hipparcos catalogue extract (the one star an ayanāṃśa names, Spica)*, <https://vizier.cds.unistra.fr/viz-bin/asu-tsv?-source=I/239/hip_main&HIP=65474&-out.all>, <https://cdsarc.cds.unistra.fr/ftp/I/239/ReadMe> (fetched 2026-10-09).

- **Used by:** modern_de
- **Tables:** `tables/hipparcos.yaml`

### `stephenson_2016_supplement`

*Stephenson, Morrison & Hohenkerk 2016, supplementary data (stephenson_2016)*, <https://ndownloader.figshare.com/files/6998699>, <https://ndownloader.figshare.com/files/6998702> (fetched 2026-10-09).

- **Used by:** modern_de
- **Tables:** `tables/deltat_smh2016.yaml`

### `iau2006_precession`

*IAU 2006 precession coefficients, published tables*, <https://iers-conventions.obspm.fr/content/chapter5/icc5.pdf> (fetched 2026-10-09).

- **Used by:** modern_de
- **Tables:** `tables/precession_iau2006.yaml`

### `iau2000a_nutation`

*IAU 2000A nutation series (IERS Conventions 2010, tables 5.3a and 5.3b)*, <https://iers-conventions.obspm.fr/content/chapter5/additional_info/tab5.3a.txt>, <https://iers-conventions.obspm.fr/content/chapter5/additional_info/tab5.3b.txt> (fetched 2026-10-09).

- **Used by:** modern_de
- **Tables:** `tables/nutation_iau2000a.yaml`

### `espenak_meeus_2006`

*Espenak & Meeus 2006 ΔT polynomials, NASA publication*, <https://eclipse.gsfc.nasa.gov/SEcat5/deltatpoly.html> (fetched 2026-10-09).

- **Used by:** modern_de
- **Tables:** `tables/deltat_em2006.yaml`

### `iana_tzdata`

*IANA time zone database, release 2025b (tzdata2025b.tar.gz)*, <https://data.iana.org/time-zones/releases/tzdata2025b.tar.gz> (fetched 2026-10-08).

- **Used by:** time standards
- **Tables:** `tables/tzdata_asia_kolkata.yaml`

## Summary

| source | values | tables | worked examples | used by |
|---|--:|--:|--:|---|
| `aryabhatiya_1976` | 150 |  | 7 | aryabhatiya, eras, parahita |
| `grahacaranibandhana_1954` | 95 |  |  | parahita |
| `drgganita_1963` | 563 |  |  | drgganita |
| `vakyakarana_1962` | 7 |  | 2 | eras |
| `suryasiddhanta_burgess_1860` | 302 |  | 33 | suryasiddhanta, suryasiddhanta_paramesvara_recension |
| `suryasiddhanta_paramesvara_1957` | 135 |  | 2 | suryasiddhanta, suryasiddhanta_paramesvara_recension |
| `suryasiddhanta_hall_1859` | 226 |  | 6 | suryasiddhanta, suryasiddhanta_paramesvara_recension |
| `suryasiddhanta_bapudeva_1861` | 3 |  |  | suryasiddhanta, suryasiddhanta_paramesvara_recension |
| `grahanamandana_1965` | 83 |  |  | drgganita |
| `goladipika_1916` | 106 |  |  | drgganita |
| `sarma_1972_kerala_school` | 6 |  |  | parahita |
| `mahabhaskariya_1960` | 69 |  | 21 | aryabhatiya, parahita |
| `laghubhaskariya_1963` | 126 |  | 10 | aryabhatiya, parahita |
| `sewell_dikshit_1896` | 141 |  | 8 | Kerala profile, calendar, eras, search, time standards |
| `pillai_1911_chronology` | 6 |  | 4 | calendar, eras, search |
| `pillai_1922_ephemeris` | 2 |  |  | eras |
| `calendar_reform_committee_1955` | 34 |  | 1 | Kerala profile, calendar, eras, modern_de, time standards |
| `billard_1971` | 4 |  |  | drgganita |
| `rashtriya_panchanga_1959` | 3 |  | 2 | calendar, modern_de, time standards |
| `indian_astronomical_ephemeris` | 45 |  | 1 | modern_de |
| `golasara_1970` | 34 |  | 1 | drgganita |
| `suryasiddhanta_ranganatha_1871` | 2 |  |  | suryasiddhanta, suryasiddhanta_paramesvara_recension |
| `suryasiddhanta_ranganatha_1891` | 2 |  |  | suryasiddhanta, suryasiddhanta_paramesvara_recension |
| `travancore_almanac_1876` | 3 |  |  | Kerala profile |
| `travancore_almanac_1900` | 3 |  |  | Kerala profile |
| `travancore_almanac_1907` | 3 |  |  | Kerala profile |
| `travancore_panchangam_1921` | 101 |  |  | Kerala profile |
| `balachandra_rao_2000` |  |  | 10 | suryasiddhanta |
| `gopala_varyar_1954` | 33 |  |  | Kerala profile |
| `sarma_2009_facets` | 2 |  |  | eras |
| `gislen_2018` | 2 |  |  | eras |
| `iau1980_nutation` | 1 | 1 |  | modern_de |
| `vondrak_2011` | 10 |  | 1 | modern_de |
| `stephenson_2016` | 3 |  |  | modern_de |
| `jpl_de441` |  | 1 |  | modern_de |
| `bag_2001` |  |  | 2 | suryasiddhanta, suryasiddhanta_paramesvara_recension |
| `bag_2003_julian_days` | 2 |  | 3 | calendar, eras |
| `bag_2003_weekdays` |  |  | 1 | suryasiddhanta, suryasiddhanta_paramesvara_recension |
| `sarma_1996_kollam_era` | 10 |  |  | eras |
| `jpl_kernels` |  | 1 |  | modern_de |
| `iers_eop` |  | 2 |  | modern_de |
| `hipparcos` |  | 1 |  | modern_de |
| `stephenson_2016_supplement` |  | 1 |  | modern_de |
| `iau2006_precession` |  | 1 |  | modern_de |
| `iau2000a_nutation` |  | 1 |  | modern_de |
| `espenak_meeus_2006` |  | 1 |  | modern_de |
| `iana_tzdata` |  | 1 |  | time standards |
