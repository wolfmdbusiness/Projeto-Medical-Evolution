"""Milestone 2.0B.1: `prompt_version` in `ExecutionMetadata` reflects
whichever prompt module actually built the request -- read from the
extractor, never hardcoded to a single prompt module inside
`exam_extraction.execution`. This is what makes a 001-vs-002-vs-003
benchmark possible without touching `run_extraction` itself."""

import json

import httpx

from exam_extraction.execution import run_extraction
from exam_extraction.fake import FakeExamExtractor
from exam_extraction.models import ExamExtractionCandidate, ExamSourceEnvelope
from exam_extraction.prompts import mod_exames_2_0b_001, mod_exames_2_0b_003
from exam_extraction.providers.deepseek import DeepSeekExamExtractor
from models.medical_state import SourceType


def _envelope() -> ExamSourceEnvelope:
    return ExamSourceEnvelope(
        source_id="SRC-PV", patient_ref="PATIENT-GOLDEN-TEST",
        source_type=SourceType.MEDICAL_EVOLUTION, raw_text="31/08: HB 12,0",
    )


def test_deepseek_extractor_defaults_to_prompt_003():
    extractor = DeepSeekExamExtractor()
    assert extractor.prompt_version == mod_exames_2_0b_003.MOD_EXAMES_EXTRACTION_PROMPT_VERSION
    extractor.close()


def test_deepseek_extractor_can_be_pinned_to_prompt_001_for_a_benchmark():
    extractor = DeepSeekExamExtractor(
        build_messages_fn=mod_exames_2_0b_001.build_messages,
        prompt_version=mod_exames_2_0b_001.MOD_EXAMES_EXTRACTION_PROMPT_VERSION,
    )
    assert extractor.prompt_version == "2.0b-prompt-001"

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        body = {
            "choices": [{"message": {"content": json.dumps({"source_id": "SRC-PV", "general_labs": []})}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        return httpx.Response(200, json=body)

    extractor._client = httpx.Client(base_url="https://api.deepseek.com", transport=httpx.MockTransport(handler))
    extractor.extract(_envelope())
    # The prompt actually sent must match prompt 001's system message, not
    # the default prompt 002's.
    assert captured["body"]["messages"][0]["content"] == mod_exames_2_0b_001.SYSTEM_PROMPT
    extractor.close()


def test_run_extraction_reports_the_extractor_prompt_version():
    candidate = ExamExtractionCandidate(source_id="SRC-PV", general_labs=[])
    extractor = DeepSeekExamExtractor()  # never actually called (FakeExamExtractor is used below)
    fake = FakeExamExtractor({"SRC-PV": candidate})
    fake.prompt_version = "TEST-PROMPT-VERSION"  # simulate an extractor that reports one
    result = run_extraction(_envelope(), fake, provider="FAKE", model="fake-v0")
    assert result.metadata.prompt_version == "TEST-PROMPT-VERSION"
    extractor.close()


def test_run_extraction_falls_back_to_na_when_extractor_has_no_prompt_version():
    candidate = ExamExtractionCandidate(source_id="SRC-PV", general_labs=[])
    fake = FakeExamExtractor({"SRC-PV": candidate})  # no .prompt_version attribute
    result = run_extraction(_envelope(), fake, provider="FAKE", model="fake-v0")
    assert result.metadata.prompt_version == "N/A"


def test_run_extraction_explicit_prompt_version_overrides_extractor():
    candidate = ExamExtractionCandidate(source_id="SRC-PV", general_labs=[])
    fake = FakeExamExtractor({"SRC-PV": candidate})
    fake.prompt_version = "FROM-EXTRACTOR"
    result = run_extraction(_envelope(), fake, provider="FAKE", model="fake-v0", prompt_version="EXPLICIT-OVERRIDE")
    assert result.metadata.prompt_version == "EXPLICIT-OVERRIDE"
