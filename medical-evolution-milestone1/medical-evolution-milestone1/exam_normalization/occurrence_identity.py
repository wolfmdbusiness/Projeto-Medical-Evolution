"""Stable occurrence identity (Milestone 2.0B, item 15).

Idempotency cannot depend on the order an LLM happens to return objects in
— the same source, re-extracted, may list the same items in a different
order without that being a new occurrence. What is stable across
re-extractions of the same source is *where in the source text* an item's
evidence actually sits, once evidence grounding (`exam_extraction.grounding`)
has resolved it to a concrete character span.

This is a plain deterministic string, not a cryptographic hash — a hash
would add nothing here (there is no size, secrecy, or fixed-length need),
while the plain string stays directly readable in test failures and logs.
"""

from __future__ import annotations


def compute_occurrence_key(source_id: str, category: str, char_start: int, char_end: int) -> str:
    """Same source + same category + same character span => same
    occurrence, regardless of list order. A different span (even for
    identical text appearing twice) => a different occurrence."""
    return f"{source_id}:{category}:{char_start}:{char_end}"
