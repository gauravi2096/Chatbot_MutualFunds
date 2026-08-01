"""
INDmoney Fund Chat — single Streamlit app (UI + backend).

Runs entirely on Streamlit Cloud. Combines the Phase 3 frontend UI (fund selector,
chat, suggestion cards) with the Phase 2 backend logic (RAG retrieval, Groq LLM).
Uses phase_0 registry, phase_1 retriever, phase_2 orchestration. No changes to
the data pipeline (phase_1) or scheduler (phase_4).
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is on path when run from repo root (e.g. Streamlit Cloud)
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env from project root (Streamlit Cloud sets secrets via UI; .env for local)
_env_file = PROJECT_ROOT / ".env"
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

import streamlit as st
from phase_0.source_registry import load_registry
from phase_1.config import REGISTRY_PATH
from phase_2.fund_detection import detect_funds_in_query
from phase_2.orchestration import chat

# Welcome quick-reply examples: short card label + icon (display only) mapped to
# the actual query text sent to chat() — routing/retrieval behavior is unchanged.
EXAMPLE_QUESTIONS = [
    {"icon": "📊", "label": "NAV & AUM", "query": "What is the NAV and AUM?"},
    {"icon": "💰", "label": "Expense ratio", "query": "What's the expense ratio?"},
    {"icon": "⚖️", "label": "Compare funds", "query": "Compare expense ratios of two funds"},
]

# "Cool trust" theme: slate/navy + teal accent, off-white background.
STYLES = """
<style>
:root {
    --bg-page: #EEF2F7;
    --bg-card: #FFFFFF;
    --bg-navy: #0F172A;
    --bg-navy-elevated: #1E293B;
    --bg-navy-hover: #263447;
    --border-subtle: #E2E8F0;
    --border-navy: #2C3B52;
    --text-primary: #0F172A;
    --text-secondary: #64748B;
    --text-oninavy: #E2E8F0;
    --text-oninavy-muted: #93A3B8;
    --accent-teal: #0D9488;
    --accent-teal-hover: #0F766E;
    --accent-teal-soft: #F0FDFA;
    --accent-teal-ring: rgba(13, 148, 136, 0.30);
    --shadow-soft: 0 1px 2px rgba(15, 23, 42, 0.04), 0 4px 14px rgba(15, 23, 42, 0.07);
}

/* App background */
.stApp, [data-testid="stAppViewContainer"] {
    background-color: var(--bg-page) !important;
    color: var(--text-primary);
}

/* Sidebar: deep navy panel, off-white text, teal accent for selection */
section[data-testid="stSidebar"] {
    background-color: var(--bg-navy) !important;
    border-right: 1px solid var(--border-navy);
}
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3 {
    color: #FFFFFF !important;
    font-weight: 700;
}
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p {
    color: var(--text-oninavy-muted) !important;
}
section[data-testid="stSidebar"] hr {
    border-color: var(--border-navy) !important;
}
/* Button label text must win over the generic sidebar "p" muted-color rule above */
section[data-testid="stSidebar"] button[kind="secondary"] p,
section[data-testid="stSidebar"] button[kind="secondary"] div,
section[data-testid="stSidebar"] button[kind="secondary"] span {
    color: var(--text-oninavy) !important;
}
section[data-testid="stSidebar"] button[kind="secondary"]:hover p,
section[data-testid="stSidebar"] button[kind="secondary"]:hover div,
section[data-testid="stSidebar"] button[kind="secondary"]:hover span {
    color: #FFFFFF !important;
}
section[data-testid="stSidebar"] button[kind="primary"] p,
section[data-testid="stSidebar"] button[kind="primary"] div,
section[data-testid="stSidebar"] button[kind="primary"] span {
    color: #FFFFFF !important;
}

