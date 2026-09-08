"""Milestone 2.0B, items 9-15: deterministic evidence grounding.

Covers: GROUNDED/UNGROUNDED/AMBIGUOUS classification, offsets computed
locally (never trusted from the extractor), multiple identical occurrences
resolved via source_order only when it genuinely disambiguates, ungrounded
items redirected to `unmapped` rather than reaching MedicalState, and
stable occurrence identity that survives the extractor reordering its own
output.
"""

from exam_extraction.grounding import GroundingStatus, ground_candidate
from exam_extraction.models import (
    Evidence,
    ExamExtractionCandidate,
    ExamSourceEnvelope,
    GeneralLabCandidate,
)
from exam_normalization.occurrence_identity import compute_occurrence_key
from models.medical_state import SourceType


def _ev(text: str) -> Evidence:
    return Evidence(evidence_text=text)


def _envelope(raw_text: str, source_id: str = "SRC-GROUND") -> ExamSourceEnvelope:
    return ExamSourceEnvelope(
        source_id=source_id, patient_ref="PATIENT-GOLDEN-TEST",
        source_type=SourceType.MEDICAL_EVOLUTION, raw_text=raw_text,
    )


# --- basic classification ---------------------------------------------

def test_evidence_text_present_once_is_grounded_with_correct_offsets():
    raw_text = "31/08: HB 12,0; HT 36,0"
    candidate = ExamExtractionCandidate(
        source_id="SRC-1",
        general_labs=[
            GeneralLabCandidate(raw_name="HB", raw_value="12,0", source_order=1, evidence=_ev("HB 12,0"), source_ref="SRC-1"),
        ],
    )
    grounded, report = ground_candidate(candidate, _envelope(raw_text, "SRC-1"))
    obs = grounded.general_labs[0]
    assert obs.evidence.grounding_status == GroundingStatus.GROUNDED
    start, end = obs.evidence.char_start, obs.evidence.char_end
    assert raw_text[start:end] == "HB 12,0"
    assert report.grounded_count == 1
    assert report.ungrounded_count == 0
    assert report.ambiguous_count == 0


def test_evidence_text_absent_is_ungrounded_and_moved_to_unmapped():
    candidate = ExamExtractionCandidate(
        source_id="SRC-2",
        general_labs=[
            GeneralLabCandidate(raw_name="HB", raw_value="12,0", source_order=1, evidence=_ev("HB 99,9 (não está no texto)"), source_ref="SRC-2"),
        ],
    )
    grounded, report = ground_candidate(candidate, _envelope("31/08: HB 12,0", "SRC-2"))
    assert grounded.general_labs == []  # never silently kept as a clinical fact
    assert len(grounded.unmapped) == 1
    assert grounded.unmapped[0].evidence.grounding_status == GroundingStatus.UNGROUNDED
    assert report.ungrounded_count == 1


def test_offsets_are_computed_locally_never_from_extractor_input():
    # Even if the candidate arrives with char_start/char_end already set
    # (an extractor should never do this, but nothing stops a malformed
    # response from including them), grounding recomputes them itself.
    raw_text = "31/08: HB 12,0"
    ev = Evidence(evidence_text="HB 12,0", char_start=999, char_end=999)
    candidate = ExamExtractionCandidate(
        source_id="SRC-3",
        general_labs=[GeneralLabCandidate(raw_name="HB", raw_value="12,0", source_order=1, evidence=ev, source_ref="SRC-3")],
    )
    grounded, _ = ground_candidate(candidate, _envelope(raw_text, "SRC-3"))
    obs = grounded.general_labs[0]
    assert (obs.evidence.char_start, obs.evidence.char_end) == (7, 14)
    assert raw_text[7:14] == "HB 12,0"


# --- multiple identical occurrences (items 14-15) -----------------------

