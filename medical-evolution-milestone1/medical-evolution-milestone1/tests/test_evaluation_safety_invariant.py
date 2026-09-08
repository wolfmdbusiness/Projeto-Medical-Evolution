"""Milestone 2.0B.2, item 6 (splitting `true_hallucination_rate` from
`ambiguity_rate`) and Milestone 2.0C.1, items 3-4-7 (splitting
`support_status` from `localization_status`, and accepting a
legitimately multiply-supported single item) are reporting/acceptance
changes with one hard constraint: they must never let a genuinely
UNGROUNDED item, a genuinely UNRESOLVED (competing-items) item, or a
schema-invalid response reach `MedicalState` any more easily than before.
`exam_extraction.grounding`'s safety gate is pinned down explicitly here
so a future change to it, or to the evaluation module, can't silently
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
    assert result.metadata.accepted_count == 0


def test_single_item_restated_twice_is_now_accepted_not_blocked():
    # Milestone 2.0C.1's actual behavior change (items 3/4/6/7): a single
    # item whose evidence is real and simply restated -- no competing
    # item -- is no longer treated as if it were ambiguous. This is the
    # HOLDOUT-001 fix (docs/mod_exames_2_0c_holdout_findings.md), pinned
    # down here as the new, deliberate expected outcome.
    candidate = ExamExtractionCandidate(
        source_id="SRC-SAFE-2",
        general_labs=[
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-SAFE-2"),
        ],
    )
    extractor = FakeExamExtractor({"SRC-SAFE-2": candidate})
    result = run_extraction(_envelope("SRC-SAFE-2", "31/08: NA 140\n01/09: NA 140"), extractor, provider="FAKE", model="fake-v0")
    assert result.metadata.status == ExecutionStatus.SUCCESS
    assert len(result.batch.laboratory_observations) == 1
    assert result.batch.unmapped == []
    assert result.metadata.ungrounded_count == 0
    assert result.metadata.localization_multiple_count == 1
    assert result.metadata.accepted_count == 1


def test_genuinely_competing_items_still_blocked_as_localization_unresolved():
    # The real safety case Milestone 2.0C.1 preserves (item 7): TWO items
    # competing for text that occurs only once cannot be told apart, so
    # this -- unlike the single-item case above -- stays blocked.
    candidate = ExamExtractionCandidate(
        source_id="SRC-SAFE-2B",
        general_labs=[
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-SAFE-2B"),
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=2, evidence=_ev("NA 140"), source_ref="SRC-SAFE-2B"),
        ],
    )
    extractor = FakeExamExtractor({"SRC-SAFE-2B": candidate})
    result = run_extraction(_envelope("SRC-SAFE-2B", "31/08: NA 140"), extractor, provider="FAKE", model="fake-v0")
    assert result.metadata.status == ExecutionStatus.SUCCESS
    assert result.batch.laboratory_observations == []
    assert len(result.batch.unmapped) == 2
    assert result.metadata.localization_unresolved_count == 2
    assert result.metadata.accepted_count == 0
    # Still never mislabeled as a hallucination -- the text is real.
    assert result.metadata.ungrounded_count == 0


def test_schema_invalid_extractor_output_never_produces_a_batch():
    extractor = FakeExamExtractor({})  # no recorded response -> explicit ProviderFailure
    result = run_extraction(_envelope("SRC-SAFE-3", "31/08: HB 12,0"), extractor, provider="FAKE", model="fake-v0")
    assert result.metadata.status != ExecutionStatus.SUCCESS
    assert result.batch is None
