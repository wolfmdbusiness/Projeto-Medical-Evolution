import pytest
from pydantic import ValidationError

from models.medical_state import MedicalState


def test_unknown_top_level_field_is_rejected(golden_state_dict):
    golden_state_dict["campo_inexistente"] = "valor"
    with pytest.raises(ValidationError):
        MedicalState.model_validate(golden_state_dict)


def test_unknown_nested_field_is_rejected(golden_state_dict):
    golden_state_dict["display_identification"]["campo_extra_digitado_errado"] = 123
    with pytest.raises(ValidationError):
        MedicalState.model_validate(golden_state_dict)


def test_invalid_enum_value_is_rejected(golden_state_dict):
    golden_state_dict["diagnoses"][0]["status"] = "STATUS_QUE_NAO_EXISTE"
    with pytest.raises(ValidationError):
        MedicalState.model_validate(golden_state_dict)


def test_invalid_global_status_is_rejected(golden_state_dict):
    golden_state_dict["validation"]["overall_status"] = "TOTALMENTE_INVENTADO"
    with pytest.raises(ValidationError):
        MedicalState.model_validate(golden_state_dict)


def test_valid_golden_state_still_validates(golden_state_dict):
    # Guards against the strict-model migration being over-strict and
    # rejecting the very data it must keep accepting.
    MedicalState.model_validate(golden_state_dict)
