# MOD-EXAMES 2.0C.1 — Engine A Hardening After HOLDOUT-001

This milestone hardens deterministic infrastructure and observability in
response to the real generalization problems `HOLDOUT-001` (Milestone
2.0C) found. Per the milestone instructions, Engine A itself is
unchanged: provider, model, prompt, temperature, and clinical aliases are
frozen exactly as validated in 2.0B.2/2.0C. **`HOLDOUT-001` formally
stops being a held-out validation set after this milestone** — every
result produced against it from now on, including the regression run in
this report, carries no more evidentiary weight as "unseen data"; it is
a regression set.

## Item 11 — duplicate sources: still not deduplicated (unchanged capability gap)

Milestone 2.0C's finding stands and is explicitly **not** addressed here,
by instruction: `H001-DOPPLER-MMII-20260728-A` and its deliberate
duplicate `H001-DOPPLER-MMII-20260728-B-DUPLICATE` describe the same
clinical event (one Doppler exam) but arrive as two distinct source
documents. The deterministic pipeline has no cross-source
clinical-content deduplication — `apply_exam_batch`'s idempotency keys on
`source_id` among other fields (Milestone 2.0A/2.0A.1), so two documents
describing the same performed study are never recognized as the same
fact; each is preserved as its own, independently correct extraction
(see `docs/mod_exames_2_0c_holdout_findings.md`, "Duplicate-source
behavior").

No deduplicator was built in 2.0C, and none is built here. This is
recorded, again, as a **future requirement of state/event
reconciliation** — the general problem of recognizing that two different
source documents (different `source_id`s, potentially different
providers, different transcriptions) can refer to one real clinical
event and should collapse to one entry in `MedicalState` rather than two.

This is explicitly **not** the same problem as Engine A vs. Engine B
reconciliation (comparing two providers' extractions of the *same*
source), which belongs to a later milestone once a Provider B exists.
Cross-source event reconciliation is needed even with Engine A alone,
whenever the same real-world exam is represented by more than one
document. The two problems should not be designed together: one is about
trusting two competing interpretations of identical input, the other is
about recognizing that non-identical input describes the same fact.

## Regression protocol (item 13)

See `tests/holdout/run_regression_holdout_001.py` and
`tests/holdout/results/holdout_001_post_hardening_regression_results.json`
for the full per-source, per-run data, and
`tests/holdout/results/observability/holdout_001_post_hardening/` for the
per-(source, run) observability artifacts (item 8). Results and analysis
are in the Final Report section below, added once the regression run
completed.
