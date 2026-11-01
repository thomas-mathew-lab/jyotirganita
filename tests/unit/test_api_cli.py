"""The API, ``--set`` and the record subcommands.

The refusals of ``--set`` (an unknown key; ``method``, ``composed``,
``runs_from`` and a datum key, refused by design; a procedure slot no
engine overrides; a time standard a siddhantic preset cannot take), each
naming its field before any day is computed; an override entering the
configuration hash and nothing else; the intraday override's
``diagnostic:<id>`` flag; the derived fields absent without the option
and, with it, changing no other field; ``generate`` streaming in JDN
order and refusing a window before ``runs_from``; ``positions`` refusing
a body the method does not serve; ``eclipses`` refused under a
siddhantic configuration; the CLI's exit status and standard error for
each. The engine's output is evidence for nothing here.
"""

from __future__ import annotations

import dataclasses
import io
import json
from collections.abc import Iterator
from fractions import Fraction
from typing import Any

import pytest
from record_kit import DAY, GEOMETRIC, OBSERVER, REPO, config, line
from search_kit import config as search_config

from jyotirganita import api
from jyotirganita.config import open_config
from jyotirganita.core.types import (
    JDN,
    GregorianDate,
    JulianDate,
    ModernCivilInstant,
    Nadika,
    SiddhanticCivilInstant,
)
from jyotirganita.errors import Refusal
from jyotirganita.io import derived
from jyotirganita.io.cli import EXIT_REFUSED, main
from jyotirganita.io.dates import DateSyntaxError, parse_cli_instant

PAR = "parahita_kerala"
BASE = ["--preset", PAR, "--observer", OBSERVER, "--repo", str(REPO)]


def _refused(field: str, **sets: str) -> Refusal:
    from modern_kit import records

    with pytest.raises(Refusal) as info:
        open_config(REPO, PAR, OBSERVER, records=records(), **sets)
    assert info.value.field == field, info.value
    return info.value


# --- --set ---------------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["method", "composed", "runs_from", "method.id"])
def test_set_refuses_by_design(key: str) -> None:
    e = _refused("set", **{key: "x"})
    assert "refused by design" in e.message and "conventions.month_rule" in e.message


def test_set_refuses_a_datum_key() -> None:
    e = _refused("set", **{"time_standards.ist.definition.rashtriya_panchanga_1959": "x"})
    assert "a datum key, refused by design" in e.message


def test_set_refuses_an_unknown_key() -> None:
    e = _refused("set", gati="x")
    assert "is not a --set key" in e.message and "output.scripts" in e.message


def test_a_procedure_slot_no_engine_overrides() -> None:
    e = _refused("procedure", **{"procedure.gati": "x"})
    assert "['sunrise']" in e.message


def test_a_siddhantic_preset_takes_no_civil_standard() -> None:
    e = _refused("time_standard", time_standard="ist")
    assert "derived_ut" in e.message


def test_unknown_output_selection() -> None:
    _refused("output", **{"output.elements": "tithi,moonrise"})
    _refused("output", **{"output.scripts": "klingon"})


def test_an_override_enters_the_hash_and_a_default_does_not() -> None:
    base = config(PAR)
    same = config(PAR, **{"conventions.month_rule": "aparahna_parts"})
    other = config(PAR, **{"conventions.month_rule": "following_day"})
    assert same.config_hash == base.config_hash and same.overrides == {}
    assert other.config_hash != base.config_hash
    assert other.overrides == {"conventions.month_rule": "following_day"}
    assert other.resolved.config["overrides"] == {"conventions.month_rule": "following_day"}


def test_output_elements_selects_the_occurrence_leaves() -> None:
    cfg = config(PAR, **{"output.elements": "nakshatra,tithi"})
    doc = json.loads(line(cfg, DAY))
    assert cfg.elements == ("tithi", "nakshatra")
    assert "tithi" in doc and "nakshatra" in doc and "yoga" not in doc and "karana" not in doc
    assert cfg.overrides == {"output.elements": "tithi,nakshatra"}


