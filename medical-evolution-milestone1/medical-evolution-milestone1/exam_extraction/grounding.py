"""Deterministic evidence grounding (Milestone 2.0B, items 9-14; redesigned
in Milestone 2.0C.1 after HOLDOUT-001 surfaced a real-world pattern the 10
synthetic snippets never exercised: the same finding restated verbatim
more than once in one document — once per side/leg in a bilateral study,
or once in a report's body and again in its conclusion).

Sits between `ExamExtractionCandidate` (whatever produced it — a real LLM,
a fixture, a fake extractor) and `exam_normalization.normalize_extraction_candidate`.
It never talks to a provider and never uses any clinical judgement; it only
answers two genuinely distinct questions per candidate item (item 3):

    support_status:      does `evidence_text` exist, literally, anywhere
                          in the source at all?
    localization_status: given that it exists, can its supporting span(s)
                          be pinned down deterministically?

Milestone 2.0B's single `GroundingStatus.AMBIGUOUS` conflated these two:
a value restated twice in one document (support: yes; localization:
multiple-but-legitimate) was treated identically to two competing items
that could not be told apart (support: yes; localization: genuinely
unresolved) -- both were blocked, and both were reported as if they were
hallucination-adjacent. They are not the same failure, so they are no
longer the same status.

Only items with `support_status=GROUNDED` and `localization_status` in
{UNIQUE, MULTIPLE} are eligible to reach normalization as clinical facts.
UNGROUNDED and localization=UNRESOLVED items are redirected into
`unmapped` (item 7 — the safety gate is unchanged) — preserved for
review, never silently promoted and never silently dropped.

Hierarchical/scoped grounding (item 5): for candidates with a natural
parent (a `DiagnosticStudy` and its `findings`; a `BloodGasCandidate` and
its `observations`), the parent's own span is resolved first, sibling
parents partition the document into non-overlapping regions in document
order, and each parent's children are searched *only* within its own
region. This is what lets two different studies that both literally
contain "Sem sinais de TVP" each resolve their own copy to UNIQUE,
without ever comparing across the wrong study.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from exam_extraction.models import (
    BloodGasCandidate,
    CharSpan,
    DiagnosticStudyCandidate,
    ExamExtractionCandidate,
    ExamSourceEnvelope,
    LocalizationStatus,
    SupportStatus,
    UnmappedCandidate,
)


def _normalize_for_matching(text: str) -> str:
    """The only normalization applied before matching: line-ending
    unification (item 13, Milestone 2.0B). No case folding, no whitespace
    collapsing, no clinical interpretation — evidence matching stays
    literal and conservative on purpose."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


@dataclass(frozen=True)
class _Span:
    start: int
    end: int


def _find_all_occurrences(text: str, needle: str, offset: int = 0) -> list[_Span]:
    """Every non-overlapping literal occurrence of `needle` in `text`,
    with positions shifted by `offset` -- so a scoped (substring) search
    still reports spans in the original document's global coordinates."""
    if not needle:
        return []
    spans: list[_Span] = []
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx == -1:
            break
        spans.append(_Span(offset + idx, offset + idx + len(needle)))
        start = idx + len(needle)
    return spans


@dataclass(frozen=True)
class GroundingRecord:
    category: str
    label: str
    support_status: SupportStatus
    localization_status: Optional[LocalizationStatus]
    spans: tuple[tuple[int, int], ...] = ()

    @property
    def accepted(self) -> bool:
        return self.support_status == SupportStatus.GROUNDED and self.localization_status in (
            LocalizationStatus.UNIQUE, LocalizationStatus.MULTIPLE,
        )


