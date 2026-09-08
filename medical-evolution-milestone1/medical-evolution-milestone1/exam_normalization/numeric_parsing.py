"""Deterministic numeric value parsing (Milestone 2.0A, items 7–8).

Produces `models.medical_state.ObservationValue`, always preserving
`raw_value` and `operator` exactly — `>4000` is never collapsed to `4000`.
"""

from __future__ import annotations

import re
from typing import Optional

from models.medical_state import ComparisonOperator, ObservationValue

_OPERATOR_PATTERN = re.compile(r"^(<=|>=|<|>|=)\s*(.+)$")

_OPERATOR_BY_TOKEN = {
    "<": ComparisonOperator.LT,
    ">": ComparisonOperator.GT,
    "<=": ComparisonOperator.LTE,
    ">=": ComparisonOperator.GTE,
    "=": ComparisonOperator.EQ,
}

# Analytes conventionally shorthanded with a "K" (thousands) suffix in this
# project's source material (item 8). Deliberately small and explicit —
# there is no universal rule that "anything ending in K" means *1000.
_K_SUFFIX_SAFE_CANONICAL_IDS = {"PLAQ", "LC"}

_PLAIN_NUMBER_PATTERN = re.compile(r"^-?\d+(?:[.,]\d+)?$")
_K_SUFFIX_PATTERN = re.compile(r"^(-?\d+(?:[.,]\d+)?)[kK]$")


def parse_plain_number(text: str) -> Optional[float]:
    """Parse a number that carries at most one decimal separator (comma OR
    dot), covering both pt-BR ("0,72") and dot-decimal ("13.6") styles. A
    value using both (e.g. thousands-grouped "1.234,56") is ambiguous
    without a documented convention for this source, so it is left
    unparsed rather than guessed at — raw_value/display_value still
    preserve it exactly."""
    text = text.strip()
    if not text:
        return None
    has_comma = "," in text
    has_dot = "." in text
    if has_comma and has_dot:
        return None
    if text.count(",") > 1 or text.count(".") > 1:
        return None
    candidate = text.replace(",", ".") if has_comma else text
    try:
        return float(candidate)
    except ValueError:
        return None


def parse_numeric_value(raw: str, canonical_id: Optional[str] = None) -> ObservationValue:
    """Parse one raw exam value into a strict `ObservationValue`.

    `canonical_id` (already alias-resolved, item 6) gates the K-suffix rule
    (item 8): "253K" only becomes 253000 for analytes where that shorthand
    is a known-safe convention; everywhere else the trailing "K" is simply
    left unparsed (normalized_numeric_value=None), never guessed at.
    """
    raw = raw.strip()
    operator: Optional[ComparisonOperator] = None
    remainder = raw

    match = _OPERATOR_PATTERN.match(raw)
    if match:
        operator = _OPERATOR_BY_TOKEN[match.group(1)]
        remainder = match.group(2).strip()

    normalized_numeric_value: Optional[float] = None

    k_match = _K_SUFFIX_PATTERN.match(remainder)
    if k_match and canonical_id in _K_SUFFIX_SAFE_CANONICAL_IDS:
        base = parse_plain_number(k_match.group(1))
        if base is not None:
            normalized_numeric_value = base * 1000
    elif _PLAIN_NUMBER_PATTERN.match(remainder):
        normalized_numeric_value = parse_plain_number(remainder)

    return ObservationValue(
        raw_value=raw,
        operator=operator,
        normalized_numeric_value=normalized_numeric_value,
        display_value=raw,
    )
