import os
import re

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from tenth_man import get_tenth_man_analysis_from_history


load_dotenv()
STATUS_MESSAGE = "Consulting the devil..."


def _require_env(var_name: str, expected_prefix: str) -> str:
    value = os.environ.get(var_name, "")
    if not value:
        raise RuntimeError(f"Missing required env var: {var_name}")
    if not value.startswith(expected_prefix):
        raise RuntimeError(f"{var_name} should start with '{expected_prefix}'")
    return value


def _strip_mention(text: str) -> str:
    return re.sub(r"<@[A-Z0-9]+>", "", text).strip()


def _format_sources(sources: list[str]) -> str:
    if not sources:
        return ""
    lines = ["\nSources:"]
    for idx, url in enumerate(sources[:3], start=1):
        lines.append(f"{idx}. {url}")
    return "\n".join(lines)


def _parse_user_prompt(event: dict) -> str:
    return _strip_mention(event.get("text", ""))


def _message_role(message: dict, bot_user_id: str) -> str | None:
    if message.get("user") == bot_user_id:
        return "assistant"
    if message.get("subtype") == "bot_message" or message.get("bot_id"):
        return "assistant"
    if message.get("user"):
        return "user"
    return None


def _fetch_channel_history(client, channel_id: str) -> list[dict]:
    messages: list[dict] = []
    cursor: str | None = None

    while True:
        kwargs = {"channel": channel_id, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        response = client.conversations_history(**kwargs)
        messages.extend(response.get("messages", []))
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    # conversations.history returns newest first.
    return list(reversed(messages))


def _to_chat_history(messages: list[dict], bot_user_id: str) -> list[dict[str, str]]:
    chat_history: list[dict[str, str]] = []
    for message in messages:
        if message.get("subtype") in {"channel_join", "channel_leave"}:
            continue
        role = _message_role(message, bot_user_id=bot_user_id)
        if role is None:
            continue
        text = _strip_mention(str(message.get("text", "")))
        if role == "assistant" and text == STATUS_MESSAGE:
            continue
        if text:
            chat_history.append({"role": role, "content": text})
    return chat_history


def _looks_like_context_overflow(final_text: str) -> bool:
    lowered = final_text.lower()
    markers = [
        "prompt is too long",
        "maximum context length",
        "context window",
        "too many tokens",
        "input is too long",
    ]
    return final_text.startswith("Tenth Man failed to score this proposal:") and any(
        marker in lowered for marker in markers
    )


def _analysis_with_truncation(chat_history: list[dict[str, str]]):
    total = len(chat_history)
    candidate_sizes = [total, 400, 200, 100, 50, 20]
    unique_sizes: list[int] = []
    for size in candidate_sizes:
        bounded = min(size, total)
        if bounded > 0 and bounded not in unique_sizes:
            unique_sizes.append(bounded)

    last_analysis = None
    for idx, size in enumerate(unique_sizes, start=1):
        scoped_history = chat_history[-size:]
        analysis = get_tenth_man_analysis_from_history(scoped_history)
        last_analysis = analysis
        print(
            "[slack_bot] analysis attempt",
            {"attempt": idx, "used_messages": size, "overflow": _looks_like_context_overflow(analysis.final_text)},
            flush=True,
        )
        if not _looks_like_context_overflow(analysis.final_text):
            return analysis, size
    return last_analysis, unique_sizes[-1]


def _build_slack_reply(analysis) -> str:
    cleaned = analysis.final_text.replace(STATUS_MESSAGE, "").strip()
    if not cleaned:
        cleaned = "No response generated."
    return cleaned + _format_sources(analysis.sources)


slack_bot_token = _require_env("SLACK_BOT_TOKEN", "xoxb-")
app = App(token=slack_bot_token)
bot_user_id = app.client.auth_test()["user_id"]


@app.event("app_mention")
def handle_mention(event, say):
    print(
        "[slack_bot] app_mention received",
        {
            "channel": event.get("channel"),
            "user": event.get("user"),
            "ts": event.get("ts"),
            "text_preview": str(event.get("text", ""))[:120],
        },
        flush=True,
    )
    user_text = _parse_user_prompt(event)
    say(STATUS_MESSAGE)

    channel_id = event.get("channel", "")
    history_messages = _fetch_channel_history(app.client, channel_id)
    chat_history = _to_chat_history(history_messages, bot_user_id=bot_user_id)
    if user_text and (
        not chat_history or chat_history[-1]["role"] != "user" or chat_history[-1]["content"] != user_text
    ):
        chat_history.append({"role": "user", "content": user_text})

    print(
        "[slack_bot] history prepared",
        {"fetched_messages": len(history_messages), "usable_messages": len(chat_history)},
        flush=True,
    )

    if not chat_history:
        say("No usable channel history found to analyze yet.")
        return

    analysis, used_count = _analysis_with_truncation(chat_history)
    print(
        "[slack_bot] analysis complete",
        {
            "used_messages": used_count,
            "sources_count": len(analysis.sources),
            "response_chars": len(analysis.final_text),
        },
        flush=True,
    )
    response_text = _build_slack_reply(analysis)
    say(response_text)


if __name__ == "__main__":
    slack_app_token = _require_env("SLACK_APP_TOKEN", "xapp-")
    handler = SocketModeHandler(app, slack_app_token)
    handler.start()
