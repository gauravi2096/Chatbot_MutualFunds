# Phase 1 — Data Ingestion & RAG Pipeline

Ingest live data from the 10 INDmoney fund pages, validate against Phase 0 schema, persist to structured store, and build a vector index for retrieval. Run on-demand (Phase 4 adds daily automation).

## Components

| Component | Module | Description |
|-----------|--------|-------------|
| **Scraper / fetcher** | `scraper.py` | Fetch fund pages with **Playwright** (JS rendering), parse HTML (BeautifulSoup), extract fields via regex/text patterns |
| **Validation** | `validation.py` | Validate raw dicts into Phase 0 `FundRecord`; log failures |
| **Structured store** | `structured_store.py` | Load/save fund records to `data/funds.json` |
| **Document preparation** | `documents.py` | Convert `FundRecord` to text chunks (field: value) for embedding |
| **Embedding** | `vector_store.py` | Uses sentence-transformers (all-MiniLM-L6-v2) via ChromaDB |
| **Vector store** | `vector_store.py` | ChromaDB persistent collection for similarity search |
| **Retriever** | `retriever.py` | Query vector store; return top-k chunks + source URL + last_data_update |

## Setup

From project root:

```bash
pip install -r phase_0/requirements.txt
pip install -r phase_1/requirements.txt
playwright install chromium
```

Ensure `phase_0/data/source_registry.json` exists (Phase 0). Playwright needs the Chromium browser installed (`playwright install chromium`).

## Run ingestion (on-demand)

```bash
# From project root
python phase_1/run_ingestion.py
```

This will:

1. Load the source registry (10 URLs).
2. Scrape each page, extract fields, validate to `FundRecord`.
3. Save all valid records to `phase_1/data/funds.json`.
4. Rebuild the ChromaDB index at `phase_1/data/chroma/`.
5. Update `phase_0/data/source_registry.json` with `last_data_update` (12h am/pm).

Exit code 0 if at least one fund was ingested, 1 otherwise.

## Using the retriever

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

from phase_1.retriever import Retriever

retriever = Retriever()
out = retriever.retrieve("What is the NAV and expense ratio of HDFC Mid Cap Fund?")
print(out["source_url"])         # One clickable source link
print(out["last_data_update"])   # Timestamp for responses
for c in out["chunks"]:
    print(c["text"][:200], c["source_url"])
```

## Config

- `phase_1/config.py`: paths (`FUNDS_JSON`, `CHROMA_DIR`, `REGISTRY_PATH`), `TOP_K`, HTTP timeout and User-Agent.

## Scraper notes

Scraping uses **Playwright** (Chromium) so JS-rendered content is fully loaded before extraction. The ingestion script reuses a single browser and page for all 10 URLs. Extraction uses regex and text patterns keyed to the current INDmoney page structure; if the site markup or copy changes, adjust patterns in `scraper.py`.

## Output

- **Structured data**: `phase_1/data/funds.json`
- **Vector index**: `phase_1/data/chroma/`
- **Last update timestamp**: in `phase_0/data/source_registry.json` (`last_data_update`)

Daily automation is added in Phase 4 (scheduler).
