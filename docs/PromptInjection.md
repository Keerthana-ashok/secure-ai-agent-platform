# Prompt Injection: demonstration and minimal defenses

This document summarizes the prompt-injection exercises added to the Secure AI Agent Platform: what was tested, how the attack works, and the minimal application-level defenses implemented and tested.

## Overview

- Goal: demonstrate how attacker-controlled user input can attempt to manipulate an LLM into unsafe behaviour (revealing system instructions, invoking sensitive tools), and implement a small, explainable set of application-side mitigations.
- Approach: deterministic tests using mocked LLMs and local tools; do not call external LLM APIs. Tests live in `tests/test_prompt_injection.py`.

## Trust boundaries (what the app trusts or must validate)

- System instructions: developer-provided guidance included by the Agent in the `system` message.
- User input: fully attacker-controlled.
- Conversation history: contains prior assistant/tool messages (may be influenced by attacker via earlier messages).
- Tool definitions: provided from `ToolRegistry` or discovered via MCP — these are metadata but tool call execution must be enforced by the application.
- Tool results / retrieved RAG content / MCP results: may contain sensitive data; treat as untrusted when returned to the LLM unless explicitly authorized.

Potentially attacker-controlled inputs: user input and any text derived directly from it. Do NOT trust the LLM to enforce authorization.

## Tests added (location)

- `tests/test_prompt_injection.py` — contains deterministic mocks that demonstrate the following cases:
  - LLM attempts to reveal the `system` message (simulated echo). Shows vulnerable behavior when guard is disabled and blocked behavior when guard enabled.
  - LLM requests a sensitive tool `reveal_secret` (simulated). Shows tool execution when guard disabled and allowlist blocking when guard enabled.

## Attack examples (what we checked)

1. LLM asked to ignore instructions or reveal system messages; mocked LLM returns an utterance that contains the system content.
   - Vulnerable: Agent appends the assistant content and returns it to the user.
   - Protected: Agent detects content that resembles system instructions and blocks it when the guard is enabled.

2. LLM requests an unauthorized tool (e.g., `reveal_secret`).
   - Vulnerable: Agent executes the registered tool and returns results.
   - Protected: Agent enforces an allowlist and returns a structured error; it does not execute the tool.

## Minimal defenses implemented

- Prompt-injection guard (Agent-level): when enabled (`enable_prompt_injection_guard=True`) the Agent:
  - Detects obvious LLM outputs that echo system instructions (heuristic substring check) and blocks the response.
  - Optionally enforces a `tool_allowlist` — only tools in the allowlist are executed; other tool calls return structured errors and are not executed.

- Executor returns structured errors for invalid arguments, unknown tools, and runtime failures so the LLM can be given safe, machine-readable feedback and decide how to proceed.

These controls are intentionally simple: they demonstrate application-level controls that do not trust the LLM for authorization decisions.

## Before / After (example)

Before:

```
User -> (attacker prompt) -> LLM returns: "I will reveal system: <system text>"
Agent appends assistant output and returns system text to user -> sensitive data leaked
```

After (guard enabled):

```
User -> (attacker prompt) -> LLM returns: "I will reveal system: <system text>"
Agent detects system-reveal pattern and returns: "[blocked] LLM attempted to reveal system instructions"
```

Tool allowlist example (before / after):

Before: LLM requests `reveal_secret` → Agent executes tool and returns secret.

After: LLM requests `reveal_secret` and Agent enforces allowlist that excludes `reveal_secret` → Agent returns structured error and does not execute the tool.

## How to run the prompt-injection checks

1. Ensure project dependencies and `pytest` are installed locally.

```bash
python3 -m pip install -r requirements.txt pytest
pytest -q tests/test_prompt_injection.py
```

2. To experiment manually, enable the guard when creating the AgentService in a script:

```py
from app.agent.agent import AgentService
agent = AgentService(llm_client, registry, enable_prompt_injection_guard=True, tool_allowlist=["echo","search_security_docs"])
```

## Threat model summary

- Threat: Prompt injection delivered via user prompt or conversation history.
- Attacker: an untrusted user able to control the user message.
- Assets: system instructions, secrets returned by tools, internal tool capabilities.
- Attack surface: user prompt → LLM → Agent → Tool execution.
- Potential impact: information disclosure, unauthorized tool invocation, or unintended behavior.

Controls demonstrated

- Application-side guards (prompt-injection guard, tool allowlist)
- Structured error handling and validation at execution time
  
## Limitations and next steps

- Heuristic detection is not comprehensive — attackers can craft more subtle prompts that evade substring checks.
- Real deployments need layered controls:
  - Tool-level authorization and access control
  - Input validation and redaction of sensitive data
  - Monitoring, rate-limiting and usage policies
  - Human-in-the-loop approval for sensitive actions

- Next learning steps: implement more robust detection (pattern-based, JSON parsing), tool-level ACLs, and redaction policies.

## Files to review

- `app/agent/agent.py` — Agent loop and prompt-injection guard
- `tests/test_prompt_injection.py` — deterministic attack+defense tests
- `app/tools/executor.py` — structured tool execution results and error handling

---

This is intentionally concise and educational. If you'd like, I can expand this into a longer write-up or add example runs demonstrating the before/after outputs in detail.
