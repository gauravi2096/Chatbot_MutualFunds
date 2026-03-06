# Deployment

## Streamlit Cloud (recommended)

The project runs as a **single Streamlit application** that provides both the UI and backend logic (RAG, Groq, fund selection, chat, source links, timestamps). Deploy it on [Streamlit Community Cloud](https://share.streamlit.io/) so the app is runnable entirely on Streamlit Cloud—no separate API server or Vercel deployment is required.

### Steps

1. **Connect to Streamlit Cloud** and select this repo and branch (`main`).

2. **App settings**
   - **Main file path**: `streamlit_app.py`
   - **Working directory**: leave empty (repo root).

3. **Secrets**: Add `GROQ_API_KEY` (and optionally `GROQ_MODEL`).

4. **Deploy** — Data files are read from the repo; keep them updated (e.g. daily-data-update workflow).

### Local run

```bash
pip install -r requirements.txt
export GROQ_API_KEY=your_key
streamlit run streamlit_app.py
```

---

## FastAPI (optional, for Phase 3 frontend)

The REST API and Phase 3 frontend are unchanged. To run or deploy them locally or on a separate server:

- **Local**: `python3 phase_2/run_api.py` (see phase_2/README.md). Open http://localhost:8000/ for the frontend.
- **Production**: Deploy `phase_2/api:app` (e.g. with uvicorn) on Railway, Render, Fly.io, or similar. Use the same `requirements` as before (phase_0, phase_1, phase_2) and set `GROQ_API_KEY`.
