# Fin

[![Daily data update](https://github.com/gauravi2096/Chatbot_MutualFunds/actions/workflows/daily-data-update.yml/badge.svg)](https://github.com/gauravi2096/Chatbot_MutualFunds/actions/workflows/daily-data-update.yml)

Fin answers factual questions about 10 HDFC mutual funds listed on INDmoney — NAV, expense ratio, AUM, exit load, returns, holdings, risk level, benchmark. Every reply includes a source link and a data timestamp, and it refuses anything that drifts into advice.

---

## The problem

Retail investors comparing mutual fund schemes have two options: read the KIM/SID documents to find one number, or ask a distributor who's paid a commission to sell a particular fund. The first is slow, the second has a conflict of interest built in.

The same problem shows up on the support side. Content and support teams field the same factual questions repeatedly — "what's the expense ratio," "what's the exit load" — and each answer carries compliance exposure the moment it drifts from fact into advice ("I'd go with this one").

Fin only answers what's askable as fact. Every answer is cited and timestamped so it's checkable against the source. There's no recommendation step in the pipeline, so there's nothing to bias — it refuses advice-shaped questions by design, not by accident.

---

## What I built

- **Single-fund and multi-fund factual queries** — ask about one fund, or ask a factual comparison across two ("compare expense ratios of X and Y"); both are answered from retrieved context, not the model's own judgment.
- **Mandatory source citation + timestamp on every reply** — each response carries one link back to the INDmoney fund page and the last data-refresh timestamp (date + 12-hour time).
- **Intent-based advice refusal with an AMFI redirect** — questions asking which fund to buy, "which is better," or for a recommendation are refused and redirected to an AMFI investor-education page instead of a dead end.
- **Ambiguous-fund clarification** — in "All funds" mode, a question that doesn't name a fund ("what's the expense ratio?") triggers a clarifying question with a fund picker instead of guessing which fund was meant.
- **Deferred, session-only personalization** — Fin asks for a name once, after the first successful answer instead of on the landing screen, and never persists it beyond the session.
- **Daily automated data refresh** — a GitHub Actions workflow re-scrapes all 10 fund pages every morning at 10:00 AM IST and commits the updated structured data and vector index back to the repo.

---

## PM thinking — key decisions

### Decision 1 — Audited the RAG choice after the fact, not before

ChromaDB went in early, before I'd tested whether this corpus actually needed semantic search. Auditing the data later made the gap obvious: each fund's page is one block of structured fields (NAV, AUM, expense ratio, exit load) that a keyed lookup could serve just as well as a vector search. Rather than retrofit a justification for the architecture I'd already built, I documented the gap in the limitations below. RAG earns its place once the corpus expands to unstructured content — fund manager commentary, scheme notes — which is the direction I'd take it next.

### Decision 2 — A refusal that generalizes, not just matches keywords

The first version only fired on exact phrasing ("should I buy") and broke on any rephrasing. I broadened the trigger phrase list, and moved the refusal response itself out of a hardcoded string and into the LLM's system instructions. I also changed the refusal's link from a fund page — the same one the question was refused for — to an AMFI investor-education page.

### Decision 3 — Closing the one gap where the bot broke its own promise

Testing surfaced that ambiguous queries in "All funds" mode were being silently answered using whichever fund's data happened to embed closest to the query — an assumption presented as fact, the same failure category as hallucination, just at the retrieval layer instead of generation. I added explicit fund-detection before retrieval runs: if a query in "All funds" mode doesn't name a fund, it now triggers a clarifying question with a fund picker instead of a guess.

### Decision 4 — Scoped the corpus on purpose, documented what's out

None of the 10 HDFC funds in the corpus are ELSS funds, so lock-in-period questions aren't answerable — the schema has a field for it, but every fund's value is empty. I kept the corpus at its current 10-fund lineup rather than scope-creep it to "fix" this, and named the gap in limitations rather than leaving a user to discover it by asking and getting a non-answer.

### Decision 5 — Personalization that earns its place

Asking for a name before delivering any value adds friction for nothing in return. I reordered the flow so it asks after the first successful answer instead of on the landing screen. It only asks once per session, and the name is stored in session state, never persisted.

---

## Screenshots

*Add these three screenshots to a `docs/screenshots/` folder, then paste the markdown below into this section:*

1. **Landing screen** — the hero greeting and starter-prompt cards
2. **Comparison answer** — a multi-fund factual comparison with source link and timestamp visible
3. **Refusal example** — an advice-shaped question being redirected to AMFI

```markdown
![Landing screen](docs/screenshots/landing.png)
![Comparison answer](docs/screenshots/comparison.png)
![Refusal example](docs/screenshots/refusal.png)
```

---

## Honest limitations

- **Corpus is sourced from INDmoney's public fund pages, not directly from AMC/SEBI/AMFI filings.** INDmoney is itself aggregating this data; Fin doesn't go to the primary regulatory source.
- **No ELSS fund in the corpus** — lock-in-period questions aren't answerable for any of the 10 funds.
- **RAG is currently retrieving over data that doesn't strictly need semantic search yet.** Each fund is one block of structured key-value fields; a direct lookup by fund ID would serve most queries just as well as the current vector search. See Decision 1 above.
- **No cross-session memory.** Names and conversation context live in Streamlit session state only and disappear when the session ends — nothing about a user persists across visits.

---

## What I'd build next

- **Expand the corpus with unstructured content** — fund manager commentary, scheme notes, factsheet narrative — the point at which semantic retrieval earns its place over a structured lookup.
- **Add an ELSS fund** to the lineup so lock-in questions have a real answer instead of a documented gap.
- **Cross-session memory** — recognize a returning user without re-asking for a name every session.
- **Source directly from AMC/SEBI/AMFI filings** if this needed to be more than a portfolio project.

---

## Setup / running locally

The repo ships with pre-ingested data (`phase_1/data/funds.json` and a persisted ChromaDB index at `phase_1/data/chroma/`, refreshed daily by GitHub Actions), so running the app locally doesn't require scraping anything first.

```bash
pip install -r requirements.txt

# Create a .env file in the repo root, or export directly:
export GROQ_API_KEY=your_groq_api_key

streamlit run streamlit_app.py
```

Open the local URL Streamlit prints (defaults to `http://localhost:8501`).

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|--------------|
| `GROQ_API_KEY` | Yes | — | Groq API key for LLM generation |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model name |
| `RAG_TOP_K` | No | `5` | Number of chunks retrieved per query |

### Refreshing the data manually (optional)

```bash
pip install -r phase_0/requirements.txt -r phase_1/requirements.txt
playwright install chromium
python phase_1/run_ingestion.py
```

This re-scrapes all 10 INDmoney fund pages and rebuilds `phase_1/data/funds.json` and the ChromaDB index — the same pipeline the daily GitHub Actions workflow (`.github/workflows/daily-data-update.yml`) runs automatically every morning at 10:00 AM IST.

### Supported funds

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

### Project structure

```
├── streamlit_app.py   # Streamlit app — UI + backend, the entry point
├── requirements.txt   # Deps for the Streamlit app
├── ARCHITECTURE.md    # Phase-wise system design
├── DEPLOYMENT.md      # Deployment guide
├── phase_0/           # Data schema, source registry, update-timestamp rules
├── phase_1/           # Scraper, validation, structured store, vector store, retriever
├── phase_2/           # Groq integration, intent classification, orchestration, FastAPI backend
├── phase_3/           # Static HTML/CSS/JS chat frontend (alternative to the Streamlit app)
├── phase_4/           # Daily data-update pipeline entry point
└── tests/             # Intent classification and end-to-end chatbot tests
```

### Disclaimer

Fin provides factual information only. It does not offer investment advice, recommendations, or personalized guidance. Always verify data on the linked INDmoney source page before making decisions.
