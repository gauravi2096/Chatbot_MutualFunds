# Deployment

## Vercel (Phase 3 frontend)

Deploy the chat UI on [Vercel](https://vercel.com) so users can access it from a public URL. The frontend calls the **FastAPI backend** (REST API) for `/funds`, `/last-update`, and `/chat`. You must deploy the FastAPI backend separately (Railway, Render, etc.) and set its URL in Vercel.

### Prerequisites

- **FastAPI backend deployed** at a public URL (e.g. `https://chatbot-api.railway.app`). Deploy `phase_2/api:app` on Railway, Render, Fly.io, or similar. See [FastAPI](#fastapi-unchanged) below.

### Steps

1. **Connect the repo to Vercel**
   - Go to [vercel.com](https://vercel.com), sign in with GitHub.
   - Import this repository.

2. **Configure the project**
   - **Framework Preset**: Other
   - **Root Directory**: leave empty (repo root)
   - **Build Command**: `npm run build`
   - **Output Directory**: `phase_3`
   - **Install Command**: `npm install` (or leave default)

3. **Environment variable**
   - In Project Settings → Environment Variables, add:
   - **Name**: `API_BASE_URL`
   - **Value**: Your deployed FastAPI URL, e.g. `https://chatbot-api.railway.app` (no trailing slash)

4. **Deploy**
   - Trigger a deployment. The build runs `npm run build`, which writes `phase_3/config.js` with the API URL. The frontend will call your deployed backend.

### Local development

- With backend on localhost: leave `API_BASE_URL` unset or empty; `config.js` uses `""` and relative URLs work.
- With deployed backend: `API_BASE_URL=https://your-api.railway.app npm run build` then serve `phase_3/` (e.g. `npx serve phase_3`).

---

## Streamlit Cloud (primary deployment — full app)

Deploy the **entire application** (frontend UI + backend logic) on [Streamlit Community Cloud](https://share.streamlit.io/). The single Streamlit app includes: mutual fund selection, chat interface, suggestion cards, RAG pipeline, Groq LLM, source links, and last-updated timestamps. No separate FastAPI or Phase 3 frontend needed.

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
