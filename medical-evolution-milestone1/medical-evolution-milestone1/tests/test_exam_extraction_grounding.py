"""Milestone 2.0B, items 9-15; redesigned in Milestone 2.0C.1 after
HOLDOUT-001 (docs/mod_exames_2_0c_holdout_findings.md) surfaced a
real-world pattern the 10 synthetic snippets never exercised: the same
finding restated verbatim more than once in one document.

Covers: `support_status` (GROUNDED/UNGROUNDED) vs `localization_status`
(UNIQUE/MULTIPLE/UNRESOLVED) as two genuinely distinct questions, offsets
computed locally (never trusted from the extractor), multiple identical
occurrences resolved via `source_order` only when it genuinely
disambiguates, a legitimately-restated single item accepted with all its
spans preserved, hierarchical/scoped grounding for `DiagnosticStudy` ->
`findings`, ungrounded/unresolved items redirected to `unmapped` rather
than reaching MedicalState, and stable occurrence identity (now
span-set-based) that survives the extractor reordering its own output.
"""

from exam_extraction.grounding import ground_candidate
from exam_extraction.models import (
    DiagnosticStudyCandidate,
    DiagnosticStudyFindingCandidate,
    Evidence,
    ExamExtractionCandidate,
    ExamSourceEnvelope,
    GeneralLabCandidate,
    LocalizationStatus,
    SupportStatus,
)
from exam_normalization.occurrence_identity import compute_occurrence_key
from models.medical_state import SourceType


def _ev(text: str) -> Evidence:
    return Evidence(evidence_text=text)


def _envelope(raw_text: str, source_id: str = "SRC-GROUND") -> ExamSourceEnvelope:
    return ExamSourceEnvelope(
        source_id=source_id, patient_ref="PATIENT-GOLDEN-TEST",
        source_type=SourceType.MEDICAL_EVOLUTION, raw_text=raw_text,
    )


# --- basic support vs localization --------------------------------------

def test_evidence_text_present_once_is_grounded_unique_with_correct_offsets():
    raw_text = "31/08: HB 12,0; HT 36,0"
    candidate = ExamExtractionCandidate(
        source_id="SRC-1",
        general_labs=[
            GeneralLabCandidate(raw_name="HB", raw_value="12,0", source_order=1, evidence=_ev("HB 12,0"), source_ref="SRC-1"),
        ],
    )
    grounded, report = ground_candidate(candidate, _envelope(raw_text, "SRC-1"))
    obs = grounded.general_labs[0]
    assert obs.evidence.support_status == SupportStatus.GROUNDED
    assert obs.evidence.localization_status == LocalizationStatus.UNIQUE
    start, end = obs.evidence.char_start, obs.evidence.char_end
    assert raw_text[start:end] == "HB 12,0"
    assert len(obs.evidence.matching_spans) == 1
    assert report.grounded_count == 1
    assert report.ungrounded_count == 0
    assert report.accepted_count == 1
    assert report.localization_unresolved_count == 0


def test_evidence_text_absent_is_ungrounded_and_moved_to_unmapped():
    candidate = ExamExtractionCandidate(
        source_id="SRC-2",
        general_labs=[
            GeneralLabCandidate(raw_name="HB", raw_value="12,0", source_order=1, evidence=_ev("HB 99,9 (não está no texto)"), source_ref="SRC-2"),
        ],
    )
    grounded, report = ground_candidate(candidate, _envelope("31/08: HB 12,0", "SRC-2"))
    assert grounded.general_labs == []  # never silently kept as a clinical fact
    assert len(grounded.unmapped) == 1
    assert grounded.unmapped[0].evidence.support_status == SupportStatus.UNGROUNDED
    assert grounded.unmapped[0].evidence.localization_status is None
    assert report.ungrounded_count == 1
    assert report.accepted_count == 0


def test_offsets_are_computed_locally_never_from_extractor_input():
    # Even if the candidate arrives with char_start/char_end already set
    # (an extractor should never do this, but nothing stops a malformed
    # response from including them), grounding recomputes them itself.
    raw_text = "31/08: HB 12,0"
    ev = Evidence(evidence_text="HB 12,0", char_start=999, char_end=999)
    candidate = ExamExtractionCandidate(
        source_id="SRC-3",
        general_labs=[GeneralLabCandidate(raw_name="HB", raw_value="12,0", source_order=1, evidence=ev, source_ref="SRC-3")],
    )
    grounded, _ = ground_candidate(candidate, _envelope(raw_text, "SRC-3"))
    obs = grounded.general_labs[0]
    assert (obs.evidence.char_start, obs.evidence.char_end) == (7, 14)
    assert raw_text[7:14] == "HB 12,0"


