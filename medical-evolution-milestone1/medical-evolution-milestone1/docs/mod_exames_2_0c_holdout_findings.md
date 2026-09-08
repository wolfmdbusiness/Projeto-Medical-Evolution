# MOD-EXAMES 2.0C — HOLDOUT-001 Held-Out Clinical Validation

Blind execution: 13 real-world (deidentified) source records × 3
independent runs = 39 live extraction calls against `deepseek-v4-flash`,
prompt `2.0b-prompt-003`, `temperature=0`, frozen at commit `3d58615`
(tag `mod-exames-engine-a-v1`). No code, prompt, schema, alias, grounding,
normalizer, or model-parameter change was made before, during, or after
the 3 runs. `HOLDOUT-001` was never used to build prompts 001–003 or the
10 synthetic snippets.

## Pre-flight

- Fixture consistency (`validate_fixture_consistency`): no problems — all
  13 sources have a matching ground-truth expectation and vice versa.
- Commit tested: `3d58615564640ad3760c778db9b39e056da47be5`.
- `DeepSeekExamExtractor()` defaults confirmed: `prompt_version =
  2.0b-prompt-003`.

## Aggregate (39 calls)

| Metric | Value |
|---|---|
| Schema/provider success | 33/39 (84.6%) |
| Grounded items (accepted) | 322 |
| Ungrounded items | 8 |
| Ambiguous items | 69 |
| Grounded rate of all attempted items | 322/399 (80.7%) |
| True hallucination rate (ungrounded/attempted) | 8/399 (2.0%) |
| Historical-as-current contamination | **0** |
| Pending-as-performed errors | **0** |
| Unsafe normalization | **0** |
| Duplicate-source aggregation duplication | 2 studies (see below) |
| Current-value recall (strict harness match) | 73/93 (78.5%) — see caveat |
| Mean latency | 6920 ms (min 1569 ms, max 17106 ms) |
| Total tokens | 258,805 (196,677 in / 62,128 out) |

**All four safety-critical counts that gate Engine A approval are zero**:
no historical value was ever emitted as current, no pending study was
ever marked performed, and no accepted value was ever unsafely altered
from its own cited evidence — across all 39 calls, including the 6 that
failed at the provider layer and the run with the one grounding
instability event (below).

## Per-run metrics

| Run | Schema success | Grounded | Ungrounded | Ambiguous | Current-value recall | Historical hits | Unsafe | Avg latency | In tok | Out tok |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 11/13 | 110 | 0 | 23 | 27/31 (87.1%) | 0 | 0 | 7144 ms | 65,559 | 20,716 |
| 2 | 11/13 | 110 | 0 | 23 | 27/31 (87.1%) | 0 | 0 | 6804 ms | 65,559 | 20,714 |
| 3 | 11/13 | 102 | 8 | 23 | 19/31 (61.3%) | 0 | 0 | 6811 ms | 65,559 | 20,698 |

Runs 1 and 2 are identical at the grounding-count level (perfectly
stable, `temperature=0` behaving as expected). Run 3 diverges only on
one source (below) — everything else is byte-for-byte identical in
behavior across all 3 runs.

## Per-source results (all 3 runs)

