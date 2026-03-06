"""
Phase 0 — Update timestamp: single 'last data update' value used in every chatbot response.

Format: date + 12-hour time with am/pm (e.g. "Mar 6, 2025 2:30 pm").
Rules: Set after a successful ingestion run; Phase 4 scheduler will run daily and update it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo


# Default timezone for "last data update" (India)
DEFAULT_TZ = ZoneInfo("Asia/Kolkata")

# Format: date and 12-hour time with am/pm (cross-platform)
LAST_UPDATE_DATETIME_FMT = "%b %d, %Y %I:%M %p"  # e.g. Mar 06, 2025 02:30 pm


def format_last_update(dt: Optional[datetime] = None) -> str:
    """
    Return the 'last data update' string for chatbot responses.

    Uses current time in DEFAULT_TZ if dt is not provided. In production,
    this should read the stored value from the source registry or a dedicated
    store that is updated only after a successful ingestion run.

    Args:
        dt: Time of last successful data update. If None, uses now() in DEFAULT_TZ.

    Returns:
        Formatted string, e.g. "Mar 06, 2025 02:30 pm".
    """
    if dt is None:
        dt = datetime.now(DEFAULT_TZ)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=DEFAULT_TZ)
    s = dt.strftime(LAST_UPDATE_DATETIME_FMT)
    return s.replace(" AM", " am").replace(" PM", " pm")


def parse_last_update(value: str) -> Optional[datetime]:
    """
    Parse a stored 'last data update' string back to datetime (for comparison or storage).
    """
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    # strptime %p is often locale-specific; normalize to uppercase for parsing
    for suffix in (" am", " pm"):
        if value.endswith(suffix):
            value = value[:-len(suffix)] + suffix.upper()
            break
    try:
        return datetime.strptime(value, LAST_UPDATE_DATETIME_FMT).replace(
            tzinfo=DEFAULT_TZ
        )
    except (ValueError, TypeError):
        return None


# --- Rules for when "last update" is set (documentation) ---
# 1. Set only after a successful ingestion run (all or configured subset of sources).
# 2. Do not update on partial failure; optionally keep previous value and log.
# 3. Phase 4 scheduler will trigger daily runs; each successful run updates this value.
# 4. Chatbot must include this value in every response (date + 12-hour time, am/pm).
