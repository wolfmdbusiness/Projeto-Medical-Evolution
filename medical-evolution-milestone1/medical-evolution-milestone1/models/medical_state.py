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
    ANSWERED = "ANSWERED"
    CANCELLED = "CANCELLED"


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


class DiagnosticStudyStatus(str, Enum):
    ORDERED = "ORDERED"
    SCHEDULED = "SCHEDULED"
    PERFORMED = "PERFORMED"
    RESULTED = "RESULTED"
    PENDING = "PENDING"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class SourceType(str, Enum):
    MEDICAL_EVOLUTION = "MEDICAL_EVOLUTION"
    OTHER = "OTHER"


class SourceModality(str, Enum):
    TEXT = "TEXT"
    OTHER = "OTHER"


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
    hospital_admission_date: ClinicalField = Field(default_factory=ClinicalField)
    icu_admission_date: ClinicalField = Field(default_factory=ClinicalField)
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
    datetime: Optional[str] = None
    period: Optional[str] = "UNSPECIFIED"
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
    raw: str
    normalized: Optional[Union[float, int, str]] = None
    display: Optional[str] = None


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


class LabObservation(StrictModel):
    observation_id: str
    analyte: Analyte
    value: ObservationValue
    unit: UnitValue = Field(default_factory=UnitValue)
    collection_datetime: Optional[str] = None
    reference_range: Optional[dict[str, Any]] = None
    differential: list[DifferentialComponent] = Field(default_factory=list)
    abnormal_flag: Optional[str] = None
    source_order: Optional[int] = None
    validation_status: ValidationStatus = ValidationStatus.CONFIRMED
    source_refs: list[str] = Field(default_factory=list)


class BloodGas(StrictModel):
    gas_id: str
    collection_datetime: Optional[str] = None
    sample_type: Optional[str] = None
    observations: list[LabObservation] = Field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.CONFIRMED
    source_refs: list[str] = Field(default_factory=list)


class DiagnosticStudy(StrictModel):
    study_id: str
    study_name: str
    status: DiagnosticStudyStatus = DiagnosticStudyStatus.UNKNOWN
    ordered_at: Optional[str] = None
    scheduled_at: Optional[str] = None
    performed_at: Optional[str] = None
    resulted_at: Optional[str] = None
    findings: list[ClinicalField] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class MicrobiologySerology(StrictModel):
    exam_id: str
    exam_type: str
    collection_datetime: Optional[str] = None
    result: ClinicalField = Field(default_factory=ClinicalField)
    organism: Optional[str] = None
    susceptibility: Optional[Any] = None
    validation_status: ValidationStatus = ValidationStatus.CONFIRMED
    source_refs: list[str] = Field(default_factory=list)


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
    request_datetime: Optional[str] = None
    response_datetime: Optional[str] = None
    assessment: ClinicalField = Field(default_factory=ClinicalField)
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


class IcuContext(StrictModel):
    explicit_justification: ClinicalField = Field(default_factory=ClinicalField)
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


class Provenance(StrictModel):
    sources: list[Source] = Field(default_factory=list)


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
    consultations: list[Consultation] = Field(default_factory=list)
    pending: list[PendingItem] = Field(default_factory=list)
    care_actions: list[CareAction] = Field(default_factory=list)
    icu_context: IcuContext = Field(default_factory=IcuContext)
    validation: GlobalValidation = Field(default_factory=GlobalValidation)
    provenance: Provenance = Field(default_factory=Provenance)
