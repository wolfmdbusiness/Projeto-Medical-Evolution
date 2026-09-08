"""MOD-EXAMES extraction contract (Milestone 2.0A).

These models describe what ANY exam extractor (a real LLM in 2.0B, a
hand-written test fixture today) hands to the normalizer. They are
deliberately independent of `models.medical_state.MedicalState`: an
extractor's output is a *candidate*, never a fact about the patient until it
has passed through deterministic normalization and validation.

    RAW EXAM TEXT
    -> ExamSourceEnvelope
    -> ExamExtractionCandidate   (this module)
    -> Pydantic validation
    -> deterministic normalization      (exam_normalization/)
    -> NormalizedExamBatch              (exam_normalization/models.py)
    -> deterministic validation
    -> apply_exam_batch()               (exam_normalization/apply.py)
    -> MedicalState

An extractor never writes to MedicalState directly.
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from models.medical_state import SourceType, StrictModel, TemporalValue


class ExamSourceEnvelope(StrictModel):
    """A single textual source of exam data (Milestone 2.0A, item 1).

    Only text is supported in this milestone — no PDF, OCR, image, or
    audio ingestion. `document_temporal_value` is optional context (e.g.
    the document's own dateline) the normalizer may use to complete a
    bare "31/08"-style date; it is never invented when absent.
    """

    source_id: str
    patient_ref: str
    source_type: SourceType
    origin_context: Optional[str] = None
    raw_text: str
    document_temporal_value: Optional[TemporalValue] = None
    metadata: dict[str, str] = Field(default_factory=dict)


class Evidence(StrictModel):
    """Provenance pointer back to the raw source text (item 3).

    `evidence_text` is sufficient for Milestone 2.0A. The extra fields are
    reserved for future OCR/vision extractors (page, line, character span,
    bounding box) and are simply left unset today — adding a real value to
    one of them later requires no change to this contract.
    """

    evidence_text: str
    page: Optional[int] = None
    line: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    bounding_box: Optional[dict[str, float]] = None


class ExtractionWarning(StrictModel):
    message: str
    item_ref: Optional[str] = None


class ObservationCandidate(StrictModel):
    """Shared shape for anything that looks like "a named value on a date":
    a general lab, a urinalysis line, a troponin, or one observation inside
    a blood gas panel.

    `canonical_hint` may be set by the extractor but is never authoritative
    (item 2) — only `exam_normalization.aliases.resolve_canonical_id`,
    working from `raw_name`, decides the canonical analyte id.
    """

    raw_name: str
    raw_value: Optional[str] = None
    raw_unit: Optional[str] = None
    raw_reference_range: Optional[str] = None
    raw_temporal: Optional[str] = None
    source_order: Optional[int] = None
    evidence: Evidence
    source_ref: str
    canonical_hint: Optional[str] = None


class GeneralLabCandidate(ObservationCandidate):
    pass


class UrinalysisCandidate(ObservationCandidate):
    pass


class TroponinCandidate(ObservationCandidate):
    pass


class BloodGasObservationCandidate(ObservationCandidate):
    pass


class BloodGasCandidate(StrictModel):
    """A blood gas panel as its own event (item 13), not a bag of loose
    observations — mirrors `models.medical_state.BloodGas`."""

    raw_specimen_type: Optional[str] = None
    raw_temporal: Optional[str] = None
    observations: list[BloodGasObservationCandidate] = Field(default_factory=list)
    source_order: Optional[int] = None
    evidence: Evidence
    source_ref: str


class MicrobiologyCandidate(StrictModel):
    """Every occurrence is independent (item 15): "ESBL", "ESBL 02", "ESBL
    03" are three separate candidates, never merged by name."""

    raw_name: str
    raw_result: Optional[str] = None
    raw_temporal: Optional[str] = None
    organism_hint: Optional[str] = None
    source_order: Optional[int] = None
    evidence: Evidence
    source_ref: str


class DiagnosticStudyFindingCandidate(StrictModel):
    raw_text: str
    evidence: Evidence


class DiagnosticStudyCandidate(StrictModel):
    """`procedure_status_hint`/`result_status_hint` are candidate hints,
    not final authority (item 17): the normalizer only accepts them when
    they match a known enum value outright, and never infers ORDERED (or
    any other status) from free narrative text such as "RECOMENDADO
    SOLICITAR"."""

    raw_name: str
    raw_temporal: Optional[str] = None
    procedure_status_hint: Optional[str] = None
    result_status_hint: Optional[str] = None
    findings: list[DiagnosticStudyFindingCandidate] = Field(default_factory=list)
    source_order: Optional[int] = None
    evidence: Evidence
    source_ref: str


class UnmappedCandidate(StrictModel):
    """Content the extractor could not place in any bucket above. Carried
    through normalization unchanged — never dropped, never guessed at."""

    raw_text: str
    evidence: Evidence
    source_ref: str
    source_order: Optional[int] = None


class ExamExtractionCandidate(StrictModel):
    source_id: str
    general_labs: list[GeneralLabCandidate] = Field(default_factory=list)
    urinalysis: list[UrinalysisCandidate] = Field(default_factory=list)
    blood_gases: list[BloodGasCandidate] = Field(default_factory=list)
    troponins: list[TroponinCandidate] = Field(default_factory=list)
    microbiology: list[MicrobiologyCandidate] = Field(default_factory=list)
    diagnostic_studies: list[DiagnosticStudyCandidate] = Field(default_factory=list)
    unmapped: list[UnmappedCandidate] = Field(default_factory=list)
    extraction_warnings: list[ExtractionWarning] = Field(default_factory=list)
