import pytest

from models.medical_state import MedicalState
from rendering.medical_note_renderer import render_medical_note
from rendering.renderability_gate import RenderNotAllowedError


def _validate(state_dict: dict) -> MedicalState:
    return MedicalState.model_validate(state_dict)


def test_ready_renders_normally(golden_state_dict):
    state = _validate(golden_state_dict)
    rendered = render_medical_note(state)
    assert "EVOLUÇÃO CLINICA MEDICA ADULTO" in rendered


def test_ready_with_warnings_renders_normally(golden_state_dict):
    golden_state_dict["validation"]["overall_status"] = "READY_WITH_WARNINGS"
    state = _validate(golden_state_dict)
    rendered = render_medical_note(state)
    assert "EVOLUÇÃO CLINICA MEDICA ADULTO" in rendered


def test_processing_blocks_rendering(golden_state_dict):
    golden_state_dict["validation"]["overall_status"] = "PROCESSING"
    state = _validate(golden_state_dict)
    with pytest.raises(RenderNotAllowedError):
        render_medical_note(state)


def test_review_required_blocks_rendering(golden_state_dict):
    golden_state_dict["validation"]["overall_status"] = "REVIEW_REQUIRED"
    state = _validate(golden_state_dict)
    with pytest.raises(RenderNotAllowedError) as exc_info:
        render_medical_note(state)
    assert any("REVIEW_REQUIRED" in reason for reason in exc_info.value.reasons)


def test_failed_blocks_rendering(golden_state_dict):
    golden_state_dict["validation"]["overall_status"] = "FAILED"
    state = _validate(golden_state_dict)
    with pytest.raises(RenderNotAllowedError) as exc_info:
        render_medical_note(state)
    assert any("FAILED" in reason for reason in exc_info.value.reasons)


def test_active_conflict_blocks_rendering_even_if_overall_status_says_ready(golden_state_dict):
    golden_state_dict["validation"]["overall_status"] = "READY"
    golden_state_dict["validation"]["conflicts"] = [
        {"description": "troponina duplicada com valores divergentes"}
    ]
    state = _validate(golden_state_dict)
    with pytest.raises(RenderNotAllowedError) as exc_info:
        render_medical_note(state)
    assert any("conflicts" in reason for reason in exc_info.value.reasons)


def test_active_unresolved_blocks_rendering_even_if_overall_status_says_ready(golden_state_dict):
    golden_state_dict["validation"]["overall_status"] = "READY"
    golden_state_dict["validation"]["unresolved"] = ["origem do paciente ambígua"]
    state = _validate(golden_state_dict)
    with pytest.raises(RenderNotAllowedError) as exc_info:
        render_medical_note(state)
    assert any("unresolved" in reason for reason in exc_info.value.reasons)


def test_resolved_conflict_does_not_block_rendering(golden_state_dict):
    golden_state_dict["validation"]["overall_status"] = "READY"
    golden_state_dict["validation"]["conflicts"] = [
        {"description": "já reconciliado", "status": "RESOLVED"}
    ]
    state = _validate(golden_state_dict)
    render_medical_note(state)  # must not raise


def test_consumed_field_with_conflict_blocks_rendering(golden_state_dict):
    golden_state_dict["display_identification"]["validation_status"] = "CONFLICT"
    state = _validate(golden_state_dict)
    with pytest.raises(RenderNotAllowedError) as exc_info:
        render_medical_note(state)
    assert any("display_identification" in reason for reason in exc_info.value.reasons)


def test_consumed_field_with_unresolved_blocks_rendering(golden_state_dict):
    golden_state_dict["physical_exam"]["general"]["validation_status"] = "UNRESOLVED"
    state = _validate(golden_state_dict)
    with pytest.raises(RenderNotAllowedError) as exc_info:
        render_medical_note(state)
    assert any("physical_exam.general" in reason for reason in exc_info.value.reasons)


def test_missing_negated_not_applicable_never_block_rendering(golden_state_dict):
    # therapies.hemotransfusion is clinical_state=NOT_APPLICABLE /
    # validation_status=MISSING in the golden sample itself, and
    # history.allergies is clinical_state=NEGATED / validation_status=CONFIRMED.
    # Neither combination is an error: they are normal field semantics
    # (item 4), so the gate must never block on them.
    assert golden_state_dict["therapies"]["hemotransfusion"]["clinical_state"] == "NOT_APPLICABLE"
    assert golden_state_dict["therapies"]["hemotransfusion"]["validation_status"] == "MISSING"
    assert golden_state_dict["history"]["allergies"]["clinical_state"] == "NEGATED"
    state = _validate(golden_state_dict)
    render_medical_note(state)  # must not raise
