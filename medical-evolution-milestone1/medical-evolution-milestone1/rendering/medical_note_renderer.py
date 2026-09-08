from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Optional

from models.medical_state import (
    MedicalState,
    LabObservation,
    DiagnosticStudy,
    DiagnosticStudyProcedureStatus,
    MedicationStatus,
    ConsultationSectionState,
    ClinicalField,
    TemporalPeriod,
)
from templates.uti_hospitalis_v1 import DEFAULT_TEMPLATE, UTIHospitalisV1
from templates.registry import get_template_profile, TemplateProfileMismatchError
from rendering.text_utils import (
    text,
    has_value,
    format_date,
    format_datetime,
    format_temporal,
    analyte_readings_order_is_ambiguous,
)
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
    return obs.value.display_value or obs.value.raw_value


def _group_latest_by_day(observations: Iterable[LabObservation]) -> list[tuple[str, list[LabObservation]]]:
    """Group observations by collection day and collapse same-analyte
    duplicates to the single latest value for that day.

    Collapsing to one reading only happens when
    `analyte_readings_order_is_ambiguous` (rendering/text_utils.py) says the
    order is NOT ambiguous (every reading of that analyte on that day
    carries an explicit time-of-day). Otherwise every reading is kept and
    shown — deterministic and honest about the ambiguity rather than
    picking one arbitrarily.
    """
    groups: dict[str, list[LabObservation]] = defaultdict(list)
    for obs in observations:
        day = (obs.collection_datetime or "SEM_DATA")[:10]
        groups[day].append(obs)

    result = []
    for day, items in sorted(groups.items(), key=lambda kv: kv[0]):
        per_analyte: dict[str, list[LabObservation]] = {}
        extras: list[LabObservation] = []
        for obs in items:
            cid = (obs.analyte.canonical_id or obs.analyte.display_name or obs.analyte.raw_name).upper()
            if cid:
                per_analyte.setdefault(cid, []).append(obs)
            else:
                extras.append(obs)

        chosen: list[LabObservation] = []
        for cid, obs_list in per_analyte.items():
            if len(obs_list) == 1:
                chosen.append(obs_list[0])
            elif analyte_readings_order_is_ambiguous(obs_list):
                chosen.extend(
                    sorted(obs_list, key=lambda o: o.source_order if o.source_order is not None else 10_000)
                )
            else:
                chosen.append(max(obs_list, key=lambda o: o.collection_datetime))
        chosen.extend(extras)
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
        prefix = f"- {dt}: " if dt else "- "
        lines.append(prefix + "; ".join(parts))
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
        prefix = f"- {dt}: " if dt else "- "
        lines.append(prefix + "; ".join(parts))
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
        specimen_label = template.gas_specimen_labels.get(gas.specimen_type.value)
        specimen_suffix = f" ({specimen_label})" if specimen_label else ""
        lines.append(f"- {format_datetime(gas.collection_datetime)}{specimen_suffix}: " + "; ".join(parts))
    return lines


def _render_troponins(state: MedicalState, template: UTIHospitalisV1) -> list[str]:
    trops = state.complementary_exams.troponins
    if not trops:
        return []
    lines = [f"> {template.troponin_title}"]
    for obs in sorted(trops, key=lambda x: x.collection_datetime or ""):
        lines.append(f"- {format_datetime(obs.collection_datetime)}: TROPONINA {_display_observation_value(obs)}")
    return lines


def _render_microbiology(state: MedicalState, template: UTIHospitalisV1) -> list[str]:
    # Milestone 1.2, item 10/32: no dedup by name/date — every exam entry
    # (e.g. "ESBL", "ESBL 02", "ESBL 03") is an independent occurrence and
    # is rendered as such. A missing result stays empty; it is never
    # copied from a previous entry.
    exams = state.complementary_exams.microbiology_serology
    if not exams:
        return []
    lines = [f"> {template.microbiology_title}"]
    for exam in exams:
        date = format_date(exam.collection_datetime)
        prefix = f"- {date}: " if date else "- "
        lines.append(f"{prefix}{exam.exam_type}: {text(exam.result)}")
    return lines


def _study_date(study: DiagnosticStudy) -> str:
    value = study.resulted_at or study.performed_at or study.scheduled_at or study.ordered_at
    return format_date(value)


