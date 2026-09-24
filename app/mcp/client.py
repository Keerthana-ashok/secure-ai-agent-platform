"""Minimal MCP Client adapter.

This client wraps the official MCP Python SDK when available. For testing
we use a small adapter API so tests can inject fake MCP connections.
"""
from typing import Any, Dict, Callable, List, Optional
import logging

try:
    import mcp  # type: ignore
except Exception:  # pragma: no cover - runtime import guard
    mcp = None


class MCPClient:
    """Adapter that connects to an MCP server and discovers/invokes tools.

    If the SDK is unavailable this class raises ImportError at construction.
    Tests should instantiate their own fake client implementation.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8005):
        if mcp is None:  # pragma: no cover
            raise ImportError("mcp SDK is required to use MCPClient (install the official MCP Python SDK)")
        self.host = host
        self.port = port
        self._client = None

    def connect(self):
        """Connect to the MCP server (SDK-specific)."""
        raise NotImplementedError("MCPClient.connect requires the official SDK; tests use a fake client")

    def list_tools(self) -> List[Dict[str, Any]]:
        raise NotImplementedError()

    def invoke(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError()

    def register_tools_into_registry(self, registry) -> None:
        """Discover remote tools and register wrapper callables into a local registry.

        The wrapper callables invoke `self.invoke(tool_name, args)` and return the result.
        """
        from .allowlist import get_global_allowlist

        tools = self.list_tools()
        server_id = f"{self.host}:{self.port}"
        allow = get_global_allowlist()
        for t in tools:
            name = t.get("name")
            params = t.get("parameters") or {}
            desc = t.get("description", "")

            # attach mcp server id to params so the agent can treat results as untrusted
            params = dict(params)
            params["_mcp_server"] = server_id

            # check allowlist before registering
            if not allow.is_tool_allowed(server_id, name):
                logging.info("MCPClient: skipping unapproved tool %s from server %s", name, server_id)
                # skip unapproved tools
                continue

            logging.info("MCPClient: registering tool %s from server %s", name, server_id)

            def make_callable(n):
                def _callable(**kwargs):
                    # Extract user from kwargs if provided and pass separately to invoke
                    user = kwargs.pop("user", None)
                    return self.invoke(n, kwargs, user=user)

                return _callable

            registry.register(name=name, func=make_callable(name), description=desc, params=params)


__all__ = ["MCPClient"]
