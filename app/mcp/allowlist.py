"""Simple MCP server/tool allowlist for client-side enforcement."""
from typing import Dict, List

# Example allowlist: map server_id -> list of allowed tool names
DEFAULT_ALLOWLIST = {
    "security-docs": ["search_security_docs"],
}


class MCPAllowlist:
    def __init__(self, allowlist: Dict[str, List[str]] = None):
        self.allowlist = allowlist or dict(DEFAULT_ALLOWLIST)

    def is_server_allowed(self, server_id: str) -> bool:
        return server_id in self.allowlist

    def is_tool_allowed(self, server_id: str, tool_name: str) -> bool:
        tools = self.allowlist.get(server_id, [])
        return tool_name in tools


_GLOBAL_ALLOWLIST = MCPAllowlist()


def get_global_allowlist() -> MCPAllowlist:
    return _GLOBAL_ALLOWLIST


def set_global_allowlist(allowlist: Dict[str, List[str]]):
    global _GLOBAL_ALLOWLIST
    _GLOBAL_ALLOWLIST = MCPAllowlist(allowlist)
