"""
Phase 1 — Data Ingestion & RAG Pipeline.

Components: scraper, validation, structured store, document preparation,
vector store, retriever. Run on-demand via run_ingestion.py.
"""

from phase_1.config import (
    CHROMA_COLLECTION,
    CHROMA_DIR,
    DATA_DIR,
    FUNDS_JSON,
    PHASE_1_ROOT,
    REGISTRY_PATH,
    TOP_K,
)
from phase_1.documents import record_to_text, records_to_documents
from phase_1.retriever import Retriever
from phase_1.scraper import extract_fund_data, fetch_html, scrape_fund
from phase_1.structured_store import load_funds, save_funds
from phase_1.validation import validate_batch, validate_fund_record
from phase_1.vector_store import VectorStore, get_embedding_function

__all__ = [
    "CHROMA_COLLECTION",
    "CHROMA_DIR",
    "DATA_DIR",
    "FUNDS_JSON",
    "PHASE_1_ROOT",
    "REGISTRY_PATH",
    "TOP_K",
    "record_to_text",
    "records_to_documents",
    "Retriever",
    "scrape_fund",
    "fetch_html",
    "extract_fund_data",
    "load_funds",
    "save_funds",
    "validate_fund_record",
    "validate_batch",
    "VectorStore",
    "get_embedding_function",
]
