import os
import re

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from tenth_man import get_tenth_man_analysis


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
    lines = ["\nStimulus Evidence:"]
    for idx, url in enumerate(sources[:3], start=1):
        lines.append(f"{idx}. {url}")
    return "\n".join(lines)


slack_bot_token = _require_env("SLACK_BOT_TOKEN", "xoxb-")
app = App(token=slack_bot_token)


@app.event("app_mention")
def handle_mention(event, say):
    user_text = _strip_mention(event.get("text", ""))

    say("Tenth Man is actively scoring these assumptions against real-world data...")

    if not user_text:
        say("Please include a proposal after mentioning me.")
        return

    analysis = get_tenth_man_analysis(user_text)
    response_text = analysis.final_text

    if analysis.degraded_mode:
        response_text = (
            "Warning: Search-backed directional stimulus was unavailable for this run.\n\n"
            f"{response_text}"
        )

    response_text += _format_sources(analysis.sources)
    say(response_text)


if __name__ == "__main__":
    slack_app_token = _require_env("SLACK_APP_TOKEN", "xapp-")
    handler = SocketModeHandler(app, slack_app_token)
    handler.start()
