"""
Phase 2 — Orchestration: RAG retrieval + prompt build + Groq + response shaping.
Ensures every response includes one source link and last data update timestamp.
Handles restricted queries (advisory, sensitive info, comparisons) with polite, professional responses.
"""

import logging
import re
from typing import Optional

from phase_1.retriever import Retriever
from phase_2.groq_client import chat_completion
from phase_2.config import RAG_TOP_K

logger = logging.getLogger(__name__)

# Official source for factual fund data (used in restricted responses)
INDMONEY_BASE = "https://www.indmoney.com/mutual-funds"

SYSTEM_PROMPT = """You are a factual assistant for INDmoney mutual fund data. You answer only factual questions about the 10 listed funds (NAV, AUM, expense ratio, returns, holdings, risk, benchmark, etc.) using ONLY the context provided below.

Rules:
- Answer ONLY from the provided context. If the context does not contain the answer, say so and do not guess.
- Do NOT give investment advice, recommendations, or personalized guidance.
- Do NOT compare funds for "best" or "should I invest".
- Keep answers concise and factual. Include the fund name when citing a value.
- Do not include source links or timestamps in your answer text; they will be added separately."""


def build_messages(query: str, context_text: str, source_url: str, last_data_update: str) -> list:
    """Build system + user messages for Groq. Context and format rules are in the user message."""
    user_content = f"""Use the following context to answer the user question. Answer only from this context. Do not give advice or recommendations.

Context:
{context_text}

User question: {query}

Reply with a short, factual answer only."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# Patterns for sensitive personal/financial information (do not store or process)
_PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
_AADHAAR_PATTERN = re.compile(r"\b[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}\b")
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
# Indian mobile: 10 digits starting with 6-9, optional +91 (avoid matching AUM/NAV numbers)
_PHONE_PATTERN = re.compile(r"\b(?:\+91[\s-]?)?[6-9][0-9]{9}\b")


def contains_sensitive_info(query: str) -> bool:
    """Return True if the message appears to contain PAN, Aadhaar, email, or phone numbers."""
    if not query or len(query.strip()) < 4:
        return False
    # PAN (Indian Permanent Account Number)
    if _PAN_PATTERN.search(query):
        return True
    # Aadhaar-like 12 digits (possibly spaced)
    if _AADHAAR_PATTERN.search(query):
        return True
    # Email
    if _EMAIL_PATTERN.search(query):
        return True
    # Indian mobile number
    if _PHONE_PATTERN.search(query):
        return True
    # Keywords that often accompany sensitive data
    q = query.lower()
    if any(k in q for k in ("aadhaar", "aadhar", "pan card", "account number", "otp", "one time password")):
        return True
    return False


def is_likely_advisory(query: str) -> bool:
    """True if query asks for opinion, advice, or which fund to invest in."""
    q = query.lower().strip()
    advisory_phrases = (
        "should i invest",
        "should i buy",
        "should i sell",
        "which fund should",
        "best fund",
        "recommend",
        "advice",
        "which one to choose",
        "better to invest",
        "good for me",
        "suit my",
        "suitable for",
        "what do you think",
        "opinion on",
        "is it good to invest",
    )
    return any(p in q for p in advisory_phrases)


def is_comparison_or_recommendation(query: str) -> bool:
    """True if query asks for performance comparison, return calculations, or recommendations."""
    q = query.lower().strip()
    comparison_phrases = (
        "compare returns",
        "performance comparison",
        "which performed better",
        "calculate returns",
        "compute returns",
        "compare funds",
        "which is better",
        "best performing",
        "top performing",
        "recommend a fund",
        "suggest a fund",
    )
    return any(p in q for p in comparison_phrases)


def _restricted_response(
    message: str,
    source_url: str,
    last_data_update: str,
    rejected: bool = True,
) -> dict:
    """Return a standard response dict for restricted queries."""
    url = source_url.strip() or INDMONEY_BASE
    return {
        "message": message,
        "source_url": url,
        "last_data_update": last_data_update,
        "rejected": rejected,
    }


def chat(
    query: str,
    retriever: Optional[Retriever] = None,
    top_k: Optional[int] = None,
    fund_id: Optional[str] = None,
) -> dict:
    """
    Run RAG + Groq pipeline. Returns dict with:
      - message: assistant reply text (factual only)
      - source_url: one clickable source link (INDmoney fund page)
      - last_data_update: timestamp (date + 12h am/pm)
      - rejected: True if query was treated as restricted (advisory, sensitive, comparison)
    If fund_id is set, retrieval is scoped to that fund so answers refer to it.
    """
    retriever = retriever or Retriever()
    k = top_k or RAG_TOP_K
    fund_id_clean = (fund_id or "").strip() or None
    retrieved = retriever.retrieve(query=query, top_k=k, fund_id=fund_id_clean)
    source_url = retrieved.get("source_url", "")
    last_data_update = retrieved.get("last_data_update", "")
    chunks = retrieved.get("chunks", [])

    # Sensitive personal/financial information: do not accept or process
    if contains_sensitive_info(query):
        return _restricted_response(
            "Thank you for reaching out. This chatbot cannot accept, store, or process any personal or financial information such as PAN, Aadhaar, account numbers, OTPs, email addresses, or phone numbers. Please do not share such details here. For factual information about HDFC mutual funds (e.g. NAV, AUM, expense ratio, or returns), feel free to ask a specific question—I’ll be glad to help with that.",
            source_url,
            last_data_update,
            rejected=True,
        )

    # Opinion-based or advisory questions
    if is_likely_advisory(query):
        return _restricted_response(
            "I provide factual information only and cannot offer investment advice or personal recommendations. If you’d like, you can ask about specific data points for any of the listed funds—for example NAV, AUM, expense ratio, or returns—and I’ll answer from the available data. You can also refer to the official source link below for the latest information.",
            source_url,
            last_data_update,
            rejected=True,
        )

    # Performance comparisons, return calculations, or recommendations
    if is_comparison_or_recommendation(query):
        return _restricted_response(
            "I don’t compute or compare returns or recommend funds. For performance comparisons and accurate figures, please use the official factsheet or the source link provided below. I can still help with factual questions about a specific fund’s NAV, AUM, expense ratio, or other published data.",
            source_url,
            last_data_update,
            rejected=True,
        )

    context_text = "\n\n---\n\n".join(c.get("text", "") for c in chunks if c.get("text"))
    if not context_text.strip():
        return {
            "message": "I don't have enough data to answer that. Please ask a factual question about one of the 10 INDmoney funds (e.g. NAV, expense ratio, returns).",
            "source_url": source_url or "",
            "last_data_update": last_data_update,
            "rejected": False,
        }

    messages = build_messages(query, context_text, source_url, last_data_update)
    reply = chat_completion(messages)
    if not reply:
        return {
            "message": "I couldn't generate a response right now. Please try again.",
            "source_url": source_url or "",
            "last_data_update": last_data_update,
            "rejected": False,
        }

    return {
        "message": reply,
        "source_url": source_url or "",
        "last_data_update": last_data_update,
        "rejected": False,
    }
