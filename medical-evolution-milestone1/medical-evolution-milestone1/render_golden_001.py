import json
from pathlib import Path

from models.medical_state import MedicalState
from rendering.medical_note_renderer import render_medical_note


ROOT = Path(__file__).resolve().parent
state_path = ROOT / "golden_samples" / "golden_001" / "golden_001_state.json"

state = MedicalState.model_validate(json.loads(state_path.read_text(encoding="utf-8")))
print(render_medical_note(state))
