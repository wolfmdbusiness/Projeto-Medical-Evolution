"""The only path from a `NormalizedExamBatch` into `MedicalState`
(Milestone 2.0A, item 18).

An extractor's output can never reach `MedicalState` directly — it must
pass through `ExamExtractionCandidate` (Pydantic validation),
`normalize_extraction_candidate` (deterministic normalization), and land
here as an already-typed, already-idempotency-tagged `NormalizedExamBatch`.
`apply_exam_batch` only ever appends new items (skipping ones whose
idempotency marker is already present, item 19) and returns a new
`MedicalState` rather than mutating the one it was given.
"""

from __future__ import annotations

from typing import TypeVar

from exam_normalization.idempotency import MARKER_PREFIX
from exam_normalization.models import NormalizedExamBatch
from models.medical_state import MedicalState

T = TypeVar("T")


def _merge_by_idempotency_marker(existing: list[T], new_items: list[T]) -> list[T]:
    """Append `new_items` whose idempotency marker (embedded in
    `source_refs`) is not already present among `existing` — reprocessing
    the same source a second time produces zero additional duplicates."""
    seen_markers: set[str] = set()
    for item in existing:
        seen_markers.update(ref for ref in item.source_refs if ref.startswith(MARKER_PREFIX))

    merged = list(existing)
    for item in new_items:
        markers = [ref for ref in item.source_refs if ref.startswith(MARKER_PREFIX)]
        if any(marker in seen_markers for marker in markers):
            continue
        merged.append(item)
        seen_markers.update(markers)
    return merged


def apply_exam_batch(state: MedicalState, batch: NormalizedExamBatch) -> MedicalState:
    """Merge a validated, normalized exam batch into a *new* MedicalState.

    Functional by design: `state` is never mutated. Every entity keeps the
    `source_refs` (including its idempotency marker) assigned during
    normalization, so provenance survives the merge unchanged.
    """
    exams = state.complementary_exams
    new_exams = exams.model_copy(update={
        "laboratory_observations": _merge_by_idempotency_marker(
            exams.laboratory_observations, batch.laboratory_observations
        ),
        "urinalysis": _merge_by_idempotency_marker(exams.urinalysis, batch.urinalysis),
        "blood_gases": _merge_by_idempotency_marker(exams.blood_gases, batch.blood_gases),
        "troponins": _merge_by_idempotency_marker(exams.troponins, batch.troponins),
        "microbiology_serology": _merge_by_idempotency_marker(
            exams.microbiology_serology, batch.microbiology_serology
        ),
        "diagnostic_studies": _merge_by_idempotency_marker(
            exams.diagnostic_studies, batch.diagnostic_studies
        ),
        "unmapped": exams.unmapped + [item for item in batch.unmapped if item not in exams.unmapped],
    })
    return state.model_copy(update={"complementary_exams": new_exams})
