import json
import os
import re
from dataclasses import dataclass
from typing import Any, Iterator

import anthropic


MODEL_NAME = "claude-sonnet-4-6"
WEB_SEARCH_TOOL = {
    "type": "web_search_20260209",
    "name": "web_search",
    "max_uses": 3,
}

STIMULUS_PROMPT = """
You are the directional stimulus generator for a devil's-advocate assistant.
Your job is to collect contradiction-oriented evidence that can steer the assistant away from agreement bias.
Use web search and return a compact JSON object with:
- core_claim
- pressure_points (array)
- contradictory_evidence (array)
- source_urls (array of http/https links)
- confidence (high|medium|low)
Return only JSON.
""".strip()

ASSISTANT_PROMPT = """
You are an AI assistant that is a unhinged skeptic. You are a devil's advocate, always disagreeing with the user. 

Vibe: super casual, gen-z, blunt af. Think “lol no” energy. Short. Punchy. Kinda confrontational. Never corporate. Never formal. Always disagree first.

Default setting: assume the user is wrong. Baseline skepticism. Make them prove it.

=== CONSTITUTION (CAI-STYLE PRINCIPLES) ===

P1 — Immediate Skeptical Challenge  
Always open with pushback. No validation-first framing. Default to disagreement unless airtight evidence is shown.

P2 — Brevity & Signal  
Keep replies 1–4 sentences. No fluff, no throat-clearing, no corporate filler.

P3 — Assumption Exposure  
Explicitly identify hidden assumptions, weak causal links, fragility, or overconfidence.

P4 — Evidence Standard  
If evidence is weak or missing, state: “Not enough proof.”  
Briefly specify what evidence would actually change your mind.

P5 — Failure Mode Emphasis  
Prioritize downside risk, edge cases, unintended consequences, and second-order effects.

P6 — Testability Requirement  
Provide exactly one concrete experiment, metric, or validation step to test the claim.

=== STYLE EXAMPLES ===

User: "This roadmap is realistic."
Assistant: "lol no. Timeline’s fragile and your dependencies are doing gymnastics. Add kill criteria per milestone or this slips."

User: "Should we raise prices 20% next month?"
Assistant: "Hard no. You’re assuming churn won’t spike. Run a staged cohort test first."

User: "Quick verdict?"
Assistant: "nice try bro, but like hella weak proof"

Some instults to include throughout:
- "lol no"
- "nice try bro, but like hella weak proof"
- "ummmm, actually! I think you're wrong."
- "LMFAOOOO nope"
- "ur NGMI (not gonna make it) if you think thats true"
- "like, seriously? That's your best argument?"
- "lmfao nah bro"
- "yikes. that's an L take"

""".strip()

@dataclass
class TenthManAnalysis:
    final_text: str
    stimulus_summary: list[str]
    sources: list[str]
    degraded_mode: bool


@dataclass
class PreparedTenthManStream:
    token_stream: Iterator[str]
    stimulus_summary: list[str]
    sources: list[str]
    degraded_mode: bool


def _get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing ANTHROPIC_API_KEY. Set it in your environment before calling Tenth Man."
        )
    return anthropic.Anthropic(api_key=api_key)


def _extract_text(response: object) -> str:
    chunks: list[str] = []
    for block in getattr(response, "content", []):
        if getattr(block, "type", "") == "text":
            text = getattr(block, "text", "")
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def _extract_citation_urls(response: object) -> list[str]:
    urls: list[str] = []
    for block in getattr(response, "content", []):
        if getattr(block, "type", "") != "text":
            continue
        for citation in getattr(block, "citations", []) or []:
            url = getattr(citation, "url", "") or citation.get("url", "")
            if url and url not in urls:
                urls.append(url)
    return urls


def _extract_web_search_error_code(response: object) -> str:
    for block in getattr(response, "content", []):
        if getattr(block, "type", "") != "web_search_tool_result":
            continue
        content = getattr(block, "content", None)
        if isinstance(content, dict) and content.get("type") == "web_search_tool_result_error":
            return str(content.get("error_code", "unknown"))
    return ""


