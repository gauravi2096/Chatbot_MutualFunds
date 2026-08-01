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

# Welcome quick-reply examples: single consolidated set of 3 starter prompts
EXAMPLE_QUESTIONS = [
    "What is the NAV and AUM?",
    "What's the expense ratio?",
    "Compare expense ratios of two funds",
]

# Light theme and layout CSS
STYLES = """
<style>
/* App background */
.stApp, [data-testid="stAppViewContainer"] {
    background-color: #F8FAFC !important;
    color: #0f172a;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #F1F5F9 !important;
    border-right: 1px solid #E2E8F0;
}
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p {
    color: #0f172a !important;
}

/* Fund list: clickable buttons, reduced padding, highlight selected (primary = green) */
section[data-testid="stSidebar"] button {
    margin-bottom: 2px !important;
    padding: 0.4rem 0.75rem !important;
    text-align: left !important;
    border-radius: 8px;
    border: 1px solid #E2E8F0;
}
section[data-testid="stSidebar"] button[kind="secondary"] {
    background: #FFFFFF !important;
    color: #0f172a !important;
}
section[data-testid="stSidebar"] button[kind="secondary"]:hover {
    border-color: #84CC16;
    background: #F8FAFC !important;
}
section[data-testid="stSidebar"] button[kind="primary"] {
    background: #84CC16 !important;
    color: #0f172a !important;
    border-color: #65a30d;
}

/* Main content: center chat container and limit width so messages don't stretch full page */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 1rem;
    max-width: 680px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* Example question buttons on welcome screen */
.example-card {
    height: 100%;
}
.example-card button {
    width: 100%;
    height: 100%;
    min-height: 64px;
    text-align: center;
    background: #FFFFFF !important;
    border-radius: 12px;
    border: 1px solid #E2E8F0;
    padding: 0.6rem 0.5rem;
    box-shadow: none;
    color: #0f172a !important;
    font-weight: 500;
    font-size: 0.875rem;
}
.example-card button:hover {
    background: #F8FAFC !important;
    border-color: #84CC16;
    color: #0f172a !important;
}

/* Chat messages: improved spacing between messages; reduced padding inside bubbles */
div[data-testid="stChatMessage"] {
    margin-bottom: 1.25rem !important;
}
/* Hide only the avatar/icon elements */
div[data-testid="stChatMessage"] [data-testid="stImage"],
div[data-testid="stChatMessage"] img,
div[data-testid="stChatMessage"] svg,
div[data-testid="stChatMessage"] .stChatAvatar {
    display: none !important;
}

/* Chat bubble content: no green background; reduced padding; subtle border */
div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] {
    padding: 0.5rem 0.75rem !important;
    border-radius: 12px;
    border: 1px solid #E2E8F0;
}

/* User message: no green, right aligned - Streamlit sets aria-label="user" or "human" */
div[data-testid="stChatMessage"][aria-label="user"],
div[data-testid="stChatMessage"][aria-label="human"] {
    margin-left: auto !important;
    margin-right: 0 !important;
    max-width: 85%;
}
div[data-testid="stChatMessage"][aria-label="user"] div[data-testid="stChatMessageContent"],
div[data-testid="stChatMessage"][aria-label="human"] div[data-testid="stChatMessageContent"] {
    background: #FFFFFF !important;
    color: #0f172a !important;
}

/* Assistant message: light grey, left aligned - Streamlit sets aria-label="assistant" or "ai" */
div[data-testid="stChatMessage"][aria-label="assistant"],
div[data-testid="stChatMessage"][aria-label="ai"] {
    margin-left: 0 !important;
    margin-right: auto !important;
    max-width: 85%;
}
div[data-testid="stChatMessage"][aria-label="assistant"] div[data-testid="stChatMessageContent"],
div[data-testid="stChatMessage"][aria-label="ai"] div[data-testid="stChatMessageContent"] {
    background: #F1F5F9 !important;
    color: #0f172a !important;
}
div[data-testid="stChatMessage"][aria-label="assistant"] div[data-testid="stChatMessageContent"] .stCaptionContainer,
div[data-testid="stChatMessage"][aria-label="ai"] div[data-testid="stChatMessageContent"] .stCaptionContainer {
    color: #475569 !important;
}

/* Fallback when aria-label is not on container: odd = user, even = assistant (no green) */
div[data-testid="stChatMessage"]:not([aria-label]):nth-of-type(odd) {
    margin-left: auto !important;
    max-width: 85%;
}
div[data-testid="stChatMessage"]:not([aria-label]):nth-of-type(odd) div[data-testid="stChatMessageContent"] {
    background: #FFFFFF !important;
    color: #0f172a !important;
}
div[data-testid="stChatMessage"]:not([aria-label]):nth-of-type(even) {
    margin-right: auto !important;
    max-width: 85%;
}
div[data-testid="stChatMessage"]:not([aria-label]):nth-of-type(even) div[data-testid="stChatMessageContent"] {
    background: #F1F5F9 !important;
    color: #0f172a !important;
}

/* Chat input: fixed at bottom, light theme */
div[data-testid="stChatInput"] {
    border-top: 1px solid #E2E8F0;
    background: #F8FAFC !important;
}
div[data-testid="stChatInput"] textarea {
    background: #FFFFFF !important;
    color: #0f172a !important;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
}

/* Primary green send button */
button[kind="primary"], div[data-testid="stChatInput"] button[kind="primary"] {
    background: #84CC16 !important;
    color: #0f172a !important;
    border: none !important;
    border-radius: 12px;
}
button[kind="primary"]:hover, div[data-testid="stChatInput"] button:hover {
    background: #65a30d !important;
    color: #0f172a !important;
}

/* Reset Chat button: ensure fully visible, not cut off at top */
.reset-button button {
    border-radius: 9999px;
    border: 1px solid #E2E8F0;
    background: #FFFFFF !important;
    color: #0f172a !important;
    margin-top: 0 !important;
    padding-top: 0.35rem !important;
    padding-bottom: 0.35rem !important;
}
.reset-button button:hover {
    border-color: #84CC16;
    color: #0f172a !important;
}

/* Disclaimer below input */
.disclaimer {
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid #E2E8F0;
    color: #64748b;
    font-size: 0.8rem;
}

/* Welcome section: centered, tight spacing */
.welcome-section {
    text-align: center;
    margin: 1rem 0 1.25rem 0;
}
.welcome-section h4 {
    color: #0f172a;
    margin-bottom: 0.4rem;
    font-size: 1.1rem;
    font-weight: 600;
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
    col_title, col_spacer, col_reset = st.columns([2, 1, 1])
    with col_title:
        st.markdown("### INDmoney Fund Chat")
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
        # Welcome message introducing Fin + single instance of facts-only disclaimer
        st.markdown(
            '<div class="welcome-section">'
            '<h4>Hi, I\'m Fin — I help you check facts on 10 HDFC mutual funds. Pick a fund or tap a question below to get started.</h4>'
            '<p style="font-size:0.875rem; color:#64748B; font-weight:500; margin-top:0.4rem; margin-bottom:0;">Facts-only. No investment advice.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Single consolidated set of 3 tappable starter prompt buttons
        st.markdown("<p style='font-size:0.875rem; font-weight:600; color:#475569; margin-bottom:0.4rem;'>Example questions:</p>", unsafe_allow_html=True)
        q_cols = st.columns(3)
        for q_text, col in zip(EXAMPLE_QUESTIONS, q_cols):
            with col:
                st.markdown('<div class="example-card">', unsafe_allow_html=True)
                if st.button(
                    q_text,
                    key=f"ex_q_{q_text.replace(' ', '_')}",
                    use_container_width=True,
                ):
                    append_user_then_pending(q_text, selected_fund_id)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
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

    # ----- Disclaimer below the text input -----
    st.markdown(
        '<p class="disclaimer">INDmoney Fund Chat is for factual information only. Check important information on the source link.</p>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
