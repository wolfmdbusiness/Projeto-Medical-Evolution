"""Milestone 1.2 cross-cutting behaviors that are not tied to one specific
golden sample: TemporalValue, consultation section state, diagnostic study
procedure/result split, ICU justifications/requirement history, lab value
operators, reference ranges, gas specimen type, medication course tracking,
diagnosis certainty, and the lab temporal-ambiguity guard."""

import pytest

from models.medical_state import (
    Admission,
    Analyte,
    BloodGas,
    CareAction,
    ClinicalField,
    ClinicalState,
    ComparisonOperator,
    ComplementaryExams,
    Consultation,
    ConsultationSectionState,
    ConsultationStatus,
    Diagnosis,
    DiagnosisStatus,
    DiagnosticStudy,
    DiagnosticStudyProcedureStatus,
    DiagnosticStudyResultStatus,
    GasSpecimenType,
    IcuContext,
    IcuJustificationEntry,
    IcuRequirementStatus,
    IcuRequirementStatusEntry,
    LabObservation,
    MedicalState,
    Medication,
    Meta,
    ObservationValue,
    ReferenceRange,
    Source,
    SourceModality,
    SourceType,
    TemporalPeriod,
    TemporalPrecision,
    TemporalValue,
    Therapies,
    ValidationStatus,
)
from rendering.medical_note_renderer import render_medical_note
from rendering.renderability_gate import RenderNotAllowedError
from rendering.text_utils import has_value


def _cf(value, state=ClinicalState.PRESENT, status=ValidationStatus.CONFIRMED):
    return ClinicalField(value=value, clinical_state=state, validation_status=status)


def _tv(raw, normalized=None, precision=TemporalPrecision.DATE, status=ValidationStatus.CONFIRMED):
    return TemporalValue(raw=raw, normalized=normalized or raw, precision=precision, validation_status=status)


def _state(**overrides) -> MedicalState:
    base = dict(meta=Meta(state_id="S-TEST"), patient_ref="P-TEST")
    base.update(overrides)
    return MedicalState(**base)


# --- item 2/3: TemporalValue + invalid dates -------------------------------

def test_temporal_precision_and_period_cover_the_minimum_vocabulary():
    assert {p.value for p in TemporalPrecision} >= {"DATE", "DATE_TIME", "PARTIAL_DATE", "UNKNOWN"}
    assert {p.value for p in TemporalPeriod} >= {"DAY", "NIGHT", "UNSPECIFIED"}


def test_invalid_date_is_preserved_raw_and_never_silently_corrected():
    tv = TemporalValue(
        raw="31/09", normalized=None, precision=TemporalPrecision.PARTIAL_DATE,
        validation_status=ValidationStatus.UNRESOLVED,
    )
    assert tv.raw == "31/09"
    assert tv.normalized is None


def test_invalid_admission_date_blocks_rendering_and_requires_review():
    state = _state(admission=Admission(
        hospital_admission_date=TemporalValue(
            raw="31/09", normalized=None, precision=TemporalPrecision.PARTIAL_DATE,
            validation_status=ValidationStatus.UNRESOLVED,
        ),
    ))
    with pytest.raises(RenderNotAllowedError) as exc_info:
        render_medical_note(state)
    assert any("hospital_admission_date" in r for r in exc_info.value.reasons)
    assert state.admission.hospital_admission_date.raw == "31/09"


# --- item 4: admission datetime with/without time --------------------------

def test_admission_datetime_with_time_is_preserved_in_render():
    state = _state(admission=Admission(
        hospital_admission_date=_tv("2026-09-03T03:34:00", precision=TemporalPrecision.DATE_TIME),
        icu_admission_date=_tv("2026-09-03T03:34:00", precision=TemporalPrecision.DATE_TIME),
    ))
    rendered = render_medical_note(state)
    assert "DATA DE INTERNAÇÃO HOSPITALAR: 03/09/2026 03:34" in rendered


