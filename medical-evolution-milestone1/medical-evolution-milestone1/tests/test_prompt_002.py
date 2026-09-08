"""Milestone 2.0B.1: prompt 002 construction, offline and deterministic.

Covers items 2 (versioning + prompt 001 preserved), 4 (every bucket shown,
not just general_labs), 5-10 (the specific structural rules that caused
prompt 001's live schema failures), and 11 (no chain-of-thought
requested/stored).
"""

from exam_extraction.models import ExamExtractionCandidate
from exam_extraction.prompts import mod_exames_2_0b_001, mod_exames_2_0b_002


def test_prompt_002_has_its_own_version_distinct_from_001():
    assert mod_exames_2_0b_002.MOD_EXAMES_EXTRACTION_PROMPT_VERSION == "2.0b-prompt-002"
    assert mod_exames_2_0b_001.MOD_EXAMES_EXTRACTION_PROMPT_VERSION == "2.0b-prompt-001"
    assert mod_exames_2_0b_001.MOD_EXAMES_EXTRACTION_PROMPT_VERSION != mod_exames_2_0b_002.MOD_EXAMES_EXTRACTION_PROMPT_VERSION


def test_prompt_001_module_is_untouched_and_still_importable():
    # item 2: preserved in the repository for audit, not deleted or
    # overwritten by the 002 iteration.
    assert callable(mod_exames_2_0b_001.build_messages)
    messages = mod_exames_2_0b_001.build_messages("31/08: HB 12,0", "SRC-1")
    assert len(messages) == 2


def test_build_messages_returns_system_and_user_roles():
    messages = mod_exames_2_0b_002.build_messages("31/08: HB 12,0", "SRC-1")
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "SRC-1" in messages[1]["content"]
    assert "31/08: HB 12,0" in messages[1]["content"]


def test_embedded_example_candidate_validates_against_the_real_schema():
    # The prompt's own worked example must itself be schema-valid --
    # otherwise it would be actively misleading the model.
    candidate = ExamExtractionCandidate.model_validate(mod_exames_2_0b_002._EXAMPLE_CANDIDATE)
    assert candidate.source_id == "SRC-EXAMPLE"
    assert len(candidate.general_labs) == 2
    assert len(candidate.blood_gases) == 1
    assert len(candidate.blood_gases[0].observations) == 2
    assert len(candidate.microbiology) == 2
    assert len(candidate.diagnostic_studies) == 1
    assert len(candidate.diagnostic_studies[0].findings) == 1


def test_example_shows_every_required_bucket_at_least_once():
    example = mod_exames_2_0b_002._EXAMPLE_CANDIDATE
    for bucket in (
        "general_labs", "urinalysis", "blood_gases", "troponins",
        "microbiology", "diagnostic_studies", "unmapped", "extraction_warnings",
    ):
        assert example[bucket], f"example has no item in {bucket}"


def test_blood_gas_example_is_nested_not_flattened():
    # item 5: PH/PCO2/... must appear only under blood_gases[i].observations,
    # never as top-level general_labs entries.
    example = mod_exames_2_0b_002._EXAMPLE_CANDIDATE
    gas = example["blood_gases"][0]
    assert "observations" in gas
    assert {o["raw_name"] for o in gas["observations"]} == {"PH", "PCO2"}
    assert all(lab["raw_name"] not in {"PH", "PCO2"} for lab in example["general_labs"])


def test_microbiology_example_uses_raw_result_not_raw_value():
    # item 6
    example = mod_exames_2_0b_002._EXAMPLE_CANDIDATE
    for entry in example["microbiology"]:
        assert "raw_result" in entry
        assert "raw_value" not in entry
    assert example["microbiology"][1]["raw_result"] is None  # missing result stays null, never copied


def test_diagnostic_study_example_uses_findings_not_raw_value():
    # item 7
    example = mod_exames_2_0b_002._EXAMPLE_CANDIDATE
    study = example["diagnostic_studies"][0]
    assert "findings" in study
    assert "raw_value" not in study
    assert study["findings"][0]["raw_text"]


def test_unknown_analyte_stays_in_general_labs_in_the_example():
    # item 9: unknown canonical id != unknown clinical category.
    example = mod_exames_2_0b_002._EXAMPLE_CANDIDATE
    ca1_entries = [item for item in example["general_labs"] if item["raw_name"] == "CA1"]
    assert len(ca1_entries) == 1
    assert ca1_entries[0]["canonical_hint"] is None


def test_prompt_text_states_the_unknown_analyte_and_external_source_rules():
    # items 9-10 are stated as explicit prose rules, not just implied by
    # the example.
    prompt = mod_exames_2_0b_002.SYSTEM_PROMPT
    assert "CA1" in prompt
    assert "REALIZADO EM SERVIÇO EXTERNO" in prompt or "SERVIÇO EXTERNO" in prompt


def test_prompt_text_instructs_no_chain_of_thought():
    # item 11: a silent self-check, explicitly never written out.
    prompt_lower = mod_exames_2_0b_002.SYSTEM_PROMPT.lower()
    assert "raciocínio" in prompt_lower
    assert "silenc" in prompt_lower  # "silenciosa"/"silenciosamente"


def test_prompt_text_covers_all_bucket_shape_pitfalls():
    prompt = mod_exames_2_0b_002.SYSTEM_PROMPT
    assert "raw_result" in prompt
    assert "raw_value" in prompt
    assert "findings" in prompt
    assert "observations" in prompt


def test_prompt_002_is_deterministic():
    assert mod_exames_2_0b_002.build_messages("x", "y") == mod_exames_2_0b_002.build_messages("x", "y")
