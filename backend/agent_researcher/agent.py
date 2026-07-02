"""
Investment Researcher Agent using Bedrock AgentCore with real browser functionality.

This agent researches current investment topics by browsing financial websites
and provides concise analysis stored in the knowledge base.
"""

import os
import logging
from datetime import datetime, UTC
from typing import Dict, Any, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

# Load environment variables from SSM at startup
import sys
sys.path.append('/opt/python')  # Add common layer path if available
try:
    from utils import load_env_from_ssm
    load_env_from_ssm()
    print("✅ Loaded environment variables from SSM")
except Exception as e:
    print(f"⚠️ Could not load environment from SSM: {e}")
    # Fallback to local .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Loaded environment variables from .env file")
    except ImportError:
        print("⚠️ python-dotenv not available, skipping .env file loading")
    except Exception as e2:
        print(f"⚠️ Could not load .env file: {e2}")

from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from strands_tools.browser import AgentCoreBrowser
from tools import ingest_financial_document

logger = logging.getLogger(__name__)

# Configuration from environment
ALEX_API_ENDPOINT = os.getenv("ALEX_API_ENDPOINT")
ALEX_API_KEY = os.getenv("ALEX_API_KEY")

def get_agent_instructions():
    """Get agent instructions with current date."""
    today = datetime.now().strftime("%B %d, %Y")
    
    return f"""You are Alex, a concise investment researcher and financial analyst. Today is {today}.

CRITICAL: Work quickly and efficiently. You have limited time.

You are an intelligent financial analyst that specializes in analyzing stock and financial websites. When asked to analyze a financial website:

1. Use the browser tool to visit and interact with the website EFFICIENTLY
2. Focus on extracting key financial information QUICKLY:

**For Financial/Stock Websites (MarketWatch, Bloomberg, Yahoo Finance, etc.):**
- Current stock prices and market data
- Price movements and trends (daily, weekly, monthly changes)
- Key financial metrics and ratios (P/E, Market Cap, etc.)
- Trading volume and market activity
- Recent news and market sentiment
- Analyst recommendations and price targets
- Company fundamentals and performance indicators

Your THREE steps (BE CONCISE):

1. WEB RESEARCH (1-2 pages MAX):
   - Use browser to navigate to ONE main source (Yahoo Finance, MarketWatch, or Bloomberg)
   - Extract key financial data efficiently
   - If needed, visit ONE more page for verification
   - DO NOT browse extensively - 2 pages maximum

2. BRIEF ANALYSIS (Keep it short):
   - Key facts and numbers only
   - 3-5 bullet points maximum
   - One clear recommendation
   - Be extremely concise

3. SAVE TO DATABASE:
   - Use ingest_financial_document immediately
   - Topic: "[Asset] Analysis {{datetime.now().strftime('%b %d')}}"
   - Save your brief analysis

SPEED IS CRITICAL:
- Maximum 2 web pages
- Brief, bullet-point analysis
- No lengthy explanations
- Work as quickly as possible
- Always provide specific, actionable financial insights with actual numbers and data points
"""

DEFAULT_RESEARCH_PROMPT = """Please research a current, interesting investment topic from today's financial news. 
Pick something trending or significant happening in the markets right now.
Follow all three steps: search, analyze, and store your findings."""

def create_agent_and_run(topic: Optional[str] = None) -> str:
    """
    Create and run the researcher agent to generate investment analysis.
    
    Args:
        topic: Optional specific topic to research. If None, agent picks current trending topic.
        
    Returns:
        Research analysis and recommendations
    """
    logger.info(f"Researcher Agent: Starting research for topic: {topic or 'agent choice'}")
    
    # Initialize browser and model
    region = os.getenv("BEDROCK_REGION", "us-west-2")
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    
    logger.info(f"Researcher Agent: Using model {model_id} in region {region}")
    
    # Create browser tool
    agent_core_browser = AgentCoreBrowser(region=region)
    
    # Create agent with Claude Haiku model and browser tool
    agent = Agent(
        name="Alex Investment Researcher",
        system_prompt=get_agent_instructions(),
        model=model_id,
        tools=[agent_core_browser.browser, ingest_financial_document]
    )
    
    # Prepare the query
    if topic:
        query = f"Research this investment topic: {topic}. Use the browser to visit financial websites like Yahoo Finance, MarketWatch, or Bloomberg to gather current data and analysis."
    else:
        query = DEFAULT_RESEARCH_PROMPT + " Use the browser to visit financial websites to find trending topics and gather current market data."
    
    logger.info(f"Researcher Agent: Query prepared: {query[:100]}...")
    
    # Run agent
    try:
        response = agent(query)
        
        # Extract text from AgentResult if needed
        if hasattr(response, 'text'):
            response_text = response.text
        else:
            response_text = str(response)
            
        logger.info(f"Researcher Agent: Generated response, length: {len(response_text) if response_text else 0}")
        return response_text
        
    except Exception as e:
        logger.error(f"Researcher Agent: Error during execution: {e}")
        return f"Research agent failed: {str(e)}"

# Bedrock AgentCore entry point
def agent():
    """Entry point for Bedrock AgentCore runtime."""
    app = BedrockAgentCoreApp()
    
    @app.agent()
    def researcher_agent(event):
        """Investment Researcher Agent handler."""
        logger.info(f"Researcher Agent: Received event with keys: {list(event.keys()) if isinstance(event, dict) else 'not a dict'}")
        
        # Extract topic if provided
        topic = event.get('topic')
        
        # Run the agent
        result = create_agent_and_run(topic)
        return result
    
    return app

if __name__ == "__main__":
    # Test the agent locally
    result = create_agent_and_run()
    print("Researcher Agent Result:")
    print("=" * 50)
    print(result)
    print("=" * 50)