def test_admission_datetime_without_time_never_invents_one():
    state = _state(admission=Admission(hospital_admission_date=_tv("2026-08-30")))
    rendered = render_medical_note(state)
    assert "DATA DE INTERNAÇÃO HOSPITALAR: 30/08/2026" in rendered
    assert "30/08/2026 (" not in rendered


# --- item 6/7: consultation section state -----------------------------------

def test_consultation_not_requested_renders_explicit_text():
    state = _state(consultations_section_state=ConsultationSectionState.NOT_REQUESTED)
    rendered = render_medical_note(state)
    assert "- NÃO SOLICITADO" in rendered


def test_consultation_unknown_with_no_data_falls_back_to_blank():
    state = _state()  # default UNKNOWN, empty consultations
    rendered = render_medical_note(state)
    block = rendered.split("## INTERCONSULTA DE ESPECIALIDADES:", 1)[1].split("## AGUARDO:", 1)[0]
    assert block.strip() == "-"


def test_requested_consultation_without_answer_invents_nothing():
    state = _state(
        consultations_section_state=ConsultationSectionState.PRESENT,
        consultations=[Consultation(
            consultation_id="C1",
            specialty=_cf("UROLOGIA"),
            temporal_value=_tv("2026-09-02"),
            assessment=_cf("SOLICITADA AVALIAÇÃO"),
            status=ConsultationStatus.REQUESTED,
        )],
    )
    rendered = render_medical_note(state)
    assert "> UROLOGIA" in rendered
    assert "02/09: SOLICITADA AVALIAÇÃO" in rendered
    assert "CONDUTAS" not in rendered
    assert "CONCLUSÃO" not in rendered


# --- item 8: conclusions vs recommendations ---------------------------------

def test_conclusions_and_recommendations_are_rendered_distinctly():
    state = _state(
        consultations_section_state=ConsultationSectionState.PRESENT,
        consultations=[Consultation(
            consultation_id="C1",
            specialty=_cf("OFTALMOLOGICA"),
            temporal_value=_tv("2026-09-01"),
            assessment=_cf("AMAUROSE FUGAZ"),
            conclusions=[_cf("EXAME DENTRO DA NORMALIDADE")],
        )],
    )
    rendered = render_medical_note(state)
    assert "CONCLUSÃO: 01) EXAME DENTRO DA NORMALIDADE" in rendered
    assert "CONDUTAS" not in rendered


# --- item 9: grouping by specialty ------------------------------------------

def test_adjacent_consultations_same_specialty_are_grouped_under_one_header():
    def entry(date, assessment):
        return Consultation(
            consultation_id=f"C-{date}",
            specialty=_cf("CIRURGIA VASCULAR"),
            temporal_value=_tv(date),
            assessment=_cf(assessment),
        )

    state = _state(
        consultations_section_state=ConsultationSectionState.PRESENT,
        consultations=[
            entry("2026-08-29", "AVALIACAO INICIAL"),
            entry("2026-08-30", "REAVALIACAO"),
            entry("2026-09-01", "REAVALIACAO 2"),
        ],
    )
    rendered = render_medical_note(state)
    assert rendered.count("> CIRURGIA VASCULAR") == 1
    assert "AVALIACAO INICIAL" in rendered
    assert "REAVALIACAO 2" in rendered


def test_different_specialties_are_never_mixed_under_one_header():
    state = _state(
        consultations_section_state=ConsultationSectionState.PRESENT,
        consultations=[
            Consultation(consultation_id="C1", specialty=_cf("CARDIOLOGIA"), temporal_value=_tv("2026-08-29"), assessment=_cf("A")),
            Consultation(consultation_id="C2", specialty=_cf("NEUROCIRURGIA"), temporal_value=_tv("2026-08-30"), assessment=_cf("B")),
        ],
    )
    rendered = render_medical_note(state)
    assert "> CARDIOLOGIA" in rendered
    assert "> NEUROCIRURGIA" in rendered


# --- item 11: procedure vs result status ------------------------------------

