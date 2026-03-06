"""
Phase 2 — Backend configuration: Groq API, model, RAG settings.
Secrets and config from environment; no hardcoded keys.
"""

import os
from pathlib import Path

# Project root (parent of phase_2)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Groq (from env)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# RAG (delegate to Phase 1 config when needed)
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "5"))

# API
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8000"))
