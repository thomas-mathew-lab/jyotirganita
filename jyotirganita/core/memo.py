"""The bounded per-run memo of day results.

A run computes each civil day's result once and keeps it while the days
around it are asked for: the calendar layer asks for the neighbours of a
day (the kṣaya and vṛddhi flags, the previous and next day's endings), the
month rule for the days near a month's first day, the record for the next
day's longitudes. :class:`DayMemo` keeps the most recently used entries up
to its capacity and forgets the least recently used beyond it, so that a
stream of any length holds a bounded window in memory.

**What it may change.** Nothing a run returns: every memo holds a pure
function of its key within one run (the run is built from one
configuration and never altered), so an entry forgotten is recomputed to
the same value; the width can change only how much is computed twice.
That is why ``MEMO_DAYS`` is structural, stated here, and not an engine
parameter (the search's widths pass the same test). Every memo belongs to
the run it serves: there is no module-level cache of a result, so nothing
is shared across configurations; a run, and with it its memos, is made per
configuration hash. The partial-versus-batch
identity of ``tests/unit/test_determinism.py`` shows that a day's record
does not depend on where its window starts.

``MEMO_DAYS``, a thousand days, is wider than every neighbour the
calendar layer and the month rule ask for (a month's span and the
saṅkrānti search around it are within a few months of the day); a memo of
several entries a day (the record's longitudes, one per body and instant)
is sized as ``MEMO_DAYS`` times its entries per day.
"""

from __future__ import annotations

from collections.abc import Hashable

__all__ = ["MEMO_DAYS", "DayMemo"]

#: the days a memo keeps: structural, it changes only what is computed twice (docstring)
MEMO_DAYS = 1000


class DayMemo[K: Hashable, V]:
    """A least-recently-used memo of at most ``MEMO_DAYS × per_day`` entries."""

    __slots__ = ("_data", "capacity")

    def __init__(self, per_day: int = 1) -> None:
        if per_day < 1:
            raise ValueError(f"a memo keeps at least one entry a day, not {per_day}")
        self.capacity = MEMO_DAYS * per_day
        self._data: dict[K, V] = {}

    def __contains__(self, key: K) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, key: K) -> V:
        v = self._data.pop(key)
        self._data[key] = v  # now the most recently used
        return v

    def get(self, key: K) -> V | None:
        """The entry, or None when it is not held (an entry is never None: use ``in``)."""
        if key not in self._data:
            return None
        return self[key]

    def __setitem__(self, key: K, value: V) -> None:
        self._data.pop(key, None)
        self._data[key] = value
        while len(self._data) > self.capacity:
            del self._data[next(iter(self._data))]
