"""Milestone 2.0B, items 22-24: evaluation harness + the required
snippet corpus, run offline against the recorded/synthetic fixtures under
`exam_extraction/fixtures/recorded_responses/` (item 19) via
`FakeExamExtractor` (item 18). No network call in this file.
"""

import pytest

from exam_extraction.evaluation import EvaluationResult, ExpectedItem, evaluate_extraction
from exam_extraction.execution import ExecutionStatus, run_extraction
from exam_extraction.fake import FakeExamExtractor, load_recorded_responses
from exam_extraction.fixtures.snippets import EXPECTED_ITEMS, SNIPPETS
from exam_extraction.grounding import GroundingReport, GroundingRecord, GroundingStatus
from exam_extraction.models import ExamSourceEnvelope
from exam_normalization.models import NormalizedExamBatch
from models.medical_state import SourceType


def _envelope(source_id: str) -> ExamSourceEnvelope:
    return ExamSourceEnvelope(
        source_id=source_id, patient_ref="PATIENT-GOLDEN-TEST",
        source_type=SourceType.MEDICAL_EVOLUTION, raw_text=SNIPPETS[source_id],
    )


@pytest.fixture(scope="module")
def recorded_extractor() -> FakeExamExtractor:
    return FakeExamExtractor(load_recorded_responses())


# --- harness math, on synthetic inputs (no dependency on real fixtures) --

def test_perfect_match_yields_precision_and_recall_of_one():
    report = GroundingReport(records=[
        GroundingRecord("general_lab", "HB", GroundingStatus.GROUNDED, 0, 7),
        GroundingRecord("general_lab", "HT", GroundingStatus.GROUNDED, 8, 15),
    ])
    batch = NormalizedExamBatch(source_id="SRC-EVAL")
    expected = [ExpectedItem("general_lab", "HB"), ExpectedItem("general_lab", "HT")]
    result = evaluate_extraction("SYN-1", expected, report, batch)
    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.true_hallucination_rate == 0.0
    assert result.ambiguity_rate == 0.0
    assert result.missed_items == 0
    assert result.false_positive_items == 0


def test_ungrounded_item_counts_toward_true_hallucination_rate_not_correctness():
    report = GroundingReport(records=[
        GroundingRecord("general_lab", "HB", GroundingStatus.GROUNDED, 0, 7),
        GroundingRecord("general_lab", "GLICOSE", GroundingStatus.UNGROUNDED, None, None),
    ])
    batch = NormalizedExamBatch(source_id="SRC-EVAL")
    expected = [ExpectedItem("general_lab", "HB")]
    result = evaluate_extraction("SYN-2", expected, report, batch)
    assert result.extracted_items == 2
    assert result.correct_items == 1
    assert result.true_hallucination_rate == 0.5  # 1 ungrounded / 2 extracted
    assert result.ambiguity_rate == 0.0
    assert result.false_positive_items == 0  # ungrounded is not a "grounded but wrong" false positive


def test_ambiguous_item_counts_toward_ambiguity_rate_never_hallucination():
    # Milestone 2.0B.2, item 5: AMBIGUOUS is a localization problem (the
    # evidence text is real, just not attributable to one item), never
    # conflated with a true hallucination (text that never existed at all).
    report = GroundingReport(records=[
        GroundingRecord("general_lab", "HB", GroundingStatus.GROUNDED, 0, 7),
        GroundingRecord("general_lab", "NA", GroundingStatus.AMBIGUOUS, None, None),
        GroundingRecord("general_lab", "K", GroundingStatus.AMBIGUOUS, None, None),
    ])
    batch = NormalizedExamBatch(source_id="SRC-EVAL")
    expected = [ExpectedItem("general_lab", "HB")]
    result = evaluate_extraction("SYN-2B", expected, report, batch)
    assert result.extracted_items == 3
    assert result.ambiguous_items == 2
    assert result.true_hallucination_rate == 0.0  # 0 ungrounded / 3 extracted -- AMBIGUOUS never counted here
    assert result.ambiguity_rate == pytest.approx(2 / 3)


def test_missing_expected_item_is_a_miss_not_a_crash():
    report = GroundingReport(records=[GroundingRecord("general_lab", "HB", GroundingStatus.GROUNDED, 0, 7)])
    batch = NormalizedExamBatch(source_id="SRC-EVAL")
    expected = [ExpectedItem("general_lab", "HB"), ExpectedItem("general_lab", "NEVER-EXTRACTED")]
    result = evaluate_extraction("SYN-3", expected, report, batch)
    assert result.missed_items == 1
    assert result.recall == 0.5


