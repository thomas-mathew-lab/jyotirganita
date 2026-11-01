"""The reference path: every day of the window through the day view.

Slow and simple: each civil day of the window is evaluated by
:meth:`Evaluator.evaluate` and kept when it is a candidate. The staged
path (``search/stages.py``) must return exactly these candidates; the
invariant test is how the staged path is known to be right. The brute
path has no limit but the run's own range.

No ``math``, ``numpy`` or ``decimal`` import.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from jyotirganita.core.types import JDN
from jyotirganita.search.config import SearchConfig
from jyotirganita.search.evaluate import Evaluator
from jyotirganita.search.query import Query
from jyotirganita.search.results import Candidate

__all__ = ["brute", "search_provenance"]


def search_provenance(
    config: SearchConfig,
    query: Query,
    path: str,
    stages: Sequence[Mapping[str, Any]],
    derived: Sequence[str] = (),
    planets: str | None = None,
) -> dict[str, Any]:
    """The candidates' provenance block: the run's, and the search's own."""
    out = config.provenance()
    out["search"] = {
        "reading_profile": query.profile.id,
        "reading_profile_file": query.profile.path,
        "query_sha256": query.sha256,
        "window": {"from_jdn": query.first.value, "to_jdn": query.last.value},
        "near_miss": {"max_misses": query.max_misses} if query.near_miss else None,
        "path": path,
        "derived_records": list(derived),
        "planet_pruning": planets,
        "stages": [dict(s) for s in stages],
    }
    return out


def brute(config: SearchConfig, query: Query) -> Iterator[Candidate]:
    """Every candidate of the window, in JDN order, by full evaluation of each day."""
    ev = Evaluator(config, query)
    days = query.last.days_since(query.first) + 1
    ev.provenance = search_provenance(
        config, query, "brute", [{"stage": "full_evaluation", "days_in": days}]
    )
    for j in range(query.first.value, query.last.value + 1):
        c = ev.evaluate(JDN(j))
        if c is not None:
            yield c