def test_performed_study_with_pending_result_is_not_collapsed_to_one_status():
    study = DiagnosticStudy(
        study_id="ST1", study_name="RM DE COLUNA",
        procedure_status=DiagnosticStudyProcedureStatus.PERFORMED,
        result_status=DiagnosticStudyResultStatus.PENDING,
    )
    state = _state(complementary_exams=ComplementaryExams(diagnostic_studies=[study]))
    rendered = render_medical_note(state)
    assert "REALIZADO, LAUDO PENDENTE" in rendered


def test_ordered_but_not_performed_study_shows_procedure_label():
    study = DiagnosticStudy(study_id="ST1", study_name="HOLTER 24H", procedure_status=DiagnosticStudyProcedureStatus.ORDERED)
    state = _state(complementary_exams=ComplementaryExams(diagnostic_studies=[study]))
    rendered = render_medical_note(state)
    assert "SOLICITADO" in rendered


# --- item 12/13: studies without a date; multiple findings not deduped -----

def test_study_without_date_renders_without_invented_date():
    study = DiagnosticStudy(
        study_id="ST1", study_name="TC DE CRANIO",
        procedure_status=DiagnosticStudyProcedureStatus.PERFORMED,
        result_status=DiagnosticStudyResultStatus.FINAL,
        findings=[_cf("SEM ALTERAÇÕES")],
    )
    state = _state(complementary_exams=ComplementaryExams(diagnostic_studies=[study]))
    rendered = render_medical_note(state)
    assert "- TC DE CRANIO" in rendered
    assert "- 01/01" not in rendered


def test_identical_findings_across_different_studies_are_not_deduplicated():
    def study(sid, name):
        return DiagnosticStudy(
            study_id=sid, study_name=name,
            procedure_status=DiagnosticStudyProcedureStatus.PERFORMED,
            result_status=DiagnosticStudyResultStatus.FINAL,
            findings=[_cf("SEM ALTERAÇÕES")],
        )

    state = _state(complementary_exams=ComplementaryExams(
        diagnostic_studies=[study("ST1", "TC DE CRANIO"), study("ST2", "RM DE CRANIO")],
    ))
    rendered = render_medical_note(state)
    assert rendered.count("SEM ALTERAÇÕES") == 2


# --- item 14/15: ICU justifications list + requirement history -------------

def test_multiple_icu_justifications_render_as_multiple_bullets():
    state = _state(icu_context=IcuContext(explicit_justifications=[
        IcuJustificationEntry(text=_cf("JUSTIFICATIVA 1")),
        IcuJustificationEntry(text=_cf("JUSTIFICATIVA 2")),
    ]))
    rendered = render_medical_note(state)
    assert "- JUSTIFICATIVA 1" in rendered
    assert "- JUSTIFICATIVA 2" in rendered


def test_icu_requirement_status_history_is_append_only_and_not_rendered_yet():
    state = _state(icu_context=IcuContext(requirement_status_history=[
        IcuRequirementStatusEntry(status=IcuRequirementStatus.REQUIRED),
        IcuRequirementStatusEntry(
            status=IcuRequirementStatus.NO_LONGER_REQUIRED,
            text=_cf("AUSÊNCIA DE CRITÉRIOS QUE JUSTIFIQUEM MONITORIZAÇÃO INTENSIVA"),
        ),
    ]))
    history = state.icu_context.requirement_status_history
    assert len(history) == 2
    assert history[0].status == IcuRequirementStatus.REQUIRED
    assert history[1].status == IcuRequirementStatus.NO_LONGER_REQUIRED
    rendered = render_medical_note(state)
    assert "AUSÊNCIA DE CRITÉRIOS" not in rendered


# --- item 16: risk-of-X is not active-X -------------------------------------

def test_risk_factor_never_implies_active_support():
    state = _state(icu_context=IcuContext(risk_factors=["RISK_OF_IOT", "RISK_OF_VASOACTIVE_SUPPORT"]))
    assert state.icu_context.active_supports == []
    assert has_value(state.therapies.invasive_mechanical_ventilation) is False


# --- item 17/18: lab value operator + raw reference range -------------------

