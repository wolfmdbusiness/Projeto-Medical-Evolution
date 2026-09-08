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

from enum import Enum
from typing import Optional

from pydantic import Field

from models.medical_state import SourceType, StrictModel, TemporalValue


class SupportStatus(str, Enum):
    """Does `evidence_text` exist, literally, anywhere in the source
    (Milestone 2.0C.1, item 3)? This is deliberately independent of
    *where* it exists or how many times: a value restated twice in one
    document (e.g. a radiology report's body and its own conclusion) is
    just as much "supported" as a value stated once. Conflating "the text
    exists" with "the text's location is unambiguous" was Milestone
    2.0B's `AMBIGUOUS` status — mislabeling a pure localization problem
    as if it were a hallucination-adjacent failure. `LocalizationStatus`
    now carries that second, genuinely distinct question.

    - GROUNDED: `evidence_text` matches one or more locations in
      `ExamSourceEnvelope.raw_text`.
    - UNGROUNDED: `evidence_text` was not found in `raw_text` at all —
      this is the only status that means "no textual support exists."
    """

    GROUNDED = "GROUNDED"
    UNGROUNDED = "UNGROUNDED"


class LocalizationStatus(str, Enum):
    """Given `support_status=GROUNDED`, can this item's supporting span(s)
    be pinned down deterministically (Milestone 2.0C.1, item 3)?

    - UNIQUE: exactly one matching span applies to this item (either the
      text occurs once in its search scope, or multiple items/occurrences
      were cleanly paired one-to-one).
    - MULTIPLE: the text has more than one matching span, all of which
      legitimately support this one item (e.g. the same finding restated
      in a report's body and its conclusion) — item 4/6: every matching
      span is preserved, none is silently discarded, and the item's
      occurrence identity is derived from the full, ordered set of spans.
    - UNRESOLVED: more than one item competes for a set of occurrences
      that cannot be cleanly paired (count mismatch, or no ordering
      signal to pair them) — clinical identity genuinely cannot be
      determined, so (item 7) this stays blocked from `MedicalState`
      exactly like before, even though `support_status` is GROUNDED.
    """

    UNIQUE = "UNIQUE"
    MULTIPLE = "MULTIPLE"
    UNRESOLVED = "UNRESOLVED"


class CharSpan(StrictModel):
    """One literal character span in `ExamSourceEnvelope.raw_text`
    (post line-ending normalization). Always computed by
    `exam_extraction.grounding`, never supplied by an extractor."""

    start: int
    end: int


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
    """Provenance pointer back to the raw source text (item 3; extended in
    Milestone 2.0B, item 12, for deterministic evidence grounding).

    `evidence_text` is sufficient for Milestone 2.0A. `page`, `line`, and
    `bounding_box` are reserved for future OCR/vision extractors and are
    simply left unset today — adding a real value to one of them later
    requires no change to this contract.

    `char_start`/`char_end`, `matching_spans`, `support_status`, and
    `localization_status` are populated by
    `exam_extraction.grounding.ground_candidate`, never by an extractor:
    the LLM is never the authority on its own offsets (item 11) or on
    whether its own claim is grounded (item 9).

    `char_start`/`char_end` is the first (or only) span in
    `matching_spans`, kept as a simple, always-present shortcut for the
    common `LocalizationStatus.UNIQUE` case; `matching_spans` is the
    complete, authoritative list -- every legitimate supporting
    occurrence, in document order, never silently narrowed to one
    (Milestone 2.0C.1, item 4).
    """

    evidence_text: str
    page: Optional[int] = None
    line: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    matching_spans: list[CharSpan] = Field(default_factory=list)
    bounding_box: Optional[dict[str, float]] = None
    support_status: Optional[SupportStatus] = None
    localization_status: Optional[LocalizationStatus] = None


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
