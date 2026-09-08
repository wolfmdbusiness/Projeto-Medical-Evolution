import copy
import dataclasses

from models.medical_state import MedicalState, DiagnosisStatus
from rendering.medical_note_renderer import render_medical_note
from templates.uti_hospitalis_v1 import DEFAULT_TEMPLATE


def _state_with_diagnosis_status(golden_state_dict: dict, status: str) -> MedicalState:
    data = copy.deepcopy(golden_state_dict)
    data["diagnoses"][0]["status"] = status
    return MedicalState.model_validate(data)


def _diagnoses_block(rendered: str) -> str:
    return rendered.split("## HIPÓTESES DIAGNÓSTICAS:", 1)[1].split("## HPMA:", 1)[0]


def test_active_diagnosis_renders_by_default(golden_state_dict):
    state = _state_with_diagnosis_status(golden_state_dict, "ACTIVE")
    rendered = render_medical_note(state)
    assert "01) PROTOCOLO DOR TORACICA" in _diagnoses_block(rendered)


def test_resolved_diagnosis_renders_with_conservative_default(golden_state_dict):
    # Default policy shows every status, preserving Milestone 1 behaviour.
    state = _state_with_diagnosis_status(golden_state_dict, "RESOLVED")
    rendered = render_medical_note(state)
    assert "01) PROTOCOLO DOR TORACICA" in _diagnoses_block(rendered)


def test_ruled_out_diagnosis_renders_with_conservative_default(golden_state_dict):
    state = _state_with_diagnosis_status(golden_state_dict, "RULED_OUT")
    rendered = render_medical_note(state)
    assert "01) PROTOCOLO DOR TORACICA" in _diagnoses_block(rendered)


def test_ruled_out_diagnosis_can_be_excluded_via_template_policy(golden_state_dict):
    state = _state_with_diagnosis_status(golden_state_dict, "RULED_OUT")
    restrictive_template = dataclasses.replace(
        DEFAULT_TEMPLATE,
        diagnosis_visible_statuses=frozenset({DiagnosisStatus.ACTIVE}),
    )
    rendered = render_medical_note(state, restrictive_template)
    block = _diagnoses_block(rendered)
    assert "PROTOCOLO DOR TORACICA" not in block
    assert "01)" in block
