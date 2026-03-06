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
from phase_2.orchestration import chat

# Starter cards: (title, short description, prompt sent when card is clicked)
SUGGESTION_CARDS = [
    ("NAV & AUM", "Get latest NAV and fund size for any of the 10 funds.", "What is the NAV and AUM of HDFC Mid Cap Fund?"),
    ("Expense & Returns", "Expense ratio and 1Y/3Y/5Y returns.", "What is the expense ratio and 1Y returns of HDFC Flexi Cap Fund?"),
    ("Holdings & Risk", "Top holdings, risk level, and benchmark.", "What are the top holdings and risk level of HDFC Small Cap Fund?"),
]

# Dark theme and layout CSS
STYLES = """
<style>
/* Force dark app background */
.stApp, [data-testid="stAppViewContainer"] {
    background-color: #020617 !important;
    color: #e5e7eb;
}

/* Sidebar: dark navy, border */
section[data-testid="stSidebar"] {
    background-color: #020617 !important;
    border-right: 1px solid #1f2937;
}
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p {
    color: #e5e7eb !important;
}

/* Fund list in sidebar: vertical list styling */
.stRadio > div {
    background: transparent !important;
    gap: 0.25rem;
}
.stRadio label {
    background: #0f172a !important;
    border: 1px solid #1f2937;
    border-radius: 12px;
    padding: 0.75rem 1rem !important;
    color: #e5e7eb !important;
}
.stRadio label:hover {
    border-color: #22c55e;
    background: #0b1120 !important;
}
.stRadio label[data-checked="true"] {
    border-color: #22c55e;
    background: #0b1120 !important;
}

/* Main content spacing */
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 1rem;
    max-width: 900px;
}

/* Header area */
.main-header {
    margin-bottom: 1.5rem;
}

/* Starter cards: equal width, equal height, one row, rounded, border */
.suggestion-card {
    height: 100%;
    min-height: 120px;
}
.suggestion-card button {
    width: 100%;
    height: 100%;
    min-height: 120px;
    text-align: left;
    background: #0f172a !important;
    border-radius: 16px;
    border: 1px solid #1f2937;
    padding: 1rem;
    box-shadow: none;
    color: #e5e7eb !important;
}
.suggestion-card button:hover {
    background: #0b1120 !important;
    border-color: #22c55e;
    color: #e5e7eb !important;
}

/* Chat message bubbles */
div[data-testid="stChatMessageContent"] {
    background: #0f172a;
    border-radius: 18px;
    padding: 0.75rem 1rem;
    border: 1px solid #1f2937;
}

/* Chat input: dark background, fixed at bottom feel */
div[data-testid="stChatInput"] {
    border-top: 1px solid #1f2937;
    background: #020617 !important;
}
div[data-testid="stChatInput"] textarea {
    background: #0f172a !important;
    color: #e5e7eb !important;
    border: 1px solid #1f2937;
    border-radius: 12px;
}

/* Green send button */
button[kind="primary"], div[data-testid="stChatInput"] button {
    background: #22c55e !important;
    color: #020617 !important;
    border: none !important;
    border-radius: 12px;
}
button[kind="primary"]:hover, div[data-testid="stChatInput"] button:hover {
    background: #16a34a !important;
    color: #020617 !important;
}

/* Reset Chat: only after first message */
.reset-button button {
    border-radius: 9999px;
    border: 1px solid #4b5563;
    background: #0f172a !important;
    color: #e5e7eb !important;
}
.reset-button button:hover {
    border-color: #22c55e;
    color: #bbf7d0 !important;
}

/* Disclaimer below input */
.disclaimer {
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid #1f2937;
    color: #9ca3af;
    font-size: 0.875rem;
}

/* Welcome section: centered */
.welcome-section {
    text-align: center;
    margin: 2rem 0;
}
.welcome-section h2 {
    color: #e5e7eb;
    margin-bottom: 0.5rem;
}
.welcome-section p {
    color: #9ca3af;
    margin-bottom: 1.5rem;
}
</style>
"""


def run_chat(prompt: str, selected_fund_id: str | None) -> None:
    """Process a user prompt through RAG + Groq and append to messages."""
    st.session_state.messages.append({"role": "user", "content": prompt, "source_url": None, "last_data_update": None})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                result = chat(query=prompt, fund_id=selected_fund_id)
                reply = result.get("message", "")
                source_url = result.get("source_url", "")
                last_data_update = result.get("last_data_update", "")
                st.markdown(reply)
                if source_url:
                    st.caption(f"[View source on INDmoney]({source_url})")
                if last_data_update:
                    st.caption(f"Data as of {last_data_update}")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": reply,
                    "source_url": source_url,
                    "last_data_update": last_data_update,
                })
            except Exception as e:
                st.error(f"Something went wrong: {e}")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": str(e),
                    "source_url": None,
                    "last_data_update": None,
                })


def main():
    st.set_page_config(
        page_title="INDmoney Fund Chat",
        page_icon="💬",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(STYLES, unsafe_allow_html=True)

    # Load fund list (same source as FastAPI GET /funds)
    try:
        registry = load_registry(REGISTRY_PATH)
        funds = [{"fund_id": s.fund_id, "fund_name": s.fund_name} for s in registry.sources]
        last_update = registry.last_data_update or "—"
    except Exception as e:
        st.error(f"Could not load fund list: {e}")
        funds = []
        last_update = "—"

    # ----- Left sidebar: scrollable fund list -----
    with st.sidebar:
        st.markdown("## Select a fund")
        st.caption("Choose a fund to ask questions about it.")
        st.markdown("")  # spacing

        fund_options = ["All funds"] + [f["fund_name"] for f in funds]
        fund_name_to_id = {f["fund_name"]: f["fund_id"] for f in funds}

        selected_label = st.radio(
            "Fund",
            options=fund_options,
            label_visibility="collapsed",
            key="fund_selector",
        )
        selected_fund_id = None if selected_label == "All funds" else fund_name_to_id.get(selected_label)

        st.divider()
        st.caption(f"Data as of: **{last_update}**")

    # Session state for chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

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
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("")  # spacing

    # ----- Welcome + starter cards OR chat view -----
    if not st.session_state.messages:
        # Welcome message (centered)
        st.markdown('<div class="welcome-section">', unsafe_allow_html=True)
        st.markdown("#### Hi, welcome — how can I help you?")
        st.markdown(
            "Select a fund from the list on the left, then ask questions about NAV, AUM, expense ratio, returns, and more."
        )
        st.markdown("</div>", unsafe_allow_html=True)

        # Three starter cards in one row, equal width and height
        cols = st.columns(3)
        for (title, desc, prompt), col in zip(SUGGESTION_CARDS, cols):
            with col:
                st.markdown('<div class="suggestion-card">', unsafe_allow_html=True)
                if st.button(
                    f"**{title}**\n\n{desc}",
                    key=f"suggest_{title.replace(' ', '_')}",
                    use_container_width=True,
                ):
                    run_chat(prompt, selected_fund_id)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        # Chat view: show all messages with source link and timestamp
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("source_url"):
                    st.caption(f"[View source on INDmoney]({msg['source_url']})")
                if msg.get("last_data_update"):
                    st.caption(f"Data as of {msg['last_data_update']}")

    # ----- Chat input (fixed at bottom in flow) -----
    if prompt := st.chat_input("Ask about the selected fund..."):
        run_chat(prompt, selected_fund_id)
        st.rerun()

    # ----- Disclaimer below the text input -----
    st.markdown(
        '<p class="disclaimer">INDmoney Fund Chat is for factual information only. It does not provide investment advice. Check important information on the source link.</p>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
