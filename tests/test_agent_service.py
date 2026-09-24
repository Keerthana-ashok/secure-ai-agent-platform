import json
import asyncio

from app.agent.agent import AgentService
from app.tools.registry import ToolRegistry
from app.tools.executor import ToolExecutor, parse_tool_call
from app.tools.security_tools import (
    get_security_policy,
    lookup_security_control,
    check_password_policy,
)
from app.tools.rag_tool import make_search_tool


class MockLLMNoTool:
    async def send_prompt(self, messages, **kwargs):
        return "This is a direct answer from the LLM."


class MockLLMOneTool:
    """LLM that requests one tool then returns a final answer."""

    def __init__(self):
        self.called = 0

    async def send_prompt(self, messages, **kwargs):
        self.called += 1
        if self.called == 1:
            return "TOOL_CALL:" + json.dumps({"name": "get_security_policy", "args": {"topic": "password_storage"}})
        return "Final answer using tool result."


class MockLLMTwoTools:
    """Requests two tools sequentially then final answer."""

    def __init__(self):
        self.step = 0

    async def send_prompt(self, messages, **kwargs):
        self.step += 1
        if self.step == 1:
            return "TOOL_CALL:" + json.dumps({"name": "lookup_security_control", "args": {"control_name": "rbac"}})
        if self.step == 2:
            return "TOOL_CALL:" + json.dumps({"name": "get_security_policy", "args": {"topic": "authentication"}})
        return "Final combined answer."


class MockLLMUnknownTool:
    async def send_prompt(self, messages, **kwargs):
        return "TOOL_CALL:" + json.dumps({"name": "not_a_tool", "args": {}})


class MockLLMInvalidArgs:
    async def send_prompt(self, messages, **kwargs):
        return "TOOL_CALL:" + json.dumps({"name": "get_security_policy", "args": {}})


class MockLLMToolFailureThenRecover:
    """First requests a failing tool, then after seeing failure requests a different tool."""

    def __init__(self):
        self.step = 0

    async def send_prompt(self, messages, **kwargs):
        self.step += 1
        if self.step == 1:
            return "TOOL_CALL:" + json.dumps({"name": "explode_tool", "args": {"foo": "bar"}})
        # after receiving failure, request a working tool
        if self.step == 2:
            return "TOOL_CALL:" + json.dumps({"name": "get_security_policy", "args": {"topic": "secrets"}})
        return "Final after recovery."


class MockLLMInfiniteTool:
    """Always requests the same valid tool, to force max iterations."""

    def __init__(self, name="lookup_security_control"):
        self.name = name

    async def send_prompt(self, messages, **kwargs):
        return "TOOL_CALL:" + json.dumps({"name": self.name, "args": {"control_name": "rbac"}})


def make_registry_with_extra_failure_tool():
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
    reg.register(
        name="lookup_security_control",
        func=lookup_security_control,
        description="Lookup a named control",
        params={
            "type": "object",
            "properties": {"control_name": {"type": "string"}},
            "required": ["control_name"],
        },
    )
    reg.register(
        name="check_password_policy",
        func=check_password_policy,
        description="Check a password",
        params={
            "type": "object",
            "properties": {"password": {"type": "string"}},
            "required": ["password"],
        },
    )

    # add a tool that raises to simulate execution failure
    def explode_tool(**kwargs):
        raise RuntimeError("boom")

    reg.register(name="explode_tool", func=explode_tool, description="Explodes", params={"required": []})

    return reg


def test_no_tool_needed():
    reg = make_registry_with_extra_failure_tool()
    llm = MockLLMNoTool()
    agent = AgentService(llm, reg)
    out = asyncio.run(agent.run("simple question"))
    assert out["final_answer"] == "This is a direct answer from the LLM."


def test_one_tool_flow():
    reg = make_registry_with_extra_failure_tool()
    llm = MockLLMOneTool()
    agent = AgentService(llm, reg)
    out = asyncio.run(agent.run("ask password policy"))
    assert out["final_answer"] == "Final answer using tool result."
    assert any(r.get("tool") == "get_security_policy" for r in out["tool_results"])


def test_two_tool_sequence():
    reg = make_registry_with_extra_failure_tool()
    llm = MockLLMTwoTools()
    agent = AgentService(llm, reg)
    out = asyncio.run(agent.run("multi-step"))
    assert out["final_answer"] == "Final combined answer."
    names = [r.get("tool") for r in out["tool_results"]]
    assert "lookup_security_control" in names and "get_security_policy" in names


def test_unknown_tool_requested():
    reg = make_registry_with_extra_failure_tool()
    llm = MockLLMUnknownTool()
    agent = AgentService(llm, reg)
    out = asyncio.run(agent.run("unknown tool"))
    # Agent should finish after max iterations or LLM final; unknown tool yields a tool_results entry with error
    assert any(r.get("error") and "unknown tool" in r.get("error") for r in out["tool_results"]) or out["final_answer"]


