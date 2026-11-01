"""A modern method run: the engine, its element stream and the calendar binding.

:class:`ModernRun` is the modern counterpart of ``methods/compose.py``'s
``MethodRun``: it binds one :class:`~jyotirganita.modern.engine.ModernConfig`
and one observer to the ``modern_de`` registry entry, builds the engine
and its element stream (``modern/source.py``) and gives the calendar layer
its :class:`~jyotirganita.calendar.day.Binding`:

- the day count is the **JDN difference** from the ``kali`` era record's
  epoch (the leaf ``jdn_difference``):
  the modern engine has no ahargaṇa;
- the month stream searches from the locator calibrated on the engine
  (``modern/source.py``, :func:`~jyotirganita.modern.source.mean_locator`);
  a ``sun: mean`` year start is not served;
- every record carries ``provisional_method`` while ``modern_de`` is
  provisional, and the observer's flags.

The provenance block is the engine's
(:meth:`ModernEngine.provenance`) with the method, the version, the
quantum and the SHA-256 of every data file the engine reads.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jyotirganita import __version__
from jyotirganita.calendar.day import JDN_DIFFERENCE, Binding
from jyotirganita.core.types import JDN
from jyotirganita.data.datum import Record
from jyotirganita.data.engine_parameters import EngineParameter
from jyotirganita.data.time_standards import TimeStandard
from jyotirganita.methods.registry import Method
from jyotirganita.modern.engine import ModernConfig, ModernEngine
from jyotirganita.modern.kernels import Ephemeris
from jyotirganita.modern.riseset import ModernObserver
from jyotirganita.modern.source import ModernSource, mean_locator
from jyotirganita.provenance.hashing import file_sha256, files_digest

__all__ = ["DAY_COUNT_ERA", "QUANTUM", "ModernRun"]

#: the era whose epoch the modern day count is counted from (reading 16)
DAY_COUNT_ERA = "kali"
QUANTUM = "modern.calendar_quantum"
_DATA_DIRS = (("jyotirganita", "data", "modern"),)
_FILES = (
    ("jyotirganita", "data", "engine_parameters.yaml"),
    ("jyotirganita", "data", "time_standards"),
)


class ModernRun:
    """A ``modern_de`` run bound to one configuration and observer (module docstring)."""

    def __init__(
        self,
        method: Method,
        config: ModernConfig,
        observer: ModernObserver,
        *,
        repo: Path,
        data: Mapping[str, Record],
        time_standards: Mapping[str, TimeStandard],
        parameters: Mapping[str, EngineParameter],
        ephemeris: Ephemeris | None = None,
    ) -> None:
        if method.engine != "modern":
            raise ValueError(f"{method.id} is not a modern method")
        self.method = method
        self.config = config
        self.engine = ModernEngine(
            config,
            observer,
            data=data,
            time_standards=time_standards,
            parameters=parameters,
            ephemeris=ephemeris,
        )
        status = ("provisional_method",) if method.status == "provisional" else ()
        self.source = ModernSource(self.engine, method.id, parameters[QUANTUM], status)
        self.binding = Binding(
            method.id,
            self.source,
            mean_locator(self.engine),
            False,
            self.engine,
            DAY_COUNT_ERA,
            JDN_DIFFERENCE,
            self.source.runs_from,
            clock=True,
        )
        self.provenance = self._provenance(repo, parameters)

    @property
    def runs_from(self) -> JDN:
        """The first civil day the run serves (the components' ranges)."""
        return self.source.runs_from

    @property
    def runs_to(self) -> JDN:
        """The last civil day the run serves."""
        return self.source.runs_to

    def _provenance(self, repo: Path, parameters: Mapping[str, EngineParameter]) -> dict[str, Any]:
        paths: list[Path] = []
        for parts in _DATA_DIRS:
            paths.extend(sorted(repo.joinpath(*parts).glob("*.yaml")))
        for parts in _FILES:
            p = repo.joinpath(*parts)
            paths.extend(sorted(p.glob("*.yaml")) if p.is_dir() else [p])
        files = {p.relative_to(repo).as_posix(): file_sha256(p) for p in paths}
        names = (
            QUANTUM,
            "modern.light_time_iterations",
            "modern.cio_locator_step",
            "modern.root.scan_step",
            "modern.riseset.scan_step",
            "modern.root.tolerance",
            "modern.root.iteration_cap",
        )
        return {
            **self.engine.provenance(),
            "version": __version__,
            "method_id": self.method.id,
            "method_status": self.method.status,
            "runs_from": self.runs_from.value,
            "runs_to": self.runs_to.value,
            "range": self.engine.range_text(),
            "day_count": {"era": DAY_COUNT_ERA, "leaf": JDN_DIFFERENCE},
            "data_files": files,
            "parameters_sha256": files_digest(files.items()),
            "engine_parameters": {k: str(parameters[k].value) for k in names},
        }
