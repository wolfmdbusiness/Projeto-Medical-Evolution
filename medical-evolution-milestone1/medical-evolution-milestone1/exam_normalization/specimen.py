"""Deterministic blood gas specimen type resolution (Milestone 2.0A, item 13)."""

from __future__ import annotations

from typing import Optional

from models.medical_state import GasSpecimenType

_SPECIMEN_ALIASES: dict[str, GasSpecimenType] = {
    "ARTERIAL": GasSpecimenType.ARTERIAL,
    "VENOSA": GasSpecimenType.VENOUS,
    "VENOSO": GasSpecimenType.VENOUS,
    "VENOUS": GasSpecimenType.VENOUS,
    "CAPILAR": GasSpecimenType.CAPILLARY,
    "CAPILLARY": GasSpecimenType.CAPILLARY,
}


def resolve_specimen_type(raw: Optional[str]) -> GasSpecimenType:
    if not raw:
        return GasSpecimenType.UNKNOWN
    return _SPECIMEN_ALIASES.get(raw.strip().upper(), GasSpecimenType.UNKNOWN)