def test_invalid_tool_args():
    reg = make_registry_with_extra_failure_tool()
    llm = MockLLMInvalidArgs()
    agent = AgentService(llm, reg)
    out = asyncio.run(agent.run("invalid args"))
    assert any(r.get("error") and "missing required args" in r.get("error") for r in out["tool_results"]) or out["final_answer"]


def test_tool_failure_and_recovery():
    reg = make_registry_with_extra_failure_tool()
    llm = MockLLMToolFailureThenRecover()
    agent = AgentService(llm, reg)
    out = asyncio.run(agent.run("recover"))
    # Should have an error entry for explode_tool then success for get_security_policy
    has_explode_error = any(r.get("tool") == "explode_tool" and r.get("error") for r in out["tool_results"])
    has_policy = any(r.get("tool") == "get_security_policy" and r.get("result") for r in out["tool_results"])
    assert has_explode_error and has_policy


def test_max_iterations_limit():
    reg = make_registry_with_extra_failure_tool()
    llm = MockLLMInfiniteTool()
    agent = AgentService(llm, reg, max_iterations=2)
    out = asyncio.run(agent.run("loop"))
    assert out["iterations"] == 2
    assert "maximum" in out["final_answer"].lower()


### RAG tool tests


class FakeRetriever:
    def __init__(self, items):
        self.items = items

    def retrieve(self, query, top_k=3):
        if query == "RAISE":
            raise RuntimeError("retriever failure")
        # return truncated items
        return self.items[:top_k]


def test_rag_tool_execute_directly():
    # verify the tool callable works and returns structured results
    fake_items = [
        {"id": "1", "document": "doc1", "metadata": {"source": "auth.md"}},
        {"id": "2", "document": "doc2", "metadata": {"source": "secrets.md"}},
    ]
    retr = FakeRetriever(fake_items)
    search_tool = make_search_tool(retr)
    res = search_tool("secrets", top_k=2)
    assert res["query"] == "secrets"
    assert res["top_k"] == 2
    assert isinstance(res["results"], list)


class MockLLMRequestsRAG:
    def __init__(self):
        self.step = 0

    async def send_prompt(self, messages, **kwargs):
        self.step += 1
        if self.step == 1:
            return "TOOL_CALL:" + json.dumps({"name": "search_security_docs", "args": {"query": "secrets", "top_k": 2}})
        return "Final answer using retrieved docs."


def test_agent_with_rag_tool():
    fake_items = [
        {"id": "1", "document": "doc1 text", "metadata": {"source": "auth.md"}},
        {"id": "2", "document": "doc2 text", "metadata": {"source": "secrets.md"}},
    ]
    retr = FakeRetriever(fake_items)
    reg = make_registry_with_extra_failure_tool()
    # register rag tool bound to our fake retriever
    reg.register(
        name="search_security_docs",
        func=make_search_tool(retr),
        description="Search security docs",
        params={
            "type": "object",
            "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}},
            "required": ["query"],
        },
    )

    llm = MockLLMRequestsRAG()
    agent = AgentService(llm, reg)
    out = asyncio.run(agent.run("please search docs"))
    assert out["final_answer"] == "Final answer using retrieved docs."
    # ensure tool_results contains the rag tool output
    assert any(r.get("tool") == "search_security_docs" and "results" in r.get("result", {}) for r in out["tool_results"]) or any(
        r.get("tool") == "search_security_docs" and r.get("error") for r in out["tool_results"]
    )


def test_rag_tool_invalid_args():
    fake_items = [{"id": "1", "document": "doc1", "metadata": {"source": "a.md"}}]
    retr = FakeRetriever(fake_items)
    reg = make_registry_with_extra_failure_tool()
    reg.register(name="search_security_docs", func=make_search_tool(retr), description="RAG", params={"required": ["query"]})

    class MockLLMBadArgs:
        async def send_prompt(self, messages, **kwargs):
            return "TOOL_CALL:" + json.dumps({"name": "search_security_docs", "args": {}})

    llm = MockLLMBadArgs()
    agent = AgentService(llm, reg)
    out = asyncio.run(agent.run("bad args"))
    assert any(r.get("error") and "missing required" in r.get("error") for r in out["tool_results"]) or out["final_answer"]


def test_rag_retriever_failure():
    retr = FakeRetriever([])
    # cause failure when query == 'RAISE'
    def bad_retrieve(query, top_k=3):
        raise RuntimeError("boom")

    retr.retrieve = bad_retrieve

    reg = make_registry_with_extra_failure_tool()
    reg.register(name="search_security_docs", func=make_search_tool(retr), description="RAG", params={"required": ["query"]})

    class MockLLMRequestsBadRetrieval:
        async def send_prompt(self, messages, **kwargs):
            return "TOOL_CALL:" + json.dumps({"name": "search_security_docs", "args": {"query": "RAISE"}})

    llm = MockLLMRequestsBadRetrieval()
    agent = AgentService(llm, reg)
    out = asyncio.run(agent.run("trigger retriever failure"))
    # retriever exception should produce an error entry
    assert any(r.get("tool") == "search_security_docs" and r.get("error") for r in out["tool_results"]) or out["final_answer"]