def test_intraday_override_flags_every_record() -> None:
    cfg = config(PAR, intraday="full_evaluation")
    recs = list(api.generate(cfg, DAY, DAY.plus_days(1)))
    assert all("diagnostic:diagnostic.full_evaluation" in r["flags"] for r in recs)
    assert cfg.overrides == {"intraday": "full_evaluation"}


def test_the_search_shares_the_configuration() -> None:
    a = search_config(PAR, intraday="full_evaluation")
    b = config(PAR, intraday="full_evaluation")
    assert type(a) is type(b) and a.config_hash == b.config_hash
    assert a.diagnostic == b.diagnostic and a.provenance()["overrides"] == b.overrides


# --- the derived fields ---------------------------------------------------------------------


def _without_derived(text: str) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(text)
    doc.pop("derived_ut", None)
    doc.pop("derived_tt", None)
    doc["flags"] = [f for f in doc["flags"] if f != "provisional:derived_ut.time_reckoning"]
    doc["provenance"].pop("derived", None)
    return doc


def test_no_derived_field_without_the_option() -> None:
    doc = json.loads(line(config(PAR), DAY))
    assert "derived_ut" not in doc and "derived_tt" not in doc
    assert "derived" not in doc["provenance"]


def test_the_derived_option_changes_no_other_field() -> None:
    cfg = config(PAR)
    plain = line(cfg, DAY)
    derived = line(cfg, DAY, "mean", "smh2016")
    doc = json.loads(derived)
    assert doc["derived_ut"]["time_reckoning"] == {"value": "mean", "basis": "caller"}
    assert doc["derived_tt"]["delta_t_model"] == "smh2016"
    assert json.dumps(_without_derived(derived), sort_keys=True) == json.dumps(
        json.loads(plain), sort_keys=True
    )
    assert doc["config_hash"] == json.loads(plain)["config_hash"]


@pytest.mark.parametrize(
    ("ut", "tt", "field"),
    [
        ("solar", None, "derived_ut"),
        ("apparent:modern:parahita_kerala", None, "derived_ut"),
        ("apparent:modern:modern_smh", None, "derived_ut"),
        ("apparent:nowhere", None, "derived_ut"),
        (None, "smh2016", "derived_tt"),
        ("mean", "no_such_model", "derived_tt"),
        ("mean", "constant", "derived_tt"),
    ],
)
def test_derived_refusals(ut: str | None, tt: str | None, field: str) -> None:
    with pytest.raises(Refusal) as info:
        api.day(config(PAR), DAY, derived_ut=ut, derived_tt=tt)
    assert info.value.field == field


def test_derived_refused_under_a_modern_preset_and_a_text_units_place() -> None:
    with pytest.raises(Refusal) as info:
        api.records(config("modern_iers"), derived_ut="mean")
    assert info.value.field == "derived_ut" and "modern preset" in info.value.message
    with pytest.raises(Refusal) as info:
        api.records(config("suryasiddhanta_text"), derived_ut="mean")
    assert "modern longitude" in info.value.message


