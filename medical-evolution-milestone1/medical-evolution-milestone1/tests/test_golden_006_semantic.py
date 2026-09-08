"""GOLDEN-006 — SEMANTIC_RENDER_REFERENCE.

Focus (item 35): an active antibiotic with a documented D1/start date; a
REQUESTED consultation; cultures pending without an invented result; a
documented risk of DVA/mechanical ventilation that never becomes an
active support.
"""

from models.medical_state import ConsultationStatus, MedicalState, MedicationStatus
from rendering.medical_note_renderer import render_medical_note
from rendering.text_utils import has_value
from tests.conftest import load_golden_state_number


def _state() -> MedicalState:
    return MedicalState.model_validate(load_golden_state_number("006"))


def test_active_antibiotic_with_documented_start_day():
    state = _state()
    med = state.medications[0]
    assert med.status == MedicationStatus.ACTIVE
    assert "ANTIBIOTIC" in med.classifications
    assert med.documented_therapy_day == "D1"
    assert med.started_at.normalized == "2026-09-02"
    rendered = render_medical_note(state)
    assert "## ANTIBIOTICOTERAPIA:\n- CEFTRIAXONE D1: 02/09" in rendered


def test_consultation_is_requested_not_answered():
    state = _state()
    consultation = state.consultations[0]
    assert consultation.status == ConsultationStatus.REQUESTED
    rendered = render_medical_note(state)
    assert "SOLICITADA AVALIAÇÃO" in rendered
    assert "CONDUTAS" not in rendered


def test_cultures_pending_do_not_invent_a_result():
    state = _state()
    assert state.complementary_exams.microbiology_serology == []
    labels = [p.label for p in state.pending]
    assert "CULTURAS" in labels
    rendered = render_medical_note(state)
    assert "CULTURAS" in rendered.split("## AGUARDO:", 1)[1]


def test_risk_of_dva_and_vm_never_becomes_active_support():
    state = _state()
    assert state.icu_context.active_supports == []
    assert any("RISK_OF" in r for r in state.icu_context.risk_factors)
    assert has_value(state.therapies.invasive_mechanical_ventilation) is False