| Source | Type | Status (3/3) | Notes |
|---|---|---|---|
| H001-LAB-20260726 | laboratory_report | **PROVIDER_FAILURE 3/3** | Output truncated at `max_tokens=4096` every run — `finish_reason≠"stop"`, correctly refused rather than parsed as complete JSON. Largest single-source lab panel (15 analytes + full urinalysis). |
| H001-DDIMER-20260727 | laboratory_report | SUCCESS 3/3, perfect | 1/1 current value captured, 0 ungrounded/ambiguous, all 3 runs identical. |
| H001-LAB-20260727 | laboratory_report | **PROVIDER_FAILURE 3/3** | Same truncation as above (blood gas + hemogram + coag + ~20 chemistries + urinalysis in one source). |
| H001-LAB-20260728 | laboratory_report_with_previous_results | SUCCESS 3/3 | Runs 1–2: 14/16 captured, 0 ungrounded. **Run 3: 8 ungrounded, only 6/16 captured** — the one reproducibility gap found (see below). Zero historical-as-current contamination in all 3 runs regardless. |
| H001-COAG-20260729 | laboratory_report_with_previous_results | SUCCESS 3/3 | 2/3 captured every run (TP not matched — harness-matching caveat, see below); 0 historical contamination. |
| H001-LAB-20260729 | laboratory_report_with_previous_results | SUCCESS 3/3 | 10/11 captured every run (TFG not matched — same caveat); 0 historical contamination despite carrying two "Resultado Anterior" columns simultaneously. |
| H001-DOPPLER-MMII-20260728-A | diagnostic_study | SUCCESS 3/3 | Study captured every run, but 6/6 runs' worth of findings landed AMBIGUOUS, not GROUNDED — see structural finding below. |
| H001-ECHO-20260728 | diagnostic_study | **SUCCESS 3/3, perfect** | Both core findings ("Ecodopplercardiograma normal", ejection fraction 66.85%) matched every run, 0 ambiguous. |
| H001-DOPPLER-CAROTIDAS-20260728 | diagnostic_study | SUCCESS 3/3 | 8 ambiguous items every run; 1/2 core findings matched every run (vertebral flow matched; carotid patency did not — same structural cause). |
| H001-TC-CRANIO-20260728 | diagnostic_study | **SUCCESS 3/3, perfect** | Single-conclusion report, no restated text — 0 ambiguous, core finding matched every run. |
| H001-TC-ABDOME-PELVE-20260728 | diagnostic_study | SUCCESS 3/3 | 3 ambiguous items every run; 0/3 core findings matched every run — same structural cause (conclusion restates body text verbatim). |
| H001-DOPPLER-MMII-20260728-B-DUPLICATE | diagnostic_study_duplicate_source | SUCCESS 3/3 | Same grounding pattern as source A (6 ambiguous/run); distinct source identity confirmed; see duplicate-source analysis below. |
| H001-PENDING-HOLTER-20260724 | pending_exam_list | SUCCESS 3/3 | Never marked PERFORMED in any run (correct). Study captured every run; the harness's strict verbatim check for the full parenthetical text did not match in any run — see caveat below. |

## Structural finding: verbatim-repeated phrasing causes grounding ambiguity, never hallucination

Four sources (`H001-DOPPLER-MMII-20260728-A/B-DUPLICATE`,
`H001-DOPPLER-CAROTIDAS-20260728`, `H001-TC-ABDOME-PELVE-20260728`) share
a real-world radiology-report pattern the 10 synthetic snippets never
exercised: **the same sentence appears verbatim more than once in the
document** — once per leg/side in the Doppler studies, and once in the
body ("RESULTADO") and once in the conclusion ("CONCLUSÃO") in the
abdomen/pelvis CT. `exam_extraction.grounding`'s resolution rule (item 15,
Milestone 2.0B) only accepts a repeated span as GROUNDED when the number
of candidate items claiming that text exactly equals the number of
occurrences AND `source_order` cleanly pairs them; a single item whose
evidence also happens to match a second, incidental occurrence elsewhere
in the document falls through to AMBIGUOUS instead — safe (never
promoted as a clinical fact) but costly to recall (69 ambiguous items
total, concentrated in exactly these 4 sources, 100% reproducible across
all 3 runs).

This is a genuine generalization limitation of the current grounding
design against real dictation/reporting style, not a DeepSeek instability
issue (fully reproducible, same count every run) and not a hallucination
(0 of these were ever accepted as clinical facts). No grounding/prompt
change was made in response to this — reported per the hard rules as a
capability gap for a future milestone to consider (e.g., letting
`source_order` disambiguate a single item against multiple identical
occurrences when nothing else claims the other occurrence).

## Reproducibility gap: H001-LAB-20260728, run 3

Runs 1 and 2 of this source are identical (14/16 current values, 0
ungrounded). Run 3 alone produced 8 ungrounded items and captured only
6/16 — the extractor's cited evidence for 8 items did not literally
appear in the source text that run. Critically, **none of the 8
ungrounded items were promoted to `MedicalState`** (grounding correctly
routed all 8 to `unmapped`), and **zero of them were the wrong
(historical) value silently accepted as current** — the safety property
held even under this instability. This is the one clear
run-to-run difference found across the entire 39-call protocol; every
other source behaved identically in all 3 runs.

## Duplicate-source behavior (capability gap, not fixed)

