"""DeepSeek adapter for `ExamExtractor` (Milestone 2.0B, items 1-3, 6-8,
28-29).

This is the ONLY file in the repository allowed to know that DeepSeek
exists. `exam_normalization` never imports this module; it only ever sees
`exam_extraction.base.ExamExtractor`. Swapping providers later means
writing a new file here, never touching the normalizer.

Fixed for this milestone (item 1) -- no other provider, no fallback:

    provider  = DeepSeek
    model     = deepseek-v4-flash
    base_url  = https://api.deepseek.com
    thinking  = disabled
    stream    = False
    response_format = {"type": "json_object"}

Authentication (item 2) has two modes, and this adapter never tries to
tell them apart up front -- it just makes the request and lets the actual
HTTP response decide:

    A. Claude Code Cloud: the environment's proxy injects the credential
       outside this process. No `Authorization` header is added here.
    B. Local/future server: if `DEEPSEEK_API_KEY` is set in the
       environment, it is sent as `Authorization: Bearer <key>`.

The key itself is never printed, logged, serialized, or written to a
file -- it is read once per request straight from `os.environ` and used
only as an in-memory header value on the outgoing `httpx` request.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable, Optional

from pydantic import ValidationError

import httpx

from exam_extraction.base import (
    EmptyProviderResponse,
    ExtractionSchemaFailure,
    InvalidJsonResponse,
    ProviderCallInfo,
    ProviderFailure,
)
from exam_extraction.models import ExamExtractionCandidate, ExamSourceEnvelope
from exam_extraction.prompts.mod_exames_2_0b_002 import (
    MOD_EXAMES_EXTRACTION_PROMPT_VERSION as _DEFAULT_PROMPT_VERSION,
    build_messages as _default_build_messages,
)

DEEPSEEK_PROVIDER_NAME = "DEEPSEEK"
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_CHAT_COMPLETIONS_PATH = "/chat/completions"

# Generous enough for a single clinical fragment's worth of structured
# JSON; deliberately bounded rather than left unset (item 8: this is
# extraction, not open-ended generation).
_DEFAULT_MAX_TOKENS = 4096

_API_KEY_ENV_VAR = "DEEPSEEK_API_KEY"


def _summarize_validation_error(exc: ValidationError) -> str:
    """A `ValidationError`'s default string form can echo back the
    offending input value per error. That input value may be extracted
    clinical text, so operational failure messages only ever carry the
    field path and error type (item 30) -- never the value."""
    parts = []
    for err in exc.errors(include_url=False):
        loc = ".".join(str(p) for p in err.get("loc", ()))
        parts.append(f"{loc or '<root>'}: {err.get('type', 'invalid')}")
    return "; ".join(parts) or str(exc)


class DeepSeekExamExtractor:
    """Implements `exam_extraction.base.ExamExtractor` against DeepSeek's
    chat completions endpoint. Stateless aside from the underlying HTTP
    client and the last call's `ProviderCallInfo` (item 26)."""

    def __init__(
        self,
        *,
        base_url: str = DEEPSEEK_BASE_URL,
        model: str = DEEPSEEK_MODEL,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        timeout: float = 60.0,
        client: Optional[httpx.Client] = None,
        build_messages_fn: Callable[[str, str], list[dict[str, str]]] = _default_build_messages,
        prompt_version: str = _DEFAULT_PROMPT_VERSION,
    ) -> None:
        # No API key is required in the constructor (item 3): Claude Code
        # Cloud never gives this process one, and the client must still be
        # constructible and usable in that mode.
        self._model = model
        self._max_tokens = max_tokens
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout)
        self._build_messages = build_messages_fn
        # Milestone 2.0B.1: which prompt module actually built the request
        # -- overridable (e.g. to run prompt 001 for a side-by-side
        # benchmark) without editing this file. `exam_extraction.execution`
        # reads this to fill `ExecutionMetadata.prompt_version` instead of
        # hardcoding a single prompt module's version.
        self.prompt_version = prompt_version
        self.last_call_info: Optional[ProviderCallInfo] = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get(_API_KEY_ENV_VAR)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        # Cloud mode: no Authorization header is added here at all -- the
        # environment's proxy injects the credential outside this process.
        return headers

    def extract(self, source: ExamSourceEnvelope) -> ExamExtractionCandidate:
        payload: dict[str, Any] = {
            "model": self._model,
            "stream": False,
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
            "max_tokens": self._max_tokens,
            "messages": self._build_messages(source.raw_text, source.source_id),
        }

        started = time.monotonic()
        try:
            response = self._client.post(
                DEEPSEEK_CHAT_COMPLETIONS_PATH, json=payload, headers=self._headers(),
            )
        except httpx.HTTPError as exc:
            raise ProviderFailure(f"HTTP transport error calling DeepSeek: {exc!r}") from exc
        latency_ms = (time.monotonic() - started) * 1000.0

        if response.status_code != 200:
            # Never echo response headers (may carry proxy/auth details);
            # a short body snippet from DeepSeek's own error payload is
            # safe -- it is provider-generated, not clinical content.
            snippet = response.text[:500] if response.text else ""
            raise ProviderFailure(f"DeepSeek returned HTTP {response.status_code}: {snippet}")

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderFailure(f"DeepSeek response was not valid JSON envelope: {exc!r}") from exc

        usage = data.get("usage") or {}
        choices = data.get("choices") or []
        if not choices:
            raise ProviderFailure("DeepSeek response contained no choices")

        message = choices[0].get("message") or {}
        content = message.get("content")
        finish_reason = choices[0].get("finish_reason")

        self.last_call_info = ProviderCallInfo(
            latency_ms=latency_ms,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            finish_reason=finish_reason,
        )

        # item 29: a non-"stop" finish_reason (notably "length") means the
        # content may be truncated mid-JSON. It is never parsed as if it
        # were a complete, trustworthy response.
        if finish_reason not in (None, "stop"):
            raise ProviderFailure(
                f"DeepSeek finish_reason={finish_reason!r} (not 'stop'); "
                "response content is not trusted as complete JSON"
            )

        # item 28: DeepSeek's own docs note JSON Output can occasionally
        # return empty content. This is a distinct, explicit failure --
        # never reinterpreted as "an empty ExamExtractionCandidate".
        if content is None or not content.strip():
            raise EmptyProviderResponse("DeepSeek returned empty content")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise InvalidJsonResponse(f"DeepSeek content was not valid JSON: {exc}") from exc

        # DeepSeek JSON Output guarantees syntactically valid JSON, never
        # that it matches ExamExtractionCandidate (item 7). No permissive
        # parser or regex is used to try to rescue a structural mismatch.
        try:
            return ExamExtractionCandidate.model_validate(parsed)
        except ValidationError as exc:
            raise ExtractionSchemaFailure(_summarize_validation_error(exc)) from exc

    def close(self) -> None:
        self._client.close()
