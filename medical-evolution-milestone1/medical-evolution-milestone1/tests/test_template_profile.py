import dataclasses

import pytest

from models.medical_state import MedicalState
from rendering.medical_note_renderer import render_medical_note
from templates.registry import get_template_profile, UnknownTemplateProfileError, TemplateProfileMismatchError
from templates.uti_hospitalis_v1 import DEFAULT_TEMPLATE


def test_get_template_profile_resolves_known_id():
    assert get_template_profile("UTI_HOSPITALIS_V1") is DEFAULT_TEMPLATE


def test_get_template_profile_unknown_id_raises():
    with pytest.raises(UnknownTemplateProfileError):
        get_template_profile("PROFILE_QUE_NAO_EXISTE")


def test_state_with_unknown_requested_profile_fails_to_render(golden_state_dict):
    golden_state_dict["meta"]["template_profile_id"] = "PROFILE_QUE_NAO_EXISTE"
    state = MedicalState.model_validate(golden_state_dict)
    with pytest.raises(UnknownTemplateProfileError):
        render_medical_note(state)


def test_explicit_template_incompatible_with_requested_profile_raises(golden_state_dict):
    state = MedicalState.model_validate(golden_state_dict)  # requests UTI_HOSPITALIS_V1
    other_template = dataclasses.replace(DEFAULT_TEMPLATE, template_profile_id="OUTRO_PROFILE")
    with pytest.raises(TemplateProfileMismatchError):
        render_medical_note(state, other_template)


def test_explicit_template_matching_requested_profile_renders(golden_state_dict):
    state = MedicalState.model_validate(golden_state_dict)
    rendered = render_medical_note(state, DEFAULT_TEMPLATE)
    assert "EVOLUÇÃO CLINICA MEDICA ADULTO" in rendered
