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

# Template cards (Part 2): category prompts with no fund named in the text
SUGGESTION_CARDS = [
    ("NAV & AUM", "Get latest NAV and fund size for any of the 10 funds.", "What is the NAV and AUM?"),
    ("Expense & Returns", "Expense ratio and 1Y/3Y/5Y returns.", "What is the expense ratio and 1Y returns?"),
    ("Holdings & Risk", "Top holdings, risk level, and benchmark.", "What are the top holdings and risk level?"),
]

# Welcome quick-reply examples (Part 1): no fund named; fund detection applies on click
EXAMPLE_QUESTIONS = [
    "What's the expense ratio?",
    "What's the risk level?",
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
    padding-top: 2rem !important;
    padding-bottom: 1rem;
    max-width: 680px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* Starter cards: white, border, rounded */
.suggestion-card {
    height: 100%;
    min-height: 120px;
}
.suggestion-card button {
    width: 100%;
    height: 100%;
    min-height: 120px;
    text-align: left;
    background: #FFFFFF !important;
    border-radius: 16px;
    border: 1px solid #E2E8F0;
    padding: 1rem;
    box-shadow: none;
    color: #0f172a !important;
}
.suggestion-card button:hover {
    background: #F8FAFC !important;
    border-color: #84CC16;
    color: #0f172a !important;
}

/* Example question buttons on welcome screen */
.example-card {
    height: 100%;
}
.example-card button {
    width: 100%;
    height: 100%;
    min-height: 70px;
    text-align: center;
    background: #FFFFFF !important;
    border-radius: 12px;
    border: 1px solid #E2E8F0;
    padding: 0.75rem 0.5rem;
    box-shadow: none;
    color: #0f172a !important;
    font-weight: 500;
    font-size: 0.9rem;
}
.example-card button:hover {
    background: #F8FAFC !important;
    border-color: #84CC16;
    color: #0f172a !important;
}

/* Chat messages: improved spacing between messages; reduced padding inside bubbles */
div[data-testid="stChatMessage"] {
    margin-bottom: 1.5rem !important;
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
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid #E2E8F0;
    color: #64748b;
    font-size: 0.875rem;
}

/* Welcome section: centered */
.welcome-section {
    text-align: center;
    margin: 1.5rem 0 2rem 0;
}
.welcome-section h4 {
    color: #0f172a;
    margin-bottom: 0.5rem;
    font-size: 1.15rem;
    font-weight: 600;
}
</style>
"""


def append_user_then_pending(prompt: str, selected_fund_id: str | None) -> None:
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

        st.session_state.messages.append({
            "role": "assistant",
            "content": reply,
            "source_url": source_url,
            "last_data_update": last_data_update,
            "rejected": rejected,
            "needs_fund_clarification": needs_fund_clarification,
        })

        if needs_fund_clarification:
            st.session_state.pending_ambiguous_query = prompt
        else:
            st.session_state.pending_ambiguous_query = None

        # Deferred name ask: trigger after the first successful factual answer
        if (
            not rejected
            and not needs_fund_clarification
            and not st.session_state.get("name_asked", False)
            and not st.session_state.get("name_skipped", False)
            and st.session_state.get("user_name") is None
        ):
            st.session_state.name_asked = True
            st.session_state.show_name_prompt = True

    except Exception as e:
        st.session_state.messages.append({
            "role": "assistant",
            "content": str(e),
            "source_url": None,
            "last_data_update": None,
            "rejected": True,
            "needs_fund_clarification": False,
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
    if "show_name_prompt" not in st.session_state:
        st.session_state.show_name_prompt = False
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
                st.session_state.show_name_prompt = False
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("")  # spacing

    # ----- Welcome screen OR chat view -----
    if not st.session_state.messages:
        # Welcome message with bot identity "Fin" and upfront facts-only disclaimer
        st.markdown('<div class="welcome-section">', unsafe_allow_html=True)
        st.markdown("#### Hi, I'm Fin — I help you check facts on 10 HDFC mutual funds. Pick a fund or tap a question below to get started.")
        st.markdown("<p style='font-size:0.875rem; color:#64748B; font-weight:500; margin-top:0.5rem;'>Facts-only. No investment advice.</p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # 3 tappable example questions as quick-reply buttons (Part 1 requirement)
        st.markdown("<p style='font-size:0.9rem; font-weight:600; color:#475569; margin-bottom:0.5rem;'>Example questions:</p>", unsafe_allow_html=True)
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

        st.markdown("<br>", unsafe_allow_html=True)

        # Pre-existing template cards (Part 2 requirement: also route through fund detection)
        st.markdown("<p style='font-size:0.9rem; font-weight:600; color:#475569; margin-bottom:0.5rem;'>Explore by topic:</p>", unsafe_allow_html=True)
        cols = st.columns(3)
        for (title, desc, prompt), col in zip(SUGGESTION_CARDS, cols):
            with col:
                st.markdown('<div class="suggestion-card">', unsafe_allow_html=True)
                if st.button(
                    f"**{title}**\n\n{desc}",
                    key=f"suggest_{title.replace(' ', '_')}",
                    use_container_width=True,
                ):
                    append_user_then_pending(prompt, selected_fund_id)
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

                # Part 2: Quick-reply buttons for 10 funds when clarification is required
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
                                target_query = f"{ambiguous_q} for {f['fund_name']}" if ambiguous_q else f["fund_name"]
                                append_user_then_pending(target_query, f["fund_id"])
                                st.rerun()

        # Part 1: Deferred Skippable Name Ask (shown once after first successful factual answer)
        if st.session_state.get("show_name_prompt") and st.session_state.user_name is None and not st.session_state.name_skipped:
            with st.chat_message("assistant", avatar=None):
                st.markdown("Glad that helped! What should I call you, so I'm not just 'hey there' every time?")
                col_in, col_save, col_skip = st.columns([3, 1, 1])
                with col_in:
                    name_val = st.text_input("Name", key="name_input_val", label_visibility="collapsed", placeholder="Enter your name...")
                with col_save:
                    if st.button("Save", key="save_name_btn", type="primary", use_container_width=True):
                        if name_val and name_val.strip():
                            name_clean = name_val.strip()
                            st.session_state.user_name = name_clean
                            st.session_state.show_name_prompt = False
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": f"Nice to meet you, {name_clean}! What else can I look up for you?",
                                "source_url": None,
                                "last_data_update": None,
                                "rejected": False,
                                "needs_fund_clarification": False,
                            })
                            st.rerun()
                with col_skip:
                    if st.button("No thanks", key="skip_name_btn", type="secondary", use_container_width=True):
                        st.session_state.name_skipped = True
                        st.session_state.show_name_prompt = False
                        st.rerun()

        # If we have a pending query, show assistant bubble with spinner then process and rerun
        if st.session_state.pending_query:
            with st.chat_message("assistant", avatar=None):
                with st.spinner("Thinking…"):
                    process_pending_response()
                    st.rerun()

    # ----- Chat input (fixed at bottom in flow) -----
    if prompt := st.chat_input("Ask about the selected fund..."):
        # If user typed a new query while name prompt was active, treat name ask as skipped
        if st.session_state.get("show_name_prompt"):
            st.session_state.name_skipped = True
            st.session_state.show_name_prompt = False
        append_user_then_pending(prompt, selected_fund_id)
        st.rerun()

    # ----- Disclaimer below the text input -----
    st.markdown(
        '<p class="disclaimer">INDmoney Fund Chat is for factual information only. It does not provide investment advice. Check important information on the source link.</p>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
