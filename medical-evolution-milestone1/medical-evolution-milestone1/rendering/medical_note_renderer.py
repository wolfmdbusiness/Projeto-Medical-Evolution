from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Optional

from models.medical_state import (
    MedicalState,
    LabObservation,
    DiagnosticStudy,
    MedicationStatus,
)
from templates.uti_hospitalis_v1 import DEFAULT_TEMPLATE, UTIHospitalisV1
from templates.registry import get_template_profile, TemplateProfileMismatchError
from rendering.text_utils import text, has_value, format_date, format_datetime
from rendering.renderability_gate import check_renderable

__all__ = [
    "render_medical_note",
    "TemplateProfileMismatchError",
]


def _resolve_template(state: MedicalState, template: Optional[UTIHospitalisV1]) -> UTIHospitalisV1:
    """Wire state.meta.template_profile_id into the actual template used.

    - explicit `template` + matching/absent requested id -> use it as-is.
    - explicit `template` + mismatched requested id -> fail loudly.
    - no `template` -> resolve the requested id through the registry.
    """
    requested_id = state.meta.template_profile_id
    if template is not None:
        if requested_id is not None and template.template_profile_id != requested_id:
            raise TemplateProfileMismatchError(requested_id, template.template_profile_id)
        return template
    if requested_id is None:
        return DEFAULT_TEMPLATE
    return get_template_profile(requested_id)


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
    # Structured differential (Milestone 1.1, item 7): components live on
    # obs.differential, each with its own raw/display value, in the order
    # they were captured. reference_range is no longer overloaded for this.
    value = _display_observation_value(obs)
    if not obs.differential:
        return f"LC {value}"
    diff_parts = [f"{c.display_name} {c.display_value or c.raw_value}" for c in obs.differential]
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
        dt = format_datetime(items[-1].collection_datetime if items else day)
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
        dt = format_datetime(items[-1].collection_datetime if items else day)
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
        lines.append(f"- {format_datetime(gas.collection_datetime)}: " + "; ".join(parts))
    return lines


def _render_troponins(state: MedicalState, template: UTIHospitalisV1) -> list[str]:
    trops = state.complementary_exams.troponins
    if not trops:
        return []
    lines = [f"> {template.troponin_title}"]
    for obs in sorted(trops, key=lambda x: x.collection_datetime or ""):
        lines.append(f"- {format_datetime(obs.collection_datetime)}: TROPONINA {_display_observation_value(obs)}")
    return lines


def _study_date(study: DiagnosticStudy) -> str:
    value = study.resulted_at or study.performed_at or study.scheduled_at or study.ordered_at
    return format_date(value)


def _study_status_text(study: DiagnosticStudy, template: UTIHospitalisV1) -> str:
    return template.study_status_labels.get(study.status.value, "")


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
                if has_value(finding):
                    lines.append(f"  >> {text(finding)}")
        else:
            status_text = _study_status_text(study, template)
            if status_text:
                lines.append(f"  >> {status_text}")
    return lines


def _render_controls(state: MedicalState, template: UTIHospitalisV1) -> list[str]:
    mapping = [
        (template.control_labels[attr], getattr(state.controls, attr))
        for attr in template.controls_order
    ]
    if not any(has_value(v) for _, v in mapping):
        return []
    lines = [template.controls_title]
    for label, value in mapping:
        if has_value(value):
            lines.append(f"- {label}: {text(value)}")
    return lines


