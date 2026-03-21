import os
from google.adk.agents import Agent
from .prompt import agent_instructions
from google.adk.tools import FunctionTool
from ...tools import triageQueryTool

triage_agent = Agent(
    model= os.getenv("MODEL_ID"),
    name="triage_agent",
    description="Assesses alert severity, deduplication, and context via SIEM",
    instruction=agent_instructions,
    tools=[FunctionTool(triageQueryTool)],
    output_key="triage_agent_output"
)