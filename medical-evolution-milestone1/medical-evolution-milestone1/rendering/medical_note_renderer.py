from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Iterable, Optional

from models.medical_state import (
    MedicalState,
    ClinicalField,
    LabObservation,
    DiagnosticStudy,
)
from templates.uti_hospitalis_v1 import DEFAULT_TEMPLATE, UTIHospitalisV1


def _text(field: ClinicalField | None) -> str:
    if field is None or field.value is None:
        return ""
    return str(field.value).strip()


def _has_value(field: ClinicalField | None) -> bool:
    return bool(_text(field))


def _date_display(value: Optional[str], with_year: bool = False) -> str:
    if not value:
        return ""
    raw = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%d/%m/%Y" if with_year else "%d/%m")
        except ValueError:
            pass
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return f"{raw[8:10]}/{raw[5:7]}/{raw[0:4]}" if with_year else f"{raw[8:10]}/{raw[5:7]}"
    return raw


def _date_time_display(value: Optional[str], with_year: bool = False) -> str:
    if not value:
        return ""
    raw = value.strip()
    date_part = _date_display(raw, with_year=with_year)
    if "T" in raw and len(raw) >= 16:
        return f"{date_part} ({raw[11:16]})"
    return date_part


def _display_observation_value(obs: LabObservation) -> str:
    return obs.value.display or obs.value.raw


def _group_latest_by_day(observations: Iterable[LabObservation]) -> list[tuple[str, list[LabObservation]]]:
    groups: dict[str, list[LabObservation]] = defaultdict(list)
    for obs in observations:
        day = (obs.collection_datetime or "SEM_DATA")[:10]
        groups[day].append(obs)

    result = []
    for day, items in sorted(groups.items(), key=lambda kv: kv[0]):
        by_analyte: dict[str, LabObservation] = {}
        extras: list[LabObservation] = []
        for obs in sorted(items, key=lambda x: x.collection_datetime or ""):
            cid = (obs.analyte.canonical_id or obs.analyte.display_name or obs.analyte.raw_name).upper()
            if cid:
                by_analyte[cid] = obs
            else:
                extras.append(obs)
        chosen = list(by_analyte.values()) + extras
        result.append((day, chosen))
    return result


def _sort_observations(observations: list[LabObservation], order: list[str]) -> list[LabObservation]:
    rank = {name: idx for idx, name in enumerate(order)}
    return sorted(
        observations,
        key=lambda obs: (
            rank.get((obs.analyte.canonical_id or "").upper(), 10_000),
            obs.source_order if obs.source_order is not None else 10_000,
        ),
    )


def _render_wbc(obs: LabObservation) -> str:
    # Support optional differential encoded in reference_range["differential"] for MVP Golden Sample.
    value = _display_observation_value(obs)
    diff = (obs.reference_range or {}).get("differential")
    if not diff:
        return f"LC {value}"
    diff_parts = [f"{k} {v}" for k, v in diff.items()]
    return f"LC {value} [{'; '.join(diff_parts)}]"


def _render_general_labs(state: MedicalState, template: UTIHospitalisV1) -> list[str]:
    observations = [
        x for x in state.complementary_exams.laboratory_observations
        if (x.analyte.canonical_id or "").upper() not in template.excluded_lab_ids
    ]
    if not observations:
        return []

    lines = [f"> {template.laboratory_title}"]
    for day, items in _group_latest_by_day(observations):
        items = _sort_observations(items, template.general_lab_order)
        parts = []
        for obs in items:
            cid = (obs.analyte.canonical_id or obs.analyte.display_name or obs.analyte.raw_name).upper()
            if cid == "LC":
                parts.append(_render_wbc(obs))
            else:
                label = obs.analyte.display_name or cid or obs.analyte.raw_name
                parts.append(f"{label} {_display_observation_value(obs)}")
        dt = _date_time_display(items[-1].collection_datetime if items else day)
        lines.append(f"- {dt}: " + "; ".join(parts))
    return lines


def _render_urinalysis(state: MedicalState, template: UTIHospitalisV1) -> list[str]:
    obs = state.complementary_exams.urinalysis
    if not obs:
        return []
    lines = [f"> {template.urinalysis_title}"]
    for day, items in _group_latest_by_day(obs):
        items = _sort_observations(items, template.urine_order)
        parts = []
        for x in items:
            label = x.analyte.display_name or x.analyte.canonical_id or x.analyte.raw_name
            parts.append(f"{label} {_display_observation_value(x)}")
        dt = _date_time_display(items[-1].collection_datetime if items else day)
        lines.append(f"- {dt}: " + "; ".join(parts))
    return lines


