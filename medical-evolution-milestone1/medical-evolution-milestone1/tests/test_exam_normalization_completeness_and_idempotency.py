"""Milestone 2.0A, items 19–20: completeness accounting and idempotency."""

from exam_extraction.models import (
    Evidence,
    ExamExtractionCandidate,
    ExamSourceEnvelope,
    GeneralLabCandidate,
    UnmappedCandidate,
)
from exam_normalization.completeness import compute_completeness
from exam_normalization.orchestrator import normalize_extraction_candidate
from exam_normalization.apply import apply_exam_batch
from models.medical_state import MedicalState, Meta, SourceType


def _ev(text: str) -> Evidence:
    return Evidence(evidence_text=text)


def _envelope(source_id: str = "SRC-COMPLETE") -> ExamSourceEnvelope:
    return ExamSourceEnvelope(
        source_id=source_id, patient_ref="PATIENT-GOLDEN-TEST",
        source_type=SourceType.MEDICAL_EVOLUTION, raw_text="(fragment)",
    )


def _state() -> MedicalState:
    return MedicalState(meta=Meta(state_id="S-COMPLETE"), patient_ref="PATIENT-GOLDEN-TEST")


# --- completeness accounting (item 20) ------------------------------------

def test_completeness_holds_for_a_fully_normalizable_batch():
    candidate = ExamExtractionCandidate(
        source_id="SRC-A",
        general_labs=[
            GeneralLabCandidate(raw_name="HB", raw_value="14,9", source_order=1, evidence=_ev("HB 14,9"), source_ref="SRC-A"),
            GeneralLabCandidate(raw_name="HT", raw_value="44,5", source_order=2, evidence=_ev("HT 44,5"), source_ref="SRC-A"),
        ],
        unmapped=[UnmappedCandidate(raw_text="ALGO NAO CLASSIFICADO", evidence=_ev("ALGO NAO CLASSIFICADO"), source_ref="SRC-A")],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-A"))
    report = compute_completeness(candidate, batch)
    assert report.items_extracted == 3
    assert report.items_normalized == 2
    assert report.items_unmapped == 1
    assert report.items_conflicting == 0
    assert report.is_complete


def test_item_missing_raw_value_becomes_a_conflict_not_a_silent_drop():
    candidate = ExamExtractionCandidate(
        source_id="SRC-B",
        general_labs=[
            GeneralLabCandidate(raw_name="NA", raw_value=None, source_order=1, evidence=_ev("NA <sem valor legível>"), source_ref="SRC-B"),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-B"))
    report = compute_completeness(candidate, batch)
    assert report.items_extracted == 1
    assert report.items_normalized == 0
    assert report.items_conflicting == 1
    assert report.is_complete
    assert batch.conflicts[0].category == "MISSING_VALUE"


def test_completeness_accounts_for_nested_blood_gas_observations():
    from exam_extraction.models import BloodGasCandidate, BloodGasObservationCandidate

    candidate = ExamExtractionCandidate(
        source_id="SRC-C",
        blood_gases=[
            BloodGasCandidate(
                raw_specimen_type="ARTERIAL", source_order=1, evidence=_ev("gas panel"), source_ref="SRC-C",
                observations=[
                    BloodGasObservationCandidate(raw_name="PH", raw_value="7,40", source_order=1, evidence=_ev("PH 7,40"), source_ref="SRC-C"),
                    BloodGasObservationCandidate(raw_name="PCO2", raw_value="40,0", source_order=2, evidence=_ev("PCO2 40,0"), source_ref="SRC-C"),
                ],
            ),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-C"))
    report = compute_completeness(candidate, batch)
    # 1 gas panel + 2 nested observations extracted; 1 panel + 2 nested
    # observations normalized.
    assert report.items_extracted == 3
    assert report.items_normalized == 3
    assert report.is_complete


# --- idempotency (item 19) ------------------------------------------------

def test_reprocessing_the_same_source_does_not_duplicate():
    candidate = ExamExtractionCandidate(
        source_id="SRC-IDEMP",
        general_labs=[
            GeneralLabCandidate(raw_name="HB", raw_value="14,9", source_order=1, evidence=_ev("HB 14,9"), source_ref="SRC-IDEMP"),
            GeneralLabCandidate(raw_name="HT", raw_value="44,5", source_order=2, evidence=_ev("HT 44,5"), source_ref="SRC-IDEMP"),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-IDEMP"))

    state = _state()
    once = apply_exam_batch(state, batch)
    twice = apply_exam_batch(once, batch)

    assert len(once.complementary_exams.laboratory_observations) == 2
    assert len(twice.complementary_exams.laboratory_observations) == 2  # not 4


def test_reprocessing_a_different_source_does_add_new_items():
    candidate_a = ExamExtractionCandidate(
        source_id="SRC-A2",
        general_labs=[GeneralLabCandidate(raw_name="HB", raw_value="14,9", source_order=1, evidence=_ev("HB 14,9"), source_ref="SRC-A2")],
    )
    candidate_b = ExamExtractionCandidate(
        source_id="SRC-B2",
        general_labs=[GeneralLabCandidate(raw_name="HB", raw_value="13,0", source_order=1, evidence=_ev("HB 13,0"), source_ref="SRC-B2")],
    )
    batch_a = normalize_extraction_candidate(candidate_a, _envelope("SRC-A2"))
    batch_b = normalize_extraction_candidate(candidate_b, _envelope("SRC-B2"))

    state = _state()
    state = apply_exam_batch(state, batch_a)
    state = apply_exam_batch(state, batch_b)
    assert len(state.complementary_exams.laboratory_observations) == 2


def test_apply_exam_batch_does_not_mutate_the_original_state():
    candidate = ExamExtractionCandidate(
        source_id="SRC-PURE",
        general_labs=[GeneralLabCandidate(raw_name="HB", raw_value="14,9", source_order=1, evidence=_ev("HB 14,9"), source_ref="SRC-PURE")],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-PURE"))
    state = _state()
    new_state = apply_exam_batch(state, batch)

    assert len(state.complementary_exams.laboratory_observations) == 0
    assert len(new_state.complementary_exams.laboratory_observations) == 1
    assert state is not new_state


# --- idempotency vs. legitimate repeated occurrences (Milestone 2.0A.1,
# item 4): reapplying the same batch never duplicates, but two genuinely
# distinct occurrences sharing identical name/date/result are still both
# preserved -- identity comes from source_order/processing_key, never from
# content equality. --------------------------------------------------------

def test_reapplying_the_identical_batch_never_duplicates_processing_metadata():
    candidate = ExamExtractionCandidate(
        source_id="SRC-IDEMP-META",
        general_labs=[
            GeneralLabCandidate(raw_name="NA", raw_value="140", raw_temporal="31/08", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-IDEMP-META"),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-IDEMP-META"))

    state = _state()
    once = apply_exam_batch(state, batch)
    twice = apply_exam_batch(once, batch)

    assert len(once.complementary_exams.laboratory_observations) == 1
    assert len(twice.complementary_exams.laboratory_observations) == 1
    # processing_metadata itself must not grow on reprocessing either.
    assert len(once.provenance.processing_metadata) == 1
    assert len(twice.provenance.processing_metadata) == 1
    key = twice.complementary_exams.laboratory_observations[0].processing_key
    assert key is not None
    assert twice.provenance.processing_metadata[0].processing_key == key


def test_two_distinct_occurrences_with_identical_name_date_and_result_are_both_preserved():
    # Two lines in the *same* source document, same analyte, same raw date,
    # same raw value -- but genuinely two separate readings (e.g. a repeat
    # draw reported twice verbatim). They must never be collapsed into one
    # just because their content is identical: identity is source_order,
    # not content.
    candidate = ExamExtractionCandidate(
        source_id="SRC-REPEAT",
        general_labs=[
            GeneralLabCandidate(raw_name="K", raw_value="4,2", raw_temporal="31/08 (08:00)", source_order=1, evidence=_ev("K 4,2 (1a coleta)"), source_ref="SRC-REPEAT"),
            GeneralLabCandidate(raw_name="K", raw_value="4,2", raw_temporal="31/08 (08:00)", source_order=2, evidence=_ev("K 4,2 (repetido)"), source_ref="SRC-REPEAT"),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-REPEAT"))
    assert len(batch.laboratory_observations) == 2  # never deduplicated by content
    keys = {obs.processing_key for obs in batch.laboratory_observations}
    assert len(keys) == 2  # distinct processing_key per source_order

    state = _state()
    applied = apply_exam_batch(state, batch)
    assert len(applied.complementary_exams.laboratory_observations) == 2
    assert len(applied.provenance.processing_metadata) == 2

    # Reapplying the same batch again still does not duplicate either one.
    reapplied = apply_exam_batch(applied, batch)
    assert len(reapplied.complementary_exams.laboratory_observations) == 2
    assert len(reapplied.provenance.processing_metadata) == 2


# --- source_refs stays purely clinical (Milestone 2.0A.1, item 1) --------

def test_source_refs_never_carries_a_processing_or_idempotency_marker():
    candidate = ExamExtractionCandidate(
        source_id="SRC-CLEAN-REFS",
        general_labs=[
            GeneralLabCandidate(raw_name="HB", raw_value="14,9", source_order=1, evidence=_ev("HB 14,9"), source_ref="SRC-CLEAN-REFS"),
        ],
    )
    batch = normalize_extraction_candidate(candidate, _envelope("SRC-CLEAN-REFS"))
    obs = batch.laboratory_observations[0]
    assert obs.source_refs == ["SRC-CLEAN-REFS"]
    assert obs.processing_key is not None
    assert all("MOD-EXAMES" not in ref and "IDEMP" not in ref for ref in obs.source_refs)

    state = _state()
    applied = apply_exam_batch(state, batch)
    entry = applied.provenance.processing_metadata[0]
    assert entry.processing_key == obs.processing_key
    assert entry.source_id == "SRC-CLEAN-REFS"
    assert entry.module == "MOD-EXAMES"
