"""
Phase 1 — Run ingestion on-demand: scrape all Phase 1 sources, validate,
save to structured store, rebuild vector store, update registry last_data_update.

A fund whose scrape fails or is rejected by validation (after retries) keeps its previous
record from funds.json unchanged. Each run writes ingestion_status.json with one result per fund.
"""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# Project root on path for phase_0 / phase_1 imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

from phase_0.schema import FundRecord
from phase_0.source_registry import RegisteredSource, load_registry, save_registry
from phase_0.update_timestamp import format_last_update
from phase_1.config import (
    FUNDS_JSON,
    INGESTION_STATUS_JSON,
    REGISTRY_PATH,
    SCRAPE_BACKOFF_SECONDS,
    SCRAPE_RETRIES,
    USER_AGENT,
)
from phase_1.documents import records_to_documents
from phase_1.scraper import scrape_fund
from phase_1.structured_store import load_funds, save_funds
from phase_1.validation import check_record_quality, count_populated, validate_fund_record
from phase_1.vector_store import VectorStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

# Per-fund outcomes written to ingestion_status.json.
STATUS_OK = "ok"  # scraped and accepted on the first attempt
STATUS_RETRIED = "retried"  # accepted after at least one retry
STATUS_KEPT_PREVIOUS = "kept_previous"  # rejected; the previous record was kept unchanged
STATUS_DROPPED = "dropped"  # rejected and no usable previous record, so the fund is left out
FAILING_STATUSES = (STATUS_KEPT_PREVIOUS, STATUS_DROPPED)


def load_previous_records(path: Path) -> Dict[str, FundRecord]:
    """Existing records keyed by fund_id; empty if the file is missing or unreadable."""
    try:
        return {r.fund_id: r for r in load_funds(path)}
    except Exception as e:
        logger.warning("Could not read previous records from %s: %s", path, e)
        return {}


def resolve_fund(
    src: RegisteredSource,
    scrape_one: Callable[[RegisteredSource], Optional[dict]],
    previous: Dict[str, FundRecord],
    retries: int = SCRAPE_RETRIES,
    backoff: float = SCRAPE_BACKOFF_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> Tuple[Optional[FundRecord], dict]:
    """
    Scrape one fund, retrying up to `retries` more times when the fetch fails or validation
    rejects the record. If every attempt fails, fall back to the fund's previous record
    (only if that record itself passes the quality gate). Returns (record or None, status entry).
    """
    last_reason = "unknown"
    attempts = 0
    for attempt in range(1, retries + 2):
        attempts = attempt
        try:
            raw = scrape_one(src)
        except Exception as e:  # a browser error must not take the whole run down
            raw, last_reason = None, f"scrape raised {type(e).__name__}: {e}"
        else:
            if raw is None:
                last_reason = "page could not be fetched"
            else:
                record, err = validate_fund_record(raw)
                if record is not None:
                    return record, {
                        "fund_id": src.fund_id,
                        "fund_name": src.fund_name,
                        "status": STATUS_OK if attempt == 1 else STATUS_RETRIED,
                        "attempts": attempt,
                        "populated": count_populated(record),
                        "reason": last_reason if attempt > 1 else None,
                    }
                last_reason = err or "rejected"
        logger.warning("%s attempt %d/%d failed: %s", src.fund_id, attempt, retries + 1, last_reason)
        if attempt <= retries:
            sleep(backoff * attempt)

    entry = {"fund_id": src.fund_id, "fund_name": src.fund_name, "attempts": attempts, "populated": None, "reason": last_reason}
    prev = previous.get(src.fund_id)
    if prev is not None and check_record_quality(prev) is None:
        logger.error("%s: keeping previous record (scraped_at %s). Reason: %s", src.fund_id, prev.scraped_at, last_reason)
        return prev, {**entry, "status": STATUS_KEPT_PREVIOUS, "previous_scraped_at": prev.scraped_at}
    logger.error("%s: no usable previous record, leaving the fund out. Reason: %s", src.fund_id, last_reason)
    return None, {**entry, "status": STATUS_DROPPED}


def write_status(path: Path, results: List[dict]) -> None:
    """Write the per-fund results plus a count per status."""
    counts: Dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    payload = {
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": counts,
        "funds": results,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_ingestion(
    registry_path: Optional[Path] = None,
    funds_path: Optional[Path] = None,
    status_path: Optional[Path] = None,
    chroma_dir: Optional[Path] = None,
) -> bool:
    """
    Run full ingestion: scrape -> validate -> merge with previous records -> save funds ->
    rebuild vector store -> update registry last_data_update.
    Returns True if at least one fund was freshly scraped and stored. The path arguments
    default to the real data files; pass temp paths to run without touching them.
    """
    registry_path = registry_path or REGISTRY_PATH
    funds_path = funds_path or FUNDS_JSON
    status_path = status_path or INGESTION_STATUS_JSON
    registry = load_registry(registry_path)
    previous = load_previous_records(funds_path)

    records: List[FundRecord] = []
    results: List[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(user_agent=USER_AGENT)
            page = ctx.new_page()

            def scrape_one(src: RegisteredSource) -> Optional[dict]:
                logger.info("Scraping %s ...", src.fund_id)
                return scrape_fund(str(src.url), src.fund_id, src.fund_name, page=page)

            for src in registry.sources:
                record, entry = resolve_fund(src, scrape_one, previous)
                results.append(entry)
                if record is not None:
                    records.append(record)
        finally:
            browser.close()

    write_status(status_path, results)
    fresh = [r for r in results if r["status"] not in FAILING_STATUSES]
    if not fresh:
        logger.error("No freshly scraped records; skipping save and vector store update.")
        return False

    last_ts = format_last_update()
    save_funds(records, path=funds_path, last_updated=last_ts)
    logger.info("Saved %d funds to structured store (%d fresh).", len(records), len(fresh))

    docs_meta = records_to_documents(records)
    documents = [t for t, _ in docs_meta]
    metadatas = [m for _, m in docs_meta]
    store = VectorStore(persist_directory=str(chroma_dir) if chroma_dir else None)
    store.clear()
    store.add_documents(documents=documents, metadatas=metadatas)
    logger.info("Rebuilt vector store with %d documents.", len(documents))

    registry.last_data_update = last_ts
    save_registry(registry, registry_path)
    logger.info("Updated registry last_data_update: %s", registry.last_data_update)
    return True


if __name__ == "__main__":
    ok = run_ingestion()
    sys.exit(0 if ok else 1)