def test_lab_value_operator_is_preserved_not_collapsed():
    obs = LabObservation(
        observation_id="LAB-DDIMER",
        analyte=Analyte(canonical_id="DDIMERO", raw_name="D DIMERO"),
        value=ObservationValue(raw_value=">4000", operator=ComparisonOperator.GT, normalized_numeric_value=4000.0, display_value=">4000"),
        reference_range=ReferenceRange(upper=500.0, reference_raw="VR<500"),
    )
    assert obs.value.operator == ComparisonOperator.GT
    assert obs.value.raw_value == ">4000"
    assert obs.value.normalized_numeric_value == 4000.0
    assert obs.reference_range.reference_raw == "VR<500"


# --- item 19: excluded-from-display != deleted from state -------------------

def test_excluded_lab_ids_remain_stored_even_though_hidden_from_display():
    obs = LabObservation(
        observation_id="LAB-VCM", analyte=Analyte(canonical_id="VCM", raw_name="VCM"),
        value=ObservationValue(raw_value="79,5", display_value="79,5"),
    )
    state = _state(complementary_exams=ComplementaryExams(laboratory_observations=[obs]))
    rendered = render_medical_note(state)
    assert "79,5" not in rendered
    assert state.complementary_exams.laboratory_observations[0].analyte.canonical_id == "VCM"


# --- item 20: gas specimen type ---------------------------------------------

def test_gas_specimen_type_is_structured_and_shown_when_known():
    gas = BloodGas(
        gas_id="G1", collection_datetime="2026-08-28T00:00:00", specimen_type=GasSpecimenType.VENOUS,
        observations=[LabObservation(observation_id="G1-PH", analyte=Analyte(canonical_id="PH", raw_name="PH"), value=ObservationValue(raw_value="7,36", display_value="7,36"))],
    )
    state = _state(complementary_exams=ComplementaryExams(blood_gases=[gas]))
    rendered = render_medical_note(state)
    assert "(VENOSA)" in rendered


def test_gas_specimen_type_unknown_shows_no_suffix():
    gas = BloodGas(
        gas_id="G1", collection_datetime="2026-08-28T00:00:00",
        observations=[LabObservation(observation_id="G1-PH", analyte=Analyte(canonical_id="PH", raw_name="PH"), value=ObservationValue(raw_value="7,36", display_value="7,36"))],
    )
    state = _state(complementary_exams=ComplementaryExams(blood_gases=[gas]))
    rendered = render_medical_note(state)
    assert "(VENOSA)" not in rendered
    assert "(ARTERIAL)" not in rendered


# --- item 21: external provenance -------------------------------------------

def test_external_source_types_are_supported_conservatively():
    Source(source_id="SRC-EXT-1", source_type=SourceType.EXTERNAL_LAB_REPORT, modality=SourceModality.TEXT)
    Source(source_id="SRC-EXT-2", source_type=SourceType.EXTERNAL_MEDICAL_DOCUMENT)


# --- item 22/23: antibiotic course + anticoagulant classification -----------

def test_antibiotic_documented_therapy_day_renders():
    med = Medication(
        medication_id="MED1", generic_name="CEFTRIAXONE", classifications=["ANTIBIOTIC"],
        documented_therapy_day="D1", started_at=_tv("02/09", normalized="2026-09-02"),
    )
    state = _state(medications=[med])
    rendered = render_medical_note(state)
    assert "CEFTRIAXONE D1: 02/09" in rendered


def test_anticoagulant_never_appears_in_antibiotic_section():
    med = Medication(medication_id="MED2", generic_name="ENOXAPARINA", classifications=["ANTICOAGULANT"], dosage="40MG SC")
    state = _state(medications=[med])
    rendered = render_medical_note(state)
    assert "## ANTIBIOTICOTERAPIA:\n- NÃO SE APLICA" in rendered
    assert "## EM USO DE:\n- ENOXAPARINA [40MG SC]" in rendered


# --- item 24: current medications section -----------------------------------

