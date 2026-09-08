from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Union
from pydantic import BaseModel, Field


Scalar = Union[str, int, float, bool]


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


class ClinicalField(BaseModel):
    value: Optional[Scalar] = None
    clinical_state: ClinicalState = ClinicalState.UNKNOWN
    validation_status: ValidationStatus = ValidationStatus.MISSING
    source_refs: list[str] = Field(default_factory=list)


class Meta(BaseModel):
    state_id: str
    state_revision: int = 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    language: str = "pt-BR"
    template_profile_id: Optional[str] = "UTI_HOSPITALIS_V1"


class Admission(BaseModel):
    hospital_admission_date: ClinicalField = Field(default_factory=ClinicalField)
    icu_admission_date: ClinicalField = Field(default_factory=ClinicalField)
    origin: ClinicalField = Field(default_factory=ClinicalField)


class Diagnosis(BaseModel):
    diagnosis_id: str
    main: ClinicalField
    specifications: list[ClinicalField] = Field(default_factory=list)
    status: str = "ACTIVE"
    source_refs: list[str] = Field(default_factory=list)


class Hpma(BaseModel):
    text: ClinicalField = Field(default_factory=ClinicalField)
    source_type: Optional[str] = None
    source_datetime: Optional[str] = None
    source_refs: list[str] = Field(default_factory=list)


class EvolutionHistoryEntry(BaseModel):
    evolution_id: str
    datetime: Optional[str] = None
    period: Optional[str] = "UNSPECIFIED"
    text: ClinicalField
    author_type: str = "HUMAN"
    source_refs: list[str] = Field(default_factory=list)


class ClinicalEvent(BaseModel):
    event_id: str
    datetime: Optional[str] = None
    event_type: str
    description: ClinicalField
    severity: Optional[str] = "UNKNOWN"
    status: str = "ACTIVE"
    related_entities: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class PhysicalExam(BaseModel):
    general: ClinicalField = Field(default_factory=ClinicalField)
    neurologic: ClinicalField = Field(default_factory=ClinicalField)
    cardiovascular: ClinicalField = Field(default_factory=ClinicalField)
    respiratory: ClinicalField = Field(default_factory=ClinicalField)
    abdominal: ClinicalField = Field(default_factory=ClinicalField)
    extremities: ClinicalField = Field(default_factory=ClinicalField)


class History(BaseModel):
    allergies: ClinicalField = Field(default_factory=ClinicalField)
    past_medical_history: ClinicalField = Field(default_factory=ClinicalField)
    previous_surgeries: ClinicalField = Field(default_factory=ClinicalField)
    chronic_medications: ClinicalField = Field(default_factory=ClinicalField)
    habits: ClinicalField = Field(default_factory=ClinicalField)
    family_history: ClinicalField = Field(default_factory=ClinicalField)


class Medication(BaseModel):
    medication_id: str
    raw_name: Optional[str] = None
    generic_name: Optional[str] = None
    presentation: Optional[str] = None
    dosage: Optional[str] = None
    route: Optional[str] = None
    source_order: Optional[int] = None
    classifications: list[str] = Field(default_factory=list)
    status: str = "ACTIVE"
    validation_status: ValidationStatus = ValidationStatus.CONFIRMED
    source_refs: list[str] = Field(default_factory=list)


class Therapies(BaseModel):
    hemotransfusion: ClinicalField = Field(default_factory=ClinicalField)
    niv: ClinicalField = Field(default_factory=ClinicalField)
    invasive_mechanical_ventilation: ClinicalField = Field(default_factory=ClinicalField)
    renal_replacement_therapy: ClinicalField = Field(default_factory=ClinicalField)


class Controls(BaseModel):
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


class Analyte(BaseModel):
    canonical_id: Optional[str] = None
    raw_name: str
    display_name: Optional[str] = None


