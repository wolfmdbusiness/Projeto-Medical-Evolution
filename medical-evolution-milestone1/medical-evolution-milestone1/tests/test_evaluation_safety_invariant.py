"""Milestone 2.0B.2, item 6: splitting true_hallucination_rate from
ambiguity_rate (item 5) is a reporting change only -- it must not let
UNGROUNDED, AMBIGUOUS, or schema-invalid items reach `MedicalState` any
more easily than before. `exam_extraction.grounding` itself is untouched
by this milestone; this test pins that invariant down explicitly against
the new evaluation module so a future change to either can't silently
regress it.
"""

from exam_extraction.execution import ExecutionStatus, run_extraction
from exam_extraction.fake import FakeExamExtractor
from exam_extraction.models import Evidence, ExamExtractionCandidate, ExamSourceEnvelope, GeneralLabCandidate
from models.medical_state import SourceType


def _ev(text: str) -> Evidence:
    return Evidence(evidence_text=text)


def _envelope(source_id: str, raw_text: str) -> ExamSourceEnvelope:
    return ExamSourceEnvelope(
        source_id=source_id, patient_ref="PATIENT-GOLDEN-TEST",
        source_type=SourceType.MEDICAL_EVOLUTION, raw_text=raw_text,
    )


def test_ungrounded_item_still_never_reaches_a_clinical_bucket():
    candidate = ExamExtractionCandidate(
        source_id="SRC-SAFE-1",
        general_labs=[
            GeneralLabCandidate(raw_name="HB", raw_value="99,9", source_order=1, evidence=_ev("HB 99,9 -- not in the source"), source_ref="SRC-SAFE-1"),
        ],
    )
    extractor = FakeExamExtractor({"SRC-SAFE-1": candidate})
    result = run_extraction(_envelope("SRC-SAFE-1", "31/08: HB 12,0"), extractor, provider="FAKE", model="fake-v0")
    assert result.metadata.status == ExecutionStatus.SUCCESS
    assert result.batch.laboratory_observations == []
    assert len(result.batch.unmapped) == 1
    assert result.metadata.ungrounded_count == 1


def test_ambiguous_item_still_never_reaches_a_clinical_bucket():
    # Text occurs twice, only one candidate claims it -- unresolvable.
    candidate = ExamExtractionCandidate(
        source_id="SRC-SAFE-2",
        general_labs=[
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-SAFE-2"),
        ],
    )
    extractor = FakeExamExtractor({"SRC-SAFE-2": candidate})
    result = run_extraction(_envelope("SRC-SAFE-2", "31/08: NA 140\n01/09: NA 140"), extractor, provider="FAKE", model="fake-v0")
    assert result.metadata.status == ExecutionStatus.SUCCESS
    assert result.batch.laboratory_observations == []
    assert len(result.batch.unmapped) == 1
    assert result.metadata.ambiguous_count == 1


def test_schema_invalid_extractor_output_never_produces_a_batch():
    extractor = FakeExamExtractor({})  # no recorded response -> explicit ProviderFailure
    result = run_extraction(_envelope("SRC-SAFE-3", "31/08: HB 12,0"), extractor, provider="FAKE", model="fake-v0")
    assert result.metadata.status != ExecutionStatus.SUCCESS
    assert result.batch is None
