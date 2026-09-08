"""Milestone 2.0B, items 2-3, 27-29: `DeepSeekExamExtractor` behavior,
entirely offline via `httpx.MockTransport` -- no real network call, no
DeepSeek credential needed. Exercises the request shape, both
authentication modes, and every explicit failure type.
"""

import json

import httpx
import pytest

from exam_extraction.base import (
    EmptyProviderResponse,
    ExtractionSchemaFailure,
    InvalidJsonResponse,
    ProviderFailure,
)
from exam_extraction.models import ExamSourceEnvelope
from exam_extraction.providers.deepseek import DeepSeekExamExtractor
from models.medical_state import SourceType


def _envelope() -> ExamSourceEnvelope:
    return ExamSourceEnvelope(
        source_id="SRC-DS", patient_ref="PATIENT-GOLDEN-TEST",
        source_type=SourceType.MEDICAL_EVOLUTION, raw_text="31/08: HB 12,0",
    )


def _ok_response(content: str, finish_reason: str = "stop") -> dict:
    return {
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 42, "completion_tokens": 7},
    }


def _extractor_with(handler) -> DeepSeekExamExtractor:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="https://api.deepseek.com", transport=transport)
    return DeepSeekExamExtractor(client=client)


# --- request shape ---------------------------------------------------------

def test_request_uses_fixed_provider_settings():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["path"] = request.url.path
        body = _ok_response(json.dumps({"source_id": "SRC-DS", "general_labs": []}))
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    extractor.extract(_envelope())

    assert captured["path"] == "/chat/completions"
    assert captured["body"]["model"] == "deepseek-v4-flash"
    assert captured["body"]["stream"] is False
    assert captured["body"]["thinking"] == {"type": "disabled"}
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert len(captured["body"]["messages"]) == 2


def test_request_sets_temperature_zero_and_never_sets_top_p():
    # Milestone 2.0B.2, item 1: deterministic sampling, and top_p is left
    # alone (not simultaneously overridden).
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        body = _ok_response(json.dumps({"source_id": "SRC-DS", "general_labs": []}))
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    extractor.extract(_envelope())

    assert captured["body"]["temperature"] == 0
    assert "top_p" not in captured["body"]


def test_request_sets_max_tokens_16384():
    # Milestone 2.0C.1, item 2: HOLDOUT-001's two largest lab panels
    # reproducibly truncated at the previous 4096 ceiling.
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        body = _ok_response(json.dumps({"source_id": "SRC-DS", "general_labs": []}))
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    extractor.extract(_envelope())

    assert captured["body"]["max_tokens"] == 16384


# --- authentication modes (item 2) -----------------------------------------

def test_no_authorization_header_when_no_api_key_env_var(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["has_auth"] = "authorization" in {k.lower() for k in request.headers.keys()}
        body = _ok_response(json.dumps({"source_id": "SRC-DS", "general_labs": []}))
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    extractor.extract(_envelope())
    assert captured["has_auth"] is False


def test_authorization_header_set_when_api_key_env_var_present(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-a-real-key")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        body = _ok_response(json.dumps({"source_id": "SRC-DS", "general_labs": []}))
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    extractor.extract(_envelope())
    assert captured["auth"] == "Bearer sk-test-not-a-real-key"


# --- success path + usage/latency capture (item 26) -------------------------

def test_successful_extraction_populates_last_call_info():
    def handler(request: httpx.Request) -> httpx.Response:
        body = _ok_response(json.dumps({"source_id": "SRC-DS", "general_labs": []}))
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    candidate = extractor.extract(_envelope())
    assert candidate.source_id == "SRC-DS"
    assert extractor.last_call_info is not None
    assert extractor.last_call_info.input_tokens == 42
    assert extractor.last_call_info.output_tokens == 7
    assert extractor.last_call_info.finish_reason == "stop"
    assert extractor.last_call_info.latency_ms >= 0.0


# --- explicit failure types (item 27) ---------------------------------------

def test_non_200_status_raises_provider_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    extractor = _extractor_with(handler)
    with pytest.raises(ProviderFailure):
        extractor.extract(_envelope())


def test_network_error_raises_provider_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure")

    extractor = _extractor_with(handler)
    with pytest.raises(ProviderFailure):
        extractor.extract(_envelope())


def test_finish_reason_length_raises_provider_failure_never_parsed_as_complete():
    def handler(request: httpx.Request) -> httpx.Response:
        body = _ok_response(json.dumps({"source_id": "SRC-DS", "general_labs": []}), finish_reason="length")
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    with pytest.raises(ProviderFailure, match="length"):
        extractor.extract(_envelope())


def test_none_content_raises_empty_provider_response():
    def handler(request: httpx.Request) -> httpx.Response:
        body = _ok_response(None)  # type: ignore[arg-type]
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    with pytest.raises(EmptyProviderResponse):
        extractor.extract(_envelope())


def test_whitespace_only_content_raises_empty_provider_response():
    def handler(request: httpx.Request) -> httpx.Response:
        body = _ok_response("   \n  ")
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    with pytest.raises(EmptyProviderResponse):
        extractor.extract(_envelope())


def test_malformed_json_content_raises_invalid_json_response():
    def handler(request: httpx.Request) -> httpx.Response:
        body = _ok_response("{not valid json")
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    with pytest.raises(InvalidJsonResponse):
        extractor.extract(_envelope())


def test_json_not_matching_schema_raises_extraction_schema_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        body = _ok_response(json.dumps({"this_is": "not a valid ExamExtractionCandidate"}))
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    with pytest.raises(ExtractionSchemaFailure):
        extractor.extract(_envelope())


def test_schema_failure_message_never_echoes_raw_field_values():
    # A validation error message must name the field path, not smuggle the
    # rejected clinical-looking value back out (item 30). The bad value is
    # placed on the field that actually fails validation, so this is a
    # meaningful check of what Pydantic's error would otherwise include.
    secret_value = "PACIENTE JOAO DA SILVA CONFIDENCIAL"

    def handler(request: httpx.Request) -> httpx.Response:
        body = _ok_response(json.dumps({"source_id": "SRC-DS", "general_labs": secret_value}))
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    with pytest.raises(ExtractionSchemaFailure) as exc_info:
        extractor.extract(_envelope())
    assert secret_value not in str(exc_info.value)
