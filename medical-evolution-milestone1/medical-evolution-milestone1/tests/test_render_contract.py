import copy

from models.medical_state import MedicalState
from rendering.medical_note_renderer import render_medical_note


def test_intentionally_unrendered_fields_do_not_change_output_or_leak(golden_state_dict):
    baseline_state = MedicalState.model_validate(copy.deepcopy(golden_state_dict))
    baseline_rendered = render_medical_note(baseline_state)

    augmented = copy.deepcopy(golden_state_dict)

    augmented["clinical_events"] = [{
        "event_id": "EVT-001",
        "event_type": "ARRHYTHMIA",
        "description": {
            "value": "EVENTO_DE_TESTE_NAO_DEVE_APARECER",
            "clinical_state": "PRESENT",
            "validation_status": "CONFIRMED",
        },
    }]

    augmented["icu_context"]["active_supports"] = ["VASOPRESSOR_DE_TESTE"]
    augmented["icu_context"]["monitoring_requirements"].append("ARRHYTHMIA_WATCH_DE_TESTE")
    augmented["icu_context"]["instabilities"] = ["HEMODYNAMIC_DE_TESTE"]
    augmented["icu_context"]["risk_factors"] = ["BLEEDING_DE_TESTE"]

    augmented["therapies"]["invasive_mechanical_ventilation"] = {
        "value": "MODO_VCV_DE_TESTE",
        "clinical_state": "PRESENT",
        "validation_status": "CONFIRMED",
    }
    augmented["therapies"]["renal_replacement_therapy"] = {
        "value": "HEMODIALISE_INTERMITENTE_DE_TESTE",
        "clinical_state": "PRESENT",
        "validation_status": "CONFIRMED",
    }

    augmented["complementary_exams"]["microbiology_serology"] = [{
        "exam_id": "MICRO-001",
        "exam_type": "HEMOCULTURA",
        "result": {
            "value": "RESULTADO_DE_MICRO_NAO_DEVE_APARECER",
            "clinical_state": "PRESENT",
            "validation_status": "CONFIRMED",
        },
    }]

    augmented_state = MedicalState.model_validate(augmented)
    augmented_rendered = render_medical_note(augmented_state)

    assert augmented_rendered == baseline_rendered

    for leaked_text in (
        "EVENTO_DE_TESTE_NAO_DEVE_APARECER",
        "VASOPRESSOR_DE_TESTE",
        "HEMODYNAMIC_DE_TESTE",
        "BLEEDING_DE_TESTE",
        "MODO_VCV_DE_TESTE",
        "HEMODIALISE_INTERMITENTE_DE_TESTE",
        "RESULTADO_DE_MICRO_NAO_DEVE_APARECER",
    ):
        assert leaked_text not in augmented_rendered
