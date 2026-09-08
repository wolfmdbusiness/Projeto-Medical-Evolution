"""Milestone 2.0C.1, item 8 -- observability artifact persistence for the
live holdout harness.

Persists, per deidentified source + run, exactly what item 8 asks for:
provider response content; parsed `ExamExtractionCandidate`; grounding
result; `NormalizedExamBatch`; evaluation result; provider/model/prompt/
config; token usage; latency; `finish_reason`.

Never persists: API key; `Authorization` header; chain-of-thought;
identified documents. Concretely:

  - The source's own `raw_text` (and any envelope field beyond
    `source_id`) is never read into an artifact -- only the pipeline's
    own outputs (candidate, grounding, batch, evaluation, metadata) are
    written, and those never carry `patient_ref` (see
    `exam_normalization.models.NormalizedExamBatch`, which has no such
    field).
  - `thinking` is fixed to `"disabled"` for this extractor (Milestone
    2.0B, item 1) -- there is no chain-of-thought field anywhere in a
    DeepSeek JSON-mode response to persist in the first place.
  - `DeepSeekExamExtractor` never exposes its request headers or API key
    as an attribute (`exam_extraction/providers/deepseek.py` reads the
    key once, straight from `os.environ`, directly into an in-memory
    header on the outgoing request) -- there is nothing here that could
    reach into that value even by accident.

This module is evaluation-only infrastructure over already-deidentified
HOLDOUT-001 fixtures (`tests/holdout/fixtures`); the M2.0C.1 instructions
(item 8) explicitly permit persisting artifacts for that regression set on
that basis. It must never be pointed at a live/identified document.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Optional

from exam_extraction.evaluation import EvaluationResult
from exam_extraction.execution import ExecutionResult
from exam_extraction.grounding import GroundingReport
from exam_extraction.providers.deepseek import DeepSeekExamExtractor

RESULTS_DIR = Path(__file__).resolve().parent / "results" / "observability"

# Checked by the offline privacy test -- kept next to the writer so the
# allow/deny boundary for what may ever appear in a persisted artifact
# lives in exactly one place.
FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "Authorization",
    "authorization",
    "Bearer ",
    "DEEPSEEK_API_KEY",
    "api_key",
    "apikey",
)


def _grounding_report_to_dict(report: Optional[GroundingReport]) -> Optional[dict[str, Any]]:
    if report is None:
        return None
    return {
        "records": [
            {
                "category": r.category,
                "label": r.label,
                "support_status": r.support_status.value,
                "localization_status": r.localization_status.value if r.localization_status else None,
                "spans": [list(span) for span in r.spans],
                "accepted": r.accepted,
            }
            for r in report.records
        ],
        "grounded_count": report.grounded_count,
        "ungrounded_count": report.ungrounded_count,
        "localization_unique_count": report.localization_unique_count,
        "localization_multiple_count": report.localization_multiple_count,
        "localization_unresolved_count": report.localization_unresolved_count,
        "accepted_count": report.accepted_count,
    }


def build_observability_artifact(
    *,
    source_id: str,
    run_index: int,
    extractor: DeepSeekExamExtractor,
    result: ExecutionResult,
    evaluation_result: Optional[EvaluationResult] = None,
) -> dict[str, Any]:
    """Assemble one artifact as a plain dict -- pure function, no I/O -- so
    both the writer below and the offline privacy test can exercise it
    without touching disk or the network."""
    metadata = result.metadata
    return {
        "source_id": source_id,
        "run_index": run_index,
        "run_id": metadata.run_id,
        "provider": metadata.provider,
        "model": metadata.model,
        "prompt_version": metadata.prompt_version,
        "config": {
            "temperature": 0,
            "max_tokens": getattr(extractor, "_max_tokens", None),
            "thinking": "disabled",
            "response_format": "json_object",
        },
        "started_at": metadata.started_at,
        "completed_at": metadata.completed_at,
        "status": metadata.status.value,
        "latency_ms": metadata.latency_ms,
        "input_tokens": metadata.input_tokens,
        "output_tokens": metadata.output_tokens,
        "finish_reason": metadata.finish_reason,
        "schema_validation_status": metadata.schema_validation_status,
        "error_code": metadata.error_code,
        "provider_response_content": getattr(extractor, "last_raw_content", None),
        "parsed_candidate": (
            result.candidate.model_dump(mode="json") if result.candidate is not None else None
        ),
        "grounding_result": _grounding_report_to_dict(result.grounding_report),
        "normalized_batch": result.batch.model_dump(mode="json") if result.batch is not None else None,
        "evaluation_result": (
            dataclasses.asdict(evaluation_result) if evaluation_result is not None else None
        ),
    }


def persist_observability_artifact(
    *,
    source_id: str,
    run_index: int,
    extractor: DeepSeekExamExtractor,
    result: ExecutionResult,
    evaluation_result: Optional[EvaluationResult] = None,
    out_dir: Path = RESULTS_DIR,
) -> Path:
    """Write one artifact to `<out_dir>/<source_id>__run<run_index>.json`
    and return its path. Called once per (source, run) by the live
    HOLDOUT-001 regression harness -- never by any offline test, which
    exercises `build_observability_artifact` directly instead."""
    artifact = build_observability_artifact(
        source_id=source_id,
        run_index=run_index,
        extractor=extractor,
        result=result,
        evaluation_result=evaluation_result,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{source_id}__run{run_index}.json"
    path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path
