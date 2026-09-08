"""Milestone 2.0A: ExamSourceEnvelope / ExamExtractionCandidate contract.

Confirms the extraction models are strict, independent of MedicalState,
and that an extractor genuinely has no way to write into MedicalState
without going through the candidate -> normalization -> batch -> apply
pipeline.
"""

import pytest
from pydantic import ValidationError

from exam_extraction.models import (
    Evidence,
    ExamExtractionCandidate,
    ExamSourceEnvelope,
    GeneralLabCandidate,
)
from models.medical_state import MedicalState, SourceType


def test_exam_source_envelope_requires_only_declared_fields():
    envelope = ExamSourceEnvelope(
        source_id="SRC-1", patient_ref="P-1", source_type=SourceType.MEDICAL_EVOLUTION,
        raw_text="HB 14,9; HT 44,5",
    )
    assert envelope.origin_context is None
    assert envelope.document_temporal_value is None
    assert envelope.metadata == {}


def test_exam_source_envelope_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ExamSourceEnvelope(
            source_id="SRC-1", patient_ref="P-1", source_type=SourceType.MEDICAL_EVOLUTION,
            raw_text="x", something_unexpected="oops",
        )


def test_candidate_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ExamExtractionCandidate(source_id="SRC-1", not_a_real_bucket=[])


def test_candidate_item_preserves_raw_fields_and_evidence():
    item = GeneralLabCandidate(
        raw_name="LEUCO", raw_value="12510", raw_unit="/mm3", raw_reference_range="4000-10000",
        raw_temporal="03/09 (04:21)", source_order=1,
        evidence=Evidence(evidence_text="LEUCOCITOSE (LC 12510)"),
        source_ref="SRC-1", canonical_hint="LC",
    )
    assert item.raw_name == "LEUCO"
    assert item.raw_value == "12510"
    assert item.raw_unit == "/mm3"
    assert item.raw_reference_range == "4000-10000"
    assert item.raw_temporal == "03/09 (04:21)"
    assert item.evidence.evidence_text == "LEUCOCITOSE (LC 12510)"
    assert item.canonical_hint == "LC"


def test_evidence_is_extensible_without_breaking_the_contract():
    # page/line/char span/bounding box are reserved for future OCR/vision
    # extractors (item 3) -- they must be settable today even though
    # nothing in Milestone 2.0A populates them from real documents.
    evidence = Evidence(evidence_text="HB 14,9", page=2, line=17, char_start=100, char_end=107)
    assert evidence.page == 2
    assert evidence.bounding_box is None


def test_extraction_candidate_is_not_medical_state():
    # The candidate contract must never reuse MedicalState as its own type
    # (item 4's "não reutilize MedicalState como candidate" applies to the
    # whole extraction/normalization boundary).
    candidate = ExamExtractionCandidate(source_id="SRC-1")
    assert not isinstance(candidate, MedicalState)
    assert "MedicalState" not in {base.__name__ for base in ExamExtractionCandidate.__mro__}
