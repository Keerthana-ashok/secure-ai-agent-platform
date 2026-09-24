import json
import asyncio

from app.tools.registry import ToolRegistry
from app.tools.executor import ToolExecutor, parse_tool_call
from app.agent.agent import AgentService
from app.auth.authorizer import Authorizer
from app.tools.sensitive_tools import delete_document, get_document_store_snapshot
from app.tools.rag_tool import make_search_tool


class DummyLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    async def send_prompt(self, messages):
        if not self._responses:
            return ""
        return self._responses.pop(0)


def make_registry_with_sensitive_tools():
    reg = ToolRegistry()

    # register delete_document (sensitive)
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

    # register a read-only search tool (RAG wrapper) for tests
    # make_search_tool returns a callable; it expects a retriever, but for tests we can register a stub.
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


def test_authorized_user_can_delete_and_audit():
    reg = make_registry_with_sensitive_tools()
    authorizer = Authorizer()

    # user with DOCUMENT_DELETE permission
    user = {"id": "alice", "permissions": ["DOCUMENT_DELETE", "DOCUMENT_READ"]}

    # LLM will request delete_document
    llm = DummyLLM([make_tool_call_text("delete_document", {"document_id": "doc1"}), "Done"])

    agent = AgentService(llm, reg, authorizer=authorizer, max_iterations=2)
    res = asyncio.run(agent.run("delete doc1", user=user))

    # tool_results should contain successful deletion
    assert any(isinstance(tr, dict) and tr.get("deleted") == "doc1" or ("result" in tr and tr.get("result", {}).get("deleted") == "doc1") for tr in res.get("tool_results", []))

    logs = authorizer.get_audit_logs()
    assert any(l["tool"] == "delete_document" and l["decision"] == "allowed" and l["success"] for l in logs)


def test_unauthorized_user_blocked():
    reg = make_registry_with_sensitive_tools()
    authorizer = Authorizer()

    # user without delete permission
    user = {"id": "bob", "permissions": ["DOCUMENT_READ"]}

    llm = DummyLLM([make_tool_call_text("delete_document", {"document_id": "doc1"}), "Done"])
    agent = AgentService(llm, reg, authorizer=authorizer, max_iterations=2)
    res = asyncio.run(agent.run("delete doc1", user=user))

    # tool_results should contain an authorization error
    assert any(isinstance(tr, dict) and tr.get("error") in ("unauthorized",) or ("TOOL_ERROR" in tr if isinstance(tr, dict) else False) for tr in res.get("tool_results", []))

    logs = authorizer.get_audit_logs()
    assert any(l["tool"] == "delete_document" and l["decision"] == "denied" for l in logs)


def test_llm_requests_sensitive_tool_authorization_denies():
    # same as unauthorized behavior but emphasizing LLM driven request
    reg = make_registry_with_sensitive_tools()
    authorizer = Authorizer()
    user = {"id": "eve", "permissions": []}

    llm = DummyLLM([make_tool_call_text("delete_document", {"document_id": "doc2"}), "Done"])
    agent = AgentService(llm, reg, authorizer=authorizer, max_iterations=2)
    res = asyncio.run(agent.run("please clean up unnecessary files", user=user))

    assert any(isinstance(tr, dict) and tr.get("error") == "unauthorized" for tr in res.get("tool_results", []))


def test_read_only_rag_tool_allowed_for_read_user():
    reg = make_registry_with_sensitive_tools()
    authorizer = Authorizer()
    user = {"id": "reader", "permissions": ["DOCUMENT_READ"]}

    llm = DummyLLM([make_tool_call_text("search_security_docs", {"query": "authentication"}), "Answer"])
    agent = AgentService(llm, reg, authorizer=authorizer, max_iterations=2)
    res = asyncio.run(agent.run("Find authentication info", user=user))

    # ensure search tool result is present
    assert any(isinstance(tr, dict) and ("results" in tr.get("result", {}) or tr.get("results")) for tr in res.get("tool_results", []))


def test_unknown_tool_and_invalid_args_behave():
    reg = make_registry_with_sensitive_tools()
    authorizer = Authorizer()
    user = {"id": "carol", "permissions": ["DOCUMENT_READ", "DOCUMENT_DELETE"]}

    # unknown tool
    llm = DummyLLM([make_tool_call_text("nonexistent_tool", {}), "Done"])
    agent = AgentService(llm, reg, authorizer=authorizer, max_iterations=2)
    res = asyncio.run(agent.run("call unknown", user=user))
    assert any(isinstance(tr, dict) and tr.get("error") == "unknown tool" or ("TOOL_ERROR" in tr if isinstance(tr, dict) else False) for tr in res.get("tool_results", []))

    # missing args
    llm2 = DummyLLM([make_tool_call_text("delete_document", {}), "Done"])
    agent2 = AgentService(llm2, reg, authorizer=authorizer, max_iterations=2)
    res2 = asyncio.run(agent2.run("delete something", user=user))
    assert any(isinstance(tr, dict) and "missing required" in (tr.get("error") or "") for tr in res2.get("tool_results", []))
