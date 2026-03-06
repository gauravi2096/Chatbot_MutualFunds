# E2E tests — INDmoney Fund Chatbot

End-to-end tests for the full RAG chatbot flow: retrieval, context, response format, and guardrails.

## What is verified

- **Health**: `GET /health` returns ok.
- **Factual queries** (NAV/AUM, expense ratio, returns/risk): Response has `message`, `source_url` (INDmoney fund link), and `last_data_update` (date + 12h am/pm). Source link matches the retrieved fund. If the LLM is available (valid `GROQ_API_KEY`), the message content is checked for factual data.
- **Advisory query**: Request like "Which fund should I invest in?" receives a redirect message (factual-only, no advice); response still includes `last_data_update` (and `source_url` when retrieval runs).
- **Out-of-scope query**: Unknown fund or unsupported question still returns valid shape and timestamp; message indicates no data or inability to answer.

## Run

Backend must be running (e.g. `python3 phase_2/run_api.py`).

```bash
# From project root
python3 tests/e2e_chatbot_test.py
```

Optional: set base URL.

```bash
CHATBOT_BASE_URL=http://localhost:8000 python3 tests/e2e_chatbot_test.py
```

## Requirements

- Backend running with Phase 1 data (funds.json, chroma, source_registry) and Phase 2 API.
- For full LLM content checks: set `GROQ_API_KEY` in the environment (or in `.env`) before starting the server. If the key is missing or invalid, factual tests still pass for response shape, source link, and timestamp; the script notes "LLM unavailable".
