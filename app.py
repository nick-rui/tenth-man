import json
from pathlib import Path

import streamlit as st

from tenth_man import get_tenth_man_analysis_from_history


TEXTS_PATH = Path(__file__).with_name("frontend_text.json")


def _load_texts() -> dict[str, str]:
    with TEXTS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def _build_chat_history_payload(messages: list[dict[str, object]]) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role", ""))
        content = str(message.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            payload.append({"role": role, "content": content})
    return payload


def _compute_threat_level(text: str) -> int:
    lowered = text.lower()
    score = 15
    hot_terms = [
        "failing grade",
        "unsupported",
        "contradict",
        "no evidence",
        "high risk",
        "failed",
        "does not hold",
        "unrealistic",
    ]
    for term in hot_terms:
        if term in lowered:
            score += 12
    return max(0, min(100, score))


TEXT = _load_texts()


st.set_page_config(
    page_title=TEXT["page_title"],
    page_icon=":warning:",
    layout="wide",
)

st.title(TEXT["page_title"])
st.caption(TEXT["page_caption"])

if "messages" not in st.session_state:
    st.session_state.messages = []

last_assistant_text = ""
last_source_count = 0
last_degraded_mode = False
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            stimulus_summary = message.get("stimulus_summary", [])
            sources = message.get("sources", [])
            degraded_mode = bool(message.get("degraded_mode", False))
            with st.expander(TEXT["stimulus_expander_title"], expanded=False):
                if degraded_mode:
                    st.warning(TEXT["degraded_warning"])
                if stimulus_summary:
                    st.markdown(f"**{TEXT['stimulus_cues_heading']}**")
                    for item in stimulus_summary:
                        st.markdown(f"- {item}")
                else:
                    st.markdown(f"- {TEXT['no_stimulus_cues']}")
                if sources:
                    st.markdown(f"**{TEXT['sources_heading']}**")
                    for url in sources[:5]:
                        st.markdown(f"- {url}")
    if message["role"] == "assistant":
        last_assistant_text = message["content"]
        last_source_count = len(message.get("sources", []))
        last_degraded_mode = bool(message.get("degraded_mode", False))

with st.sidebar:
    threat_level = _compute_threat_level(last_assistant_text) if last_assistant_text else 10
    st.subheader(TEXT["sidebar_fragility_label"])
    st.progress(threat_level, text=f"{threat_level}%")
    st.metric(
        TEXT["sidebar_risk_signal_label"],
        (
            TEXT["risk_signal_critical"]
            if threat_level >= 70
            else TEXT["risk_signal_moderate"] if threat_level >= 40 else TEXT["risk_signal_low"]
        ),
    )
    st.metric(TEXT["sidebar_evidence_coverage_label"], last_source_count)
    if last_degraded_mode:
        st.caption(TEXT["sidebar_degraded_caption"])

if user_prompt := st.chat_input(TEXT["chat_input_placeholder"]):
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        with st.spinner(TEXT["spinner_text"]):
            history_payload = _build_chat_history_payload(st.session_state.messages)
            analysis = get_tenth_man_analysis_from_history(history_payload)
            assistant_reply = analysis.final_text
            st.markdown(assistant_reply)
            with st.expander(TEXT["stimulus_expander_title"], expanded=False):
                if analysis.degraded_mode:
                    st.warning(TEXT["degraded_warning"])
                if analysis.stimulus_summary:
                    st.markdown(f"**{TEXT['stimulus_cues_heading']}**")
                    for item in analysis.stimulus_summary:
                        st.markdown(f"- {item}")
                else:
                    st.markdown(f"- {TEXT['no_stimulus_cues']}")
                if analysis.sources:
                    st.markdown(f"**{TEXT['sources_heading']}**")
                    for url in analysis.sources[:5]:
                        st.markdown(f"- {url}")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": assistant_reply,
            "stimulus_summary": analysis.stimulus_summary,
            "sources": analysis.sources,
            "degraded_mode": analysis.degraded_mode,
        }
    )
