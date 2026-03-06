"""
Streamlit app for INDmoney Fund Chat — runs on Streamlit Cloud.
Uses the same backend logic as the FastAPI API (phase_2.orchestration.chat,
phase_1 retriever, phase_0 registry). The FastAPI app (phase_2/api.py) is
unchanged and can be deployed separately for the Phase 3 frontend and API consumers.
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


def main():
    st.set_page_config(
        page_title="INDmoney Fund Chat",
        page_icon="💬",
        layout="centered",
        initial_sidebar_state="expanded",
    )

    # Load fund list (same source as FastAPI GET /funds)
    try:
        registry = load_registry(REGISTRY_PATH)
        funds = [{"fund_id": s.fund_id, "fund_name": s.fund_name} for s in registry.sources]
        last_update = registry.last_data_update or "—"
    except Exception as e:
        st.error(f"Could not load fund list: {e}")
        funds = []
        last_update = "—"

    # Sidebar: fund selector
    with st.sidebar:
        st.title("Select a fund")
        st.caption("Choose a fund to ask questions about it.")
        fund_options = ["All funds"] + [f["fund_name"] for f in funds]
        fund_id_to_name = {f["fund_name"]: f["fund_id"] for f in funds}
        selected_label = st.selectbox("Fund", fund_options, label_visibility="collapsed")
        selected_fund_id = None if selected_label == "All funds" else fund_id_to_name.get(selected_label)
        st.divider()
        st.caption(f"Data as of: **{last_update}**")

    # Chat history in session state
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Main area: welcome + messages + input
    st.title("INDmoney Fund Chat")
    st.markdown("Ask factual questions about NAV, AUM, expense ratio, returns, holdings, and more. Select a fund in the sidebar to scope answers.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("source_url"):
                st.caption(f"[View source on INDmoney]({msg['source_url']})")
            if msg.get("last_data_update"):
                st.caption(f"Data as of {msg['last_data_update']}")

    if prompt := st.chat_input("Ask a question about the selected fund…"):
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

    st.divider()
    st.caption("INDmoney Fund Chat is for factual information only. It does not provide investment advice. Check the source link for official data.")


if __name__ == "__main__":
    main()