/* Fund list: clickable buttons restyled as navy cards; teal = selected */
section[data-testid="stSidebar"] button {
    margin-bottom: 4px !important;
    padding: 0.5rem 0.85rem !important;
    text-align: left !important;
    border-radius: 10px;
    font-weight: 500;
    transition: border-color .15s ease, background-color .15s ease;
}
section[data-testid="stSidebar"] button[kind="secondary"] {
    background: var(--bg-navy-elevated) !important;
    color: var(--text-oninavy) !important;
    border: 1px solid var(--border-navy) !important;
}
section[data-testid="stSidebar"] button[kind="secondary"]:hover {
    border-color: var(--accent-teal) !important;
    background: var(--bg-navy-hover) !important;
    color: #FFFFFF !important;
}
section[data-testid="stSidebar"] button[kind="primary"] {
    background: var(--accent-teal) !important;
    color: #FFFFFF !important;
    border: 1px solid var(--accent-teal-hover) !important;
}
section[data-testid="stSidebar"] button[kind="primary"]:hover {
    background: var(--accent-teal-hover) !important;
}

/* Main content: use the same full width as the docked chat input below it,
   instead of a narrow centered column. padding-top clears Streamlit's fixed
   ~60px header bar. */
.block-container {
    padding-top: 4.5rem !important;
    padding-bottom: 1rem;
    max-width: 100% !important;
    padding-left: 3rem !important;
    padding-right: 3rem !important;
}
div[data-testid="stChatInput"] {
    padding-left: 3rem !important;
    padding-right: 3rem !important;
}

/* App title: single line */
.app-title {
    color: var(--text-primary);
    margin: 0;
    font-size: 1.4rem;
    font-weight: 700;
    line-height: 1.3;
    white-space: nowrap;
}

/* Hero greeting on landing screen */
.welcome-hero {
    text-align: center;
    margin: 1.75rem 0 1.5rem 0;
}
.welcome-hero .hero-line {
    color: var(--text-primary);
    margin: 0;
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.2;
    letter-spacing: -0.01em;
}
.welcome-hero .hero-line .accent {
    color: var(--accent-teal);
}

/* Example cards: tight spacing right beneath the hero */
.example-cards-spacer {
    margin-top: 0.25rem;
}

/* Welcome screen: a fixed (not viewport-height-based) gap pushes the
   disclaimer down from the cards. A vh-based min-height was tried here but
   it under-counted Streamlit's real chrome on shorter windows, forcing a
   page scrollbar and hiding the disclaimer behind the docked input — a
   fixed gap can never do that. */
.disclaimer.welcome-disclaimer {
    margin-top: 2.5rem;
}

/* Example question cards: compact, icon + short text, tight spacing.
   Streamlit renders each st.markdown/st.button call as a separate sibling -
   wrapping them with raw '<div class="example-card">...</div>' markdown
   calls does NOT nest the button inside that div, so a ".example-card
   button" descendant selector never matches anything. The reliable hook is
   the auto-generated "st-key-<key>" class Streamlit puts on the button's
   own wrapper when it has a key= (all three cards' keys start with
   "ex_q_"), matched here via an attribute-contains selector. */
div[class*="st-key-ex_q_"] button {
    min-height: 32px;
    text-align: center;
    background: var(--bg-card) !important;
    border-radius: 12px;
    border: 1px solid var(--border-subtle) !important;
    padding: 0.3rem 0.2rem !important;
    box-shadow: var(--shadow-soft);
    color: var(--text-primary) !important;
    font-weight: 600;
    font-size: 0.8rem;
    transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease;
}
div[class*="st-key-ex_q_"] button:hover {
    background: var(--accent-teal-soft) !important;
    border-color: var(--accent-teal) !important;
    color: var(--text-primary) !important;
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.10);
    transform: translateY(-1px);
}

