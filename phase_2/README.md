# Phase 2 — Backend (API & Groq Integration)

Exposes a single chat endpoint that runs RAG retrieval (Phase 1), calls Groq for generation, and returns every response with one clickable source link and the last data update timestamp.

## Components

| Component | Module | Description |
|-----------|--------|-------------|
| **API layer** | `api.py` | FastAPI app; `POST /chat` accepts `{"message": "..."}`, returns `{"message", "source_url", "last_data_update"}` |
| **Orchestration** | `orchestration.py` | Calls retriever → builds prompt (context + factual-only rules) → Groq → response shaping |
| **Groq integration** | `groq_client.py` | `chat_completion(messages)` using `GROQ_API_KEY` and `GROQ_MODEL` |
| **Response shaping** | `orchestration.py` | Every response includes `source_url` and `last_data_update`; advisory queries get a redirect message |
| **Config** | `config.py` | `GROQ_API_KEY`, `GROQ_MODEL`, `RAG_TOP_K`, `API_HOST`, `API_PORT` from env |

## Setup

From project root:

```bash
pip install -r phase_0/requirements.txt
pip install -r phase_1/requirements.txt
pip install -r phase_2/requirements.txt
```

Ensure Phase 1 ingestion has been run at least once (so the vector store and `source_registry.json` exist).

## Environment

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key (required for LLM) | — |
| `GROQ_MODEL` | Model name | `llama-3.3-70b-versatile` |
| `RAG_TOP_K` | Number of chunks to retrieve | `5` |
| `API_HOST` | Bind host | `0.0.0.0` |
| `API_PORT` | Bind port | `8000` |

## Run the API

```bash
export GROQ_API_KEY=your_groq_api_key
python phase_2/run_api.py
```

Or with uvicorn directly:

```bash
export GROQ_API_KEY=your_groq_api_key
uvicorn phase_2.api:app --host 0.0.0.0 --port 8000
```

## Endpoints

- **GET /health** — Health check; returns `{"status": "ok"}`.
- **POST /chat** — Request body: `{"message": "What is the NAV of HDFC Mid Cap Fund?"}`. Response: `{"message": "...", "source_url": "https://...", "last_data_update": "Mar 06, 2026 05:19 am"}`.

If `GROQ_API_KEY` is not set, the LLM step is skipped and the API returns a fallback message (still with `source_url` and `last_data_update` from RAG).

## Constraints

- The chatbot answers **only factual** questions about the 10 funds; no advice or recommendations.
- Advisory-style queries receive a short redirect and still include `source_url` and `last_data_update`.
