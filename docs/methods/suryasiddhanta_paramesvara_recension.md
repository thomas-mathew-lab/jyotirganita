# `suryasiddhanta_paramesvara_recension`: the Sūrya-siddhānta in Parameśvara's recension

**Presets:** `suryasiddhanta_paramesvara_recension_text` and
`suryasiddhanta_paramesvara_recension_kerala`. **Status:** provisional (see [`../verification.md`](../verification.md)): its own
Moon apogee and node figures, the two numbers in which it differs from the vulgate, have no
second witness or outside comparison yet; what it shares with the vulgate is covered by the
vulgate's checks.

## What it is

The Sūrya-siddhānta as the text stands in K. S. Shukla's edition with
Parameśvara's commentary (suryasiddhanta_paramesvara_1957, Lucknow 1957). It differs from the
vulgate of [`suryasiddhanta`](suryasiddhanta.md) in two numbers only:
the revolutions of the Moon's apogee and of its node. A collation of
every element found nothing else. Shukla's Introduction prints both
readings and assigns this one to the versions of Parameśvara, Rāmakṛṣṇa
and Bhūdhara. It is a reading of one branch of the text's manuscripts,
not a correction Parameśvara proposes as his own. Parameśvara's own
Kerala corrections are not part of this method.

## What the engine computes

Everything `suryasiddhanta` computes, with the two numbers replaced.
Every procedure, convention and place is shared with the base method,
and tests check this.

## What is checked, and what is open

- The worked examples that name this method (Parameśvara's mean places
  at the start of the Kali yuga and his count to the start of the
  Tretā, and Bag's count arithmetic) reproduce as under the base.
  **They don't separate the two recensions, though**: at those dates
  both readings put the Moon's apogee and node in the same whole signs.
  So no worked example yet tests the two replaced numbers.
- The two numbers are Devanagari readings that await the author's
  individual sign-off. The held copy of suryasiddhanta_paramesvara_1957 is not a durable one, so it
  cannot by itself support `verified`.
- The recension's own date of composition is not stated. The vulgate's
  is used for the `before_composition` flag.
