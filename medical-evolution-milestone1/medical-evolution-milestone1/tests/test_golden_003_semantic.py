"""GOLDEN-003 — SEMANTIC_RENDER_REFERENCE / AUDIT_CASE.

Focus (item 35): diagnosis with specifications; microbiology with a
positive urease result; an invalid date detected (never silently
corrected); multiple same-day labs that must not be resolved arbitrarily.
Known audit findings are documented separately (see
golden_samples/golden_003/golden_003_audit_notes.json).
"""

import copy

import pytest

from models.medical_state import MedicalState, TemporalPrecision, TemporalValue, ValidationStatus
from rendering.medical_note_renderer import render_medical_note
from rendering.renderability_gate import RenderNotAllowedError
from tests.conftest import load_golden_state_number


def _state() -> MedicalState:
    return MedicalState.model_validate(load_golden_state_number("003"))


def test_diagnosis_has_specifications():
    state = _state()
    dx = state.diagnoses[0]
    assert dx.main.value == "HEMORRAGIA DIGESTIVA A/E"
    assert [s.value for s in dx.specifications] == ["HEMATEMESE", "MELENA", "DOR ABDOMINAL DIFUSA A/E"]
    rendered = render_medical_note(state)
    block = rendered.split("## HIPÓTESES DIAGNÓSTICAS:", 1)[1].split("## HPMA:", 1)[0]
    assert ">> HEMATEMESE" in block
    assert ">> MELENA" in block


def test_microbiology_urease_positive_is_rendered():
    state = _state()
    exam = state.complementary_exams.microbiology_serology[0]
    assert exam.exam_type == "TESTE UREASE"
    assert exam.result.value == "POSITIVO"
    rendered = render_medical_note(state)
    assert "TESTE UREASE: POSITIVO" in rendered


def test_invalid_scheduled_date_is_preserved_raw_on_the_study():
    # The colonoscopy in this record is documented as scheduled for "31/09"
    # -- an impossible calendar date. It is preserved verbatim on the study
    # (ordered_at, a TemporalValue) rather than silently fixed to 30/09,
    # 31/08, or any other date (item 3, hardened in Milestone 2.0A.1).
    state = _state()
    colonoscopy = next(s for s in state.complementary_exams.diagnostic_studies if "COLONOSCOPIA" in s.study_name)
    assert colonoscopy.ordered_at.raw == "31/09"
    assert colonoscopy.ordered_at.normalized is None
    assert colonoscopy.ordered_at.validation_status == ValidationStatus.UNRESOLVED


def test_invalid_temporal_value_is_flagged_not_auto_corrected():
    # The same raw text ("31/09") run through TemporalValue -- the type
    # every gate-checked date in the schema actually uses (admission dates,
    # evolution entries, consultations, ...) -- must never normalize to a
    # valid date and must be classified as needing review.
    tv = TemporalValue(raw="31/09", normalized=None, precision=TemporalPrecision.PARTIAL_DATE, validation_status=ValidationStatus.UNRESOLVED)
    assert tv.raw == "31/09"
    assert tv.normalized is None
    assert tv.precision == TemporalPrecision.PARTIAL_DATE
    assert tv.validation_status == ValidationStatus.UNRESOLVED


def test_invalid_temporal_value_is_never_silently_used_by_the_renderer():
    # If GOLDEN-003's exact "31/09" value were captured as a gate-checked
    # TemporalValue (rather than a plain, unchecked string on
    # DiagnosticStudy.ordered_at), the renderability gate must refuse to
    # render rather than silently treat it as a valid clinical date.
    data = copy.deepcopy(load_golden_state_number("003"))
    data["admission"]["hospital_admission_date"] = {
        "raw": "31/09",
        "normalized": None,
        "precision": "PARTIAL_DATE",
        "period": "UNSPECIFIED",
        "validation_status": "UNRESOLVED",
    }
    state = MedicalState.model_validate(data)
    assert state.admission.hospital_admission_date.raw == "31/09"
    assert state.admission.hospital_admission_date.normalized is None

    with pytest.raises(RenderNotAllowedError) as exc_info:
        render_medical_note(state)
    assert any("hospital_admission_date" in reason for reason in exc_info.value.reasons)


def test_same_day_lab_ambiguity_is_not_silently_resolved():
    # 31/08 carries two creatinine readings: one with a time (13:20), one
    # without -- there is no way to know which is "the latest" (item 33).
    state = _state()
    cr_values = {
        obs.value.raw_value
        for obs in state.complementary_exams.laboratory_observations
        if obs.analyte.canonical_id == "CR" and (obs.collection_datetime or "").startswith("2026-08-31")
    }
    assert cr_values == {"0,85", "0,99"}
    rendered = render_medical_note(state)
    day_line = next(line for line in rendered.splitlines() if line.startswith("- 31/08:"))
    assert "CR 0,85" in day_line
    assert "CR 0,99" in day_line