# --- single item, legitimately restated (item 3, 4, 6) -------------------

def test_single_item_with_text_appearing_twice_is_grounded_with_multiple_localization():
    # Only one candidate claims this text, and it occurs twice in the
    # source -- no OTHER item competes for it, so this is real support
    # with multiple legitimate locations, not an identity conflict.
    # Milestone 2.0B blocked this outright (AMBIGUOUS); 2.0C.1 accepts it
    # and preserves every matching span (never silently picks one).
    raw_text = "31/08: NA 140\n01/09: NA 140"
    candidate = ExamExtractionCandidate(
        source_id="SRC-4",
        general_labs=[GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-4")],
    )
    grounded, report = ground_candidate(candidate, _envelope(raw_text, "SRC-4"))
    assert len(grounded.general_labs) == 1
    obs = grounded.general_labs[0]
    assert obs.evidence.support_status == SupportStatus.GROUNDED
    assert obs.evidence.localization_status == LocalizationStatus.MULTIPLE
    assert len(obs.evidence.matching_spans) == 2
    assert report.localization_multiple_count == 1
    assert report.accepted_count == 1
    assert report.localization_unresolved_count == 0


# --- multiple competing items (items 14-15) ------------------------------

def test_two_distinct_occurrences_are_both_grounded_unique_at_different_spans():
    # Two genuinely distinct readings, identical text, different source
    # positions -- source_order resolves them cleanly (item 14).
    raw_text = "31/08 (13:20): NA 140\n01/09: NA 140"
    candidate = ExamExtractionCandidate(
        source_id="SRC-5",
        general_labs=[
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-5"),
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=2, evidence=_ev("NA 140"), source_ref="SRC-5"),
        ],
    )
    grounded, report = ground_candidate(candidate, _envelope(raw_text, "SRC-5"))
    assert len(grounded.general_labs) == 2
    assert all(o.evidence.support_status == SupportStatus.GROUNDED for o in grounded.general_labs)
    assert all(o.evidence.localization_status == LocalizationStatus.UNIQUE for o in grounded.general_labs)
    spans = {(o.evidence.char_start, o.evidence.char_end) for o in grounded.general_labs}
    assert len(spans) == 2  # distinct spans, never collapsed to one
    assert report.accepted_count == 2


def test_count_mismatch_between_items_and_occurrences_is_unresolved_and_blocked():
    # 2 items claim the same text, but it only occurs once in the source
    # -- one physical span cannot be split between two competing items,
    # and there is no way to tell which one it really belongs to.
    raw_text = "31/08: NA 140"
    candidate = ExamExtractionCandidate(
        source_id="SRC-7",
        general_labs=[
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-7"),
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=2, evidence=_ev("NA 140"), source_ref="SRC-7"),
        ],
    )
    grounded, report = ground_candidate(candidate, _envelope(raw_text, "SRC-7"))
    assert grounded.general_labs == []
    assert all(u.evidence.support_status == SupportStatus.GROUNDED for u in grounded.unmapped)
    assert all(u.evidence.localization_status == LocalizationStatus.UNRESOLVED for u in grounded.unmapped)
    assert report.localization_unresolved_count == 2
    assert report.accepted_count == 0
    # Critically: this is GROUNDED (the text is real), never UNGROUNDED --
    # a localization failure is not a hallucination (item 3).
    assert report.ungrounded_count == 0


# --- hierarchical / scoped grounding (item 5) -----------------------------

def _study(name: str, order: int, evidence_text: str, findings: list[tuple[str, str]], source_id: str) -> DiagnosticStudyCandidate:
    return DiagnosticStudyCandidate(
        raw_name=name, source_order=order, evidence=_ev(evidence_text), source_ref=source_id,
        findings=[
            DiagnosticStudyFindingCandidate(raw_text=raw_text, evidence=_ev(finding_evidence))
            for raw_text, finding_evidence in findings
        ],
    )


