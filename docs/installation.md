# Installation and tests

## Installing

Python 3.12 or later.

```
pip install jyotirganita
```

To work from a checkout instead:

```
git clone https://github.com/thomas-mathew-lab/jyotirganita.git
cd jyotirganita
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e .
```

The runtime dependencies are numpy, jplephem, PyYAML and jsonschema.
The data files ship inside the package, under `jyotirganita/data/`,
`jyotirganita/methods/` and `jyotirganita/regions/`.

## JPL kernels

The modern presets read a JPL planetary ephemeris. The engine never
downloads anything while it runs: a run that needs a kernel you have not
fetched is refused, and the message names the command below. Fetch each
kernel once:

```
jyotirganita fetch-kernel de440    # modern_iers and modern_smh, about 120 MB
jyotirganita fetch-kernel de441    # modern_antiquity, about 3.3 GB
jyotirganita fetch-kernel de440 --verify
```

The command downloads from JPL and checks the file's size and SHA-256
against `jyotirganita/data/tables/kernels.yaml`. The engine checks it
again before every load. By default the kernel is written into the installed package, under
`jyotirganita/data/ephemerides/`, and the engine looks there; so the
environment must be writable (a virtual environment is), each
environment holds its own copy, and `pip uninstall` leaves the file
behind. To keep the kernels elsewhere (a read-only installation, or one
copy shared by several environments), set `JYOTIRGANITA_KERNEL_DIR` to
an absolute path, both when you fetch and when you run:

```
export JYOTIRGANITA_KERNEL_DIR=/data/jpl-kernels
jyotirganita fetch-kernel de440
```

`fetch-kernel` creates the folder if needed. The kernel is checked
against its SHA-256 wherever it lies, so the folder changes no result
and is not recorded in a record. A leading `~` stands for your home
folder; an empty or other relative value is refused. The
siddhantic presets need no kernel, unless you ask one of them for the
modern geometric sunrise
(`--set procedure.sunrise=modern_geometric:<modern preset>`), which
reads local mean time: only `modern_smh` and `modern_antiquity` serve
it, and both end at the start of 2016.

## The pinned environment and the tests

The tests run in a pinned environment: every runtime and test
dependency is pinned with its hashes in `requirements/dev.lock`. The
build backend (setuptools 77.0.3 or later, `pyproject.toml`'s
`build-system`) is not pinned there; it builds the package and computes
nothing.

```
python3.12 -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r requirements/dev.lock
pip install --no-deps -e .
jyotirganita fetch-kernel de440
PYTHONHASHSEED=0 pytest
```

The suite takes about two hours on four cores. Collecting it takes a few
minutes on its own, because the fixtures are computed when they are
collected, so even a run of one test waits that long. It has three tiers:

| tier | how to run | what it needs |
|---|---|---|
| `ci` (the default) | `pytest` | DE440 |
| `de441` | `pytest --tier de441` | DE441 |
| `extras` | `pytest --tier extras` | `pip install -e .[swisseph]`; it holds no test in 1.0.0 |

A test that needs what a tier lacks carries that tier's marker and is
deselected, never skipped at run time.

What the tests check:

- `tests/authority/`: the worked examples the sources print. A worked
  example by the text's author or a pre-modern commentator must come
  out exactly, in the text's own units. A modern editor's decimal
  recomputation is matched to the editor's stated precision.
- `tests/crosscheck/`: published tables: the Indian Astronomical
  Ephemeris's ayanāṃśa polynomial and the fetched IERS and Hipparcos
  extracts. No comparison with independent software is in the suite
  yet.
- `tests/invariants/` and `tests/conformance/`: the internal
  redundancies of the texts (symmetries, totals, the same value stated
  twice) and the contract of every method and preset.
- `tests/regression/`: change detectors only, never evidence. One
  method-year of each preset's calendar leaves (the day's calendar
  fields, without the provenance block and the planets), compared
  exactly, so a change to any of those fields fails; they do not cover
  every field of a record.
- `tests/unit/`: the engine's parts.

`tools/regression.py` writes and checks the regression files, and
`tools/step_scan.py` and `tools/iae_comparison.py` are the tools some
tests load.

## Reproducibility

- The siddhantic engine, the calendar layer and the search compute with
  integers and fractions only, so their computed fields are identical
  on every platform. Two parts of a record are not: its `environment`
  block (Python version, platform, machine), which is informational and
  read by no comparison, and any value that comes from the modern
  engine (a hybrid sunrise, a modern preset), which is a float.
- The modern engine computes in IEEE-754 doubles through numpy and
  jplephem. Its results can differ between platforms in the last bits,
  so the tests that compare them with outside values use stated
  tolerances; the determinism tests and the regression files compare
  runs on one machine exactly. The
  reference platform is Linux (CPython 3.12, Debian bookworm). No
  cross-platform tolerance has been measured yet.
- No output depends on the wall clock, the locale, the time zone, the
  hash seed or the network. `tests/unit/test_determinism.py` checks this
  in fresh interpreters under several time zones, locales and hash
  seeds.
