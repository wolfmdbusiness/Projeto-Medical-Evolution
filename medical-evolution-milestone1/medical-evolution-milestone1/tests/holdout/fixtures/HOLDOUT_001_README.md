# HOLDOUT-001 — deidentified M2.0C package

This package was assembled from real-world source material supplied for project validation.

## Privacy

The files in this package intentionally omit:
- patient name
- date of birth
- medical record / attendance / request identifiers
- insurance details
- clinician names and professional IDs
- phone, email and street address
- signatures and administrative footer data

Clinical dates, test names, values, units, historical-result columns, findings and conclusions were retained because they are required for temporal/extraction validation.

Do not add the original identified PDF/DOCX files to the repository.

## Files

- `holdout_001_sources.json`: deidentified text-only source records
- `holdout_001_ground_truth.json`: predeclared expected behavior and safety assertions
- `M2_0C_CLAUDE_INSTRUCTIONS.md`: instructions for the held-out live benchmark

## Important methodological point

The source records with prior-result columns deliberately preserve historical values. The extractor must distinguish current values from historical display values.

The duplicate venous Doppler source is deliberately preserved as a separate source to test source identity and downstream duplicate behavior.

The Holter source is deliberately only REQUESTED/PENDING.
