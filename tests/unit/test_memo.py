"""The bounded per-run memo (``core/memo.py``)."""

from __future__ import annotations

import pytest

from jyotirganita.core.memo import MEMO_DAYS, DayMemo


def test_keeps_the_most_recently_used_up_to_its_capacity() -> None:
    m: DayMemo[int, int] = DayMemo()
    for k in range(MEMO_DAYS + 5):
        m[k] = k * k
    assert len(m) == MEMO_DAYS
    assert 4 not in m and 5 in m and m.get(MEMO_DAYS + 4) == (MEMO_DAYS + 4) ** 2


def test_a_read_renews_an_entry() -> None:
    m: DayMemo[int, str] = DayMemo()
    for k in range(MEMO_DAYS):
        m[k] = str(k)
    assert m[0] == "0"  # 0 is now the most recent; 1 is the oldest
    m[MEMO_DAYS] = "new"
    assert 0 in m and 1 not in m


def test_none_entries_are_held_and_the_width_scales_per_day() -> None:
    m: DayMemo[str, None] = DayMemo(per_day=3)
    m["a"] = None
    assert "a" in m and m["a"] is None and m.capacity == 3 * MEMO_DAYS
    with pytest.raises(ValueError):
        DayMemo(per_day=0)
