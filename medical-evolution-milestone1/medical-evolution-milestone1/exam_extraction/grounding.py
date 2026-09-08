"""Deterministic evidence grounding (Milestone 2.0B, items 9-14).

Sits between `ExamExtractionCandidate` (whatever produced it — a real LLM,
a fixture, a fake extractor) and `exam_normalization.normalize_extraction_candidate`.
It never talks to a provider and never uses any clinical judgement; it only
answers one question per candidate item: does `evidence.evidence_text`
actually occur in `ExamSourceEnvelope.raw_text`, and if so, exactly where?

The LLM is never the authority on this: `canonical_hint`, `char_start`,
`char_end`, and `grounding_status` on a candidate item are always either
unset (as produced by the extractor) or overwritten here — never trusted
from the extractor's own output.

Only GROUNDED items are eligible to reach normalization as clinical facts.
UNGROUNDED and AMBIGUOUS items are redirected into `unmapped` (item 10) —
preserved for review, never silently promoted and never silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from exam_extraction.models import (
    BloodGasCandidate,
    DiagnosticStudyCandidate,
    ExamExtractionCandidate,
    ExamSourceEnvelope,
    GroundingStatus,
    UnmappedCandidate,
)


def _normalize_for_matching(text: str) -> str:
    """The only normalization applied before matching: line-ending
    unification (item 13). No case folding, no whitespace collapsing, no
    clinical interpretation — evidence matching stays literal and
    conservative on purpose."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


@dataclass(frozen=True)
class _Span:
    start: int
    end: int


def _find_all_occurrences(text: str, needle: str) -> list[_Span]:
    if not needle:
        return []
    spans: list[_Span] = []
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx == -1:
            break
        spans.append(_Span(idx, idx + len(needle)))
        start = idx + len(needle)
    return spans


@dataclass(frozen=True)
class GroundingRecord:
    category: str
    label: str
    status: GroundingStatus
    char_start: Optional[int]
    char_end: Optional[int]


@dataclass(frozen=True)
class GroundingReport:
    records: list[GroundingRecord] = field(default_factory=list)

    @property
    def grounded_count(self) -> int:
        return sum(1 for r in self.records if r.status == GroundingStatus.GROUNDED)

    @property
    def ungrounded_count(self) -> int:
        return sum(1 for r in self.records if r.status == GroundingStatus.UNGROUNDED)

    @property
    def ambiguous_count(self) -> int:
        return sum(1 for r in self.records if r.status == GroundingStatus.AMBIGUOUS)


def _resolve_statuses(
    entries: list[tuple[Any, str, Optional[int]]],
    source_text: str,
) -> dict[Any, tuple[GroundingStatus, Optional[int], Optional[int]]]:
    """Core resolution algorithm (items 9, 14): group candidate items by
    identical `evidence_text`, find every non-overlapping occurrence of
    that text in the source, and resolve each group:

    - 0 occurrences -> UNGROUNDED for every item in the group.
    - 1 occurrence, 1 item -> GROUNDED at that span.
    - 1 occurrence, >1 items -> AMBIGUOUS (one physical span cannot be
      claimed by more than one item).
    - N occurrences, N items, and every item's `source_order` is present
      and distinct -> `source_order` genuinely resolves the mapping:
      sort items by `source_order`, sort occurrences by position, and pair
      them up 1:1. This is what keeps the result stable even if the
      extractor lists the same items in a different order on a re-run
      (item 15): the pairing is keyed by `source_order`, never by list
      position.
    - Anything else (count mismatch, or `source_order` missing/duplicated)
      -> AMBIGUOUS for every item in the group; never a silent guess.
    """
    by_text: dict[str, list[tuple[Any, Optional[int]]]] = {}
    for key, text, order in entries:
        by_text.setdefault(text, []).append((key, order))

    result: dict[Any, tuple[GroundingStatus, Optional[int], Optional[int]]] = {}
    for text, group in by_text.items():
        occurrences = _find_all_occurrences(source_text, text)

        if not occurrences:
            for key, _ in group:
                result[key] = (GroundingStatus.UNGROUNDED, None, None)
            continue

        if len(occurrences) == 1:
            if len(group) == 1:
                key, _ = group[0]
                span = occurrences[0]
                result[key] = (GroundingStatus.GROUNDED, span.start, span.end)
            else:
                for key, _ in group:
                    result[key] = (GroundingStatus.AMBIGUOUS, None, None)
            continue

        orders = [order for _, order in group]
        resolvable = (
            len(group) == len(occurrences)
            and all(o is not None for o in orders)
            and len(set(orders)) == len(orders)
        )
        if resolvable:
            sorted_group = sorted(group, key=lambda ko: ko[1])
            sorted_spans = sorted(occurrences, key=lambda s: s.start)
            for (key, _), span in zip(sorted_group, sorted_spans):
                result[key] = (GroundingStatus.GROUNDED, span.start, span.end)
        else:
            for key, _ in group:
                result[key] = (GroundingStatus.AMBIGUOUS, None, None)

    return result