def test_extra_grounded_item_not_in_expected_is_a_false_positive():
    report = GroundingReport(records=[
        GroundingRecord("general_lab", "HB", GroundingStatus.GROUNDED, 0, 7),
        GroundingRecord("general_lab", "SURPRISE_ANALYTE", GroundingStatus.GROUNDED, 8, 25),
    ])
    batch = NormalizedExamBatch(source_id="SRC-EVAL")
    expected = [ExpectedItem("general_lab", "HB")]
    result = evaluate_extraction("SYN-4", expected, report, batch)
    assert result.false_positive_items == 1
    assert result.precision == 0.5  # 1 correct / 2 extracted


# --- optional expected items (Milestone 2.0B.2, item 4) -------------------

def test_optional_item_present_is_credited_never_a_false_positive():
    report = GroundingReport(records=[
        GroundingRecord("diagnostic_study", "COLONOSCOPIA", GroundingStatus.GROUNDED, 0, 20),
        GroundingRecord("diagnostic_study_finding", "COLONOSCOPIA", GroundingStatus.GROUNDED, 21, 31),
    ])
    batch = NormalizedExamBatch(source_id="SRC-EVAL")
    expected = [
        ExpectedItem("diagnostic_study", "COLONOSCOPIA"),
        ExpectedItem("diagnostic_study_finding", "COLONOSCOPIA", optional=True),
    ]
    result = evaluate_extraction("SYN-5", expected, report, batch)
    assert result.precision == 1.0  # both grounded records credited, neither a false positive
    assert result.recall == 1.0  # the one required item was found
    assert result.optional_matched_items == 1
    assert result.missed_items == 0


def test_optional_item_absent_never_counts_as_missed_or_hurts_recall():
    report = GroundingReport(records=[
        GroundingRecord("diagnostic_study", "COLONOSCOPIA", GroundingStatus.GROUNDED, 0, 20),
    ])
    batch = NormalizedExamBatch(source_id="SRC-EVAL")
    expected = [
        ExpectedItem("diagnostic_study", "COLONOSCOPIA"),
        ExpectedItem("diagnostic_study_finding", "COLONOSCOPIA", optional=True),
    ]
    result = evaluate_extraction("SYN-6", expected, report, batch)
    assert result.recall == 1.0  # denominator excludes the optional item entirely
    assert result.precision == 1.0
    assert result.missed_items == 0
    assert result.optional_matched_items == 0
    assert result.expected_items == 1  # only the required item is counted


# --- the required snippet corpus, run through the full offline pipeline -

@pytest.mark.parametrize("source_id", list(SNIPPETS.keys()))
def test_every_required_snippet_extracts_and_grounds_cleanly(source_id, recorded_extractor):
    result = run_extraction(_envelope(source_id), recorded_extractor, provider="FAKE", model="fake-v0")
    assert result.metadata.status == ExecutionStatus.SUCCESS
    evaluation = evaluate_extraction(source_id, EXPECTED_ITEMS[source_id], result.grounding_report, result.batch)
    assert isinstance(evaluation, EvaluationResult)
    assert evaluation.precision == 1.0
    assert evaluation.recall == 1.0
    assert evaluation.true_hallucination_rate == 0.0
    assert evaluation.ambiguity_rate == 0.0


def test_unknown_analyte_snippet_is_unresolved_not_a_silent_pass(recorded_extractor):
    result = run_extraction(_envelope("SNIPPET-UNKNOWN-ANALYTE"), recorded_extractor, provider="FAKE", model="fake-v0")
    obs = result.batch.laboratory_observations[0]
    assert obs.analyte.raw_name == "CA1"
    assert obs.analyte.canonical_id is None


def test_invalid_date_snippet_preserves_31_09_as_unresolved_temporal_value():
    extractor = FakeExamExtractor(load_recorded_responses())
    result = run_extraction(_envelope("SNIPPET-INVALID-DATE"), extractor, provider="FAKE", model="fake-v0")
    study = result.batch.diagnostic_studies[0]
    assert study.ordered_at.raw == "31/09"
    assert study.ordered_at.normalized is None


def test_microbiology_snippet_keeps_four_independent_entries_last_unresolved_result():
    extractor = FakeExamExtractor(load_recorded_responses())
    result = run_extraction(_envelope("SNIPPET-MICROBIOLOGY"), extractor, provider="FAKE", model="fake-v0")
    assert len(result.batch.microbiology_serology) == 4
    last = result.batch.microbiology_serology[-1]
    assert last.result.value is None


def test_temporal_ambiguity_snippet_keeps_both_readings_visible():
    extractor = FakeExamExtractor(load_recorded_responses())
    result = run_extraction(_envelope("SNIPPET-TEMPORAL-AMBIGUITY"), extractor, provider="FAKE", model="fake-v0")
    assert {o.value.raw_value for o in result.batch.laboratory_observations} == {"140", "141"}
