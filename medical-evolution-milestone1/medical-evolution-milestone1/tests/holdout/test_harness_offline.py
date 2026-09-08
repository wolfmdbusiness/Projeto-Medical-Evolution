"""Offline unit tests for the M2.0C holdout scoring harness itself
(`tests/holdout/harness.py`). No network call, no live extractor -- these
prove the scoring logic is correct against small, hand-built
`NormalizedExamBatch`/`ExamExtractionCandidate` fixtures, independent of
any live DeepSeek response.
"""

from exam_extraction.models import (
    Evidence,
    ExamExtractionCandidate,
    GeneralLabCandidate,
)
from exam_normalization.models import NormalizedExamBatch
from models.medical_state import (
    Analyte,
    LabObservation,
    ObservationValue,
    SourceType,
    UnitValue,
)
from tests.holdout.harness import (
    build_envelope,
    load_holdout,
    score_source,
    validate_fixture_consistency,
)


def _obs(raw_name: str, raw_value: str) -> LabObservation:
    return LabObservation(
        observation_id=f"OBS-{raw_name}",
        analyte=Analyte(raw_name=raw_name, canonical_id=None, display_name=raw_name),
        value=ObservationValue(raw_value=raw_value),
        unit=UnitValue(),
    )


def _cand(raw_name: str, raw_value: str, evidence_text: str) -> GeneralLabCandidate:
    return GeneralLabCandidate(
        raw_name=raw_name, raw_value=raw_value, source_order=1,
        evidence=Evidence(evidence_text=evidence_text), source_ref="SRC-1",
    )


# --- fixture loading / consistency ----------------------------------------

def test_the_real_holdout_001_fixtures_are_internally_consistent():
    sources, ground_truth = load_holdout("holdout_001")
    problems = validate_fixture_consistency(sources, ground_truth)
    assert problems == []
    assert len(sources["sources"]) == 13


def test_build_envelope_maps_source_type_and_sets_reference_date():
    sources, _ = load_holdout("holdout_001")
    source = next(s for s in sources["sources"] if s["source_id"] == "H001-LAB-20260726")
    envelope = build_envelope(source)
    assert envelope.source_type == SourceType.EXTERNAL_LAB_REPORT
    assert envelope.document_temporal_value.normalized == "2026-07-26"
    assert envelope.raw_text == source["raw_text"]


# --- scoring: captured / missing current values ----------------------------

def test_score_source_reports_all_current_values_captured():
    candidate = ExamExtractionCandidate(source_id="SRC-1", general_labs=[
        _cand("HB", "13,1", "HB 13,1"),
    ])
    batch = NormalizedExamBatch(source_id="SRC-1", laboratory_observations=[_obs("HB", "13,1")])
    expectation = {"must_capture_current_values": [["HB", "13,1"]]}
    score = score_source("SRC-1", candidate, batch, expectation)
    assert score.captured_current == 1
    assert score.missing_current == []
    assert score.all_required_met


def test_score_source_reports_missing_current_value():
    candidate = ExamExtractionCandidate(source_id="SRC-1", general_labs=[])
    batch = NormalizedExamBatch(source_id="SRC-1", laboratory_observations=[])
    expectation = {"must_capture_current_values": [["HB", "13,1"]]}
    score = score_source("SRC-1", candidate, batch, expectation)
    assert score.captured_current == 0
    assert score.missing_current == ["HB=13,1"]
    assert not score.all_required_met


def test_value_matching_tolerates_operator_and_decimal_separator():
    candidate = ExamExtractionCandidate(source_id="SRC-1", general_labs=[
        _cand("PCR", "<0.6", "PCR <0.6"),
    ])
    batch = NormalizedExamBatch(source_id="SRC-1", laboratory_observations=[_obs("PCR", "<0.6")])
    expectation = {"must_capture_current_values": [["PCR", "<0,6"]]}
    score = score_source("SRC-1", candidate, batch, expectation)
    assert score.captured_current == 1


# --- safety-critical: historical-as-current contamination ------------------

def test_historical_as_current_contamination_is_detected():
    # The batch (simulating a mistake) carries the OLD value for HB, which
    # is exactly what must_not_promote_previous_as_current guards against.
    candidate = ExamExtractionCandidate(source_id="SRC-1", general_labs=[])
    batch = NormalizedExamBatch(source_id="SRC-1", laboratory_observations=[_obs("Hemoglobina", "12.6")])
    expectation = {"must_not_promote_previous_as_current": [["Hemoglobina", "12.6"]]}
    score = score_source("SRC-1", candidate, batch, expectation)
    assert score.historical_as_current_hits == ["Hemoglobina=12.6"]
    assert not score.all_required_met


def test_no_contamination_when_historical_value_is_absent():
    candidate = ExamExtractionCandidate(source_id="SRC-1", general_labs=[])
    batch = NormalizedExamBatch(source_id="SRC-1", laboratory_observations=[_obs("Hemoglobina", "13.3")])
    expectation = {"must_not_promote_previous_as_current": [["Hemoglobina", "12.6"]]}
    score = score_source("SRC-1", candidate, batch, expectation)
    assert score.historical_as_current_hits == []


# --- safety-critical: unsafe normalization ---------------------------------

def test_unsafe_normalization_detected_when_value_not_in_its_own_evidence():
    candidate = ExamExtractionCandidate(source_id="SRC-1", general_labs=[
        _cand("HB", "13,1", "HB 99,9"),  # evidence does not actually contain "13,1"
    ])
    batch = NormalizedExamBatch(source_id="SRC-1", laboratory_observations=[_obs("HB", "13,1")])
    expectation = {"must_capture_current_values": [["HB", "13,1"]]}
    score = score_source("SRC-1", candidate, batch, expectation)
    assert len(score.unsafe_normalization_hits) == 1
    assert not score.all_required_met


def test_no_unsafe_normalization_when_value_is_in_its_own_evidence():
    candidate = ExamExtractionCandidate(source_id="SRC-1", general_labs=[
        _cand("HB", "13,1", "HB 13,1"),
    ])
    batch = NormalizedExamBatch(source_id="SRC-1", laboratory_observations=[_obs("HB", "13,1")])
    expectation = {"must_capture_current_values": [["HB", "13,1"]]}
    score = score_source("SRC-1", candidate, batch, expectation)
    assert score.unsafe_normalization_hits == []
