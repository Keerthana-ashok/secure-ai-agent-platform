import json
import asyncio

from app.tools.registry import ToolRegistry
from app.tools.security_tools import get_security_policy
from app.tools.executor import ToolExecutor, parse_tool_call


class MockLLM:
    async def send_prompt(self, messages, **kwargs):
        # Simulate returning a tool call for 'get_security_policy'
        call = {"name": "get_security_policy", "args": {"topic": "authentication"}}
        return "TOOL_CALL:" + json.dumps(call)


async def run_flow():
    reg = ToolRegistry()
    reg.register(
        name="get_security_policy",
        func=get_security_policy,
        description="Return security policy for topic",
        params={
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
        },
    )

    llm = MockLLM()
    resp = await llm.send_prompt(None)
    call = parse_tool_call(resp)
    executor = ToolExecutor(reg)
    result = executor.execute(call["name"], call.get("args", {}))
    return result


def test_tool_flow():
    result = asyncio.run(run_flow())
    assert isinstance(result, dict)
    assert "result" in result
    assert "policy" in result["result"]
    assert "authentication" in result["result"]["policy"].lower()
