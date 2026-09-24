"""Demo the tool-calling flow with the DummyLLM.

This script shows:
 - how tool definitions are provided to the LLM
 - how an LLM requests a tool call using the TOOL_CALL: JSON convention
 - how the application executes the tool and returns the TOOL_RESULT: JSON
 - how the LLM then returns a final answer
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asyncio
import json

from app.tools.registry import ToolRegistry
from app.tools.security_tools import get_security_policy
from app.tools.executor import ToolExecutor, parse_tool_call, format_tool_result
from app.llm.client import LLMClient


class DummyLLM:
    """A dummy LLM that demonstrates requesting a tool call for 'secrets'."""

    async def send_prompt(self, messages, **kwargs):
        # messages are ignored; this dummy decides to call the 'get_security_policy' tool
        # for demonstration. It returns the TOOL_CALL marker with tool name and args.
        call = {"name": "get_security_policy", "args": {"topic": "secrets"}}
        return "TOOL_CALL:" + json.dumps(call)


async def demo():
    # Build registry and register the security tool
    reg = ToolRegistry()
    reg.register(
        name="get_security_policy",
        func=get_security_policy,
        description="Return a short security policy for a requested topic.",
        params={
            "type": "object",
            "properties": {"topic": {"type": "string", "description": "security topic"}},
            "required": ["topic"],
        },
    )

    # Provide tool schema to LLM (in a real integration these would be included in the prompt)
    schemas = reg.get_tool_definitions()
    print("Tool schemas provided to LLM:")
    print(json.dumps(schemas, indent=2))

    # Call LLM with the user question and tool schemas (dummy llm returns a tool call)
    dummy = DummyLLM()
    user_question = "What are best practices for managing secrets?"
    print("\nUser question:", user_question)
    llm_response = await dummy.send_prompt(None)
    print("\nLLM response (requested):", llm_response)

    # Parse the tool call and execute
    call = parse_tool_call(llm_response)
    executor = ToolExecutor(reg)
    result = executor.execute(call["name"], call.get("args", {}))
    print("\nTool execution result:", result)

    # Send tool result back to LLM (in real flow you would call LLM again)
    tool_result_message = "TOOL_RESULT:" + json.dumps(result)
    print("\nTool result sent back to LLM:", tool_result_message)

    # Dummy final response (in real flow, LLM would now answer using tool result)
    final = "Based on retrieved policy: " + result["result"]["policy"]
    print("\nFinal answer:\n", final)


if __name__ == "__main__":
    asyncio.run(demo())
