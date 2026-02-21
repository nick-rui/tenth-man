# Tenth Man

Anti-groupthink AI mediator for sustainability and smart city proposals (humans& hackathon).

## What this MVP includes

- `tenth_man.py`: core Anthropic scoring logic
- `app.py`: Streamlit fallback chat UI for live demos
- `slack_bot.py`: Slack Bolt Socket Mode app for `@mention`-driven critiques
- `render.yaml`: Render worker deployment config for persistent Slack bot runtime

## Tech stack

- Python 3.11+
- Anthropic SDK (`claude-sonnet-4.6` + `web_search_20260209`)
- Streamlit
- Slack Bolt (Socket Mode)

## Directional Stimulus Prompting (DSP) variation

This MVP implements a two-pass steering workflow inspired by DSP:

1. **Stimulus pass** (`generate_directional_stimulus` in `tenth_man.py`)
   - Uses web search to extract contradictory, real-world cues.
   - Produces a structured stimulus packet: assumptions, contradictions, historical failures, source URLs.
2. **Scoring pass** (`score_with_stimulus` in `tenth_man.py`)
   - Consumes proposal + stimulus packet.
   - Produces strict Tenth Man scorecard output.

This lets us credibly claim that external, fact-based stimuli steer the black-box model response.

## Environment variables

Set these before running:

- `ANTHROPIC_API_KEY`
- `SLACK_BOT_TOKEN` (must start with `xoxb-`)
- `SLACK_APP_TOKEN` (must start with `xapp-`)

Example:

```bash
export ANTHROPIC_API_KEY="your-key"
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_APP_TOKEN="xapp-..."
```

## Local setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run Streamlit fallback UI:

```bash
streamlit run app.py
```

3. Run Slack bot (Socket Mode):

```bash
python slack_bot.py
```

## Demo script (hackathon)

Use this flow in your live demo:

1. Paste a smart city proposal in Streamlit chat (or mention bot in Slack).
2. Show the **Directional Stimulus Used** section:
   - assumptions detected
   - contradictory facts
   - source links
3. Highlight final scorecard sections:
   - failing grade (if unsupported)
   - evidence contradictions
   - minimum changes required to pass
4. Explain the steering claim:
   - "The model is not free-form critiquing first. It is being steered by an external evidence stimulus."

## Deployment

### Streamlit Community Cloud (frontend)

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, choose **Create App**.
3. Select this repo and set the main file to `app.py`.
4. In Advanced Settings -> Secrets, add `ANTHROPIC_API_KEY`.

### Render Background Worker (backend)

1. In Render, create a new service from this GitHub repo.
2. Render auto-detects `render.yaml` and provisions:
   - worker type
   - build command: `pip install -r requirements.txt`
   - start command: `python slack_bot.py`
3. In Render dashboard environment variables, set:
   - `ANTHROPIC_API_KEY`
   - `SLACK_BOT_TOKEN`
   - `SLACK_APP_TOKEN`

## Troubleshooting degraded mode

If output says degraded mode was used:

- Confirm `ANTHROPIC_API_KEY` is set and valid.
- Retry with a more specific proposal (clear assumptions are easier to search).
- Check internet access and API availability.
- If web search grounding fails temporarily, the app still returns a conservative critique but marks it as degraded.