@dataclass(frozen=True)
class GroundingReport:
    records: list[GroundingRecord] = field(default_factory=list)

    @property
    def grounded_count(self) -> int:
        """Items with literal textual support, regardless of whether
        their location could be pinned down (item 3/9 -- this is the
        denominator partner of `ungrounded_count`, not a synonym for
        "accepted")."""
        return sum(1 for r in self.records if r.support_status == SupportStatus.GROUNDED)

    @property
    def ungrounded_count(self) -> int:
        return sum(1 for r in self.records if r.support_status == SupportStatus.UNGROUNDED)

    @property
    def localization_unique_count(self) -> int:
        return sum(1 for r in self.records if r.localization_status == LocalizationStatus.UNIQUE)

    @property
    def localization_multiple_count(self) -> int:
        return sum(1 for r in self.records if r.localization_status == LocalizationStatus.MULTIPLE)

    @property
    def localization_unresolved_count(self) -> int:
        return sum(1 for r in self.records if r.localization_status == LocalizationStatus.UNRESOLVED)

    @property
    def accepted_count(self) -> int:
        """What actually reaches `MedicalState` as a clinical fact."""
        return sum(1 for r in self.records if r.accepted)


@dataclass(frozen=True)
class _Outcome:
    support: SupportStatus
    localization: Optional[LocalizationStatus]
    spans: list[_Span]


def _resolve_group(
    entries: list[tuple[Any, str, Optional[int]]],
    search_text: str,
    offset: int,
) -> dict[Any, _Outcome]:
    """Core resolution algorithm (items 3, 4, 14 — redesigned in 2.0C.1):
    group candidate items by identical `evidence_text`, find every
    non-overlapping occurrence of that text within `search_text` (already
    scoped to the right parent region, or the whole document for
    top-level items), and resolve each group:

    - 0 occurrences -> UNGROUNDED, no localization, for every item.
    - 1 item, N>=1 occurrences -> GROUNDED; localization UNIQUE if N==1
      else MULTIPLE. No competing item, so every occurrence legitimately
      supports this one item (item 6) -- all spans are preserved, none
      silently discarded.
    - >1 items, N occurrences, N == item count, and every item's
      `source_order` is present and distinct -> GROUNDED + UNIQUE for
      each, paired by sorting items by `source_order` and occurrences by
      position. Stable regardless of the extractor's own list order
      (item 15, Milestone 2.0B).
    - Anything else (count mismatch, or `source_order` missing/duplicated
      among competing items) -> GROUNDED + UNRESOLVED for every item in
      the group: the text exists (never mislabeled as hallucination), but
      which item owns which occurrence cannot be determined, so it stays
      blocked (item 7) exactly as Milestone 2.0B's AMBIGUOUS did.
    """
    by_text: dict[str, list[tuple[Any, Optional[int]]]] = {}
    for key, text, order in entries:
        by_text.setdefault(text, []).append((key, order))

    result: dict[Any, _Outcome] = {}
    for text, group in by_text.items():
        occurrences = _find_all_occurrences(search_text, text, offset)

        if not occurrences:
            for key, _ in group:
                result[key] = _Outcome(SupportStatus.UNGROUNDED, None, [])
            continue

        if len(group) == 1:
            key, _ = group[0]
            localization = LocalizationStatus.UNIQUE if len(occurrences) == 1 else LocalizationStatus.MULTIPLE
            result[key] = _Outcome(SupportStatus.GROUNDED, localization, list(occurrences))
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
                result[key] = _Outcome(SupportStatus.GROUNDED, LocalizationStatus.UNIQUE, [span])
        else:
            for key, _ in group:
                result[key] = _Outcome(SupportStatus.GROUNDED, LocalizationStatus.UNRESOLVED, list(occurrences))

    return result


def _label_of(item: Any) -> str:
    return getattr(item, "raw_name", None) or getattr(item, "raw_text", None) or "(unnamed)"


def _apply_outcome(evidence, outcome: _Outcome):
    spans = [CharSpan(start=s.start, end=s.end) for s in outcome.spans]
    primary = spans[0] if spans else None
    return evidence.model_copy(update={
        "support_status": outcome.support,
        "localization_status": outcome.localization,
        "matching_spans": spans,
        "char_start": primary.start if primary else None,
        "char_end": primary.end if primary else None,
    })


def _to_unmapped(item: Any, category: str) -> UnmappedCandidate:
    ev = item.evidence
    tag = f"{ev.support_status.value}/{ev.localization_status.value if ev.localization_status else 'NONE'}"
    return UnmappedCandidate(
        raw_text=f"[{category}:{tag}] {_label_of(item)}: {ev.evidence_text}",
        evidence=ev,
        source_ref=item.source_ref,
        source_order=item.source_order,
    )