def test_single_item_with_text_appearing_twice_is_ambiguous():
    # Only one candidate claims this text, but it occurs twice in the
    # source -- source_order alone cannot say which occurrence is meant.
    raw_text = "31/08: NA 140\n01/09: NA 140"
    candidate = ExamExtractionCandidate(
        source_id="SRC-4",
        general_labs=[GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-4")],
    )
    grounded, report = ground_candidate(candidate, _envelope(raw_text, "SRC-4"))
    assert grounded.general_labs == []
    assert grounded.unmapped[0].evidence.grounding_status == GroundingStatus.AMBIGUOUS
    assert report.ambiguous_count == 1


def test_two_distinct_occurrences_are_both_grounded_at_different_spans():
    # Two genuinely distinct readings, identical text, different source
    # positions -- source_order resolves them cleanly (item 14).
    raw_text = "31/08 (13:20): NA 140\n01/09: NA 140"
    candidate = ExamExtractionCandidate(
        source_id="SRC-5",
        general_labs=[
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-5"),
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=2, evidence=_ev("NA 140"), source_ref="SRC-5"),
        ],
    )
    grounded, report = ground_candidate(candidate, _envelope(raw_text, "SRC-5"))
    assert len(grounded.general_labs) == 2
    assert all(o.evidence.grounding_status == GroundingStatus.GROUNDED for o in grounded.general_labs)
    spans = {(o.evidence.char_start, o.evidence.char_end) for o in grounded.general_labs}
    assert len(spans) == 2  # distinct spans, never collapsed to one
    assert report.grounded_count == 2


def test_reordering_the_same_two_candidates_yields_the_same_pair_of_spans():
    # Same source, LLM lists the two items in the opposite order -- the
    # resulting spans (and therefore occurrence identity) must be
    # identical regardless of list order (item 15).
    raw_text = "31/08 (13:20): NA 140\n01/09: NA 140"

    forward = ExamExtractionCandidate(
        source_id="SRC-6",
        general_labs=[
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-6"),
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=2, evidence=_ev("NA 140"), source_ref="SRC-6"),
        ],
    )
    reversed_order = ExamExtractionCandidate(
        source_id="SRC-6",
        general_labs=[
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=2, evidence=_ev("NA 140"), source_ref="SRC-6"),
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-6"),
        ],
    )

    envelope = _envelope(raw_text, "SRC-6")
    grounded_fwd, _ = ground_candidate(forward, envelope)
    grounded_rev, _ = ground_candidate(reversed_order, envelope)

    spans_fwd = sorted((o.evidence.char_start, o.evidence.char_end) for o in grounded_fwd.general_labs)
    spans_rev = sorted((o.evidence.char_start, o.evidence.char_end) for o in grounded_rev.general_labs)
    assert spans_fwd == spans_rev

    keys_fwd = {compute_occurrence_key("SRC-6", "general_lab", s, e) for s, e in spans_fwd}
    keys_rev = {compute_occurrence_key("SRC-6", "general_lab", s, e) for s, e in spans_rev}
    assert keys_fwd == keys_rev


def test_count_mismatch_between_items_and_occurrences_is_ambiguous():
    # 2 items claim the same text, but it only occurs once in the source.
    raw_text = "31/08: NA 140"
    candidate = ExamExtractionCandidate(
        source_id="SRC-7",
        general_labs=[
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-7"),
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=2, evidence=_ev("NA 140"), source_ref="SRC-7"),
        ],
    )
    grounded, report = ground_candidate(candidate, _envelope(raw_text, "SRC-7"))
    assert grounded.general_labs == []
    assert report.ambiguous_count == 2


# --- occurrence_identity module in isolation ----------------------------

def test_occurrence_key_is_deterministic_and_span_sensitive():
    key_a = compute_occurrence_key("SRC-X", "general_lab", 10, 17)
    key_b = compute_occurrence_key("SRC-X", "general_lab", 10, 17)
    key_c = compute_occurrence_key("SRC-X", "general_lab", 20, 27)
    assert key_a == key_b
    assert key_a != key_c
