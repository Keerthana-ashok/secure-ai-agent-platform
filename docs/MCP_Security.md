**MCP Security**

- **Trust boundary**: MCP introduces a distinct trust boundary: the MCP server and the tools it exposes are external systems. The agent must treat discovered tools, tool metadata, and tool results as untrusted data.
- **Principle**: "MCP standardizes communication between AI applications and tool/data servers; it does not automatically make an MCP server or its tools trustworthy."

Key controls implemented in this project:

- **Client-side allowlist**: only approved MCP servers/tools are registered into the local tool registry (`app/mcp/allowlist.py`).
- **Server-side authorization**: test MCP servers perform their own authorization checks; the project demonstrates defense-in-depth rather than assuming client trust.
- **Application authorization**: the agent enforces application-level authorization (see `app/auth/authorizer.py`) before invoking MCP tools, including resource-scoped checks.
- **Untrusted results**: MCP-discovered tools are marked as untrusted when their results are appended to the agent conversation, so the LLM cannot treat results as authoritative instructions.
- **Argument validation**: tool arguments are validated at the executor boundary (`app/tools/validators.py`) regardless of their origin.
- **Audit logging**: discovery, skipped tools, and registration actions are logged; authorization decisions are recorded via the authorizer audit logs.

What this project demonstrates (not production guidance):

- How an attacker could poison discovery (expose malicious tools) and why the client should not auto-trust discovered tools.
- How to enforce least privilege by allowlisting servers and specific tools.
- The need for server-side and client-side authorization checks.

Production items omitted (and recommended):

- Secure authenticated transport and server identity verification for MCP (TLS, mutual TLS, signed manifests).
- Persistent, tamper-evident audit store.
- Fine-grained IAM integration for user identity and permissions.