def _render_antibiotics(state: MedicalState, template: UTIHospitalisV1) -> list[str]:
    antibiotics = [
        m for m in state.medications
        if m.status == MedicationStatus.ACTIVE and "ANTIBIOTIC" in {x.upper() for x in m.classifications}
    ]
    lines = [template.antibiotics_title]
    if not antibiotics:
        lines.append(f"- {template.antibiotics_not_applicable_text}")
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
    template: Optional[UTIHospitalisV1] = None,
) -> str:
    template = _resolve_template(state, template)
    check_renderable(state, template)

    lines: list[str] = []

    lines.append(template.main_title)
    lines.append(f"- {template.identification_label}: {text(state.display_identification)}")
    lines.append(
        f"- {template.hospital_admission_label}: "
        f"{format_date(text(state.admission.hospital_admission_date), with_year=True)}"
    )
    lines.append(
        f"- {template.icu_admission_label}: "
        f"{format_date(text(state.admission.icu_admission_date), with_year=True)}"
    )
    lines.append(f"- {template.origin_label}: {text(state.admission.origin)}")
    lines.append("")

    lines.append(template.diagnoses_title)
    visible_diagnoses = [dx for dx in state.diagnoses if dx.status in template.diagnosis_visible_statuses]
    if visible_diagnoses:
        for idx, dx in enumerate(visible_diagnoses, 1):
            lines.append(f"{idx:02d}) {text(dx.main)}")
            if dx.specifications:
                for spec in dx.specifications:
                    if has_value(spec):
                        lines.append(f"  >> {text(spec)}")
    else:
        lines.append("01)")
    lines.append("")

    lines.append(template.hpma_title)
    lines.append(f"- {text(state.hpma.text)}")
    lines.append("")

    lines.append(template.evolution_title)
    if state.evolution_history:
        for ev in state.evolution_history:
            date = format_date(ev.datetime, with_year=True)
            prefix = f"{date} - " if date else ""
            lines.append(f"- {prefix}{text(ev.text)}")
            lines.append("")
        if lines[-1] == "":
            lines.pop()
    else:
        lines.append("- ")
    lines.append("")

    lines.append(template.physical_exam_title)
    for attr in template.physical_exam_order:
        label = template.physical_exam_labels[attr]
        lines.append(f"- {label}: {text(getattr(state.physical_exam, attr))}")
    lines.append("")

    lines.append(template.history_title)
    for attr in template.history_order:
        label = template.history_labels[attr]
        lines.append(f"- {label}: {text(getattr(state.history, attr))}")
    lines.append("")

    lines.extend(_render_antibiotics(state, template))
    lines.append("")

    therapy_entries = []
    if has_value(state.therapies.hemotransfusion):
        therapy_entries.append(f"> {template.hemotransfusion_label}: {text(state.therapies.hemotransfusion)}")
    if has_value(state.therapies.niv):
        therapy_entries.append(f"> {template.niv_label}: {text(state.therapies.niv)}")
    if therapy_entries or template.show_empty_therapies:
        lines.append(template.therapies_title)
        lines.extend(therapy_entries)
        lines.append("")

    control_lines = _render_controls(state, template)
    if control_lines or template.show_empty_controls:
        lines.extend(control_lines if control_lines else [template.controls_title])
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
        lines.append(template.complementary_exams_title)
        for i, section in enumerate(exam_sections):
            lines.extend(section)
            if i != len(exam_sections) - 1:
                lines.append("")
        lines.append("")

    lines.append(template.icu_justification_title)
    lines.append(f"- {text(state.icu_context.explicit_justification)}")
    lines.append("")

    lines.append(template.consultations_title)
    if state.consultations:
        for consultation in state.consultations:
            lines.append(f"> {text(consultation.specialty)}")
            date = format_date(consultation.response_datetime or consultation.request_datetime)
            assessment = text(consultation.assessment)
            prefix = f"- {date}: " if date else "- "
            lines.append(prefix + assessment)
            if consultation.recommendations:
                if len(consultation.recommendations) == 1:
                    lines.append(f"  >> {template.consultations_conduct_label}: 01) {text(consultation.recommendations[0])}")
                else:
                    first = True
                    for idx, recommendation in enumerate(consultation.recommendations, 1):
                        if first:
                            lines.append(f"  >> {template.consultations_conduct_label}: {idx:02d}) {text(recommendation)}")
                            first = False
                        else:
                            lines.append(f"               {idx:02d}) {text(recommendation)}")
    else:
        lines.append("- ")
    lines.append("")

    lines.append(template.pending_title)
    if state.pending:
        labels = [p.label for p in state.pending if p.status.value not in {"COMPLETED", "CANCELLED"}]
        lines.append("- " + "; ".join(labels))
    else:
        lines.append("- ")
    lines.append("")

    lines.append(template.care_actions_title)
    if state.care_actions:
        for action in state.care_actions:
            lines.append(f"- {text(action.description)}")
    else:
        lines.append("- ")

    result = "\n".join(lines).rstrip()

    if template.uppercase:
        result = result.upper()

    return result
