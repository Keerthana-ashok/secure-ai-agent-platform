"""Minimal MCP Server adapter.

This module provides a thin adapter around the official MCP Python SDK.
If the SDK is not installed, the classes here raise ImportError to make
the dependency explicit. Tests should use a fake server implementation
so they do not require the SDK.
"""
from typing import Callable, Dict, Any

try:
    import mcp  # type: ignore
except Exception as e:  # pragma: no cover - runtime import guard
    mcp = None


class MCPServer:
    """Adapter for an MCP server that exposes tools backed by local callables.

    This server registers a single tool `search_security_docs` which delegates
    to a retriever callable passed at construction time.
    """

    def __init__(self, retriever_callable: Callable[[str, int], Any], host: str = "127.0.0.1", port: int = 8005):
        if mcp is None:  # pragma: no cover - only if mcp SDK is available
            raise ImportError("mcp SDK is required to run MCPServer (install the official MCP Python SDK)")
        self.retriever = retriever_callable
        self.host = host
        self.port = port
        self._server = None

    def start(self):
        # Implementation depends on official SDK; left as an adapter.
        # A real implementation would register tool schemas and handlers
        # via the MCP server APIs and start listening.
        raise NotImplementedError("MCP server adapter requires the official MCP SDK and is not implemented here")

    def stop(self):
        if self._server:
            # stop server
            pass


__all__ = ["MCPServer"]
