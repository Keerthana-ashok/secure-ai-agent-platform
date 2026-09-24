# AI Security Architecture

This document consolidates the secure design, threat model, controls, and tests implemented in this repository. It is a security-focused reference implementation intended for engineering review and experimentation — not a production deployment guide.

## 1. Architecture Overview

High-level control and data-flow (interaction summary):

- User (external actor)
- Authentication (app-managed)
- Authorization (app-managed; Authorizer)
- Agent / Orchestrator (`AgentService`)
- LLM (external model provider via `LLMClient`)
- RAG / Tools / MCP (retriever, tool registry, MCP client)
- Authorized Data / External Systems
- Tool Results / Retrieved Context (tagged with provenance/trust)
- LLM (for reasoning + generation)
- Output Security Checks (application-layer validation, sanitization)
- User

Major trust boundaries:

- Trust Boundary 1 — User → Application: user input is untrusted.
- Trust Boundary 2 — Application → LLM: LLM outputs are not security decisions.
- Trust Boundary 3 — Agent → Tools: LLM-generated tool requests must be validated/authorized.
- Trust Boundary 4 — MCP Client → MCP Server: remote MCP servers are external and untrusted by default.
- Trust Boundary 5 — RAG → LLM: retrieved documents are untrusted and may be poisoned.
- Trust Boundary 6 — Application → External Data: external systems/data require explicit authorization.

## 2. Threat Model (concise)

This project targets common threats for LLM-enabled systems. Each threat below lists attack, controls implemented in this repository, and test coverage.

- Prompt Injection
  - Attack: user includes instructions that try to alter agent behavior.
  - Controls (implemented): prompt-injection guard that prevents assistant from echoing system/tool definitions; restricted tool exposure; agent enforces authorization.
  - Test: `tests/test_prompt_injection.py` (controlled injection scenarios)

- Indirect Prompt Injection (RAG)
  - Attack: malicious content in retrieved documents instructs the model to misbehave.
  - Controls (implemented): RAG provenance metadata, label retrieved content as untrusted, prioritize trusted sources.
  - Test: `tests/test_rag_poisoning.py`

- Tool Abuse / Excessive Agency
  - Attack: model attempts to invoke a powerful or unauthorized tool.
  - Controls (implemented): tool allowlists, `Authorizer` permission checks, audit logging, application-level tool execution gate.
  - Test: `tests/test_tool_authorization.py`

- Malicious Tool Arguments
  - Attack: model supplies harmful or invalid arguments to tools.
  - Controls (implemented): argument validators, schema & type checks in `app/tools/validators.py`, executor-level validation.
  - Test: `tests/test_tool_argument_validation.py`

- RAG Poisoning
  - Attack: attacker inserts poisoned documents into vector store.
  - Controls (implemented): provenance metadata on ingestion (owner, hash, source_type, ingested_at), integrity checks, prioritization of trusted docs.
  - Test: `tests/test_rag_poisoning.py`

- Sensitive Data Leakage
  - Attack: unauthorized user attempts to retrieve confidential information through RAG, tools, MCP, or LLM interaction.
  - Controls (implemented): authentication and resource-level authorization (`Authorizer`), redaction in audit logs, least-privilege tool exposure.
  - Test: cross-user and unauthorized-resource tests in `tests/` (authorization suite)

- MCP Security
  - Attack: malicious/compromised MCP server, malicious tool metadata, unauthorized tool discovery, or malicious tool results.
  - Controls (implemented): MCP allowlist, client-side enforcement, annotated `_mcp_server` metadata, server-side authorization checks exercised in fake MCP tests, label MCP results as untrusted.
  - Test: `tests/test_mcp_security.py`

## 3. Security Control Matrix

The table below maps threats to implemented controls and automated tests. Controls are explicitly marked `Implemented` if present in the codebase, otherwise `Recommended`.

| Threat | Example Attack | Security Control | Implemented / Recommended | Automated Test |
|---|---|---:|:---:|---|
| Prompt injection | User prompt overrides system rules | Prompt-injection guard; disallow echoing system/tool defs | Implemented | `tests/test_prompt_injection.py` |
| Indirect prompt injection (RAG) | Malicious docs instruct agent | Label RAG results untrusted; provenance metadata | Implemented | `tests/test_rag_poisoning.py` |
| Tool abuse / excessive agency | Model calls `delete_document` | Tool allowlist; `Authorizer` permission checks; audit logging | Implemented | `tests/test_tool_authorization.py` |
| Malicious tool arguments | Invalid/overlarge args to tools | Validators (schema/type/range); executor-level validation | Implemented | `tests/test_tool_argument_validation.py` |
| RAG poisoning | Poisoned docs inserted into vector store | Provenance (owner/hash/ingested_at); prioritize trusted sources | Implemented | `tests/test_rag_poisoning.py` |
| Sensitive data leakage | Cross-user data exfiltration | Authentication; resource-level authorization; redaction in audit logs | Implemented | Authorization tests suite |
| MCP compromise | Rogue MCP server offers dangerous tools | MCP server allowlist; client-side allowlist enforcement; mark MCP results untrusted | Implemented | `tests/test_mcp_security.py` |
| Supply-chain / model compromise | Model returns incorrect facts | Output security checks; verification outside LLM | Recommended | Add integration tests with external model failures |

Notes:
- The matrix lists only controls that exist in this repository as `Implemented` (per your instruction). Some production hardening controls (HSM, secrets management, hardened PKI, runtime sandboxes) are recommended but not implemented here.

## 4. Responsibilities

Component responsibilities (who enforces what):

- LLM:
  - Reasoning and generating candidate responses
  - Selecting which tools to call (based on prompts)
  - NOT a security boundary — do not treat LLM outputs as authoritative for security decisions

