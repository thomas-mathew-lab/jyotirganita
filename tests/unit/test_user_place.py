"""A run at user-supplied coordinates, for every method.

The observer ``<region>/@<lat>,<lon>`` (degrees north and east, decimal or
``d:m[:s]``) is served by route (b) with the conversion
and meridian rules of the region's ``user`` entry; the modern engine takes
the coordinates as given. At a tabled place's own coordinates the run
must give that place's observer and records, but for the flags, the
observer id and the provenance; every record at user coordinates carries
``user_place`` and ``modern_coordinates``, and every record at a tabled
route (b) place carries ``modern_coordinates``. The coordinates
compared are read from the tabled place's data through the loader, never
typed; no printed value enters here.
"""

from __future__ import annotations

import json
from fractions import Fraction

import jsonschema
import pytest
from modern_kit import records
from record_kit import REPO

from jyotirganita import api
from jyotirganita.config import open_config
from jyotirganita.core.types import JDN
from jyotirganita.errors import Refusal
from jyotirganita.io.record import record_schema
from jyotirganita.regions.places import (
    MODERN_FLAG,
    USER_FLAG,
    PlaceError,
    load_modern_place,
    load_place,
    user_coordinates,
)

TABLED = "kozhikode"
DAY = JDN(2447893)  # Gregorian 1990-01-01
SIDDHANTIC = ("parahita_kerala", "aryabhatiya_kerala", "suryasiddhanta_kerala", "drgganita_kerala")


def _dms(x: Fraction) -> str:
    """``x`` degrees as ``d:m:s`` (exact for a whole number of seconds)."""
    sign, x = ("-", -x) if x < 0 else ("", x)
    d = int(x)
    m = int((x - d) * 60)
    s = (x - d - Fraction(m, 60)) * 3600
    assert s.denominator == 1, x
    return f"{sign}{d}:{m}:{s.numerator}"


@pytest.fixture(scope="module")
def at_tabled() -> str:
    mp = load_modern_place(REPO, "kerala", TABLED, records().data)
    return f"kerala/@{_dms(mp.latitude_deg)},{_dms(mp.longitude_deg)}"


def test_coordinates_parse_decimal_and_sexagesimal() -> None:
    assert user_coordinates("@10.5,76.25") == (Fraction(21, 2), Fraction(305, 4))
    assert user_coordinates("@-8:30,76:15:36") == (
        Fraction(-17, 2),
        Fraction(76) + Fraction(26, 100),
    )
    assert user_coordinates("thrissur") is None
    for bad in ("@10.5", "@a,b", "@91,76", "@10,181", "@10:60,76", "@1e1,76"):
        with pytest.raises(PlaceError):
            user_coordinates(bad)


def test_user_coordinates_at_a_tabled_place_give_its_observer(at_tabled: str) -> None:
    data = records().data
    tabled = load_place(REPO, "kerala", TABLED, data)
    region, _, place = at_tabled.partition("/")
    user = load_place(REPO, region, place, data)
    assert (user.latitude_degrees, user.meridian_offset_ghatis) == (
        tabled.latitude_degrees,
        tabled.meridian_offset_ghatis,
    )
    assert user.texts == tabled.texts and user.text_flags == tabled.text_flags
    assert MODERN_FLAG in tabled.flags and USER_FLAG not in tabled.flags
    assert {MODERN_FLAG, USER_FLAG} <= set(user.flags)


@pytest.mark.parametrize("preset", [*SIDDHANTIC, "modern_smh"])
def test_a_record_at_user_coordinates_is_the_tabled_place_s_but_for_flags_and_provenance(
    preset: str, at_tabled: str
) -> None:
    tabled = api.day(open_config(REPO, preset, f"kerala/{TABLED}", records=records()), DAY)
    user = api.day(open_config(REPO, preset, at_tabled, records=records()), DAY)
    assert MODERN_FLAG in tabled["flags"] and USER_FLAG not in tabled["flags"]
    assert {MODERN_FLAG, USER_FLAG} <= set(user["flags"])
    prov = user["provenance"]
    assert prov["observer"] == at_tabled
    for rec in (tabled, user):
        jsonschema.Draft202012Validator(record_schema()).validate(json.loads(api.dumps(rec)))
    differ = {"flags", "provenance", "config_hash"}
    assert {k: v for k, v in user.items() if k not in differ} == {
        k: v for k, v in tabled.items() if k not in differ
    }


def test_the_provenance_records_the_coordinates_as_input(at_tabled: str) -> None:
    rec = api.day(open_config(REPO, "parahita_kerala", at_tabled, records=records()), DAY)
    coords = rec["provenance"]["observer_coordinates"]
    lat, lon = user_coordinates(at_tabled.partition("/")[2]) or (None, None)
    assert coords == {"latitude_deg": str(lat), "longitude_deg": str(lon), "source": "user"}


@pytest.mark.parametrize(
    ("observer", "word"),
    [("kerala/@10.5", "@<lat>,<lon>"), ("kerala/@95,76", "latitude"), ("nowhere/@10,76", "region")],
)
def test_malformed_or_unserved_coordinates_are_refused(observer: str, word: str) -> None:
    with pytest.raises(Refusal) as info:
        open_config(REPO, "parahita_kerala", observer, records=records())
    assert info.value.field == "observer" and word in info.value.message


# --- the user place's own checks -----------------------------------------

#: a latitude the Āryabhaṭan sunrise rule cannot serve on every day (beyond the polar circle)
POLAR = "kerala/@70,76"


@pytest.mark.parametrize("preset", SIDDHANTIC)
def test_a_latitude_without_a_sunrise_is_refused_at_open_naming_the_observer(
    preset: str,
) -> None:
    # the Kerala profile's month rule is probed when the run opens
    with pytest.raises(Refusal) as info:
        open_config(REPO, preset, POLAR, records=records())
    assert info.value.field == "observer" and "no sunrise" in info.value.message


def test_a_day_without_a_sunrise_is_refused_naming_the_date() -> None:
    cfg = open_config(REPO, "aryabhatiya_text", POLAR, records=records())
    with pytest.raises(Refusal) as info:
        for jdn in range(DAY.value, DAY.value + 366):  # a polar night or day within the year
            api.day(cfg, JDN(jdn))
    assert info.value.field == "date" and "no sunrise" in info.value.message


@pytest.mark.parametrize("derived_ut", ["mean", "apparent:text_bhujantara"])
def test_derived_ut_at_user_coordinates_takes_the_user_s_longitude(
    derived_ut: str, at_tabled: str
) -> None:
    tabled = api.day(
        open_config(REPO, "parahita_kerala", f"kerala/{TABLED}", records=records()),
        DAY,
        derived_ut=derived_ut,
    )
    user = api.day(
        open_config(REPO, "parahita_kerala", at_tabled, records=records()),
        DAY,
        derived_ut=derived_ut,
    )
    assert user["derived_ut"]["value"] == tabled["derived_ut"]["value"]
    lon = (user_coordinates(at_tabled.partition("/")[2]) or (None, None))[1]
    assert user["derived_ut"]["place"]["longitude"] == f"user:{lon}"
    assert tabled["derived_ut"]["place"]["longitude"].startswith("regions.kerala.places.")
    jsonschema.Draft202012Validator(record_schema()).validate(json.loads(api.dumps(user)))
