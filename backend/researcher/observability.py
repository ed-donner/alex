"""
Langfuse observability for Alex agents.

Uses the official OpenInference instrumentation for the OpenAI Agents SDK
and Langfuse Python SDK v4 APIs (propagate_attributes, observation types).
Agents work normally when Langfuse credentials are not configured.
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from typing import Any, Iterator, Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_EMAIL_RE = re.compile(r"\b[\w.-]+@[\w.-]+\.\w+\b")
_PHONE_RE = re.compile(r"\b\d{3}[-. ]?\d{3}[-. ]?\d{4}\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

_instrumented = False
_client: Any = None


def _is_deployed() -> bool:
    return bool(
        os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        or os.getenv("AWS_EXECUTION_ENV")
        or os.getenv("AWS_APP_RUNNER_SERVICE_ID")
    )


def _sync_host_env() -> Optional[str]:
    """Langfuse accepts LANGFUSE_BASE_URL (current) or LANGFUSE_HOST (legacy)."""
    host = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST")
    if host:
        os.environ["LANGFUSE_BASE_URL"] = host
        os.environ["LANGFUSE_HOST"] = host
    return host


def _default_environment() -> str:
    return os.getenv("LANGFUSE_TRACING_ENVIRONMENT") or (
        "production" if _is_deployed() else "development"
    )


def _mask_text(value: str) -> str:
    masked = _EMAIL_RE.sub("[REDACTED EMAIL]", value)
    masked = _PHONE_RE.sub("[REDACTED PHONE]", masked)
    masked = _CARD_RE.sub("[REDACTED CARD]", masked)
    return masked


def _mask_data(*, data: Any, **kwargs: Any) -> Any:
    if isinstance(data, str):
        return _mask_text(data)
    if isinstance(data, dict):
        return {key: _mask_data(data=value) for key, value in data.items()}
    if isinstance(data, list):
        return [_mask_data(data=item) for item in data]
    return data


def _stringify_metadata(metadata: Optional[dict[str, Any]]) -> dict[str, str]:
    if not metadata:
        return {}
    result: dict[str, str] = {}
    for key, value in metadata.items():
        text = str(value)
        if len(text) > 200:
            text = text[:197] + "..."
        result[str(key)] = text
    return result


def _mask_otel_spans(*, params: Any) -> Any:
    try:
        from langfuse.types import MaskOtelSpansResult, OtelSpanPatch
    except ImportError:
        return None

    patches = {}
    for identifier, span in params.spans.items():
        replacements = {}
        for key, value in span.attributes.items():
            if isinstance(value, str):
                masked = _mask_text(value)
                if masked != value:
                    replacements[key] = masked
        if replacements:
            patches[identifier] = OtelSpanPatch(set_attributes=replacements)
    return MaskOtelSpansResult(span_patches=patches) if patches else None


@dataclass
class Observability:
    """Handle yielded by observe(). Falsy when Langfuse is not configured."""

    client: Any = None
    observation: Any = None

    def __bool__(self) -> bool:
        return self.client is not None

    def update(self, **kwargs: Any) -> None:
        if self.observation is not None:
            self.observation.update(**kwargs)

    def start_evaluator(self, name: str, **kwargs: Any):
        if self.client is None:
            return nullcontext()
        return self.client.start_as_current_observation(
            as_type="evaluator", name=name, **kwargs
        )


def setup_instrumentation() -> Any:
    """Idempotent Langfuse + OpenAI Agents SDK instrumentation."""
    global _instrumented, _client

    if _instrumented:
        return _client

    logger.info("Observability: Checking Langfuse configuration...")
    if not os.getenv("LANGFUSE_SECRET_KEY") or not os.getenv("LANGFUSE_PUBLIC_KEY"):
        logger.info("Observability: Langfuse not configured, skipping setup")
        _instrumented = True
        _client = None
        return None

    _sync_host_env()
    os.environ.setdefault("LANGFUSE_TRACING_ENVIRONMENT", _default_environment())

    try:
        from langfuse import Langfuse
        from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor

        try:
            _client = Langfuse(mask=_mask_data, mask_otel_spans=_mask_otel_spans)
        except TypeError:
            _client = Langfuse(mask=_mask_data)
        OpenAIAgentsInstrumentor().instrument()
        logger.info(
            "Observability: Langfuse client ready (environment=%s)",
            os.environ.get("LANGFUSE_TRACING_ENVIRONMENT"),
        )

        try:
            if _client.auth_check():
                logger.info("Observability: Langfuse authentication succeeded")
            else:
                logger.warning("Observability: Langfuse auth check returned false")
        except Exception as auth_error:
            logger.warning("Observability: Auth check failed but continuing: %s", auth_error)

    except ImportError as e:
        logger.error("Observability: Missing required package: %s", e)
        _client = None
    except Exception as e:
        logger.error("Observability: Setup failed: %s", e)
        _client = None

    _instrumented = True
    return _client


@contextmanager
def observe(
    *,
    name: str = "run-agent",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
    input: Any = None,
) -> Iterator[Observability]:
    """
    Trace one agent run. Groups related agents with session_id=job_id.

    Usage:
        with observe(name="plan-portfolio", session_id=job_id, user_id=user_id) as obs:
            result = asyncio.run(run_orchestrator(job_id))
            obs.update(output={"status": "completed"})
    """
    from langfuse import propagate_attributes

    client = setup_instrumentation()
    if client is None:
        yield Observability()
        return

    handle = Observability(client=client)
    try:
        with client.start_as_current_observation(
            as_type="span",
            name=name,
            input=input,
        ) as root:
            handle.observation = root
            attr_kwargs: dict[str, Any] = {
                "trace_name": name,
                "tags": tags or [],
                "metadata": _stringify_metadata(metadata),
                "version": os.getenv("LANGFUSE_RELEASE", "1.0.0"),
            }
            if user_id:
                attr_kwargs["user_id"] = user_id
            if session_id:
                attr_kwargs["session_id"] = session_id
            with propagate_attributes(**attr_kwargs):
                yield handle
    finally:
        try:
            logger.info("Observability: Flushing traces to Langfuse...")
            client.flush()
            logger.info("Observability: Traces flushed successfully")
        except Exception as e:
            logger.error("Observability: Failed to flush traces: %s", e)


@contextmanager
def observation(
    name: str,
    *,
    as_type: str = "span",
    input: Any = None,
    output: Any = None,
) -> Iterator[Any]:
    """Nested observation that no-ops when Langfuse is not configured."""
    client = _client or setup_instrumentation()
    if client is None:
        yield None
        return

    with client.start_as_current_observation(
        as_type=as_type,
        name=name,
        input=input,
    ) as obs:
        try:
            yield obs
            if output is not None:
                obs.update(output=output)
        except Exception as e:
            obs.update(output={"error": str(e)})
            raise