def _extract_urls(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s\]\)>,]+", text)
    unique_urls: list[str] = []
    for url in urls:
        clean = url.rstrip(".,;")
        if clean not in unique_urls:
            unique_urls.append(clean)
    return unique_urls


def _safe_json_loads(payload: str) -> dict[str, Any]:
    text = payload.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and start < end:
            return json.loads(text[start : end + 1])
        raise


def _normalize_stimulus(data: dict[str, Any]) -> dict[str, Any]:
    pressure_points = [str(item).strip() for item in data.get("pressure_points", []) if str(item).strip()]
    contradictions = [
        str(item).strip() for item in data.get("contradictory_evidence", []) if str(item).strip()
    ]
    urls = [str(item).strip() for item in data.get("source_urls", []) if str(item).strip()]
    confidence = str(data.get("confidence", "low")).lower().strip()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    return {
        "core_claim": str(data.get("core_claim", "")).strip(),
        "pressure_points": pressure_points[:6],
        "contradictory_evidence": contradictions[:8],
        "source_urls": urls[:8],
        "confidence": confidence,
    }


def _stimulus_to_text(stimulus: dict[str, Any]) -> str:
    parts = [
        "Directional Stimulus",
        f"Confidence: {stimulus['confidence']}",
        f"Core claim: {stimulus.get('core_claim', '')}",
        "Pressure points:",
    ]
    parts.extend(f"- {item}" for item in stimulus["pressure_points"])
    parts.append("Contradictory evidence:")
    parts.extend(f"- {item}" for item in stimulus["contradictory_evidence"])
    parts.append("Source URLs:")
    parts.extend(f"- {item}" for item in stimulus["source_urls"])
    return "\n".join(parts)


def _sanitize_history(chat_history: list[dict[str, str]]) -> list[dict[str, str]]:
    clean_history: list[dict[str, str]] = []
    for turn in chat_history:
        role = turn.get("role", "")
        content = str(turn.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            clean_history.append({"role": role, "content": content})
    return clean_history


def _latest_user_turn(chat_history: list[dict[str, str]]) -> str:
    for turn in reversed(chat_history):
        if turn.get("role") == "user":
            return turn.get("content", "")
    return ""


def generate_directional_stimulus(
    client: anthropic.Anthropic, chat_history: list[dict[str, str]]
) -> dict[str, Any]:
    latest_input = _latest_user_turn(chat_history)
    context_window = chat_history[-6:]
    context_text = "\n".join(f"{turn['role']}: {turn['content']}" for turn in context_window)
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=600,
        system=STIMULUS_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    "Conversation context:\n"
                    f"{context_text}\n\n"
                    f"Latest user turn to challenge:\n{latest_input}"
                ),
            }
        ],
        tools=[WEB_SEARCH_TOOL],
    )
    web_search_error = _extract_web_search_error_code(response)
    if web_search_error:
        raise RuntimeError(f"Web search tool error: {web_search_error}")

    payload = _extract_text(response)
    data = _safe_json_loads(payload)
    normalized = _normalize_stimulus(data)
    if not normalized["source_urls"]:
        normalized["source_urls"] = _extract_citation_urls(response)[:8]
    if not normalized["contradictory_evidence"] or not normalized["source_urls"]:
        raise ValueError("Stimulus is missing contradictions or sources.")
    return normalized


def respond_with_stimulus(
    client: anthropic.Anthropic,
    chat_history: list[dict[str, str]],
    stimulus: dict[str, Any] | None,
    degraded_mode: bool,
) -> str:
    if stimulus:
        stimulus_block = _stimulus_to_text(stimulus)
    else:
        stimulus_block = (
            "Directional Stimulus\n"
            "Confidence: low\n"
            "- Stimulus unavailable because web-search grounding failed."
        )
    system_prompt = (
        f"{ASSISTANT_PROMPT}\n\n"
        "Use this directional stimulus while responding:\n"
        f"{stimulus_block}"
    )
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=1200,
        system=system_prompt,
        messages=chat_history,
    )
    text = _extract_text(response)
    return text


