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
per-(source, run) observability artifacts (item 8).

---

# Final Report (item 15)

## Commit

`39f990d1e76f0e86ef7f2ce5d32d01a08a05ea95` on branch
`milestone-2.0-mod-exames`. The `HOLDOUT-001 POST-HARDENING REGRESSION`
run was executed against this exact commit (all 3 runs; `commit` field
inside the results JSON confirms it).

## Offline tests

278 offline tests pass (`pytest -q`), 25 `live`/`holdout_live` tests
deselected as before. 272 pre-existing tests continue to pass unchanged
in behavior or were updated to reflect an intentional behavior change
(see below); 7 are new: `test_request_sets_max_tokens_16384`, 4 new
`_find_observation` fallback/collision tests
(`test_tp_matches_via_unique_value_fallback_not_substring`,
`test_tfg_matches_via_unique_value_fallback_not_substring`,
`test_unique_value_fallback_never_guesses_when_ambiguous`,
`test_canonical_id_based_match_takes_priority_over_raw_name_spelling`),
`test_tp_does_not_collide_with_ttpa_via_naive_substring` (added after
the live regression surfaced the collision described below), and 6
`tests/holdout/test_observability_offline.py` tests covering item 8/12's
persisted-artifact completeness and privacy guarantees.

## GOLDEN-001

Byte-identical, both before and after every change in this milestone
(`python render_golden_001.py` diffed against
`golden_samples/golden_001/golden_001_expected.txt`).

## `max_tokens`: before / after

`4096` -> `16384` (`exam_extraction/providers/deepseek.py`). Verified by
an offline test that inspects the outgoing request body
(`test_request_sets_max_tokens_16384`). In the regression run, the
largest completion observed across all 39 calls was 7261 output tokens
(`H001-LAB-20260727`, a 24-analyte panel) — comfortably under the new
ceiling and roughly half of the *old* ceiling, so this was true
truncation, not a borderline case.

## Design: support vs. localization (items 3-4-7)

`GroundingStatus` (`GROUNDED`/`UNGROUNDED`/`AMBIGUOUS`) is replaced by
two independent properties on `Evidence`:

- `support_status`: `GROUNDED` if the evidence text exists literally
  anywhere in the source, else `UNGROUNDED`. Purely mechanical, never
  reinterpreted.