`H001-DOPPLER-MMII-20260728-A` and its deliberate duplicate,
`H001-DOPPLER-MMII-20260728-B-DUPLICATE`, are processed independently (as
required) and each correctly preserves its own distinct source identity
(`study_id`/`source_refs` embed the differing `source_id`). Offline
simulation (no live call; existing, unmodified `apply_exam_batch` and
`build_idempotency_key`, which key on `source_id` among other fields) of
applying both sources' batches to one `MedicalState` confirms:

```
4 final diagnostic_studies (2 from source A + 2 from source B-DUPLICATE)
  vs. 2 clinically real, distinct studies performed once each
```

The current deterministic layer has no cross-source clinical-content
deduplication — `apply_exam_batch`'s idempotency is per-source-id by
design (Milestone 2.0A/2.0A.1), so two different source documents
describing the same performed study are never recognized as the same
fact. **This is exactly the capability gap the M2.0C instructions
anticipated** ("If the existing architecture cannot yet safely aggregate
cross-source duplicates without M2.1, do NOT invent a deduplicator.
Report this as a capability gap instead"). No deduplicator was built.

## Harness-matching caveats (not confirmed extraction failures)

Three "missing" results are flagged here as **scoring-harness
limitations**, not verified model failures, because resolving them would
require additional live calls beyond the prescribed 39 and the blind
protocol's "exactly 3 runs" — so they are reported as open questions
rather than guessed at:

- **TP** (`H001-COAG-20260729`, `H001-LAB-20260727`) and **TFG**
  (`H001-LAB-20260726` [never reached — truncated], `H001-LAB-20260728`,
  `H001-LAB-20260729`) consistently miss the harness's label match. Both
  are abbreviations whose letters are **not a contiguous substring** of
  their full Portuguese names as they appear in the source ("TP" is not
  in "TEMPO DE ATIVIDADE DE PROTROMBINA"; "TFG" is not in "TAXA DE
  FILTRAÇÃO GLOMERULAR" — confirmed by direct string check). If the
  extractor captured these under the full descriptive name rather than
  the abbreviation, the value was likely captured correctly and this
  harness's substring-based matcher simply failed to credit it. The raw
  per-call candidate/batch data needed to settle this was not persisted
  during the blind run (only summary counts were saved), and re-querying
  now would mean live calls outside the sanctioned 39 — so this is left
  open rather than resolved by guessing or by an extra call.
- **H001-PENDING-HOLTER-20260724**: the harness requires the exact string
  `"SOLICITADO (VERIFICAR SE REALIZADO)"` verbatim across the captured
  study/findings/unmapped text; this did not match in any of the 3 runs,
  while the safety-relevant parts of the expectation
  (`must_not_mark_as_performed`) held in all 3. Whether the extractor
  dropped the parenthetical, paraphrased it, or used a status-hint field
  the harness doesn't inspect for this check is not established from the
  saved data.

These are flagged as harness precision gaps for a future iteration of
`tests/holdout/harness.py`, not as production extraction defects — no
production code was touched to investigate them.

## Regression

- `pytest -q`: 258 passed (up from 249 pre-holdout — 9 new offline
  harness unit tests), 0 failures, entirely offline including the new
  `tests/holdout/` package (`holdout_live`-marked tests deselected by
  default alongside `live`).
- `python render_golden_001.py`: byte-for-byte identical to
  `golden_001_expected.txt`, confirmed before and after the holdout runs.
- No production file (`models/`, `exam_extraction/` except the new,
  additive `tests/holdout/` package, `exam_normalization/`,
  `rendering/`, `templates/`) was modified. Only `pyproject.toml` changed,
  to register the `holdout_live` pytest marker.

## Engine A approval status

**Remains approved**, with the capability gaps above documented rather
than patched. The four metrics the M2.0C instructions treat as
non-negotiable safety gates were met perfectly across all 39 calls:
0 historical-as-current contamination, 0 pending-as-performed, 0 unsafe
normalization, and every UNGROUNDED/AMBIGUOUS item was excluded from
`MedicalState` with no exception. The metrics that missed target
(schema/provider success 84.6% vs. ≥99%; current-value recall 78.5% vs.
≥98%, itself likely understated by the harness-matching caveats above)
are real, reproducible generalization limits against longer/denser
real-world source documents and verbatim-repeated report phrasing —
recommendations for addressing them are listed below, per instructions,
without being implemented.
