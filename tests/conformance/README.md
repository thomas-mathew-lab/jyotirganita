# tests/conformance/

Contracts every method of the registry, regional profile and preset
satisfies, parametrised over the registry:

- `test_methods.py`: the engine protocol on a sampled year; `runs_from`
  refused the day before, naming it, and run on the day itself;
  `before_composition:<id>` before the composition date and none after;
  every procedure name resolves, every registered procedure is used or
  reserved, and each procedure datum has an authority test, a declared
  lack of a printed example, or a declaration that its implementation
  is pending;
  `base`/`layers` composition; the hybrid sunrise under a test-only
  provider; the day's rules (sunrise, carry, endings, intraday).
- `test_profiles_presets.py`: regional profiles, era records and
  time-standard records load; every name has an id and accepted Latin
  spellings; a fictitious second profile with its own era loads and
  produces calendar leaves with no code changed; every preset is
  complete once an observer is named and rejected without one; the
  effective composition date, the day before it flagged and nothing
  refused; every provisional convention or name table with its reason
  and flag.
- `test_modern_presets.py`, `test_search.py`: the modern presets and the
  inverse search.
