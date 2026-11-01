"""Shared loaders for the search's tests: configurations, windows, round-trip queries.

Every configuration is a shipped preset opened at a Kerala place through
:func:`jyotirganita.search.open_search`, with the records loaded once
(``modern_kit.records``). :func:`own_query` builds the query a day's own
elements make: each value is read off the day's calendar record and the
engine's places (through the search's own day view), never typed into a
test. None of these is evidence for a method: the search has no authority tests yet.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

from modern_kit import records

from jyotirganita.core.types import JDN
from jyotirganita.data import engine_parameters
from jyotirganita.search import SearchConfig, open_search
from jyotirganita.search.evaluate import Evaluator, span_index
from jyotirganita.search.query import compile_query

REPO = Path(__file__).resolve().parents[1]
OBSERVER = "kerala/kozhikode"
#: the place each text's route serves (regions/*/places.yaml ``texts``)
OBSERVERS: Mapping[str, str] = {
    "suryasiddhanta_text": "meridians/suryasiddhanta_lanka",
    "suryasiddhanta_paramesvara_recension_text": "meridians/suryasiddhanta_lanka",
}
#: one preset per registered method the CI tier serves (modern_antiquity is the de441 tier's)
METHOD_PRESETS: Mapping[str, str] = {
    "aryabhatiya": "aryabhatiya_text",
    "parahita": "parahita_kerala",
    "drgganita": "drgganita_kerala",
    "suryasiddhanta": "suryasiddhanta_text",
    "suryasiddhanta_paramesvara_recension": "suryasiddhanta_paramesvara_recension_text",
    "modern_de": "modern_iers",
}
PLANETS = ("mercury", "venus", "mars", "jupiter", "saturn", "rahu", "ketu")
#: the element groups a round-trip query draws from
GROUPS = ("era", "solar", "weekday", "planet", "lunar")


#: the month rule where the convention set's default cannot run at that place (the preset's
#: header); none since the Dṛggaṇita has a sunset at the Kerala places
MONTH_RULES: Mapping[str, str] = {}


@cache
def config(preset: str, observer: str | None = None, intraday: str | None = None) -> SearchConfig:
    place = observer or OBSERVERS.get(preset, OBSERVER)
    rule = MONTH_RULES.get(preset) if observer is None else None
    return open_search(REPO, preset, place, month_rule=rule, intraday=intraday, records=records())


def window_doc(first: int, last: int) -> dict[str, Any]:
    return {"from": {"jdn": first}, "to": {"jdn": last}}


def served_span(cfg: SearchConfig) -> tuple[int, int]:
    """The days a seeded window may fall in: the step-scan range, cut to the run's."""
    params = engine_parameters.load()
    lo = max(params["search.floor"].value.numerator, cfg.runs_from.value)
    hi = params["search.horizon"].value.numerator
    if cfg.runs_to is not None:
        hi = min(hi, cfg.runs_to.value)
    # keep clear of the month stream's own edge near runs_from
    return lo + 400, hi - 400


def window_at(cfg: SearchConfig, u: float, length: int) -> tuple[int, int]:
    """The window of ``length`` days at the fraction ``u`` of the served span."""
    lo, hi = served_span(cfg)
    a = lo + int(u * (hi - lo - length))
    return a, a + length - 1


def _first_index(rows: Sequence[Mapping[str, Any]]) -> int:
    return int(rows[0]["index"])


def own_elements(cfg: SearchConfig, jdn: int) -> list[dict[str, Any]]:
    """Every constraint the day ``jdn`` satisfies, read off the day (module docstring)."""
    probe = compile_query(
        {
            "reading_profile": "kerala_default",
            "window": window_doc(jdn, jdn),
            "constraints": [{"element": "weekday", "value": 1}],
        },
        cfg,
    )
    ev = Evaluator(cfg, probe)
    v = ev.view(JDN(jdn))
    rec = v.record()
    out: list[dict[str, Any]] = []
    eras = rec["eras"]
    era = next((e for e in ("kollam", "saka", "kali") if isinstance(eras.get(e), Mapping)), None)
    if era is not None and "year" in eras[era]:
        out.append(
            {
                "element": "era_year",
                "era": era,
                "value": eras[era]["year"],
                "year_start": eras[era]["year_start"],
            }
        )
    out.append({"element": "era_day", "era": "kali", "value": ev.count(v)})
    if isinstance(rec.get("masa"), Mapping) and isinstance(rec["masa"]["day"], int):
        out.append({"element": "masa", "value": rec["masa"]["rasi_index"]})
        out.append({"element": "day_of_month", "value": rec["masa"]["day"]})
    out.append({"element": "weekday", "value": rec["weekday"]["index"]})
    sun = ev.lon("sun", JDN(jdn))
    out.append({"element": "sun_rasi", "value": span_index(sun, 12), "match": "at_sunrise"})
    if isinstance(rec.get("sankranti"), Mapping):
        out.append({"element": "sankranti_day", "value": rec["sankranti"]["rasi_index"]})
    for e in ("tithi", "nakshatra", "yoga"):
        out.append({"element": e, "value": _first_index(rec[e]), "match": "any_occurrence"})
    out.append({"element": "karana", "value": rec["karana"][0]["index"]})
    moon = ev.lon("moon", JDN(jdn))
    out.append({"element": "moon_rasi", "value": span_index(moon, 12), "match": "at_sunrise"})
    for body in PLANETS:
        if body not in ev.bodies:
            continue
        lam = ev.lon(body, JDN(jdn))
        out.append(
            {
                "element": "planet_rasi",
                "body": body,
                "value": span_index(lam, 12),
                "position": True,
                "match": "at_sunrise",
            }
        )
    lam = ev.lon("mercury", JDN(jdn))
    out.append(
        {
            "element": "planet_nakshatra",
            "body": "mercury",
            "value": span_index(lam, 27),
            "position": True,
            "match": "any_time_in_day",
        }
    )
    return out


def group_of(c: Mapping[str, Any]) -> str:
    e = str(c["element"])
    if e in ("era_year", "era_day"):
        return "era"
    if e in ("masa", "day_of_month", "sun_rasi", "sankranti_day", "ayana"):
        return "solar"
    if e in ("planet_rasi", "planet_nakshatra"):
        return "planet"
    if e == "weekday":
        return e
    return "lunar"


def miswrite(c: Mapping[str, Any]) -> dict[str, Any]:
    """The constraint with its value moved off the day's own (a record with one slip)."""
    out = dict(c)
    v = c["value"]
    cycles = {
        "weekday": 7,
        "masa": 12,
        "sun_rasi": 12,
        "moon_rasi": 12,
        "planet_rasi": 12,
        "planet_nakshatra": 27,
        "nakshatra": 27,
        "tithi": 30,
        "yoga": 27,
        "sankranti_day": 12,
        "karana": 60,
    }
    e = c["element"]
    if e in cycles:
        out["value"] = (int(v) + cycles[e] // 2 - 1) % cycles[e] + 1
    elif e == "day_of_month":
        out["value"] = int(v) + 10 if int(v) <= 15 else int(v) - 10
    elif e in ("era_year", "era_day"):
        out["value"] = int(v) + 3
    else:
        raise ValueError(f"no slip for {e}")
    return out


def query(
    constraints: Sequence[Mapping[str, Any]], first: int, last: int, **extra: Any
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "reading_profile": "kerala_default",
        "window": window_doc(first, last),
        "constraints": [dict(c) for c in constraints],
    }
    doc.update(extra)
    return doc


def frac(x: Any) -> Fraction:
    return Fraction(x["exact"]) if isinstance(x, Mapping) else Fraction(x)
