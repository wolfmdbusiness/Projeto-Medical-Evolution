from models.medical_state import LabObservation, MedicalState
from rendering.medical_note_renderer import render_medical_note


def test_golden_wbc_differential_renders_expected_format(golden_state_dict):
    state = MedicalState.model_validate(golden_state_dict)
    rendered = render_medical_note(state)
    assert "LC 9090 [SEG% 60,7; EOS% 1,8; BASO% 0,2; LINF T% 30,6; MONO% 6,7]" in rendered
    assert "LC 9480 [SEG% 56,5; EOS% 2,3; BASO% 0,4; LINF T% 32,3; MONO% 8,5]" in rendered


def test_reference_range_no_longer_carries_the_differential(golden_state_dict):
    lc_observations = [
        obs
        for obs in golden_state_dict["complementary_exams"]["laboratory_observations"]
        if obs["analyte"]["canonical_id"] == "LC"
    ]
    assert lc_observations
    for obs in lc_observations:
        assert obs["reference_range"] is None
        assert obs["differential"]


def test_differential_component_preserves_order_raw_and_display_values():
    obs = LabObservation.model_validate({
        "observation_id": "LAB-X",
        "analyte": {"canonical_id": "LC", "raw_name": "LC", "display_name": "LC"},
        "value": {"raw": "9090", "display": "9090"},
        "differential": [
            {"display_name": "SEG%", "raw_value": "60,7"},
            {"display_name": "EOS%", "raw_value": "1,8", "display_value": "1,8 (revisado)"},
        ],
    })
    assert [c.display_name for c in obs.differential] == ["SEG%", "EOS%"]
    assert obs.differential[0].raw_value == "60,7"
    assert obs.differential[0].display_value is None
    assert obs.differential[1].display_value == "1,8 (revisado)"
