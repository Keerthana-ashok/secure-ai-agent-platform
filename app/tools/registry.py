"""Tool registry and tool schema generation."""
from typing import Callable, Dict, Any, List, Union


class ToolDefinition:
    def __init__(self, name: str, func: Callable, description: str, params: Dict[str, Any]):
        self.name = name
        self.func = func
        self.description = description
        self.params = params

    def to_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.params,
        }


class ToolRegistry:
    """Registry for tool definitions.

    Supports dynamic registration and retrieval. `register` accepts either a
    `ToolDefinition` instance or the traditional parameter form for convenience.
    """

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, *args, **kwargs) -> None:
        """Register a tool.

        Usage:
          register(ToolDefinition(...))
        or
          register(name=str, func=callable, description=str, params=dict)
        """
        # Support single ToolDefinition argument
        if len(args) == 1 and isinstance(args[0], ToolDefinition):
            td = args[0]
        else:
            name = kwargs.get("name") or (args[0] if args else None)
            func = kwargs.get("func") or (args[1] if len(args) > 1 else None)
            description = kwargs.get("description") or (args[2] if len(args) > 2 else "")
            params = kwargs.get("params") or (args[3] if len(args) > 3 else {})
            if not name or not func:
                raise ValueError("register requires a name and func")
            td = ToolDefinition(name, func, description, params)

        if td.name in self._tools:
            raise ValueError(f"tool already registered: {td.name}")
        self._tools[td.name] = td

    def get(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name]

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [t.to_schema() for t in self._tools.values()]


__all__ = ["ToolRegistry", "ToolDefinition"]
