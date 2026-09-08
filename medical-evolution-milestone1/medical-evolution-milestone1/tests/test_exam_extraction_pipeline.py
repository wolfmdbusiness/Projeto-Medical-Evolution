"""Milestone 2.0B: end-to-end pipeline tests through
`exam_extraction.execution.run_extraction` (extractor -> grounding ->
normalization -> apply), using `FakeExamExtractor` so the whole thing runs
offline. Covers item 16 (occurrence identity integrated into the existing
processing_key/idempotency machinery, never back into `source_refs`) and
item 17 (canonical_hint is never authoritative, even end-to-end).
"""

from exam_extraction.base import ProviderFailure
from exam_extraction.execution import ExecutionStatus, run_extraction
from exam_extraction.fake import FakeExamExtractor
from exam_extraction.models import (
    Evidence,
    ExamExtractionCandidate,
    ExamSourceEnvelope,
    GeneralLabCandidate,
)
from exam_normalization.apply import apply_exam_batch
from models.medical_state import MedicalState, Meta, SourceType, ValidationStatus


def _ev(text: str) -> Evidence:
    return Evidence(evidence_text=text)


def _envelope(source_id: str, raw_text: str) -> ExamSourceEnvelope:
    return ExamSourceEnvelope(
        source_id=source_id, patient_ref="PATIENT-GOLDEN-TEST",
        source_type=SourceType.MEDICAL_EVOLUTION, raw_text=raw_text,
    )


def _state() -> MedicalState:
    return MedicalState(meta=Meta(state_id="S-PIPELINE"), patient_ref="PATIENT-GOLDEN-TEST")


# --- item 17: canonical_hint is never authoritative, end-to-end ---------

def test_canonical_hint_never_overrides_the_alias_registry_end_to_end():
    raw_text = "31/08: CA1 1,33"
    candidate = ExamExtractionCandidate(
        source_id="SRC-CA1-E2E",
        general_labs=[
            GeneralLabCandidate(
                raw_name="CA1", raw_value="1,33", raw_temporal="31/08", source_order=1,
                evidence=_ev("CA1 1,33"), source_ref="SRC-CA1-E2E",
                canonical_hint="CAI",  # the LLM's own (wrong) guess
            ),
        ],
    )
    extractor = FakeExamExtractor({"SRC-CA1-E2E": candidate})
    envelope = _envelope("SRC-CA1-E2E", raw_text)

    result = run_extraction(envelope, extractor, provider="FAKE", model="fake-v0")
    assert result.metadata.status == ExecutionStatus.SUCCESS

    obs = result.batch.laboratory_observations[0]
    assert obs.analyte.raw_name == "CA1"
    assert obs.analyte.canonical_id is None  # never "CAI", never "CA1"
    assert obs.validation_status == ValidationStatus.UNRESOLVED


# --- item 16: occurrence identity feeds processing_key, never source_refs

def test_occurrence_identity_prevents_duplicate_application_across_runs():
    raw_text = "31/08: NA 140"
    candidate = ExamExtractionCandidate(
        source_id="SRC-DUP",
        general_labs=[GeneralLabCandidate(raw_name="NA", raw_value="140", raw_temporal="31/08", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-DUP")],
    )
    extractor = FakeExamExtractor({"SRC-DUP": candidate})
    envelope = _envelope("SRC-DUP", raw_text)

    result = run_extraction(envelope, extractor, provider="FAKE", model="fake-v0")
    obs = result.batch.laboratory_observations[0]
    assert obs.processing_key is not None
    assert obs.source_refs == ["SRC-DUP"]  # purely clinical, no marker

    state = _state()
    once = apply_exam_batch(state, result.batch)
    twice = apply_exam_batch(once, result.batch)
    assert len(once.complementary_exams.laboratory_observations) == 1
    assert len(twice.complementary_exams.laboratory_observations) == 1
    assert len(twice.provenance.processing_metadata) == 1


def test_two_grounded_occurrences_at_different_spans_both_survive_apply():
    raw_text = "31/08 (13:20): NA 140\n01/09: NA 140"
    candidate = ExamExtractionCandidate(
        source_id="SRC-TWO-SPANS",
        general_labs=[
            GeneralLabCandidate(raw_name="NA", raw_value="140", raw_temporal="31/08 (13:20)", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-TWO-SPANS"),
            GeneralLabCandidate(raw_name="NA", raw_value="140", raw_temporal="01/09", source_order=2, evidence=_ev("NA 140"), source_ref="SRC-TWO-SPANS"),
        ],
    )
    extractor = FakeExamExtractor({"SRC-TWO-SPANS": candidate})
    envelope = _envelope("SRC-TWO-SPANS", raw_text)

    result = run_extraction(envelope, extractor, provider="FAKE", model="fake-v0")
    assert len(result.batch.laboratory_observations) == 2
    keys = {o.processing_key for o in result.batch.laboratory_observations}
    assert len(keys) == 2  # distinct occurrence identity per span

    state = _state()
    applied = apply_exam_batch(state, result.batch)
    assert len(applied.complementary_exams.laboratory_observations) == 2


# --- unresolved source_id is an explicit failure, never a silent empty result

def test_extractor_with_no_recorded_response_fails_explicitly():
    extractor = FakeExamExtractor({})
    envelope = _envelope("SRC-MISSING", "31/08: HB 12,0")
    result = run_extraction(envelope, extractor, provider="FAKE", model="fake-v0")
    assert result.metadata.status == ExecutionStatus.PROVIDER_FAILURE
    assert result.batch is None
    assert result.metadata.error_code == "PROVIDER_FAILURE"
