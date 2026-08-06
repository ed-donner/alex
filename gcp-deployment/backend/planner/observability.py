"""
Observability module for LangFuse integration.
Provides a simple context manager for setting up and flushing traces.
"""

import os
import logging
from contextlib import contextmanager

# Use root logger for Lambda compatibility
logger = logging.getLogger()
logger.setLevel(logging.INFO)


@contextmanager
def observe():
    """
    Context manager for observability with LangFuse.

    Sets up LangFuse observability if environment variables are configured,
    and ensures traces are flushed on exit.

    Usage:
        from observability import observe

        with observe():
            # Your code that uses OpenAI Agents SDK
            result = await agent.run(...)
    """
    logger.info("🔍 Observability: Checking configuration...")

    # Check if required environment variables exist
    has_langfuse = bool(os.getenv("LANGFUSE_SECRET_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))

    logger.info(f"🔍 Observability: LANGFUSE_SECRET_KEY exists: {has_langfuse}")
    logger.info(f"🔍 Observability: OPENAI_API_KEY exists: {has_openai}")

    if not has_langfuse:
        logger.info("🔍 Observability: LangFuse not configured, skipping setup")
        yield
        return

    if not has_openai:
        logger.warning("⚠️  Observability: OPENAI_API_KEY not set, traces may not export")

    # Local variable for the client (no global needed)
    langfuse_client = None

    # Try to set up LangFuse
    try:
        logger.info("🔍 Observability: Setting up LangFuse...")

        import logfire
        from langfuse import get_client

        # Configure logfire to instrument OpenAI Agents SDK
        logfire.configure(
            service_name="alex_planner_agent",
            send_to_logfire=False,  # Don't send to Logfire cloud
        )
        logger.info("✅ Observability: Logfire configured")

        # Instrument OpenAI Agents SDK
        logfire.instrument_openai_agents()
        logger.info("✅ Observability: OpenAI Agents SDK instrumented")

        # Initialize LangFuse client
        langfuse_client = get_client()
        logger.info("✅ Observability: LangFuse client initialized")

        # Optional: Check authentication (blocking call, use sparingly)
        try:
            auth_result = langfuse_client.auth_check()
            logger.info(
                f"✅ Observability: LangFuse authentication check passed (result: {auth_result})"
            )
        except Exception as auth_error:
            logger.warning(f"⚠️  Observability: Auth check failed but continuing: {auth_error}")

        logger.info("🎯 Observability: Setup complete - traces will be sent to LangFuse")

    except ImportError as e:
        logger.error(f"❌ Observability: Missing required package: {e}")
        langfuse_client = None
    except Exception as e:
        logger.error(f"❌ Observability: Setup failed: {e}")
        langfuse_client = None

    try:
        # Yield control back to the calling code
        yield
    finally:
        # Flush traces on exit
        if langfuse_client:
            try:
                logger.info("🔍 Observability: Flushing traces to LangFuse...")
                langfuse_client.flush()
                langfuse_client.shutdown()

                # Add a 10 second delay to ensure network requests complete
                # This is a workaround for Lambda's immediate termination
                import time

                logger.info("🔍 Observability: Waiting 15 seconds for flush to complete...")
                time.sleep(15)

                logger.info("✅ Observability: Traces flushed successfully")
            except Exception as e:
                logger.error(f"❌ Observability: Failed to flush traces: {e}")
        else:
            logger.debug("🔍 Observability: No client to flush")