def _study_status_text(study: DiagnosticStudy, template: UTIHospitalisV1) -> str:
    # Milestone 1.2, item 11: procedure_status and result_status are two
    # independent axes. Once the procedure was actually PERFORMED, the
    # displayed text is driven by result_status (e.g. "REALIZADO, LAUDO
    # PENDENTE"); before that, it is driven by procedure_status alone.
    if study.procedure_status == DiagnosticStudyProcedureStatus.PERFORMED:
        return template.study_performed_result_labels.get(study.result_status.value, "")
    return template.study_procedure_status_labels.get(study.procedure_status.value, "")


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
        name = med.generic_name or med.raw_name or "NÃO LEGÍVEL"
        if med.documented_therapy_day:
            # Milestone 1.2, item 22: Dn is whatever the source documented,
            # never computed from started_at here.
            date = format_temporal(med.started_at)
            lines.append(f"- {name} {med.documented_therapy_day}: {date}")
            continue
        bits = [name]
        if med.dosage:
            bits.append(med.dosage)
        if med.route:
            bits.append(med.route)
        lines.append("- " + " ".join(bits))
    return lines


def _render_current_medications(state: MedicalState, template: UTIHospitalisV1) -> list[str]:
    # Milestone 1.2, item 24: derived from medications[], never a second
    # source of truth. Antibiotics are excluded here since they already have
    # their own section (no duplication).
    meds = [
        m for m in state.medications
        if m.status == MedicationStatus.ACTIVE and "ANTIBIOTIC" not in {c.upper() for c in m.classifications}
    ]
    if not meds:
        return []
    meds = sorted(meds, key=lambda m: m.source_order if m.source_order is not None else 10_000)
    lines = [template.current_medications_title]
    for med in meds:
        bits = [med.generic_name or med.raw_name or "NÃO LEGÍVEL"]
        if med.presentation:
            bits.append(f"({med.presentation})")
        if med.dosage:
            bits.append(f"[{med.dosage}]")
        if med.route:
            bits.append(med.route)
        lines.append("- " + " ".join(bits))
    return lines


def _render_numbered_block(label: str, items: list[ClinicalField]) -> list[str]:
    """Shared numbering for consultation conclusions/recommendations.
    Padding is computed from the label itself so alignment stays correct
    regardless of label length (Milestone 1.2, item 8)."""
    if not items:
        return []
    prefix = f"  >> {label}: "
    padding = " " * len(prefix)
    lines = []
    for idx, item in enumerate(items, 1):
        bullet = f"{idx:02d}) {text(item)}"
        lines.append(f"{prefix if idx == 1 else padding}{bullet}")
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
        f"{format_temporal(state.admission.hospital_admission_date, with_year=True, paren_time=False)}"
    )
    lines.append(
        f"- {template.icu_admission_label}: "
        f"{format_temporal(state.admission.icu_admission_date, with_year=True, paren_time=False)}"
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
            date = format_temporal(ev.temporal_value, with_year=True)
            suffix = ""
            period = ev.temporal_value.period
            if template.show_evolution_period_suffix and period != TemporalPeriod.UNSPECIFIED:
                label = template.evolution_period_labels.get(period.value)
                if label:
                    suffix = f" ({label})"
            prefix = f"{date}{suffix} - " if date else ""
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

    current_medication_lines = _render_current_medications(state, template)
    if current_medication_lines:
        lines.extend(current_medication_lines)
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
        _render_microbiology(state, template),
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
    if state.icu_context.explicit_justifications:
        for entry in state.icu_context.explicit_justifications:
            lines.append(f"- {text(entry.text)}")
    else:
        lines.append("- ")
    lines.append("")

    lines.append(template.consultations_title)
    if state.consultations_section_state == ConsultationSectionState.NOT_REQUESTED:
        lines.append(f"- {template.consultations_not_requested_text}")
    elif state.consultations:
        # Milestone 1.2, item 9: group adjacent entries of the same
        # specialty under a single header, preserving source order and
        # never mixing entries from different specialties.
        groups: list[tuple[str, list]] = []
        for consultation in state.consultations:
            specialty_text = text(consultation.specialty)
            if groups and groups[-1][0] == specialty_text:
                groups[-1][1].append(consultation)
            else:
                groups.append((specialty_text, [consultation]))

        for specialty_text, entries in groups:
            lines.append(f"> {specialty_text}")
            for consultation in entries:
                date = format_temporal(consultation.temporal_value)
                assessment = text(consultation.assessment)
                prefix = f"- {date}: " if date else "- "
                lines.append(prefix + assessment)
                lines.extend(_render_numbered_block(template.consultations_conclusion_label, consultation.conclusions))
                lines.extend(_render_numbered_block(template.consultations_conduct_label, consultation.recommendations))
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
