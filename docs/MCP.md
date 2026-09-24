# Minimal MCP Integration

This project includes a small learning-oriented MCP adapter that demonstrates
how to expose existing capabilities as MCP tools and how to discover/invoke
those tools from an AI application.

What is MCP?
- MCP is a protocol that standardizes communication between AI applications
  and external capability providers (tools, services, data sources).

MCP Server
- The MCP Server registers tools and serves them over the MCP protocol.
- In this project the MCP server would expose `search_security_docs(query, top_k)`
  and delegates the actual work to the existing RAG retriever.

MCP Client
- The MCP Client connects to one or more MCP servers, discovers available tools,
  and registers wrapper callables into the local `ToolRegistry` so the Agent
  and LLM can use them as if they were local tools.

Agent Integration
- The `AgentService` continues to orchestrate LLM ↔ tools.
- Tools discovered via MCP are registered into `ToolRegistry` with callables
  that invoke MCP remotely; the Agent routes the request through the registry
  and therefore does not need to know whether a tool is local or remote.

Limitations
- This learning integration provides adapters and tests using fake MCP
  server/client objects. To run against a real MCP server, install the
  official MCP Python SDK and provide a concrete server implementation.
 