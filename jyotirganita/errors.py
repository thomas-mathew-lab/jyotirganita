"""The engine's one refusal type for a caller's request.

A configuration, an override, a window, a query or a profile the engine
cannot serve is refused with :class:`Refusal`, which names the field it
concerns (``preset``, ``observer``, ``set``, ``conventions.month_rule``,
``window.from``, ``constraints[2].value``, ...) and what the engine offers
instead, before any day is computed. The search's ``SearchError`` is this
class under its earlier name (``search/errors.py``).
"""

from __future__ import annotations

__all__ = ["Refusal"]


class Refusal(ValueError):
    """A request the engine refuses, with the field named."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message
