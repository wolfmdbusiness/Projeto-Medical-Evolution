from __future__ import annotations

from datetime import datetime
from typing import Optional

from models.medical_state import ClinicalField

# Single, predictable list of datetime shapes the Medical State can carry.
# Both format_date and format_datetime funnel through parse_clinical_datetime
# so there is exactly one place that knows how to read a state datetime.
_DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def text(field: Optional[ClinicalField]) -> str:
    if field is None or field.value is None:
        return ""
    return str(field.value).strip()


def has_value(field: Optional[ClinicalField]) -> bool:
    return bool(text(field))


def parse_clinical_datetime(raw: str) -> Optional[datetime]:
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def format_date(value: Optional[str], with_year: bool = False) -> str:
    if not value:
        return ""
    raw = value.strip()
    dt = parse_clinical_datetime(raw)
    if dt is not None:
        return dt.strftime("%d/%m/%Y" if with_year else "%d/%m")
    # Defensive fallback for ISO-looking strings that don't match any of the
    # known formats exactly (e.g. unexpected fractional seconds). We never
    # invent a time here; we only reslice the date part that is already
    # present in the raw string.
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return f"{raw[8:10]}/{raw[5:7]}/{raw[0:4]}" if with_year else f"{raw[8:10]}/{raw[5:7]}"
    return raw


def format_datetime(value: Optional[str], with_year: bool = False) -> str:
    if not value:
        return ""
    raw = value.strip()
    date_part = format_date(raw, with_year=with_year)
    if "T" in raw and len(raw) >= 16:
        return f"{date_part} ({raw[11:16]})"
    return date_part
