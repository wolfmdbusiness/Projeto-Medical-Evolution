"""GOLDEN-005 — SEMANTIC_RENDER_REFERENCE / AUDIT_CASE.

Focus (item 35): consultation conclusions (distinct from recommendations);
a procedure that was performed with its report still pending; multiple ICU
justifications; VCM/HCM stored even though the template hides them from
display. Known audit findings are documented separately (see
golden_samples/golden_005/golden_005_audit_notes.json).
"""

from models.medical_state import DiagnosticStudyProcedureStatus, DiagnosticStudyResultStatus, MedicalState
from rendering.medical_note_renderer import render_medical_note
from tests.conftest import load_golden_state_number


def _state() -> MedicalState:
    return MedicalState.model_validate(load_golden_state_number("005"))


def test_consultation_conclusion_is_rendered_distinctly_from_recommendation():
    state = _state()
    consultation = state.consultations[0]
    assert consultation.conclusions[0].value == "EXAME DENTRO DA NORMALIDADE AO."
    assert consultation.recommendations == []
    rendered = render_medical_note(state)
    assert "CONCLUSÃO: 01) EXAME DENTRO DA NORMALIDADE AO." in rendered
    assert "CONDUTAS" not in rendered


def test_procedure_performed_with_result_pending():
    state = _state()
    study = next(s for s in state.complementary_exams.diagnostic_studies if "ANGIORM" in s.study_name)
    assert study.procedure_status == DiagnosticStudyProcedureStatus.PERFORMED
    assert study.result_status == DiagnosticStudyResultStatus.PENDING
    rendered = render_medical_note(state)
    assert "REALIZADO, LAUDO PENDENTE" in rendered


def test_multiple_icu_justifications_are_all_present():
    state = _state()
    assert len(state.icu_context.explicit_justifications) == 2
    rendered = render_medical_note(state)
    justification_block = rendered.split("## JUSTIFICATIVA DE INTERNAÇÃO EM UTI:", 1)[1].split("## INTERCONSULTA", 1)[0]
    assert justification_block.count("- ") == 2


def test_vcm_hcm_are_stored_even_though_hidden_from_display():
    state = _state()
    canonical_ids = {obs.analyte.canonical_id for obs in state.complementary_exams.laboratory_observations}
    assert {"VCM", "HCM"} <= canonical_ids
    rendered = render_medical_note(state)
    assert "VCM" not in rendered
    assert "HCM" not in rendered
