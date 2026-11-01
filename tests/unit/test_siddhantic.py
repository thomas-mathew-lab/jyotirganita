"""Unit tests of the siddhantic arithmetic on planted tables.

Every number here is planted to exercise the arithmetic; none is a text's
value (the texts' values are tested against their printed examples under
``tests/authority/aryabhatiya/``). The planted Rsine table has an interval
of 10′ and the differences 5, 4, 3, 1 (radius 13, quadrant 40′).
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from jyotirganita.core.calendar import Weekday
from jyotirganita.core.types import JDN
from jyotirganita.data.datum import context_for, load_records
from jyotirganita.data.yamlio import dump_canonical, load_exact
from jyotirganita.methods.compose import REPO, build, load_method
from jyotirganita.regions.places import PlaceError, load_place
from jyotirganita.siddhantic.ahargana import (
    ahargana_of_day,
    day_of_ahargana,
    weekday_of_ahargana,
)
from jyotirganita.siddhantic.corrections import Layer, YearDatum
from jyotirganita.siddhantic.engine import EngineRefusal, Observer
from jyotirganita.siddhantic.epicycle import (
    Epicycle,
    _integer_root,
    bhuja_koti,
    corrected_epicycle,
    karna,
    manda_correction,
    quadrant_parts,
    sighra_correction,
)
from jyotirganita.siddhantic.mean import mean_longitude, node_from_mean
from jyotirganita.siddhantic.tables import RsineTable

F = Fraction
T = RsineTable.of(10, [5, 4, 3, 1])
KENDRAS = [F(k) for k in (0, 1, 30, 45, 89, 90, 91, 135, 179, 180, 181, 270, 300, 359)] + [
    F(1, 7),
    F(2333, 13),
]


# --- the Rsine table ----------------------------------------------------------------------


def test_the_table_s_radius_and_quadrant() -> None:
    assert (T.radius, T.quadrant) == (13, 40)


@pytest.mark.parametrize(
    ("arc", "rsine", "rversine"),
    [(0, 0, 0), (10, 5, 1), (15, 7, F(5, 2)), (25, F(21, 2), 6), (40, 13, 13)],
)
def test_rsine_and_rversine_by_linear_interpolation(arc: int, rsine: F, rversine: F) -> None:
    assert T.rsine(arc) == rsine
    assert T.rversine(arc) == rversine


def test_rsine_and_rversine_of_the_complement_sum_to_the_radius() -> None:
    for arc in (F(0), F(3), F(17, 3), F(20), F(39)):
        assert T.rsine(arc) + T.rversine(T.quadrant - arc) == T.radius


def test_the_arc_inverts_the_rsine() -> None:
    for arc in (F(0), F(1, 3), F(10), F(27, 2), F(33), F(40)):
        assert T.arc(T.rsine(arc)) == arc


@pytest.mark.parametrize("bad", [F(-1), F(41)])
def test_an_arc_outside_the_quadrant_is_refused(bad: F) -> None:
    with pytest.raises(ValueError, match="outside the quadrant"):
        T.rsine(bad)


def test_a_rsine_beyond_the_radius_is_refused() -> None:
    with pytest.raises(ValueError, match="outside"):
        T.arc(14)


@pytest.mark.parametrize(("interval", "diffs"), [(0, [1]), (10, []), (10, [3, 0])])
def test_a_malformed_table_is_refused(interval: int, diffs: list[int]) -> None:
    with pytest.raises(ValueError):
        RsineTable.of(interval, diffs)


# --- bhujā, koṭi, quadrants ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("kendra", "expected"),
    [
        (30, (1, 30, 30, 60)),
        (120, (2, 30, 60, 30)),
        (200, (3, 20, 20, 70)),
        (300, (4, 30, 60, 30)),
        (390, (1, 30, 30, 60)),
        (-60, (4, 30, 60, 30)),
    ],
)
def test_bhuja_and_koti_by_quadrant(kendra: int, expected: tuple[int, int, int, int]) -> None:
    assert bhuja_koti(F(kendra)) == tuple(F(x) if i else x for i, x in enumerate(expected))


def test_the_parts_of_a_kendra_alternate_rsine_and_rversine() -> None:
    assert quadrant_parts(F(200)) == [("rsine", F(90)), ("rversine", F(90)), ("rsine", F(20))]
    assert quadrant_parts(F(0)) == []
    assert sum(p for _, p in quadrant_parts(F(359))) == 359


# --- the pulsating epicycle ------------------------------------------------------------------

E = Epicycle(F(14), F(18))  # planted: odd 14, even 18


@pytest.mark.parametrize(("kendra", "value"), [(0, 14), (90, 18), (180, 14), (270, 18)])
def test_the_epicycle_takes_its_stated_values_at_the_quadrants_beginnings(
    kendra: int, value: int
) -> None:
    # the planted table's quadrant is 40′, so the planted kendras are scaled to it
    t = RsineTable.of(225, [1] * 24)  # radius 24, quadrant 5400′ = 90°
    assert corrected_epicycle(E, F(kendra), t) == value


def test_the_epicycle_lies_between_its_stated_values() -> None:
    t = RsineTable.of(225, [1] * 24)
    for k in KENDRAS:
        assert 14 <= corrected_epicycle(E, k, t) <= 18
    assert corrected_epicycle(Epicycle(F(7), F(7)), F(45), t) == 7


def test_a_greater_epicycle_at_the_beginning_is_diminished() -> None:
    t = RsineTable.of(225, [1] * 24)
    reversed_e = Epicycle(F(18), F(14))
    assert corrected_epicycle(reversed_e, F(45), t) == 18 - corrected_epicycle(E, F(45), t) + 14


# --- the manda and śīghra corrections ----------------------------------------------------------

R = RsineTable.of(225, [225 - 2 * i for i in range(24)])  # planted, decreasing differences
DIVISOR = 80
RES = F(1, 3600)


@pytest.mark.parametrize("arc", [False, True])
def test_the_manda_correction_is_subtractive_from_aries_and_additive_from_libra(arc: bool) -> None:
    for k in KENDRAS:
        c = manda_correction(E, k, R, DIVISOR, arc=arc)
        if k % 180 == 0:
            assert c == 0
        elif k % 360 < 180:
            assert c < 0
        else:
            assert c > 0


@pytest.mark.parametrize("arc", [False, True])
def test_the_manda_correction_is_antisymmetric(arc: bool) -> None:
    for k in KENDRAS:
        assert manda_correction(E, k, R, DIVISOR, arc=arc) == -manda_correction(
            E, 360 - k, R, DIVISOR, arc=arc
        )


def test_the_sighra_correction_is_additive_from_aries_and_antisymmetric() -> None:
    e = Epicycle(F(53), F(51))
    for k in KENDRAS:
        c = sighra_correction(e, k, R, DIVISOR, RES)
        if k % 180 == 0:
            assert c == 0
        else:
            assert (c > 0) == (k % 360 < 180)
        assert c == -sighra_correction(e, 360 - k, R, DIVISOR, RES)


@pytest.mark.parametrize("n", [0, 1, 2, 3, 4, 15, 16, 17, 10**12, 10**12 + 1, 2**127 - 1])
def test_the_integer_root(n: int) -> None:
    r = _integer_root(n)
    assert r * r <= n < (r + 1) * (r + 1)


def test_the_karna_is_the_root_truncated_at_the_resolution() -> None:
    assert karna(F(25), F(1)) == 5
    for square in (F(2), F(3460, 7), F(10**7 + 3)):
        h = karna(square, RES)
        assert (h / RES).denominator == 1
        assert h * h <= square < (h + RES) * (h + RES)
    with pytest.raises(ValueError):
        karna(F(-1), RES)
    with pytest.raises(ValueError):
        karna(F(4), F(0))


# --- mean positions --------------------------------------------------------------------------


def test_mean_longitude_truncates_at_the_vikala() -> None:
    m = mean_longitude(7, 3, 1)  # 2 1/3 revolutions: 120°, exact
    assert (m.revolutions, m.degrees, m.exact) == (2, F(120), F(120))
    m = mean_longitude(1, 7 * 3600, 1)  # 360/25200 degrees = 1/70°: 51.43″
    assert m.degrees == F(51, 3600) and m.exact == F(1, 70)


def test_the_node_is_counted_back_from_a_circle() -> None:
    assert node_from_mean(F(10), 6) == 170
    assert node_from_mean(F(0), 0) == 0
    assert node_from_mean(F(200), 6) == 340


# --- the day count and the weekday ----------------------------------------------------------------


def test_ahargana_and_day_are_inverse() -> None:
    epoch = JDN(1000)
    for d in (0, 1, 365, 10**6):
        a = ahargana_of_day("planted", epoch, epoch.plus_days(d))
        assert a.day == d and day_of_ahargana(epoch, a) == epoch.plus_days(d)


def test_the_weekday_counts_from_the_first() -> None:
    assert weekday_of_ahargana(0, Weekday.FRIDAY) == Weekday.FRIDAY
    assert weekday_of_ahargana(1, Weekday.FRIDAY) == Weekday.SATURDAY
    assert weekday_of_ahargana(7 * 10**9 + 6, Weekday.FRIDAY) == Weekday.THURSDAY


# --- year data and layers -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("unit", "year", "threshold"),
    [
        ("kali_years_elapsed", 3600, 3600),
        ("kali_years_current", 3600, 3599),
        ("saka_years_elapsed", 444, 444 + 3179),
        ("saka_years_current", 444, 443 + 3179),
    ],
)
def test_a_year_datum_s_kali_threshold(unit: str, year: int, threshold: int) -> None:
    assert YearDatum.of("planted", year, unit, "stated").kali_threshold(3179) == threshold


@pytest.mark.parametrize("unit", ["years", "ad_years_elapsed", "kali_years_since"])
def test_a_bare_or_unknown_year_is_refused(unit: str) -> None:
    with pytest.raises(ValueError, match="a bare year is a gap"):
        YearDatum.of("planted", 444, unit, "stated")


def test_a_layer_counts_completed_years_after_its_epoch_with_a_floor_before() -> None:
    epoch = YearDatum.of("planted.epoch", 10, "kali_years_elapsed", "stated")
    layer = Layer("planted", epoch, epoch, {"moon": F(-9, 85)})
    assert [layer.count(k, 0) for k in (8, 9, 10, 11)] == [-2, -1, 0, 1]
    assert layer.correction("moon", 85 * 60) == -9
    assert layer.correction("sun", 100) == 0
    assert layer.zeroed().correction("moon", 1000) == 0


# --- places and observers ---------------------------------------------------------------------


def test_the_text_s_meridian_point_loads_on_route_a() -> None:
    obs = load_place(REPO, "meridians", "lanka", load_records(REPO, context_for(REPO)).data)
    assert (obs.id, obs.texts, obs.meridian_offset_ghatis, obs.latitude_degrees) == (
        "meridians.lanka",
        ("aryabhatiya",),
        F(0),
        F(0),
    )
    # served by the keyed sunrise and carries, not provisional
    assert (obs.flags, obs.route) == ((), "text_units")


def _degrees(value: object) -> Fraction:
    parts = value if isinstance(value, list) else [value]
    assert all(isinstance(v, int | Fraction) for v in parts)
    return sum((F(v) / 60**i for i, v in enumerate(parts)), F(0))


def test_a_modern_coordinate_is_converted_by_the_text_s_rules() -> None:
    data = load_records(REPO, context_for(REPO)).data
    obs = load_place(REPO, "kerala", "kozhikode", data)
    entry = {
        e["id"]: e for e in load_exact(REPO / "jyotirganita/regions/kerala/places.yaml")["places"]
    }["kozhikode"]
    lat, lon, mer = (
        _degrees(data[entry[k]["statement"]].value)
        for k in ("latitude", "longitude", "meridian_longitude")
    )
    # laghubhaskariya_1963 I.24, I.31: the yojana scalings cancel; the offset is the difference's
    # share of 60 ghaṭīs
    assert (obs.latitude_degrees, obs.meridian_offset_ghatis) == (lat, (lon - mer) * 60 / 360)
    assert obs.route == "modern_converted"
    # no longer provisional: the meridian witness is decided; the modern coordinates are
    # flagged on every method's records
    assert obs.flags == ("modern_coordinates",)
    # the Dṛggaṇita reaches the same meridian through the editor's identification, the
    # Sūrya-siddhānta through Whitney's
    assert obs.texts == ("aryabhatiya", "drgganita", "suryasiddhanta")
    assert obs.flags_for("aryabhatiya") == ("modern_coordinates",)
    assert obs.route_data_for("aryabhatiya") == ()
    surya = entry["conversion"]["suryasiddhanta"]["meridian_identification"]
    assert f"provisional:{surya}" in obs.flags_for("suryasiddhanta")
    ident = entry["conversion"]["drgganita"]["meridian_identification"]
    assert f"provisional:{ident}" in obs.flags_for("drgganita")
    assert obs.route_data_for("drgganita") == (
        ident,
        entry["conversion"]["drgganita"]["meridian_gap"],
        entry["meridian_longitude"]["statement"],
    )


def _kerala_copy(tmp: Path) -> Path:
    dst = tmp / "jyotirganita" / "regions" / "kerala"
    dst.mkdir(parents=True)
    shutil.copy2(REPO / "jyotirganita/regions/kerala/places.yaml", dst / "places.yaml")
    return dst / "places.yaml"


def _edit_place(path: Path, place: str, edit: Callable[[dict[str, Any]], None]) -> None:
    doc = load_exact(path)
    edit(next(e for e in doc["places"] if e["id"] == place))
    path.write_text(dump_canonical(doc), encoding="utf-8")


def test_route_b_through_another_text_s_meridian_names_its_identification(
    tmp_path: Path,
) -> None:
    data = load_records(REPO, context_for(REPO)).data
    path = _kerala_copy(tmp_path)
    _edit_place(path, "kozhikode", lambda e: e["conversion"].pop("drgganita"))
    with pytest.raises(PlaceError, match="names the conversion rules of each of"):
        load_place(tmp_path, "kerala", "kozhikode", data)
    path = _kerala_copy(tmp_path / "b")

    def no_identification(e: dict[str, Any]) -> None:
        for k in ("meridian_identification", "meridian_gap"):
            e["conversion"]["drgganita"].pop(k)

    _edit_place(path, "kozhikode", no_identification)
    with pytest.raises(PlaceError, match="names the statement identifying its line with it"):
        load_place(tmp_path / "b", "kerala", "kozhikode", data)
    path = _kerala_copy(tmp_path / "c")

    def gap_is_datum(e: dict[str, Any]) -> None:
        conv = e["conversion"]["drgganita"]
        conv["meridian_gap"] = conv["meridian_identification"]

    _edit_place(path, "kozhikode", gap_is_datum)
    with pytest.raises(PlaceError, match="which is not a gap"):
        load_place(tmp_path / "c", "kerala", "kozhikode", data)


def test_a_place_without_a_route_is_refused_naming_its_gap() -> None:
    data = load_records(REPO, context_for(REPO)).data
    with pytest.raises(PlaceError, match="no route serves this place"):
        load_place(REPO, "kerala", "thalassery", data)


def _places_copy(tmp: Path) -> Path:
    dst = tmp / "jyotirganita" / "regions" / "meridians"
    dst.mkdir(parents=True)
    shutil.copy2(REPO / "jyotirganita/regions/meridians/places.yaml", dst / "places.yaml")
    return dst / "places.yaml"


def _edit(path: Path, **over: object) -> None:
    doc = load_exact(path)
    doc["places"][0].update(over)
    path.write_text(dump_canonical(doc), encoding="utf-8")


def test_place_errors(tmp_path: Path) -> None:
    data = load_records(REPO, context_for(REPO)).data
    with pytest.raises(PlaceError, match="no place table"):
        load_place(tmp_path, "nowhere", "lanka", data)
    path = _places_copy(tmp_path)
    with pytest.raises(PlaceError, match="no place 'ujjain'"):
        load_place(tmp_path, "meridians", "ujjain", data)
    _edit(path, route="modern_converted")
    with pytest.raises(PlaceError, match="route \\(b\\) names the text's conversion rules"):
        load_place(tmp_path, "meridians", "lanka", data)
    _edit(path, route="gap")
    with pytest.raises(PlaceError, match="route gap names its gap datum"):
        load_place(tmp_path, "meridians", "lanka", data)
    _edit(path, route="text_units", texts=["suryasiddhanta"])
    with pytest.raises(PlaceError, match="a datum of none of its texts"):
        load_place(tmp_path, "meridians", "lanka", data)
    lat = dict(load_exact(path)["places"][0]["latitude"], unit="radians")
    _edit(path, texts=["aryabhatiya"], latitude=lat)
    with pytest.raises(PlaceError, match="route text_units takes degrees_north"):
        load_place(tmp_path, "meridians", "lanka", data)
    lat = dict(lat, unit="degrees_north", statement="texts.aryabhatiya.no_such_datum")
    _edit(path, latitude=lat)
    with pytest.raises(PlaceError, match="which is not a datum"):
        load_place(tmp_path, "meridians", "lanka", data)


def test_the_engine_refuses_an_observer_it_cannot_serve() -> None:
    r = load_method("aryabhatiya", REPO)
    other = Observer("planted.other", ("suryasiddhanta",), F(0), F(0))
    with pytest.raises(EngineRefusal, match="has no coordinates for aryabhatiya"):
        build(r, other)
    pole = Observer("planted.pole", ("aryabhatiya",), F(0), F(90))
    with pytest.raises(EngineRefusal, match="is not a place"):
        build(r, pole)


def test_an_observer_east_of_the_meridian_takes_the_desantara() -> None:
    r = load_method("aryabhatiya", REPO)
    jdn = JDN(2438031)
    on = build(r, Observer("planted.on", ("aryabhatiya",), F(0), F(0))).day(jdn)
    east = build(r, Observer("planted.east", ("aryabhatiya",), F(6), F(0))).day(jdn)
    # six ghaṭīs east see sunrise a tenth of a day earlier: the Sun is behind by its tenth
    sun_rate = F(r.text_model.revolutions["sun"] * 360, r.text_model.civil_days)
    assert (on.mean["sun"] - east.mean["sun"]) % 360 == sun_rate / 10