- `localization_status`: `UNIQUE` (exactly one item resolves to exactly
  one occurrence), `MULTIPLE` (one item, several textually identical
  occurrences, no competing item — every span kept), or `UNRESOLVED`
  (more than one item can't be cleanly paired to occurrences — blocked).

Acceptance rule into `MedicalState`: `support_status == GROUNDED and
localization_status in (UNIQUE, MULTIPLE)`. `UNGROUNDED` or `UNRESOLVED`
routes to `unmapped`, exactly as `AMBIGUOUS` did before — the safety gate
is unchanged in strength, only in what it now correctly distinguishes.

## Repeated evidence (item 6, the actual HOLDOUT-001 fix)

A single item whose `evidence_text` legitimately appears more than once
in the source (no other item competing for it) is `GROUNDED` +
`MULTIPLE`, **accepted**, with every matching span preserved in
`Evidence.matching_spans` (never a silently chosen first/last span, never
an invented offset). This directly resolves the two 2.0C findings:

- **TC-ABDOME-PELVE**: a single finding restated once in `RESULTADO` and
  once in `CONCLUSÃO` — regression confirms `localization_multiple=3,
  accepted=16, localization_unresolved=0` on all 3 runs (previously these
  3 were blocked as ambiguous).
- **DOPPLER-MMII per-leg**: two `DiagnosticStudyCandidate`s (left leg,
  right leg) each independently containing "Sem sinais de TVP" in their
  own conclusion — hierarchical/scoped grounding (item 5) resolves each
  study's own finding within that study's own text span, so each leg's
  finding is `UNIQUE`, not `MULTIPLE`/`UNRESOLVED`. Regression confirms
  `accepted=8, localization_multiple=0, localization_unresolved=0` for
  both `H001-DOPPLER-MMII-20260728-A` and its `-B-DUPLICATE` counterpart,
  on all 3 runs (previously ~6 ambiguous per run per source).

Two competing items for one real occurrence (no legitimate way to tell
them apart) remain `UNRESOLVED` and blocked —
`test_genuinely_competing_items_still_blocked_as_localization_unresolved`
pins this down explicitly so the fix above can never regress into
"treat all ambiguity as success."

## Occurrence identity (item 6/15)

`compute_occurrence_key` now takes the full, sorted set of an item's
matching spans (`source_id:category:start1-end1,start2-end2,...`)
instead of one `(char_start, char_end)` pair, so a multi-span item (e.g.
the TC-ABDOME-PELVE finding above) gets one stable identity regardless of
re-extraction order — `test_occurrence_key_for_multi_span_items_is_order_independent`
and `test_reordering_the_same_two_candidates_yields_the_same_pair_of_spans`
cover this. `exam_normalization/orchestrator.py`'s idempotency key
derivation was updated to match.

## HOLDOUT-001 POST-HARDENING REGRESSION — results

**This is a regression run, not a new held-out validation.** 3 runs x 13
sources = 39 live `deepseek-v4-flash` calls, `2.0b-prompt-003`,
`temperature=0`, against commit `39f990d1e76f0e86ef7f2ce5d32d01a08a05ea95`.
Full data: `tests/holdout/results/holdout_001_post_hardening_regression_results.json`;
per-call artifacts: `tests/holdout/results/observability/holdout_001_post_hardening/`.

### Truncation (item 9 of the checklist)

**Zero.** All 39 calls returned `finish_reason="stop"` and `status=SUCCESS`
(compare to the original blind run, where `H001-LAB-20260726` and at
least one other large panel hit `PROVIDER_FAILURE` at exactly
`output_tokens=4096`). The two largest panels that previously truncated
now complete at 5379-5389 (`H001-LAB-20260726`) and 7216-7261
(`H001-LAB-20260727`) output tokens.

### Grounded / ungrounded (aggregate across 39 calls, 720 total grounding records)

| Metric | Count |
|---|---|
| `grounded` (support=GROUNDED) | 720 |
| `ungrounded` | 0 |
| `accepted` (reaches `MedicalState`) | 696 |
| `localization_multiple` (accepted, >1 span) | 9 |
| `localization_unresolved` (blocked) | 24 |

Zero `UNGROUNDED` items across all 39 calls: every piece of cited
evidence text was literally present in its source, every run. The 24
`UNRESOLVED` items are entirely concentrated in one source
(`H001-DOPPLER-CAROTIDAS-20260728`, 8 per run x 3 runs = 24) — see
"Remaining limitations" below; this is a real, still-blocked case, not a
regression of the safety gate.

### Localization multiple / unresolved by source (stable across all 3 runs)

| Source | grounded | accepted | loc_multiple | loc_unresolved |
|---|---|---|---|---|
| H001-TC-ABDOME-PELVE-20260728 | 16 | 16 | 3 | 0 |
| H001-DOPPLER-CAROTIDAS-20260728 | 10 | 2 | 0 | 8 |
| all 11 other sources | (unaffected) | = grounded | 0 | 0 |

### Semantic hallucinations adjudicated

`semantic_hallucination_status = "NOT_ADJUDICATED"` for all 39 calls, as
designed (item 9): with 0 `UNGROUNDED` items and no human clinical
adjudication performed as part of this regression, there is no basis to
report a `semantic_hallucination_rate`, and none is presumed.

### Histórico -> atual (historical-as-current contamination)

Zero hits across all 39 calls (`historical_as_current_hits: []`
everywhere) — no source's old/historical value was ever promoted as the
current one.

### Pending -> performed

Zero cases of a pending/requested study being marked as performed
(`pending_marked_performed: false` on every run of
`H001-PENDING-HOLTER-20260724`, the one pending-item source in this set).

### Unsafe normalizations

Zero (`unsafe_normalization_hits: []` on every run, every source) — every
accepted value traces back to its own cited evidence text.

### Precision / recall (evaluator-corrected)

Using the corrected `_find_observation` (canonical_id -> raw-name ->
explicit unique-value fallback, no bare substring as primary method),
aggregated over the 13 sources (run 1; runs 2-3 identical except where
noted):

| Bucket | Captured / Expected |
|---|---|
| Current lab/coag/chem values | 69 / 70 |
| Urinalysis | 13 / 13 |
| Blood gas | 7 / 7 |
| Diagnostic-study core findings | 9 / 10 |

11 of 13 sources have `all_required_met = True` on every run. The two
that don't are analyzed below — neither is a hallucination, a safety-gate
failure, or (for one of them) even an extraction failure.

## Specific inspection: the old Run-3 instability (`H001-LAB-20260728`)

Milestone 2.0C found run 3 of this source alone produced 8 ungrounded
items and only captured 6/16 values, while runs 1-2 captured 14/16 — the
one clear run-to-run difference across the entire original 39-call
protocol. In this regression, **all 3 runs of `H001-LAB-20260728` are now
identical**: `grounded=28, ungrounded=0, accepted=28` and
`captured_current=16/16` on every run. The instability did not
reproduce. This is consistent with (though not conclusively proven to be
caused by) the truncation fix: the original run 3's 8 ungrounded items
were plausibly a truncated/malformed completion under the old 4096
ceiling being partially parsed, and this source now completes at
3422-3450 output tokens, well under both ceilings.

## A real bug the live regression caught (and fixed before finalizing this report)

The first pass of this regression showed `H001-LAB-20260728` and
`H001-COAG-20260729` each "missing" their `TP` (Tempo de Atividade de
Protrombina) value, even though the observability artifacts showed the
value was correctly extracted, grounded, and normalized. Root cause: the
evaluator's raw-name substring fallback used a bare `in` containment
check, and `"TP"` is a literal character substring of `"Tempo (TTPa)"`
(`"TTPa"` contains the letters `T`, `P` adjacent) — an entirely different
analyte (Tempo de Tromboplastina Parcial Ativada). The substring tier
matched the wrong observation before the unique-value fallback ever got
a chance to run.

Fixed in `tests/holdout/harness.py` by requiring word-boundary
containment (`_contains_as_whole_word`, using
`(?<!\w)...(?!\w)`) instead of bare substring for the raw-name fallback
tier — this is still evaluation-harness-only, per item 10; no production
alias or matching logic changed. Covered by a new regression test,
`test_tp_does_not_collide_with_ttpa_via_naive_substring`. The results
JSON in this report reflects the **corrected** harness, recomputed
offline from the already-persisted observability artifacts (no
additional live calls were needed or made).

One case remains legitimately unresolved by the evaluator even after
this fix: `H001-LAB-20260727`'s `TP=13,30` is not credited, because
`Leucócitos=13,3` in the same panel is numerically equal to `13,30` under
the harness's decimal-tolerant comparison — two different, clinically
plausible values that happen to collide, so the unique-value fallback
correctly declines to guess between them (`len(value_matches) == 2`).
The observability artifact confirms the extractor and normalizer both
handled `TP` correctly; this is purely an evaluation-harness limitation,
listed under "Remaining limitations" below.

## Observability files

- `tests/holdout/observability.py`: `build_observability_artifact` (pure,
  unit-tested) and `persist_observability_artifact` (writes one JSON per
  source/run).
- `tests/holdout/results/observability/holdout_001_post_hardening/`: 39
  artifacts (`<source_id>__run<N>.json`), one per live call in this
  regression, each carrying provider response content, parsed candidate,
  grounding result, normalized batch, evaluation-relevant metadata,
  provider/model/prompt/config, token usage, latency, and
  `finish_reason` — never a credential, header, chain-of-thought, or
  (beyond the already-deidentified `source_id`) any document content
  read directly from the envelope. `tests/holdout/test_observability_offline.py`
  proves this offline, including a decoy-secret test that fails loudly if
  a header or API key value were ever accidentally routed into an
  artifact.
- `tests/holdout/results/holdout_001_post_hardening_regression_results.json`:
  the full 39-row table, labeled `"HOLDOUT-001 POST-HARDENING REGRESSION"`.

## Remaining limitations

1. **`H001-DOPPLER-CAROTIDAS-20260728`'s 8 `UNRESOLVED` items (all 3
   runs)** are still blocked from `MedicalState`, unchanged by this
   milestone. This source's extractor output has more competing items
   than can be cleanly paired to occurrences even after hierarchical
   scoping — a genuine case item 7 requires to stay blocked, not a
   regression. Its persisted observability artifacts are available for
   manual inspection of exactly which items and spans are involved.