def _render_gases(state: MedicalState, template: UTIHospitalisV1) -> list[str]:
    gases = state.complementary_exams.blood_gases
    if not gases:
        return []
    lines = [f"> {template.gasometry_title}"]
    for gas in sorted(gases, key=lambda g: g.collection_datetime or ""):
        items = _sort_observations(gas.observations, template.gas_order)
        parts = []
        for obs in items:
            label = obs.analyte.display_name or obs.analyte.canonical_id or obs.analyte.raw_name
            parts.append(f"{label} {_display_observation_value(obs)}")
        lines.append(f"- {_date_time_display(gas.collection_datetime)}: " + "; ".join(parts))
    return lines


def _render_troponins(state: MedicalState, template: UTIHospitalisV1) -> list[str]:
    trops = state.complementary_exams.troponins
    if not trops:
        return []
    lines = [f"> {template.troponin_title}"]
    for obs in sorted(trops, key=lambda x: x.collection_datetime or ""):
        lines.append(f"- {_date_time_display(obs.collection_datetime)}: TROPONINA {_display_observation_value(obs)}")
    return lines


def _study_date(study: DiagnosticStudy) -> str:
    value = study.resulted_at or study.performed_at or study.scheduled_at or study.ordered_at
    return _date_display(value)


def _study_status_text(study: DiagnosticStudy) -> str:
    if study.status == "ORDERED":
        return "SOLICITADO"
    if study.status == "SCHEDULED":
        return "AGENDADO"
    if study.status == "PENDING":
        return "PENDENTE"
    if study.status == "CANCELLED":
        return "CANCELADO"
    return ""


def _render_studies(state: MedicalState, template: UTIHospitalisV1) -> list[str]:
    studies = state.complementary_exams.diagnostic_studies
    if not studies:
        return []
    lines = [f"> {template.imaging_title}"]
    for study in studies:
        date = _study_date(study)
        prefix = f"- {date}: " if date else "- "
        lines.append(prefix + study.study_name)
        if study.findings:
            for finding in study.findings:
                if _has_value(finding):
                    lines.append(f"  >> {_text(finding)}")
        else:
            status_text = _study_status_text(study)
            if status_text:
                lines.append(f"  >> {status_text}")
    return lines


def _render_controls(state: MedicalState) -> list[str]:
    mapping = [
        ("FC", state.controls.heart_rate),
        ("FR", state.controls.respiratory_rate),
        ("PAS", state.controls.systolic_bp),
        ("PAD", state.controls.diastolic_bp),
        ("PAM", state.controls.mean_arterial_pressure),
        ("SPO2", state.controls.spo2),
        ("TX", state.controls.temperature),
        ("DX", state.controls.glucose),
        ("BALANÇO HIDRICO TOTAL", state.controls.fluid_balance_total),
        ("BALANÇO HIDRICO ULTIMAS 24H", state.controls.fluid_balance_24h),
        ("DIURESE ULTIMAS 24H", state.controls.urine_output_24h),
    ]
    if not any(_has_value(v) for _, v in mapping):
        return []
    lines = ["## CONTROLES:"]
    for label, value in mapping:
        if _has_value(value):
            lines.append(f"- {label}: {_text(value)}")
    return lines


def _render_antibiotics(state: MedicalState) -> list[str]:
    antibiotics = [
        m for m in state.medications
        if m.status == "ACTIVE" and "ANTIBIOTIC" in {x.upper() for x in m.classifications}
    ]
    lines = ["## ANTIBIOTICOTERAPIA:"]
    if not antibiotics:
        lines.append("- NÃO SE APLICA")
        return lines

    antibiotics.sort(key=lambda x: x.source_order if x.source_order is not None else 10_000)
    for med in antibiotics:
        bits = [med.generic_name or med.raw_name or "NÃO LEGÍVEL"]
        if med.dosage:
            bits.append(med.dosage)
        if med.route:
            bits.append(med.route)
        lines.append("- " + " ".join(bits))
    return lines


