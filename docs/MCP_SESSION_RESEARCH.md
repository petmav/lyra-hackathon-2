# MCP Session Research

Checked on 2026-04-29 against the public Model Context Protocol specification.

Relevant standard behavior:

- Streamable HTTP servers may return `MCP-Session-Id` during `initialize`; clients must include that session ID on subsequent requests.
- HTTP clients must include `MCP-Protocol-Version` after initialization.
- Streamable HTTP requests carry mirrored routing headers such as `Mcp-Method` and, for named requests, `Mcp-Name`.
- MCP authorization treats protected MCP servers as OAuth 2.1 resource servers. Clients discover authorization metadata through OAuth Protected Resource Metadata and use access tokens for protected requests.
- MCP clients should discover Protected Resource Metadata, then Authorization Server Metadata or OIDC discovery, and may use OAuth Dynamic Client Registration when `registration_endpoint` is advertised.
- Capability negotiation happens through `initialize`, and richer discovery is exposed through calls such as `tools/list`, `resources/list`, and `prompts/list`.

Praetor implementation:

- `praetor_api.services.mcp_client` now initializes a session, stores the negotiated protocol version and session ID, redacts session IDs in API output, and includes standard MCP request headers.
- Hook `auth_ref` values resolve to bearer tokens when configured.
- Health checks discover tools, resources, and prompts.
- Tool calls include `Mcp-Name` and attach session/protocol headers.
- Bundled stubs optionally enforce bearer auth through `MCP_STUB_TOKEN`, return session IDs during initialize, and support `prompts/list`.

Still open:

- Persisted OAuth client registrations now exist through `mcp_oauth_connection`.
- Authorization-code callback and token refresh endpoints now store token sets with API responses redacted.

Remaining production hardening:

- Move MCP OAuth client secrets and token sets into Vault/secret-manager write APIs instead of Postgres JSONB.
- Add provider-specific consent UX around the returned authorization URL.
- Add refresh-token rotation history and revocation support.
- Long-lived SSE/stream resumption and server-to-client notifications.
- Persisted MCP session cache across API process restarts.

Sources:

- https://modelcontextprotocol.io/specification/draft/basic/transports
- https://modelcontextprotocol.io/specification/draft/basic/authorization
- https://modelcontextprotocol.io/specification/draft/schema
