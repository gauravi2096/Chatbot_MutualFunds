"""
Phase 1 — Run ingestion on-demand: scrape all Phase 1 sources, validate,
save to structured store, rebuild vector store, update registry last_data_update.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# Project root on path for phase_0 / phase_1 imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

from phase_0.source_registry import load_registry, save_registry
from phase_0.update_timestamp import format_last_update
from phase_1.config import REGISTRY_PATH, USER_AGENT
from phase_1.documents import records_to_documents
from phase_1.scraper import scrape_fund
from phase_1.structured_store import save_funds
from phase_1.validation import validate_fund_record
from phase_1.vector_store import VectorStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def run_ingestion(registry_path: Optional[Path] = None) -> bool:
    """
    Run full ingestion: scrape -> validate -> save funds -> rebuild vector store -> update registry.
    Returns True if at least one fund was ingested and stored.
    """
    registry_path = registry_path or REGISTRY_PATH
    registry = load_registry(registry_path)
    records = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(user_agent=USER_AGENT)
            page = ctx.new_page()
            for src in registry.sources:
                logger.info("Scraping %s ...", src.fund_id)
                raw = scrape_fund(str(src.url), src.fund_id, src.fund_name, page=page)
                if not raw:
                    logger.warning("No data for %s", src.fund_id)
                    continue
                record, err = validate_fund_record(raw)
                if record is None:
                    logger.warning("Validation failed for %s: %s", src.fund_id, err)
                    continue
                records.append(record)
        finally:
            browser.close()

    if not records:
        logger.error("No valid records; skipping save and vector store update.")
        return False

    last_ts = format_last_update()
    save_funds(records, last_updated=last_ts)
    logger.info("Saved %d funds to structured store.", len(records))

    docs_meta = records_to_documents(records)
    documents = [t for t, _ in docs_meta]
    metadatas = [m for _, m in docs_meta]
    store = VectorStore()
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