def test_two_studies_with_the_same_finding_text_each_resolve_uniquely_within_their_own_scope():
    # Real-world pattern from HOLDOUT-001's H001-DOPPLER-MMII source: two
    # separate studies (left leg / right leg), each concluding with the
    # exact same sentence. Globally that sentence occurs twice; scoped to
    # each study's own region (from its header to the next study's
    # header, or the end of the document) it occurs exactly once.
    raw_text = (
        "ECOCOLORDOPPLER VENOSO DO MEMBRO INFERIOR ESQUERDO\n"
        "Veias pérvias e compressíveis.\n"
        "CONCLUSÃO:\n"
        "Sem sinais de TVP\n"
        "\n"
        "ECOCOLORDOPPLER VENOSO DO MEMBRO INFERIOR DIREITO\n"
        "Veias pérvias e compressíveis.\n"
        "CONCLUSÃO:\n"
        "Sem sinais de TVP\n"
    )
    candidate = ExamExtractionCandidate(
        source_id="SRC-DOPPLER",
        diagnostic_studies=[
            _study("ECOCOLORDOPPLER VENOSO DO MEMBRO INFERIOR ESQUERDO", 1,
                   "ECOCOLORDOPPLER VENOSO DO MEMBRO INFERIOR ESQUERDO",
                   [("Sem sinais de TVP", "Sem sinais de TVP")], "SRC-DOPPLER"),
            _study("ECOCOLORDOPPLER VENOSO DO MEMBRO INFERIOR DIREITO", 2,
                   "ECOCOLORDOPPLER VENOSO DO MEMBRO INFERIOR DIREITO",
                   [("Sem sinais de TVP", "Sem sinais de TVP")], "SRC-DOPPLER"),
        ],
    )
    grounded, report = ground_candidate(candidate, _envelope(raw_text, "SRC-DOPPLER"))

    assert len(grounded.diagnostic_studies) == 2
    left, right = grounded.diagnostic_studies
    assert len(left.findings) == 1
    assert len(right.findings) == 1
    assert left.findings[0].evidence.localization_status == LocalizationStatus.UNIQUE
    assert right.findings[0].evidence.localization_status == LocalizationStatus.UNIQUE
    # Each finding's span sits within its own study's own text region:
    # the left finding ends before the right study's header even starts,
    # and the right finding starts after it -- proving the search was
    # scoped per-study, not global.
    assert left.findings[0].evidence.char_end <= right.evidence.char_start
    assert right.findings[0].evidence.char_start >= right.evidence.char_start
    assert report.localization_unresolved_count == 0
    assert report.accepted_count == 4  # 2 studies + 2 findings


def test_body_and_conclusion_repeating_the_same_finding_is_accepted_with_both_spans():
    # Real-world pattern from HOLDOUT-001's H001-TC-ABDOME-PELVE source: a
    # single study whose own RESULTADO section states a finding verbatim,
    # and whose CONCLUSÃO restates the exact same sentence. One study, one
    # finding item, two legitimate spans -- accepted (item 6), never
    # blocked.
    raw_text = (
        "TOMOGRAFIA COMPUTADORIZADA DO ABDOME E PELVE\n"
        "RESULTADO:\n"
        "Microcálculo no grupamento caliciano superior do rim direito, não obstrutivo.\n"
        "CONCLUSÃO:\n"
        "Microcálculo no grupamento caliciano superior do rim direito, não obstrutivo.\n"
    )
    candidate = ExamExtractionCandidate(
        source_id="SRC-TC",
        diagnostic_studies=[
            _study(
                "TOMOGRAFIA COMPUTADORIZADA DO ABDOME E PELVE", 1,
                "TOMOGRAFIA COMPUTADORIZADA DO ABDOME E PELVE",
                [("Microcálculo no grupamento caliciano superior do rim direito, não obstrutivo.",
                  "Microcálculo no grupamento caliciano superior do rim direito, não obstrutivo.")],
                "SRC-TC",
            ),
        ],
    )
    grounded, report = ground_candidate(candidate, _envelope(raw_text, "SRC-TC"))

    assert len(grounded.diagnostic_studies) == 1
    study = grounded.diagnostic_studies[0]
    assert len(study.findings) == 1
    finding_evidence = study.findings[0].evidence
    assert finding_evidence.support_status == SupportStatus.GROUNDED
    assert finding_evidence.localization_status == LocalizationStatus.MULTIPLE
    assert len(finding_evidence.matching_spans) == 2
    assert report.localization_multiple_count == 1
    assert report.localization_unresolved_count == 0


