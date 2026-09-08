"""Deterministic, schema-derived structure guide for the extraction prompt
(Milestone 2.0B.1, item 3).

Prompt 001's failures (documented in
`docs/mod_exames_2_0b_live_findings.md`) came from a hand-written example
that only showed one bucket's shape (`general_labs`) and let the model
generalize it to every other bucket, which has different, incompatible
fields. The fix here is not to hand-write a longer description (a second,
maintained-by-hand taxonomy that can silently drift from
`exam_extraction.models` the moment either one changes) -- it is to render
`ExamExtractionCandidate.model_json_schema()` itself into compact text.

This module has no clinical judgement and no bucket-specific knowledge: it
is a generic JSON-schema-to-text walker. Every bucket's shape it prints is
exactly what Pydantic itself would enforce, so the guide and the actual
validator can never disagree.
"""

from __future__ import annotations

from typing import Any

from exam_extraction.models import ExamExtractionCandidate

# Leaf fields that exist in the schema but are populated by our own code
# after the extractor has already returned (grounding/offsets), never by
# the extractor itself. This is a fixed, narrow exclusion list applied
# uniformly to whatever fields the schema actually has -- it does not
# describe bucket shapes (that stays 100% schema-derived) and cannot drift
# into a parallel taxonomy of its own.
#
# Milestone 2.0C.1 replaced char_start/char_end + grounding_status with a
# richer support/localization model (matching_spans, support_status,
# localization_status) -- all still system-populated, so the excluded set
# grows with them. This keeps render_schema_guide()'s output, and
# therefore Prompt 003's literal text, byte-identical across that change:
# the prompt was never supposed to ask the model to fill in grounding
# results in the first place.
_SYSTEM_POPULATED_FIELDS = frozenset({
    "char_start", "char_end", "matching_spans", "support_status", "localization_status",
})


def _resolve_ref(ref: str, defs: dict[str, Any]) -> dict[str, Any]:
    name = ref.rsplit("/", 1)[-1]
    return defs[name]


def _type_text(prop_schema: dict[str, Any], defs: dict[str, Any]) -> str:
    if "$ref" in prop_schema:
        target = _resolve_ref(prop_schema["$ref"], defs)
        if "enum" in target:
            return " | ".join(repr(v) for v in target["enum"])
        return target.get("title", prop_schema["$ref"].rsplit("/", 1)[-1])

    if "anyOf" in prop_schema:
        parts = [_type_text(sub, defs) for sub in prop_schema["anyOf"]]
        # de-duplicate while preserving order (e.g. two branches both "null")
        seen: list[str] = []
        for p in parts:
            if p not in seen:
                seen.append(p)
        return " | ".join(seen)

    schema_type = prop_schema.get("type")
    if schema_type == "array":
        return f"array<{_type_text(prop_schema['items'], defs)}>"
    if schema_type == "object":
        return "object"
    if schema_type == "null":
        return "null"
    if schema_type:
        return schema_type
    return "any"


def _object_lines(object_schema: dict[str, Any], defs: dict[str, Any], indent: int, visited: frozenset[str]) -> list[str]:
    lines: list[str] = []
    required = set(object_schema.get("required", []))
    pad = "  " * indent
    for field_name, prop_schema in object_schema.get("properties", {}).items():
        if field_name in _SYSTEM_POPULATED_FIELDS:
            continue
        marker = "required" if field_name in required else "optional"
        lines.append(f"{pad}- {field_name}: {_type_text(prop_schema, defs)} ({marker})")

        nested_ref = None
        if "$ref" in prop_schema:
            nested_ref = prop_schema["$ref"]
        elif prop_schema.get("type") == "array" and "$ref" in prop_schema.get("items", {}):
            nested_ref = prop_schema["items"]["$ref"]

        if nested_ref:
            target = _resolve_ref(nested_ref, defs)
            if "properties" in target and nested_ref not in visited:
                lines.extend(_object_lines(target, defs, indent + 1, visited | {nested_ref}))
    return lines


def render_schema_guide() -> str:
    """A compact, deterministic, indented text rendering of
    `ExamExtractionCandidate.model_json_schema()` -- every bucket, every
    field, every required/optional marker, derived programmatically. Two
    calls always produce byte-identical output for the same schema."""
    schema = ExamExtractionCandidate.model_json_schema()
    defs = schema.get("$defs", {})

    lines = ["ExamExtractionCandidate:"]
    lines.extend(_object_lines(schema, defs, indent=1, visited=frozenset()))
    return "\n".join(lines)