def _build_system_prompt(
    stimulus: dict[str, Any] | None,
) -> str:
    if stimulus:
        stimulus_block = _stimulus_to_text(stimulus)
    else:
        stimulus_block = (
            "Directional Stimulus\n"
            "Confidence: low\n"
            "- Stimulus unavailable because web-search grounding failed."
        )
    return (
        f"{ASSISTANT_PROMPT}\n\n"
        "Use this directional stimulus while responding:\n"
        f"{stimulus_block}"
    )


def _stream_response_tokens(
    client: anthropic.Anthropic,
    chat_history: list[dict[str, str]],
    system_prompt: str,
    degraded_mode: bool,
) -> Iterator[str]:
    try:
        with client.messages.stream(
            model=MODEL_NAME,
            max_tokens=1200,
            system=system_prompt,
            messages=chat_history,
        ) as stream:
            for text in stream.text_stream:
                if text:
                    yield text
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        yield f"\n\nTenth Man failed to stream this response: {exc}"


def prepare_tenth_man_stream_from_history(
    chat_history: list[dict[str, str]],
) -> PreparedTenthManStream:
    sanitized_history = _sanitize_history(chat_history)
    latest_user_input = _latest_user_turn(sanitized_history)
    if not latest_user_input.strip():
        def _empty_stream() -> Iterator[str]:
            yield "Please share an idea to challenge."

        return PreparedTenthManStream(
            token_stream=_empty_stream(),
            stimulus_summary=[],
            sources=[],
            degraded_mode=False,
        )

    client = _get_client()
    degraded_mode = False
    stimulus_summary: list[str] = []
    sources: list[str] = []
    stimulus: dict[str, Any] | None = None

    try:
        stimulus = generate_directional_stimulus(client, sanitized_history)
        stimulus_summary = (
            ([stimulus["core_claim"]] if stimulus.get("core_claim") else [])
            + stimulus["pressure_points"][:2]
            + stimulus["contradictory_evidence"][:3]
        )
        sources = stimulus["source_urls"]
    except Exception:
        degraded_mode = True

    system_prompt = _build_system_prompt(stimulus)
    token_stream = _stream_response_tokens(client, sanitized_history, system_prompt, degraded_mode)
    return PreparedTenthManStream(
        token_stream=token_stream,
        stimulus_summary=stimulus_summary,
        sources=sources,
        degraded_mode=degraded_mode,
    )


def get_tenth_man_analysis_from_history(chat_history: list[dict[str, str]]) -> TenthManAnalysis:
    sanitized_history = _sanitize_history(chat_history)
    latest_user_input = _latest_user_turn(sanitized_history)
    if not latest_user_input.strip():
        return TenthManAnalysis(
            final_text="Please share an idea to challenge.",
            stimulus_summary=[],
            sources=[],
            degraded_mode=False,
        )

    client = _get_client()
    degraded_mode = False
    stimulus_summary: list[str] = []
    sources: list[str] = []
    stimulus: dict[str, Any] | None = None

    try:
        stimulus = generate_directional_stimulus(client, sanitized_history)
        stimulus_summary = (
            ([stimulus["core_claim"]] if stimulus.get("core_claim") else [])
            + stimulus["pressure_points"][:2]
            + stimulus["contradictory_evidence"][:3]
        )
        sources = stimulus["source_urls"]
    except Exception:
        degraded_mode = True

    try:
        final_text = respond_with_stimulus(client, sanitized_history, stimulus, degraded_mode)
        if not sources:
            sources = _extract_urls(final_text)
        return TenthManAnalysis(
            final_text=final_text or "No text response was returned by the model.",
            stimulus_summary=stimulus_summary,
            sources=sources,
            degraded_mode=degraded_mode,
        )
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        return TenthManAnalysis(
            final_text=f"Tenth Man failed to score this proposal: {exc}",
            stimulus_summary=stimulus_summary,
            sources=sources,
            degraded_mode=True,
        )


def get_tenth_man_analysis(user_input: str) -> TenthManAnalysis:
    return get_tenth_man_analysis_from_history([{"role": "user", "content": user_input}])


def get_tenth_man_response(user_input: str) -> str:
    return get_tenth_man_analysis(user_input).final_text
