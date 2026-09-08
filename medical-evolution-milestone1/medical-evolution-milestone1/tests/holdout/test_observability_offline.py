"""Offline tests for `tests/holdout/observability.py` (Milestone 2.0C.1,
items 8 and 12's "privacy dos artefatos" case). No network call: the
DeepSeek HTTP call is mocked exactly as in `test_deepseek_adapter_offline.py`,
so these prove the artifact builder/writer's own behavior, independent of
any live response.
"""

import json

import httpx

from exam_extraction.execution import run_extraction
from exam_extraction.models import ExamSourceEnvelope
from exam_extraction.providers.deepseek import DeepSeekExamExtractor
from models.medical_state import SourceType
from tests.holdout.observability import (
    FORBIDDEN_SUBSTRINGS,
    build_observability_artifact,
    persist_observability_artifact,
)

_FAKE_SECRET = "sk-not-a-real-key-0000000000000000"
_SECRET_MARKER = "PACIENTE-SECRETO-987-NAO-DESIDENTIFICADO"


def _envelope() -> ExamSourceEnvelope:
    return ExamSourceEnvelope(
        source_id="SRC-OBS-1",
        patient_ref=_SECRET_MARKER,
        source_type=SourceType.MEDICAL_EVOLUTION,
        raw_text=f"31/08: HB 12,0 -- {_SECRET_MARKER}",
    )


def _extractor_with(handler) -> DeepSeekExamExtractor:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="https://api.deepseek.com", transport=transport)
    return DeepSeekExamExtractor(client=client)


def _run(monkeypatch) -> tuple:
    monkeypatch.setenv("DEEPSEEK_API_KEY", _FAKE_SECRET)

    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps({
            "source_id": "SRC-OBS-1",
            "general_labs": [
                {
                    "raw_name": "HB", "raw_value": "12,0", "source_order": 1,
                    "evidence": {"evidence_text": "HB 12,0"}, "source_ref": "SRC-OBS-1",
                }
            ],
        })
        body = {
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    result = run_extraction(_envelope(), extractor, provider="DEEPSEEK", model="deepseek-v4-flash")
    return extractor, result


# --- privacy: never a credential, header, or identified document -----------

def test_artifact_never_contains_authorization_header_or_api_key(monkeypatch):
    extractor, result = _run(monkeypatch)
    artifact = build_observability_artifact(
        source_id="SRC-OBS-1", run_index=1, extractor=extractor, result=result,
    )
    serialized = json.dumps(artifact)
    assert _FAKE_SECRET not in serialized
    for forbidden in FORBIDDEN_SUBSTRINGS:
        assert forbidden not in serialized


def test_artifact_never_contains_the_source_raw_text_or_patient_ref(monkeypatch):
    # The envelope's own raw_text/patient_ref carry a marker that would
    # only leak if this module read the envelope directly instead of just
    # the pipeline's own outputs (candidate/grounding/batch/evaluation).
    extractor, result = _run(monkeypatch)
    artifact = build_observability_artifact(
        source_id="SRC-OBS-1", run_index=1, extractor=extractor, result=result,
    )
    serialized = json.dumps(artifact)
    assert _SECRET_MARKER not in serialized


def test_no_authorization_header_case_when_env_var_absent(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps({"source_id": "SRC-OBS-1", "general_labs": []})
        body = {
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    result = run_extraction(_envelope(), extractor, provider="DEEPSEEK", model="deepseek-v4-flash")
    artifact = build_observability_artifact(
        source_id="SRC-OBS-1", run_index=1, extractor=extractor, result=result,
    )
    serialized = json.dumps(artifact)
    for forbidden in FORBIDDEN_SUBSTRINGS:
        assert forbidden not in serialized


# --- completeness: everything item 8 asks for is actually present ----------

def test_artifact_contains_every_field_item_8_requires(monkeypatch):
    extractor, result = _run(monkeypatch)
    artifact = build_observability_artifact(
        source_id="SRC-OBS-1", run_index=2, extractor=extractor, result=result,
    )
    assert artifact["provider_response_content"] is not None
    assert "HB" in artifact["provider_response_content"]
    assert artifact["parsed_candidate"]["source_id"] == "SRC-OBS-1"
    assert artifact["grounding_result"]["accepted_count"] == 1
    assert artifact["normalized_batch"]["source_id"] == "SRC-OBS-1"
    assert artifact["provider"] == "DEEPSEEK"
    assert artifact["model"] == "deepseek-v4-flash"
    assert artifact["prompt_version"]
    assert artifact["config"]["max_tokens"] == 16384
    assert artifact["config"]["temperature"] == 0
    assert artifact["config"]["thinking"] == "disabled"
    assert artifact["input_tokens"] == 10
    assert artifact["output_tokens"] == 5
    assert artifact["latency_ms"] is not None
    assert artifact["finish_reason"] == "stop"
    assert artifact["evaluation_result"] is None  # not supplied in this call


def test_artifact_finish_reason_and_status_reflect_a_truncated_response(monkeypatch):
    # item 2/8: a non-"stop" finish_reason must itself be inspectable in
    # the persisted artifact, not just silently turned into a failure.
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "choices": [{"message": {"content": '{"source_id": "SRC-OBS-1"'}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 16384},
        }
        return httpx.Response(200, json=body)

    extractor = _extractor_with(handler)
    result = run_extraction(_envelope(), extractor, provider="DEEPSEEK", model="deepseek-v4-flash")
    artifact = build_observability_artifact(
        source_id="SRC-OBS-1", run_index=1, extractor=extractor, result=result,
    )
    assert artifact["finish_reason"] == "length"
    assert artifact["status"] == "PROVIDER_FAILURE"
    # The truncated content is still inspectable via the persisted artifact.
    assert artifact["provider_response_content"] == '{"source_id": "SRC-OBS-1"'
    assert artifact["parsed_candidate"] is None
    assert artifact["normalized_batch"] is None


# --- persistence -------------------------------------------------------------

def test_persist_writes_a_json_file_named_by_source_and_run(tmp_path, monkeypatch):
    extractor, result = _run(monkeypatch)
    path = persist_observability_artifact(
        source_id="SRC-OBS-1", run_index=3, extractor=extractor, result=result, out_dir=tmp_path,
    )
    assert path == tmp_path / "SRC-OBS-1__run3.json"
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["source_id"] == "SRC-OBS-1"
    assert loaded["run_index"] == 3
