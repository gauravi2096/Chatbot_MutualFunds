# Phase 3 — Frontend (Chat UI)

Chat interface for the INDmoney Fund Chatbot. Sends user messages to the Phase 2 backend and displays answers with a clickable source link and last data update timestamp. UI follows the EchoAI-style reference: light background, lime green accents, rounded cards, and a clear disclaimer.

## Components

| Component | File | Description |
|-----------|------|-------------|
| **Chat UI** | `index.html`, `styles.css` | Header, welcome block with suggestion cards, message list, input and send button. |
| **Backend integration** | `app.js` | `POST /chat` with `{ message }`; loading state and error handling. |
| **Response display** | `app.js` | Assistant message plus “View source on INDmoney” link and “Data as of &lt;timestamp&gt;”. |
| **Guardrails** | `index.html` | Footer disclaimer: factual only, not advisory; check source link. |

## UI style (reference)

- Light gray/off-white background with subtle green gradient.
- Lime green (`#84cc16`) for primary actions (send button, links, card hover).
- Rounded corners (cards, input, bubbles); subtle shadows.
- Suggestion cards: icon, title, short description; click sends that question.
- Footer: pill-shaped input, green circular send button, small disclaimer.

## How to run

**Option A — Served by Phase 2 (recommended)**  
Start the backend; the app serves the Phase 3 folder at `/`:

```bash
export GROQ_API_KEY=your_key
python3 phase_2/run_api.py
```

Open **http://localhost:8000/** in a browser. The same origin is used for the API, so no extra config is needed.

**Option B — Standalone**  
Serve the `phase_3` folder with any static server (e.g. `python3 -m http.server 5500` in `phase_3`). Then set the API base before loading the app, e.g. in the console or by editing `index.html` to add:

```html
<script>window.API_BASE = "http://localhost:8000";</script>
<script src="app.js"></script>
```

Ensure the Phase 2 API is running on port 8000 (or the URL you set). CORS is enabled on the backend for cross-origin requests.

## Requirements

- Phase 2 backend running (for `/chat` and optional static serving).
- Modern browser (ES5-style JS, no build step).

## Response format

Every assistant reply is shown with:

1. **Message** — Factual answer from the backend.
2. **View source on INDmoney** — Link to the INDmoney fund page (opens in a new tab).
3. **Data as of &lt;date time am/pm&gt;** — Last data update timestamp.
