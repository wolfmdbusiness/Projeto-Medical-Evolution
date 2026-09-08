"""Stable occurrence identity (Milestone 2.0B, item 15; extended in
Milestone 2.0C.1, item 6, for items with more than one legitimate
supporting span).

Idempotency cannot depend on the order an LLM happens to return objects in
— the same source, re-extracted, may list the same items in a different
order without that being a new occurrence. What is stable across
re-extractions of the same source is *where in the source text* an item's
evidence actually sits, once evidence grounding (`exam_extraction.grounding`)
has resolved it to one or more concrete character spans.

An item with `localization_status=MULTIPLE` (its evidence legitimately
supports it from more than one place, e.g. a finding restated in a
report's body and its conclusion — item 6) is not reduced to just its
first span here: every matching span, in document order, is part of the
identity, so two re-extractions that land on the same full set of spans
agree, and an item whose span set genuinely differs (a different
occurrence) never collides with it.

This is a plain deterministic string, not a cryptographic hash — a hash
would add nothing here (there is no size, secrecy, or fixed-length need),
while the plain string stays directly readable in test failures and logs.
"""

from __future__ import annotations

from typing import Iterable


def compute_occurrence_key(
    source_id: str,
    category: str,
    spans: Iterable[tuple[int, int]],
) -> str:
    """Same source + same category + same ordered set of matching spans
    => same occurrence, regardless of list order in the extractor's
    response. A different span set (even for identical evidence text
    appearing elsewhere) => a different occurrence.

    `spans` is sorted by position before joining, so callers never need
    to pre-sort — only the *set* of spans a re-extraction lands on
    matters, not the order it happened to enumerate them in.
    """
    ordered = sorted(spans)
    span_text = ",".join(f"{start}-{end}" for start, end in ordered)
    return f"{source_id}:{category}:{span_text}"
