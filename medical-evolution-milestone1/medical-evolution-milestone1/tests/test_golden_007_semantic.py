"""GOLDEN-007 — SEMANTIC_RENDER_REFERENCE / AUDIT_CASE.

Focus (item 35): external provenance preserved; ">4000" keeps its operator
instead of being collapsed to "4000"; "<500" keeps the raw reference range
text; an anticoagulant never appears as an antibiotic. Known audit
findings are documented separately (see
golden_samples/golden_007/golden_007_audit_notes.json).
"""

from models.medical_state import ComparisonOperator, MedicalState, SourceType
from rendering.medical_note_renderer import render_medical_note
from tests.conftest import load_golden_state_number


def _state() -> MedicalState:
    return MedicalState.model_validate(load_golden_state_number("007"))


def test_external_provenance_is_preserved():
    state = _state()
    external_sources = [s for s in state.provenance.sources if s.source_type == SourceType.EXTERNAL_LAB_REPORT]
    assert external_sources
    ddimer = state.complementary_exams.laboratory_observations[0]
    assert external_sources[0].source_id in ddimer.source_refs


def test_ddimer_operator_is_preserved_not_collapsed():
    state = _state()
    ddimer = state.complementary_exams.laboratory_observations[0]
    assert ddimer.value.raw_value == ">4000"
    assert ddimer.value.operator == ComparisonOperator.GT
    assert ddimer.value.normalized_numeric_value == 4000.0
    rendered = render_medical_note(state)
    assert "DDIMERO >4000" in rendered
    assert "DDIMERO 4000" not in rendered


def test_reference_range_raw_text_is_preserved():
    state = _state()
    ddimer = state.complementary_exams.laboratory_observations[0]
    assert ddimer.reference_range.reference_raw == "VR<500"
    assert ddimer.reference_range.upper == 500.0


def test_anticoagulant_never_appears_as_antibiotic():
    state = _state()
    med = state.medications[0]
    assert med.classifications == ["ANTICOAGULANT"]
    rendered = render_medical_note(state)
    assert "## ANTIBIOTICOTERAPIA:\n- NÃO SE APLICA" in rendered
    assert "ENOXAPARINA" in rendered.split("## EM USO DE:", 1)[1]
