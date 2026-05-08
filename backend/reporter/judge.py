from agents import Agent, Runner
from pydantic import BaseModel, Field
import os
import logging
from agents.extensions.models.litellm_model import LitellmModel

logger = logging.getLogger()


def create_model():
    """Create the configured model, defaulting to Bedrock unless OpenAI is selected."""
    model_provider = os.getenv("MODEL_PROVIDER", "bedrock").lower()
    if model_provider == "openai":
        model_id = os.getenv("OPENAI_MODEL_ID", "gpt-4.1-mini")
        logger.info(f"Judge: Using OpenAI model {model_id}")
        return model_id

    model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
    bedrock_region = os.getenv("BEDROCK_REGION", "us-west-2")
    os.environ["AWS_REGION_NAME"] = bedrock_region
    os.environ["AWS_REGION"] = bedrock_region
    os.environ["AWS_DEFAULT_REGION"] = bedrock_region
    logger.info(f"Judge: Using Bedrock model {model_id} in {bedrock_region}")
    return LitellmModel(model=f"bedrock/{model_id}")


class Evaluation(BaseModel):
    feedback: str = Field(
        description="Your feedback on the financial report and rationale for your score"
    )
    score: float = Field(
        description="Score from 0 to 100 where 0 represents a terrible quality financial report and 100 represents an outstanding financial report"
    )


async def evaluate(original_instructions, original_task, original_output) -> Evaluation:
    model = create_model()

    instructions = """
You are an Evaluation Agent that evaluates the quality of a financial report from a financial planning agent.
You will be provided with the instructions that were sent to the analyst, and its output, and you must evaluate the quality of the output.
"""

    # Create task
    task = f"""
The financial planning agent was given the following instructions:

{original_instructions}

And it was assigned this task:

{original_task}

The financial planning agent's output was:

{original_output}

Evaluate this output and respond with your comments and score.
"""

    try:
        logger.info("Judging financial report")
        agent = Agent(
            name="Judge Agent", instructions=instructions, model=model, output_type=Evaluation
        )
        result = await Runner.run(agent, input=task, max_turns=5)
        return result.final_output_as(Evaluation)
    except Exception as e:
        logger.error(f"Error evaluating financial report: {e}")
        return Evaluation(feedback=f"Error evaluating financial report: {e}", score=80)
