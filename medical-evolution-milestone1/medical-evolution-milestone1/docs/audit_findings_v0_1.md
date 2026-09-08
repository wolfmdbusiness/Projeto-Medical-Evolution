# Audit Findings v0.1 (Milestone 1.2, items 36–37)

This document defines the three categories used to classify a known issue
recorded in a `golden_00X_audit_notes.json` file. **No auditor is
implemented in this milestone** — this is a taxonomy and a place to record
real examples so a future auditor can be tested against them.

The three categories are deliberately distinct and must not be conflated:

## CONTRADICTED

Two statements in the record assert **incompatible facts about the same
clinical reality**, and the incompatibility does not depend on when either
statement was made — they cannot both be true at once.

Example (GOLDEN-003): the ICU justification asserts a "queda hematimétrica
documentada" (a falling blood count), while the structured lab series for
the same window shows HB/HT rising. One of the two is simply wrong about
the same fact.

## POTENTIAL_TEMPORAL_CONFLICT

Two data points **about the same variable cannot be placed in a confident
chronological order** — not because they disagree in content, but because
the record does not give enough information (a missing or ambiguous
timestamp) to know which one is more recent.

Example (GOLDEN-003, also covered by a live test rather than only
metadata): "NA 140 às 13:20" vs. "NA 141 sem horário" on the same day — both
values may be entirely correct measurements; the record just does not let
anyone determine which came last. See item 33 / `_group_latest_by_day` in
`rendering/medical_note_renderer.py` — the renderer's answer to this
category is to show every reading rather than silently pick one.

## STALE_DOCUMENTATION

A statement was **true and correctly documented when it was written**, but
a later, clearly-dated event supersedes it, and the original was never
retracted or updated. Unlike CONTRADICTED, there is no logical
incompatibility (both were true in their own moment); unlike
POTENTIAL_TEMPORAL_CONFLICT, the chronological order between the two is
perfectly clear.

Example (GOLDEN-008): `icu_context.explicit_justifications` still describes
an active need for intensive monitorization from 27/08, while
`icu_context.requirement_status_history` records a later, clearly dated
(01/09) statement that criteria for ICU are no longer met. The older
justification is not deleted or rewritten — it is simply out of date next
to newer information.

## DIAGNOSTIC_UNCERTAINTY is not an audit category

`DIAGNOSTIC_UNCERTAINTY != CONTRADICTION != TEMPORAL_CONFLICT`.

A record holding several competing diagnostic hypotheses at once — some
`ACTIVE`, some `UNCERTAIN`, phrased with "?" or "X" ("AIT? / AVEI?", "AVCI
X AIT") — is a **normal differential diagnosis**, not a finding. Milestone
1.2 already gives this its own, correct representation
(`DiagnosisStatus.UNCERTAIN`, item 26) precisely so the system is not
tempted to treat open clinical uncertainty as a defect in the record.

This is not CONTRADICTED: the hypotheses are not asserted as simultaneously
true facts, they are alternatives under active consideration — there is
nothing for two of them to contradict.

This is not POTENTIAL_TEMPORAL_CONFLICT either: that category is about two
data points **for the same variable** whose chronological order cannot be
determined (item 33's same-day, ambiguous-timestamp lab reading). A
differential diagnosis is not "the same variable measured twice" — it is
several distinct hypotheses about a single, still-open question, and having
no explicit record of which was promoted or demoted over time is simply
what "still being investigated" looks like, not an ambiguity about event
order.

A previous audit note for GOLDEN-005 classified exactly this situation as
POTENTIAL_TEMPORAL_CONFLICT; it was removed on review (see
`golden_005_audit_notes.json`) rather than kept or swapped for an invented
replacement. An `AUDIT_CASE` fixture legitimately has **zero** confirmed
findings when nothing in it actually contradicts itself or is temporally
ambiguous — an empty `known_issues` list is a valid, honest outcome, not a
gap to be filled.

## Why the distinction matters

A future auditor that cannot tell these apart will either over-flag (every
STALE_DOCUMENTATION case looks like a CONTRADICTED one if you only diff
text) or under-flag (a genuine CONTRADICTED case gets waved off as "just
timing"). Recording real examples of each category now — even without
building the auditor — means that distinction can be tested for
correctness later instead of being designed from scratch against no data.
