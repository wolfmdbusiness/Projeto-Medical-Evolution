import json
from pathlib import Path

from models.medical_state import MedicalState
from rendering.medical_note_renderer import render_medical_note


ROOT = Path(__file__).resolve().parents[1]


def test_golden_001_exact_render():
    state_path = ROOT / "golden_samples" / "golden_001" / "golden_001_state.json"
    expected_path = ROOT / "golden_samples" / "golden_001" / "golden_001_expected.txt"

    state = MedicalState.model_validate(
        json.loads(state_path.read_text(encoding="utf-8"))
    )
    rendered = render_medical_note(state).rstrip() + "\n"
    expected = expected_path.read_text(encoding="utf-8")

    assert rendered == expected


def test_no_empty_controls_section_in_golden_001():
    state_path = ROOT / "golden_samples" / "golden_001" / "golden_001_state.json"
    state = MedicalState.model_validate(
        json.loads(state_path.read_text(encoding="utf-8"))
    )
    rendered = render_medical_note(state)
    assert "## CONTROLES:" not in rendered


def test_antibioticotherapy_fallback():
    state_path = ROOT / "golden_samples" / "golden_001" / "golden_001_state.json"
    state = MedicalState.model_validate(
        json.loads(state_path.read_text(encoding="utf-8"))
    )
    rendered = render_medical_note(state)
    assert "## ANTIBIOTICOTERAPIA:\n- NÃO SE APLICA" in rendered


def test_diagnosis_without_empty_specification_line():
    state_path = ROOT / "golden_samples" / "golden_001" / "golden_001_state.json"
    state = MedicalState.model_validate(
        json.loads(state_path.read_text(encoding="utf-8"))
    )
    rendered = render_medical_note(state)
    block = rendered.split("## HIPÓTESES DIAGNÓSTICAS:", 1)[1].split("## HPMA:", 1)[0]
    assert "01) PROTOCOLO DOR TORACICA" in block
    assert ">>" not in block
