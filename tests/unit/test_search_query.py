"""The query's refusals and the near-miss mode.

Every malformed or unservable query is refused by
:func:`jyotirganita.search.search` itself, before it returns the iterator
(so before any day of the window is evaluated), with the field named,
in ``require`` and in ``report`` mode alike. The ``--set`` case is the
CLI's (``tests/unit/test_cli_search.py``). The planet a vākya set does
not key has no shipped vākya method; the refusal is tested on
the parahita run with a capability set from which the body is removed.

The near-miss tests: a record with one element miswritten returns its
true day as ``near_miss`` with the failed element and its margin under
``max_misses: 1`` and not without ``near_miss``; a full match is
``match`` under both. The staged-equals-brute invariant and the round
trip under both modes are ``tests/invariants/test_search_invariants.py``.
No printed value enters here.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping
from types import SimpleNamespace
from typing import Any

import pytest
from modern_kit import records
from search_kit import config, own_elements, query

from jyotirganita.core.types import JDN
from jyotirganita.search import SearchError, open_search, search
from jyotirganita.search.query import compile_query

PRESET = "parahita_kerala"
MODERN = "modern_iers"
#: a January of the Kollam era's fourth century under parahita (any served month would do)
FIRST, LAST = 2167024, 2167054


def _doc(*constraints: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    return query(constraints, FIRST, LAST, **extra)


def _refused(cfg: Any, doc: Mapping[str, Any]) -> SearchError:
    """The refusal ``search`` raises when called: no iterator, so no day evaluated."""
    with pytest.raises(SearchError) as info:
        search(cfg, doc)
    return info.value


#: (id, constraint, field the refusal names, a word of its message)
BAD_CONSTRAINTS: list[tuple[str, dict[str, Any], str, str]] = [
    ("unknown_element", {"element": "tithis", "value": 1}, "constraints[0].element", "tithis"),
    (
        "misspelled_name",
        {"element": "weekday", "value": "Wednesdy"},
        "constraints[0].value",
        "nearest ids",
    ),
    (
        "unlisted_spelling",
        {"element": "nakshatra", "value": "Makayiram"},
        "constraints[0].value",
        "nearest ids",
    ),
    ("index_out_of_range", {"element": "nakshatra", "value": 28}, "constraints[0].value", "28"),
    ("tithi_out_of_range", {"element": "tithi", "value": 31}, "constraints[0].value", "31"),
    (
        "day_of_month_out_of_range",
        {"element": "day_of_month", "value": 40},
        "constraints[0].value",
        "40",
    ),
    (
        "eclipse_under_siddhantic",
        {"element": "eclipse", "value": "lunar"},
        "constraints[0]",
        "eclipse",
    ),
    (
        "unknown_year_start",
        {"element": "era_year", "era": "kollam", "value": 396, "year_start": "mesha"},
        "constraints[0].year_start",
        "mesha",
    ),
    (
        "era_not_carried",
        {"element": "era_year", "era": "vikrama", "value": 1277},
        "constraints[0].era",
        "vikrama",
    ),
    (
        "era_year_out_of_range",
        {"element": "era_year", "era": "kollam", "value": -5},
        "constraints[0].value",
        "outside",
    ),
    (
        "era_day_out_of_range",
        {"element": "era_day", "era": "kali", "value": -5},
        "constraints[0].value",
        "outside",
    ),
    (
        "node_mean",
        {"element": "planet_rasi", "body": "rahu", "value": 1, "position": "mean"},
        "constraints[0].position",
        "node",
    ),
]


@pytest.mark.parametrize("mode", ["require", "report"])
@pytest.mark.parametrize(
    ("case", "constraint", "field", "word"), BAD_CONSTRAINTS, ids=[b[0] for b in BAD_CONSTRAINTS]
)
def test_constraint_refused_before_the_scan(
    case: str, constraint: dict[str, Any], field: str, word: str, mode: str
) -> None:
    cfg = config(PRESET)
    keep = {"element": "weekday", "value": 4}
    err = _refused(cfg, _doc({**constraint, "mode": mode}, keep))
    assert err.field.startswith(field), (case, err.field, err.message)
    assert word.lower() in err.message.lower() or word.lower() in err.field.lower(), (
        case,
        err.message,
    )


def test_window_before_runs_from_names_it() -> None:
    cfg = config(PRESET)
    start = cfg.runs_from.value
    for mode in ("require", "report"):
        doc = query([{"element": "weekday", "value": 4, "mode": mode}], start - 10, start + 10)
        err = _refused(cfg, doc)
        assert err.field == "window.from", err.field
        assert "runs_from" in err.message and str(start) in err.message, err.message


def test_window_leaving_the_kernel_or_delta_t_range() -> None:
    cfg = config(MODERN)
    assert cfg.runs_to is not None
    end = cfg.runs_to.value
    for mode in ("require", "report"):
        doc = query([{"element": "weekday", "value": 4, "mode": mode}], end - 10, end + 10)
        err = _refused(cfg, doc)
        assert err.field == "window.to", err.field
        assert str(end) in err.message, err.message


def test_mean_position_under_modern() -> None:
    cfg = config(MODERN)
    end = cfg.runs_to.value if cfg.runs_to is not None else 0
    for mode in ("require", "report"):
        c = {
            "element": "planet_rasi",
            "body": "jupiter",
            "value": 1,
            "position": "mean",
            "mode": mode,
        }
        err = _refused(cfg, query([c], end - 40, end - 20))
        assert err.field == "constraints[0].position", err.field


def test_place_without_coordinates_under_a_method_that_needs_them() -> None:
    with pytest.raises(SearchError) as info:
        open_search(
            config(MODERN).repo, MODERN, "meridians/suryasiddhanta_lanka", records=records()
        )
    assert info.value.field == "observer"
    assert "latitude and longitude" in info.value.message


def test_unknown_place_and_preset() -> None:
    repo = config(PRESET).repo
    with pytest.raises(SearchError) as info:
        open_search(repo, PRESET, "kerala/nowhere", records=records())
    assert info.value.field == "observer" and "kozhikode" in info.value.message
    with pytest.raises(SearchError) as info:
        open_search(repo, "no_such_preset", None, records=records())
    assert info.value.field == "preset"


def test_body_the_method_does_not_serve() -> None:
    """The vākya case on a capability set without Mars."""
    cfg = config(PRESET)
    caps = cfg.engine.capabilities
    stub_caps = SimpleNamespace(
        bodies=frozenset(b for b in caps.bodies if b != "mars"), node=caps.node
    )

    class Run:
        def __getattr__(self, name: str) -> Any:
            if name == "engine":
                return SimpleNamespace(capabilities=stub_caps)
            return getattr(cfg.run, name)

    stub = dataclasses.replace(cfg, run=Run(), profiles={})
    for mode in ("require", "report"):
        c = {"element": "planet_rasi", "body": "mars", "value": 1, "mode": mode}
        err = _refused(stub, _doc(c))
        assert err.field == "constraints[0].body" and "mars" in err.message


@pytest.mark.parametrize(
    ("doc_of", "field"),
    [
        (
            lambda: {
                "window": {"from": {"jdn": FIRST}, "to": {"jdn": LAST}},
                "constraints": [{"element": "weekday", "value": 4}],
            },
            "reading_profile",
        ),
        (
            lambda: {
                **_doc({"element": "weekday", "value": 4}),
                "reading_profile": "no_such_profile",
            },
            "reading_profile",
        ),
        (
            lambda: _doc({"element": "weekday", "value": 4}, near_miss={"max_misses": 0}),
            "near_miss.max_misses",
        ),
        (
            lambda: _doc({"element": "weekday", "value": 4}, near_miss={"max_misses": 2}),
            "near_miss.max_misses",
        ),
        (
            lambda: _doc(
                {"element": "weekday", "value": 4},
                {"element": "masa", "value": 10, "mode": "report"},
                near_miss={"max_misses": 2},
            ),
            "near_miss.max_misses",
        ),
        (lambda: {**_doc({"element": "weekday", "value": 4}), "constraints": []}, "constraints"),
        (lambda: query([{"element": "weekday", "value": 4}], LAST, FIRST), "window"),
    ],
    ids=[
        "no_profile",
        "unknown_profile",
        "max_misses_zero",
        "max_misses_over",
        "max_misses_over_report",
        "no_constraints",
        "window_reversed",
    ],
)
def test_query_level_refusals(doc_of: Callable[[], dict[str, Any]], field: str) -> None:
    err = _refused(config(PRESET), doc_of())
    assert err.field.startswith(field), (err.field, err.message)


def test_overlap_names_one_constraint_per_element() -> None:
    cfg = config(PRESET)
    doc = _doc(
        {"element": "tithi", "value": 11}, {"element": "overlap", "of": ["tithi", "nakshatra"]}
    )
    err = _refused(cfg, doc)
    assert err.field.startswith("constraints[1]"), err.field


def test_procedure_override_refused() -> None:
    with pytest.raises(SearchError) as info:
        open_search(
            config(PRESET).repo,
            PRESET,
            "kerala/kozhikode",
            procedures={"gati": "x"},
            records=records(),
        )
    assert info.value.field == "procedure"


# --- near misses -------------------------------------------------------------------------


def _record(day: int) -> list[dict[str, Any]]:
    """A record of ``day``: its masa, weekday and nakṣatra (read off the day)."""
    own = {c["element"]: c for c in own_elements(config(PRESET), day)}
    return [own["masa"], own["weekday"], own["nakshatra"]]


DAY = 2167034


def test_one_slip_is_a_near_miss_with_its_margin() -> None:
    cfg = config(PRESET)
    rec = _record(DAY)
    slipped = [rec[0], {**rec[1], "value": rec[1]["value"] % 7 + 1}, rec[2]]
    loose = {c.jdn: c for c in search(cfg, _doc(*slipped, near_miss={"max_misses": 1}))}
    assert DAY in loose and loose[DAY].cls == "near_miss"
    (miss,) = loose[DAY].misses
    assert miss["index"] == 1 and miss["element"] == "weekday"
    assert miss["margin"] == {"unit": "day", "value": 1}
    assert DAY not in {c.jdn for c in search(cfg, _doc(*slipped))}


def test_full_match_is_match_under_both() -> None:
    cfg = config(PRESET)
    rec = _record(DAY)
    exact = {c.jdn: c for c in search(cfg, _doc(*rec))}
    loose = {c.jdn: c for c in search(cfg, _doc(*rec, near_miss={"max_misses": 1}))}
    assert exact[DAY].cls == "match" and loose[DAY].cls == "match"
    assert not loose[DAY].misses


def test_compile_is_deterministic() -> None:
    cfg = config(PRESET)
    doc = _doc(
        {"element": "weekday", "value": "Wednesday"},
        {"element": "nakshatra", "value": ["rohini", 5]},
    )
    a, b = compile_query(doc, cfg), compile_query(dict(doc), cfg)
    assert a.sha256 == b.sha256
    assert a.first == JDN(FIRST) and a.last == JDN(LAST)


def test_place_whose_route_does_not_serve_the_text() -> None:
    with pytest.raises(SearchError) as info:
        open_search(
            config(PRESET).repo,
            "suryasiddhanta_text",
            "meridians/lanka",
            records=records(),
        )
    assert info.value.field == "observer" and "suryasiddhanta" in info.value.message


def test_month_rule_the_place_cannot_serve(monkeypatch: pytest.MonkeyPatch) -> None:
    """A month rule the place serves on no day is refused before the scan, naming the others.

    No preset meets it since the Dṛggaṇita has a sunset; the
    aparāhna rule is made to find no sunset (a stand-in, no text's case).
    """
    from jyotirganita.calendar import months

    def no_sunset(*_: object) -> JDN:
        raise months.MonthRuleNotModelled("aparahna_parts needs the day's sunrise and sunset")

    rule = months.MONTH_RULES["aparahna_parts"]
    monkeypatch.setitem(
        months.MONTH_RULES, "aparahna_parts", dataclasses.replace(rule, fn=no_sunset)
    )
    with pytest.raises(SearchError) as info:
        open_search(config(PRESET).repo, "drgganita_kerala", "kerala/kozhikode", records=records())
    assert info.value.field == "month_rule" and "following_day" in info.value.message


def test_era_year_no_day_of_the_window_carries() -> None:
    """Review N8: a year beyond the window is refused where the run's range is open."""
    cfg = config(PRESET)
    assert cfg.runs_to is None
    own = next(c for c in own_elements(cfg, DAY) if c["element"] == "era_year")
    keep = {"element": "weekday", "value": 4}
    assert search(cfg, _doc(own, keep)) is not None
    for year in (own["value"] + 50, own["value"] - 50):
        for mode in ("require", "report"):
            err = _refused(cfg, _doc({**own, "value": year, "mode": mode}, keep))
            assert err.field == "constraints[0].value", err.field
            assert "window spans" in err.message, err.message
