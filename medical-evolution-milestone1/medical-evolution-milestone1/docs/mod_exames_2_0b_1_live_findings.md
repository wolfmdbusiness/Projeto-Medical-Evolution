# MOD-EXAMES 2.0B.1 — Prompt 002 Live Benchmark

Two independent live executions of `pytest -m live` / the same 10
synthetic snippets against DeepSeek (`deepseek-v4-flash`), comparing
prompt `2.0b-prompt-001` (Milestone 2.0B) against `2.0b-prompt-002`
(Milestone 2.0B.1). As with the 2.0B findings, these are results from
specific executions, not a determinism guarantee — a live LLM can produce
a structurally different response for the same input on different calls;
this is reported explicitly rather than smoothed over.

## Run A — paired same-session comparison (both prompts, one script, one after the other)

| Snippet | 001 status | 001 precision/recall | 002 status | 002 precision/recall |
|---|---|---|---|---|
| SNIPPET-EASY | SUCCESS | 1.00 / 1.00 | SUCCESS | 1.00 / 1.00 |
| SNIPPET-OPERATORS | SUCCESS | 1.00 / 1.00 | SUCCESS | 1.00 / 1.00 |
| SNIPPET-ALIASES | SUCCESS | 1.00 / 1.00 | SUCCESS | **0.00 / 0.00** (see note 1) |
| SNIPPET-UNKNOWN-ANALYTE | SUCCESS | 1.00 / 1.00 | SUCCESS | 1.00 / 1.00 |
| SNIPPET-GAS | EXTRACTION_SCHEMA_FAILURE | — | SUCCESS | 1.00 / 1.00 |
| SNIPPET-MICROBIOLOGY | EXTRACTION_SCHEMA_FAILURE | — | SUCCESS | 1.00 / 1.00 |
| SNIPPET-TEMPORAL-AMBIGUITY | SUCCESS | 1.00 / 1.00 | SUCCESS | 1.00 / 1.00 |
| SNIPPET-EXTERNAL | SUCCESS | 1.00 / 1.00 | SUCCESS | 1.00 / 1.00 |
| SNIPPET-DIAGNOSTIC-STUDY | EXTRACTION_SCHEMA_FAILURE | — | SUCCESS | 1.00 / 1.00 |
| SNIPPET-INVALID-DATE | EXTRACTION_SCHEMA_FAILURE | — | SUCCESS | 1.00 / **0.50** (see note 2) |

### Aggregate — Run A

| Metric | Prompt 001 | Prompt 002 |
|---|---|---|
| Schema success | 6/10 | **10/10** |
| Precision (avg over successes) | 1.00 | 0.90 |
| Recall (avg over successes) | 1.00 | 0.85 |
| Hallucination rate (avg) | 0.00 | 0.10 |
| Grounded items (total) | 15 | 22 |
| Ungrounded items (total) | 0 | 0 |
| Ambiguous items (total) | 0 | 4 |
| Avg latency | 2286 ms | 2376 ms |
| Avg input tokens | 905 | 4058 |
| Avg output tokens | 338 | 329 |

## Run B — `pytest -m live -s`, prompt 002 only, independent execution

| Snippet | Status | Precision | Recall | Hallucination |
|---|---|---|---|---|
| SNIPPET-EASY | SUCCESS | 1.00 | 1.00 | 0.00 |
| SNIPPET-OPERATORS | SUCCESS | 1.00 | 1.00 | 0.00 |
| SNIPPET-ALIASES | SUCCESS | 1.00 | 1.00 | 0.00 |
| SNIPPET-UNKNOWN-ANALYTE | SUCCESS | 1.00 | 1.00 | 0.00 |
| SNIPPET-GAS | SUCCESS | 1.00 | 1.00 | 0.00 |
| SNIPPET-MICROBIOLOGY | SUCCESS | 1.00 | 1.00 | 0.00 |
| SNIPPET-TEMPORAL-AMBIGUITY | SUCCESS | 1.00 | 1.00 | 0.00 |
| SNIPPET-EXTERNAL | SUCCESS | 1.00 | 1.00 | 0.00 |
| SNIPPET-DIAGNOSTIC-STUDY | SUCCESS | 1.00 | 1.00 | 0.00 |
| SNIPPET-INVALID-DATE | SUCCESS | 1.00 | 0.50 | 0.00 |

