"""
Phase 2 — Groq integration: send prompt to Groq LLM and return generated text.
"""

import os
import logging
from pathlib import Path
from typing import List, Optional

from groq import Groq

from phase_2.config import GROQ_API_KEY, GROQ_MODEL, PROJECT_ROOT

logger = logging.getLogger(__name__)

_env_loaded = False


def _load_dotenv_once() -> None:
    """Load .env from project root once per process so GROQ_API_KEY is set regardless of startup."""
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    _env_file = PROJECT_ROOT / ".env"
    if not _env_file.is_file():
        return
    try:
        with open(_env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip()
                    if v and ((v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'"))):
                        v = v[1:-1]
                    os.environ.setdefault(k, v)
    except Exception as e:
        logger.warning("Could not load .env: %s", e)


def get_groq_client() -> Optional[Groq]:
    """Return Groq client if API key is set, else None. Loads .env once if present."""
    _load_dotenv_once()
    key = (os.environ.get("GROQ_API_KEY") or GROQ_API_KEY or "").strip()
    if not key:
        logger.warning("GROQ_API_KEY not set; skipping LLM call. Set it in .env or environment.")
        return None
    return Groq(api_key=key)


def chat_completion(
    messages: List[dict],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> Optional[str]:
    """
    Call Groq chat completion. messages is a list of {"role": "system"|"user"|"assistant", "content": "..."}.
    Returns the assistant message content, or None on failure.
    """
    client = get_groq_client()
    if not client:
        logger.warning("GROQ_API_KEY not set; skipping LLM call")
        return None
    model = model or GROQ_MODEL
    try:
        # Groq SDK accepts max_tokens (some versions use max_completion_tokens; try both via kwargs)
        response = client.chat.completions.create(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not response.choices:
            logger.warning("Groq returned no choices")
            return None
        content = getattr(response.choices[0].message, "content", None)
        out = (content or "").strip()
        if not out:
            logger.warning("Groq returned empty content")
        return out if out else None
    except Exception as e:
        logger.exception("Groq chat completion failed: %s", e)
        return None
