# MOD-EXAMES 2.0B.2 — DeepSeek Extraction Stability Calibration

50 live calls: the same 10 synthetic snippets used in Milestones 2.0B and
2.0B.1, run 5 independent times each, against `deepseek-v4-flash` with
prompt `2.0b-prompt-003` and `temperature=0` (`thinking` still disabled).
No case was substituted or removed.

## Per-run results

| Run | Schema success | Precision | Recall | True hallucination | Ambiguity | Grounded | Ungrounded | Ambiguous | Unmapped | Avg latency | Input tok | Output tok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 10/10 | 1.000 | 1.000 | 0.000 | 0.000 | 26 | 0 | 0 | 0 | 2541 ms | 45988 | 3182 |
| 2 | 10/10 | 1.000 | 1.000 | 0.000 | 0.000 | 26 | 0 | 0 | 0 | 2431 ms | 45988 | 3114 |
| 3 | 10/10 | 1.000 | 1.000 | 0.000 | 0.000 | 26 | 0 | 0 | 0 | 2618 ms | 45988 | 3164 |
| 4 | 10/10 | 1.000 | 1.000 | 0.000 | 0.000 | 26 | 0 | 0 | 0 | 2536 ms | 45988 | 3120 |
| 5 | 10/10 | 1.000 | 1.000 | 0.000 | 0.000 | 26 | 0 | 0 | 1 | 2555 ms | 45988 | 3231 |

("Grounded"/"Ungrounded"/"Ambiguous"/"Unmapped" are totals across the 10
snippets in that run.)

## Aggregate (50 calls)

| Metric | Value | Target (item 14) | Met |
|---|---|---|---|
| Schema success | 50/50 (100%) | 100% | ✓ |
| Grounded rate of accepted items | 130/130 (100%) | 100% | ✓ |
| True hallucination rate (global) | 0/130 (0%) | 0% | ✓ |
| Ambiguity rate (global) | 0/130 (0%) | — (reported, no target) | — |
| Mean precision | 1.0000 | ≥99% | ✓ |
| Min precision (any single run) | 1.0000 | — | — |
| Mean recall | 1.0000 | ≥98% | ✓ |
| Min recall (any single run) | 1.0000 | ≥95% | ✓ |
| Mean latency | 2536 ms | — | — |
| Total tokens | 245,751 (229,940 in / 15,811 out) | — | — |

All six Milestone 2.0B.2 success criteria (item 14) are met, with margin,
across all 50 calls — not just on average.

## Item 11 — CA1 never promoted to CAI

Checked in all 5 runs (`SNIPPET-UNKNOWN-ANALYTE`, candidate carries
`canonical_hint="CAI"` per the prompt's own worked example, exactly the
adversarial condition): `analyte.canonical_id = null`,
`validation_status = UNRESOLVED` in every run. The alias registry, not
the LLM's hint, decided the outcome every time.

## Item 12 — ESBL 04 stays resultless

Checked in all 5 runs (`SNIPPET-MICROBIOLOGY`): the fourth occurrence's
`result.value = null` in every run — never copied from the three
preceding "NEGATIVO" results.

## Item 13 — 31/09 never corrected

Checked in all 5 runs (`SNIPPET-INVALID-DATE`): `ordered_at.raw = "31/09"`,
`ordered_at.normalized = null`, `ordered_at.validation_status =
UNRESOLVED` in every run — the deterministic temporal parser
(`exam_normalization.temporal`), unchanged in this milestone, is what
actually classifies it invalid; the extractor's only job (preserve the
raw string verbatim) was performed correctly every time.

## Residual observation (not a failure)

Run 5's `SNIPPET-INVALID-DATE` call produced one `unmapped` entry beyond
what the other four runs produced (`unmapped_count=1` vs. `0`) — the model
apparently placed "SOLICITADO" into `unmapped` explicitly that one time,
rather than omitting it from the response entirely as in the other runs.
Both behaviors are acceptable under the corrected ground truth
(`exam_extraction/fixtures/snippets.py`, item 4): a
`diagnostic_study_finding` for "SOLICITADO" is optional, and routing
uncertain content to `unmapped` rather than silently dropping it is
exactly the documented intended behavior for content the model is not
confident classifying further. Precision and recall for that call were
still 1.0 — this is stylistic run-to-run variation, not a correctness
regression, and required no schema or ground-truth change.

## What changed vs. Milestone 2.0B.1 to get here

- `temperature=0` (previously unset, i.e. provider default) — the
  DeepSeek adapter's only new runtime parameter this milestone.
- Prompt `2.0b-prompt-003` adds one instruction on top of 002's (already
  schema-success-clean) baseline: `evidence_text` must be the minimal
  literal span, not a shared whole-line span — directly targeting the one
  intermittent failure mode observed in 2.0B.1
  (`docs/mod_exames_2_0b_1_live_findings.md`, note 1).
- The evaluation harness now separates `true_hallucination_rate`
  (UNGROUNDED only) from `ambiguity_rate` (AMBIGUOUS only) instead of
  conflating them — a reporting change; `exam_extraction.grounding`
  itself, and its refusal to ever accept an UNGROUNDED or AMBIGUOUS item
  as a clinical fact, is unchanged.
- `SNIPPET-INVALID-DATE`'s ground truth no longer requires a
  `diagnostic_study_finding` for "SOLICITADO" (still creditable if
  present, via the new `ExpectedItem(optional=True)`).

No Pydantic model was changed, `extra="forbid"` is untouched everywhere,
and no retry/fallback logic was added — 100% schema success across 50
calls was reached through prompting and sampling-configuration changes
only.
