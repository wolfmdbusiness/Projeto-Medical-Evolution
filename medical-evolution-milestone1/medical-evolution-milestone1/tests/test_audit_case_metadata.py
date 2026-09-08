"""Milestone 1.2, item 36: AUDIT_CASE metadata for G003/G004/G005/G007/G008.

This only proves the metadata is structured and machine-readable so a
future auditor can be tested against it -- it does NOT implement any
auditing logic itself (item 36 explicitly defers that)."""

import json

import pytest

from tests.conftest import ROOT

VALID_CATEGORIES = {"CONTRADICTED", "POTENTIAL_TEMPORAL_CONFLICT", "STALE_DOCUMENTATION"}
AUDIT_CASE_NUMBERS = ["003", "004", "005", "007", "008"]


def _load_audit_notes(number: str) -> dict:
    path = ROOT / "golden_samples" / f"golden_{number}" / f"golden_{number}_audit_notes.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("number", AUDIT_CASE_NUMBERS)
def test_audit_notes_file_exists_and_is_well_formed(number):
    notes = _load_audit_notes(number)
    assert notes["case_id"] == f"GOLDEN-{number}"
    assert notes["role"] == "AUDIT_CASE"
    # An AUDIT_CASE may legitimately have zero confirmed findings -- see
    # docs/audit_findings_v0_1.md ("DIAGNOSTIC_UNCERTAINTY is not an audit
    # category"). known_issues must be a list either way, never missing.
    assert isinstance(notes["known_issues"], list)
    for issue in notes["known_issues"]:
        assert issue["category"] in VALID_CATEGORIES
        assert issue["summary"]
        assert issue["detail"]


def test_golden_005_has_no_confirmed_findings_after_review():
    # The only candidate finding for G005 (concurrent uncertain diagnoses
    # classified as POTENTIAL_TEMPORAL_CONFLICT) was reviewed and removed:
    # differential diagnosis alone is not a temporal conflict or a
    # contradiction. It was not replaced by an invented finding.
    notes = _load_audit_notes("005")
    assert notes["known_issues"] == []


def test_at_least_one_case_documents_each_audit_category():
    # Guards against the three categories from docs/audit_findings_v0_1.md
    # collapsing into one another in practice.
    seen = set()
    for number in AUDIT_CASE_NUMBERS:
        for issue in _load_audit_notes(number)["known_issues"]:
            seen.add(issue["category"])
    assert seen == VALID_CATEGORIES
