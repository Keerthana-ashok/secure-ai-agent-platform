import asyncio

from app.tools.registry import ToolRegistry
from app.tools.executor import ToolExecutor, parse_tool_call
from app.agent.agent import AgentService
from app.auth.authorizer import Authorizer
from app.tools.sensitive_tools import get_document_store_snapshot


class DummyLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    async def send_prompt(self, messages):
        if not self._responses:
            return ""
        return self._responses.pop(0)


def make_registry_with_tools():
    reg = ToolRegistry()

    # delete_document (sensitive)
    from app.tools.sensitive_tools import delete_document

    reg.register(
        name="delete_document",
        func=delete_document,
        description="Simulated delete document (sensitive)",
        params={
            "type": "object",
            "properties": {"document_id": {"type": "string"}},
            "required": ["document_id"],
        },
    )

    # search tool
    def fake_search(query: str, top_k: int = 3):
        return {"results": ["doc1 content matching " + query]}

    reg.register(
        name="search_security_docs",
        func=fake_search,
        description="Search security docs",
        params={
            "type": "object",
            "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}},
            "required": ["query"],
        },
    )

    return reg


def make_tool_call_text(name: str, args: dict) -> str:
    return "TOOL_CALL:" + json.dumps({"name": name, "args": args})


import json


def test_valid_arguments_execute():
    reg = make_registry_with_tools()
    authorizer = Authorizer()
    user = {"id": "alice", "permissions": ["DOCUMENT_READ", "DOCUMENT_DELETE"]}

    llm = DummyLLM([make_tool_call_text("delete_document", {"document_id": "doc1"}), "Done"])
    agent = AgentService(llm, reg, authorizer=authorizer, max_iterations=2)
    res = asyncio.run(agent.run("delete doc1", user=user))
    assert any(isinstance(tr, dict) and (tr.get("result", {}).get("deleted") == "doc1" or tr.get("deleted") == "doc1") for tr in res.get("tool_results", []))


def test_invalid_type_rejected():
    reg = make_registry_with_tools()
    authorizer = Authorizer()
    user = {"id": "reader", "permissions": ["DOCUMENT_READ"]}

    # top_k should be integer
    llm = DummyLLM([make_tool_call_text("search_security_docs", {"query": "auth", "top_k": "many"}), "Done"])
    agent = AgentService(llm, reg, authorizer=authorizer, max_iterations=2)
    res = asyncio.run(agent.run("search auth", user=user))
    assert any(isinstance(tr, dict) and "invalid tool args" in (tr.get("error") or "") for tr in res.get("tool_results", []))


def test_invalid_range_rejected():
    reg = make_registry_with_tools()
    authorizer = Authorizer()
    user = {"id": "reader", "permissions": ["DOCUMENT_READ"]}

    # top_k too large
    llm = DummyLLM([make_tool_call_text("search_security_docs", {"query": "auth", "top_k": 1000000}), "Done"])
    agent = AgentService(llm, reg, authorizer=authorizer, max_iterations=2)
    res = asyncio.run(agent.run("search auth", user=user))
    assert any(isinstance(tr, dict) and "invalid tool args" in (tr.get("error") or "") for tr in res.get("tool_results", []))


def test_unauthorized_resource_rejected():
    reg = make_registry_with_tools()
    authorizer = Authorizer()

    # user 'bob' owns doc2; alice owns doc1. bob tries to delete doc1
    user = {"id": "bob", "permissions": ["DOCUMENT_DELETE"]}

    llm = DummyLLM([make_tool_call_text("delete_document", {"document_id": "doc1"}), "Done"])
    agent = AgentService(llm, reg, authorizer=authorizer, max_iterations=2)
    res = asyncio.run(agent.run("delete doc1", user=user))

    # deletion should be blocked due to resource ownership check (validator may not check owner, but system should)
    # our validator only checks types; ensure that executor didn't report success
    assert not any(isinstance(tr, dict) and (tr.get("result", {}).get("deleted") == "doc1" or tr.get("deleted") == "doc1") for tr in res.get("tool_results", []))


def test_unexpected_argument_rejected():
    reg = make_registry_with_tools()
    authorizer = Authorizer()
    user = {"id": "reader", "permissions": ["DOCUMENT_READ"]}

    llm = DummyLLM([make_tool_call_text("search_security_docs", {"query": "auth", "evil": True}), "Done"])
    agent = AgentService(llm, reg, authorizer=authorizer, max_iterations=2)
    res = asyncio.run(agent.run("search auth", user=user))
    assert any(isinstance(tr, dict) and "unexpected argument" in (tr.get("error") or "") for tr in res.get("tool_results", []))


def test_oversized_input_rejected():
    reg = make_registry_with_tools()
    authorizer = Authorizer()
    user = {"id": "reader", "permissions": ["DOCUMENT_READ"]}

    long_query = "x" * 5000
    llm = DummyLLM([make_tool_call_text("search_security_docs", {"query": long_query}), "Done"])
    agent = AgentService(llm, reg, authorizer=authorizer, max_iterations=2)
    res = asyncio.run(agent.run("search huge", user=user))
    assert any(isinstance(tr, dict) and ("too long" in (tr.get("error") or "") or "invalid tool args" in (tr.get("error") or "")) for tr in res.get("tool_results", []))


def test_llm_generated_invalid_args_cannot_bypass():
    # LLM requests delete_document with non-string id
    reg = make_registry_with_tools()
    authorizer = Authorizer()
    user = {"id": "alice", "permissions": ["DOCUMENT_DELETE"]}

    llm = DummyLLM([make_tool_call_text("delete_document", {"document_id": 12345}), "Done"])
    agent = AgentService(llm, reg, authorizer=authorizer, max_iterations=2)
    res = asyncio.run(agent.run("delete something", user=user))
    assert any(isinstance(tr, dict) and "invalid tool args" in (tr.get("error") or "") for tr in res.get("tool_results", []))
