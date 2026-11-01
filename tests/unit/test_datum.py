"""The datum loader (jyotirganita/data/datum.py).

Each failing case loads a planted datum file and asserts that the error
names the key and the rule. The values are planted (records_kit).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from records_kit import (
    DROP,
    FABLE,
    FABLE_2,
    OPUS,
    OPUS_2,
    Sample,
    datum,
    fixture,
    numeral_word,
    read,
    signoff,
)

from jyotirganita.data.datum import (
    DISPUTED,
    RECORDED,
    DatumError,
    MethodStatus,
    context_for,
    load_datum_file,
    load_records,
    non_canonical,
    signed_hash,
)

KEY = "texts.sample.revolutions"


def _load(
    tmp_path: Path, items: list[dict[str, Any]], status: MethodStatus = "provisional"
) -> list[Any]:
    s = Sample(tmp_path)
    path = s.data(items)
    return load_datum_file(path, context_for(tmp_path), status, tmp_path)


def _fails(
    tmp_path: Path, items: list[dict[str, Any]], rule: str, status: MethodStatus = "provisional"
) -> None:
    with pytest.raises(DatumError) as err:
        _load(tmp_path, items, status)
    msg = str(err.value)
    assert items[0]["key"] in msg, msg
    assert rule in msg, msg


def test_a_double_read_datum_loads(tmp_path: Path) -> None:
    (rec,) = _load(tmp_path, [datum()], "validated")
    assert rec.status == "double_read" and rec.value == 4320000 and not rec.cross_model
    assert rec.file == "aryabhatiya_1976.pdf" and rec.flags == ()


# --- the loader's rules ----------------------------------------------------------


@pytest.mark.parametrize("missing", ["source", "edition_page", "pdf_page", "locus"])
def test_uncited_datum_fails(tmp_path: Path, missing: str) -> None:
    _fails(tmp_path, [datum(KEY, **{missing: DROP})], f"'{missing}' is a required property")


def test_decimal_where_sexagesimal_is_declared_fails(tmp_path: Path) -> None:
    from jyotirganita.data.yamlio import PrintedNumber

    _fails(
        tmp_path,
        [datum(form="sexagesimal", unit="degrees", value=PrintedNumber("12.5"))],
        "carries its parts as a list of integers, never a decimal",
    )


def test_unheld_source_without_gap_fails(tmp_path: Path) -> None:
    _fails(tmp_path, [datum(source="venvaroha_1956")], "is not held")


def test_unheld_source_as_a_gap_loads(tmp_path: Path) -> None:
    gap = {
        "key": KEY,
        "status": "gap",
        "reason": "planted",
        "searched": "planted",
        "effect": "planted",
        "source": "venvaroha_1956",
    }
    (rec,) = _load(tmp_path, [gap], "validated")
    assert rec.status == "gap"


@pytest.mark.parametrize("written", ["verified", "validated", "corroborated"])
def test_hand_written_verified_fails(tmp_path: Path, written: str) -> None:
    _fails(tmp_path, [datum(status=written)], "is computed by the ledger, never written")


def test_numeral_word_decode_differs_from_value_fails(tmp_path: Path) -> None:
    d = numeral_word()
    d["word"]["decode"] = 1577917501
    _fails(tmp_path, [d], "differs from value and the datum carries no mismatch_issue")


def test_numeral_word_decode_differs_from_adopted_fails(tmp_path: Path) -> None:
    d = numeral_word(
        emendation={
            "printed": 1577917500,
            "adopted": 1577917540,
            "evidence": "planted: the text's own rule",
            "evidence_indic": False,
            "by": OPUS,
            "on": "2026-10-02",
            "owner_signoff": None,
        }
    )
    _fails(tmp_path, [d], "differs from emendation.adopted and the datum carries no mismatch_issue")
    d["word"]["decode"] = 1577917540
    (rec,) = _load(tmp_path / "ok", [d])
    assert rec.value == 1577917540


def test_numeral_word_mismatch_under_validated_fails_even_with_issue(tmp_path: Path) -> None:
    d = numeral_word(mismatch_issue="I-901")
    d["word"]["decode"] = 1577917501
    _fails(tmp_path, [d], "loads only while its method is not corroborated", "corroborated")
    # the loosened grade lets it load: the ledger holds it to classes B to D
    (rec,) = _load(tmp_path / "v", [d], "validated")
    assert rec.flags == (f"provisional:{d['key']}",)


def test_numeral_word_mismatch_under_provisional_loads_flagged(tmp_path: Path) -> None:
    d = numeral_word(mismatch_issue="I-901")
    d["word"]["decode"] = 1577917501
    (rec,) = _load(tmp_path, [d])
    assert rec.flags == (f"provisional:{d['key']}",)


def test_mismatch_issue_must_exist(tmp_path: Path) -> None:
    d = numeral_word(mismatch_issue="I-999")
    d["word"]["decode"] = 1577917501
    _fails(tmp_path, [d], "mismatch_issue I-999 is not in the issue register")


def test_signoff_without_ref_fails(tmp_path: Path) -> None:
    d = numeral_word()
    d["owner_signoff"] = signoff(d, ref="")
    _fails(tmp_path, [d], "a sign-off without a ref fails to load")


def test_signoff_with_stale_hash_fails(tmp_path: Path) -> None:
    d = numeral_word()
    d["owner_signoff"] = signoff(d)
    d["value"] = d["word"]["decode"] = 1577917520
    _fails(tmp_path, [d], "re-sign needed")


def test_signoff_with_current_hash_loads(tmp_path: Path) -> None:
    d = numeral_word()
    d["owner_signoff"] = signoff(d)
    (rec,) = _load(tmp_path, [d], "validated")
    assert rec.signed_off and rec.indic


def test_signoff_ref_must_name_a_decision_or_url(tmp_path: Path) -> None:
    d = numeral_word()
    d["owner_signoff"] = signoff(d, ref="D-999")
    _fails(tmp_path, [d], "ref D-999 is not in the decision register")
    d["owner_signoff"] = signoff(d, ref="https://github.com/o/r/pull/1#c")
    assert _load(tmp_path / "ok", [d])


def _without_registers(root: Path) -> None:
    for name in ("ISSUES.md", "DECISIONS.md"):
        (root / name).unlink()


def test_a_tree_without_registers_writes_disputed_and_recorded(tmp_path: Path) -> None:
    d = numeral_word(mismatch_issue=DISPUTED)
    d["word"]["decode"] = 1577917501
    s = numeral_word(key="texts.sample.other")
    s["owner_signoff"] = signoff(s, ref=RECORDED)
    sample = Sample(tmp_path)
    path = sample.data([d, s])
    _without_registers(tmp_path)
    ctx = context_for(tmp_path)
    assert not ctx.registers and not ctx.issues and not ctx.decisions
    one, two = load_datum_file(path, ctx, "provisional", tmp_path)
    assert one.flags == (f"provisional:{d['key']}",) and two.signed_off


def test_a_tree_without_registers_cites_no_id(tmp_path: Path) -> None:
    d = numeral_word(mismatch_issue="I-901")
    d["word"]["decode"] = 1577917501
    path = Sample(tmp_path).data([d])
    _without_registers(tmp_path)
    with pytest.raises(DatumError, match=r"mismatch_issue I-901 is not in the issue register"):
        load_datum_file(path, context_for(tmp_path), "provisional", tmp_path)


def test_a_tree_with_registers_never_writes_disputed_or_recorded(tmp_path: Path) -> None:
    d = numeral_word(mismatch_issue=DISPUTED)
    d["word"]["decode"] = 1577917501
    _fails(tmp_path / "a", [d], "mismatch_issue disputed is written only where")
    s = numeral_word()
    s["owner_signoff"] = signoff(s, ref=RECORDED)
    _fails(tmp_path / "b", [s], "ref development-record is written only where")


def test_deciding_reading_needs_individual_scope(tmp_path: Path) -> None:
    d = numeral_word(decides=["procedure"])
    d["owner_signoff"] = signoff(d, scope="batch")
    _fails(tmp_path, [d], "scope: individual")


def test_verified_by_citing_an_excluded_copy_fails(tmp_path: Path) -> None:
    _fails(
        tmp_path,
        [datum(verified_by=["tantrasangraha_2011 printed p. 45"])],
        "a copy without an established licence",
    )


def test_verified_by_a_datum_from_an_excluded_copy_fails(tmp_path: Path) -> None:
    s = Sample(tmp_path)
    witness = datum("texts.other.revolutions", source="tantrasangraha_2011", script="latin")
    s.data([witness], "texts/other/elements.yaml")
    s.data([datum(verified_by=["texts.other.revolutions"])])
    with pytest.raises(
        DatumError, match=f"{KEY}: verified_by texts.other.revolutions rests on tantrasangraha_2011"
    ):
        load_records(tmp_path)


def test_indic_datum_read_twice_by_one_model_fails(tmp_path: Path) -> None:
    d = numeral_word(second_read=[read(OPUS_2)])
    _fails(tmp_path, [d], "double_read only by two reads whose model ids differ")
    d = datum(script="malayalam", second_read=[read(OPUS_2)])
    _fails(tmp_path / "m", [d], "double_read only by two reads whose model ids differ")


def test_table_is_cross_model(tmp_path: Path) -> None:
    d = datum(
        form="table", columns=["n", "jya"], value=[[1, 225], [2, 449]], second_read=[read(FABLE)]
    )
    (rec,) = _load(tmp_path, [d])
    assert rec.cross_model and rec.cross_model_pair and rec.value == ((1, 225), (2, 449))
    d["second_read"] = [read(OPUS_2)]
    _fails(tmp_path / "same", [d], "model ids differ")


def test_latin_datum_two_opus_contexts_loads(tmp_path: Path) -> None:
    (rec,) = _load(tmp_path, [datum()])
    assert not rec.cross_model_pair and rec.agreeing_reader == OPUS_2


def test_second_read_by_the_first_context_fails(tmp_path: Path) -> None:
    _fails(tmp_path, [datum(second_read=[read(OPUS)])], "does not count")


def test_status_read_loads_only_below_corroborated(tmp_path: Path) -> None:
    d = datum(status="read", second_read=DROP)
    assert _load(tmp_path, [d])[0].status == "read"
    assert _load(tmp_path / "v", [d], "validated")[0].status == "read"
    _fails(tmp_path / "c", [d], "loads only under a method not corroborated", "corroborated")


def test_double_read_without_second_read_fails(tmp_path: Path) -> None:
    _fails(tmp_path, [datum(second_read=DROP)], "needs a second_read")


# --- further rules ------------------------------------------------------------


def test_read_records_dpi_clip_and_ppi(tmp_path: Path) -> None:
    r = read()
    del r["delivered_ppi"]
    _fails(tmp_path, [datum(read=[r])], "'delivered_ppi' is a required property")


def test_text_layer_read_only_for_born_digital(tmp_path: Path) -> None:
    tl = read("text-layer/pymupdf-1.26.4", dpi=None, clip="page", delivered_ppi="vector")
    _fails(tmp_path, [datum(read=[tl])], "only for a born-digital file")
    (rec,) = _load(tmp_path / "bd", [datum(source="grahacaranibandhana_1954", read=[tl])])
    assert rec.first_reader is not None and rec.first_reader.startswith("text-layer/")


def test_transcription_read_only_for_corpus_cells(tmp_path: Path) -> None:
    tr = read(
        "transcription/opendigi-tei", dpi=None, clip="page", delivered_ppi="none", sha256="a" * 64
    )
    _fails(tmp_path, [datum(read=[tr])], "a first read of a corpus cell only")
    s = Sample(tmp_path / "c")
    cell = datum("corpora.sample.c1", read=[tr], second_read=[read(FABLE)])
    for k in ("source", "verified_by", "emendation", "notes"):
        cell.pop(k)
    s.write(
        "corpora/sample/cells/p1.yaml",
        {"corpus": "sample", "source": "aryabhatiya_1976", "cells": [cell]},
    )
    recs = load_records(tmp_path / "c")
    assert recs.cells["corpora.sample.c1"].cross_model


def test_multi_file_source_names_its_file(tmp_path: Path) -> None:
    _fails(tmp_path, [datum(source="drgganita_1963")], "names its `file`")
    (rec,) = _load(
        tmp_path / "ok", [datum(source="drgganita_1963", file="drgganita_1963-v2.pdf", pdf_page=70)]
    )
    assert rec.file == "drgganita_1963-v2.pdf"
    _fails(
        tmp_path / "far",
        [datum(source="drgganita_1963", file="drgganita_1963-v2.pdf", pdf_page=90)],
        "beyond the 80 pages",
    )


def test_misprint_needs_an_emendation(tmp_path: Path) -> None:
    printed = [3, 12, 67]
    _fails(
        tmp_path,
        [datum(form="rdms", unit="rdms", value=printed)],
        "a printed misprint loads only with an emendation",
    )
    em = {
        "printed": printed,
        "adopted": [3, 12, 7],
        "evidence": "planted: a second printing",
        "evidence_indic": False,
        "by": OPUS,
        "on": "2026-10-02",
        "owner_signoff": None,
    }
    (rec,) = _load(tmp_path / "ok", [datum(form="rdms", unit="rdms", value=printed, emendation=em)])
    assert rec.value == 3 * 30 + 12 + __import__("fractions").Fraction(7, 60)


def test_emendation_keeps_the_printed_value(tmp_path: Path) -> None:
    em = {
        "printed": 4320001,
        "adopted": 4320002,
        "evidence": "planted",
        "evidence_indic": False,
        "by": OPUS,
        "on": "2026-10-02",
        "owner_signoff": None,
    }
    _fails(tmp_path, [datum(emendation=em)], "emendation.printed is the value as printed")


def test_indic_emendation_unsigned_is_provisional(tmp_path: Path) -> None:
    d = numeral_word()
    d["emendation"] = {
        "printed": d["value"],
        "adopted": 1577917540,
        "evidence": "planted: the word's own decode",
        "evidence_indic": True,
        "by": OPUS,
        "on": "2026-10-02",
        "owner_signoff": None,
    }
    d["word"]["decode"] = 1577917540
    (rec,) = _load(tmp_path, [d])
    assert rec.flags == (f"provisional:{d['key']}",) and not rec.signed_off
    d["owner_signoff"] = signoff(d)  # the datum's own sign-off does not cover the emendation
    _fails(
        tmp_path / "v", [d], "needs owner_signoff before its method is corroborated", "corroborated"
    )
    assert _load(tmp_path / "l", [d], "validated")[0].flags == (f"provisional:{d['key']}",)
    d["emendation"]["owner_signoff"] = signoff(d, scope="individual")
    d["owner_signoff"] = signoff(d)
    (rec,) = _load(tmp_path / "s", [d], "corroborated")
    assert rec.signed_off and rec.flags == ()


def test_third_look_settles_a_disagreement(tmp_path: Path) -> None:
    d = numeral_word(
        second_read=DROP,
        third_look={"issue": "I-902", "read": read(FABLE_2), "matches": "read"},
    )
    d.pop("second_read", None)
    (rec,) = _load(tmp_path, [d])
    assert rec.status == "double_read" and rec.agreeing_reader == FABLE_2
    d["third_look"]["matches"] = "neither"
    _fails(tmp_path / "n", [d], "matches neither reading leaves the datum at read")


OPUS_3 = "claude-opus-5-5/2026-10-08-t5"


def _looked(third: str, further: str) -> dict[str, Any]:
    """A numeral-word read by Opus, second-read and third-looked by Fable."""
    d = numeral_word(
        status="read",
        second_read=[read(FABLE)],
        third_look={"issue": "I-901", "read": read(FABLE_2), "matches": third},
        further_look=[{"issue": "I-902", "read": read(OPUS_3), "matches": further}],
    )
    return d


def test_a_further_look_of_the_other_model_adopts_the_second_reading(tmp_path: Path) -> None:
    # the second reading carried by two Fable reads and one Opus look
    d = _looked("second_read", "second_read")
    _fails(tmp_path / "r", [d], "two contexts of two models is adopted: double_read")
    d["status"] = "double_read"
    (rec,) = _load(tmp_path, [d])
    assert rec.status == "double_read"
    assert rec.first_reader == FABLE and rec.agreeing_reader == OPUS_3


def test_a_further_look_matching_the_first_read_leaves_it_at_read(tmp_path: Path) -> None:
    # two Opus reads against two Fable reads: the owner adjudicates
    d = _looked("second_read", "read")
    d["status"] = "double_read"
    _fails(tmp_path / "d", [d], "the datum stays at read")
    d["status"] = "read"
    _fails(tmp_path / "i", [d], "carries read_issue")
    d["read_issue"] = "I-901"
    (rec,) = _load(tmp_path, [d])
    assert rec.status == "read"


def test_a_further_look_is_a_fresh_context(tmp_path: Path) -> None:
    d = _looked("second_read", "second_read")
    d["status"] = "double_read"
    d["further_look"][0]["read"] = read(FABLE_2)
    _fails(tmp_path, [d], "different from every earlier reader")
    d = _looked("second_read", "second_read")
    d.pop("third_look")
    _fails(tmp_path / "t", [d], "a further look follows a third look")


OPUS_4 = "claude-opus-5-5/2026-10-09-t6"
FABLE_3 = "claude-fable-5-1/2026-10-09-t7"


def _looked_again(*further: dict[str, Any]) -> dict[str, Any]:
    """`_looked` with a third look that matched neither and more further looks."""
    d = _looked("neither", "neither")
    d["further_look"].extend(further)
    d["read_issue"] = "I-901"
    return d


def test_a_look_matching_an_earlier_look_carries_its_reading(tmp_path: Path) -> None:
    # the third look's own reading, matched by later looks of both models
    d = _looked_again(
        {"issue": "I-903", "read": read(OPUS_4), "matches": "look", "look": FABLE_2},
    )
    d["further_look"][0]["matches"] = "look"
    d["further_look"][0]["look"] = FABLE_2
    d["status"] = "double_read"
    d.pop("read_issue")
    (rec,) = _load(tmp_path, [d])
    assert rec.status == "double_read"
    assert rec.first_reader == FABLE_2 and rec.agreeing_reader == OPUS_3


def test_two_new_looks_agreeing_on_a_new_reading_adopt_it(tmp_path: Path) -> None:
    # a reading no earlier reader made, carried by two looks of two models
    d = _looked_again(
        {"issue": "I-903", "read": read(FABLE_3), "matches": "look", "look": OPUS_3},
    )
    d["status"] = "double_read"
    d.pop("read_issue")
    (rec,) = _load(tmp_path, [d])
    assert rec.first_reader == OPUS_3 and rec.agreeing_reader == FABLE_3


def test_a_new_reading_carried_by_one_model_stays_at_read(tmp_path: Path) -> None:
    d = _looked_again(
        {"issue": "I-903", "read": read(OPUS_4), "matches": "look", "look": OPUS_3},
    )
    d["status"] = "double_read"
    _fails(tmp_path, [d], "the datum stays at read")
    d["status"] = "read"
    (rec,) = _load(tmp_path / "r", [d])
    assert rec.status == "read"


def test_matches_look_names_an_earlier_look(tmp_path: Path) -> None:
    d = _looked_again(
        {"issue": "I-903", "read": read(FABLE_3), "matches": "look", "look": OPUS_4},
    )
    _fails(tmp_path, [d], "names an earlier third or further look")
    d = _looked_again({"issue": "I-903", "read": read(FABLE_3), "matches": "read", "look": OPUS_3})
    _fails(tmp_path / "l", [d], "`look` goes only with matches: look")
    d = _looked("neither", "neither")
    d["third_look"]["matches"] = "look"
    d["third_look"]["look"] = FABLE
    d["further_look"] = []
    d.pop("further_look")
    d["read_issue"] = "I-901"
    _fails(tmp_path / "t", [d], "a third look has no earlier look to match")


def test_procedure_datum_carries_basis(tmp_path: Path) -> None:
    s = Sample(tmp_path)
    path = s.data(
        [datum("texts.sample.rounding", form="text", value="truncate", unit="none")],
        "texts/sample/procedures.yaml",
    )
    with pytest.raises(DatumError, match=r"rounding: a procedure datum carries basis"):
        load_datum_file(path, context_for(tmp_path), "provisional", tmp_path)


def test_inferred_basis_names_a_text_computed_fixture(tmp_path: Path) -> None:
    s = Sample(tmp_path)
    s.data(
        [
            datum(
                "texts.sample.rounding",
                form="text",
                value="truncate",
                unit="none",
                basis="inferred_from_example",
                basis_ref="authority/sample/ex_one",
            )
        ],
        "texts/sample/procedures.yaml",
    )
    s.fixture(fixture(**{"class": "editor_computed", "precision": "planted: 0.01"}))
    with pytest.raises(DatumError, match="names a text_computed fixture"):
        load_records(tmp_path)


def test_duplicate_key_fails(tmp_path: Path) -> None:
    s = Sample(tmp_path)
    s.data([datum()], "texts/a/elements.yaml")
    s.data([datum()], "texts/b/elements.yaml")
    with pytest.raises(DatumError, match=f"{KEY}: key also defined in"):
        load_records(tmp_path)


def test_fixture_loads_and_reports_status(tmp_path: Path) -> None:
    s = Sample(tmp_path)
    s.data([datum()])
    fx = fixture(datum_keys=[KEY])
    fx["values"][1]["status"] = "read"
    del fx["values"][1]["second_read"]
    s.fixture(fx)
    recs = load_records(tmp_path)
    got = recs.fixtures["authority/sample/ex_one"]
    assert got.status == "read" and [v.key for v in got.values] == [
        "authority/sample/ex_one#input.days",
        "authority/sample/ex_one#output.longitude",
    ]


def test_fixture_id_is_its_path(tmp_path: Path) -> None:
    s = Sample(tmp_path)
    s.write("tests/authority/sample/elsewhere.yaml", fixture())
    with pytest.raises(DatumError, match="is not its path"):
        load_records(tmp_path)


def test_fixture_datum_keys_must_exist(tmp_path: Path) -> None:
    s = Sample(tmp_path)
    s.fixture(fixture(datum_keys=["texts.sample.nothing"]))
    with pytest.raises(DatumError, match=r"datum_keys names texts\.sample\.nothing"):
        load_records(tmp_path)


def test_unknown_field_fails(tmp_path: Path) -> None:
    _fails(tmp_path, [datum(confidence="high")], "Unevaluated properties are not allowed")


def test_signed_hash_definition() -> None:
    d = numeral_word()
    assert signed_hash(d) == signed_hash({"value": d["value"], "word": {"text": d["word"]["text"]}})
    assert signed_hash(d) != signed_hash({**d, "value": 1})


def test_written_files_are_canonical(tmp_path: Path) -> None:
    s = Sample(tmp_path)
    path = s.data([datum()])
    assert not non_canonical(path)
    path.write_text(
        path.read_text(encoding="utf-8").replace("value: 4320000", "value:   4320000"),
        encoding="utf-8",
    )
    assert non_canonical(path)


def test_committed_records_load_and_are_canonical() -> None:
    repo = Path(__file__).resolve().parents[2]
    recs = load_records(repo)
    from jyotirganita.data.datum import corpus_files, datum_files, fixture_files

    for path in [*datum_files(repo), *fixture_files(repo), *corpus_files(repo)]:
        assert not non_canonical(path), path
    assert isinstance(recs.data, dict)


# --- an outside review's items ----------------------------------------------------


def test_a_fixture_value_from_an_excluded_copy_does_not_verify(tmp_path: Path) -> None:
    """The check read the fixture's own source, not a value's (item 5)."""
    s = Sample(tmp_path)
    s.data([datum(verified_by=["authority/sample/ex_one"])])
    fx = fixture()
    fx["values"][1]["source"] = "tantrasangraha_2011"
    s.fixture(fx)
    with pytest.raises(DatumError, match="verified_by authority/sample/ex_one rests on"):
        load_records(tmp_path)


def test_a_transcription_is_never_a_second_read(tmp_path: Path) -> None:
    """A transcription as the second read passed as another model's read (item 7)."""
    tr = read(
        "transcription/opendigi-tei", dpi=None, clip="page", delivered_ppi="none", sha256="a" * 64
    )
    s = Sample(tmp_path)
    cell = datum("corpora.sample.c1", read=[read(FABLE)], second_read=[tr])
    for k in ("source", "verified_by", "emendation", "notes"):
        cell.pop(k)
    s.write(
        "corpora/sample/cells/p1.yaml",
        {"corpus": "sample", "source": "aryabhatiya_1976", "cells": [cell]},
    )
    with pytest.raises(DatumError, match="a first read of a corpus cell only"):
        load_records(tmp_path)