def _label_of(item: Any) -> str:
    return getattr(item, "raw_name", None) or getattr(item, "raw_text", None) or "(unnamed)"


def _to_unmapped(item: Any, category: str) -> UnmappedCandidate:
    status = item.evidence.grounding_status
    return UnmappedCandidate(
        raw_text=f"[{category}:{status.value}] {_label_of(item)}: {item.evidence.evidence_text}",
        evidence=item.evidence,
        source_ref=item.source_ref,
        source_order=item.source_order,
    )


def _ground_flat_bucket(items: list[Any], category: str, source_text: str):
    entries = [(i, item.evidence.evidence_text, item.source_order) for i, item in enumerate(items)]
    resolutions = _resolve_statuses(entries, source_text)

    kept: list[Any] = []
    excluded: list[UnmappedCandidate] = []
    records: list[GroundingRecord] = []
    for i, item in enumerate(items):
        status, start, end = resolutions[i]
        updated_evidence = item.evidence.model_copy(update={
            "grounding_status": status, "char_start": start, "char_end": end,
        })
        updated_item = item.model_copy(update={"evidence": updated_evidence})
        records.append(GroundingRecord(category, _label_of(item), status, start, end))
        if status == GroundingStatus.GROUNDED:
            kept.append(updated_item)
        else:
            excluded.append(_to_unmapped(updated_item, category))
    return kept, excluded, records


def _ground_blood_gases(gases: list[BloodGasCandidate], source_text: str):
    panel_entries = [(i, gas.evidence.evidence_text, gas.source_order) for i, gas in enumerate(gases)]
    panel_resolutions = _resolve_statuses(panel_entries, source_text)

    kept: list[BloodGasCandidate] = []
    excluded: list[UnmappedCandidate] = []
    records: list[GroundingRecord] = []

    for i, gas in enumerate(gases):
        status, start, end = panel_resolutions[i]
        updated_panel_evidence = gas.evidence.model_copy(update={
            "grounding_status": status, "char_start": start, "char_end": end,
        })
        records.append(GroundingRecord("blood_gas", gas.raw_specimen_type or "(gas panel)", status, start, end))

        if status != GroundingStatus.GROUNDED:
            # The panel's own dateline/specimen claim is not grounded --
            # nothing under it (including otherwise-grounded observations)
            # can be trusted as belonging to a real, located panel.
            updated_gas = gas.model_copy(update={"evidence": updated_panel_evidence})
            excluded.append(_to_unmapped(updated_gas, "blood_gas"))
            continue

        obs_entries = [(j, obs.evidence.evidence_text, obs.source_order) for j, obs in enumerate(gas.observations)]
        obs_resolutions = _resolve_statuses(obs_entries, source_text)
        kept_observations = []
        for j, obs in enumerate(gas.observations):
            ostatus, ostart, oend = obs_resolutions[j]
            updated_obs_evidence = obs.evidence.model_copy(update={
                "grounding_status": ostatus, "char_start": ostart, "char_end": oend,
            })
            updated_obs = obs.model_copy(update={"evidence": updated_obs_evidence})
            records.append(GroundingRecord("blood_gas_observation", _label_of(obs), ostatus, ostart, oend))
            if ostatus == GroundingStatus.GROUNDED:
                kept_observations.append(updated_obs)
            else:
                excluded.append(_to_unmapped(updated_obs, "blood_gas_observation"))

        kept.append(gas.model_copy(update={"evidence": updated_panel_evidence, "observations": kept_observations}))

    return kept, excluded, records


