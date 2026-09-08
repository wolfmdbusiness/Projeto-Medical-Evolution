"""Milestone 2.0A, item 23: unit-level normalization test cases.

Covers aliases, numeric parsing, temporal parsing, reference range parsing,
and specimen type resolution in isolation from the orchestrator.
"""

import pytest

from exam_normalization.aliases import resolve_canonical_id
from exam_normalization.numeric_parsing import parse_numeric_value
from exam_normalization.reference_range import parse_reference_range
from exam_normalization.specimen import resolve_specimen_type
from exam_normalization.temporal import parse_exam_temporal
from models.medical_state import ComparisonOperator, GasSpecimenType, TemporalPrecision, ValidationStatus


# --- aliases (item 6) --------------------------------------------------

@pytest.mark.parametrize("raw_name,expected_canonical", [
    ("LEUCO", "LC"),
    ("LEUCÓCITOS", "LC"),
    ("PLQ", "PLAQ"),
    ("PLAQ", "PLAQ"),
    ("RNI", "INR"),
    ("INR", "INR"),
    ("U", "UR"),
    ("UR", "UR"),
    ("AST", "TGO"),
    ("TGO", "TGO"),
    ("ALT", "TGP"),
    ("TGP", "TGP"),
])
def test_known_aliases_resolve_to_canonical_id(raw_name, expected_canonical):
    assert resolve_canonical_id(raw_name) == expected_canonical


def test_ca1_is_never_silently_corrected_to_cai():
    # CA1 has no safe, evidenced alias to CAI -- it must resolve to itself.
    assert resolve_canonical_id("CA1") == "CA1"
    assert resolve_canonical_id("CA1") != "CAI"


def test_unlisted_alias_passes_through_unchanged():
    assert resolve_canonical_id("SOME_UNSEEN_ANALYTE") == "SOME_UNSEEN_ANALYTE"


# --- numeric parsing (item 7) -------------------------------------------

def test_operator_lt_with_comma_decimal():
    value = parse_numeric_value("<0,6")
    assert value.raw_value == "<0,6"
    assert value.operator == ComparisonOperator.LT
    assert value.normalized_numeric_value == 0.6
    assert value.display_value == "<0,6"


def test_operator_gt_plain_integer():
    value = parse_numeric_value(">4000")
    assert value.operator == ComparisonOperator.GT
    assert value.normalized_numeric_value == 4000.0
    assert value.raw_value == ">4000"  # never collapsed to "4000"


def test_operator_gt_small_integer():
    value = parse_numeric_value(">90")
    assert value.operator == ComparisonOperator.GT
    assert value.normalized_numeric_value == 90.0


def test_operator_lt_with_comma_decimal_second_case():
    value = parse_numeric_value("<2,0")
    assert value.operator == ComparisonOperator.LT
    assert value.normalized_numeric_value == 2.0


def test_operators_lte_gte_eq_are_supported():
    assert parse_numeric_value("<=10").operator == ComparisonOperator.LTE
    assert parse_numeric_value(">=10").operator == ComparisonOperator.GTE
    assert parse_numeric_value("=10").operator == ComparisonOperator.EQ


# --- K suffix (item 8) ---------------------------------------------------

def test_k_suffix_expands_in_safe_context():
    value = parse_numeric_value("253K", canonical_id="PLAQ")
    assert value.raw_value == "253K"
    assert value.display_value == "253K"
    assert value.normalized_numeric_value == 253000.0


def test_k_suffix_does_not_expand_outside_safe_context():
    # No universal "anything ending in K" rule (item 8).
    value = parse_numeric_value("253K", canonical_id="MG")
    assert value.raw_value == "253K"
    assert value.normalized_numeric_value is None


def test_k_suffix_without_canonical_id_does_not_expand():
    value = parse_numeric_value("253K")
    assert value.normalized_numeric_value is None
    assert value.raw_value == "253K"


# --- reference range (item 9) --------------------------------------------

def test_one_sided_reference_range_is_preserved_raw():
    ref = parse_reference_range("VR <500")
    assert ref.reference_raw == "VR <500"
    assert ref.upper == 500.0
    assert ref.lower is None


def test_reference_range_without_vr_prefix():
    ref = parse_reference_range("<500")
    assert ref.upper == 500.0
    assert ref.reference_raw == "<500"


def test_unparseable_reference_range_keeps_raw_text_only():
    ref = parse_reference_range("4000-10000")
    assert ref.reference_raw == "4000-10000"
    assert ref.lower is None
    assert ref.upper is None


def test_missing_reference_range_is_none():
    assert parse_reference_range(None) is None
    assert parse_reference_range("") is None


# --- temporal (item 10) ---------------------------------------------------

def test_date_with_time_in_parens():
    tv = parse_exam_temporal("31/08 (13:20)", reference_year=2026)
    assert tv.raw == "31/08 (13:20)"
    assert tv.normalized == "2026-08-31T13:20:00"
    assert tv.precision == TemporalPrecision.DATE_TIME
    assert tv.validation_status == ValidationStatus.NORMALIZED


def test_full_date_with_year():
    tv = parse_exam_temporal("31/08/2026")
    assert tv.raw == "31/08/2026"
    assert tv.normalized == "2026-08-31"
    assert tv.precision == TemporalPrecision.DATE


def test_bare_date_without_year_or_reference_stays_partial():
    tv = parse_exam_temporal("31/08")
    assert tv.raw == "31/08"
    assert tv.normalized is None
    assert tv.precision == TemporalPrecision.PARTIAL_DATE


def test_impossible_date_is_preserved_raw_and_flagged_invalid():
    tv = parse_exam_temporal("31/09", reference_year=2026)
    assert tv.raw == "31/09"
    assert tv.normalized is None
    assert tv.validation_status == ValidationStatus.UNRESOLVED


def test_impossible_date_without_reference_year_is_also_flagged():
    tv = parse_exam_temporal("31/09")
    assert tv.raw == "31/09"
    assert tv.normalized is None
    assert tv.validation_status == ValidationStatus.UNRESOLVED


def test_never_invents_a_missing_time():
    tv = parse_exam_temporal("31/08/2026")
    assert tv.normalized == "2026-08-31"
    assert "T" not in tv.normalized


# --- specimen type (item 13) ----------------------------------------------

def test_venosa_normalizes_to_venous():
    assert resolve_specimen_type("VENOSA") == GasSpecimenType.VENOUS


def test_unknown_specimen_text_stays_unknown():
    assert resolve_specimen_type(None) == GasSpecimenType.UNKNOWN
    assert resolve_specimen_type("ALGO_NAO_MAPEADO") == GasSpecimenType.UNKNOWN
