"""
Phase 1 — Validation: validate scraped data against Phase 0 FundRecord schema.
Log failures and return validated records or None.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from phase_0.schema import FundRecord

logger = logging.getLogger(__name__)


def validate_fund_record(raw: Dict[str, Any]) -> Tuple[Optional[FundRecord], Optional[str]]:
    """
    Validate a raw scraped dict into a FundRecord.
    Returns (FundRecord, None) on success, (None, error_message) on failure.
    """
    try:
        # Coerce source_url to str if already str (Pydantic HttpUrl accepts str)
        if "source_url" in raw and raw["source_url"]:
            raw = {**raw, "source_url": str(raw["source_url"])}
        record = FundRecord.model_validate(raw)
        return record, None
    except Exception as e:
        msg = str(e)
        logger.warning("Validation failed for fund_id=%s: %s", raw.get("fund_id"), msg)
        return None, msg


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
