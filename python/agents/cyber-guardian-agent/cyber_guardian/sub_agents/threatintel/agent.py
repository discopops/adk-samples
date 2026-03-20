import os
from google.adk.agents import Agent
from .prompt import agent_instructions

from google.adk.tools import FunctionTool
from ...tools import threatIntelQueryTool


threatintel_agent = Agent(
    model= os.getenv("MODEL_ID"),
    name="threat_intel_agent",
    description="Enriches IPs/domains/hashes with threat intelligence context",
    instruction=agent_instructions,
    tools=[FunctionTool(threatIntelQueryTool)],
    output_key="threatintel_agent_output"
)