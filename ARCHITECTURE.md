# RAG-Based Chatbot for INDmoney Mutual Funds — Phase-Wise Architecture

## Overview

A factual, non-advisory chatbot that answers queries about mutual fund data scraped from INDmoney fund pages. Every response includes one clickable source link and the timestamp of the last data update (date and 12-hour time with am/pm). The system uses Groq as the LLM and a RAG pipeline over structured fund data.

---

## System Constraints (All Phases)

- **Factual only**: No advice, recommendations, or personalized guidance.
- **Response format**: Every answer must include (1) one clickable source link (to the relevant INDmoney fund page), (2) last data update timestamp (date + 12-hour time, am/pm).
- **LLM**: Groq for all generation.
- **Data scope (Phase 1)**: The 10 specified INDmoney mutual fund pages only.

---

## Supported Factual Data Points (Phase 1)

| Category | Data Points |
|----------|-------------|
| Identity & valuation | Fund Name, NAV, NAV Date, Daily % Change |
| Size & cost | AUM, Expense Ratio |
| Investment terms | Min Investment (Lumpsum), Min Investment (SIP), Exit Load, ELSS Lock-in |
| Returns | 1Y CAGR, 3Y CAGR, 5Y CAGR, Since Inception |
| Allocation | Equity %, Debt + Cash %, Market Cap Split |
| Holdings & risk | Top Holdings, Risk Level |
| Reference | Benchmark |

---

## Phase-Wise Architecture

### Phase 0 — Foundation & Data Contract

**Purpose**: Define data model, sources, and update semantics before building pipelines.

| Component | Responsibility |
|-----------|----------------|
| **Data schema** | Canonical schema for all supported fields (Fund Name, NAV, NAV Date, Daily % Change, AUM, Expense Ratio, Min Lumpsum/SIP, Exit Load, 1Y/3Y/5Y CAGR, Since Inception, Equity %, Debt+Cash %, Market Cap Split, Top Holdings, Risk Level, Benchmark, ELSS Lock-in). |
| **Source registry** | List of Phase 1 URLs (10 INDmoney fund pages) with fund identifier and last-successful-update timestamp. |
| **Update timestamp** | Single “last data update” value (date + 12-hour time, am/pm) used in every chatbot response. |

**Output**: Agreed schema, source list, and rules for when “last update” is set (e.g., after a successful ingestion run; daily automation in Phase 4).

---

### Phase 1 — Data Ingestion & RAG Pipeline

**Purpose**: Ingest live data from the 10 INDmoney pages, store it in a form suitable for retrieval, and expose it to the backend.

#### 1.1 Data ingestion

| Component | Responsibility |
|-----------|----------------|
| **Scraper / fetcher** | Fetch the 10 Phase 1 INDmoney fund pages; parse and extract the supported factual fields into the canonical schema. |
| **Validation** | Validate extracted data against schema; handle missing/optional fields; log failures. |
| **Structured store** | Persist one record per fund (or per fund + date) with all supported fields and metadata (e.g., source URL, scraped-at timestamp). |

#### 1.2 RAG pipeline

| Component | Responsibility |
|-----------|----------------|
| **Document preparation** | Convert each fund record into text/chunks (e.g., “Fund Name: X, NAV: Y, …”) suitable for embedding and retrieval. |
| **Embedding** | Generate embeddings for chunks using an embedding model (e.g., via Groq or a separate embedding API). |
| **Vector store** | Store embeddings and metadata (fund ID, source URL, field names) for similarity search. |
| **Retriever** | Given a user query, run retrieval (e.g., vector search + optional keyword/filter) and return top-k chunks plus source URL and “last data update” timestamp. |

**Output**: Data ingestion and RAG pipeline that can be run on-demand (e.g., manual or scripted); structured data, vector index, and “last data update” value for responses. Daily automation is added in Phase 4.

---

### Phase 2 — Backend (API & Groq Integration)

**Purpose**: Expose a single entry point for the frontend, run RAG retrieval, call Groq for generation, and enforce response format.

| Component | Responsibility |
|-----------|----------------|
| **API layer** | REST (or equivalent) endpoint(s) for chat: accept user message (and optional session/thread id); return assistant reply. |
| **Orchestration** | For each user query: (1) call RAG retriever with query, (2) receive chunks + source URL + last-update timestamp, (3) build prompt with retrieved context + system rules (factual only, no advice). |
| **Groq integration** | Send prompt to Groq LLM; stream or return full response. |
| **Response shaping** | Ensure every response includes: (1) one clickable source link (from retrieval), (2) last data update timestamp (date + 12-hour am/pm). Reject or redirect non-factual/advisory queries per system constraints. |
| **Config & secrets** | Groq API key and any config (model name, RAG top-k) managed securely (env/config, not in code). Scheduler config (e.g., cron) added in Phase 4. |

**Output**: Backend API that returns factual answers with mandatory source link and timestamp.

