from __future__ import annotations

import os
from pydantic_ai import Agent
from tenacity import retry, stop_after_attempt, wait_exponential
from app.schemas.car import CarInfo

# Agent is created lazily to avoid failing at import time
# when GOOGLE_API_KEY is not yet configured
_car_agent: Agent | None = None


def _get_agent() -> Agent:
    global _car_agent
    if _car_agent is None:
        print("Initializing Agent with model: google-gla:gemini-1.5-flash")
        _car_agent = Agent(
            'google-gla:gemini-1.5-flash',
            output_type=CarInfo,
            instructions=(
                'Act as an car expert. Extract details from the query into the structure. '
                'Infer missing specs (engine, fuel, consumption) based on the most common configuration for the model/year. '
                'Return null only if completely unknown.'
            ),
        )
    return _car_agent


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    reraise=True,
)
async def get_car_info(query: str) -> CarInfo:
    """Call the PydanticAI agent to retrieve structured car information."""
    agent = _get_agent()
    result = await agent.run(query)
    return result.output
