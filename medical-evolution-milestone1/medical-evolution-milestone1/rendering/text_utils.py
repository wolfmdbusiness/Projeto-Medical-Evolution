from __future__ import annotations

from datetime import datetime
from typing import Optional

from models.medical_state import ClinicalField, LabObservation, TemporalValue

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


def has_time_component(value: Optional[str]) -> bool:
    """True only when `value` is an ISO-ish string that also carries a
    time-of-day. A bare date ("2026-09-02") or an empty/None value both
    return False — used to tell "this timestamp lets us order events" apart
    from "we only know the day" (Milestone 1.2, item 33)."""
    return bool(value) and "T" in value and len(value) >= 16


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


def format_datetime(value: Optional[str], with_year: bool = False, paren_time: bool = True) -> str:
    if not value:
        return ""
    raw = value.strip()
    date_part = format_date(raw, with_year=with_year)
    if has_time_component(raw):
        time_part = raw[11:16]
        return f"{date_part} ({time_part})" if paren_time else f"{date_part} {time_part}"
    return date_part


def format_temporal(tv: Optional[TemporalValue], with_year: bool = False, paren_time: bool = True) -> str:
    """Render a TemporalValue the same way a plain ISO string was rendered
    before Milestone 1.2: prefer `normalized` (falls back to `raw` when the
    value could not be normalized, e.g. an invalid date) and never invents a
    missing time."""
    if tv is None:
        return ""
    value = tv.normalized or tv.raw
    return format_datetime(value, with_year=with_year, paren_time=paren_time)


def analyte_readings_order_is_ambiguous(observations: list[LabObservation]) -> bool:
    """Milestone 1.2, item 33: the explicit answer to "which of these same-
    analyte, same-day readings is the latest?".

    True means the system has determined it CANNOT know — at least one
    reading lacks a time-of-day, so no confident chronological order exists
    between them. Shared by the renderer (`_group_latest_by_day`) and
    Milestone 2.0A's exam normalizer so this determination is made in
    exactly one place rather than reimplemented per consumer.
    """
    return len(observations) > 1 and not all(has_time_component(o.collection_datetime) for o in observations)
