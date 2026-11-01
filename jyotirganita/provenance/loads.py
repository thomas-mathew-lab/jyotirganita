"""The set of data files loaded in this process.

A tier record of ``reports/test_summary.json`` hashes the data files its
tests loaded, and a record's ``parameters_sha256`` hashes the files its
configuration loaded. Loaders call
:func:`note_loaded`; the test plugin reads :func:`loaded_data_files` at the
end of a run. Only files under the package's ``data/`` directory are kept.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["DATA_ROOT", "loaded_data_files", "note_loaded", "reset_loaded"]

DATA_ROOT = (Path(__file__).resolve().parent.parent / "data").resolve()

_LOADED: set[Path] = set()


def note_loaded(path: Path) -> None:
    """Record that ``path`` was loaded, if it lies under the package's data root."""
    p = Path(path).resolve()
    if p.is_relative_to(DATA_ROOT):
        _LOADED.add(p)


def loaded_data_files() -> list[Path]:
    """The data files loaded so far, sorted."""
    return sorted(_LOADED)


def reset_loaded() -> None:
    """Forget the recorded loads (the test plugin calls it at session start)."""
    _LOADED.clear()
