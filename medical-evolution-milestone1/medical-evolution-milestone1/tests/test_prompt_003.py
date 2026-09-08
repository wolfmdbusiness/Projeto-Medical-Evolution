"""Milestone 2.0B.2: prompt 003 construction, offline and deterministic.

Prompt 003 keeps everything from prompt 002 intact (schema guide, one
example per bucket, structural pitfalls, no-chain-of-thought self-check)
and adds exactly one new rule: minimal evidence_text (item 3). These
tests focus on what's new; prompt 002's own tests already cover the
inherited structural guarantees.
"""

from exam_extraction.models import ExamExtractionCandidate
from exam_extraction.prompts import mod_exames_2_0b_001, mod_exames_2_0b_002, mod_exames_2_0b_003


def test_prompt_003_has_its_own_version_distinct_from_001_and_002():
    versions = {
        mod_exames_2_0b_001.MOD_EXAMES_EXTRACTION_PROMPT_VERSION,
        mod_exames_2_0b_002.MOD_EXAMES_EXTRACTION_PROMPT_VERSION,
        mod_exames_2_0b_003.MOD_EXAMES_EXTRACTION_PROMPT_VERSION,
    }
    assert versions == {"2.0b-prompt-001", "2.0b-prompt-002", "2.0b-prompt-003"}


def test_prompts_001_and_002_are_still_importable_and_unchanged():
    # Preserved for audit (item 2) -- their own version constants must
    # never shift just because 003 exists.
    assert mod_exames_2_0b_001.MOD_EXAMES_EXTRACTION_PROMPT_VERSION == "2.0b-prompt-001"
    assert mod_exames_2_0b_002.MOD_EXAMES_EXTRACTION_PROMPT_VERSION == "2.0b-prompt-002"


def test_prompt_003_states_the_minimal_evidence_rule_explicitly():
    prompt = mod_exames_2_0b_003.SYSTEM_PROMPT
    assert "MENOR trecho" in prompt or "menor trecho" in prompt.lower()
    # The worked good-vs-bad example from item 3.
    assert "LEUCO 8330; PLQ 270K; RNI 1,03; U 25" in prompt
    assert prompt.count('"LEUCO 8330"') >= 1  # the minimal, correct evidence form is shown


def test_prompt_003_self_check_mentions_minimal_evidence():
    prompt = mod_exames_2_0b_003.SYSTEM_PROMPT
    self_check_section = prompt.split("ANTES DE RESPONDER", 1)[1]
    assert "mínimo" in self_check_section.lower() or "minimo" in self_check_section.lower()


def test_prompt_003_reuses_the_same_schema_derived_guide_as_002():
    # Structurally based on the schema guide (item 2) -- not a rewritten
    # or divergent description.
    from exam_extraction.schema_guide import render_schema_guide
    guide = render_schema_guide()
    assert guide in mod_exames_2_0b_003.SYSTEM_PROMPT


def test_prompt_003_example_candidate_is_still_schema_valid():
    # Reuses prompt 002's example (already minimal-evidence-style) rather
    # than duplicating it -- validated again here as a regression guard.
    candidate = ExamExtractionCandidate.model_validate(mod_exames_2_0b_003._EXAMPLE_CANDIDATE)
    assert candidate.source_id == "SRC-EXAMPLE"


def test_prompt_003_example_evidence_is_already_minimal_not_whole_line():
    # Each blood gas observation's evidence_text is its own short span,
    # not the panel's full evidence_text repeated.
    example = mod_exames_2_0b_003._EXAMPLE_CANDIDATE
    gas = example["blood_gases"][0]
    panel_evidence = gas["evidence"]["evidence_text"]
    for obs in gas["observations"]:
        assert obs["evidence"]["evidence_text"] != panel_evidence
        assert len(obs["evidence"]["evidence_text"]) < len(panel_evidence)


def test_build_messages_still_returns_system_and_user_roles():
    messages = mod_exames_2_0b_003.build_messages("31/08: HB 12,0", "SRC-1")
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "SRC-1" in messages[1]["content"]


def test_prompt_003_is_deterministic():
    assert mod_exames_2_0b_003.build_messages("x", "y") == mod_exames_2_0b_003.build_messages("x", "y")