def test_text_bhujantara_refused_where_the_carry_is_deferred(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # no preset defers its carry; a deferral datum (deferred.*), kept for
    # a text that defers, applies no bhujāntara, so the text's own equation cannot be named
    cfg = config("suryasiddhanta_text")
    procs = cfg.run.resolved.procedures
    rec = procs["carry.bhujantara"]
    deferred = dataclasses.replace(rec, raw={**rec.raw, "procedure": "deferred.pending_keying"})
    monkeypatch.setitem(procs, "carry.bhujantara", deferred)
    with pytest.raises(Refusal) as info:
        derived._eot_source(cfg, derived.TEXT_BHUJANTARA)
    assert info.value.field == "derived_ut" and "deferred" in info.value.message


def test_geometric_sunrise_refusals_name_the_procedure_and_both_options() -> None:
    # served under the Kerala presets, its era years spliced and its sunset
    # the modern engine's (tests/unit/test_geometric_kerala.py)
    assert (
        "diagnostic:era_years.text_sunrise"
        in config(PAR, **{"procedure.sunrise": GEOMETRIC}).diagnostic
    )
    hybrid = config("aryabhatiya_text", **{"procedure.sunrise": GEOMETRIC})
    with pytest.raises(Refusal) as info:
        api.records(hybrid, derived_ut="apparent:modern:modern_smh")
    assert info.value.field == "derived_ut"
    assert "--derived-ut apparent:modern:modern_smh" in info.value.message
    assert f"procedure.sunrise={GEOMETRIC}" in info.value.message


@pytest.mark.parametrize("preset", [PAR, "aryabhatiya_text"])
def test_a_modern_equation_refused_where_the_text_applies_its_own(preset: str) -> None:
    # the text's bhujāntara is inside the sunrise offset (io/derived.py docstring): a modern E
    # on top would apply the equation of time twice
    with pytest.raises(Refusal) as info:
        api.records(config(preset), derived_ut="apparent:modern:modern_smh")
    assert info.value.field == "derived_ut"
    assert "twice" in info.value.message and "text_bhujantara" in info.value.message


# --- generate, day, positions, sankrantis, eclipses -----------------------------------------


def test_generate_streams_in_jdn_order() -> None:
    cfg = config(PAR)
    it = api.generate(cfg, DAY, DAY.plus_days(2))
    assert isinstance(it, Iterator)
    assert [r["dates"]["jdn"] for r in it] == [DAY.value, DAY.value + 1, DAY.value + 2]
    assert list(api.generate(cfg, DAY, DAY.plus_days(-1))) == []


def test_tagged_dates_and_runs_from() -> None:
    cfg = config(PAR)
    g = api.day(cfg, GregorianDate(1954, 8, 17))
    j = api.day(cfg, JulianDate(1954, 8, 4))
    assert g["dates"] == j["dates"] and g["dates"]["jdn"] == DAY.value
    with pytest.raises(Refusal) as info:
        list(api.generate(cfg, cfg.runs_from.plus_days(-1), cfg.runs_from))
    assert info.value.field == "date" and "runs_from" in info.value.message


def test_positions_at_an_instant() -> None:
    cfg = config(PAR)
    inst = SiddhanticCivilInstant(DAY, Nadika(15), cfg.time_standard)
    out = api.positions(cfg, inst, ["sun", "moon", "ketu"])
    assert list(out["planets"]) == ["sun", "moon", "ketu"]
    at_start = api.positions(
        cfg, SiddhanticCivilInstant(DAY, Nadika(0), cfg.time_standard), ["sun"]
    )
    rec = api.day(cfg, DAY)
    assert at_start["planets"]["sun"] == rec["planets"]["sun"]
    with pytest.raises(Refusal) as info:
        api.positions(cfg, inst, ["uranus"])
    assert info.value.field == "bodies" and "serves" in info.value.message
    with pytest.raises(Refusal) as info:
        api.positions(cfg, ModernCivilInstant(DAY, 0.25, "ist"), ["sun"])
    assert info.value.field == "instant"


def test_sankrantis_are_the_record_leaves() -> None:
    cfg = config(PAR)
    first, last = DAY.plus_days(-3), DAY.plus_days(30)
    got = list(api.sankrantis(cfg, (first, last)))
    leaves = [
        (r["dates"]["jdn"], r["sankranti"])
        for r in api.generate(cfg, first, last)
        if r["sankranti"] is not None
    ]
    assert [(s["dates"]["jdn"], s["rasi_index"]) for s in got] == [
        (j, s["rasi_index"]) for j, s in leaves
    ]
    assert [s["instant"] for s in got] == [s["instant"] for _, s in leaves]


def test_eclipses_refused_under_a_siddhantic_configuration() -> None:
    with pytest.raises(Refusal) as info:
        api.eclipses(config(PAR), (DAY, DAY.plus_days(30)))
    assert info.value.field == "eclipses" and "modern preset" in info.value.message


def test_eclipses_flagged_provisional() -> None:
    cfg = config("modern_iers")
    first = JDN(2459700)  # a window of 2022 the run serves
    found = list(api.eclipses(cfg, (first, first.plus_days(200))))
    assert all("provisional:eclipse" in e["flags"] for e in found)
    for e in found:
        api.dumps(e)


# --- instants -------------------------------------------------------------------------------


def test_instant_syntax() -> None:
    s = parse_cli_instant("gregorian:1954-08-17+7/2nadika", "siddhantic", "text_local:x")
    assert s == SiddhanticCivilInstant(DAY, Nadika(Fraction(7, 2)), "text_local:x")
    m = parse_cli_instant("gregorian:2022-08-17T06:00/ist", "modern", "ist")
    assert m == ModernCivilInstant(JDN(2459809), 0.25, "ist")
    for text, kind in (
        ("gregorian:1954-08-17", "siddhantic"),
        ("gregorian:1954-08-17T06:00/ist", "siddhantic"),
        ("gregorian:2022-08-17+3nadika", "modern"),
        ("gregorian:2022-08-17T06:00/lmt", "modern"),
        ("1954-08-17+3nadika", "siddhantic"),
    ):
        with pytest.raises(DateSyntaxError):
            parse_cli_instant(text, kind, "ist")


# --- the CLI ----------------------------------------------------------------------------------


def _cli(args: list[str]) -> tuple[int, list[dict[str, Any]]]:
    out = io.BytesIO()
    code = main(args, out=out)
    return code, [json.loads(x) for x in out.getvalue().decode("ascii").splitlines()]


@pytest.mark.parametrize(
    ("extra", "field"),
    [
        (["--set", "method=aryabhatiya"], "set"),
        (["--set", "composed=1"], "set"),
        (["--set", "runs_from=jdn:0"], "set"),
        (["--set", "time_standards.ist.definition.rashtriya_panchanga_1959=x"], "set"),
        (["--set", "procedure.gati=x"], "procedure"),
        (["--set", "time_standard=ist"], "time_standard"),
        (["--set", "noequals"], "set"),
        # a key named like a parameter of open_config raised a TypeError
        (["--set", "records=x"], "set"),
        (["--set", "repo=x"], "set"),
        (["--set", "observer=x"], "set"),
    ],
)
def test_cli_set_refusals(extra: list[str], field: str, capsys: pytest.CaptureFixture[str]) -> None:
    code, lines = _cli(["day", *BASE, "--date", "jdn:2434972", *extra])
    assert code == EXIT_REFUSED and lines == []
    assert f"jyotirganita day: {field}: " in capsys.readouterr().err


def test_cli_untagged_date(capsys: pytest.CaptureFixture[str]) -> None:
    code, lines = _cli(["generate", *BASE, "--from", "1954-08-17", "--to", "jdn:2434973"])
    assert code == EXIT_REFUSED and lines == []
    assert "jyotirganita generate: from: " in capsys.readouterr().err


def test_cli_generate_writes_the_records(capsys: pytest.CaptureFixture[str]) -> None:
    code, lines = _cli(["generate", *BASE, "--from", "jdn:2434972", "--to", "jdn:2434973"])
    assert code == 0 and [x["dates"]["jdn"] for x in lines] == [2434972, 2434973]
    assert lines[0] == json.loads(line(config(PAR), DAY))


def test_cli_search_set_and_alias_together(
    tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    q = tmp_path / "q.json"
    q.write_text(
        json.dumps(
            {
                "reading_profile": "kerala_default",
                "window": {"from": {"jdn": 2167030}, "to": {"jdn": 2167031}},
                "constraints": [{"element": "weekday", "value": "Wednesday"}],
            }
        ),
        encoding="utf-8",
    )
    code, _ = _cli(
        [
            "search",
            *BASE,
            "--query",
            str(q),
            "--intraday",
            "full_evaluation",
            "--set",
            "intraday=linear_gati",
        ]
    )
    assert code == EXIT_REFUSED
    assert "jyotirganita search: set: intraday is given both" in capsys.readouterr().err


# --- the end of a run, and no partial output ----------------------------------------

#: the runs with a runs_to: the CI modern presets, and a siddhantic run on the geometric sunrise
ENDED_RUNS = (("modern_iers", ()), ("modern_smh", ()), ("aryabhatiya_text", (GEOMETRIC,)))


def _ended(preset: str, sunrise: tuple[str, ...]) -> Any:
    return config(preset, **({"procedure.sunrise": sunrise[0]} if sunrise else {}))


@pytest.mark.parametrize(("preset", "sunrise"), ENDED_RUNS)
def test_the_last_served_day_and_the_refusals_after_it(
    preset: str, sunrise: tuple[str, ...]
) -> None:
    # a day before runs_to whose record looks past it (the node's next day, the month's next
    # saṅkrānti) is refused naming the range, never a traceback (io/record.py serving)
    cfg = _ended(preset, sunrise)
    assert cfg.runs_to is not None
    with pytest.raises(Refusal) as info:
        api.day(cfg, cfg.runs_to.plus_days(1))
    assert info.value.field == "date" and "after the run's last day" in info.value.message
    jdn, refused = cfg.runs_to, 0
    while True:
        try:
            api.day(cfg, jdn)
        except Refusal as e:
            assert e.field == "date" and "cannot be served" in e.message, e.message
            assert "range" in e.message
            refused += 1
            jdn = jdn.plus_days(-1)
            continue
        break
    assert jdn.days_since(cfg.runs_from) > 0
    if refused:
        # the window ending past the last served day is refused before its first record
        with pytest.raises(Refusal) as info:
            api.generate(cfg, jdn, cfg.runs_to)
        assert info.value.field == "date"
        assert [r["dates"]["jdn"] for r in api.generate(cfg, jdn, jdn)] == [jdn.value]


def test_cli_refuses_the_run_end_without_a_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    cfg = config("modern_iers")
    assert cfg.runs_to is not None
    args = ["--preset", "modern_iers", "--observer", OBSERVER, "--repo", str(REPO)]
    code, lines = _cli(["day", *args, "--date", f"jdn:{cfg.runs_to.value}"])
    err = capsys.readouterr().err
    assert code == EXIT_REFUSED and lines == [] and "Traceback" not in err
    assert "jyotirganita day: date: " in err


def test_a_refused_window_leaves_no_jsonl_file(tmp_path: Any) -> None:
    # TT outside the IERS series inside the window: refused before the first line, and a file
    # already at the target keeps its bytes
    target = tmp_path / "out.jsonl"
    target.write_bytes(b"earlier\n")
    args = [*BASE, "--from", "jdn:2461289", "--to", "jdn:2461294", "--derived-ut", "mean"]
    code = main(["generate", *args, "--derived-tt", "iers", "--jsonl", str(target)])
    assert code == EXIT_REFUSED
    assert target.read_bytes() == b"earlier\n" and sorted(tmp_path.iterdir()) == [target]


def test_a_failure_part_way_leaves_no_partial_file(tmp_path: Any) -> None:
    from argparse import Namespace

    from jyotirganita.io.cli import _write

    def lines() -> Iterator[str]:
        yield "{}"
        raise Refusal("date", "part way")

    target = tmp_path / "out.jsonl"
    with pytest.raises(Refusal):
        _write(lines(), Namespace(jsonl=str(target)), None)
    assert list(tmp_path.iterdir()) == []
    assert _write(iter(["{}"]), Namespace(jsonl=str(target)), None) == 1
    assert target.read_bytes() == b"{}\n" and list(tmp_path.iterdir()) == [target]


def test_the_geometric_sunrise_without_an_observer_is_the_observers_refusal() -> None:
    from modern_kit import records

    with pytest.raises(Refusal) as info:
        open_config(REPO, PAR, None, records=records(), **{"procedure.sunrise": GEOMETRIC})
    assert info.value.field == "observer"
