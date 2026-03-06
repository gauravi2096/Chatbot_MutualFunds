"""
Phase 1 — Structured store: persist fund records (one per fund) to JSON.
"""

import json
from pathlib import Path
from typing import List, Optional

from phase_0.schema import FundRecord

from phase_1.config import FUNDS_JSON


def load_funds(path: Optional[Path] = None) -> List[FundRecord]:
    """Load all fund records from JSON. Returns empty list if file missing."""
    p = path or FUNDS_JSON
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("funds", data.get("records", []))
    return [FundRecord.model_validate(obj) for obj in items]


def save_funds(
    records: List[FundRecord],
    path: Optional[Path] = None,
    last_updated: Optional[str] = None,
) -> None:
    """Persist fund records to JSON. Optionally include top-level last_updated (date + 12h am/pm)."""
    p = path or FUNDS_JSON
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = [r.model_dump(mode="json") for r in records]
    if last_updated is not None:
        payload = {"last_updated": last_updated, "funds": payload}
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
