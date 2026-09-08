"""End-to-end run orchestration (Milestone 2.0B, items 9, 26-27, 30).

This is the concrete implementation of the architecture diagram:

    ExamSourceEnvelope
        -> extractor.extract()          (any ExamExtractor)
        -> ExamExtractionCandidate
        -> deterministic evidence grounding
        -> deterministic normalization
        -> NormalizedExamBatch

`run_extraction` never raises on an expected extraction failure
(`ProviderFailure`, `EmptyProviderResponse`, `InvalidJsonResponse`,
`ExtractionSchemaFailure`) — it captures it into `ExecutionMetadata` and
returns an `ExecutionResult` with `batch=None`, so a caller (a script, an
evaluation loop, a test) always gets a structured answer rather than a
crash (item 27: none of these become a silent success, but they also
never take down the whole process).

Direct calls to `exam_normalization.normalize_extraction_candidate` (used
throughout the Milestone 2.0A/2.0A.1 offline test suite, operating on
hand-authored candidates that never needed grounding) are unaffected by
this module — `run_extraction` is the new, additional entry point used by
real or fake extractors, not a replacement for the existing one.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from exam_extraction.base import ExamExtractor, ExtractionError
from exam_extraction.grounding import GroundingReport, ground_candidate
from exam_extraction.models import ExamExtractionCandidate, ExamSourceEnvelope
from exam_extraction.prompts.mod_exames_2_0b_001 import MOD_EXAMES_EXTRACTION_PROMPT_VERSION
from exam_normalization.idempotency import MOD_EXAMES_MODULE, MOD_EXAMES_MODULE_VERSION
from exam_normalization.models import NormalizedExamBatch
from exam_normalization.orchestrator import normalize_extraction_candidate

logger = logging.getLogger("mod_exames.execution")


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    EMPTY_PROVIDER_RESPONSE = "EMPTY_PROVIDER_RESPONSE"
    INVALID_JSON_RESPONSE = "INVALID_JSON_RESPONSE"
    EXTRACTION_SCHEMA_FAILURE = "EXTRACTION_SCHEMA_FAILURE"


@dataclass(frozen=True)
class ExecutionMetadata:
    """Milestone 2.0B, item 26. Deliberately excludes chain-of-thought, any
    credential, and the full raw document (item 30) — only counts, ids,
    timing, and a short error code."""

    run_id: str
    source_id: str
    module: str
    module_version: str
    prompt_version: str
    provider: str
    model: str
    started_at: str
    completed_at: str
    status: ExecutionStatus
    latency_ms: Optional[float]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    schema_validation_status: str
    grounded_count: int
    ungrounded_count: int
    ambiguous_count: int
    error_code: Optional[str]


@dataclass(frozen=True)
class ExecutionResult:
    metadata: ExecutionMetadata
    batch: Optional[NormalizedExamBatch]
    candidate: Optional[ExamExtractionCandidate]
    grounding_report: Optional[GroundingReport]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_extraction(
    source: ExamSourceEnvelope,
    extractor: ExamExtractor,
    *,
    provider: str,
    model: str,
) -> ExecutionResult:
    run_id = str(uuid.uuid4())
    started_at = _now_iso()

    # item 30: only safe fields ever reach the logger -- no raw_text, no
    # patient identifier, no candidate content.
    logger.info("run_extraction start run_id=%s source_id=%s provider=%s model=%s", run_id, source.source_id, provider, model)

    try:
        candidate = extractor.extract(source)
    except ExtractionError as exc:
        completed_at = _now_iso()
        call_info = getattr(extractor, "last_call_info", None)
        metadata = ExecutionMetadata(
            run_id=run_id, source_id=source.source_id, module=MOD_EXAMES_MODULE,
            module_version=MOD_EXAMES_MODULE_VERSION, prompt_version=MOD_EXAMES_EXTRACTION_PROMPT_VERSION,
            provider=provider, model=model, started_at=started_at, completed_at=completed_at,
            status=ExecutionStatus(exc.error_code), latency_ms=call_info.latency_ms if call_info else None,
            input_tokens=call_info.input_tokens if call_info else None,
            output_tokens=call_info.output_tokens if call_info else None,
            schema_validation_status="NOT_ATTEMPTED" if exc.error_code != "EXTRACTION_SCHEMA_FAILURE" else "FAILED",
            grounded_count=0, ungrounded_count=0, ambiguous_count=0, error_code=exc.error_code,
        )
        logger.warning(
            "run_extraction failed run_id=%s source_id=%s error_code=%s", run_id, source.source_id, exc.error_code,
        )
        return ExecutionResult(metadata=metadata, batch=None, candidate=None, grounding_report=None)

    call_info = getattr(extractor, "last_call_info", None)

    grounded_candidate, grounding_report = ground_candidate(candidate, source)
    batch = normalize_extraction_candidate(grounded_candidate, source)
    completed_at = _now_iso()

    metadata = ExecutionMetadata(
        run_id=run_id, source_id=source.source_id, module=MOD_EXAMES_MODULE,
        module_version=MOD_EXAMES_MODULE_VERSION, prompt_version=MOD_EXAMES_EXTRACTION_PROMPT_VERSION,
        provider=provider, model=model, started_at=started_at, completed_at=completed_at,
        status=ExecutionStatus.SUCCESS, latency_ms=call_info.latency_ms if call_info else None,
        input_tokens=call_info.input_tokens if call_info else None,
        output_tokens=call_info.output_tokens if call_info else None,
        schema_validation_status="OK",
        grounded_count=grounding_report.grounded_count,
        ungrounded_count=grounding_report.ungrounded_count,
        ambiguous_count=grounding_report.ambiguous_count,
        error_code=None,
    )
    logger.info(
        "run_extraction success run_id=%s source_id=%s grounded=%d ungrounded=%d ambiguous=%d",
        run_id, source.source_id, grounding_report.grounded_count,
        grounding_report.ungrounded_count, grounding_report.ambiguous_count,
    )
    return ExecutionResult(metadata=metadata, batch=batch, candidate=grounded_candidate, grounding_report=grounding_report)
