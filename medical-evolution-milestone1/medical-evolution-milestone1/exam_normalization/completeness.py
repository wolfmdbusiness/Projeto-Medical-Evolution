"""Completeness accounting (Milestone 2.0A, item 20).

Proves, deterministically and testably, that no candidate item vanishes
during normalization:

    items_extracted == items_normalized + items_unmapped + items_conflicting

Every candidate item the orchestrator processes lands in exactly one of the
three buckets on the right — never zero, never more than one. Items the
Template Profile later decides not to *display* are unaffected: they are
still counted as normalized here, and still stored in `MedicalState`
(item 21) — display policy is not extraction policy.
"""

from __future__ import annotations

from exam_extraction.models import ExamExtractionCandidate
from exam_normalization.models import NormalizedExamBatch
from models.medical_state import StrictModel


class CompletenessReport(StrictModel):
    items_extracted: int
    items_normalized: int
    items_unmapped: int
    items_conflicting: int

    @property
    def is_complete(self) -> bool:
        return self.items_extracted == (
            self.items_normalized + self.items_unmapped + self.items_conflicting
        )


def _count_candidate_items(candidate: ExamExtractionCandidate) -> int:
    blood_gas_observations = sum(len(gas.observations) for gas in candidate.blood_gases)
    return (
        len(candidate.general_labs)
        + len(candidate.urinalysis)
        + len(candidate.blood_gases)
        + blood_gas_observations
        + len(candidate.troponins)
        + len(candidate.microbiology)
        + len(candidate.diagnostic_studies)
        + len(candidate.unmapped)
    )


def _count_normalized_items(batch: NormalizedExamBatch) -> int:
    blood_gas_observations = sum(len(gas.observations) for gas in batch.blood_gases)
    return (
        len(batch.laboratory_observations)
        + len(batch.urinalysis)
        + len(batch.blood_gases)
        + blood_gas_observations
        + len(batch.troponins)
        + len(batch.microbiology_serology)
        + len(batch.diagnostic_studies)
    )


def compute_completeness(candidate: ExamExtractionCandidate, batch: NormalizedExamBatch) -> CompletenessReport:
    return CompletenessReport(
        items_extracted=_count_candidate_items(candidate),
        items_normalized=_count_normalized_items(batch),
        items_unmapped=len(batch.unmapped),
        items_conflicting=len(batch.conflicts),
    )
