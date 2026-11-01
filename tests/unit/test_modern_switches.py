"""The modern engine's four ``--set`` switches.

``modern.sunrise_event`` (``<reference>/<refraction>/<dip>``, the dip
``none`` or ``<kind>:<height>m``, optionally ``@<height>m`` for the
observer's height), ``modern.ayanamsa`` (``<id>/<equinox>`` and, for
``citra_180``, ``aberration`` or ``no_aberration``, for the custom
polynomials the coefficients in arcseconds), ``modern.delta_t`` (a model
id, ``constant:<seconds>``) and ``modern.node`` (``mean``, ``osculating``).
Each defaults to the preset's value; a switched run carries the switch in
its provenance (the override and the engine's own component) and the flag
``diagnostic:modern.<switch>`` on every record. Under a siddhantic preset
the switches are refused. Engine output only; no printed value enters here.
"""

from __future__ import annotations

from typing import Any

import pytest
from modern_kit import records
from record_kit import REPO

from jyotirganita import api
from jyotirganita.config import open_config
from jyotirganita.core.types import JDN
from jyotirganita.errors import Refusal

PRESET = "modern_smh"
PLACE = "kerala/thrissur"
DAY = JDN(2447893)  # Gregorian 1990-01-01


def _day(**sets: str) -> dict[str, Any]:
    return api.day(open_config(REPO, PRESET, PLACE, records=records(), **sets), DAY)


@pytest.fixture(scope="module")
def default() -> dict[str, Any]:
    return _day()


#: (key, a value other than modern_smh's, the provenance field, its value under the switch)
SWITCHES = [
    ("modern.sunrise_event", "centre/none/none", "sunrise_event", "centre/none/none"),
    (
        "modern.sunrise_event",
        "upper_limb/iae_india/geometric:10m@10m",
        "sunrise_event",
        "upper_limb/iae_india/geometric:10m",
    ),
    ("modern.delta_t", "em2006", "delta_t", "em2006"),
    ("modern.delta_t", "constant:60", "delta_t", "constant"),
    ("modern.node", "osculating", "node", "osculating"),
    ("modern.ayanamsa", "citra_180/true/aberration", "ayanamsa", "citra_180"),
    ("modern.ayanamsa", "custom_linear/mean/85000,5000", "ayanamsa", "custom_linear"),
]


def _component(prov: dict[str, Any], field: str) -> Any:
    v = prov[field]
    if field == "delta_t":
        return v["model"]
    if field == "ayanamsa":
        return v["ayanamsa"]
    return v


@pytest.mark.parametrize(("key", "value", "field", "seen"), SWITCHES)
def test_a_switch_is_used_recorded_and_flagged(
    key: str, value: str, field: str, seen: str, default: dict[str, Any]
) -> None:
    rec = _day(**{key: value})
    prov = rec["provenance"]
    assert _component(prov, field) == seen
    assert prov["overrides"] == {key: value}
    assert f"diagnostic:{key}" in rec["flags"]
    assert f"diagnostic:{key}" not in default["flags"]
    assert rec["config_hash"] != default["config_hash"]


def test_the_preset_s_own_value_is_no_override(default: dict[str, Any]) -> None:
    prov = default["provenance"]
    same = {
        "modern.sunrise_event": prov["sunrise_event"],
        "modern.node": prov["node"],
        "modern.delta_t": prov["delta_t"]["model"],
        "modern.ayanamsa": f"{prov['ayanamsa']['ayanamsa']}/{prov['ayanamsa']['equinox']}",
    }
    rec = _day(**same)
    assert rec["config_hash"] == default["config_hash"]
    assert not any(f.startswith("diagnostic:modern.") for f in rec["flags"])


def test_the_centre_without_refraction_rises_later(default: dict[str, Any]) -> None:
    """The Sun's centre with no refraction clears the horizon after its refracted upper limb."""
    rec = _day(**{"modern.sunrise_event": "centre/none/none"})
    assert rec["sunrise"]["ut1"] > default["sunrise"]["ut1"]


def test_the_osculating_node_moves_rahu(default: dict[str, Any]) -> None:
    rec = _day(**{"modern.node": "osculating"})
    lon = rec["planets"]["rahu"]["sidereal_longitude"]
    assert lon != default["planets"]["rahu"]["sidereal_longitude"]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("modern.sunrise_event", "centre/none"),
        ("modern.sunrise_event", "rim/none/none"),
        ("modern.sunrise_event", "centre/none/geometric"),
        ("modern.ayanamsa", "lahiri/true"),
        ("modern.ayanamsa", "citra_180/true"),
        ("modern.ayanamsa", "custom_linear/true/1,2,3"),
        ("modern.delta_t", "constant"),
        ("modern.delta_t", "nasa"),
        ("modern.node", "true"),
    ],
)
def test_a_malformed_switch_is_refused(key: str, value: str) -> None:
    with pytest.raises(Refusal) as info:
        open_config(REPO, PRESET, PLACE, records=records(), **{key: value})
    assert info.value.field == key


def test_the_switches_are_refused_under_a_siddhantic_preset() -> None:
    with pytest.raises(Refusal) as info:
        open_config(
            REPO, "parahita_kerala", PLACE, records=records(), **{"modern.node": "osculating"}
        )
    assert info.value.field == "modern.node" and "modern preset" in info.value.message
