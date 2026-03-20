import os
from google.adk.agents import Agent
from .prompt import agent_instructions
from google.adk.tools import FunctionTool
from ...tools import responseExecutionTool, getPlaybookTool

response_agent = Agent(
    model= os.getenv("MODEL_ID"),
    name="response_agent",
    description="Recommends and triggers incident response actions",
    instruction= agent_instructions,
    tools=[FunctionTool(responseExecutionTool), FunctionTool(getPlaybookTool)],
    output_key="response_agent_output"
)