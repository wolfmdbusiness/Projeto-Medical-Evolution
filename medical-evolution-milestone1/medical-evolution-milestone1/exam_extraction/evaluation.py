"""Minimal evaluation harness (Milestone 2.0B, items 22-23; hardened in
Milestone 2.0B.2, item 5; hardened again in Milestone 2.0C.1, item 9).

Compares what an extractor produced for one snippet against a small,
hand-authored list of `ExpectedItem`s, and computes the metrics item 22
asks for. This module has no network dependency and no opinion about which
extractor produced the candidate — it is exercised by both the offline
`FakeExamExtractor` tests and the live DeepSeek tests (item 25).

Definitions, reproduced here as the single source of truth so the numbers
in the final report and in test assertions never drift apart:

    precision              = correct_items / extracted_items
    recall                 = correct_required_items / required_expected_items
    ungrounded_rate         = ungrounded_items / extracted_items
    localization_unresolved_rate = localization_unresolved_items / extracted_items
    localization_multiple_rate   = localization_multiple_items / extracted_items
    unmapped_rate           = unmapped_count / extracted_items

Milestone 2.0C.1, item 9 draws a second hard line on top of the one
Milestone 2.0B.2 already drew: `ungrounded_rate` is a purely mechanical
property of `exam_extraction.grounding`'s output (`support_status=
UNGROUNDED` — the cited text does not exist in the source at all) and is
NEVER, on its own, evidence of a *semantic* hallucination (extracted
clinical content whose *meaning* is not actually supported by the source,
even though some matching text might exist). Determining semantic
hallucination requires clinical-content adjudication this deterministic
pipeline cannot perform on its own — so `semantic_hallucination_status`
defaults to `"NOT_ADJUDICATED"` and `semantic_hallucination_rate` stays
`None` unless a caller explicitly supplies adjudicated counts (e.g. a
human reviewer's findings) via `evaluate_extraction`'s
`adjudicated_semantic_hallucinations` parameter. This module never
presumes a value it has no basis for.

`localization_unresolved_rate` replaces Milestone 2.0B.2's
`ambiguity_rate`: it is exactly the items that stay blocked from
`MedicalState` because `exam_extraction.grounding` could not attribute
them to one occurrence (`LocalizationStatus.UNRESOLVED`).
`localization_multiple_rate` is new and purely informational — items that
*were* accepted despite having more than one legitimate supporting span
(item 6, Milestone 2.0C.1) — never a failure signal on its own.

`extracted_items` counts every groundable clinical claim the extractor
made — one entry per `GroundingReport` record. This deliberately differs
from `exam_normalization.completeness.count_candidate_items` (which counts
top-level candidate objects, e.g. one per diagnostic study, not per nested
finding): that function serves the pipeline's completeness accounting,
while this harness needs a denominator that matches what it evaluates
grounding *record by record*, findings and nested observations included,
so precision never exceeds 1.0.

An `ExpectedItem` is matched against `GroundingReport` records by
`(category, label)` (case-insensitive on `label`); `expect_unresolved=True`
additionally requires that the matching item never resolved to a canonical
id in the normalized batch (used for the adversarial "unknown analyte"
case). `optional=True` (item 4, Milestone 2.0B.2) marks an item that is
*creditable if extracted* (it still counts toward `correct_items`/
precision when found, and its grounded record is never treated as a false
positive) but *never required* (its absence never counts against
`missed_items`/recall) — used for content whose presence is a defensible
but non-obligatory extraction choice, e.g. "SOLICITADO" as a
`diagnostic_study_finding` in SNIPPET-INVALID-DATE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from exam_extraction.grounding import GroundingReport
from exam_extraction.models import SupportStatus
from exam_normalization.models import NormalizedExamBatch
from models.medical_state import ValidationStatus


@dataclass(frozen=True)
class ExpectedItem:
    category: str
    label: str
    expect_unresolved: bool = False
    optional: bool = False


@dataclass(frozen=True)
class EvaluationResult:
    snippet_id: str
    expected_items: int  # required (non-optional) expected items only
    extracted_items: int
    grounded_items: int
    ungrounded_items: int
    accepted_items: int
    localization_multiple_items: int
    localization_unresolved_items: int
    correct_items: int
    optional_matched_items: int
    false_positive_items: int
    missed_items: int
    unmapped_count: int
    precision: float
    recall: float
    ungrounded_rate: float
    localization_multiple_rate: float
    localization_unresolved_rate: float
    unmapped_rate: float
    semantic_hallucination_status: str
    semantic_hallucination_rate: Optional[float]


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
    *,
    adjudicated_semantic_hallucinations: Optional[int] = None,
) -> EvaluationResult:
    extracted_items = len(grounding_report.records)
    grounded_items = grounding_report.grounded_count
    ungrounded_items = grounding_report.ungrounded_count
    accepted_items = grounding_report.accepted_count
    localization_multiple_items = grounding_report.localization_multiple_count
    localization_unresolved_items = grounding_report.localization_unresolved_count

    grounded_records = [
        (r.category, _norm(r.label)) for r in grounding_report.records if r.support_status == SupportStatus.GROUNDED
    ]

    required_expected = [item for item in expected if not item.optional]

    correct_required = 0
    optional_matched = 0
    missed = 0
    matched_records: set[tuple[str, str]] = set()
    for item in expected:
        key = (item.category, _norm(item.label))
        found = key in grounded_records
        if found and item.expect_unresolved:
            found = _batch_is_unresolved(batch, item.label)
        if found:
            matched_records.add(key)
            if item.optional:
                optional_matched += 1
            else:
                correct_required += 1
        elif not item.optional:
            missed += 1

    correct = correct_required + optional_matched
    false_positives = sum(1 for key in grounded_records if key not in matched_records)

    unmapped_count = len(batch.unmapped)

    precision = correct / extracted_items if extracted_items else 0.0
    recall = correct_required / len(required_expected) if required_expected else 0.0
    ungrounded_rate = ungrounded_items / extracted_items if extracted_items else 0.0
    localization_multiple_rate = localization_multiple_items / extracted_items if extracted_items else 0.0
    localization_unresolved_rate = localization_unresolved_items / extracted_items if extracted_items else 0.0
    unmapped_rate = unmapped_count / extracted_items if extracted_items else 0.0

    if adjudicated_semantic_hallucinations is None:
        semantic_hallucination_status = "NOT_ADJUDICATED"
        semantic_hallucination_rate = None
    else:
        semantic_hallucination_status = "ADJUDICATED"
        semantic_hallucination_rate = (
            adjudicated_semantic_hallucinations / extracted_items if extracted_items else 0.0
        )

    return EvaluationResult(
        snippet_id=snippet_id,
        expected_items=len(required_expected),
        extracted_items=extracted_items,
        grounded_items=grounded_items,
        ungrounded_items=ungrounded_items,
        accepted_items=accepted_items,
        localization_multiple_items=localization_multiple_items,
        localization_unresolved_items=localization_unresolved_items,
        correct_items=correct,
        optional_matched_items=optional_matched,
        false_positive_items=false_positives,
        missed_items=missed,
        unmapped_count=unmapped_count,
        precision=precision,
        recall=recall,
        ungrounded_rate=ungrounded_rate,
        localization_multiple_rate=localization_multiple_rate,
        localization_unresolved_rate=localization_unresolved_rate,
        unmapped_rate=unmapped_rate,
        semantic_hallucination_status=semantic_hallucination_status,
        semantic_hallucination_rate=semantic_hallucination_rate,
    )
