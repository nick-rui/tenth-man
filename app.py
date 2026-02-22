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

.landing-title {{
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
  background-color: var(--tm-white) !important;
  border-top: 1px solid var(--tm-purple-soft);
  bottom: 2.8rem !important;
}}

[data-testid="stBottomBlockContainer"],
[data-testid="stBottomBlockContainer"] > div,
[data-testid="stBottomBlockContainer"] > div > div,
[data-testid="stChatFloatingInputContainer"] {{
  background: var(--tm-white) !important;
  background-color: var(--tm-white) !important;
  background-image: none !important;
  backdrop-filter: none !important;
}}

[data-testid="stChatInput"] {{
  background: var(--tm-white) !important;
  background-color: var(--tm-white) !important;
}}

[data-testid="stChatInputContainer"] > div,
[data-testid="stChatInputContainer"] > div > div,
[data-testid="stChatInputContainer"] > div > div > div {{
  background: var(--tm-white) !important;
  background-color: var(--tm-white) !important;
}}

[data-testid="stChatInputContainer"] [data-baseweb="textarea"],
[data-testid="stChatInputContainer"] [data-baseweb="base-input"],
[data-testid="stChatInputContainer"] [data-baseweb="input"],
[data-testid="stChatInputContainer"] [data-baseweb="textarea"] > div {{
  background: var(--tm-white) !important;
  background-color: var(--tm-white) !important;
}}

[data-testid="stChatInputContainer"] textarea {{
  background: var(--tm-white) !important;
  background-color: var(--tm-white) !important;
}}

[data-testid="stChatInputContainer"] input {{
  background: var(--tm-white) !important;
  background-color: var(--tm-white) !important;
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
                f'<h1 class="landing-title">{TEXT["landing_title"]}</h1>'
                f'<p class="landing-subtitle">{TEXT["landing_subtitle"]}</p>'
            ),
            unsafe_allow_html=True,
        )
        if st.button(TEXT["landing_cta_label"], type="primary"):
            st.session_state.view = "chat"
            st.rerun()
        st.markdown("</section>", unsafe_allow_html=True)


def _render_chat() -> None:
    st.title(TEXT["chat_title"])
    st.caption(TEXT["chat_caption"])
    nav_col1, _ = st.columns([1, 7])
    with nav_col1:
        if st.button(TEXT["chat_back_button_label"]):
            st.session_state.view = "landing"
            st.rerun()

    for message in st.session_state.messages:
        role = message["role"]
        if role == "assistant":
            chat_ctx = st.chat_message("assistant", avatar=TEXT["assistant_avatar"])
        else:
            chat_ctx = st.chat_message(role)

        with chat_ctx:
            st.markdown(message["content"])

    if user_prompt := st.chat_input(TEXT["chat_input_placeholder"]):
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant", avatar=TEXT["assistant_avatar"]):
            with st.spinner(TEXT["spinner_text"]):
                history_payload = _build_chat_history_payload(st.session_state.messages)
                prepared = prepare_tenth_man_stream_from_history(history_payload)
                assistant_reply = st.write_stream(prepared.token_stream)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": assistant_reply,
            }
        )


if st.session_state.view == "landing":
    _render_landing()
else:
    _render_chat()
