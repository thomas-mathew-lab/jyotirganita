# Changelog

## How versions are numbered

Versions are MAJOR.MINOR.PATCH. The aim: anyone who cites a 1.0.x release
gets the same dates from every 1.0.x release.

- **Patch** (1.0.1): no computed value changes. Documentation, speed,
  messages, packaging, and fixes for a crash where no answer was given.
- **Minor** (1.1.0): any change to a computed value (a bug fix, a corrected
  table entry, a new reading), and new methods or options. The changelog
  entry names the methods and date ranges that moved and about how many
  days changed.
- **Major** (2.0.0): a change that can break code using the package (a
  renamed function, a changed output format, a removed method), or a
  milestone such as the first `corroborated` method.
- A method that moves up a grade is a minor release, even when no number
  changes; the first release with a `corroborated` method is the one
  exception, a major release. A move down carries a warning in the
  changelog.
- A large or risky change comes first as a beta (for example 1.1.0b1).
- Every release has a git tag, a changelog entry and a PyPI upload.
  1.0.0 and each later minor or major version also has a GitHub release
  and a Zenodo DOI; a patch has none of its own, since it changes no
  computed value, and the DOI of its minor version serves it.

## 1.0.0 (2026-11-01)

The first public release. It carries six methods (`aryabhatiya`,
`parahita`, `drgganita`, `suryasiddhanta`,
`suryasiddhanta_paramesvara_recension`, `modern_de`) and eleven presets
under the Kerala calendar conventions and the texts' own. It also has
the inverse search, the command line and the Python API. Four methods
are `validated` (`aryabhatiya`, `parahita`, `suryasiddhanta` and
`modern_de`), `drgganita` and `suryasiddhanta_paramesvara_recension`
are `provisional`, and no method is `corroborated`:
[`docs/verification.md`](docs/verification.md) says what has and has not
been checked, and [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) what is not yet
done.

Later versions are numbered as described above.
