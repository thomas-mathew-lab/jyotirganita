"""The inverse search.

``search(config, query)`` returns every civil day of the query's window on
which its elements hold, as :class:`~jyotirganita.search.results.Candidate`
objects in JDN order, of class ``match`` or (under ``near_miss``)
``near_miss``. ``config`` is a preset opened at an observer
(:func:`open_search`); ``query`` a query document (a mapping, as read
from YAML or JSON) or a compiled :class:`~jyotirganita.search.query.Query`.
The query is compiled, and every refusal raised, before the iterator is
returned. The staged path (``search/stages.py``) is the default; the
brute path (``search/brute.py``) is the reference, selected with
``brute=True``.

No ``math``, ``numpy`` or ``decimal`` import.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from jyotirganita.search.config import SearchConfig, open_search
from jyotirganita.search.errors import SearchError
from jyotirganita.search.query import Query, compile_query
from jyotirganita.search.results import Candidate

__all__ = ["Candidate", "Query", "SearchConfig", "SearchError", "open_search", "search"]


def search(
    config: SearchConfig, query: Query | Mapping[str, Any], *, brute: bool = False
) -> Iterator[Candidate]:
    """The candidates of ``query`` under ``config`` (module docstring)."""
    from jyotirganita.search.brute import brute as run_brute
    from jyotirganita.search.stages import staged

    # a compiled query is compiled again under this configuration: its window and its
    # constraints were checked against the one it was compiled for
    compiled = compile_query(query.doc if isinstance(query, Query) else query, config)
    if brute:
        return run_brute(config, compiled)
    return staged(config, compiled)