/* Chat messages: improved spacing between messages */
div[data-testid="stChatMessage"] {
    margin-bottom: 1rem !important;
}
/* Hide the underlying avatar image/icon; we recolor the avatar shape itself below */
div[data-testid="stChatMessage"] [data-testid="stImage"],
div[data-testid="stChatMessage"] img,
div[data-testid="stChatMessage"] svg,
div[data-testid="stChatMessage"] .stChatAvatar {
    display: none !important;
}
/* No avatar for the user's own messages (cleaner, matches right-aligned "sent" bubbles) */
div[data-testid="stChatMessage"] [data-testid="stChatMessageAvatarUser"] {
    display: none !important;
}
/* Small circular avatar for the assistant only, for a less boxy, more chat-app feel */
div[data-testid="stChatMessage"] [data-testid="stChatMessageAvatarAssistant"] {
    background-color: var(--accent-teal) !important;
    border-radius: 50% !important;
}

/* Chat bubble content: soft rounded pill, no hard border, distinguished by color only */
div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] {
    padding: 0.65rem 1rem !important;
    border-radius: 20px;
    border: none !important;
    box-shadow: var(--shadow-soft);
}
div[data-testid="stChatMessage"] a {
    color: var(--accent-teal) !important;
}
div[data-testid="stChatMessage"] a:hover {
    color: var(--accent-teal-hover) !important;
}

/* Role detection: this Streamlit version sets neither aria-label nor a stable
   per-role class on stChatMessage, and each message is wrapped in its own
   unique parent (so :nth-of-type(odd/even) always evaluates to "odd" for
   every message). The one reliable, confirmed-working signal is which
   avatar test-id the message contains, so both alignment and bubble color
   key off that via :has(). */

/* User message: teal-tinted pill, right aligned, no avatar */
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    margin-left: auto !important;
    margin-right: 0 !important;
    max-width: min(85%, 640px);
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) div[data-testid="stChatMessageContent"] {
    background: var(--accent-teal-soft) !important;
    color: var(--text-primary) !important;
}

/* Assistant message: white pill with a circular teal avatar, left aligned */
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    margin-left: 0 !important;
    margin-right: auto !important;
    max-width: min(85%, 640px);
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stChatMessageContent"] {
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stChatMessageContent"] .stCaptionContainer {
    color: var(--text-secondary) !important;
}

/* Bottom bar wrapper: Streamlit paints this its own off-white (#F8FAFC),
   which reads as a visible seam against our page background - match it. */
div[data-testid="stBottom"] > div {
    background: var(--bg-page) !important;
}

/* Chat input: fixed at bottom, pill-shaped, teal focus ring */
div[data-testid="stChatInput"] {
    border-top: 1px solid var(--border-subtle);
    background: var(--bg-page) !important;
    padding-top: 0.5rem;
}
div[data-testid="stChatInput"] textarea {
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border: 1.5px solid var(--border-subtle) !important;
    border-radius: 26px !important;
    padding: 0.9rem 1.35rem !important;
    box-shadow: var(--shadow-soft);
    transition: border-color .15s ease, box-shadow .15s ease;
}
div[data-testid="stChatInput"] textarea:focus {
    border-color: var(--accent-teal) !important;
    box-shadow: 0 0 0 4px var(--accent-teal-ring) !important;
    outline: none !important;
}
/* Vertically re-center the send button now that the pill textarea is taller;
   Streamlit's default wrapper uses align-items:flex-end which no longer centers it */
div[data-testid="stChatInput"] div:has(> button[data-testid="stChatInputSubmitButton"]) {
    align-items: center !important;
}

/* Primary teal buttons (e.g. selected fund in the sidebar) */
button[kind="primary"] {
    background: var(--accent-teal) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 9999px;
}
button[kind="primary"]:hover {
    background: var(--accent-teal-hover) !important;
    color: #FFFFFF !important;
}

/* Chat input send button: this is a plain button with no kind="primary"
   attribute in this Streamlit version, so it needs its own rule rather than
   inheriting from button[kind="primary"] above (which never matched it) */
div[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"] {
    color: var(--accent-teal) !important;
    background: transparent !important;
    border-radius: 9999px !important;
    transition: background-color .15s ease, color .15s ease;
}
div[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"]:hover:not(:disabled) {
    color: var(--accent-teal-hover) !important;
    background: var(--accent-teal-soft) !important;
}
div[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"]:disabled {
    color: var(--text-secondary) !important;
}

