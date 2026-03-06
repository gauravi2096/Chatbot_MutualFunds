# Deployment

## Streamlit Cloud (chat backend UI)

Deploy the backend chat on [Streamlit Community Cloud](https://share.streamlit.io/) so users can run the same RAG + Groq pipeline in a browser. The FastAPI API (`phase_2/api.py`) is **not** modified; deploy it separately if you need REST endpoints or the Phase 3 frontend.

### Steps

1. **Push the repo to GitHub** (already done if you use this repo).

2. **Connect to Streamlit Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io/), sign in with GitHub.
   - Click **New app**, select this repository and branch (`main`).

3. **App settings**
   - **Main file path**: `streamlit_app.py`
   - **Working directory**: leave empty (repo root).
   - Streamlit Cloud will use the root `requirements.txt` by default.

4. **Secrets** (in Streamlit Cloud → your app → Settings → Secrets)
   - Add `GROQ_API_KEY` (required for LLM). Optionally `GROQ_MODEL` (default: `llama-3.3-70b-versatile`).

5. **Deploy**  
   After saving, the app will build and run. The first run may take a few minutes (sentence-transformers and Chroma are installed). Data files (`phase_1/data/funds.json`, `phase_0/data/source_registry.json`, `phase_1/data/chroma`) are read from the repo, so ensure they are committed and up to date (e.g. after the daily-data-update workflow runs).

### Local run

From project root:

```bash
pip install -r requirements.txt
export GROQ_API_KEY=your_key
streamlit run streamlit_app.py
```

---

## FastAPI (unchanged)

The REST API and Phase 3 frontend are unchanged. To run or deploy them:

- **Local**: `python3 phase_2/run_api.py` (see phase_2/README.md). Open http://localhost:8000/ for the frontend.
- **Production**: Deploy `phase_2/api:app` (e.g. with uvicorn) on Railway, Render, Fly.io, or similar. Use the same `requirements` as before (phase_0, phase_1, phase_2) and set `GROQ_API_KEY`.
