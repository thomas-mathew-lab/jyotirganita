# tests/regression/

Change detectors on the engine's own earlier output. Every file says in
its header that it is a change detector; nothing is claimed from it.

One file per preset, `<preset>.jsonl`: one method-year of the preset's
calendar leaves, at Kozhikode except for the two Sūrya-siddhānta `_text`
presets, which run at `meridians/suryasiddhanta_lanka` (each file's
header names its observer), written by `tools/regression.py` (its
docstring gives the year and the form) and checked by
`test_regression.py`. A change to the engine's output shows here first,
and is made only with a changelog entry naming the file.
