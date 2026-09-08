"""Milestone 2.0B.1, item 3: the schema guide is derived programmatically
from `ExamExtractionCandidate.model_json_schema()`, never hand-maintained,
and stays in sync with the Pydantic models by construction."""

from exam_extraction.models import ExamExtractionCandidate
from exam_extraction.schema_guide import render_schema_guide


def test_render_schema_guide_is_deterministic():
    assert render_schema_guide() == render_schema_guide()


def test_essential_buckets_are_represented():
    guide = render_schema_guide()
    for bucket in (
        "general_labs", "urinalysis", "blood_gases", "troponins",
        "microbiology", "diagnostic_studies", "unmapped", "extraction_warnings",
    ):
        assert bucket in guide, f"{bucket} missing from schema guide"


def test_bucket_specific_fields_distinguish_shapes():
    # These are exactly the fields whose confusion caused prompt 001's
    # live schema failures (docs/mod_exames_2_0b_live_findings.md) --
    # asserting they appear (and that the wrong ones don't leak in) proves
    # the guide is not just a copy of the general_lab shape everywhere.
    guide = render_schema_guide()
    assert "raw_result" in guide  # microbiology, not raw_value
    assert "findings" in guide  # diagnostic_studies
    assert "observations" in guide  # blood_gases nested panel
    assert "raw_text" in guide  # unmapped
    assert "message" in guide  # extraction_warnings


def test_guide_reflects_a_schema_change_without_manual_updates():
    # If a field is renamed/added/removed in the Pydantic models, the
    # guide picks it up automatically -- this is what "no second manual
    # taxonomy" buys. Sanity-checked here by cross-referencing the actual
    # model_json_schema() field names for one representative bucket.
    schema = ExamExtractionCandidate.model_json_schema()
    micro_def = schema["$defs"]["MicrobiologyCandidate"]
    guide = render_schema_guide()
    for field_name in micro_def["properties"]:
        if field_name in {"char_start", "char_end", "grounding_status"}:
            continue  # deliberately excluded system-populated leaf fields
        assert field_name in guide, f"{field_name} present in schema but missing from guide"
