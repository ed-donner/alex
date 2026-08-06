# Using Gemini 2.0 Flash with Alex Backend

## Quick Reference

All backend agents now use a shared helper (`common/llm.py`) to configure LiteLLM models. The helper defaults to Vertex AI Gemini 2.0 Flash but can switch to OpenAI by changing a single environment variable.

## Environment Variables

Add these to `.env` (and your deployment environments):

```bash
# Core project settings
PROJECT_ID=alex-multi-agent-saas-479504
GCP_PROJECT_ID=alex-multi-agent-saas-479504
GCP_REGION=us-central1

# LLM configuration
LLM_PROVIDER=vertex_ai          # or "openai"
VERTEX_AI_MODEL=vertex_ai/gemini-2.0-flash-exp
OPENAI_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=                # only required if LLM_PROVIDER=openai
OPENAI_API_BASE=               # optional custom endpoint

# Optional per-agent overrides
PLANNER_MODEL=
REPORTER_MODEL=
REPORTER_JUDGE_MODEL=
RETIREMENT_MODEL=
CHARTER_MODEL=
TAGGER_MODEL=
RESEARCHER_MODEL=
```

If you need to store secrets in Secret Manager, set the env var at runtime by reading the secret before launching the container.

## Shared Helper

All agents import the helper:

```python
from common.llm import get_litellm_model

model = get_litellm_model(os.getenv("PLANNER_MODEL"))
```

The helper automatically:

- Builds a Vertex AI LiteLLM model when `LLM_PROVIDER=vertex_ai` (using `GCP_PROJECT_ID` + `GCP_REGION`)
- Builds an OpenAI LiteLLM model when `LLM_PROVIDER=openai` (requires `OPENAI_API_KEY`)
- Accepts optional overrides, so each agent can specify a different model if needed

## When You Need OpenAI

Set:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=openai/gpt-4o-mini
```

Or override per agent:

```python
model = get_litellm_model(os.getenv("REPORTER_MODEL", "openai/gpt-4o"))
```

## Why a Shared Helper?

- Keeps all providers in one place
- Ensures consistent validation (project/region/API keys)
- Makes switching providers as simple as editing `.env`

## Testing Locally

```powershell
gcloud auth application-default login
gcloud auth application-default set-quota-project alex-multi-agent-saas-479504
```

Then run your agent test as normal; the helper will pick up the credentials.

## Cost Reminder

- Gemini 2.0 Flash ~95% cheaper than Claude Sonnet
- Keep `LLM_PROVIDER=vertex_ai` for day-to-day work, only switch to OpenAI for experiments that truly need GPT-4

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ValueError: GCP_PROJECT_ID must be set` | Populate `GCP_PROJECT_ID` (or `PROJECT_ID`) in `.env` |
| `OPENAI_API_KEY must be set` | Set `OPENAI_API_KEY` when `LLM_PROVIDER=openai` |
| `Model not found` | Check `VERTEX_AI_MODEL` or `OPENAI_MODEL` spelling and regional availability |
| `Permission denied` | Ensure `aiplatform.googleapis.com` is enabled and Cloud Run service account has `roles/aiplatform.user` |

Gemini remains the recommended default for cost and latency. Use OpenAI only when absolutely required.
