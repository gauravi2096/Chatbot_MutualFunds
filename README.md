# Fin

[![Daily data update](https://github.com/gauravi2096/Chatbot_MutualFunds/actions/workflows/daily-data-update.yml/badge.svg)](https://github.com/gauravi2096/Chatbot_MutualFunds/actions/workflows/daily-data-update.yml)

Fin answers factual questions about 10 HDFC mutual funds listed on INDmoney. Every answer carries a source link and a data timestamp, and it declines anything shaped like advice.

---

## Who this is for, and the problem

A retail investor comparing mutual funds has two options: read the KIM/SID documents to find one number, or ask a distributor who's paid a commission to sell a particular fund. The first is slow. The second has a conflict of interest built in — the person answering has a reason to steer the answer.

The same problem shows up on the support side, in brief: content and support teams field the same factual questions repeatedly, and every answer risks drifting from fact into advice.

Fin only answers what's askable as fact, from retrieved data — there's no recommendation step in the pipeline to steer an answer. Every answer is cited and timestamped so it's checkable against the source.

---

## Walking through Fin

It opens with a greeting and three starter cards: NAV & AUM, Expense ratio, Compare funds.

A plain factual question gets one line, one link, one timestamp:

> The expense ratio of HDFC Flexi Cap Fund is 0.75%.
> View source on INDmoney · Data as of Aug 05, 2026 12:45 pm

Ask a question that doesn't name a fund — "what's the expense ratio?" — in "All funds" mode, and Fin doesn't guess. It asks: "Which fund would you like to know about?" with a grid of all 10 funds. Earlier, queries like this were answered silently, using whichever fund's data happened to embed closest to the query — an assumption presented as fact, the same failure category as hallucination, just one layer down, at retrieval instead of generation. Explicit fund-detection before retrieval now catches this instead of guessing.

Ask it to compare two funds without naming both, and the same picker becomes multi-select instead. Tap a fund to select it — it highlights, checkmarked. Tap a second, and a "Compare X and Y" button appears. This used to be broken: the picker was single-select even for comparison queries, so picking one fund submitted immediately instead of waiting for a second pick. Tapping a third fund now swaps out the older selection, instead of requiring an explicit deselect first. The resulting answer carries two separately labeled source links, one per fund — that was also a bug: it used to show one link standing in for both.

Ask something advice-shaped — "should I invest in HDFC Value Fund" — and Fin declines instead of hedging:

> I'm happy to help you learn more about investing, but I'd like to point you in the direction of some helpful resources first... If you have any specific questions about HDFC funds, such as their expense ratios or NAVs, I'd be happy to help you find the answers.

This refusal used to only fire on exact phrasing like "should I buy," and broke on any rephrasing. The trigger set was broadened. Separately, the refusal text itself moved out of a hardcoded string and into the LLM's system instructions, so it reads as a redirect rather than a canned rejection. The link changed too — from a fund page (the same one the question had just been refused for) to an actual investor-education resource.

Try to hand it personal information — tested with a PAN number — and it refuses that too, plainly:

> This chatbot cannot accept, store, or process any personal or financial information such as PAN, Aadhaar, account numbers, OTPs, email addresses, or phone numbers. Please do not share such details here.

Both refusals still carry a source link and timestamp. The response format holds even when the answer is "no."

After the first real answer, Fin asks for a name, once:

> Glad that helped! What should I call you, so I'm not just 'hey there' every time?

This used to ask upfront, before delivering any value. It's asked after the first successful answer instead now. It comes up once or twice a session at most, and isn't persisted beyond it.

---

## Honest limitations

- **Corpus is sourced from INDmoney's public fund pages, not directly from AMC/SEBI/AMFI filings.** INDmoney is itself aggregating this data; Fin doesn't go to the primary regulatory source.
- **No ELSS fund in the corpus** — lock-in-period questions aren't answerable for any of the 10 funds.
- **No cross-session memory.** Names and conversation context live in Streamlit session state only and disappear when the session ends — nothing about a user persists across visits.

---

## What I'd build next

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
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` | Groq model name |
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
