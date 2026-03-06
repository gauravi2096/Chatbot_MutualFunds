"""
Phase 2 — Backend (API & Groq Integration).

Exposes a REST chat endpoint, runs RAG retrieval, calls Groq for generation,
and enforces response format (source link + last data update timestamp).
"""

from phase_2.api import app
from phase_2.config import API_HOST, API_PORT, GROQ_MODEL, RAG_TOP_K
from phase_2.groq_client import chat_completion, get_groq_client
from phase_2.orchestration import chat, is_likely_advisory

__all__ = [
    "app",
    "chat",
    "chat_completion",
    "get_groq_client",
    "is_likely_advisory",
    "API_HOST",
    "API_PORT",
    "GROQ_MODEL",
    "RAG_TOP_K",
]