- Agent (`AgentService`):
  - Orchestration and iteration control
  - Enforce prompt-injection guards and tool-selection constraints
  - Attach user context and provenance to tool calls

- Application (FastAPI, Authorizer, Executor):
  - Authentication (user identity)
  - Authorization (tool-level and resource-level permission checks)
  - Policy enforcement, auditing, and deterministic checks
  - Final output validation and sanitization before returning to user

- Tool (tool implementation):
  - Validate input arguments strictly
  - Enforce resource-scoped authorization for sensitive operations
  - Limit side effects and return structured, safe results

- MCP Server (remote):
  - Expose capabilities and enforce server-side authorization
  - Treat client-provided context carefully; the client must not automatically trust server tools

- RAG / VectorStore:
  - Store provenance and owner metadata on ingestion
  - Return documents with metadata for downstream trust decisions

- Output Security Layer:
  - Apply defense-in-depth checks (sanitization, redaction, sensitive data detection)
  - Ensure logs are redacted and do not contain secrets

Explicit statement: The LLM is not a security boundary. All security decisions (authorization, access control, validation) are performed in application code outside the model.

## 5. Least Privilege

- User permissions: users should only be able to invoke tools and access data they are authorized for. `Authorizer` enforces mapping from tool to permission and resource checks.
- Tool permissions: tools are registered in a registry and gated by allowlists/permissions. Dangerous tools such as `delete_document` are restricted to specific roles/owners.
- MCP permissions: MCP servers and their tools are allowlisted; the client enforces discovery-time allowlist and app-level authorization is still required before execution.
- Data access: data returned from external systems must be filtered and authorized per user; RAG hits include owner/provenance metadata used for authorization.
- RAG access: retrieval returns documents as untrusted; downstream logic must corroborate provenance and integrity before relying on content.
- External system access: external APIs should be accessed through narrow service wrappers with parameter validation and quotas.

Why least privilege for agents: granting an agent more capabilities than necessary increases attack surface and blast radius; keep tool permissions and data access minimal and time-scoped.

## 6. Defense-in-Depth

Security requires multiple independent controls. Key layers in this project:

1. Authentication — verify user identity
2. Authorization — permission checks outside LLM (Authorizer)
3. Input validation — strict schema and validators for tool inputs
4. Tool authorization — application-level checks and allowlists
5. Resource authorization — owner-scoped checks (e.g., `authorize_resource`)
6. RAG provenance — mark and prefer trusted content
7. MCP trust controls — allowlist MCP servers and treat remote results as untrusted
8. Output checks — final sanitization and redaction
9. Audit logging — record security-relevant events with redaction

Deterministic controls (authorization, validation, auditing) remain outside the LLM.

## 7. Attack-path Examples

Indirect attack (RAG poisoning):

1. Attacker uploads a document into vector store claiming to be guidance on account deletion.
2. The document is ingested with metadata; provenance shows unknown owner and lower integrity.
3. Agent issues a retrieval; the document is returned and marked `untrusted`.
4. LLM receives the untrusted content but agent logic does not allow it to override authorization or call privileged tools.
5. Request for `delete_document` is blocked by `Authorizer.authorize_resource` because the user is not owner.
6. Event is logged; no sensitive action taken.

Direct attack (prompt injection):

1. User submits a prompt containing instructions to reveal internal tool usage or secret keys.
2. Agent's prompt-injection guard prevents system/tool definitions from being echoed and rejects policy-violating outputs.
3. Agent enforces authorization for any tool calls; sensitive tools are allowlisted and require explicit permissions.
4. Event is logged and request is rejected.

## 8. Checklist

- Authentication
  - [ ] Users are authenticated
  - [ ] Credentials are protected

- Authorization
  - [ ] Authorization occurs outside the LLM
  - [ ] Resource-level authorization exists
  - [ ] Tools require appropriate permissions

- LLM Security
  - [x] Direct prompt injection tested
  - [x] Indirect prompt injection tested
  - [x] LLM output is not treated as trusted policy

- Agent Security
  - [x] Agent has iteration limits (configurable)
  - [x] Tool access is restricted via allowlist
  - [x] Excessive agency is controlled (Authorizer + audit)

- RAG Security
  - [x] Retrieved content is treated as untrusted
  - [x] Document access is authorized
  - [x] Provenance is tracked on ingest
  - [x] RAG poisoning is tested

- Tool Security
  - [x] Arguments are validated
  - [x] Resources are authorized
  - [x] Dangerous capabilities are restricted

- MCP Security
  - [x] MCP servers are allowlisted at discovery
  - [x] MCP tools are allowlisted on client
  - [x] Server-side authorization is exercised in tests
  - [x] Tool results are treated as untrusted

- Data Security
  - [x] Sensitive data access is controlled by resource checks
  - [ ] Secrets are managed via a secrets provider (recommended)
  - [x] Errors do not expose internal information (best-effort)

- Auditability
  - [x] Security-relevant actions are logged
  - [x] Logs redact sensitive information

## 9. Production Considerations (Not implemented here)

- Hardened secrets management (e.g., Vault, cloud KMS) for API keys and credentials
- Network-level isolation and service mesh for MCP and external APIs
- Runtime sandboxing or process isolation for untrusted tool execution
- Strong PKI for MCP server authentication and mutual TLS
- Continuous monitoring, alerting, and SOC integration

## 10. Tests and Coverage

Security-relevant automated tests in this repository include (non-exhaustive):

- `tests/test_prompt_injection.py`
- `tests/test_rag_poisoning.py`
- `tests/test_tool_authorization.py`
- `tests/test_tool_argument_validation.py`
- `tests/test_mcp_security.py`

Run tests with:

```bash
python3 -m pytest -q
```

---

End of consolidated security reference.