2. **`H001-LAB-20260727`'s `TP` credit** is blocked by a coincidental
   cross-analyte value collision (`Leucócitos=13,3` == `TP=13,30`) in the
   evaluation harness's unique-value fallback, described above — an
   evaluator limitation, not a pipeline defect.
3. **`H001-PENDING-HOLTER-20260724`'s free-text preservation is
   run-to-run unstable** (`pending_text_preserved`: False/True/False):
   run 1 and run 3's extractions omit the pending item's own
   `">> SOLICITADO (VERIFICAR SE REALIZADO)"` line entirely (run 3
   substitutes a paraphrased `extraction_warning` instead of preserving
   the literal text; run 1 omits it altogether), while run 2 correctly
   preserves it verbatim in `unmapped`. This is model output variability
   on a very short, low-signal source, consistent with the pre-existing
   stability characteristics documented in
   `docs/mod_exames_2_0b_2_stability_benchmark.md`; nothing in this
   milestone targeted or changed it, and no safety property was
   violated in any of the 3 variants (never marked performed, never
   silently dropped as if resolved).
4. **Cross-source deduplication is still not implemented** (item 11,
   restated above) — a future state/event reconciliation requirement,
   distinct from Engine A vs. Engine B reconciliation.
5. **Semantic hallucination remains permanently `NOT_ADJUDICATED`**
   without a human-in-the-loop review step; this milestone does not add
   one, by design (item 9) — `ungrounded_rate` is mechanical and
   complete, `semantic_hallucination_rate` is not.

Stop. M2.1 is not implemented. Prompt `2.0b-prompt-003` was not
modified.
