"""Deterministic reference-range parsing (Milestone 2.0A, item 9).

Integrates with the existing `models.medical_state.ReferenceRange`: a
one-sided raw range like "VR <500" is valid on its own, `reference_raw`
always preserves the source text, and a bilateral range is never required.
"""

from __future__ import annotations

import re
from typing import Optional

from models.medical_state import ReferenceRange

from exam_normalization.numeric_parsing import parse_plain_number

_ONE_SIDED_PATTERN = re.compile(r"^(?:VR\s*)?(<=|>=|<|>)\s*([\d.,]+)$", re.IGNORECASE)


def parse_reference_range(raw: Optional[str]) -> Optional[ReferenceRange]:
    if raw is None or not raw.strip():
        return None
    raw_stripped = raw.strip()
    match = _ONE_SIDED_PATTERN.match(raw_stripped)
    if not match:
        # Preserve the raw text even when we cannot derive a structured
        # bound from it (item 9: a bilateral range is never required).
        return ReferenceRange(reference_raw=raw_stripped)

    operator, value_str = match.groups()
    value = parse_plain_number(value_str)
    if value is None:
        return ReferenceRange(reference_raw=raw_stripped)

    if operator in ("<", "<="):
        return ReferenceRange(reference_raw=raw_stripped, upper=value)
    return ReferenceRange(reference_raw=raw_stripped, lower=value)
