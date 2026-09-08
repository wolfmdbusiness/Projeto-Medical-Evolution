"""Deterministic temporal parsing for raw exam text (Milestone 2.0A, item 10).

Reuses the `TemporalValue` model unchanged (`models.medical_state`) — this
module only adds the missing direction: parsing the DD/MM-style strings raw
exam text actually contains ("31/08", "31/08 (13:20)", "31/08/2026") into
that model. `rendering.text_utils.parse_clinical_datetime` already covers
the ISO direction (formatting an already-normalized value for display) and
is intentionally left untouched — these are different directions of the
same round trip, not a duplicate of the same logic.

An impossible calendar date ("31/09") is never corrected: `raw` is kept
verbatim, `normalized` stays unset, and `validation_status` is `UNRESOLVED`
so a gate-checked field the renderer or apply layer consumes will refuse to
silently treat it as valid — see docs/audit_findings_v0_1.md for the exact
precedent this follows (established for GOLDEN-003's "31/09").
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from typing import Optional

from models.medical_state import TemporalPeriod, TemporalPrecision, TemporalValue, ValidationStatus

# DD/MM, DD/MM/YY(YY), optionally followed by "(HH:MM)".
_DATE_PATTERN = re.compile(
    r"^(?P<day>\d{1,2})/(?P<month>\d{1,2})(?:/(?P<year>\d{2,4}))?"
    r"(?:\s*\((?P<hour>\d{1,2}):(?P<minute>\d{2})\))?$"
)

# A permissive proxy year used only to check day/month plausibility when no
# real year is known (so 29/02 is not flagged invalid just because the true
# year is unknown) -- never used to produce a `normalized` value.
_LEAP_PROXY_YEAR = 2000


def _resolve_year(year_group: Optional[str], reference_year: Optional[int]) -> Optional[int]:
    if year_group is not None:
        year = int(year_group)
        return 2000 + year if len(year_group) == 2 else year
    return reference_year


def _is_plausible_day_month(day: int, month: int, year: Optional[int]) -> bool:
    if not (1 <= month <= 12):
        return False
    effective_year = year if year is not None else _LEAP_PROXY_YEAR
    return 1 <= day <= calendar.monthrange(effective_year, month)[1]


def parse_exam_temporal(raw: Optional[str], reference_year: Optional[int] = None) -> TemporalValue:
    """Parse a raw exam date/time string into a `TemporalValue`.

    `reference_year` is optional context (e.g. from
    `ExamSourceEnvelope.document_temporal_value`) used only to complete a
    bare "DD/MM" into a full date. It is never fabricated — when absent,
    a bare "DD/MM" simply stays `PARTIAL_DATE` with `normalized=None`.
    """
    if raw is None or not raw.strip():
        return TemporalValue(raw=raw, normalized=None, precision=TemporalPrecision.UNKNOWN, validation_status=ValidationStatus.MISSING)

    raw_stripped = raw.strip()
    match = _DATE_PATTERN.match(raw_stripped)
    if not match:
        return TemporalValue(
            raw=raw_stripped, normalized=None, precision=TemporalPrecision.UNKNOWN,
            validation_status=ValidationStatus.UNRESOLVED,
        )

    day = int(match.group("day"))
    month = int(match.group("month"))
    year = _resolve_year(match.group("year"), reference_year)
    has_time = match.group("hour") is not None

    if not _is_plausible_day_month(day, month, year):
        precision = TemporalPrecision.PARTIAL_DATE if year is None else TemporalPrecision.UNKNOWN
        return TemporalValue(
            raw=raw_stripped, normalized=None, precision=precision,
            validation_status=ValidationStatus.UNRESOLVED,
        )

    if year is None:
        # Day/month known and plausible, but no year to anchor a full date.
        return TemporalValue(
            raw=raw_stripped, normalized=None, precision=TemporalPrecision.PARTIAL_DATE,
            validation_status=ValidationStatus.MISSING,
        )

    # Final calendar-validity check (handles real leap-year edge cases now
    # that a concrete year is known).
    try:
        date(year, month, day)
    except ValueError:
        return TemporalValue(
            raw=raw_stripped, normalized=None, precision=TemporalPrecision.UNKNOWN,
            validation_status=ValidationStatus.UNRESOLVED,
        )

    if has_time:
        hour, minute = int(match.group("hour")), int(match.group("minute"))
        normalized = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00"
        precision = TemporalPrecision.DATE_TIME
    else:
        normalized = f"{year:04d}-{month:02d}-{day:02d}"
        precision = TemporalPrecision.DATE

    return TemporalValue(
        raw=raw_stripped, normalized=normalized, precision=precision,
        period=TemporalPeriod.UNSPECIFIED, validation_status=ValidationStatus.NORMALIZED,
    )
