"""Normalization orchestration (Milestone 2.0A, item 5).

`normalize_extraction_candidate` is the single entry point: it turns a
Pydantic-validated `ExamExtractionCandidate` into a `NormalizedExamBatch`
by delegating to the focused modules in this package (aliases, numeric
parsing, temporal parsing, specimen handling, reference ranges). It never
implements any of that logic itself, and it never picks a "latest" reading
among same-day/same-analyte observations (item 11) — that selection stays
where it already lives, in the presentation layer
(`rendering.text_utils.analyte_readings_order_is_ambiguous`); this module
only flags the ambiguity as a warning when it is worth surfacing early.

Every candidate item ends up in exactly one place: normalized, unmapped, or
conflicts (never silently dropped) — see `exam_normalization.completeness`.
"""

from __future__ import annotations

from typing import Optional

from exam_extraction.models import (
    BloodGasCandidate,
    DiagnosticStudyCandidate,
    ExamExtractionCandidate,
    ExamSourceEnvelope,
    MicrobiologyCandidate,
    ObservationCandidate,
)
from exam_normalization.aliases import resolve_canonical_id
from exam_normalization.idempotency import build_idempotency_key, idempotency_marker
from exam_normalization.numeric_parsing import parse_numeric_value
from exam_normalization.reference_range import parse_reference_range
from exam_normalization.specimen import resolve_specimen_type
from exam_normalization.temporal import parse_exam_temporal
from exam_normalization.models import NormalizationIssue, NormalizedExamBatch
from models.medical_state import (
    Analyte,
    BloodGas,
    ClinicalField,
    ClinicalState,
    DiagnosticStudy,
    DiagnosticStudyProcedureStatus,
    DiagnosticStudyResultStatus,
    LabObservation,
    MicrobiologySerology,
    UnitValue,
    ValidationStatus,
)
from rendering.text_utils import analyte_readings_order_is_ambiguous


def _reference_year(envelope: ExamSourceEnvelope) -> Optional[int]:
    doc_tv = envelope.document_temporal_value
    if doc_tv is None or not doc_tv.normalized:
        return None
    try:
        return int(doc_tv.normalized[:4])
    except ValueError:
        return None


def _normalize_observation(
    item: ObservationCandidate,
    category: str,
    envelope: ExamSourceEnvelope,
    reference_year: Optional[int],
    conflicts: list[NormalizationIssue],
) -> Optional[LabObservation]:
    if item.raw_value is None or not item.raw_value.strip():
        conflicts.append(NormalizationIssue(
            category="MISSING_VALUE",
            message=f"{category} item '{item.raw_name}' has no raw_value to normalize",
            source_ref=item.source_ref,
            raw_snapshot=item.raw_name,
        ))
        return None

    canonical_id = resolve_canonical_id(item.raw_name)
    value = parse_numeric_value(item.raw_value, canonical_id=canonical_id)
    temporal = parse_exam_temporal(item.raw_temporal, reference_year=reference_year)
    key = build_idempotency_key(envelope.source_id, category, str(item.source_order))

    return LabObservation(
        observation_id=f"{envelope.source_id}:{category}:{item.source_order}",
        analyte=Analyte(canonical_id=canonical_id, raw_name=item.raw_name, display_name=canonical_id),
        value=value,
        unit=UnitValue(raw=item.raw_unit),
        collection_datetime=temporal.normalized or temporal.raw,
        reference_range=parse_reference_range(item.raw_reference_range),
        source_order=item.source_order,
        validation_status=ValidationStatus.CONFIRMED,
        source_refs=[item.source_ref, idempotency_marker(key)],
    )