def test_children_are_scoped_by_parent_text_position_not_by_a_source_order_link():
    # Two studies share the exact same header text (a pathological but
    # possible case); resolved via the standard source_order pairing
    # (same mechanism flat buckets already use -- item 6 explicitly wants
    # it preserved). The point of item 5's "never source_order alone" is
    # about the CHILDREN: DiagnosticStudyFindingCandidate has no
    # source_order field at all, so a finding can only ever be attributed
    # to a parent by where it physically sits in the document. Proven
    # here: each finding lands under the study whose scope actually
    # contains it, purely from text position.
    raw_text = "ECODOPPLER\nCONCLUSÃO:\nAchado A\n\nECODOPPLER\nCONCLUSÃO:\nAchado B\n"
    candidate = ExamExtractionCandidate(
        source_id="SRC-DUP-HEADER",
        diagnostic_studies=[
            _study("ECODOPPLER", 1, "ECODOPPLER", [("Achado A", "Achado A")], "SRC-DUP-HEADER"),
            _study("ECODOPPLER", 2, "ECODOPPLER", [("Achado B", "Achado B")], "SRC-DUP-HEADER"),
        ],
    )
    grounded, report = ground_candidate(candidate, _envelope(raw_text, "SRC-DUP-HEADER"))
    assert len(grounded.diagnostic_studies) == 2
    first, second = grounded.diagnostic_studies
    assert [f.raw_text for f in first.findings] == ["Achado A"]
    assert [f.raw_text for f in second.findings] == ["Achado B"]
    assert report.localization_unresolved_count == 0


# --- occurrence_identity module in isolation (item 6) ---------------------

def test_occurrence_key_is_deterministic_and_span_sensitive():
    key_a = compute_occurrence_key("SRC-X", "general_lab", [(10, 17)])
    key_b = compute_occurrence_key("SRC-X", "general_lab", [(10, 17)])
    key_c = compute_occurrence_key("SRC-X", "general_lab", [(20, 27)])
    assert key_a == key_b
    assert key_a != key_c


def test_occurrence_key_for_multi_span_items_is_order_independent():
    key_fwd = compute_occurrence_key("SRC-X", "diagnostic_study_finding", [(10, 17), (40, 47)])
    key_rev = compute_occurrence_key("SRC-X", "diagnostic_study_finding", [(40, 47), (10, 17)])
    assert key_fwd == key_rev


def test_reordering_the_same_two_candidates_yields_the_same_pair_of_spans():
    # Same source, LLM lists the two items in the opposite order -- the
    # resulting spans (and therefore occurrence identity) must be
    # identical regardless of list order (item 15).
    raw_text = "31/08 (13:20): NA 140\n01/09: NA 140"

    forward = ExamExtractionCandidate(
        source_id="SRC-6",
        general_labs=[
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-6"),
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=2, evidence=_ev("NA 140"), source_ref="SRC-6"),
        ],
    )
    reversed_order = ExamExtractionCandidate(
        source_id="SRC-6",
        general_labs=[
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=2, evidence=_ev("NA 140"), source_ref="SRC-6"),
            GeneralLabCandidate(raw_name="NA", raw_value="140", source_order=1, evidence=_ev("NA 140"), source_ref="SRC-6"),
        ],
    )

    envelope = _envelope(raw_text, "SRC-6")
    grounded_fwd, _ = ground_candidate(forward, envelope)
    grounded_rev, _ = ground_candidate(reversed_order, envelope)

    spans_fwd = sorted((o.evidence.char_start, o.evidence.char_end) for o in grounded_fwd.general_labs)
    spans_rev = sorted((o.evidence.char_start, o.evidence.char_end) for o in grounded_rev.general_labs)
    assert spans_fwd == spans_rev

    keys_fwd = {compute_occurrence_key("SRC-6", "general_lab", [(s, e)]) for s, e in spans_fwd}
    keys_rev = {compute_occurrence_key("SRC-6", "general_lab", [(s, e)]) for s, e in spans_rev}
    assert keys_fwd == keys_rev
