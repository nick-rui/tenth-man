import json
from pathlib import Path
from typing import Any

import streamlit as st

from tenth_man import prepare_tenth_man_stream_from_history


TEXTS_PATH = Path(__file__).with_name("frontend_text.json")


def _load_texts() -> dict[str, Any]:
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


def _apply_styles(text: dict[str, Any]) -> None:
    st.markdown(
        f"""
<style>
:root {{
  --tm-purple: {text["color_primary"]};
  --tm-purple-soft: {text["color_primary_soft"]};
  --tm-white: {text["color_background"]};
  --tm-heading-font: {text["font_heading_stack"]};
  --tm-body-font: {text["font_body_stack"]};
}}

.stApp {{
  background: var(--tm-white);
}}

[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {{
  background: var(--tm-white);
}}

#MainMenu,
header,
footer,
[data-testid="stToolbar"],
[data-testid="stStatusWidget"],
[data-testid="stDecoration"] {{
  visibility: hidden;
  height: 0;
  position: fixed;
}}

h1, h2, h3 {{
  font-family: var(--tm-heading-font);
  color: var(--tm-purple);
  letter-spacing: 0.2px;
  font-style: italic;
}}

p, li, div, label, span {{
  font-family: var(--tm-heading-font);
  font-style: normal;
}}

* {{
  font-family: var(--tm-heading-font);
  font-style: normal;
}}

.landing-wrap {{
  max-width: 760px;
  margin: 3rem auto 1rem auto;
  padding: 2.5rem 2rem;
  border: 1px solid var(--tm-purple-soft);
  border-radius: 16px;
  background: var(--tm-white);
}}

.landing-subtitle {{
  font-family: var(--tm-heading-font);
  font-style: italic;
  font-size: 1.05rem;
  margin-top: -0.2rem;
  margin-bottom: 1rem;
}}

[data-testid="stCaptionContainer"] p {{
  font-family: var(--tm-heading-font);
  font-style: italic;
}}

[data-testid="stChatMessageContent"] * {{
  font-family: var(--tm-body-font) !important;
  font-style: normal !important;
}}

[data-testid="stChatMessage"],
[data-testid="stChatMessageContent"] {{
  background: transparent !important;
}}

[data-testid="stChatInputContainer"] {{
  background: var(--tm-white) !important;
  border-top: 1px solid var(--tm-purple-soft);
}}

[data-testid="stChatInputContainer"] textarea {{
  background: transparent !important;
}}

.stButton > button {{
  background-color: transparent;
  color: var(--tm-purple);
  border: 1.5px solid var(--tm-purple);
  border-radius: 8px;
  padding: 0.5rem 1.1rem;
}}

.stButton > button:hover {{
  background-color: transparent;
  color: #6a3eb6;
  border-color: #6a3eb6;
}}

.landing-wrap .stButton {{
  display: flex;
  justify-content: center;
  margin-top: 0.4rem;
}}
</style>
""",
        unsafe_allow_html=True,
    )


TEXT = _load_texts()


st.set_page_config(
    page_title=TEXT["page_title"],
    page_icon=":warning:",
    layout="wide",
)

_apply_styles(TEXT)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "view" not in st.session_state:
    st.session_state.view = "landing"


def _render_landing() -> None:
    _, center_col, _ = st.columns([1, 2, 1])
    with center_col:
        st.markdown(
            (
                '<section class="landing-wrap">'
                f"<h1>{TEXT['landing_title']}</h1>"
                f'<p class="landing-subtitle">{TEXT["landing_subtitle"]}</p>'
            ),
            unsafe_allow_html=True,
        )
        if st.button(TEXT["landing_cta_label"], type="primary"):
            st.session_state.view = "chat"
            st.rerun()
        if st.button(TEXT["landing_how_it_works_button_label"]):
            st.session_state.view = "how_it_works"
            st.rerun()
        st.markdown("</section>", unsafe_allow_html=True)


def _render_chat() -> None:
    st.title(TEXT["chat_title"])
    st.caption(TEXT["chat_caption"])
    nav_col1, nav_col2, _ = st.columns([1, 1, 6])
    with nav_col1:
        if st.button(TEXT["chat_back_button_label"]):
            st.session_state.view = "landing"
            st.rerun()
    with nav_col2:
        if st.button(TEXT["chat_how_it_works_button_label"]):
            st.session_state.view = "how_it_works"
            st.rerun()

    for message in st.session_state.messages:
        role = message["role"]
        if role == "assistant":
            chat_ctx = st.chat_message("assistant", avatar=TEXT["assistant_avatar"])
        else:
            chat_ctx = st.chat_message(role)

        with chat_ctx:
            st.markdown(message["content"])
            if role == "assistant":
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

    if user_prompt := st.chat_input(TEXT["chat_input_placeholder"]):
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant", avatar=TEXT["assistant_avatar"]):
            with st.spinner(TEXT["spinner_text"]):
                history_payload = _build_chat_history_payload(st.session_state.messages)
                prepared = prepare_tenth_man_stream_from_history(history_payload)
                assistant_reply = st.write_stream(prepared.token_stream)
                with st.expander(TEXT["stimulus_expander_title"], expanded=False):
                    if prepared.degraded_mode:
                        st.warning(TEXT["degraded_warning"])
                    if prepared.stimulus_summary:
                        st.markdown(f"**{TEXT['stimulus_cues_heading']}**")
                        for item in prepared.stimulus_summary:
                            st.markdown(f"- {item}")
                    else:
                        st.markdown(f"- {TEXT['no_stimulus_cues']}")
                    if prepared.sources:
                        st.markdown(f"**{TEXT['sources_heading']}**")
                        for url in prepared.sources[:5]:
                            st.markdown(f"- {url}")

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": assistant_reply,
                "stimulus_summary": prepared.stimulus_summary,
                "sources": prepared.sources,
                "degraded_mode": prepared.degraded_mode,
            }
        )

def _render_how_it_works() -> None:
    st.title(TEXT["how_title"])
    st.caption(TEXT["how_subtitle"])

    nav_col1, nav_col2, _ = st.columns([1, 1, 6])
    with nav_col1:
        if st.button(TEXT["how_back_button_label"]):
            st.session_state.view = "landing"
            st.rerun()
    with nav_col2:
        if st.button(TEXT["how_go_to_chat_button_label"]):
            st.session_state.view = "chat"
            st.rerun()

    st.markdown(f"### {TEXT['how_dsp_section_title']}")
    for bullet in TEXT["how_dsp_bullets"]:
        st.markdown(f"- {bullet}")

    st.markdown(f"### {TEXT['how_model_access_section_title']}")
    for bullet in TEXT["how_model_access_bullets"]:
        st.markdown(f"- {bullet}")


if st.session_state.view == "landing":
    _render_landing()
elif st.session_state.view == "how_it_works":
    _render_how_it_works()
else:
    _render_chat()
