"""Idempotency support (Milestone 2.0A, item 19).

No database. The conceptual key is `source_id + module + module_version`,
narrowed to one item within a batch by that item's own `source_order` and
category (two different lab lines from the same source are different
items, so they need different keys). The key is carried as a marker inside
the item's own `source_refs` — a field every relevant entity already has —
so `apply_exam_batch` can recognize "this exact item was already applied"
without any external storage: reprocessing the same source is checked
against what is already sitting in `MedicalState`.
"""

from __future__ import annotations

MOD_EXAMES_MODULE = "MOD-EXAMES"
MOD_EXAMES_MODULE_VERSION = "0.1.0"

MARKER_PREFIX = "IDEMP:"


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


def idempotency_marker(key: str) -> str:
    return f"{MARKER_PREFIX}{key}"


def has_idempotency_marker(source_refs: list[str], key: str) -> bool:
    return idempotency_marker(key) in source_refs
