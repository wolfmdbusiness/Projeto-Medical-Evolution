"""GOLDEN-008 — SEMANTIC_RENDER_REFERENCE / AUDIT_CASE.

Focus (item 35): an active "EM USO DE" section; venous blood gases; a
"<2,0" BETA HCG that keeps its operator; diagnostic studies without a date
that never get one invented; an ICU requirement that can become
NO_LONGER_REQUIRED without erasing the earlier REQUIRED entry; similar
findings across distinct exams that are not deduplicated. Known audit
findings are documented separately (see
golden_samples/golden_008/golden_008_audit_notes.json).
"""

from models.medical_state import GasSpecimenType, IcuRequirementStatus, MedicalState
from rendering.medical_note_renderer import render_medical_note
from tests.conftest import load_golden_state_number


def _state() -> MedicalState:
    return MedicalState.model_validate(load_golden_state_number("008"))


def test_current_medications_section_is_active():
    state = _state()
    rendered = render_medical_note(state)
    assert "## EM USO DE:" in rendered
    assert "DIPIRONA" in rendered.split("## EM USO DE:", 1)[1].split("## EXAMES", 1)[0]


def test_blood_gases_are_venous():
    state = _state()
    assert all(g.specimen_type == GasSpecimenType.VENOUS for g in state.complementary_exams.blood_gases)
    rendered = render_medical_note(state)
    assert rendered.count("(VENOSA)") == 2


def test_beta_hcg_keeps_its_operator():
    state = _state()
    beta_hcg = next(o for o in state.complementary_exams.laboratory_observations if o.analyte.canonical_id == "BETA_HCG")
    assert beta_hcg.value.raw_value == "<2,0"
    rendered = render_medical_note(state)
    assert "BETA_HCG <2,0" in rendered


def test_studies_without_a_date_never_get_one_invented():
    state = _state()
    eco = next(s for s in state.complementary_exams.diagnostic_studies if s.study_name == "ECO TT")
    assert eco.ordered_at is None and eco.performed_at is None and eco.scheduled_at is None and eco.resulted_at is None
    rendered = render_medical_note(state)
    assert "- ECO TT" in rendered
    assert "- 01/01: ECO TT" not in rendered


def test_icu_requirement_can_become_no_longer_required_without_erasing_history():
    state = _state()
    history = state.icu_context.requirement_status_history
    assert history[0].status == IcuRequirementStatus.REQUIRED
    assert history[-1].status == IcuRequirementStatus.NO_LONGER_REQUIRED
    # The earlier, still-active-sounding formal justification is untouched --
    # this divergence is exactly what docs/audit_findings_v0_1.md records as
    # STALE_DOCUMENTATION for this case, not silently reconciled here.
    assert state.icu_context.explicit_justifications  # still present, unedited


def test_similar_findings_in_distinct_exams_are_not_deduplicated():
    state = _state()
    rendered = render_medical_note(state)
    assert rendered.count("VOLUMOSA MASSA CISTICA EM TOPOGRAFIA ANEXIAL DIREITA") == 2