def _flag_same_day_ambiguity(observations: list[LabObservation], category: str, warnings: list[NormalizationIssue]) -> None:
    by_day_analyte: dict[tuple[str, str], list[LabObservation]] = {}
    for obs in observations:
        day = (obs.collection_datetime or "")[:10]
        cid = (obs.analyte.canonical_id or "").upper()
        if not day or not cid:
            continue
        by_day_analyte.setdefault((day, cid), []).append(obs)

    for (day, cid), group in by_day_analyte.items():
        if analyte_readings_order_is_ambiguous(group):
            warnings.append(NormalizationIssue(
                category="SAME_DAY_TEMPORAL_AMBIGUITY",
                message=(
                    f"{category}: {len(group)} readings of '{cid}' on {day} cannot be "
                    "confidently ordered by time; none was selected as \"latest\"."
                ),
                raw_snapshot=", ".join(o.value.raw_value for o in group),
            ))


def _normalize_blood_gas(
    item: BloodGasCandidate,
    envelope: ExamSourceEnvelope,
    reference_year: Optional[int],
    conflicts: list[NormalizationIssue],
) -> BloodGas:
    temporal = parse_exam_temporal(item.raw_temporal, reference_year=reference_year)
    key = build_idempotency_key(envelope.source_id, "blood_gas", str(item.source_order))
    observations = []
    for obs_item in item.observations:
        normalized = _normalize_observation(obs_item, "blood_gas_observation", envelope, reference_year, conflicts)
        if normalized is not None:
            observations.append(normalized)
    return BloodGas(
        gas_id=f"{envelope.source_id}:blood_gas:{item.source_order}",
        collection_datetime=temporal.normalized or temporal.raw,
        specimen_type=resolve_specimen_type(item.raw_specimen_type),
        observations=observations,
        validation_status=ValidationStatus.CONFIRMED,
        source_refs=[item.source_ref, idempotency_marker(key)],
    )


def _normalize_microbiology(
    item: MicrobiologyCandidate,
    envelope: ExamSourceEnvelope,
    reference_year: Optional[int],
) -> MicrobiologySerology:
    temporal = parse_exam_temporal(item.raw_temporal, reference_year=reference_year)
    key = build_idempotency_key(envelope.source_id, "microbiology", str(item.source_order))
    # A missing result stays MISSING -- never copied from a previous entry
    # (item 15): each candidate is normalized independently, with no
    # visibility into any other item's result.
    has_result = item.raw_result is not None and item.raw_result.strip() != ""
    result = ClinicalField(
        value=item.raw_result if has_result else None,
        clinical_state=ClinicalState.PRESENT if has_result else ClinicalState.UNKNOWN,
        validation_status=ValidationStatus.CONFIRMED if has_result else ValidationStatus.MISSING,
        source_refs=[item.source_ref],
    )
    return MicrobiologySerology(
        exam_id=f"{envelope.source_id}:microbiology:{item.source_order}",
        exam_type=item.raw_name,
        collection_datetime=temporal.normalized or temporal.raw,
        result=result,
        organism=item.organism_hint,
        validation_status=ValidationStatus.CONFIRMED,
        source_refs=[item.source_ref, idempotency_marker(key)],
    )


_VALID_PROCEDURE_STATUSES = {s.value for s in DiagnosticStudyProcedureStatus}
_VALID_RESULT_STATUSES = {s.value for s in DiagnosticStudyResultStatus}


def _resolve_procedure_status_hint(hint: Optional[str]) -> DiagnosticStudyProcedureStatus:
    # item 17: a hint is only accepted when it is already one of the known,
    # structured enum values -- never inferred from free narrative text
    # such as "RECOMENDADO SOLICITAR". Anything else defaults to UNKNOWN,
    # matching the model's own default.
    if hint and hint.strip().upper() in _VALID_PROCEDURE_STATUSES:
        return DiagnosticStudyProcedureStatus(hint.strip().upper())
    return DiagnosticStudyProcedureStatus.UNKNOWN


def _resolve_result_status_hint(hint: Optional[str]) -> DiagnosticStudyResultStatus:
    if hint and hint.strip().upper() in _VALID_RESULT_STATUSES:
        return DiagnosticStudyResultStatus(hint.strip().upper())
    return DiagnosticStudyResultStatus.NOT_AVAILABLE


