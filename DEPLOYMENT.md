# Deployment

## Vercel (full-stack: frontend + API)

Deploy both the **Phase 3 frontend** and the **backend API** on [Vercel](https://vercel.com) in one project. The frontend is served from the `phase_3` output; the API runs as Vercel serverless functions under `/api` (relative paths, no localhost).

### Backend (serverless)

- **`api/`** — Each file is a serverless function:
  - `api/health.py` → **GET** `/api/health`
  - `api/funds.py` → **GET** `/api/funds`
  - `api/last-update.py` → **GET** `/api/last-update`
  - `api/chat.py` → **POST** `/api/chat`
- Dependencies: `api/requirements.txt` (pydantic, chromadb, sentence-transformers, groq, etc.). Data is read from repo (`phase_0/data`, `phase_1/data`).

### Frontend (relative API base)

- Build writes `phase_3/config.js` with `window.API_BASE = "/api"` so the UI calls `/api/health`, `/api/funds`, `/api/last-update`, `/api/chat` on the same origin (relative paths).

### Steps

1. **Connect the repo to Vercel** and import this repository.

2. **Configure the project**
   - **Framework Preset**: Other
   - **Root Directory**: leave empty (repo root)
   - **Build Command**: `npm run build`
   - **Output Directory**: `phase_3`

3. **Environment variables** (Project Settings → Environment Variables)
   - **`API_BASE_URL`** = **`/api`** (so the frontend uses relative paths to the serverless API)
   - **`GROQ_API_KEY`** = your Groq API key (required for the `/api/chat` LLM)

4. **Deploy**  
   Vercel builds the frontend (phase_3) and deploys the `api/` functions. Open the deployment URL; the app will call `/api/*` on the same domain.

### Local development

- **Frontend only (calls external API):** Leave `API_BASE_URL` unset or set to your backend URL; run `npm run build` and serve `phase_3/`.
- **Full-stack on Vercel:** Use `vercel dev` from the project root to run frontend and API locally; set `API_BASE_URL=/api` so the app uses the local serverless API.

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
