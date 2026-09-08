"""Deterministic analyte alias resolution (Milestone 2.0A, item 6; hardened
in Milestone 2.0A.1, item 2).

Only aliases already evidenced by the Golden Samples are included. Anything
not explicitly listed here, and not already a known standalone canonical id,
resolves to `None` -- the safe default is "do not guess", never "assume it
is already canonical". This is what keeps a case like "CA1" (calcium,
ionized, one specific lab's shorthand) from being silently accepted as if it
were "CAI" (the canonical id this project already uses elsewhere): "CA1" is
in neither `ALIAS_REGISTRY` nor `KNOWN_CANONICAL_IDS`, so it resolves to
`None` and the observation is classified UNRESOLVED rather than silently
treated as valid.

`raw_name` on the candidate/observation is never touched by this module --
only `canonical_id` is derived from it, and it may legitimately be `None`.
"""

from __future__ import annotations

from typing import Optional

# key: alias as written in the source (upper-cased); value: canonical_id.
# Identity entries (e.g. "PLAQ": "PLAQ") are listed for clarity, not
# strictly required since a name already in KNOWN_CANONICAL_IDS resolves to
# itself anyway.
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

# Canonical ids that are legitimate on their own -- never aliased from
# anything else -- evidenced by the Golden Samples and existing tests. A
# raw_name that exactly matches one of these (after upper-casing) is already
# canonical; it does not need an ALIAS_REGISTRY entry to be accepted.
KNOWN_CANONICAL_IDS: frozenset[str] = frozenset({
    # General labs / chemistry
    "HB", "HT", "HEMOGLOBINA", "HEMACIAS", "NA", "K", "MG", "CA", "CAI", "CR", "UR",
    "TGO", "TGP", "GGT", "CPK", "CKMB", "PCR", "DDIMERO", "BETA_HCG",
    "GLICOSE", "BILIRRUBINA",
    # Hemogram indices excluded from headline display but still valid ids
    "VCM", "HCM",
    # Coagulation
    "INR",
    # Platelets / leukocytes
    "PLAQ", "LC", "LEUCOCITOS",
    # Urinalysis
    "ASPECTO", "COR", "DENSIDADE", "PROTEINAS", "CETONA", "UROBILINOGENIO",
    "CELULAS", "BACTERIAS", "CILINDROS", "CRISTAIS", "FILAMENTOS_DE_MUCO",
    # Blood gas
    "PH", "PCO2", "PO2", "SATO2", "HCO3", "BE", "CO2_TOTAL",
    # Troponin
    "TROPONINA",
})


def resolve_canonical_id(raw_name: str) -> Optional[str]:
    """Look up `raw_name` in the alias registry, then in the known-canonical
    set; return `None` when neither applies.

    `None` is the deliberate, explicit "unresolved" signal (Milestone
    2.0A.1, item 2) -- callers must treat it as a reason to mark the
    observation UNRESOLVED, never fall back to treating `raw_name` as if it
    were already a valid canonical id.
    """
    key = raw_name.strip().upper()
    if key in ALIAS_REGISTRY:
        return ALIAS_REGISTRY[key]
    if key in KNOWN_CANONICAL_IDS:
        return key
    return None
