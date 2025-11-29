"""
Centralized helpers for configuring LiteLLM models.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from agents.extensions.models.litellm_model import LitellmModel

LOGGER = logging.getLogger(__name__)

DEFAULT_VERTEX_MODEL = "vertex_ai/gemini-2.0-flash-exp"
DEFAULT_OPENAI_MODEL = "openai/gpt-4o-mini"

# Default GCP configuration (override with environment variables)
# These are defaults only - actual values should come from environment variables
GCP_PROJECT_ID = "your-gcp-project-id"  # Set via GCP_PROJECT_ID env var
GCP_REGION = "us-central1"  # Set via GCP_REGION env var
# Gemini model (default)
VERTEX_AI_MODEL = "vertex_ai/gemini-2.0-flash-exp"
# Optional: OpenAI API key (if using OpenAI alongside Gemini)
# Should be retrieved from Secret Manager, not hardcoded
OPENAI_API_KEY_SECRET = None  # Use Secret Manager instead
CLOUD_RUN_SERVICE_ACCOUNT_EMAIL = "cloud-run-sa@your-gcp-project-id.iam.gserviceaccount.com"  # Set via env var


def _get_project_id() -> Optional[str]:
    """Return the GCP project id from environment."""
    return os.getenv("GCP_PROJECT_ID") or os.getenv("PROJECT_ID")


def build_vertex_model(model_name: str) -> LitellmModel:
    """Create a LitellmModel configured for Vertex AI."""
    project_id = _get_project_id()
    if not project_id:
        raise ValueError(
            "GCP_PROJECT_ID (or PROJECT_ID) must be set to use Vertex AI models."
        )

    region = os.getenv("GCP_REGION", "us-central1")
    
    # Set environment variables for LiteLLM to use with Vertex AI
    # LiteLLM reads these automatically when using vertex_ai/ model prefix
    
    # Use environment variable if set, otherwise use default (for local dev only)
    if not os.getenv("GCP_PROJECT_ID"):
        os.environ["GCP_PROJECT_ID"] = project_id
    if not os.getenv("GCP_REGION"):
        os.environ["GCP_REGION"] = region
    # LiteLLM also needs AWS_REGION_NAME for some providers, but for Vertex AI it uses GCP_PROJECT_ID
    # However, some LiteLLM versions expect VERTEX_PROJECT and VERTEX_LOCATION
    os.environ["VERTEX_PROJECT"] = project_id
    os.environ["VERTEX_LOCATION"] = region
    
    LOGGER.info("Using Vertex AI model '%s' in project '%s' (%s)", model_name, project_id, region)
    # LitellmModel only accepts model and api_key - project/location come from env vars
    return LitellmModel(model=model_name)


def build_openai_model(model_name: str) -> LitellmModel:
    """Create a LitellmModel configured for OpenAI models."""
    # Get API key from environment variable or Secret Manager
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # Try to get from Secret Manager if secret ID is provided
        secret_id = os.getenv("OPENAI_API_KEY_SECRET_ID")
        if secret_id:
            try:
                from google.cloud import secretmanager
                project_id = _get_project_id()
                if project_id:
                    client = secretmanager.SecretManagerServiceClient()
                    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
                    response = client.access_secret_version(request={"name": name})
                    api_key = response.payload.data.decode("UTF-8")
            except Exception as e:
                LOGGER.warning(f"Could not retrieve OpenAI API key from Secret Manager: {e}")
    
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY must be set (via environment variable or Secret Manager) when using OPENAI provider."
        )

    api_base = os.getenv("OPENAI_API_BASE")
    extra_kwargs = {"api_base": api_base} if api_base else {}

    LOGGER.info("Using OpenAI model '%s'", model_name)
    return LitellmModel(model=model_name, api_key=api_key, **extra_kwargs)


def get_litellm_model(model_override: Optional[str] = None) -> LitellmModel:
    """
    Build a LitellmModel using environment configuration.

    Priority:
      1. Respect explicit override (e.g., per-agent needs).
      2. Use OPENAI provider if LLM_PROVIDER=openai.
      3. Default to Vertex AI Gemini 2.0 Flash.
    """

    provider = os.getenv("LLM_PROVIDER", "vertex_ai").lower()

    if provider == "openai":
        model_name = model_override or os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        return build_openai_model(model_name)

    # Default to Vertex AI
    model_name = model_override or os.getenv("VERTEX_AI_MODEL", DEFAULT_VERTEX_MODEL)
    return build_vertex_model(model_name)

