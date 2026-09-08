"""Offline extractor for testing (Milestone 2.0B, item 18).

`FakeExamExtractor` implements `exam_extraction.base.ExamExtractor` exactly
like `exam_extraction.providers.deepseek.DeepSeekExamExtractor` does, so
the full pipeline (source -> extractor -> candidate -> grounding ->
normalize -> apply) is exercised end-to-end by the standard offline test
suite, with zero network calls. It is looked up by `source.source_id`
against a fixed mapping supplied at construction time; an unknown
`source_id` is an explicit failure (`ProviderFailure`), never a silent
empty result.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from exam_extraction.base import ProviderCallInfo, ProviderFailure
from exam_extraction.models import ExamExtractionCandidate, ExamSourceEnvelope

RECORDED_RESPONSES_DIR = Path(__file__).resolve().parent / "fixtures" / "recorded_responses"


def load_recorded_response(path: Path) -> ExamExtractionCandidate:
    """Load one recorded/synthetic provider response fixture (item 19) and
    validate it through the exact same Pydantic contract a live response
    would go through -- these fixtures are regression tests for the
    contract, not just inert JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return ExamExtractionCandidate.model_validate(data)


def load_recorded_responses(directory: Path = RECORDED_RESPONSES_DIR) -> dict[str, ExamExtractionCandidate]:
    """Load every `*.json` fixture in `directory`, keyed by filename stem
    (which is also each fixture's `source_id`, by convention)."""
    responses: dict[str, ExamExtractionCandidate] = {}
    for path in sorted(directory.glob("*.json")):
        candidate = load_recorded_response(path)
        responses[path.stem] = candidate
    return responses


class FakeExamExtractor:
    """A fixed, in-memory stand-in for a real provider. No PHI, no
    network -- pass it a `{source_id: ExamExtractionCandidate}` mapping
    (typically built via `load_recorded_responses`)."""

    def __init__(self, responses: dict[str, ExamExtractionCandidate]) -> None:
        self._responses = responses
        self.last_call_info: Optional[ProviderCallInfo] = None

    def extract(self, source: ExamSourceEnvelope) -> ExamExtractionCandidate:
        candidate = self._responses.get(source.source_id)
        if candidate is None:
            raise ProviderFailure(
                f"FakeExamExtractor has no recorded response for source_id={source.source_id!r}"
            )
        self.last_call_info = ProviderCallInfo(
            latency_ms=0.0, input_tokens=None, output_tokens=None, finish_reason="stop",
        )
        return candidate
