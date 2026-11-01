"""The configuration a search runs under: a preset at an observer.

The search takes the one configuration object the records and the API
take, :class:`~jyotirganita.config.RunConfig` (``SearchConfig`` is its
earlier name), opened by :func:`~jyotirganita.config.open_config`.
:func:`open_search` is a thin call to it that keeps its keyword
arguments as aliases of their ``--set`` keys: ``month_rule`` of
``conventions.month_rule``, ``options`` (era → year-start option) of
``conventions.era.<era>.year_start``, ``intraday`` of ``intraday`` and
``procedures`` (slot → id) of ``procedure.<slot>``; ``sets`` carries any
other ``--set`` pair, and a key given both ways is a hard error
(field ``set``). Every refusal is a :class:`SearchError` naming the
field (``preset``, ``observer``, ``month_rule``, ``options``,
``intraday``, ``procedure``, ``set``, ...).

No ``math``, ``numpy`` or ``decimal`` import.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from jyotirganita.config import (
    INTRADAY_NAMES,
    PROBE_DAYS,
    RunConfig,
    check_set_keys,
    open_config,
)
from jyotirganita.data.datum import Records
from jyotirganita.search.errors import SearchError

__all__ = ["INTRADAY_NAMES", "PROBE_DAYS", "SearchConfig", "aliased", "open_search"]

SearchConfig = RunConfig


def aliased(
    *,
    month_rule: str | None = None,
    options: Mapping[str, str] | None = None,
    intraday: str | None = None,
    procedures: Mapping[str, str] | None = None,
    sets: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """The ``--set`` pairs the keyword aliases and ``sets`` name together (module docstring)."""
    out = dict(sets or {})
    named: list[tuple[str, str]] = []
    if month_rule is not None:
        named.append(("conventions.month_rule", month_rule))
    for era, option in (options or {}).items():
        named.append((f"conventions.era.{era}.year_start", option))
    if intraday is not None:
        named.append(("intraday", intraday))
    for slot, pid in (procedures or {}).items():
        named.append((f"procedure.{slot}", pid))
    for key, value in named:
        if key in out:
            raise SearchError("set", f"{key} is given both by --set and by its alias")
        out[key] = value
    return out


def open_search(
    repo: Path,
    preset_id: str,
    observer: str | None,
    *,
    month_rule: str | None = None,
    options: Mapping[str, str] | None = None,
    intraday: str | None = None,
    procedures: Mapping[str, str] | None = None,
    sets: Mapping[str, str] | None = None,
    records: Records | None = None,
) -> RunConfig:
    """Open ``preset_id`` at ``observer`` for the search (module docstring)."""
    pairs = aliased(
        month_rule=month_rule,
        options=options,
        intraday=intraday,
        procedures=procedures,
        sets=sets,
    )
    # before the call: a key ``records`` would meet the keyword as a TypeError
    check_set_keys(pairs)
    return open_config(repo, preset_id, observer, records=records, **pairs)
