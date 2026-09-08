"""GOLDEN-002 — SEMANTIC_RENDER_REFERENCE.

Focus (Milestone 1.2, item 35): admission datetime preserves time;
consultation state NOT_REQUESTED; transfer represented as a pending item.
No byte-for-byte comparison — see docs/golden_sample_roles_v0_1.md.
"""

from models.medical_state import ConsultationSectionState, MedicalState
from rendering.medical_note_renderer import render_medical_note
from tests.conftest import load_golden_state_number


def _state() -> MedicalState:
    return MedicalState.model_validate(load_golden_state_number("002"))


def test_admission_datetime_preserves_time():
    state = _state()
    assert state.admission.hospital_admission_date.raw == "2026-09-03T03:34:00"
    rendered = render_medical_note(state)
    assert "DATA DE INTERNAÇÃO HOSPITALAR: 03/09/2026 03:34" in rendered
    assert "DATA DE INTERNAÇÃO EM UTI: 03/09/2026 03:34" in rendered


def test_consultation_state_is_not_requested():
    state = _state()
    assert state.consultations_section_state == ConsultationSectionState.NOT_REQUESTED
    assert state.consultations == []
    rendered = render_medical_note(state)
    assert "## INTERCONSULTA DE ESPECIALIDADES:\n- NÃO SOLICITADO" in rendered


def test_transfer_is_represented_as_a_pending_item():
    state = _state()
    labels = [p.label for p in state.pending]
    assert any("TRANSFERENCIA" in label for label in labels)
    # It must not be smuggled in as a diagnostic study or a fabricated
    # consultation -- it is a pending administrative/clinical item.
    study_names = [s.study_name for s in state.complementary_exams.diagnostic_studies]
    assert not any("TRANSFERENCIA" in name for name in study_names)
    rendered = render_medical_note(state)
    assert "TRANSFERENCIA PARA HOSPITAL PSIQUIATRICO" in rendered.split("## AGUARDO:", 1)[1]
