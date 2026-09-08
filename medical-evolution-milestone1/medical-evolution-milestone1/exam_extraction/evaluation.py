"""Minimal evaluation harness (Milestone 2.0B, items 22-23).

Compares what an extractor produced for one snippet against a small,
hand-authored list of `ExpectedItem`s, and computes the metrics item 22
asks for. This module has no network dependency and no opinion about which
extractor produced the candidate — it is exercised by both the offline
`FakeExamExtractor` tests and the live DeepSeek tests (item 25).

Definitions (item 23), reproduced here as the single source of truth so
the numbers in the final report and in test assertions never drift apart:

    precision           = correct_items / extracted_items
    recall              = correct_items / expected_items
    hallucination_rate  = (ungrounded_items + ambiguous_items) / extracted_items
    unmapped_rate       = unmapped_count / extracted_items

`extracted_items` counts every groundable clinical claim the extractor
made — one entry per `GroundingReport` record. This deliberately differs
from `exam_normalization.completeness.count_candidate_items` (which counts
top-level candidate objects, e.g. one per diagnostic study, not per nested
finding): that function serves the pipeline's completeness accounting,
while this harness needs a denominator that matches what it evaluates
grounding *record by record*, findings and nested observations included,
so precision never exceeds 1.0. An `ExpectedItem` is matched against
`GroundingReport` records by `(category, label)` (case-insensitive on
`label`); `expect_unresolved=True` additionally requires that the matching
item never resolved to a canonical id in the normalized batch (used for
the adversarial "unknown analyte" case).
"""

from __future__ import annotations

from dataclasses import dataclass

from exam_extraction.grounding import GroundingReport
from exam_extraction.models import GroundingStatus
from exam_normalization.models import NormalizedExamBatch
from models.medical_state import ValidationStatus


@dataclass(frozen=True)
class ExpectedItem:
    category: str
    label: str
    expect_unresolved: bool = False


@dataclass(frozen=True)
class EvaluationResult:
    snippet_id: str
    expected_items: int
    extracted_items: int
    grounded_items: int
    ungrounded_items: int
    ambiguous_items: int
    correct_items: int
    false_positive_items: int
    missed_items: int
    unmapped_count: int
    precision: float
    recall: float
    hallucination_rate: float
    unmapped_rate: float


def _norm(label: str) -> str:
    return label.strip().upper()


def _batch_is_unresolved(batch: NormalizedExamBatch, label: str) -> bool:
    """True if a normalized lab observation matching `label` (by raw_name)
    exists and ended up UNRESOLVED (unknown canonical id) -- used only for
    `ExpectedItem(expect_unresolved=True)`."""
    target = _norm(label)
    for bucket in (batch.laboratory_observations, batch.urinalysis, batch.troponins):
        for obs in bucket:
            if _norm(obs.analyte.raw_name) == target:
                return obs.validation_status == ValidationStatus.UNRESOLVED
    return False


def evaluate_extraction(
    snippet_id: str,
    expected: list[ExpectedItem],
    grounding_report: GroundingReport,
    batch: NormalizedExamBatch,
) -> EvaluationResult:
    extracted_items = len(grounding_report.records)
    grounded_items = grounding_report.grounded_count
    ungrounded_items = grounding_report.ungrounded_count
    ambiguous_items = grounding_report.ambiguous_count

    grounded_records = [(r.category, _norm(r.label)) for r in grounding_report.records if r.status == GroundingStatus.GROUNDED]

    correct = 0
    missed = 0
    matched_records: set[tuple[str, str]] = set()
    for item in expected:
        key = (item.category, _norm(item.label))
        found = key in grounded_records
        if found and item.expect_unresolved:
            found = _batch_is_unresolved(batch, item.label)
        if found:
            correct += 1
            matched_records.add(key)
        else:
            missed += 1

    false_positives = sum(1 for key in grounded_records if key not in matched_records)

    unmapped_count = len(batch.unmapped)

    precision = correct / extracted_items if extracted_items else 0.0
    recall = correct / len(expected) if expected else 0.0
    hallucination_rate = (
        (ungrounded_items + ambiguous_items) / extracted_items if extracted_items else 0.0
    )
    unmapped_rate = unmapped_count / extracted_items if extracted_items else 0.0

    return EvaluationResult(
        snippet_id=snippet_id,
        expected_items=len(expected),
        extracted_items=extracted_items,
        grounded_items=grounded_items,
        ungrounded_items=ungrounded_items,
        ambiguous_items=ambiguous_items,
        correct_items=correct,
        false_positive_items=false_positives,
        missed_items=missed,
        unmapped_count=unmapped_count,
        precision=precision,
        recall=recall,
        hallucination_rate=hallucination_rate,
        unmapped_rate=unmapped_rate,
    )
