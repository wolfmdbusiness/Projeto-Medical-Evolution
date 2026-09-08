"""Milestone 2.0C.1, item 13 -- HOLDOUT-001 POST-HARDENING REGRESSION.

IMPORTANT (per the M2.0C.1 instructions): this is a REGRESSION run of a
set that already went through its one held-out clinical validation in
Milestone 2.0C. Re-running it after this milestone's changes (max_tokens,
support/localization split, hierarchical grounding, occurrence identity,
evaluator fix, observability) is explicitly NOT a new held-out validation
-- HOLDOUT-001 has no more evidentiary weight as "unseen data" from this
point on. Every artifact this script produces is labeled
"HOLDOUT-001 POST-HARDENING REGRESSION" for exactly that reason.

Run explicitly (never part of default `pytest -q`, and this is a plain
script, not a pytest module, so it is never collected at all):

    python -m tests.holdout.run_regression_holdout_001

Reuses the same frozen production pipeline and the same 3-runs x
13-sources protocol as the original blind execution
(`tests/holdout/results/holdout_001_blind_run_results.json`), unchanged:
the point of a regression is comparing the same procedure against the
same fixtures, only the code under test has changed. For each (run,
source) it also persists a full observability artifact (item 8) via
`tests/holdout/observability.py`, so any UNGROUNDED or unresolved item
can be inspected after the fact.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from exam_extraction.execution import ExecutionStatus
from exam_extraction.providers.deepseek import DeepSeekExamExtractor
from tests.holdout.harness import load_holdout, run_holdout_source, score_source
from tests.holdout.observability import persist_observability_artifact

RESULTS_PATH = Path(__file__).resolve().parent / "results" / "holdout_001_post_hardening_regression_results.json"
OBSERVABILITY_DIR = Path(__file__).resolve().parent / "results" / "observability" / "holdout_001_post_hardening"

RUNS = 3


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "UNKNOWN"


def main() -> None:
    sources, ground_truth = load_holdout("holdout_001")
    source_list = sources["sources"]

    rows: list[dict] = []
    for run in range(1, RUNS + 1):
        extractor = DeepSeekExamExtractor()
        try:
            for source in source_list:
                source_id = source["source_id"]
                result = run_holdout_source(source, extractor)

                row: dict = {
                    "run": run,
                    "source_id": source_id,
                    "status": result.metadata.status.value,
                    "error_code": result.metadata.error_code,
                    "schema_validation_status": result.metadata.schema_validation_status,
                    "latency_ms": result.metadata.latency_ms,
                    "input_tokens": result.metadata.input_tokens,
                    "output_tokens": result.metadata.output_tokens,
                    "finish_reason": result.metadata.finish_reason,
                    "grounded": result.metadata.grounded_count,
                    "ungrounded": result.metadata.ungrounded_count,
                    "accepted": result.metadata.accepted_count,
                    "localization_multiple": result.metadata.localization_multiple_count,
                    "localization_unresolved": result.metadata.localization_unresolved_count,
                }

                score = None
                if result.metadata.status == ExecutionStatus.SUCCESS:
                    expectation = ground_truth["source_expectations"][source_id]
                    score = score_source(source_id, result.candidate, result.batch, expectation)
                    row.update({
                        "unmapped_count": len(result.batch.unmapped),
                        "expected_current": score.expected_current,
                        "captured_current": score.captured_current,
                        "missing_current": score.missing_current,
                        "expected_urinalysis": score.expected_urinalysis,
                        "captured_urinalysis": score.captured_urinalysis,
                        "missing_urinalysis": score.missing_urinalysis,
                        "expected_gas": score.expected_gas,
                        "captured_gas": score.captured_gas,
                        "missing_gas": score.missing_gas,
                        "gas_specimen_ok": score.gas_specimen_ok,
                        "study_expected": score.study_expected,
                        "study_captured": score.study_captured,
                        "core_findings_expected": score.core_findings_expected,
                        "core_findings_matched": score.core_findings_matched,
                        "missing_core_findings": score.missing_core_findings,
                        "historical_as_current_hits": score.historical_as_current_hits,
                        "pending_marked_performed": score.pending_marked_performed,
                        "pending_text_preserved": score.pending_text_preserved,
                        "unsafe_normalization_hits": score.unsafe_normalization_hits,
                        "all_required_met": score.all_required_met,
                    })
                else:
                    row.update({
                        k: None for k in (
                            "unmapped_count", "expected_current", "captured_current", "missing_current",
                            "expected_urinalysis", "captured_urinalysis", "missing_urinalysis",
                            "expected_gas", "captured_gas", "missing_gas", "gas_specimen_ok",
                            "study_expected", "study_captured", "core_findings_expected",
                            "core_findings_matched", "missing_core_findings", "historical_as_current_hits",
                            "pending_marked_performed", "pending_text_preserved", "unsafe_normalization_hits",
                            "all_required_met",
                        )
                    })

                rows.append(row)
                persist_observability_artifact(
                    source_id=source_id, run_index=run, extractor=extractor,
                    result=result, out_dir=OBSERVABILITY_DIR,
                )
                print(f"[run {run}] {source_id}: {row['status']} finish_reason={row['finish_reason']}")  # noqa: T201
        finally:
            extractor.close()

    output = {
        "label": "HOLDOUT-001 POST-HARDENING REGRESSION",
        "commit": _git_commit(),
        "rows": rows,
    }
    RESULTS_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(rows)} rows to {RESULTS_PATH}")  # noqa: T201


if __name__ == "__main__":
    main()
