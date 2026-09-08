"""Milestone 2.0B, items 20-21, 25, 33: live tests against the real
DeepSeek API.

Deselected by default (`pyproject.toml` sets `addopts = "-q -m \"not
live\""`), so plain `pytest -q` never makes a paid request. Run explicitly:

    pytest -m live

Only the synthetic snippets in `exam_extraction/fixtures/snippets.py` are
used here -- never a full de-identified record. If the environment cannot
authenticate (no Cloud proxy injection and no `DEEPSEEK_API_KEY`), each
test is expected to fail at the HTTP layer with a `ProviderFailure`; that
is reported as a SKIP here, never a FAIL, so an unauthenticated environment
does not break this file when someone does run `-m live` in it.
"""

import pytest

from exam_extraction.base import ProviderFailure
from exam_extraction.evaluation import evaluate_extraction
from exam_extraction.execution import ExecutionStatus, run_extraction
from exam_extraction.fixtures.snippets import EXPECTED_ITEMS, SNIPPETS
from exam_extraction.models import ExamSourceEnvelope
from exam_extraction.providers.deepseek import DEEPSEEK_MODEL, DEEPSEEK_PROVIDER_NAME, DeepSeekExamExtractor
from models.medical_state import SourceType

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def live_extractor():
    extractor = DeepSeekExamExtractor()
    yield extractor
    extractor.close()


def _envelope(source_id: str) -> ExamSourceEnvelope:
    return ExamSourceEnvelope(
        source_id=source_id, patient_ref="PATIENT-GOLDEN-TEST",
        source_type=SourceType.MEDICAL_EVOLUTION, raw_text=SNIPPETS[source_id],
    )


def _run_or_skip(source_id: str, live_extractor):
    result = run_extraction(_envelope(source_id), live_extractor, provider=DEEPSEEK_PROVIDER_NAME, model=DEEPSEEK_MODEL)
    if result.metadata.status == ExecutionStatus.PROVIDER_FAILURE:
        pytest.skip(f"DeepSeek call failed (likely no functional authentication in this environment): {result.metadata.error_code}")
    return result


# item 21: first live test, the smallest realistic snippet.
def test_first_live_snippet_is_fully_grounded(live_extractor):
    result = _run_or_skip("SNIPPET-EASY", live_extractor)
    assert result.metadata.status == ExecutionStatus.SUCCESS
    assert result.metadata.ungrounded_count == 0
    assert result.metadata.ambiguous_count == 0

    evaluation = evaluate_extraction("SNIPPET-EASY", EXPECTED_ITEMS["SNIPPET-EASY"], result.grounding_report, result.batch)
    assert evaluation.recall == 1.0


@pytest.mark.parametrize("source_id", list(SNIPPETS.keys()))
def test_live_snippet_evaluation(source_id, live_extractor):
    result = _run_or_skip(source_id, live_extractor)

    if result.metadata.status != ExecutionStatus.SUCCESS:
        # A live model failing to produce schema-valid JSON is a real,
        # reportable outcome (item 27) -- not a reason to crash this test.
        # It is recorded as an explicit failure, never silently treated as
        # zero extracted items.
        print(  # noqa: T201
            f"[{source_id}] status={result.metadata.status.value} error_code={result.metadata.error_code} "
            f"latency_ms={result.metadata.latency_ms} input_tokens={result.metadata.input_tokens} "
            f"output_tokens={result.metadata.output_tokens}"
        )
        pytest.fail(f"{source_id}: extraction did not succeed ({result.metadata.status.value})", pytrace=False)

    evaluation = evaluate_extraction(source_id, EXPECTED_ITEMS[source_id], result.grounding_report, result.batch)
    print(  # noqa: T201 -- intentional: `pytest -m live -s` is how a human reads these numbers (item 25).
        f"[{source_id}] status={result.metadata.status.value} "
        f"precision={evaluation.precision:.2f} recall={evaluation.recall:.2f} "
        f"hallucination_rate={evaluation.hallucination_rate:.2f} unmapped_rate={evaluation.unmapped_rate:.2f} "
        f"grounded={evaluation.grounded_items} ungrounded={evaluation.ungrounded_items} ambiguous={evaluation.ambiguous_items} "
        f"latency_ms={result.metadata.latency_ms} input_tokens={result.metadata.input_tokens} "
        f"output_tokens={result.metadata.output_tokens}"
    )
    # A live LLM is not held to perfect recall/precision in this milestone
    # -- the point is to observe and report (item 25), not to gate CI on
    # a live model's output. Only structural invariants are asserted.
    assert evaluation.expected_items == len(EXPECTED_ITEMS[source_id])


def test_unauthenticated_or_malformed_auth_fails_explicitly(monkeypatch):
    # Proves item 2's "fail explicitly" requirement concretely: pointed at
    # a base_url with nothing listening and no API key, extraction must
    # raise a typed ProviderFailure, never hang or silently return an
    # empty candidate.
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    extractor = DeepSeekExamExtractor(base_url="https://127.0.0.1:1")
    with pytest.raises(ProviderFailure):
        extractor.extract(_envelope("SNIPPET-EASY"))
