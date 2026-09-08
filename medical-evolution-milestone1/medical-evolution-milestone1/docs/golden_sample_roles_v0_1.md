# Golden Sample Roles v0.1 (Milestone 1.2)

Every fixture under `golden_samples/` plays exactly one of three roles.
The role decides how strict its test is — never how the fixture itself is
built.

## STRICT_RENDER_REFERENCE

The rendered document must match `golden_00X_expected.txt` **byte-for-byte**.
This is the canonical visual contract of the renderer + template: any
change to it must be a deliberate, reviewed decision, never a side effect
of a schema/renderer change.

- **GOLDEN-001** is the only `STRICT_RENDER_REFERENCE` today.
- Test: `tests/test_golden_001.py` (exact string equality against
  `golden_001_expected.txt`).

## SEMANTIC_RENDER_REFERENCE

The fixture preserves the **facts, structure, and behavior** of a real
(de-identified) case, but its test suite never compares the whole document
byte-for-byte. Instead, each test asserts a specific, named behavior (a
field's value, a status, a rendered substring) — see item 35 of the
Milestone 1.2 request for the exact list per case.

This role exists because Milestone 1.2 introduces or exercises schema
capabilities (temporal precision, consultation grouping, procedure/result
status, etc.) using real-world shapes that GOLDEN-001 never had reason to
contain. Locking their *entire* rendered text would make the fixture as
brittle as a STRICT one while carrying none of its "this is the one true
visual contract" purpose.

- **GOLDEN-002 through GOLDEN-008** are `SEMANTIC_RENDER_REFERENCE`.
- Tests: `tests/test_golden_00X_semantic.py`.

## AUDIT_CASE

An overlay on top of a `SEMANTIC_RENDER_REFERENCE` case (never on its own):
the fixture deliberately contains known, real inconsistencies from the
source material — a contradiction between two fields, an ambiguous event
order, a stale statement superseded by a later note. These are recorded as
plain metadata (`golden_00X_audit_notes.json`), not corrected in the fixture
and not resolved by any code in this milestone.

See `docs/audit_findings_v0_1.md` for the taxonomy used to classify each
known issue, and `tests/test_audit_case_metadata.py` for the (deliberately
thin) test that keeps the metadata itself well-formed.

- **GOLDEN-003, GOLDEN-004, GOLDEN-005, GOLDEN-007, GOLDEN-008** carry
  `AUDIT_CASE` metadata in addition to being `SEMANTIC_RENDER_REFERENCE`.
- **GOLDEN-002 and GOLDEN-006** have no recorded audit findings.

No auditor is implemented in Milestone 1.2. The metadata's only purpose is
to make future auditing testable against real examples without forcing a
"fix" of the underlying case today.
