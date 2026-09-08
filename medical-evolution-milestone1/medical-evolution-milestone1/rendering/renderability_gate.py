from __future__ import annotations

from models.medical_state import (
    MedicalState,
    ClinicalField,
    ValidationStatus,
    GlobalStatus,
    MedicationStatus,
)
from templates.uti_hospitalis_v1 import UTIHospitalisV1
from rendering.text_utils import has_value

# READY / READY_WITH_WARNINGS may render. PROCESSING / REVIEW_REQUIRED /
# FAILED must never be treated as validated data (Milestone 1.1, item 3).
ALLOWED_OVERALL_STATUSES = {GlobalStatus.READY, GlobalStatus.READY_WITH_WARNINGS}

# A field consumed by the renderer with one of these statuses must never be
# printed as if it were confirmed data (item 4). MISSING/NEGATED/NOT_APPLICABLE
# are semantics, not errors, and are intentionally left out of this set.
BLOCKING_FIELD_STATUSES = {ValidationStatus.CONFLICT, ValidationStatus.UNRESOLVED}

_RESOLVED_ISSUE_MARKERS = {"RESOLVED", "CLOSED", "DISMISSED"}


class RenderNotAllowedError(Exception):
    """Raised by check_renderable() when the state must not be rendered.

    Carries every reason found (not just the first one) so a future UI layer
    can show the whole list instead of a single opaque error.
    """

    def __init__(self, reasons: list[str]):
        self.reasons = list(reasons)
        message = "; ".join(self.reasons) if self.reasons else "Renderização bloqueada"
        super().__init__(message)


def _is_active_issue(item: object) -> bool:
    """An item in validation.conflicts/unresolved counts as active unless it
    explicitly marks itself as resolved/closed/dismissed. Plain strings or
    any other shape are conservatively treated as active."""
    if isinstance(item, dict):
        status = str(item.get("status", "")).strip().upper()
        if status in _RESOLVED_ISSUE_MARKERS:
            return False
    return True


def _check_field(path: str, field: ClinicalField, reasons: list[str]) -> None:
    if field.validation_status in BLOCKING_FIELD_STATUSES:
        reasons.append(f"campo '{path}' possui validation_status={field.validation_status.value}")


def check_renderable(state: MedicalState, template: UTIHospitalisV1) -> None:
    """Deterministic pre-render gate.

    Raises RenderNotAllowedError when the state as a whole (overall_status,
    active conflicts/unresolved items) or any individual field the renderer
    would actually print is not in a renderable condition. Never mutates the
    state and never writes anything into the rendered text itself.
    """
    reasons: list[str] = []

    overall = state.validation.overall_status
    if overall not in ALLOWED_OVERALL_STATUSES:
        reasons.append(f"validation.overall_status={overall.value} não permite renderização")

    for idx, item in enumerate(state.validation.conflicts):
        if _is_active_issue(item):
            reasons.append(f"conflito ativo em validation.conflicts[{idx}]: {item!r}")

    for idx, item in enumerate(state.validation.unresolved):
        if _is_active_issue(item):
            reasons.append(f"item unresolved ativo em validation.unresolved[{idx}]: {item!r}")

    _check_field("display_identification", state.display_identification, reasons)
    _check_field("admission.hospital_admission_date", state.admission.hospital_admission_date, reasons)
    _check_field("admission.icu_admission_date", state.admission.icu_admission_date, reasons)
    _check_field("admission.origin", state.admission.origin, reasons)

    for idx, dx in enumerate(state.diagnoses):
        if dx.status not in template.diagnosis_visible_statuses:
            continue
        _check_field(f"diagnoses[{idx}].main", dx.main, reasons)
        for sidx, spec in enumerate(dx.specifications):
            if has_value(spec):
                _check_field(f"diagnoses[{idx}].specifications[{sidx}]", spec, reasons)

    _check_field("hpma.text", state.hpma.text, reasons)

    for idx, ev in enumerate(state.evolution_history):
        _check_field(f"evolution_history[{idx}].text", ev.text, reasons)

    for attr in template.physical_exam_order:
        _check_field(f"physical_exam.{attr}", getattr(state.physical_exam, attr), reasons)

    for attr in template.history_order:
        _check_field(f"history.{attr}", getattr(state.history, attr), reasons)

    for med in state.medications:
        is_rendered_antibiotic = (
            med.status == MedicationStatus.ACTIVE
            and "ANTIBIOTIC" in {c.upper() for c in med.classifications}
        )
        if is_rendered_antibiotic and med.validation_status in BLOCKING_FIELD_STATUSES:
            reasons.append(
                f"medication '{med.medication_id}' possui validation_status={med.validation_status.value}"
            )

    if has_value(state.therapies.hemotransfusion):
        _check_field("therapies.hemotransfusion", state.therapies.hemotransfusion, reasons)
    if has_value(state.therapies.niv):
        _check_field("therapies.niv", state.therapies.niv, reasons)

    for attr in template.controls_order:
        field = getattr(state.controls, attr)
        if has_value(field):
            _check_field(f"controls.{attr}", field, reasons)

    excluded = template.excluded_lab_ids
    for obs in state.complementary_exams.laboratory_observations:
        cid = (obs.analyte.canonical_id or "").upper()
        if cid in excluded:
            continue
        if obs.validation_status in BLOCKING_FIELD_STATUSES:
            reasons.append(
                f"laboratory_observation '{obs.observation_id}' possui validation_status={obs.validation_status.value}"
            )

    for obs in state.complementary_exams.urinalysis:
        if obs.validation_status in BLOCKING_FIELD_STATUSES:
            reasons.append(
                f"urinalysis '{obs.observation_id}' possui validation_status={obs.validation_status.value}"
            )

    for gas in state.complementary_exams.blood_gases:
        if gas.validation_status in BLOCKING_FIELD_STATUSES:
            reasons.append(f"blood_gas '{gas.gas_id}' possui validation_status={gas.validation_status.value}")
        for obs in gas.observations:
            if obs.validation_status in BLOCKING_FIELD_STATUSES:
                reasons.append(
                    f"blood_gas observation '{obs.observation_id}' possui validation_status={obs.validation_status.value}"
                )

    for obs in state.complementary_exams.troponins:
        if obs.validation_status in BLOCKING_FIELD_STATUSES:
            reasons.append(
                f"troponin '{obs.observation_id}' possui validation_status={obs.validation_status.value}"
            )

    for idx, study in enumerate(state.complementary_exams.diagnostic_studies):
        for fidx, finding in enumerate(study.findings):
            if has_value(finding):
                _check_field(
                    f"complementary_exams.diagnostic_studies[{idx}].findings[{fidx}]", finding, reasons
                )

    for idx, consultation in enumerate(state.consultations):
        _check_field(f"consultations[{idx}].specialty", consultation.specialty, reasons)
        _check_field(f"consultations[{idx}].assessment", consultation.assessment, reasons)
        for ridx, rec in enumerate(consultation.recommendations):
            _check_field(f"consultations[{idx}].recommendations[{ridx}]", rec, reasons)

    _check_field("icu_context.explicit_justification", state.icu_context.explicit_justification, reasons)

    for idx, action in enumerate(state.care_actions):
        _check_field(f"care_actions[{idx}].description", action.description, reasons)

    if reasons:
        raise RenderNotAllowedError(reasons)
