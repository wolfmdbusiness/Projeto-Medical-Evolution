"""Idempotency support (Milestone 2.0A, item 19; hardened in Milestone
2.0A.1, item 1).

No database. The conceptual key is `module + module_version + source_id +
category + item_key`, narrowed to one item within a batch by that item's
own `source_order` and category (two different lab lines from the same
source are different items, so they need different keys).

The key is carried on the item itself as `processing_key` -- a plain field,
not a marker hidden inside `source_refs` -- and mirrored into
`Provenance.processing_metadata` when the item is applied to a
`MedicalState` (see `exam_normalization.apply`). `source_refs` is reserved
for clinical/document source ids only; it must never carry a processing or
idempotency marker.
"""

from __future__ import annotations

from models.medical_state import ProcessingMetadataEntry

MOD_EXAMES_MODULE = "MOD-EXAMES"

# Milestone 2.0A.1: this is still the deterministic core / normalization
# pipeline, pre-real-LLM-integration -- the "a1" (alpha 1) segment reflects
# that stage, not a completed 2.0 release.
MOD_EXAMES_MODULE_VERSION = "2.0.0a1"


def build_idempotency_key(
    source_id: str,
    category: str,
    item_key: str,
    module: str = MOD_EXAMES_MODULE,
    module_version: str = MOD_EXAMES_MODULE_VERSION,
) -> str:
    """A deterministic key for one normalized item: reprocessing the exact
    same source with the exact same module version must always produce the
    exact same key for "the same" item."""
    return f"{module}:{module_version}:{source_id}:{category}:{item_key}"


def build_processing_metadata_entry(
    source_id: str,
    category: str,
    item_key: str,
    module: str = MOD_EXAMES_MODULE,
    module_version: str = MOD_EXAMES_MODULE_VERSION,
) -> ProcessingMetadataEntry:
    """Build both the key and its associated `ProcessingMetadataEntry` in
    one call, so callers never construct the two out of sync."""
    key = build_idempotency_key(source_id, category, item_key, module, module_version)
    return ProcessingMetadataEntry(
        processing_key=key, source_id=source_id, module=module, module_version=module_version,
    )
