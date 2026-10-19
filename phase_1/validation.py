"""
Phase 1 — Validation: validate scraped data against Phase 0 FundRecord schema, then
apply a quality gate so an almost-empty scrape is rejected instead of overwriting good data.
Log failures and return validated records or None.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from phase_0.schema import FundRecord

logger = logging.getLogger(__name__)

# Scraped data fields: everything except identity and the ingestion timestamp (19 fields).
_NON_DATA_FIELDS = {"fund_id", "fund_name", "source_url", "scraped_at"}
DATA_FIELDS = tuple(name for name in FundRecord.model_fields if name not in _NON_DATA_FIELDS)
MIN_POPULATED_FIELDS = 10
# For these a numeric 0 is a real value (the NAV did not move), so only None counts as unpopulated.
_ZERO_IS_VALUE = {"daily_pct_change"}


def is_populated(value: Any) -> bool:
    """False for None, empty text, "N/A" and numeric zero (the scraper's placeholders)."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in ("", "N/A")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    return True


def count_populated(record: FundRecord) -> int:
    """How many of the data fields hold a real value."""
    return sum(
        (getattr(record, name) is not None) if name in _ZERO_IS_VALUE else is_populated(getattr(record, name))
        for name in DATA_FIELDS
    )


def check_record_quality(record: FundRecord) -> Optional[str]:
    """Return why a record is unusable (NAV missing or zero, too few fields), or None if it is fine."""
    if not is_populated(record.nav):
        return "NAV is missing or zero"
    populated = count_populated(record)
    if populated < MIN_POPULATED_FIELDS:
        return f"only {populated}/{len(DATA_FIELDS)} data fields populated (minimum {MIN_POPULATED_FIELDS})"
    return None


def validate_fund_record(raw: Dict[str, Any]) -> Tuple[Optional[FundRecord], Optional[str]]:
    """
    Validate a raw scraped dict into a FundRecord and check its quality.
    Returns (FundRecord, None) on success, (None, error_message) on failure.
    """
    try:
        # Coerce source_url to str if already str (Pydantic HttpUrl accepts str)
        if "source_url" in raw and raw["source_url"]:
            raw = {**raw, "source_url": str(raw["source_url"])}
        record = FundRecord.model_validate(raw)
    except Exception as e:
        msg = str(e)
        logger.warning("Validation failed for fund_id=%s: %s", raw.get("fund_id"), msg)
        return None, msg
    problem = check_record_quality(record)
    if problem:
        logger.warning("Rejected record for fund_id=%s: %s", raw.get("fund_id"), problem)
        return None, problem
    return record, None


def validate_batch(raw_list: List[Dict[str, Any]]) -> Tuple[List[FundRecord], List[Tuple[str, str]]]:
    """
    Validate a list of raw dicts. Returns (valid_records, list of (fund_id, error) for failures).
    """
    valid: List[FundRecord] = []
    errors: List[Tuple[str, str]] = []
    for raw in raw_list:
        record, err = validate_fund_record(raw)
        if record is not None:
            valid.append(record)
        else:
            errors.append((raw.get("fund_id", "?"), err or "unknown"))
    return valid, errors
