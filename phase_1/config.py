"""
Phase 1 — Configuration: paths and RAG/ingestion settings.
"""

from pathlib import Path

# Project root (parent of phase_1)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Phase 0 assets
PHASE_0_ROOT = PROJECT_ROOT / "phase_0"
REGISTRY_PATH = PHASE_0_ROOT / "data" / "source_registry.json"

# Phase 1 paths
PHASE_1_ROOT = PROJECT_ROOT / "phase_1"
DATA_DIR = PHASE_1_ROOT / "data"
FUNDS_JSON = DATA_DIR / "funds.json"
CHROMA_DIR = DATA_DIR / "chroma"
CHROMA_COLLECTION = "indmoney_funds"

# Retriever
TOP_K = 5

# HTTP
REQUEST_TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