/* Reset Chat button */
.reset-button button {
    border-radius: 9999px;
    border: 1px solid var(--border-subtle);
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    margin-top: 0 !important;
    padding-top: 0.35rem !important;
    padding-bottom: 0.35rem !important;
}
.reset-button button:hover {
    border-color: var(--accent-teal);
    color: var(--accent-teal-hover) !important;
}

/* Disclaimer below input: small, centered under the input */
.disclaimer {
    margin-top: 1.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--border-subtle);
    color: var(--text-secondary);
    font-size: 0.65rem;
    text-align: center;
}
</style>
"""


def classify_name_response(prompt: str) -> str:
    """
    Classify user input when awaiting a name response.
    Returns: 'skip', 'name', or 'question'.
    """
    p_clean = prompt.strip().lower()

    # 1. Skip phrases
    skip_phrases = (
        "no", "skip", "no thanks", "no, thanks", "nope", "never mind",
        "nevermind", "don't want", "dont want", "pass", "none", "nah",
        "not now", "prefer not", "keep anonymous", "anonymous", "don't ask"
    )
    if p_clean in skip_phrases or any(p_clean == phrase for phrase in skip_phrases):
        return "skip"

    # 2. Real question / advisory / financial query check
    if "?" in prompt:
        return "question"

    financial_keywords = (
        "nav", "aum", "expense", "ratio", "risk", "return", "returns", "cagr",
        "holding", "holdings", "benchmark", "exit load", "fund", "hdfc", "compare",
        "invest", "investment", "buy", "sell", "best", "should", "recommend", "advice"
    )
    words = p_clean.split()
    if any(kw in p_clean for kw in financial_keywords):
        return "question"

    if len(detect_funds_in_query(prompt)) > 0:
        return "question"

    if len(prompt) > 40 or len(words) > 5:
        return "question"

    # 3. Otherwise, treat as name
    return "name"


def extract_name_from_text(text: str) -> str:
    """Extract clean name string from user input."""
    t = text.strip()
    t_lower = t.lower()
    prefixes = ("my name is ", "call me ", "i am ", "i'm ", "it's ", "its ")
    for prefix in prefixes:
        if t_lower.startswith(prefix):
            name = t[len(prefix):].strip().rstrip(".!")
            if name:
                return name.capitalize()
    return t.strip().rstrip(".!").capitalize()


def append_user_then_pending(prompt: str, selected_fund_id: Optional[str]) -> None:
    """Append user message and set pending query so we switch to chat view, then process on next run."""
    st.session_state.messages.append({"role": "user", "content": prompt, "source_url": None, "last_data_update": None})
    st.session_state.pending_query = (prompt, selected_fund_id)


def process_pending_response() -> bool:
    """If a response is pending, call RAG + Groq and append assistant message. Returns True if processed."""
    pending = st.session_state.get("pending_query")
    if not pending:
        return False
    prompt, fund_id = pending
    st.session_state.pending_query = None
    try:
        result = chat(query=prompt, fund_id=fund_id)
        reply = result.get("message", "")
        source_url = result.get("source_url", "")
        last_data_update = result.get("last_data_update", "")
        rejected = result.get("rejected", False)
        needs_fund_clarification = result.get("needs_fund_clarification", False)
        is_greeting = result.get("is_greeting", False)

        st.session_state.messages.append({
            "role": "assistant",
            "content": reply,
            "source_url": source_url,
            "last_data_update": last_data_update,
            "rejected": rejected,
            "needs_fund_clarification": needs_fund_clarification,
            "is_greeting": is_greeting,
        })

        if needs_fund_clarification:
            st.session_state.pending_ambiguous_query = prompt
        else:
            st.session_state.pending_ambiguous_query = None

        # Name capture turn: trigger conversational question after first successful factual answer
        if (
            not rejected
            and not needs_fund_clarification
            and not is_greeting
            and not st.session_state.get("name_asked", False)
            and not st.session_state.get("name_skipped", False)
            and st.session_state.get("user_name") is None
        ):
            st.session_state.name_asked = True
            st.session_state.awaiting_name = True
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Glad that helped! What should I call you, so I'm not just 'hey there' every time?",
                "source_url": None,
                "last_data_update": None,
                "rejected": False,
                "needs_fund_clarification": False,
                "is_greeting": False,
            })

    except Exception as e:
        st.session_state.messages.append({
            "role": "assistant",
            "content": str(e),
            "source_url": None,
            "last_data_update": None,
            "rejected": True,
            "needs_fund_clarification": False,
            "is_greeting": False,
        })
    return True


def main():
    st.set_page_config(
        page_title="INDmoney Fund Chat",
        page_icon="💬",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(STYLES, unsafe_allow_html=True)

    # Session state initialization
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_query" not in st.session_state:
        st.session_state.pending_query = None
    if "selected_fund_id" not in st.session_state:
        st.session_state.selected_fund_id = None
    if "user_name" not in st.session_state:
        st.session_state.user_name = None
    if "name_asked" not in st.session_state:
        st.session_state.name_asked = False
    if "name_skipped" not in st.session_state:
        st.session_state.name_skipped = False
    if "awaiting_name" not in st.session_state:
        st.session_state.awaiting_name = False
    if "pending_ambiguous_query" not in st.session_state:
        st.session_state.pending_ambiguous_query = None

    # Load fund list (same source as FastAPI GET /funds)
    try:
        registry = load_registry(REGISTRY_PATH)
        funds = [{"fund_id": s.fund_id, "fund_name": s.fund_name} for s in registry.sources]
        last_update = registry.last_data_update or "—"
    except Exception as e:
        st.error(f"Could not load fund list: {e}")
        funds = []
        last_update = "—"

    selected_fund_id = st.session_state.selected_fund_id

    # ----- Left sidebar: clickable fund list (no radio), reduced padding, highlight selected -----
    with st.sidebar:
        st.markdown("## Select a fund")
        st.caption("Choose a fund to ask questions about it.")
        st.markdown("")  # spacing

        # All funds
        if st.button(
            "All funds",
            key="fund_all",
            type="primary" if selected_fund_id is None else "secondary",
            use_container_width=True,
        ):
            st.session_state.selected_fund_id = None
            st.rerun()
        for f in funds:
            if st.button(
                f["fund_name"],
                key=f"fund_{f['fund_id']}",
                type="primary" if selected_fund_id == f["fund_id"] else "secondary",
                use_container_width=True,
            ):
                st.session_state.selected_fund_id = f["fund_id"]
                st.rerun()

        st.divider()
        st.caption(f"Data as of: **{last_update}**")

    # ----- Right side: main content -----
    # Header: title + last updated + Reset (only after first message)
    col_title, col_spacer, col_reset = st.columns([2.6, 0.4, 1])
    with col_title:
        st.markdown('<p class="app-title">INDmoney Fund Chat</p>', unsafe_allow_html=True)
        st.caption(f"Data last updated: {last_update}")
    with col_reset:
        if st.session_state.messages:
            st.markdown('<div class="reset-button">', unsafe_allow_html=True)
            if st.button("Reset Chat", use_container_width=True, key="reset_chat"):
                st.session_state.messages = []
                st.session_state.pending_query = None
                st.session_state.pending_ambiguous_query = None
                st.session_state.awaiting_name = False
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # ----- Welcome screen OR chat view -----
    if not st.session_state.messages:
        with st.container(key="welcome_screen"):
            # Two-line hero greeting
            st.markdown(
                '<div class="welcome-hero">'
                '<p class="hero-line">Hi, I\'m <span class="accent">Fin</span></p>'
                '<p class="hero-line">How can I help you today?</p>'
                '</div>',
                unsafe_allow_html=True,
            )

            # Single consolidated set of 3 tappable starter prompt cards (icon + short label)
            st.markdown('<div class="example-cards-spacer"></div>', unsafe_allow_html=True)
            q_cols = st.columns(3)
            for ex, col in zip(EXAMPLE_QUESTIONS, q_cols):
                with col:
                    if st.button(
                        ex["label"],
                        icon=ex["icon"],
                        key=f"ex_q_{ex['label'].replace(' ', '_')}",
                        use_container_width=True,
                    ):
                        append_user_then_pending(ex["query"], selected_fund_id)
                        st.rerun()

            # Disclaimer pinned near the bottom of the landing screen, just above the input
            st.markdown(
                '<p class="disclaimer welcome-disclaimer">INDmoney Fund Chat is for factual information only. '
                'Check important information on the source link.</p>',
                unsafe_allow_html=True,
            )
    else:
        # Chat view: Streamlit sets aria-label on container so CSS can target user vs assistant
        for idx, msg in enumerate(st.session_state.messages):
            with st.chat_message(msg["role"], avatar=None):
                st.markdown(msg["content"])
                if msg.get("source_url"):
                    st.caption(f"[View source on INDmoney]({msg['source_url']})")
                if msg.get("last_data_update"):
                    st.caption(f"Data as of {msg['last_data_update']}")

                # Quick-reply buttons for 10 funds when clarification is required
                if msg.get("needs_fund_clarification") and idx == len(st.session_state.messages) - 1:
                    st.markdown("<p style='font-size:0.875rem; font-weight:600; color:#475569; margin-top:0.75rem; margin-bottom:0.35rem;'>Select a fund to check:</p>", unsafe_allow_html=True)
                    grid_cols = st.columns(2)
                    for i, f in enumerate(funds):
                        col_target = grid_cols[i % 2]
                        with col_target:
                            if st.button(
                                f["fund_name"],
                                key=f"clarify_fund_{f['fund_id']}_{idx}",
                                use_container_width=True,
                            ):
                                ambiguous_q = st.session_state.get("pending_ambiguous_query", "")
                                st.session_state.pending_ambiguous_query = None
                                st.session_state.messages.append({
                                    "role": "user",
                                    "content": f["fund_name"],
                                    "source_url": None,
                                    "last_data_update": None,
                                })
                                target_query = ambiguous_q if ambiguous_q else f["fund_name"]
                                st.session_state.pending_query = (target_query, f["fund_id"])
                                st.rerun()

        # If we have a pending query, show assistant bubble with spinner then process and rerun
        if st.session_state.pending_query:
            with st.chat_message("assistant", avatar=None):
                with st.spinner("Thinking…"):
                    process_pending_response()
                    st.rerun()

    # ----- Chat input (fixed at bottom in flow) -----
    if prompt := st.chat_input("Ask about the selected fund..."):
        if st.session_state.get("awaiting_name"):
            name_class = classify_name_response(prompt)
            if name_class == "skip":
                st.session_state.awaiting_name = False
                st.session_state.name_skipped = True
                st.session_state.messages.append({
                    "role": "user",
                    "content": prompt,
                    "source_url": None,
                    "last_data_update": None,
                })
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "No problem!",
                    "source_url": None,
                    "last_data_update": None,
                })
                st.rerun()
            elif name_class == "name":
                extracted = extract_name_from_text(prompt)
                st.session_state.user_name = extracted
                st.session_state.awaiting_name = False
                st.session_state.messages.append({
                    "role": "user",
                    "content": prompt,
                    "source_url": None,
                    "last_data_update": None,
                })
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Nice to meet you, {extracted}!",
                    "source_url": None,
                    "last_data_update": None,
                })
                st.rerun()
            else:
                # Real fund query / advisory: skip name prompt silently and process actual query
                st.session_state.awaiting_name = False
                st.session_state.name_skipped = True
                append_user_then_pending(prompt, selected_fund_id)
                st.rerun()
        else:
            append_user_then_pending(prompt, selected_fund_id)
            st.rerun()

    # ----- Disclaimer below the text input (chat view only; welcome screen renders its own, pinned lower) -----
    if st.session_state.messages:
        st.markdown(
            '<p class="disclaimer">INDmoney Fund Chat is for factual information only. Check important information on the source link.</p>',
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
