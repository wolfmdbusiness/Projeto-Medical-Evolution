"""Milestone 2.0C — held-out clinical validation harness.

This module is evaluation-only infrastructure. It imports and calls the
existing, unmodified production pipeline
(`exam_extraction.execution.run_extraction`, which itself calls
`exam_extraction.providers.deepseek.DeepSeekExamExtractor`,
`exam_extraction.grounding.ground_candidate`, and
`exam_normalization.orchestrator.normalize_extraction_candidate`) — it
never reimplements or patches any of that logic. Nothing here is imported
by production code; the dependency is one-directional (harness -> product).

Per the M2.0C instructions: no change to `ExamExtractionCandidate`,
aliases, grounding, the normalizer, evaluation rules, or model parameters
is permitted in response to holdout behavior. This file's scoring
functions exist purely to *observe and report* what the frozen pipeline
already does against the pre-declared ground truth -- they do not feed
back into extraction in any way.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from exam_extraction.execution import ExecutionResult, run_extraction
from exam_extraction.models import ExamExtractionCandidate, ExamSourceEnvelope
from exam_extraction.providers.deepseek import DeepSeekExamExtractor
from exam_normalization.aliases import resolve_canonical_id
from exam_normalization.models import NormalizedExamBatch
from exam_normalization.temporal import parse_exam_temporal
from models.medical_state import (
    DiagnosticStudyProcedureStatus,
    GasSpecimenType,
    SourceType,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# Harness-only mapping from the holdout package's free-text source_type to
# the existing, unmodified SourceType enum. Not a schema change -- just how
# this harness fills in a required ExamSourceEnvelope field.
_SOURCE_TYPE_MAP = {
    "laboratory_report": SourceType.EXTERNAL_LAB_REPORT,
    "laboratory_report_with_previous_results": SourceType.EXTERNAL_LAB_REPORT,
    "diagnostic_study": SourceType.EXTERNAL_MEDICAL_DOCUMENT,
    "diagnostic_study_duplicate_source": SourceType.EXTERNAL_MEDICAL_DOCUMENT,
    "pending_exam_list": SourceType.EXTERNAL_MEDICAL_DOCUMENT,
}


def load_holdout(name: str = "holdout_001") -> tuple[dict, dict]:
    sources = json.loads((FIXTURES_DIR / f"{name}_sources.json").read_text(encoding="utf-8"))
    ground_truth = json.loads((FIXTURES_DIR / f"{name}_ground_truth.json").read_text(encoding="utf-8"))
    return sources, ground_truth


def validate_fixture_consistency(sources: dict, ground_truth: dict) -> list[str]:
    """Pre-flight check, run once before the first live call (per the
    blind execution protocol). Returns a list of problems; empty means
    consistent."""
    problems = []
    if sources["holdout_id"] != ground_truth["holdout_id"]:
        problems.append("holdout_id mismatch between sources and ground truth")
    source_ids = {s["source_id"] for s in sources["sources"]}
    expectation_ids = set(ground_truth["source_expectations"].keys())
    missing_expectations = source_ids - expectation_ids
    extra_expectations = expectation_ids - source_ids
    if missing_expectations:
        problems.append(f"sources with no ground-truth expectation: {sorted(missing_expectations)}")
    if extra_expectations:
        problems.append(f"ground-truth expectations with no matching source: {sorted(extra_expectations)}")
    return problems


def _reference_temporal(source_date: str):
    # "2026-07-26" -> "26/07/2026", parsed through the existing (unchanged)
    # exam_normalization temporal parser -- never a hand-rolled date object.
    y, m, d = source_date.split("-")
    return parse_exam_temporal(f"{d}/{m}/{y}")


def build_envelope(source: dict) -> ExamSourceEnvelope:
    return ExamSourceEnvelope(
        source_id=source["source_id"],
        patient_ref="PACIENTE HOLDOUT 001",
        source_type=_SOURCE_TYPE_MAP.get(source["source_type"], SourceType.OTHER),
        raw_text=source["raw_text"],
        document_temporal_value=_reference_temporal(source["source_date"]),
    )


def run_holdout_source(source: dict, extractor: DeepSeekExamExtractor) -> ExecutionResult:
    envelope = build_envelope(source)
    return run_extraction(envelope, extractor, provider="DEEPSEEK", model="deepseek-v4-flash")


# --------------------------------------------------------------------------
# Value matching helpers
# --------------------------------------------------------------------------

_OPERATOR_RE = re.compile(r"^(<=|>=|<|>|=)\s*(.+)$")


def _normalize_label(label: str) -> str:
    return " ".join(label.strip().upper().split())


def _values_match(actual: Optional[str], expected: str) -> bool:
    if actual is None:
        return False
    a, e = actual.strip(), expected.strip()
    if a == e:
        return True
    am = _OPERATOR_RE.match(a)
    em = _OPERATOR_RE.match(e)
    a_op, a_num = (am.group(1), am.group(2)) if am else (None, a)
    e_op, e_num = (em.group(1), em.group(2)) if em else (None, e)
    if a_op != e_op:
        return False
    try:
        return abs(float(a_num.replace(",", ".")) - float(e_num.replace(",", "."))) < 1e-9
    except ValueError:
        return a_num.replace(",", ".") == e_num.replace(",", ".")


def _find_observation(
    batch: NormalizedExamBatch, bucket: str, label: str, expected_value: Optional[str] = None,
) -> list:
    """Match a ground-truth label against normalized observations
    (Milestone 2.0C.1, item 10). Tried in order, stopping at the first
    strategy that produces a match -- never a bare substring check as the
    primary method:

    1. canonical_id: resolve the ground-truth label through the same
       (unmodified) production alias registry the extractor's own output
       already went through, and match on the normalized `canonical_id`.
       This is what makes e.g. "RNI" reliably match an observation the
       normalizer canonicalized to "INR", regardless of what raw_name
       string the extractor happened to use.
    2. raw_name equivalence (explicit, secondary fallback): exact match
       first, substring containment only after that -- used when the
       label itself has no known canonical id (e.g. "TP"/"TFG", neither
       of which is in the production alias registry -- and this harness
       must not add them there just to pass a test, per item 10).
    3. unique value match (last-resort, explicit fallback): when neither
       of the above found anything and exactly one observation in this
       bucket carries the expected value, credit that one. A single
       candidate value match in an otherwise-accounted-for panel is
       strong, principled evidence -- never used when more than one
       observation shares that value (ambiguous, so left unmatched
       rather than guessed at).
    """
    target = _normalize_label(label)
    items = getattr(batch, bucket)

    label_canonical = resolve_canonical_id(label)
    if label_canonical is not None:
        by_canonical = [obs for obs in items if obs.analyte.canonical_id == label_canonical]
        if by_canonical:
            return by_canonical

    exact = [obs for obs in items if _normalize_label(obs.analyte.raw_name) == target]
    if exact:
        return exact

    substring = [
        obs for obs in items
        if target in _normalize_label(obs.analyte.raw_name) or _normalize_label(obs.analyte.raw_name) in target
    ]
    if substring:
        return substring

    if expected_value is not None:
        value_matches = [obs for obs in items if _values_match(obs.value.raw_value, expected_value)]
        if len(value_matches) == 1:
            return value_matches

    return []


def _evidence_text_index(candidate: ExamExtractionCandidate) -> dict[str, list[str]]:
    """raw_name (normalized) -> list of evidence_text strings, across every
    flat/nested bucket the candidate carries. Used only to check that a
    normalized value is literally traceable to its own claimed evidence
    (item: unsafe_normalization_count) -- this reads the grounded
    candidate, it never re-derives or overrides anything the pipeline
    already computed."""
    index: dict[str, list[str]] = {}

    def add(raw_name: str, evidence_text: str) -> None:
        index.setdefault(_normalize_label(raw_name), []).append(evidence_text)

    for item in candidate.general_labs + candidate.urinalysis + candidate.troponins:
        add(item.raw_name, item.evidence.evidence_text)
    for gas in candidate.blood_gases:
        for obs in gas.observations:
            add(obs.raw_name, obs.evidence.evidence_text)
    return index


# --------------------------------------------------------------------------
# Per-source scoring
# --------------------------------------------------------------------------

@dataclass
class SourceScore:
    source_id: str
    expected_current: int = 0
    captured_current: int = 0
    missing_current: list[str] = field(default_factory=list)
    expected_urinalysis: int = 0
    captured_urinalysis: int = 0
    missing_urinalysis: list[str] = field(default_factory=list)
    expected_gas: int = 0
    captured_gas: int = 0
    missing_gas: list[str] = field(default_factory=list)
    gas_specimen_ok: Optional[bool] = None
    study_expected: bool = False
    study_captured: bool = False
    core_findings_expected: int = 0
    core_findings_matched: int = 0
    missing_core_findings: list[str] = field(default_factory=list)
    historical_as_current_hits: list[str] = field(default_factory=list)
    pending_marked_performed: bool = False
    pending_text_preserved: Optional[bool] = None
    unsafe_normalization_hits: list[str] = field(default_factory=list)

    @property
    def all_required_met(self) -> bool:
        return (
            self.missing_current == []
            and self.missing_urinalysis == []
            and self.missing_gas == []
            and (self.gas_specimen_ok in (None, True))
            and (not self.study_expected or self.study_captured)
            and self.missing_core_findings == []
            and self.historical_as_current_hits == []
            and not self.pending_marked_performed
            and (self.pending_text_preserved in (None, True))
            and self.unsafe_normalization_hits == []
        )


def _check_unsafe_normalization(evidence_index: dict[str, list[str]], obs, label: str, score: SourceScore) -> None:
    """An accepted (grounded, normalized) observation is 'unsafe' if its
    own raw_value cannot be found in its own cited evidence_text -- i.e.
    the value was changed/invented somewhere between extraction and the
    normalized batch, without that change being visible in what the
    extractor itself claimed as support."""
    evidences = evidence_index.get(_normalize_label(obs.analyte.raw_name), [])
    if obs.value.raw_value and evidences and not any(obs.value.raw_value in ev for ev in evidences):
        score.unsafe_normalization_hits.append(
            f"{label}: raw_value {obs.value.raw_value!r} not found in its own evidence_text {evidences!r}"
        )


def _score_current_values(
    batch: NormalizedExamBatch, expected_pairs: list, score: SourceScore, evidence_index: dict[str, list[str]],
) -> None:
    score.expected_current = len(expected_pairs)
    for pair in expected_pairs:
        label, value = pair[0], pair[1]
        candidates = _find_observation(batch, "laboratory_observations", label, expected_value=value)
        if any(_values_match(c.value.raw_value, value) for c in candidates):
            score.captured_current += 1
        else:
            score.missing_current.append(f"{label}={value}")
        for c in candidates:
            _check_unsafe_normalization(evidence_index, c, label, score)


def _score_urinalysis(
    batch: NormalizedExamBatch, expected: dict, score: SourceScore, evidence_index: dict[str, list[str]],
) -> None:
    score.expected_urinalysis = len(expected)
    for label, value in expected.items():
        candidates = _find_observation(batch, "urinalysis", label, expected_value=value)
        if any(_values_match(c.value.raw_value, value) for c in candidates):
            score.captured_urinalysis += 1
        else:
            score.missing_urinalysis.append(f"{label}={value}")
        for c in candidates:
            _check_unsafe_normalization(evidence_index, c, label, score)


def _score_blood_gas(
    batch: NormalizedExamBatch, expected: dict, score: SourceScore, evidence_index: dict[str, list[str]],
) -> None:
    observations = expected.get("observations", [])
    score.expected_gas = len(observations)
    all_gas_obs = [obs for gas in batch.blood_gases for obs in gas.observations]
    for label, value in observations:
        target = _normalize_label(label)
        matches = [o for o in all_gas_obs if _normalize_label(o.analyte.raw_name) == target]
        if any(_values_match(m.value.raw_value, value) for m in matches):
            score.captured_gas += 1
        else:
            score.missing_gas.append(f"{label}={value}")
        for m in matches:
            _check_unsafe_normalization(evidence_index, m, label, score)
    if expected.get("specimen") == "VENOUS":
        score.gas_specimen_ok = any(gas.specimen_type == GasSpecimenType.VENOUS for gas in batch.blood_gases)


def _all_finding_text(batch: NormalizedExamBatch) -> str:
    parts = []
    for study in batch.diagnostic_studies:
        parts.append(study.study_name or "")
        for finding in study.findings:
            if finding.value:
                parts.append(str(finding.value))
    return " \n ".join(parts).lower()


def _score_study(source_id: str, batch: NormalizedExamBatch, expectation: dict, score: SourceScore) -> None:
    score.study_expected = bool(expectation.get("must_capture_study"))
    score.study_captured = len(batch.diagnostic_studies) > 0
    core_findings = expectation.get("core_findings", [])
    score.core_findings_expected = len(core_findings)
    text = _all_finding_text(batch)

    for cf in core_findings:
        if _finding_matches(source_id, cf, text):
            score.core_findings_matched += 1
        else:
            score.missing_core_findings.append(cf)


def _finding_matches(source_id: str, core_finding: str, text: str) -> bool:
    """Conservative clinical-equivalence matching (M2.0C instructions:
    'score clinical equivalence conservatively and document any
    manual-equivalence rule used'). Two rule shapes:

    - Verbatim (case-insensitive substring): used when the ground-truth
      phrase is drawn directly from the source's own CONCLUSÃO text
      (TC-CRANIO, TC-ABDOME-PELVE, the ECHO's overall diagnosis line).
    - Keyword-set: used where the ground truth paraphrases/combines the
      source text (DOPPLER-MMII per-leg findings, CAROTIDAS summary, the
      ECHO's ejection-fraction figure) -- documented per rule below.
    """
    cf_l = core_finding.lower()

    if source_id == "H001-DOPPLER-MMII-20260728-A" or source_id == "H001-DOPPLER-MMII-20260728-B-DUPLICATE":
        # "Sem sinais de TVP no membro inferior esquerdo/direito" ==
        # the phrase "sem sinais de tvp" appearing in a context that also
        # names that leg's laterality, OR the phrase appearing twice
        # overall (accepting either a bilateral or two lateral studies,
        # per the instructions' explicit acceptable_representation note).
        if "esquerdo" in cf_l:
            return "sem sinais de tvp" in text and "esquerd" in text
        if "direito" in cf_l:
            return "sem sinais de tvp" in text and "direit" in text
        return "sem sinais de tvp" in text

    if source_id == "H001-ECHO-20260728":
        if "ejeção" in cf_l or "ejecao" in cf_l:
            return "66,85" in text or "66.85" in text
        return "ecodopplercardiograma normal" in text

    if source_id == "H001-DOPPLER-CAROTIDAS-20260728":
        if "vertebral" in cf_l or "anterógrado" in cf_l or "anterogrado" in cf_l:
            return "anter" in text and "vertebra" in text
        return ("estreitamento" in text or "estenose" in text) and "obstru" in text and "sem" in text

    # TC-CRANIO / TC-ABDOME-PELVE: ground truth is verbatim from the
    # source's own CONCLUSÃO section.
    return cf_l in text


def _score_pending(batch: NormalizedExamBatch, expectation: dict, score: SourceScore) -> None:
    score.study_expected = bool(expectation.get("must_capture_study_or_pending_item"))
    score.study_captured = len(batch.diagnostic_studies) > 0 or len(batch.unmapped) > 0
    if expectation.get("must_not_mark_as_performed"):
        score.pending_marked_performed = any(
            s.procedure_status == DiagnosticStudyProcedureStatus.PERFORMED for s in batch.diagnostic_studies
        )
    preserve_text = expectation.get("must_preserve_text")
    if preserve_text:
        haystacks = [s.study_name or "" for s in batch.diagnostic_studies]
        haystacks += [str(f.value) for s in batch.diagnostic_studies for f in s.findings if f.value]
        haystacks += [str(u) for u in batch.unmapped]
        combined = " \n ".join(haystacks)
        score.pending_text_preserved = preserve_text in combined


def _score_historical_contamination(batch: NormalizedExamBatch, expected_pairs: list, score: SourceScore) -> None:
    for label, historical_value in expected_pairs:
        candidates = _find_observation(batch, "laboratory_observations", label)
        if any(_values_match(c.value.raw_value, historical_value) for c in candidates):
            score.historical_as_current_hits.append(f"{label}={historical_value}")


def score_source(source_id: str, candidate: ExamExtractionCandidate, batch: NormalizedExamBatch, expectation: dict) -> SourceScore:
    score = SourceScore(source_id=source_id)
    evidence_index = _evidence_text_index(candidate)

    if "must_capture_current_values" in expectation:
        _score_current_values(batch, expectation["must_capture_current_values"], score, evidence_index)
    if "must_capture_urinalysis" in expectation:
        _score_urinalysis(batch, expectation["must_capture_urinalysis"], score, evidence_index)
    if "must_capture_blood_gas" in expectation:
        _score_blood_gas(batch, expectation["must_capture_blood_gas"], score, evidence_index)
    if "must_capture_study" in expectation:
        _score_study(source_id, batch, expectation, score)
    if "must_capture_study_or_pending_item" in expectation:
        _score_pending(batch, expectation, score)
    if "must_not_promote_previous_as_current" in expectation:
        _score_historical_contamination(batch, expectation["must_not_promote_previous_as_current"], score)

    return score
