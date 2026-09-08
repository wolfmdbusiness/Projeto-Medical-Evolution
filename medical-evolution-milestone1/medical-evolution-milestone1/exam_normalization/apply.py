"""The only path from a `NormalizedExamBatch` into `MedicalState`
(Milestone 2.0A, item 18; hardened in Milestone 2.0A.1, item 1).

An extractor's output can never reach `MedicalState` directly — it must
pass through `ExamExtractionCandidate` (Pydantic validation),
`normalize_extraction_candidate` (deterministic normalization), and land
here as an already-typed, already-idempotency-tagged `NormalizedExamBatch`.
`apply_exam_batch` only ever appends new items (skipping ones whose
`processing_key` is already recorded in `state.provenance.processing_metadata`,
item 19) and returns a new `MedicalState` rather than mutating the one it
was given.

Idempotency is checked by `processing_key` (module + module_version +
source_id + category + item_key), never by content (name, date, or result):
two genuinely distinct occurrences that happen to share the same name and
date are still preserved individually, because they were normalized from
different `source_order` positions and so carry different keys.
"""

from __future__ import annotations

from typing import TypeVar

from exam_normalization.idempotency import MOD_EXAMES_MODULE, MOD_EXAMES_MODULE_VERSION
from exam_normalization.models import NormalizedExamBatch
from models.medical_state import MedicalState, ProcessingMetadataEntry

T = TypeVar("T")


def _merge_by_processing_key(
    existing: list[T],
    new_items: list[T],
    seen_keys: set[str],
) -> tuple[list[T], list[str]]:
    """Append `new_items` whose `processing_key` is not already in
    `seen_keys` — reprocessing the same source a second time produces zero
    additional duplicates. Returns the merged list and the processing_keys
    of the items actually appended (so the caller can record them)."""
    merged = list(existing)
    appended_keys: list[str] = []
    for item in new_items:
        key = item.processing_key
        if key is not None and key in seen_keys:
            continue
        merged.append(item)
        if key is not None:
            seen_keys.add(key)
            appended_keys.append(key)
    return merged, appended_keys


def apply_exam_batch(state: MedicalState, batch: NormalizedExamBatch) -> MedicalState:
    """Merge a validated, normalized exam batch into a *new* MedicalState.

    Functional by design: `state` is never mutated. Every entity keeps its
    own `processing_key`; `state.provenance.processing_metadata` is the
    durable record of which keys have already been applied, so
    idempotency survives across separate `apply_exam_batch` calls without
    a database and without polluting `source_refs`.
    """
    seen_keys: set[str] = {
        entry.processing_key for entry in state.provenance.processing_metadata
    }

    exams = state.complementary_exams
    all_appended_keys: list[str] = []

    laboratory_observations, appended = _merge_by_processing_key(
        exams.laboratory_observations, batch.laboratory_observations, seen_keys
    )
    all_appended_keys += appended

    urinalysis, appended = _merge_by_processing_key(exams.urinalysis, batch.urinalysis, seen_keys)
    all_appended_keys += appended

    blood_gases, appended = _merge_by_processing_key(exams.blood_gases, batch.blood_gases, seen_keys)
    all_appended_keys += appended

    troponins, appended = _merge_by_processing_key(exams.troponins, batch.troponins, seen_keys)
    all_appended_keys += appended

    microbiology_serology, appended = _merge_by_processing_key(
        exams.microbiology_serology, batch.microbiology_serology, seen_keys
    )
    all_appended_keys += appended

    diagnostic_studies, appended = _merge_by_processing_key(
        exams.diagnostic_studies, batch.diagnostic_studies, seen_keys
    )
    all_appended_keys += appended

    new_exams = exams.model_copy(update={
        "laboratory_observations": laboratory_observations,
        "urinalysis": urinalysis,
        "blood_gases": blood_gases,
        "troponins": troponins,
        "microbiology_serology": microbiology_serology,
        "diagnostic_studies": diagnostic_studies,
        "unmapped": exams.unmapped + [item for item in batch.unmapped if item not in exams.unmapped],
    })

    new_processing_metadata = state.provenance.processing_metadata + [
        ProcessingMetadataEntry(
            processing_key=key, source_id=batch.source_id,
            module=MOD_EXAMES_MODULE, module_version=MOD_EXAMES_MODULE_VERSION,
        )
        for key in all_appended_keys
    ]
    new_provenance = state.provenance.model_copy(update={"processing_metadata": new_processing_metadata})

    return state.model_copy(update={"complementary_exams": new_exams, "provenance": new_provenance})
