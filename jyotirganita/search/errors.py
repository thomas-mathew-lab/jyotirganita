"""The search's one error type.

Every refusal names the field it concerns (``window.from``,
``constraints[2].value``, ``observer``, ...) and the range or capability
the method offers, and is raised before any day is computed. An empty
result is then a finding, never a symptom of a query the engine could not
serve. ``SearchError`` is the engine's :class:`~jyotirganita.errors.Refusal`
under its own name, so that the records, the API and the search refuse
alike.
"""

from __future__ import annotations

from jyotirganita.errors import Refusal

__all__ = ["SearchError"]

SearchError = Refusal