def render_medical_note(
    state: MedicalState,
    template: UTIHospitalisV1 = DEFAULT_TEMPLATE,
) -> str:
    lines: list[str] = []

    lines.append("## EVOLUÇÃO CLINICA MEDICA ADULTO - UTI HOSPITALIS ##")
    lines.append(f"- IDENTIFICAÇÃO DO PACIENTE: {_text(state.display_identification)}")
    lines.append(f"- DATA DE INTERNAÇÃO HOSPITALAR: {_date_display(_text(state.admission.hospital_admission_date), with_year=True)}")
    lines.append(f"- DATA DE INTERNAÇÃO EM UTI: {_date_display(_text(state.admission.icu_admission_date), with_year=True)}")
    lines.append(f"- ORIGEM DO PACIENTE: {_text(state.admission.origin)}")
    lines.append("")

    lines.append("## HIPÓTESES DIAGNÓSTICAS:")
    if state.diagnoses:
        for idx, dx in enumerate(state.diagnoses, 1):
            lines.append(f"{idx:02d}) {_text(dx.main)}")
            if dx.specifications:
                for spec in dx.specifications:
                    if _has_value(spec):
                        lines.append(f"  >> {_text(spec)}")
    else:
        lines.append("01)")
    lines.append("")

    lines.append("## HPMA:")
    lines.append(f"- {_text(state.hpma.text)}")
    lines.append("")

    lines.append("## EVOLUÇÃO:")
    if state.evolution_history:
        for ev in state.evolution_history:
            date = _date_display(ev.datetime, with_year=True)
            prefix = f"{date} - " if date else ""
            lines.append(f"- {prefix}{_text(ev.text)}")
            lines.append("")
        if lines[-1] == "":
            lines.pop()
    else:
        lines.append("- ")
    lines.append("")

    lines.append("## EXAME FÍSICO:")
    lines.append(f"- GERAL: {_text(state.physical_exam.general)}")
    lines.append(f"- NEURO: {_text(state.physical_exam.neurologic)}")
    lines.append(f"- CARDIOVASCULAR: {_text(state.physical_exam.cardiovascular)}")
    lines.append(f"- RESPIRATORIO: {_text(state.physical_exam.respiratory)}")
    lines.append(f"- ABDOMINAL: {_text(state.physical_exam.abdominal)}")
    lines.append(f"- EXTREMIDADES: {_text(state.physical_exam.extremities)}")
    lines.append("")

    lines.append("## ANTECEDENTES PESSOAIS:")
    lines.append(f"- ALERGIAS: {_text(state.history.allergies)}")
    lines.append(f"- ANTECEDENTES PATOLOGICOS PREGRESSOS: {_text(state.history.past_medical_history)}")
    lines.append(f"- CIRURGIAS PREVIAS: {_text(state.history.previous_surgeries)}")
    lines.append(f"- MEDICAMENTO DE USO CONTINUO: {_text(state.history.chronic_medications)}")
    lines.append(f"- HABITOS E VICIOS: {_text(state.history.habits)}")
    lines.append(f"- HISTORICO FAMILIAR: {_text(state.history.family_history)}")
    lines.append("")

    lines.extend(_render_antibiotics(state))
    lines.append("")

    therapy_entries = []
    if _has_value(state.therapies.hemotransfusion):
        therapy_entries.append(f"> HEMOTRASFUSÃO: {_text(state.therapies.hemotransfusion)}")
    if _has_value(state.therapies.niv):
        therapy_entries.append(f"> VNI: {_text(state.therapies.niv)}")
    if therapy_entries or template.show_empty_therapies:
        lines.append("## TERAPIAS:")
        lines.extend(therapy_entries)
        lines.append("")

    control_lines = _render_controls(state)
    if control_lines or template.show_empty_controls:
        lines.extend(control_lines if control_lines else ["## CONTROLES:"])
        lines.append("")

    exam_sections = []
    for section in (
        _render_general_labs(state, template),
        _render_urinalysis(state, template),
        _render_gases(state, template),
        _render_troponins(state, template),
        _render_studies(state, template),
    ):
        if section:
            exam_sections.append(section)

    if exam_sections or template.show_empty_complementary_exams:
        lines.append("## EXAMES COMPLEMENTARES")
        for i, section in enumerate(exam_sections):
            lines.extend(section)
            if i != len(exam_sections) - 1:
                lines.append("")
        lines.append("")

    lines.append("## JUSTIFICATIVA DE INTERNAÇÃO EM UTI:")
    lines.append(f"- {_text(state.icu_context.explicit_justification)}")
    lines.append("")

    lines.append("## INTERCONSULTA DE ESPECIALIDADES:")
    if state.consultations:
        for consultation in state.consultations:
            lines.append(f"> {_text(consultation.specialty)}")
            date = _date_display(consultation.response_datetime or consultation.request_datetime)
            assessment = _text(consultation.assessment)
            prefix = f"- {date}: " if date else "- "
            lines.append(prefix + assessment)
            if consultation.recommendations:
                if len(consultation.recommendations) == 1:
                    lines.append(f"  >> CONDUTAS: 01) {_text(consultation.recommendations[0])}")
                else:
                    first = True
                    for idx, recommendation in enumerate(consultation.recommendations, 1):
                        if first:
                            lines.append(f"  >> CONDUTAS: {idx:02d}) {_text(recommendation)}")
                            first = False
                        else:
                            lines.append(f"               {idx:02d}) {_text(recommendation)}")
    else:
        lines.append("- ")
    lines.append("")

    lines.append("## AGUARDO:")
    if state.pending:
        labels = [p.label for p in state.pending if p.status not in {"COMPLETED", "CANCELLED"}]
        lines.append("- " + "; ".join(labels))
    else:
        lines.append("- ")
    lines.append("")

    lines.append("## CONDUTA:")
    if state.care_actions:
        for action in state.care_actions:
            lines.append(f"- {_text(action.description)}")
    else:
        lines.append("- ")

    result = "\n".join(lines).rstrip()

    if template.uppercase:
        result = result.upper()

    return result
