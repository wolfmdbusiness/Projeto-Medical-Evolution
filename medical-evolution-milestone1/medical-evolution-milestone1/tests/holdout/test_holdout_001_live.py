"""Milestone 2.0C: single-pass live validation against HOLDOUT-001.

Deselected by default (`pyproject.toml` sets `addopts` to exclude
`holdout_live`), so plain `pytest -q` never makes a paid request. Run
explicitly:

    pytest -m holdout_live -v -s

This file exercises the frozen, unmodified production pipeline
(`exam_extraction.execution.run_extraction`) against the real DeepSeek API
using the same `DeepSeekExamExtractor` defaults as production (prompt
2.0b-prompt-003, temperature=0) -- nothing here reconfigures it. It is a
spot-check/regression tool for this holdout set, independent of the
official blind 3-run x 13-source protocol (executed separately, as a
controlled script, per M2_0C_CLAUDE_INSTRUCTIONS.md's blind-execution
requirement that all 3 runs happen with zero changes between them and be
reported together).
"""

import pytest

from exam_extraction.execution import ExecutionStatus
from exam_extraction.providers.deepseek import DeepSeekExamExtractor
from tests.holdout.harness import load_holdout, run_holdout_source, score_source

pytestmark = pytest.mark.holdout_live

_SOURCES, _GROUND_TRUTH = load_holdout("holdout_001")
_SOURCE_IDS = [s["source_id"] for s in _SOURCES["sources"]]


@pytest.fixture(scope="module")
def live_extractor():
    extractor = DeepSeekExamExtractor()
    yield extractor
    extractor.close()


@pytest.mark.parametrize("source_id", _SOURCE_IDS)
def test_holdout_source(source_id, live_extractor):
    source = next(s for s in _SOURCES["sources"] if s["source_id"] == source_id)
    result = run_holdout_source(source, live_extractor)

    if result.metadata.status != ExecutionStatus.SUCCESS:
        pytest.fail(f"{source_id}: extraction did not succeed ({result.metadata.status.value}, {result.metadata.error_code})")

    expectation = _GROUND_TRUTH["source_expectations"][source_id]
    score = score_source(source_id, result.candidate, result.batch, expectation)

    print(  # noqa: T201
        f"[{source_id}] grounded={result.metadata.grounded_count} "
        f"ungrounded={result.metadata.ungrounded_count} accepted={result.metadata.accepted_count} "
        f"loc_multiple={result.metadata.localization_multiple_count} "
        f"loc_unresolved={result.metadata.localization_unresolved_count} "
        f"captured_current={score.captured_current}/{score.expected_current} "
        f"missing={score.missing_current} historical_hits={score.historical_as_current_hits} "
        f"unsafe={score.unsafe_normalization_hits} "
        f"latency_ms={result.metadata.latency_ms}"
    )

    # Safety-critical assertions -- these are never relaxed.
    assert score.historical_as_current_hits == [], f"{source_id}: historical-as-current contamination"
    assert not score.pending_marked_performed, f"{source_id}: pending study marked performed"
    assert score.unsafe_normalization_hits == [], f"{source_id}: unsafe normalization"
    assert result.metadata.ungrounded_count == 0, f"{source_id}: true hallucination (ungrounded accepted item)"
