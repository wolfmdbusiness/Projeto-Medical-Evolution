"""GOLDEN-004 — SEMANTIC_RENDER_REFERENCE / AUDIT_CASE.

Focus (item 35): a RULED_OUT diagnosis; repeated culture entries preserved
individually; a missing microbiology result stays missing (never copied
from the previous entry); multiple consultations from the same specialty
grouped together. Known audit findings are documented separately (see
golden_samples/golden_004/golden_004_audit_notes.json).
"""

from models.medical_state import DiagnosisStatus, MedicalState
from rendering.medical_note_renderer import render_medical_note
from tests.conftest import load_golden_state_number


def _state() -> MedicalState:
    return MedicalState.model_validate(load_golden_state_number("004"))


def test_tvp_is_ruled_out_and_not_silently_removed():
    state = _state()
    tvp = next(dx for dx in state.diagnoses if "TVP" in dx.main.value)
    assert tvp.status == DiagnosisStatus.RULED_OUT
    rendered = render_medical_note(state)
    # Default template policy shows every status -- RULED_OUT is not hidden
    # without an explicit decision (item 27).
    assert "TVP (DESCARTADO)" in rendered
    # And it is backed by negative studies that are also still present
    # (plus one mention in the vascular surgery consultation text).
    assert rendered.count("SEM SINAIS DE TVP") == 3
    imaging_block = rendered.split("## EXAMES COMPLEMENTARES", 1)[1].split("## JUSTIFICATIVA", 1)[0]
    assert imaging_block.count("SEM SINAIS DE TVP") == 2


def test_repeated_cultures_are_preserved_as_independent_entries():
    state = _state()
    esbl_entries = [e for e in state.complementary_exams.microbiology_serology if e.exam_type.startswith("CULTURA DE VIGILANCIA PARA ESBL")]
    assert len(esbl_entries) == 4
    assert {e.exam_id for e in esbl_entries} == {f"G004-MICRO{i}" for i in range(1, 5)}
    rendered = render_medical_note(state)
    assert rendered.count("RESULTADO NEGATIVO") == 4


def test_missing_microbiology_result_is_never_copied_from_previous_entry():
    state = _state()
    last = next(e for e in state.complementary_exams.microbiology_serology if e.exam_id == "G004-MICRO5")
    assert last.result.value is None
    rendered = render_medical_note(state)
    lines = rendered.splitlines()
    line = next(line for line in lines if "ENTEROCOCCUS" in line)
    assert line.strip().endswith(":")  # empty result, not "RESULTADO NEGATIVO"


def test_adjacent_consultations_same_specialty_are_grouped():
    state = _state()
    vascular = [c for c in state.consultations if c.specialty.value == "CIRURGIA VASCULAR"]
    assert len(vascular) == 3
    rendered = render_medical_note(state)
    assert rendered.count("> CIRURGIA VASCULAR") == 1
    assert "> GINECOLOGIA | OBSTETRICIA" in rendered
    assert "> NEUROCIRURGIA" in rendered
