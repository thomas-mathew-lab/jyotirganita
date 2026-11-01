"""Every refusal at the API and the CLI is a :class:`Refusal`.

The API promises that every refusal is a :class:`~jyotirganita.errors.Refusal`
naming the field (``api.py``), and the CLI prints a refusal and exits
with ``EXIT_REFUSED`` (``io/cli.py``). A code review found five classes
that escaped as tracebacks: a kernel not fetched (``KernelError``),
a mean-Sun year start under a method with no text's mean Sun (``ProfileError``), an engine's refusal
of a quantity (F6's class,
``EngineRefusal``; whether the Sūrya-siddhānta presets should serve a
longitude off sunrise is F6's substance, not settled here), a civil
standard probed on a day it was not in force (``OutOfForce``), an
output directory that does not exist (``FileNotFoundError``), and the
days before a Kerala preset's first month start (``ValueError``).
One test per class. No printed value enters here.
"""

from __future__ import annotations

from typing import Any

import pytest
from modern_kit import records
from record_kit import REPO

from jyotirganita import api
from jyotirganita.config import open_config
from jyotirganita.core.types import JDN, Nadika, SiddhanticCivilInstant
from jyotirganita.errors import Refusal
from jyotirganita.io.cli import EXIT_REFUSED, main
from jyotirganita.modern.kernels import Ephemeris, KernelError

PLACE = "kerala/thrissur"
#: a civil day of 1990 and one of 1850 (Gregorian 1990-01-01, 1850-01-01)
DAY_1990, DAY_1850 = JDN(2447893), JDN(2396759)


def _refused(f: Any, *args: Any, **kw: Any) -> Refusal:
    with pytest.raises(Refusal) as info:
        f(*args, **kw)
    return info.value


def test_kernel_not_fetched_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """F3: the kernel's error names the kernel and the fetch, as a refusal of ``kernel``."""

    def absent(cls: type[Ephemeris], /, kernel_id: str, **kw: Any) -> Ephemeris:
        raise KernelError(f"kernel {kernel_id!r} is not fetched")

    monkeypatch.setattr(Ephemeris, "open", classmethod(absent))
    r = _refused(open_config, REPO, "modern_smh", PLACE, records=records())
    assert r.field == "kernel" and "not fetched" in r.message


def test_mean_sun_year_start_without_a_mean_sun_is_refused_at_open() -> None:
    """F4: refused when the configuration opens, naming the ``--set`` key."""
    key = "conventions.era.kali.year_start"
    r = _refused(open_config, REPO, "drgganita_kerala", PLACE, records=records(), **{key: "mean"})
    assert r.field == key and "mean Sun" in r.message


def test_an_engine_refusal_is_a_refusal_of_the_instant(monkeypatch: pytest.MonkeyPatch) -> None:
    """F6's class: the engine's refusal of a quantity at an instant names ``at``.

    The Sūrya-siddhānta's latitude off sunrise, which raised it, is now
    ``not_modelled`` (group C of the 1.0.0 review, C5): a refusal is planted.
    """
    from jyotirganita.siddhantic.surya import SuryaRefusal

    cfg = open_config(REPO, "suryasiddhanta_kerala", PLACE, records=records())
    at = SiddhanticCivilInstant(DAY_1990, Nadika(10), cfg.time_standard)

    def refuse(*_: Any) -> Any:
        raise SuryaRefusal("planted: no latitude at this instant")

    monkeypatch.setattr(cfg.engine, "latitude", refuse)
    r = _refused(api.positions, cfg, at, ["moon"])
    assert r.field == "at" and "planted" in r.message


def test_suryasiddhanta_positions_off_sunrise_give_no_latitude() -> None:
    """C5: off sunrise the longitude is served and the latitude is ``not_modelled``."""
    cfg = open_config(REPO, "suryasiddhanta_kerala", PLACE, records=records())
    at = SiddhanticCivilInstant(DAY_1990, Nadika(10), cfg.time_standard)
    moon = api.positions(cfg, at, ["moon"])["planets"]["moon"]
    assert moon["latitude"] == "not_modelled"
    assert moon["sidereal_longitude"] is not None
    sunrise = SiddhanticCivilInstant(DAY_1990, Nadika(0), cfg.time_standard)
    assert api.positions(cfg, sunrise, ["moon"])["planets"]["moon"]["latitude"] != "not_modelled"


def test_a_civil_standard_is_checked_on_the_day_asked() -> None:
    """F7: ``ist`` opens under a modern preset; a day before it was in force is refused."""
    cfg = open_config(REPO, "modern_smh", PLACE, records=records(), time_standard="ist")
    assert api.day(cfg, DAY_1990)["dates"]["jdn"] == DAY_1990.value
    r = _refused(api.day, cfg, DAY_1850)
    assert r.field == "time_standard" and "ist" in r.message


def test_a_missing_output_directory_is_refused(
    tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """F8: the CLI refuses ``--jsonl`` in a directory that does not exist."""
    target = tmp_path / "absent" / "out.jsonl"
    argv = ["day", "--preset", "parahita_kerala", "--observer", PLACE]
    code = main([*argv, "--date", f"jdn:{DAY_1990.value}", "--jsonl", str(target)])
    assert code == EXIT_REFUSED
    assert "jsonl" in capsys.readouterr().err
    assert not target.parent.exists()


def test_a_day_before_the_first_month_start_is_refused() -> None:
    """F10: the days from ``runs_from`` to the first month start are refused, naming it."""
    cfg = open_config(REPO, "parahita_kerala", PLACE, records=records())
    early = cfg.runs_from.plus_days(4)
    r = _refused(api.day, cfg, early)
    assert r.field == "date" and "month" in r.message


@pytest.mark.parametrize(
    ("preset", "body", "word"),
    [("modern_smh", "jupiter", "mean longitude"), ("parahita_kerala", "rahu", "node")],
)
def test_a_mean_place_not_served_is_refused_by_name(preset: str, body: str, word: str) -> None:
    """F5, F5b: the internal mean-longitude call refuses as the public query does."""
    cfg = open_config(REPO, preset, PLACE, records=records())
    positions = api.records(cfg).positions
    r = _refused(positions.lon, body, DAY_1990, "mean")
    assert r.field == "position" and word in r.message
    if body == "rahu":
        r = _refused(positions.lon, "ketu", DAY_1990, "mean")
        assert r.field == "position"


def test_an_instant_past_the_day_names_the_length_in_nadikas() -> None:
    """The refusal prints the day's length as nāḍikā;vināḍikā,vipala, not an exact fraction."""
    cfg = open_config(REPO, "parahita_kerala", PLACE, records=records())
    at = SiddhanticCivilInstant(DAY_1990, Nadika(70), cfg.time_standard)
    r = _refused(api.positions, cfg, at, ["sun"])
    assert r.field == "instant"
    length = r.message.rpartition("0 to ")[2]
    assert "/" not in length and ";" in length, r.message
