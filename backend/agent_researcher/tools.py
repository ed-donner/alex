"""
Tools for the Alex Researcher agent using AgentCore
"""
import os
from typing import Dict, Any
from datetime import datetime, UTC
import httpx
from strands.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

logger = logging.getLogger(__name__)


def _ingest(document: Dict[str, Any], api_endpoint: str, api_key: str) -> Dict[str, Any]:
    """Internal function to make the actual API call."""
    with httpx.Client() as client:
        response = client.post(
            api_endpoint,
            json=document,
            headers={"x-api-key": api_key},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def ingest_with_retries(document: Dict[str, Any], api_endpoint: str, api_key: str) -> Dict[str, Any]:
    """Ingest with retry logic for SageMaker cold starts."""
    return _ingest(document, api_endpoint, api_key)


@tool
def ingest_financial_document(topic: str, analysis: str, alex_api_endpoint: str, alex_api_key: str) -> Dict[str, Any]:
    """
    Ingest a financial document into the Alex knowledge base.
    
    Args:
        topic: The topic or subject of the analysis (e.g., "AAPL Stock Analysis", "Retirement Planning Guide")
        analysis: Detailed analysis or advice with specific data and insights
    
    Returns:
        Dictionary with success status and document ID
    """
    logger.info(f"Researcher: Ingesting document with topic: {topic}")
    
    # Read environment variables at runtime
    alex_api_endpoint = os.getenv("ALEX_API_ENDPOINT")
    alex_api_key = os.getenv("ALEX_API_KEY")
    
    logger.info(f"Researcher: API endpoint configured: {bool(alex_api_endpoint)}")
    logger.info(f"Researcher: API key configured: {bool(alex_api_key)}")
    
    if not alex_api_endpoint or not alex_api_key:
        logger.warning("Researcher: Alex API not configured, running in local mode")
        return {
            "success": False,
            "error": "Alex API not configured. Running in local mode."
        }
    
    document = {
        "text": analysis,
        "metadata": {
            "topic": topic,
            "timestamp": datetime.now(UTC).isoformat()
        }
    }
    
    try:
        result = ingest_with_retries(document, alex_api_endpoint, alex_api_key)
        logger.info(f"Researcher: Successfully ingested document: {topic}")
        return {
            "success": True,
            "document_id": result.get("document_id"),
            "message": f"Successfully ingested analysis for {topic}"
        }
    except Exception as e:
        logger.error(f"Researcher: Failed to ingest document: {e}")
        return {
            "success": False,
            "error": str(e)
        }