def _ground_diagnostic_studies(studies: list[DiagnosticStudyCandidate], source_text: str):
    entries = [(i, study.evidence.evidence_text, study.source_order) for i, study in enumerate(studies)]
    resolutions = _resolve_statuses(entries, source_text)

    kept: list[DiagnosticStudyCandidate] = []
    excluded: list[UnmappedCandidate] = []
    records: list[GroundingRecord] = []

    for i, study in enumerate(studies):
        status, start, end = resolutions[i]
        updated_evidence = study.evidence.model_copy(update={
            "grounding_status": status, "char_start": start, "char_end": end,
        })
        records.append(GroundingRecord("diagnostic_study", study.raw_name, status, start, end))

        if status != GroundingStatus.GROUNDED:
            updated_study = study.model_copy(update={"evidence": updated_evidence})
            excluded.append(_to_unmapped(updated_study, "diagnostic_study"))
            continue

        # Findings don't carry their own source_order -- a repeated finding
        # text can only ever be resolved when it occurs exactly once, never
        # via ordering, which is the conservative behavior _resolve_statuses
        # already falls back to when order is absent.
        finding_entries = [(j, f.evidence.evidence_text, None) for j, f in enumerate(study.findings)]
        finding_resolutions = _resolve_statuses(finding_entries, source_text)
        kept_findings = []
        for j, finding in enumerate(study.findings):
            fstatus, fstart, fend = finding_resolutions[j]
            updated_finding_evidence = finding.evidence.model_copy(update={
                "grounding_status": fstatus, "char_start": fstart, "char_end": fend,
            })
            updated_finding = finding.model_copy(update={"evidence": updated_finding_evidence})
            records.append(GroundingRecord("diagnostic_study_finding", study.raw_name, fstatus, fstart, fend))
            if fstatus == GroundingStatus.GROUNDED:
                kept_findings.append(updated_finding)
            else:
                # No source_order/source_ref of its own -- traced back to
                # the (already-grounded) parent study's instead.
                excluded.append(UnmappedCandidate(
                    raw_text=(
                        f"[diagnostic_study_finding:{fstatus.value}] "
                        f"{study.raw_name}: {finding.raw_text}"
                    ),
                    evidence=updated_finding_evidence,
                    source_ref=study.source_ref,
                    source_order=study.source_order,
                ))

        kept.append(study.model_copy(update={"evidence": updated_evidence, "findings": kept_findings}))

    return kept, excluded, records


def ground_candidate(
    candidate: ExamExtractionCandidate,
    envelope: ExamSourceEnvelope,
) -> tuple[ExamExtractionCandidate, GroundingReport]:
    """Ground every clinical item in `candidate` against `envelope.raw_text`
    and return a new candidate (GROUNDED items keep their bucket, with
    `evidence.char_start/char_end/grounding_status` filled in;
    UNGROUNDED/AMBIGUOUS items are moved into `unmapped`) plus a full
    `GroundingReport` covering every item, grounded or not, for evaluation
    and audit purposes."""
    source_text = _normalize_for_matching(envelope.raw_text)

    general_labs, excl_labs, rec_labs = _ground_flat_bucket(candidate.general_labs, "general_lab", source_text)
    urinalysis, excl_urine, rec_urine = _ground_flat_bucket(candidate.urinalysis, "urinalysis", source_text)
    troponins, excl_trop, rec_trop = _ground_flat_bucket(candidate.troponins, "troponin", source_text)
    microbiology, excl_micro, rec_micro = _ground_flat_bucket(candidate.microbiology, "microbiology", source_text)
    blood_gases, excl_gas, rec_gas = _ground_blood_gases(candidate.blood_gases, source_text)
    diagnostic_studies, excl_study, rec_study = _ground_diagnostic_studies(candidate.diagnostic_studies, source_text)

    all_excluded = excl_labs + excl_urine + excl_trop + excl_micro + excl_gas + excl_study
    all_records = rec_labs + rec_urine + rec_trop + rec_micro + rec_gas + rec_study

    grounded_candidate = candidate.model_copy(update={
        "general_labs": general_labs,
        "urinalysis": urinalysis,
        "troponins": troponins,
        "microbiology": microbiology,
        "blood_gases": blood_gases,
        "diagnostic_studies": diagnostic_studies,
        "unmapped": candidate.unmapped + all_excluded,
    })
    return grounded_candidate, GroundingReport(records=all_records)