def test_current_medications_section_shows_available_fields_only():
    med = Medication(
        medication_id="MED3", generic_name="DIPIRONA", presentation="1G AMP C/2ML",
        dosage="1 AMP 6/6H SE DOR OU FEBRE", route="IV",
    )
    state = _state(medications=[med])
    rendered = render_medical_note(state)
    assert "## EM USO DE:" in rendered
    assert "DIPIRONA (1G AMP C/2ML) [1 AMP 6/6H SE DOR OU FEBRE] IV" in rendered


def test_current_medications_section_absent_when_no_active_non_antibiotic_meds():
    state = _state()
    rendered = render_medical_note(state)
    assert "## EM USO DE:" not in rendered


# --- item 26: diagnosis certainty --------------------------------------------

def test_uncertain_diagnosis_preserves_original_uncertain_text():
    dx = Diagnosis(diagnosis_id="DX1", main=_cf("PIELONEFRITE?"), status=DiagnosisStatus.UNCERTAIN)
    state = _state(diagnoses=[dx])
    rendered = render_medical_note(state)
    assert "PIELONEFRITE?" in rendered


# --- item 33: lab temporal ambiguity ----------------------------------------

def test_ambiguity_is_an_explicit_determination_not_an_accident():
    # The "could the latest reading be determined?" answer is a named,
    # independently testable function -- not just an implicit side effect
    # of `_group_latest_by_day` skipping deduplication.
    from rendering.text_utils import analyte_readings_order_is_ambiguous as _analyte_readings_order_is_ambiguous

    timed = LabObservation(
        observation_id="L1", analyte=Analyte(canonical_id="NA", raw_name="NA"),
        value=ObservationValue(raw_value="140", display_value="140"),
        collection_datetime="2026-08-31T13:20:00",
    )
    untimed = LabObservation(
        observation_id="L2", analyte=Analyte(canonical_id="NA", raw_name="NA"),
        value=ObservationValue(raw_value="141", display_value="141"),
        collection_datetime="2026-08-31",
    )
    both_timed = LabObservation(
        observation_id="L3", analyte=Analyte(canonical_id="NA", raw_name="NA"),
        value=ObservationValue(raw_value="142", display_value="142"),
        collection_datetime="2026-08-31T18:00:00",
    )

    assert _analyte_readings_order_is_ambiguous([timed, untimed]) is True
    assert _analyte_readings_order_is_ambiguous([timed, both_timed]) is False
    assert _analyte_readings_order_is_ambiguous([timed]) is False


def test_same_analyte_same_day_without_clear_order_keeps_both_readings():
    obs1 = LabObservation(
        observation_id="L1", analyte=Analyte(canonical_id="NA", raw_name="NA"),
        value=ObservationValue(raw_value="140", display_value="140"),
        collection_datetime="2026-08-31T13:20:00", source_order=1,
    )
    obs2 = LabObservation(
        observation_id="L2", analyte=Analyte(canonical_id="NA", raw_name="NA"),
        value=ObservationValue(raw_value="141", display_value="141"),
        collection_datetime="2026-08-31", source_order=2,
    )
    state = _state(complementary_exams=ComplementaryExams(laboratory_observations=[obs1, obs2]))
    rendered = render_medical_note(state)
    assert "NA 140" in rendered
    assert "NA 141" in rendered


def test_same_analyte_same_day_with_both_timestamps_picks_the_latest():
    obs1 = LabObservation(
        observation_id="L1", analyte=Analyte(canonical_id="K", raw_name="K"),
        value=ObservationValue(raw_value="3,5", display_value="3,5"),
        collection_datetime="2026-08-31T08:00:00",
    )
    obs2 = LabObservation(
        observation_id="L2", analyte=Analyte(canonical_id="K", raw_name="K"),
        value=ObservationValue(raw_value="4,0", display_value="4,0"),
        collection_datetime="2026-08-31T18:00:00",
    )
    state = _state(complementary_exams=ComplementaryExams(laboratory_observations=[obs1, obs2]))
    rendered = render_medical_note(state)
    assert "K 4,0" in rendered
    assert "K 3,5" not in rendered
