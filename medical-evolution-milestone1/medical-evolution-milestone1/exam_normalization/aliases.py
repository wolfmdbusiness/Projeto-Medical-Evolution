"""Deterministic analyte alias resolution (Milestone 2.0A, item 6).

Only aliases already evidenced by the Golden Samples are included. Anything
not explicitly listed here passes through unchanged — the safe default is
"do not correct", never a guess. This is what keeps a case like "CA1"
(calcium, ionized, one specific lab's shorthand) from being silently
rewritten to "CAI" (the canonical id this project already uses elsewhere):
"CA1" is not in the registry, so it resolves to itself.

`raw_name` on the candidate/observation is never touched by this module —
only `canonical_id` is derived from it.
"""

from __future__ import annotations

# key: alias as written in the source (upper-cased); value: canonical_id.
# Identity entries (e.g. "PLAQ": "PLAQ") are listed for clarity, not
# strictly required since the fallback is already identity.
ALIAS_REGISTRY: dict[str, str] = {
    "LEUCO": "LC",
    "LEUCOCITOS": "LC",
    "LEUCÓCITOS": "LC",
    "LC": "LC",
    "PLQ": "PLAQ",
    "PLAQ": "PLAQ",
    "RNI": "INR",
    "INR": "INR",
    "U": "UR",
    "UR": "UR",
    "AST": "TGO",
    "TGO": "TGO",
    "ALT": "TGP",
    "TGP": "TGP",
}


def resolve_canonical_id(raw_name: str) -> str:
    """Look up `raw_name` in the alias registry; fall back to the
    upper-cased raw name itself when there is no known-safe alias.

    This fallback is the entire mechanism behind "never normalize an
    ambiguous alias without a safe rule" — an unlisted name is left exactly
    as written (upper-cased for comparison consistency), never guessed at.
    """
    key = raw_name.strip().upper()
    return ALIAS_REGISTRY.get(key, key)
