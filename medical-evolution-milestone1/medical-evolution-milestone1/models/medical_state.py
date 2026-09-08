from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


Scalar = Union[str, int, float, bool]


class StrictModel(BaseModel):
    """Base model for the whole Medical State schema.

    Milestone 1.1: unknown/mistyped fields must fail validation instead of
    being silently dropped, since "DADOS ESTRUTURADOS CORRETOS" is the first
    gate of the whole pipeline.
    """

    model_config = ConfigDict(extra="forbid")


class ClinicalState(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    NEGATED = "NEGATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class ValidationStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    NORMALIZED = "NORMALIZED"
    ADJUDICATED = "ADJUDICATED"
    MISSING = "MISSING"
    UNREADABLE = "UNREADABLE"
    UNRESOLVED = "UNRESOLVED"
    CONFLICT = "CONFLICT"


class GlobalStatus(str, Enum):
    PROCESSING = "PROCESSING"
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"


class DiagnosisStatus(str, Enum):
    ACTIVE = "ACTIVE"
    UNCERTAIN = "UNCERTAIN"
    RESOLVED = "RESOLVED"
    RULED_OUT = "RULED_OUT"


class MedicationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DISCONTINUED = "DISCONTINUED"


class ClinicalEventStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"


class ClinicalEventSeverity(str, Enum):
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    UNKNOWN = "UNKNOWN"


class ConsultationStatus(str, Enum):
    REQUESTED = "REQUESTED"
    PENDING = "PENDING"
    ANSWERED = "ANSWERED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class ConsultationSectionState(str, Enum):
    """Distinguishes "no consultation data captured" from an explicit
    clinical statement that none was requested (Milestone 1.2, item 6)."""

    PRESENT = "PRESENT"
    NOT_REQUESTED = "NOT_REQUESTED"
    UNKNOWN = "UNKNOWN"


class PendingItemType(str, Enum):
    EXAM = "EXAM"
    CONSULTATION = "CONSULTATION"
    PROCEDURE = "PROCEDURE"
    OTHER = "OTHER"


class PendingStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CareActionType(str, Enum):
    MEDICATION = "MEDICATION"
    PROCEDURE = "PROCEDURE"
    MONITORING = "MONITORING"
    OTHER = "OTHER"


class CareActionStatus(str, Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DiagnosticStudyProcedureStatus(str, Enum):
    ORDERED = "ORDERED"
    SCHEDULED = "SCHEDULED"
    PERFORMED = "PERFORMED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class DiagnosticStudyResultStatus(str, Enum):
    NOT_AVAILABLE = "NOT_AVAILABLE"
    PENDING = "PENDING"
    PRELIMINARY = "PRELIMINARY"
    FINAL = "FINAL"
    UNKNOWN = "UNKNOWN"


class SourceType(str, Enum):
    MEDICAL_EVOLUTION = "MEDICAL_EVOLUTION"
    EXTERNAL_LAB_REPORT = "EXTERNAL_LAB_REPORT"
    EXTERNAL_MEDICAL_DOCUMENT = "EXTERNAL_MEDICAL_DOCUMENT"
    OTHER = "OTHER"


class SourceModality(str, Enum):
    TEXT = "TEXT"
    OTHER = "OTHER"


class TemporalPrecision(str, Enum):
    DATE = "DATE"
    DATE_TIME = "DATE_TIME"
    PARTIAL_DATE = "PARTIAL_DATE"
    UNKNOWN = "UNKNOWN"


class TemporalPeriod(str, Enum):
    DAY = "DAY"
    NIGHT = "NIGHT"
    UNSPECIFIED = "UNSPECIFIED"


class ComparisonOperator(str, Enum):
    LT = "<"
    GT = ">"
    LTE = "<="
    GTE = ">="
    EQ = "="


class GasSpecimenType(str, Enum):
    ARTERIAL = "ARTERIAL"
    VENOUS = "VENOUS"
    CAPILLARY = "CAPILLARY"
    UNKNOWN = "UNKNOWN"


class IcuRequirementStatus(str, Enum):
    REQUIRED = "REQUIRED"
    NO_LONGER_REQUIRED = "NO_LONGER_REQUIRED"
    UNKNOWN = "UNKNOWN"


class TemporalValue(StrictModel):
    """Reusable, typed clinical date/time (Milestone 1.2, item 2).

    `raw` is always preserved verbatim. `normalized` is only ever an ISO-8601
    string derived from `raw` when that derivation is unambiguous; an
    impossible or partial date (e.g. "31/09", "31.08") keeps `normalized`
    unset rather than being silently corrected (item 3) — validation_status
    reflects that (e.g. UNRESOLVED/CONFLICT), which the renderability gate
    already treats as "needs review" wherever a TemporalValue is consumed.
    """

    raw: Optional[str] = None
    normalized: Optional[str] = None
    precision: TemporalPrecision = TemporalPrecision.UNKNOWN
    period: TemporalPeriod = TemporalPeriod.UNSPECIFIED
    validation_status: ValidationStatus = ValidationStatus.MISSING


class ClinicalField(StrictModel):
    value: Optional[Scalar] = None
    clinical_state: ClinicalState = ClinicalState.UNKNOWN
    validation_status: ValidationStatus = ValidationStatus.MISSING
    source_refs: list[str] = Field(default_factory=list)


class Meta(StrictModel):
    state_id: str
    state_revision: int = 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    language: str = "pt-BR"
    template_profile_id: Optional[str] = "UTI_HOSPITALIS_V1"


class Admission(StrictModel):
    hospital_admission_date: TemporalValue = Field(default_factory=TemporalValue)
    icu_admission_date: TemporalValue = Field(default_factory=TemporalValue)
    origin: ClinicalField = Field(default_factory=ClinicalField)


class Diagnosis(StrictModel):
    diagnosis_id: str
    main: ClinicalField
    specifications: list[ClinicalField] = Field(default_factory=list)
    status: DiagnosisStatus = DiagnosisStatus.ACTIVE
    source_refs: list[str] = Field(default_factory=list)


class Hpma(StrictModel):
    text: ClinicalField = Field(default_factory=ClinicalField)
    source_type: Optional[str] = None
    source_datetime: Optional[str] = None
    source_refs: list[str] = Field(default_factory=list)


class EvolutionHistoryEntry(StrictModel):
    evolution_id: str
    temporal_value: TemporalValue = Field(default_factory=TemporalValue)
    text: ClinicalField
    author_type: str = "HUMAN"
    source_refs: list[str] = Field(default_factory=list)


class ClinicalEvent(StrictModel):
    event_id: str
    datetime: Optional[str] = None
    event_type: str
    description: ClinicalField
    severity: Optional[ClinicalEventSeverity] = ClinicalEventSeverity.UNKNOWN
    status: ClinicalEventStatus = ClinicalEventStatus.ACTIVE
    related_entities: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class PhysicalExam(StrictModel):
    general: ClinicalField = Field(default_factory=ClinicalField)
    neurologic: ClinicalField = Field(default_factory=ClinicalField)
    cardiovascular: ClinicalField = Field(default_factory=ClinicalField)
    respiratory: ClinicalField = Field(default_factory=ClinicalField)
    abdominal: ClinicalField = Field(default_factory=ClinicalField)
    extremities: ClinicalField = Field(default_factory=ClinicalField)


class History(StrictModel):
    allergies: ClinicalField = Field(default_factory=ClinicalField)
    past_medical_history: ClinicalField = Field(default_factory=ClinicalField)
    previous_surgeries: ClinicalField = Field(default_factory=ClinicalField)
    chronic_medications: ClinicalField = Field(default_factory=ClinicalField)
    habits: ClinicalField = Field(default_factory=ClinicalField)
    family_history: ClinicalField = Field(default_factory=ClinicalField)


class Medication(StrictModel):
    medication_id: str
    raw_name: Optional[str] = None
    generic_name: Optional[str] = None
    presentation: Optional[str] = None
    dosage: Optional[str] = None
    route: Optional[str] = None
    source_order: Optional[int] = None
    classifications: list[str] = Field(default_factory=list)
    status: MedicationStatus = MedicationStatus.ACTIVE
    # Course tracking (Milestone 1.2, item 22) — raw/documented values only.
    # Dn is whatever the source documented ("D1"), never computed here.
    started_at: Optional[TemporalValue] = None
    documented_therapy_day: Optional[str] = None
    validation_status: ValidationStatus = ValidationStatus.CONFIRMED
    source_refs: list[str] = Field(default_factory=list)


class Therapies(StrictModel):
    hemotransfusion: ClinicalField = Field(default_factory=ClinicalField)
    niv: ClinicalField = Field(default_factory=ClinicalField)
    invasive_mechanical_ventilation: ClinicalField = Field(default_factory=ClinicalField)
    renal_replacement_therapy: ClinicalField = Field(default_factory=ClinicalField)


class Controls(StrictModel):
    heart_rate: ClinicalField = Field(default_factory=ClinicalField)
    respiratory_rate: ClinicalField = Field(default_factory=ClinicalField)
    systolic_bp: ClinicalField = Field(default_factory=ClinicalField)
    diastolic_bp: ClinicalField = Field(default_factory=ClinicalField)
    mean_arterial_pressure: ClinicalField = Field(default_factory=ClinicalField)
    spo2: ClinicalField = Field(default_factory=ClinicalField)
    temperature: ClinicalField = Field(default_factory=ClinicalField)
    glucose: ClinicalField = Field(default_factory=ClinicalField)
    fluid_balance_total: ClinicalField = Field(default_factory=ClinicalField)
    fluid_balance_24h: ClinicalField = Field(default_factory=ClinicalField)
    urine_output_24h: ClinicalField = Field(default_factory=ClinicalField)


class Analyte(StrictModel):
    canonical_id: Optional[str] = None
    raw_name: str
    display_name: Optional[str] = None


class ObservationValue(StrictModel):
    """Lab value with an optional comparison operator (Milestone 1.2, item
    17). `>4000` is never collapsed into `4000`: raw_value keeps the exact
    source text, operator/normalized_numeric_value hold the parsed pieces
    when derivable, and display_value is what the renderer prints."""

    raw_value: str
    operator: Optional[ComparisonOperator] = None
    normalized_numeric_value: Optional[float] = None
    display_value: Optional[str] = None


class UnitValue(StrictModel):
    raw: Optional[str] = None
    normalized: Optional[str] = None


class DifferentialComponent(StrictModel):
    """One component of a differential count (e.g. leukogram SEG%/EOS%/...).

    Kept as its own typed structure instead of being smuggled inside
    ``reference_range``, which must only ever describe a reference range.
    """

    canonical_id: Optional[str] = None
    display_name: str
    raw_value: str
    display_value: Optional[str] = None


class ReferenceRange(StrictModel):
    """Reference range for a lab observation (Milestone 1.2, item 18).

    A one-sided range like "VR<500" is valid on its own: `reference_raw`
    always preserves the source text, `lower`/`upper` are filled in only
    when unambiguously derivable and a bilateral range is never required.
    """

    lower: Optional[float] = None
    upper: Optional[float] = None
    reference_raw: Optional[str] = None


class LabObservation(StrictModel):
    observation_id: str
    analyte: Analyte
    value: ObservationValue
    unit: UnitValue = Field(default_factory=UnitValue)
    collection_datetime: Optional[str] = None
    reference_range: Optional[ReferenceRange] = None
    differential: list[DifferentialComponent] = Field(default_factory=list)
    abnormal_flag: Optional[str] = None
    source_order: Optional[int] = None
    validation_status: ValidationStatus = ValidationStatus.CONFIRMED
    source_refs: list[str] = Field(default_factory=list)
    processing_key: Optional[str] = None


class BloodGas(StrictModel):
    gas_id: str
    collection_datetime: Optional[str] = None
    specimen_type: GasSpecimenType = GasSpecimenType.UNKNOWN
    observations: list[LabObservation] = Field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.CONFIRMED
    source_refs: list[str] = Field(default_factory=list)
    processing_key: Optional[str] = None


class DiagnosticStudy(StrictModel):
    """Procedure vs. result are two independent axes (Milestone 1.2, item
    11): a study can be PERFORMED with its result still PENDING, which a
    single status enum could never express without collapsing information."""

    study_id: str
    study_name: str
    procedure_status: DiagnosticStudyProcedureStatus = DiagnosticStudyProcedureStatus.UNKNOWN
    result_status: DiagnosticStudyResultStatus = DiagnosticStudyResultStatus.NOT_AVAILABLE
    ordered_at: Optional[TemporalValue] = None
    scheduled_at: Optional[TemporalValue] = None
    performed_at: Optional[TemporalValue] = None
    resulted_at: Optional[TemporalValue] = None
    findings: list[ClinicalField] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    processing_key: Optional[str] = None


class MicrobiologySerology(StrictModel):
    exam_id: str
    exam_type: str
    collection_datetime: Optional[str] = None
    result: ClinicalField = Field(default_factory=ClinicalField)
    organism: Optional[str] = None
    susceptibility: Optional[Any] = None
    validation_status: ValidationStatus = ValidationStatus.CONFIRMED
    source_refs: list[str] = Field(default_factory=list)
    processing_key: Optional[str] = None


class ComplementaryExams(StrictModel):
    laboratory_observations: list[LabObservation] = Field(default_factory=list)
    urinalysis: list[LabObservation] = Field(default_factory=list)
    blood_gases: list[BloodGas] = Field(default_factory=list)
    troponins: list[LabObservation] = Field(default_factory=list)
    microbiology_serology: list[MicrobiologySerology] = Field(default_factory=list)
    diagnostic_studies: list[DiagnosticStudy] = Field(default_factory=list)
    unmapped: list[Any] = Field(default_factory=list)


class Consultation(StrictModel):
    consultation_id: str
    specialty: ClinicalField
    temporal_value: TemporalValue = Field(default_factory=TemporalValue)
    assessment: ClinicalField = Field(default_factory=ClinicalField)
    conclusions: list[ClinicalField] = Field(default_factory=list)
    recommendations: list[ClinicalField] = Field(default_factory=list)
    status: ConsultationStatus = ConsultationStatus.ANSWERED
    source_refs: list[str] = Field(default_factory=list)


class PendingItem(StrictModel):
    pending_id: str
    type: PendingItemType
    label: str
    linked_entity_id: Optional[str] = None
    status: PendingStatus = PendingStatus.PENDING
    source_refs: list[str] = Field(default_factory=list)


class CareAction(StrictModel):
    action_id: str
    description: ClinicalField
    action_type: CareActionType = CareActionType.OTHER
    status: CareActionStatus = CareActionStatus.PLANNED
    responsible_team: Optional[str] = None
    source_refs: list[str] = Field(default_factory=list)


class IcuJustificationEntry(StrictModel):
    text: ClinicalField
    temporal_value: Optional[TemporalValue] = None


class IcuRequirementStatusEntry(StrictModel):
    """A point-in-time statement about ongoing ICU need (Milestone 1.2, item
    15). This is an append-only history, distinct from
    `explicit_justifications`: recording NO_LONGER_REQUIRED never erases an
    earlier REQUIRED entry, and no discharge decision is made here."""

    status: IcuRequirementStatus
    text: Optional[ClinicalField] = None
    temporal_value: Optional[TemporalValue] = None
    source_refs: list[str] = Field(default_factory=list)


class IcuContext(StrictModel):
    explicit_justifications: list[IcuJustificationEntry] = Field(default_factory=list)
    requirement_status_history: list[IcuRequirementStatusEntry] = Field(default_factory=list)
    active_supports: list[str] = Field(default_factory=list)
    monitoring_requirements: list[str] = Field(default_factory=list)
    instabilities: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)


class GlobalValidation(StrictModel):
    overall_status: GlobalStatus = GlobalStatus.READY
    conflicts: list[Any] = Field(default_factory=list)
    unresolved: list[Any] = Field(default_factory=list)
    warnings: list[Any] = Field(default_factory=list)


class Source(StrictModel):
    source_id: str
    source_type: SourceType
    modality: Optional[SourceModality] = None
    author_type: str = "HUMAN"
    deidentified: bool = True
    created_at: Optional[str] = None


class ProcessingMetadataEntry(StrictModel):
    """Idempotency/processing bookkeeping, kept out of `source_refs` on
    purpose (Milestone 2.0A.1, item 1): `source_refs` names clinical/document
    sources only, never pipeline-internal markers."""

    processing_key: str
    source_id: str
    module: str
    module_version: str


class Provenance(StrictModel):
    sources: list[Source] = Field(default_factory=list)
    processing_metadata: list[ProcessingMetadataEntry] = Field(default_factory=list)


class MedicalState(StrictModel):
    schema_version: str = "0.3"
    meta: Meta
    patient_ref: str

    display_identification: ClinicalField = Field(default_factory=ClinicalField)
    admission: Admission = Field(default_factory=Admission)
    diagnoses: list[Diagnosis] = Field(default_factory=list)
    hpma: Hpma = Field(default_factory=Hpma)
    evolution_history: list[EvolutionHistoryEntry] = Field(default_factory=list)
    clinical_events: list[ClinicalEvent] = Field(default_factory=list)
    physical_exam: PhysicalExam = Field(default_factory=PhysicalExam)
    history: History = Field(default_factory=History)
    medications: list[Medication] = Field(default_factory=list)
    therapies: Therapies = Field(default_factory=Therapies)
    controls: Controls = Field(default_factory=Controls)
    complementary_exams: ComplementaryExams = Field(default_factory=ComplementaryExams)
    consultations_section_state: ConsultationSectionState = ConsultationSectionState.UNKNOWN
    consultations: list[Consultation] = Field(default_factory=list)
    pending: list[PendingItem] = Field(default_factory=list)
    care_actions: list[CareAction] = Field(default_factory=list)
    icu_context: IcuContext = Field(default_factory=IcuContext)
    validation: GlobalValidation = Field(default_factory=GlobalValidation)
    provenance: Provenance = Field(default_factory=Provenance)
