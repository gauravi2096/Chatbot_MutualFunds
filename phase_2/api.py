"""
Phase 2 — API layer: REST chat endpoint for the INDmoney fund chatbot.
Serves Phase 3 frontend at / when present.
"""

import json
import os
import logging
from pathlib import Path
from typing import Optional

# Load .env from project root before any phase_2 imports that read config (e.g. GROQ_API_KEY)
_project_root = Path(__file__).resolve().parent.parent
_env_file = _project_root / ".env"
if _env_file.is_file():
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                _k, _v = _k.strip(), _v.strip()
                if _v and ((_v.startswith('"') and _v.endswith('"')) or (_v.startswith("'") and _v.endswith("'"))):
                    _v = _v[1:-1]
                os.environ.setdefault(_k, _v)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from phase_0.source_registry import load_registry
from phase_1.config import REGISTRY_PATH, FUNDS_JSON
from phase_2.orchestration import chat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PHASE_3_DIR = PROJECT_ROOT / "phase_3"

app = FastAPI(
    title="INDmoney Mutual Funds Chatbot API",
    description="Factual Q&A over INDmoney fund data. Every response includes a source link and last data update timestamp.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    message: str = Field(..., min_length=1, max_length=2000, description="User question (factual only)")
    fund_id: Optional[str] = Field(None, max_length=200, description="Optional selected fund ID to scope the answer to that fund")


class ChatResponse(BaseModel):
    """Response: assistant message + one source link + last data update timestamp."""

    message: str = Field(..., description="Assistant reply (factual only)")
    source_url: str = Field(..., description="One clickable INDmoney fund page link")
    last_data_update: str = Field(..., description="Timestamp of last data update (date + 12h am/pm)")


@app.get("/health")
def health():
    """Health check."""
    return {"status": "ok"}


@app.get("/funds")
def get_funds():
    """Return the list of funds (fund_id, fund_name, source_url) for the selection UI."""
    registry = load_registry(REGISTRY_PATH)
    return [
        {"fund_id": s.fund_id, "fund_name": s.fund_name, "source_url": str(s.url)}
        for s in registry.sources
    ]


@app.get("/last-update")
def get_last_update():
    """Return the last data update timestamp (from source registry, else funds.json)."""
    registry = load_registry(REGISTRY_PATH)
    ts = registry.last_data_update or ""
    if not ts and FUNDS_JSON.exists():
        try:
            data = json.loads(FUNDS_JSON.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("last_updated"):
                ts = data["last_updated"]
        except Exception:
            pass
    return {"last_data_update": ts}


@app.post("/chat", response_model=ChatResponse)
def post_chat(request: ChatRequest) -> ChatResponse:
    """
    Send a user message and get a factual answer with source link and timestamp.
    Advisory or non-factual queries receive a short redirect message; source_url and last_data_update are still returned.
    """
    query = request.message.strip()
    if not query:
        raise HTTPException(status_code=400, detail="message must be non-empty")

    result = chat(query=query, fund_id=request.fund_id)
    return ChatResponse(
        message=result["message"],
        source_url=result.get("source_url", ""),
        last_data_update=result.get("last_data_update", ""),
    )


if PHASE_3_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(PHASE_3_DIR), html=True), name="frontend")
