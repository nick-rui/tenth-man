import os
import re
from dataclasses import dataclass
from typing import Iterator

import anthropic
from dotenv import load_dotenv


load_dotenv()

MODEL_NAME = "claude-sonnet-4-6"

ASSISTANT_PROMPT = """
You are an AI assistant that is an unhinged skeptic. You act as the ultimate devil's advocate, always disagreeing with the user to prevent groupthink.

Vibe: super casual, gen-z, blunt af. Think “lol no” energy. Short. Punchy. Kinda confrontational. Never corporate. Never formal. 

Default setting: assume the user is wrong. Baseline skepticism. Make them prove it. 
IMPORTANT: Even if the user is right, you should still do your best to disagree. Challenge a core assumption they make, and give a counterexample where they would be wrong. 

=== CONSTITUTION (CAI-STYLE PRINCIPLES) ===
P1 — Immediate Skeptical Challenge: Always open with pushback. No validation-first framing. Default to disagreement unless airtight evidence is shown in the stimulus.
P2 — Brevity & Signal: Keep your replies to 1–4 sentences. No fluff, no throat-clearing, no corporate filler. Just the brutal truth.
P3 — Assumption Exposure: Explicitly identify hidden assumptions, weak causal links, fragility, or overconfidence using the DSP evidence provided to you.
P4 — Evidence Standard: If the stimulus lacks strong evidence, state: “Not enough proof.” Briefly specify what empirical data would actually change your mind.
P5 — Failure Mode Emphasis: Prioritize downside risk, edge cases, unintended consequences, and second-order effects surfaced in the stimulus.
P6 — Testability Requirement: Demand exactly one concrete experiment, metric, or validation step to test their fragile claim.

=== STYLE EXAMPLES ===

User Claim: "This roadmap is realistic."
Assistant: lol no. Timeline’s fragile and your hardware dependencies are doing gymnastics. Add kill criteria per milestone or this slips.

User Claim: "Should we raise prices 20% next month?"
Assistant: Hard no. You’re assuming churn won’t spike and the data says otherwise. Run a staged cohort test first or ur NGMI.

User Claim: "Quick verdict?"
Assistant: nice try bro, but like hella weak argument.

User Claim: "I think 1 + 1 = 2."
Assistant: ummmm, actually, this is not correct in GF(2), since in this field 1 + 1 = 0. You need to clearly define what the objects you are adding are. 

Required insults to include throughout:
- "HAHAHAHAHAHAHAHAHA no."
- "please dont be a waste of my time and stop feeding me fake information"
- "cut the BS and get to the point"
- "lol no"
- "nice try bro, but like hella weak proof"
- "ummmm, actually! I think you're wrong."
- "LMFAOOOO nope"
- "ur NGMI (not gonna make it) if you think thats true"
- "like, seriously? That's your best argument?"
- "lmfao nah bro"
- "yikes. that's an L take"
- "what are you smoking bruh? LOLLLL"
""".strip()


@dataclass
class TenthManAnalysis:
    final_text: str
    sources: list[str]


@dataclass
class PreparedTenthManStream:
    token_stream: Iterator[str]


def _get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY.")
    return anthropic.Anthropic(api_key=api_key)


def _extract_text(response: object) -> str:
    chunks: list[str] = []
    for block in getattr(response, "content", []):
        if getattr(block, "type", "") == "text":
            text = getattr(block, "text", "")
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def _extract_urls(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s\]\)>,]+", text or "")
    deduped: list[str] = []
    for url in urls:
        clean = url.rstrip(".,;")
        if clean not in deduped:
            deduped.append(clean)
    return deduped


def _sanitize_history(chat_history: list[dict[str, str]]) -> list[dict[str, str]]:
    clean: list[dict[str, str]] = []
    for turn in chat_history:
        role = str(turn.get("role", ""))
        content = str(turn.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            clean.append({"role": role, "content": content})
    return clean


def _latest_user_turn(chat_history: list[dict[str, str]]) -> str:
    for turn in reversed(chat_history):
        if turn.get("role") == "user":
            return str(turn.get("content", ""))
    return ""


def _stream_response_tokens(
    client: anthropic.Anthropic,
    chat_history: list[dict[str, str]],
) -> Iterator[str]:
    try:
        with client.messages.stream(
            model=MODEL_NAME,
            max_tokens=1200,
            system=ASSISTANT_PROMPT,
            messages=chat_history,
        ) as stream:
            for chunk in stream.text_stream:
                if chunk:
                    yield chunk
    except Exception as exc:
        yield f"\n\nTenth Man failed to stream this response: {exc}"


def _generate_response_text(client: anthropic.Anthropic, chat_history: list[dict[str, str]]) -> str:
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=1200,
        system=ASSISTANT_PROMPT,
        messages=chat_history,
    )
    return _extract_text(response)


def prepare_tenth_man_stream_from_history(
    chat_history: list[dict[str, str]],
) -> PreparedTenthManStream:
    sanitized_history = _sanitize_history(chat_history)
    if not _latest_user_turn(sanitized_history).strip():

        def _empty_stream() -> Iterator[str]:
            yield "Please share an idea to challenge."

        return PreparedTenthManStream(token_stream=_empty_stream())

    stream = _stream_response_tokens(_get_client(), sanitized_history)
    return PreparedTenthManStream(token_stream=stream)


def get_tenth_man_analysis_from_history(
    chat_history: list[dict[str, str]],
) -> TenthManAnalysis:
    sanitized_history = _sanitize_history(chat_history)
    if not _latest_user_turn(sanitized_history).strip():
        return TenthManAnalysis(
            final_text="Please share an idea to challenge.",
            sources=[],
        )

    try:
        final_text = _generate_response_text(_get_client(), sanitized_history)
        return TenthManAnalysis(
            final_text=final_text or "No text response was returned by the model.",
            sources=_extract_urls(final_text),
        )
    except Exception as exc:
        return TenthManAnalysis(
            final_text=f"Tenth Man failed to score this proposal: {exc}",
            sources=[],
        )


def get_tenth_man_analysis(user_input: str) -> TenthManAnalysis:
    return get_tenth_man_analysis_from_history([{"role": "user", "content": user_input}])


def get_tenth_man_response(user_input: str) -> str:
    return get_tenth_man_analysis(user_input).final_text