---

### Phase 3 — Frontend

**Purpose**: Provide a chat UI that sends user messages to the backend and displays answers with source link and timestamp.

| Component | Responsibility |
|-----------|----------------|
| **Chat UI** | Input for user message; display conversation (user + assistant messages). |
| **Backend integration** | Send user message to backend chat API; handle loading and errors. |
| **Response display** | Render assistant message; prominently show the one clickable source link and the last data update timestamp (date, 12-hour am/pm). |
| **Guardrails (optional)** | Short disclaimer that the bot is factual only and not advisory; no input intended to solicit personalized advice. |

**Output**: Working chatbot frontend that satisfies the response-format requirements.

---

### Phase 4 — Scheduler for Daily Live Data, Hardening & Observability (Optional)

**Purpose**: Automate daily data updates and production readiness without changing core architecture.

| Component | Responsibility |
|-----------|----------------|
| **Scheduler (daily live data)** | Trigger the data-ingestion pipeline once per day (configurable time). On success: refresh structured store and vector store; update "last data update" timestamp. On failure: alert/log; optionally keep previous data and timestamp. Retries, idempotency, and clear "last update" semantics on partial failure. |
| **Monitoring** | Logs and metrics for scraper runs, RAG retrieval, Groq calls, API latency and errors. |
| **Rate limiting & auth** | Protect API and optional user/session handling. |
| **Out-of-scope handling** | When query is outside the 10 funds or supported data points, respond with a clear “factual only / no data” message and still include timestamp (and link if any). |

---

## Component Summary

| Layer | Components |
|-------|------------|
| **Frontend** | Chat UI, backend integration, response display (source link + timestamp). |
| **Backend** | API, orchestration, Groq integration, response shaping, config. |
| **RAG pipeline** | Document prep, embedding, vector store, retriever; fed by structured store. |
| **Data** | Scraper/fetcher, validation, structured store, “last data update” timestamp. |
| **Scheduler** | Daily job to run ingestion → update structured store + vector store + timestamp (introduced in Phase 4). |
| **LLM** | Groq for generation only (embedding may be Groq or separate service). |

---

## Phase 1 Data Sources (URLs)

1. HDFC Infrastructure Fund — `.../hdfc-infrastructure-fund-direct-plan-growth-option-3315`
2. HDFC Mid Cap Fund — `.../hdfc-mid-cap-fund-direct-plan-growth-option-3097`
3. HDFC Small Cap Fund — `.../hdfc-small-cap-fund-direct-growth-option-3580`
4. HDFC Flexi Cap Fund — `.../hdfc-flexi-cap-fund-direct-plan-growth-option-3184`
5. HDFC Value Fund — `.../hdfc-value-fund-direct-plan-growth-option-3623`
6. HDFC Dynamic Debt Fund — `.../hdfc-dynamic-debt-plan-direct-plan-growth-option-513`
7. HDFC Low Duration — `.../hdfc-low-duration-direct-plan-growth-option-1481`
8. HDFC Gold ETF FoF — `.../hdfc-gold-etf-fund-of-fund-direct-plan-growth-5359`
9. HDFC Hybrid Equity Fund — `.../hdfc-hybrid-equity-fund-direct-growth-option-4103`
10. HDFC Equity Savings Fund — `.../hdfc-equity-savings-fund-direct-plan-growth-option-4569`

Base URL: `https://www.indmoney.com/mutual-funds/...`

---

## Data Flow (High Level)

1. **Scheduler** (daily) → **Scraper** → **Validation** → **Structured store** → **Document prep** → **Embedding** → **Vector store**; update **last data update** timestamp.
2. **User** → **Frontend** → **Backend API** → **RAG Retriever** (query) → **Vector store** → chunks + source URL + timestamp.
3. **Backend** → **Groq** (prompt with context + rules) → **Response shaping** (add source link + timestamp) → **Frontend** → **User**.

This document describes only the phase-wise architecture; implementation details and code are out of scope.

---

## Deployment

### Streamlit Cloud (backend chat UI)

The same backend logic (Phase 1 retriever + Phase 2 orchestration + Groq) runs as a Streamlit app for deployment on Streamlit Cloud:

- **Entry point**: `streamlit_app.py` at repo root. Run with `streamlit run streamlit_app.py` (working directory = repo root).
- **Dependencies**: Root `requirements.txt` (streamlit, phase_0/1/2 deps for chat only; no Playwright or FastAPI).
- **Secrets**: Set `GROQ_API_KEY` (and optionally `GROQ_MODEL`) in Streamlit Cloud → App settings → Secrets.
- **Existing API**: The FastAPI app (`phase_2/api.py`) and all endpoints (`GET /health`, `GET /funds`, `GET /last-update`, `POST /chat`) are unchanged and can be deployed separately (e.g. Railway, Render) for the Phase 3 frontend and other API consumers.