def _record_of(category: str, label: str, outcome: _Outcome) -> GroundingRecord:
    return GroundingRecord(
        category=category, label=label, support_status=outcome.support,
        localization_status=outcome.localization,
        spans=tuple((s.start, s.end) for s in outcome.spans),
    )


def _ground_flat_bucket(items: list[Any], category: str, source_text: str):
    entries = [(i, item.evidence.evidence_text, item.source_order) for i, item in enumerate(items)]
    resolutions = _resolve_group(entries, source_text, offset=0)

    kept: list[Any] = []
    excluded: list[UnmappedCandidate] = []
    records: list[GroundingRecord] = []
    for i, item in enumerate(items):
        outcome = resolutions[i]
        updated_evidence = _apply_outcome(item.evidence, outcome)
        updated_item = item.model_copy(update={"evidence": updated_evidence})
        records.append(_record_of(category, _label_of(item), outcome))
        if outcome.support == SupportStatus.GROUNDED and outcome.localization in (
            LocalizationStatus.UNIQUE, LocalizationStatus.MULTIPLE,
        ):
            kept.append(updated_item)
        else:
            excluded.append(_to_unmapped(updated_item, category))
    return kept, excluded, records


def _parent_scopes(anchors: list[tuple[int, _Span]], document_length: int) -> dict[int, tuple[int, int]]:
    """Given (item_index, anchor_span) pairs for a set of sibling parents
    (already resolved, GROUNDED, non-UNRESOLVED), partition the document
    into one non-overlapping region per parent, in document order: from
    this parent's own anchor start up to the next parent's anchor start
    (or the end of the document for the last one). This is what makes
    "Sem sinais de TVP" inside the left-leg study's own conclusion
    unreachable from the right-leg study's child search, and vice versa
    (item 5) -- entirely from document position, never from
    `source_order` alone (item 5's explicit prohibition)."""
    ordered = sorted(anchors, key=lambda pair: pair[1].start)
    scopes: dict[int, tuple[int, int]] = {}
    for i, (item_index, anchor) in enumerate(ordered):
        end = ordered[i + 1][1].start if i + 1 < len(ordered) else document_length
        scopes[item_index] = (anchor.start, end)
    return scopes


def _ground_blood_gases(gases: list[BloodGasCandidate], source_text: str):
    panel_entries = [(i, gas.evidence.evidence_text, gas.source_order) for i, gas in enumerate(gases)]
    panel_resolutions = _resolve_group(panel_entries, source_text, offset=0)

    kept: list[BloodGasCandidate] = []
    excluded: list[UnmappedCandidate] = []
    records: list[GroundingRecord] = []

    # item 5: scope each panel's observations to its own region of the
    # document, bounded by sibling panels, before searching for them.
    anchors = [
        (i, outcome.spans[0])
        for i, gas in enumerate(gases)
        if (outcome := panel_resolutions[i]).support == SupportStatus.GROUNDED
        and outcome.localization in (LocalizationStatus.UNIQUE, LocalizationStatus.MULTIPLE)
    ]
    scopes = _parent_scopes(anchors, len(source_text))

    for i, gas in enumerate(gases):
        outcome = panel_resolutions[i]
        updated_panel_evidence = _apply_outcome(gas.evidence, outcome)
        records.append(_record_of("blood_gas", gas.raw_specimen_type or "(gas panel)", outcome))

        if not (outcome.support == SupportStatus.GROUNDED and outcome.localization in (
            LocalizationStatus.UNIQUE, LocalizationStatus.MULTIPLE,
        )):
            # The panel's own dateline/specimen claim is not accepted --
            # nothing under it (including otherwise-groundable
            # observations) can be trusted as belonging to a real,
            # located panel.
            updated_gas = gas.model_copy(update={"evidence": updated_panel_evidence})
            excluded.append(_to_unmapped(updated_gas, "blood_gas"))
            continue

        scope_start, scope_end = scopes[i]
        obs_entries = [(j, obs.evidence.evidence_text, obs.source_order) for j, obs in enumerate(gas.observations)]
        obs_resolutions = _resolve_group(obs_entries, source_text[scope_start:scope_end], offset=scope_start)
        kept_observations = []
        for j, obs in enumerate(gas.observations):
            oc = obs_resolutions[j]
            updated_obs_evidence = _apply_outcome(obs.evidence, oc)
            updated_obs = obs.model_copy(update={"evidence": updated_obs_evidence})
            records.append(_record_of("blood_gas_observation", _label_of(obs), oc))
            if oc.support == SupportStatus.GROUNDED and oc.localization in (
                LocalizationStatus.UNIQUE, LocalizationStatus.MULTIPLE,
            ):
                kept_observations.append(updated_obs)
            else:
                excluded.append(_to_unmapped(updated_obs, "blood_gas_observation"))

        kept.append(gas.model_copy(update={"evidence": updated_panel_evidence, "observations": kept_observations}))

    return kept, excluded, records


