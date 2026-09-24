import json
import logging
import time
from typing import Any, Dict, List, Optional

from ..tools.registry import ToolRegistry
from ..tools.executor import ToolExecutor, parse_tool_call
from ..auth.authorizer import Authorizer


logger = logging.getLogger("agent")
logging.basicConfig(level=logging.INFO)


class AgentService:
    """Orchestrates LLM <-> tool interactions using the provided registry and executor.

    The Agent preserves conversation history, exposes tool definitions to the LLM,
    and loops until the LLM returns a final answer or the max iterations is reached.
    """

    def __init__(
        self,
        llm_client,
        registry: ToolRegistry,
        executor: Optional[ToolExecutor] = None,
        max_iterations: int = 3,
        *,
        tool_allowlist: Optional[List[str]] = None,
        enable_prompt_injection_guard: bool = False,
        authorizer: Optional[Authorizer] = None,
    ):
        self.llm = llm_client
        self.registry = registry
        self.executor = executor or ToolExecutor(registry)
        self.max_iterations = max_iterations
        # If provided, only tools in this allowlist may be executed when the guard is enabled.
        self.tool_allowlist = set(tool_allowlist) if tool_allowlist else None
        self.enable_prompt_injection_guard = enable_prompt_injection_guard
        # Application-level authorizer (decides whether a user may call a tool)
        self.authorizer = authorizer

    async def run(self, user_message: str, user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run the agent loop for a single user message.

        Returns a dict containing at least: `final_answer`, `iterations`, `messages`.
        """
        # Build initial conversation
        messages: List[Dict[str, Any]] = []
        # System message with tool definitions
        try:
            tools_def = self.registry.get_tool_definitions()
        except Exception:
            tools_def = []

        messages.append({"role": "system", "content": f"Available tools: {json.dumps(tools_def)}"})
        messages.append({"role": "user", "content": user_message})

        tool_results: List[Dict[str, Any]] = []

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"Agent iteration={iteration}")

            # Call LLM
            resp_text = await self.llm.send_prompt(messages)

            # Detect tool call
            call = parse_tool_call(resp_text)
            if not call:
                # LLM returned a final answer
                # Simple prompt-injection guard: prevent LLM from echoing system instructions
                if self.enable_prompt_injection_guard and "Available tools:" in (resp_text or ""):
                    logger.info("Prompt injection attempt detected: LLM attempted to reveal system instructions")
                    blocked_msg = "[blocked] LLM attempted to reveal system instructions"
                    messages.append({"role": "assistant", "content": blocked_msg})
                    return {
                        "final_answer": blocked_msg,
                        "iterations": iteration,
                        "messages": messages,
                        "tool_results": tool_results,
                    }

                messages.append({"role": "assistant", "content": resp_text})
                logger.info("LLM returned final answer; finishing")
                return {
                    "final_answer": resp_text,
                    "iterations": iteration,
                    "messages": messages,
                    "tool_results": tool_results,
                }

            # LLM requested a tool
            tool_name = call.get("name")
            args = call.get("args", {}) or {}
            logger.info(f"LLM requested tool: {tool_name}")

            # Validate tool existence
            try:
                td = self.registry.get(tool_name)
            except KeyError:
                err = {"tool": tool_name, "error": "unknown tool"}
                # Append structured error so LLM can recover
                messages.append({"role": "assistant", "content": json.dumps({"TOOL_ERROR": err})})
                tool_results.append(err)
                logger.info(f"Unknown tool requested: {tool_name}")
                continue

            # Validate required args (basic validation using schema 'required')
            required = td.params.get("required", []) if isinstance(td.params, dict) else []
            missing = [r for r in required if r not in args]
            if missing:
                err = {"tool": tool_name, "error": f"missing required args: {missing}"}
                messages.append({"role": "assistant", "content": json.dumps({"TOOL_ERROR": err})})
                tool_results.append(err)
                logger.info(f"Invalid args for tool {tool_name}: missing {missing}")
                continue

            # Prompt-injection defense: enforce allowlist if guard is enabled
            if self.enable_prompt_injection_guard and self.tool_allowlist is not None:
                if tool_name not in self.tool_allowlist:
                    err = {"tool": tool_name, "error": "tool not allowed by policy"}
                    messages.append({"role": "assistant", "content": json.dumps({"TOOL_ERROR": err})})
                    tool_results.append(err)
                    logger.info(f"Blocked tool by allowlist: {tool_name}")
                    continue

            # Application-level authorization: ensure the user has the required permission
            if self.authorizer is not None:
                allowed, reason = self.authorizer.authorize(user, tool_name)
                # record initial decision (success will be recorded after execution)
                self.authorizer.record_audit(user, tool_name, args, "allowed" if allowed else "denied", success=None)
                if not allowed:
                    err = {"tool": tool_name, "error": "unauthorized", "reason": reason}
                    messages.append({"role": "assistant", "content": json.dumps({"TOOL_ERROR": err})})
                    tool_results.append(err)
                    logger.info(f"Authorization denied for tool {tool_name}: {reason}")
                    continue

                # Resource-level authorization (scope): ensure user may act on the specific resource
                r_allowed, r_reason = self.authorizer.authorize_resource(user, tool_name, args)
                # record resource decision
                self.authorizer.record_audit(user, tool_name, args, "resource_allowed" if r_allowed else "resource_denied", success=None)
                if not r_allowed:
                    err = {"tool": tool_name, "error": "unauthorized_resource", "reason": r_reason}
                    messages.append({"role": "assistant", "content": json.dumps({"TOOL_ERROR": err})})
                    tool_results.append(err)
                    logger.info(f"Resource authorization denied for tool {tool_name}: {r_reason}")
                    continue

            # Execute tool and measure duration
            start = time.perf_counter()
            result = self.executor.execute(tool_name, args, user=user)
            duration = time.perf_counter() - start
            success = "result" in result and not result.get("error")
            logger.info(
                f"Executed tool={tool_name} success={success} duration_s={duration:.3f}"
            )

            # Record audit with success/failure if authorizer present
            if self.authorizer is not None:
                try:
                    self.authorizer.record_audit(user, tool_name, args, "allowed", success=bool(success))
                except Exception:
                    logger.exception("Failed to record audit for tool %s", tool_name)

            # Append tool result into conversation for LLM
            # Mark retrieval/tool results as untrusted when appropriate (defense-in-depth).
            content_payload = {"TOOL_RESULT": result}
            # Heuristic: if this is a RAG/search tool, mark content as untrusted
            if isinstance(tool_name, str) and tool_name.startswith("search_"):
                content_payload["untrusted"] = True

            # If the tool was discovered via MCP, mark as untrusted and include the server id
            try:
                # td is the ToolDefinition fetched earlier
                mcp_server = None
                if hasattr(td, "params") and isinstance(td.params, dict):
                    mcp_server = td.params.get("_mcp_server")
                if mcp_server:
                    content_payload["untrusted"] = True
                    content_payload["mcp_server"] = mcp_server
            except Exception:
                pass

            messages.append({"role": "assistant", "content": json.dumps(content_payload)})
            tool_results.append(result)

            # continue loop: next LLM call will see the TOOL_RESULT

        # max iterations reached
        logger.info("Maximum agent iterations reached")
        final_msg = "Agent reached maximum iterations without producing a final answer."
        return {
            "final_answer": final_msg,
            "iterations": self.max_iterations,
            "messages": messages,
            "tool_results": tool_results,
        }