class ObservationValue(BaseModel):
    raw: str
    normalized: Optional[Union[float, int, str]] = None
    display: Optional[str] = None


class UnitValue(BaseModel):
    raw: Optional[str] = None
    normalized: Optional[str] = None


class LabObservation(BaseModel):
    observation_id: str
    analyte: Analyte
    value: ObservationValue
    unit: UnitValue = Field(default_factory=UnitValue)
    collection_datetime: Optional[str] = None
    reference_range: Optional[dict[str, Any]] = None
    abnormal_flag: Optional[str] = None
    source_order: Optional[int] = None
    validation_status: ValidationStatus = ValidationStatus.CONFIRMED
    source_refs: list[str] = Field(default_factory=list)


class BloodGas(BaseModel):
    gas_id: str
    collection_datetime: Optional[str] = None
    sample_type: Optional[str] = None
    observations: list[LabObservation] = Field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.CONFIRMED
    source_refs: list[str] = Field(default_factory=list)


class DiagnosticStudy(BaseModel):
    study_id: str
    study_name: str
    status: str = "UNKNOWN"
    ordered_at: Optional[str] = None
    scheduled_at: Optional[str] = None
    performed_at: Optional[str] = None
    resulted_at: Optional[str] = None
    findings: list[ClinicalField] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class MicrobiologySerology(BaseModel):
    exam_id: str
    exam_type: str
    collection_datetime: Optional[str] = None
    result: ClinicalField = Field(default_factory=ClinicalField)
    organism: Optional[str] = None
    susceptibility: Optional[Any] = None
    validation_status: ValidationStatus = ValidationStatus.CONFIRMED
    source_refs: list[str] = Field(default_factory=list)


class ComplementaryExams(BaseModel):
    laboratory_observations: list[LabObservation] = Field(default_factory=list)
    urinalysis: list[LabObservation] = Field(default_factory=list)
    blood_gases: list[BloodGas] = Field(default_factory=list)
    troponins: list[LabObservation] = Field(default_factory=list)
    microbiology_serology: list[MicrobiologySerology] = Field(default_factory=list)
    diagnostic_studies: list[DiagnosticStudy] = Field(default_factory=list)
    unmapped: list[Any] = Field(default_factory=list)


class Consultation(BaseModel):
    consultation_id: str
    specialty: ClinicalField
    request_datetime: Optional[str] = None
    response_datetime: Optional[str] = None
    assessment: ClinicalField = Field(default_factory=ClinicalField)
    recommendations: list[ClinicalField] = Field(default_factory=list)
    status: str = "ANSWERED"
    source_refs: list[str] = Field(default_factory=list)


class PendingItem(BaseModel):
    pending_id: str
    type: str
    label: str
    linked_entity_id: Optional[str] = None
    status: str = "PENDING"
    source_refs: list[str] = Field(default_factory=list)


class CareAction(BaseModel):
    action_id: str
    description: ClinicalField
    action_type: str = "OTHER"
    status: str = "PLANNED"
    responsible_team: Optional[str] = None
    source_refs: list[str] = Field(default_factory=list)


class IcuContext(BaseModel):
    explicit_justification: ClinicalField = Field(default_factory=ClinicalField)
    active_supports: list[str] = Field(default_factory=list)
    monitoring_requirements: list[str] = Field(default_factory=list)
    instabilities: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)


class GlobalValidation(BaseModel):
    overall_status: GlobalStatus = GlobalStatus.READY
    conflicts: list[Any] = Field(default_factory=list)
    unresolved: list[Any] = Field(default_factory=list)
    warnings: list[Any] = Field(default_factory=list)


class Source(BaseModel):
    source_id: str
    source_type: str
    modality: Optional[str] = None
    author_type: str = "HUMAN"
    deidentified: bool = True
    created_at: Optional[str] = None


class Provenance(BaseModel):
    sources: list[Source] = Field(default_factory=list)


class MedicalState(BaseModel):
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
