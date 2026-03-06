"""
Phase 4 — Run the data-ingestion pipeline (for daily scheduler / GitHub Actions).

On success: refreshes structured store (funds.json), vector store (chroma),
and last_data_update in source_registry.json. On failure: logs and exits non-zero.
"""

import logging
import sys
from pathlib import Path

# Project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase_1.run_ingestion import run_ingestion
from phase_1.config import REGISTRY_PATH

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    """Run ingestion; return 0 on success, 1 on failure."""
    logger.info("Starting daily data update pipeline.")
    try:
        ok = run_ingestion(registry_path=REGISTRY_PATH)
        if ok:
            logger.info("Daily data update completed successfully.")
            return 0
        logger.error("Daily data update failed: no valid records.")
        return 1
    except Exception as e:
        logger.exception("Daily data update failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
