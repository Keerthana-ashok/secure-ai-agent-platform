"""Tool executor and simple LLM-tool call orchestration.

This executor supports at most one tool call per request for clarity.
It expects LLM outputs requesting tool calls to follow a simple convention:
the LLM returns a string that starts with "TOOL_CALL:" followed by a JSON
object: {"name": "tool_name", "args": {...}}. This keeps the demo
independent of any LLM SDK.
"""
import json
from typing import Any, Dict, Optional

from .registry import ToolRegistry
from .validators import validate_tool_args


class ToolExecutionError(Exception):
    pass


class ToolExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, tool_name: str, args: Dict[str, Any], user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Validate tool exists
        try:
            td = self.registry.get(tool_name)
        except KeyError:
            return {"tool": tool_name, "error": f"unknown tool: {tool_name}"}

        # Validate required params present
        required = td.params.get("required", []) if isinstance(td.params, dict) else []
        missing = [r for r in required if r not in args]
        if missing:
            return {"tool": tool_name, "error": f"missing required args: {missing}"}

        # Validate against per-tool validators / schema
        try:
            ok, reason = validate_tool_args(tool_name, args or {}, user or {})
            if not ok:
                return {"tool": tool_name, "error": f"invalid tool args: {reason}"}
        except Exception as e:
            return {"tool": tool_name, "error": f"validation error: {e}"}

        # Execute tool and catch errors; return structured result or error
        try:
            # Prefer calling the tool with user context if supported by the callable.
            try:
                result = td.func(**args, user=user)
            except TypeError:
                # fallback to calling without user kwarg for legacy callables
                result = td.func(**args)
            return {"tool": tool_name, "result": result}
        except TypeError as e:
            return {"tool": tool_name, "error": f"invalid arguments for tool {tool_name}: {e}"}
        except Exception as e:
            return {"tool": tool_name, "error": f"tool execution error: {e}"}


def parse_tool_call(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text.startswith("TOOL_CALL:"):
        return {}
    json_part = text[len("TOOL_CALL:") :].strip()
    try:
        return json.loads(json_part)
    except Exception:
        return {}


def format_tool_call(name: str, args: Dict[str, Any]) -> str:
    return "TOOL_CALL:" + json.dumps({"name": name, "args": args})


def format_tool_result(result: Dict[str, Any]) -> str:
    return "TOOL_RESULT:" + json.dumps(result)


__all__ = ["ToolExecutor", "parse_tool_call", "format_tool_call", "format_tool_result", "ToolExecutionError"]
