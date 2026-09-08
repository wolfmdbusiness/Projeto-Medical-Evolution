"""Minimal evaluation harness (Milestone 2.0B, items 22-23; hardened in
Milestone 2.0B.2, item 5).

Compares what an extractor produced for one snippet against a small,
hand-authored list of `ExpectedItem`s, and computes the metrics item 22
asks for. This module has no network dependency and no opinion about which
extractor produced the candidate — it is exercised by both the offline
`FakeExamExtractor` tests and the live DeepSeek tests (item 25).

Definitions, reproduced here as the single source of truth so the numbers
in the final report and in test assertions never drift apart:

    precision           = correct_items / extracted_items
    recall              = correct_required_items / required_expected_items
    true_hallucination_rate = ungrounded_items / extracted_items
    ambiguity_rate       = ambiguous_items / extracted_items
    unmapped_rate       = unmapped_count / extracted_items

Milestone 2.0B.2, item 5 draws a hard line the Milestone 2.0B version of
this module blurred: `hallucination_rate` used to be
`(ungrounded_items + ambiguous_items) / extracted_items`, which counted a
grounding-*localization* problem (AMBIGUOUS: the cited text exists, more
than once, and the extractor's own evidence did not disambiguate which
occurrence it meant) the same as a genuine hallucination (UNGROUNDED: the
cited text does not exist in the source at all). Those are different
failure modes with different causes and different fixes, so they are now
two separate rates:

- `true_hallucination_rate` — UNGROUNDED only. This is "the extractor
  claimed something the source never said."
- `ambiguity_rate` — AMBIGUOUS only. This is "the extractor's own
  evidence was real but too imprecise/wide to safely attribute to one
  item" (e.g. an entire source line reused as `evidence_text` for every
  item on that line — see `docs/mod_exames_2_0b_1_live_findings.md`).

Neither rate changes what happens to the item: both UNGROUNDED and
AMBIGUOUS items are still excluded from every clinical bucket and land in
`unmapped` (`exam_extraction.grounding`, unchanged by this split) — this
module only reports on that outcome more precisely, it does not relax it
(item 6).

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

from exam_extraction.grounding import GroundingReport
from exam_extraction.models import GroundingStatus
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
    ambiguous_items: int
    correct_items: int
    optional_matched_items: int
    false_positive_items: int
    missed_items: int
    unmapped_count: int
    precision: float
    recall: float
    true_hallucination_rate: float
    ambiguity_rate: float
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
    true_hallucination_rate = ungrounded_items / extracted_items if extracted_items else 0.0
    ambiguity_rate = ambiguous_items / extracted_items if extracted_items else 0.0
    unmapped_rate = unmapped_count / extracted_items if extracted_items else 0.0

    return EvaluationResult(
        snippet_id=snippet_id,
        expected_items=len(required_expected),
        extracted_items=extracted_items,
        grounded_items=grounded_items,
        ungrounded_items=ungrounded_items,
        ambiguous_items=ambiguous_items,
        correct_items=correct,
        optional_matched_items=optional_matched,
        false_positive_items=false_positives,
        missed_items=missed,
        unmapped_count=unmapped_count,
        precision=precision,
        recall=recall,
        true_hallucination_rate=true_hallucination_rate,
        ambiguity_rate=ambiguity_rate,
        unmapped_rate=unmapped_rate,
    )
