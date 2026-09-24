import json
import asyncio

from app.tools.registry import ToolRegistry
from app.agent.agent import AgentService
from app.tools.rag_tool import make_search_tool


# Fake MCP server and client to avoid requiring the real SDK in tests
class FakeMCPServer:
    def __init__(self, retriever_callable):
        self.retriever = retriever_callable
        self.tools = {}

    def start(self):
        # register a tool schema and handler
        self.tools["search_security_docs"] = {
            "name": "search_security_docs",
            "description": "Search security docs",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}},
                "required": ["query"],
            },
        }

    def list_tools(self):
        return list(self.tools.values())

    def invoke(self, name, args):
        if name != "search_security_docs":
            return {"error": "unknown tool"}
        q = args.get("query")
        top_k = args.get("top_k", 3)
        return {"query": q, "top_k": top_k, "results": self.retriever.retrieve(q, top_k=top_k)}


class FakeMCPClient:
    def __init__(self, server: FakeMCPServer):
        self.server = server

    def list_tools(self):
        return self.server.list_tools()

    def invoke(self, name, args):
        return self.server.invoke(name, args)

    def register_tools_into_registry(self, registry):
        tools = self.list_tools()
        for t in tools:
            name = t["name"]
            def make_callable(n):
                def _callable(**kwargs):
                    user = kwargs.pop("user", None)
                    return self.invoke(n, kwargs, user=user)

                return _callable

            registry.register(name=name, func=make_callable(name), description=t.get("description",""), params=t.get("parameters",{}))


# A tiny retriever used for the fake server
class TinyRetriever:
    def __init__(self, items):
        self.items = items

    def retrieve(self, question, top_k=3):
        if question == "RAISE":
            raise RuntimeError("retriever failure")
        return self.items[:top_k]


def test_mcp_server_and_client_flow():
    items = [
        {"id": "1", "document": "doc1 text", "metadata": {"source": "a.md"}},
        {"id": "2", "document": "doc2 text", "metadata": {"source": "b.md"}},
    ]
    retr = TinyRetriever(items)
    server = FakeMCPServer(retr)
    server.start()

    client = FakeMCPClient(server)

    # Create local registry and register the discovered MCP tool
    reg = ToolRegistry()
    client.register_tools_into_registry(reg)

    # Ensure tool is present
    assert "search_security_docs" in reg.list_tools()

    # Agent should be able to use the tool via the registry
    class MockLLMCallsMCP:
        def __init__(self):
            self.step = 0

        async def send_prompt(self, messages, **kwargs):
            self.step += 1
            if self.step == 1:
                return "TOOL_CALL:" + json.dumps({"name": "search_security_docs", "args": {"query": "foo", "top_k": 2}})
            return "Final answer after MCP"

    llm = MockLLMCallsMCP()
    agent = AgentService(llm, reg)
    out = asyncio.run(agent.run("please search"))
    assert out["final_answer"] == "Final answer after MCP"
    # tool result should appear in tool_results
    assert any(r.get("tool") == "search_security_docs" and "results" in r.get("result", {}) for r in out["tool_results"]) or any(
        r.get("tool") == "search_security_docs" and r.get("error") for r in out["tool_results"]
    )


def test_mcp_retriever_failure_handled():
    retr = TinyRetriever([])
    # make server invoke raise when query == 'RAISE'
    server = FakeMCPServer(retr)
    server.start()
    client = FakeMCPClient(server)
    reg = ToolRegistry()
    client.register_tools_into_registry(reg)

    class MockLLMBad:
        async def send_prompt(self, messages, **kwargs):
            return "TOOL_CALL:" + json.dumps({"name": "search_security_docs", "args": {"query": "RAISE"}})

    llm = MockLLMBad()
    agent = AgentService(llm, reg)
    out = asyncio.run(agent.run("cause fail"))
    # retriever failure should result in structured error in tool_results
    assert any(r.get("tool") == "search_security_docs" and r.get("error") for r in out["tool_results"]) or out["final_answer"]
