# INDmoney Mutual Funds Chatbot

A factual, non-advisory RAG chatbot that answers questions about 10 HDFC mutual funds on INDmoney. Every response includes one clickable source link to the relevant fund page and a last data update timestamp (date + 12-hour time, am/pm).

Built with Groq for LLM generation, ChromaDB for vector search, and Playwright for live data scraping.

## Features

- **Factual answers only**: No investment advice, recommendations, or personalized guidance.
- **RAG over live fund data**: Scrapes INDmoney fund pages, embeds structured records, and retrieves relevant context per query.
- **Mandatory source attribution**: Every reply includes a link to the INDmoney fund page and when the data was last updated.
- **Two deployment options**: Streamlit app (recommended) or FastAPI backend with a static HTML frontend.
- **Daily data refresh**: GitHub Actions workflow scrapes and commits updated fund data every morning at 10:00 AM IST.

## Supported data

The chatbot can answer factual questions about these fields for each of the 10 funds:

| Category | Fields |
|----------|--------|
| Identity & valuation | Fund Name, NAV, NAV Date, Daily % Change |
| Size & cost | AUM, Expense Ratio |
| Investment terms | Min Investment (Lumpsum/SIP), Exit Load, ELSS Lock-in |
| Returns | 1Y/3Y/5Y CAGR, Since Inception |
| Allocation | Equity %, Debt + Cash %, Market Cap Split |
| Holdings & risk | Top Holdings, Risk Level, Benchmark |

## Quick start (Streamlit)

The simplest way to run the app locally or deploy to [Streamlit Community Cloud](https://share.streamlit.io/):

```bash
pip install -r requirements.txt
export GROQ_API_KEY=your_groq_api_key
streamlit run streamlit_app.py
```

For Streamlit Cloud, set `GROQ_API_KEY` (and optionally `GROQ_MODEL`) in App settings → Secrets. Main file path: `streamlit_app.py`.

See [DEPLOYMENT.md](DEPLOYMENT.md) for full deployment instructions.

## Alternative: FastAPI + HTML frontend

Run the REST API and serve the Phase 3 chat UI from the same server:

```bash
pip install -r phase_0/requirements.txt -r phase_1/requirements.txt -r phase_2/requirements.txt
export GROQ_API_KEY=your_groq_api_key
python phase_2/run_api.py
```

Open http://localhost:8000/ in a browser. API endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/funds` | List supported funds |
| GET | `/last-update` | Last data update timestamp |
| POST | `/chat` | Send a message; returns `{ message, source_url, last_data_update }` |

## Data ingestion

Fund data is scraped from INDmoney and stored in `phase_1/data/funds.json` with a ChromaDB vector index at `phase_1/data/chroma/`.

Run ingestion manually:

```bash
pip install -r phase_0/requirements.txt -r phase_1/requirements.txt
playwright install chromium
python phase_1/run_ingestion.py
```

Or use the Phase 4 daily update script:

```bash
python phase_4/run_daily_update.py
```

A GitHub Actions workflow (`.github/workflows/daily-data-update.yml`) runs this automatically at 10:00 AM IST and commits updated data to the repo.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes (for LLM) | — | Groq API key |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model name |
| `RAG_TOP_K` | No | `5` | Number of chunks to retrieve |
| `API_HOST` | No | `0.0.0.0` | FastAPI bind host |
| `API_PORT` | No | `8000` | FastAPI bind port |

Without `GROQ_API_KEY`, the API still returns retrieved context with source link and timestamp, but skips LLM generation.

## Supported funds

All 10 funds are HDFC schemes on INDmoney:

1. HDFC Infrastructure Fund
2. HDFC Mid Cap Fund
3. HDFC Small Cap Fund
4. HDFC Flexi Cap Fund
5. HDFC Value Fund
6. HDFC Dynamic Debt Fund
7. HDFC Low Duration
8. HDFC Gold ETF FoF
9. HDFC Hybrid Equity Fund
10. HDFC Equity Savings Fund

Base URL: `https://www.indmoney.com/mutual-funds/...`

## Project structure

```
├── streamlit_app.py          # Streamlit app (UI + backend, recommended entry point)
├── requirements.txt          # Root deps for Streamlit Cloud
├── ARCHITECTURE.md           # Phase-wise system design
├── DEPLOYMENT.md             # Deployment guide
├── phase_0/                  # Data schema, source registry, update timestamp rules
├── phase_1/                  # Scraper, validation, structured store, vector store, retriever
├── phase_2/                  # FastAPI backend, Groq integration, orchestration
├── phase_3/                  # Static HTML/CSS/JS chat frontend
├── phase_4/                  # Daily data update scheduler
└── tests/                    # E2E chatbot tests
```

Each phase has its own README with detailed setup and usage:

- [Phase 0 — Foundation & Data Contract](phase_0/README.md)
- [Phase 1 — Data Ingestion & RAG Pipeline](phase_1/README.md)
- [Phase 2 — Backend (API & Groq)](phase_2/README.md)
- [Phase 3 — Frontend (Chat UI)](phase_3/README.md)
- [Phase 4 — Daily Scheduler](phase_4/README.md)

## Testing

End-to-end tests verify the full chat flow (response shape, source links, timestamps, guardrails):

```bash
# Start the API first
python phase_2/run_api.py

# In another terminal
python tests/e2e_chatbot_test.py
```

See [tests/README.md](tests/README.md) for details.

## Requirements

- Python 3.10+
- Groq API key
- Playwright + Chromium (for data ingestion only)

## Disclaimer

This chatbot provides factual information only. It does not offer investment advice, recommendations, or personalized guidance. Always verify data on the linked INDmoney source page before making decisions.