def _ground_diagnostic_studies(studies: list[DiagnosticStudyCandidate], source_text: str):
    entries = [(i, study.evidence.evidence_text, study.source_order) for i, study in enumerate(studies)]
    resolutions = _resolve_group(entries, source_text, offset=0)

    kept: list[DiagnosticStudyCandidate] = []
    excluded: list[UnmappedCandidate] = []
    records: list[GroundingRecord] = []

    # item 5: scope each study's findings to its own region of the
    # document (from its own header to the next study's header, or the
    # end of the document) before searching for them. This is what lets
    # two different studies that both literally contain "Sem sinais de
    # TVP" each resolve their own copy to UNIQUE.
    anchors = [
        (i, outcome.spans[0])
        for i, study in enumerate(studies)
        if (outcome := resolutions[i]).support == SupportStatus.GROUNDED
        and outcome.localization in (LocalizationStatus.UNIQUE, LocalizationStatus.MULTIPLE)
    ]
    scopes = _parent_scopes(anchors, len(source_text))

    for i, study in enumerate(studies):
        outcome = resolutions[i]
        updated_evidence = _apply_outcome(study.evidence, outcome)
        records.append(_record_of("diagnostic_study", study.raw_name, outcome))

        if not (outcome.support == SupportStatus.GROUNDED and outcome.localization in (
            LocalizationStatus.UNIQUE, LocalizationStatus.MULTIPLE,
        )):
            updated_study = study.model_copy(update={"evidence": updated_evidence})
            excluded.append(_to_unmapped(updated_study, "diagnostic_study"))
            continue

        scope_start, scope_end = scopes[i]
        # Findings don't carry their own source_order -- a repeated
        # finding text within this study's own scope can only ever be
        # resolved via ordering when the study itself supplies it, which
        # it doesn't; _resolve_group's single-item/multiple-occurrence
        # path (item 6) is what accepts a genuinely restated finding
        # (e.g. body + conclusion) as one item with multiple spans.
        finding_entries = [(j, f.evidence.evidence_text, None) for j, f in enumerate(study.findings)]
        finding_resolutions = _resolve_group(finding_entries, source_text[scope_start:scope_end], offset=scope_start)
        kept_findings = []
        for j, finding in enumerate(study.findings):
            fc = finding_resolutions[j]
            updated_finding_evidence = _apply_outcome(finding.evidence, fc)
            updated_finding = finding.model_copy(update={"evidence": updated_finding_evidence})
            records.append(_record_of("diagnostic_study_finding", study.raw_name, fc))
            if fc.support == SupportStatus.GROUNDED and fc.localization in (
                LocalizationStatus.UNIQUE, LocalizationStatus.MULTIPLE,
            ):
                kept_findings.append(updated_finding)
            else:
                # No source_order/source_ref of its own -- traced back to
                # the (already-accepted) parent study's instead.
                excluded.append(UnmappedCandidate(
                    raw_text=(
                        f"[diagnostic_study_finding:{fc.support.value}/"
                        f"{fc.localization.value if fc.localization else 'NONE'}] "
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
    and return a new candidate (accepted items -- `support_status=GROUNDED`
    with `localization_status` UNIQUE or MULTIPLE -- keep their bucket,
    with `evidence.matching_spans`/`char_start`/`char_end` filled in;
    UNGROUNDED or localization=UNRESOLVED items are moved into `unmapped`)
    plus a full `GroundingReport` covering every item, accepted or not,
    for evaluation and audit purposes."""
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
