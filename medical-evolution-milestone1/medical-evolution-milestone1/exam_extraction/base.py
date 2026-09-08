"""Provider-independent extractor contract (Milestone 2.0B, item 4).

`exam_normalization` must never import anything from `exam_extraction.providers`
— it only ever sees an `ExamExtractor` (this Protocol) and the
`ExamExtractionCandidate` it returns. A concrete provider (DeepSeek today,
something else later) is swapped in by the caller, never by the normalizer.

The exception hierarchy here is the vocabulary every provider adapter must
use to report failure (item 27): a provider is never allowed to turn one of
these into a silent, look-like-success empty result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from exam_extraction.models import ExamExtractionCandidate, ExamSourceEnvelope


@dataclass(frozen=True)
class ProviderCallInfo:
    """What a provider adapter knows about its own last HTTP call that the
    extraction contract itself has no room for (item 26): latency and
    token usage. Never contains the request/response body, headers, or any
    credential — only the numbers."""

    latency_ms: float
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    finish_reason: Optional[str]


class ExtractionError(Exception):
    """Base class for every explicit, typed extraction failure. Never
    raised directly — always one of the subclasses below, so callers can
    tell failure modes apart (item 27)."""

    error_code: str = "EXTRACTION_ERROR"


class ProviderFailure(ExtractionError):
    """The HTTP call itself failed, or the provider returned something the
    adapter cannot proceed with in good faith (network error, non-2xx
    status, unauthenticated, or an untrustworthy `finish_reason` such as
    "length" — item 29: a truncated response must never be parsed as if it
    were complete JSON)."""

    error_code = "PROVIDER_FAILURE"


class EmptyProviderResponse(ExtractionError):
    """`content` was `None` or empty/whitespace-only after `.strip()`
    (item 28). DeepSeek's own documentation notes JSON Output can
    occasionally return empty content; this is never reinterpreted as "an
    empty ExamExtractionCandidate" — it is a distinct, explicit failure."""

    error_code = "EMPTY_PROVIDER_RESPONSE"


class InvalidJsonResponse(ExtractionError):
    """`content` was non-empty but `json.loads(content)` failed. No regex
    or permissive parser is used to try to "rescue" malformed JSON (item
    7)."""

    error_code = "INVALID_JSON_RESPONSE"


class ExtractionSchemaFailure(ExtractionError):
    """`content` parsed as JSON but `ExamExtractionCandidate.model_validate`
    rejected it. DeepSeek's JSON Output guarantees syntactically valid JSON,
    never that it matches our schema (item 7)."""

    error_code = "EXTRACTION_SCHEMA_FAILURE"


class ExamExtractor(Protocol):
    """Anything that can turn one `ExamSourceEnvelope` into one
    `ExamExtractionCandidate`. `exam_normalization` never imports a
    concrete implementation of this — only this Protocol.

    Implementations may optionally set `self.last_call_info` (a
    `ProviderCallInfo`, or `None`) after each call, for adapters that have
    real latency/token-usage data to report; callers must tolerate its
    absence via `getattr(..., "last_call_info", None)` rather than
    assuming every extractor provides it.
    """

    def extract(self, source: ExamSourceEnvelope) -> ExamExtractionCandidate:
        ...
