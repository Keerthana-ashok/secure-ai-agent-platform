import json
import asyncio

from app.tools.registry import ToolRegistry, ToolDefinition
from app.tools.security_tools import (
    get_security_policy,
    lookup_security_control,
    check_password_policy,
)
from app.tools.executor import ToolExecutor, parse_tool_call


def make_registry_with_tools():
    reg = ToolRegistry()
    # register existing security policy tool
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

    # register lookup_security_control
    reg.register(
        name="lookup_security_control",
        func=lookup_security_control,
        description="Lookup a named security control",
        params={
            "type": "object",
            "properties": {"control_name": {"type": "string"}},
            "required": ["control_name"],
        },
    )

    # register check_password_policy
    reg.register(
        name="check_password_policy",
        func=check_password_policy,
        description="Check simple password policy",
        params={
            "type": "object",
            "properties": {"password": {"type": "string"}},
            "required": ["password"],
        },
    )

    return reg


def test_register_list_get_definitions():
    reg = make_registry_with_tools()
    tools = reg.list_tools()
    assert "get_security_policy" in tools
    assert "lookup_security_control" in tools
    assert "check_password_policy" in tools

    defs = reg.get_tool_definitions()
    assert isinstance(defs, list)
    names = {d["name"] for d in defs}
    assert names >= {"get_security_policy", "lookup_security_control", "check_password_policy"}


def test_retrieve_and_execute_tools():
    reg = make_registry_with_tools()
    exec = ToolExecutor(reg)

    r1 = exec.execute("get_security_policy", {"topic": "authentication"})
    assert "result" in r1 and isinstance(r1["result"], dict)
    assert r1["result"]["topic"] == "authentication"

    r2 = exec.execute("lookup_security_control", {"control_name": "rbac"})
    assert "result" in r2 and "description" in r2["result"]

    r3 = exec.execute("check_password_policy", {"password": "Secur3!"})
    assert "result" in r3 and isinstance(r3["result"], dict)
    assert r3["result"]["password_ok"] is True or isinstance(r3["result"]["issues"], list)


def test_unknown_tool_and_invalid_args():
    reg = make_registry_with_tools()
    exec = ToolExecutor(reg)

    r_unknown = exec.execute("nonexistent_tool", {})
    assert "error" in r_unknown and "unknown tool" in r_unknown["error"]

    r_missing = exec.execute("get_security_policy", {})
    assert "error" in r_missing and "missing required args" in r_missing["error"]

    r_invalid = exec.execute("lookup_security_control", {"wrong": "x"})
    assert "error" in r_invalid


async def mock_llm_flow_then_execute(reg: ToolRegistry, chosen_tool: str, args: dict):
    # Simulate LLM returning a tool call
    text = "TOOL_CALL:" + json.dumps({"name": chosen_tool, "args": args})
    call = parse_tool_call(text)
    exec = ToolExecutor(reg)
    return exec.execute(call["name"], call.get("args", {}))


def test_mocked_llm_selects_tools():
    reg = make_registry_with_tools()
    # LLM picks lookup_security_control
    res = asyncio.run(mock_llm_flow_then_execute(reg, "lookup_security_control", {"control_name": "networkpolicy"}))
    assert "result" in res and "description" in res["result"]

    # LLM picks check_password_policy
    res2 = asyncio.run(mock_llm_flow_then_execute(reg, "check_password_policy", {"password": "Weak1"}))
    assert "result" in res2 and isinstance(res2["result"], dict)
