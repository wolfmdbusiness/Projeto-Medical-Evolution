"""Output contract of the exam normalizer (Milestone 2.0A, item 4).

`NormalizedExamBatch` is its own model — not `MedicalState` and not the
extraction candidate — so the normalizer has one explicit output shape and
`apply_exam_batch` has one explicit input shape. Its list fields reuse the
already-decoupled entity models from `models.medical_state`
(`LabObservation`, `BloodGas`, `MicrobiologySerology`, `DiagnosticStudy`):
those already represent "a normalized lab observation" independently of the
rest of the patient record, so duplicating them here would just be a
second copy of the same contract to keep in sync.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import Field

from models.medical_state import (
    BloodGas,
    DiagnosticStudy,
    LabObservation,
    MicrobiologySerology,
    StrictModel,
)


class NormalizationIssue(StrictModel):
    """One entry in `conflicts[]` or `warnings[]`. Free-form enough to cover
    the different reasons an item can fail to normalize cleanly, but always
    traceable back to its source."""

    category: str
    message: str
    source_ref: Optional[str] = None
    raw_snapshot: Optional[str] = None


class NormalizedExamBatch(StrictModel):
    source_id: str
    laboratory_observations: list[LabObservation] = Field(default_factory=list)
    urinalysis: list[LabObservation] = Field(default_factory=list)
    blood_gases: list[BloodGas] = Field(default_factory=list)
    troponins: list[LabObservation] = Field(default_factory=list)
    microbiology_serology: list[MicrobiologySerology] = Field(default_factory=list)
    diagnostic_studies: list[DiagnosticStudy] = Field(default_factory=list)
    unmapped: list[Any] = Field(default_factory=list)
    conflicts: list[NormalizationIssue] = Field(default_factory=list)
    warnings: list[NormalizationIssue] = Field(default_factory=list)