Schema success 10/10, 9/10 snippets at perfect precision/recall, same
single INVALID-DATE partial-recall case as Run A (note 2) — reproduced
independently, so this one is a consistent pattern rather than noise.
ALIASES was clean in this run (contrast with Run A's note 1), confirming
that failure mode is intermittent, not systematic.

## Notes

**(1) SNIPPET-ALIASES ambiguity (Run A only).** Inspecting the raw
response: in most calls the model emits a tight, per-item `evidence_text`
(e.g. `"LEUCO 8330"`), which grounds cleanly. In this one call, three
separate follow-up calls immediately after could not reproduce it, but
the failure signature (`ambiguous=4, grounded=0` for exactly the 4
general_labs items, each apparently sharing one identical `evidence_text`)
matches the model occasionally using the *entire source line* as
`evidence_text` for every item on that line, rather than each item's own
substring. Grounding correctly refused to accept 4 items claiming the one
occurrence of that full-line text as GROUNDED (item 14's count-mismatch
rule) and routed all 4 to `unmapped` instead of guessing — this is the
grounding stage working as designed, not a defect in it. The underlying
extractor behavior (loose, line-level evidence spans on some calls) is a
real, intermittent characteristic of the live model that a schema/prompt
change alone cannot fully eliminate; retrying is explicitly out of scope
for this milestone (item 17).

**(2) SNIPPET-INVALID-DATE recall=0.50 (both runs).** The model
consistently extracts the `DiagnosticStudyCandidate` itself correctly
(`raw_name="COLONOSCOPIA"`, `raw_temporal="31/09"` preserved verbatim,
never corrected — item 8 confirmed working) but does not add a
`findings[]` entry for "SOLICITADO". This is arguably a reasonable
modeling choice on the LLM's part: "SOLICITADO" reads as a procedure
status ("requested"), not a clinical finding in the same sense as
"GASTRITE ANTRAL ENANTEMATOSA LEVE" in the DIAGNOSTIC-STUDY snippet (where
the model does add a finding). The ground truth in
`exam_extraction/fixtures/snippets.py` (`EXPECTED_ITEMS["SNIPPET-INVALID-DATE"]`)
treats it as an expected finding; this may be the ground truth being
stricter than a defensible extraction, not a model error. Left as-is and
documented here rather than adjusted after seeing the result (item 31 --
ground truth should not be tuned post hoc to chase a score either).

## Schema failures eliminated

All 4 of prompt 001's root causes (`docs/mod_exames_2_0b_live_findings.md`)
were absent from every prompt-002 response inspected in both runs:
`unmapped`/`extraction_warnings` came back as proper objects, blood gas
observations were correctly nested under one panel, and
`microbiology`/`diagnostic_studies` used their own field names
(`raw_result`, `findings`) rather than the `general_labs` shape. No
Pydantic model was changed to reach this — the fix was exclusively the
prompt (schema-derived structure guide + one worked example per bucket,
`exam_extraction/schema_guide.py` + `prompts/mod_exames_2_0b_002.py`).

## Against the Milestone 2.0B.1 success criteria (item 16)

| Criterion | Target | Run A | Run B |
|---|---|---|---|
| Schema success | 10/10 | **10/10 ✓** | **10/10 ✓** |
| Grounding | 100% of accepted items | 100% (0 ungrounded; 4 correctly refused as ambiguous, not accepted) | 100% |
| Hallucination rate | 0% | 10% (driven entirely by note 1) | 0% |
| Precision | 100% | 90% (note 1) | 100% |
| Recall | ≥95% | 85% (notes 1+2) | 95% (note 2 only) |

Schema success and grounding-safety (never accepting an unresolvable
item) are met consistently in both runs. Precision/recall/hallucination
are met in Run B but not in Run A, driven by the two documented,
non-systematic cases above. Per item 16, no schema loosening and no
retry/fallback were implemented to close this gap — it is recorded as the
outcome of this milestone's actual live behavior.