def _normalize_diagnostic_study(
    item: DiagnosticStudyCandidate,
    envelope: ExamSourceEnvelope,
    reference_year: Optional[int],
) -> DiagnosticStudy:
    key = build_idempotency_key(envelope.source_id, "diagnostic_study", str(item.source_order))
    findings = [
        ClinicalField(
            value=f.raw_text, clinical_state=ClinicalState.PRESENT,
            validation_status=ValidationStatus.CONFIRMED, source_refs=[item.source_ref],
        )
        for f in item.findings
    ]
    temporal = parse_exam_temporal(item.raw_temporal, reference_year=reference_year)
    # The raw temporal is not attributed to any one of ordered/scheduled/
    # performed/resulted without real evidence of which it is; it is kept
    # on `ordered_at` as the least presumptive slot when a procedure status
    # is not confirmed PERFORMED, and on `performed_at` otherwise.
    procedure_status = _resolve_procedure_status_hint(item.procedure_status_hint)
    normalized_date = temporal.normalized or temporal.raw
    ordered_at = normalized_date if procedure_status != DiagnosticStudyProcedureStatus.PERFORMED else None
    performed_at = normalized_date if procedure_status == DiagnosticStudyProcedureStatus.PERFORMED else None

    return DiagnosticStudy(
        study_id=f"{envelope.source_id}:diagnostic_study:{item.source_order}",
        study_name=item.raw_name,
        procedure_status=procedure_status,
        result_status=_resolve_result_status_hint(item.result_status_hint),
        ordered_at=ordered_at,
        performed_at=performed_at,
        findings=findings,
        source_refs=[item.source_ref, idempotency_marker(key)],
    )


def normalize_extraction_candidate(
    candidate: ExamExtractionCandidate,
    envelope: ExamSourceEnvelope,
) -> NormalizedExamBatch:
    reference_year = _reference_year(envelope)
    conflicts: list[NormalizationIssue] = []
    warnings: list[NormalizationIssue] = [
        NormalizationIssue(category="EXTRACTOR_WARNING", message=w.message, source_ref=w.item_ref)
        for w in candidate.extraction_warnings
    ]

    laboratory_observations = []
    for item in candidate.general_labs:
        obs = _normalize_observation(item, "general_lab", envelope, reference_year, conflicts)
        if obs is not None:
            laboratory_observations.append(obs)
    _flag_same_day_ambiguity(laboratory_observations, "general_lab", warnings)

    urinalysis = []
    for item in candidate.urinalysis:
        obs = _normalize_observation(item, "urinalysis", envelope, reference_year, conflicts)
        if obs is not None:
            urinalysis.append(obs)
    _flag_same_day_ambiguity(urinalysis, "urinalysis", warnings)

    # Troponins stay individual and temporally independent (item 14): no
    # same-day grouping/ambiguity policy is applied to them, unlike general
    # labs and urinalysis above.
    troponins = []
    for item in candidate.troponins:
        obs = _normalize_observation(item, "troponin", envelope, reference_year, conflicts)
        if obs is not None:
            troponins.append(obs)

    blood_gases = [
        _normalize_blood_gas(item, envelope, reference_year, conflicts)
        for item in candidate.blood_gases
    ]

    microbiology_serology = [
        _normalize_microbiology(item, envelope, reference_year)
        for item in candidate.microbiology
    ]

    diagnostic_studies = [
        _normalize_diagnostic_study(item, envelope, reference_year)
        for item in candidate.diagnostic_studies
    ]

    unmapped = [item.raw_text for item in candidate.unmapped]

    return NormalizedExamBatch(
        source_id=candidate.source_id,
        laboratory_observations=laboratory_observations,
        urinalysis=urinalysis,
        blood_gases=blood_gases,
        troponins=troponins,
        microbiology_serology=microbiology_serology,
        diagnostic_studies=diagnostic_studies,
        unmapped=unmapped,
        conflicts=conflicts,
        warnings=warnings,
    )