def test_a_bare_file_name_must_name_one_file() -> None:
    """``book.pdf`` picked the first of vol1/book.pdf and vol2/book.pdf (item 12)."""
    from types import SimpleNamespace

    from jyotirganita.data.datum import _file_entry

    src: Any = SimpleNamespace(
        id="RX", files=[{"path": "vol1/book.pdf"}, {"path": "vol2/book.pdf"}]
    )
    errors: list[str] = []

    def fail(msg: str) -> None:
        errors.append(msg)
        raise DatumError(msg)

    assert _file_entry(src, "vol2/book.pdf", fail) == {"path": "vol2/book.pdf"}
    with pytest.raises(DatumError, match="names 2 files of RX"):
        _file_entry(src, "book.pdf", fail)


@pytest.mark.parametrize(
    ("text", "word"),
    [
        ("value: 010", "not a decimal integer"),
        ("value: 1:30", "not a decimal integer"),
        ("value: 0x10", "not a decimal integer"),
        ("value: 1:30.5", "not a decimal number"),
        ("value: 10\nvalue: 11", "given twice"),
    ],
)
def test_the_exact_loader_refuses_yaml_1_1_numbers_and_repeated_keys(text: str, word: str) -> None:
    """010 loaded as 8, 1:30 as 90, and a second key replaced the first (items 1, 2)."""
    from jyotirganita.data.yamlio import loads_exact

    assert loads_exact("value: 10")["value"] == 10
    with pytest.raises(ValueError, match=word):
        loads_exact(text)


def test_unsigned_indic_value_loads_below_corroborated_only(tmp_path: Path) -> None:
    # the author's Indic sign-off gates the top grade, not the loosened validated
    d = numeral_word()
    (rec,) = _load(tmp_path, [d], "validated")
    assert rec.indic and not rec.signed_off
    _fails(
        tmp_path / "c",
        [d],
        "loads under a corroborated method only with owner_signoff",
        "corroborated",
    )
