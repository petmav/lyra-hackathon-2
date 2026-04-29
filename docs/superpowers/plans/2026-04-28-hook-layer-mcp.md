# Hook Layer (MCP-native) — Sub-Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Parent plan:** `2026-04-28-praetor-hackathon-build.md` — primarily Phase 2 Task 2.6 (stub GitHub MCP) and Phase 3 Task 3.3.

**Goal:** Provide the unified abstraction for everything that crosses the platform boundary — pulling data into corpora and workflow steps, pushing data out (PRs, Slack messages, Jira tickets, ServiceNow), and supervising long-lived integrations. Every hook crossing is a hash-chained event. MCP is the primary path; native and HTTP fallbacks exist.

**Architecture:** A `Hook` row registers an external integration (MCP server endpoint, native adapter, or HTTP proxy). The Hook Layer is a service exposing `call_in` and `call_out`. Calls are policy-checked: outbound calls with `effect_radius` other than `internal` require an upstream `gate.human` approval in the workflow. The platform also exposes itself as an MCP server for downstream consumers.

**Tech Stack:** Python 3.12, MCP SDK (Anthropic, SSE transport), httpx (HTTP fallback), Pydantic v2, FastAPI (for stub MCP servers + platform-as-MCP-server), aiosqlite (for the GitHub stub's canned-files store).

**Interface this sub-plan exposes:**

```python
class HookLayer:
    async def call_in(self, hook_id: str, scope: str, args: dict,
                      workflow_run_id: str | None = None,
                      step_run_id: str | None = None) -> dict: ...
    async def call_out(self, hook_id: str, tool: str, args: dict,
                       workflow_run_id: str | None = None,
                       step_run_id: str | None = None) -> dict: ...
    async def health(self, hook_id: str) -> dict: ...
```

HTTP: `GET/POST /hooks`, `POST /hooks/{id}:test`, `GET /hook-calls?workflow_run_id=...`.

---

## File map

```
packages/hooks/
├── mcp_client/
│   ├── __init__.py
│   ├── client.py              # async MCP SSE client wrapper
│   ├── session.py             # connection pool / auth resolver
│   └── stubs/
│       ├── github_mcp_stub/
│       │   ├── server.py       # FastAPI + MCP SSE
│       │   ├── canned_files.py # the support-bot fixture
│       │   └── Dockerfile
│       ├── slack_mcp_stub/
│       │   ├── server.py
│       │   └── Dockerfile
│       └── localfiles_mcp_stub/
│           ├── server.py
│           └── Dockerfile
├── connectors/                 # native adapters; empty at hackathon scope
└── http_proxy/
    ├── __init__.py
    └── proxy.py                # generic HTTP-as-hook fallback

apps/api/praetor_api/
├── routers/hooks.py
├── services/hook_registry.py    # Hook CRUD + auth_ref resolution
├── services/hook_layer.py       # call_in / call_out implementation
└── services/platform_mcp.py     # Praetor-as-MCP-server export

tests/hooks/
├── test_mcp_client.py
├── test_hook_layer.py
├── test_github_stub.py
├── test_slack_stub.py
└── test_platform_mcp.py
```

---

## Task 1: MCP client wrapper

**Files:** `packages/hooks/mcp_client/{client.py, session.py}`.

- [ ] **Step 1: failing test** spins a tiny in-process MCP server exposing one resource and one tool; asserts client `list_resources` returns it, `call_tool` returns the canned output.

- [ ] **Step 2: implement**

```python
# packages/hooks/mcp_client/client.py
from mcp.client.sse import sse_client
from mcp import ClientSession

class MCPClient:
    def __init__(self, endpoint: str, auth: dict | None):
        self.endpoint = endpoint; self.auth = auth or {}
    async def __aenter__(self):
        self._cm = sse_client(self.endpoint, headers=self.auth)
        self._read, self._write = await self._cm.__aenter__()
        self.session = ClientSession(self._read, self._write)
        await self.session.initialize()
        return self
    async def __aexit__(self, *a):
        await self._cm.__aexit__(*a)
    async def list_resources(self, filter=None):
        return await self.session.list_resources()
    async def call_tool(self, name: str, args: dict):
        return await self.session.call_tool(name, args)
```

`session.py` resolves `auth_ref` (e.g. `secret:github_pat`) from a small in-process secrets stub backed by env vars (no real Vault at hackathon scope). Caches sessions per hook for the lifetime of a process.

- [ ] **Step 3: tests pass.** Commit.

## Task 2: Hook registry + Hook CRUD

**Files:** `apps/api/praetor_api/services/hook_registry.py`, `apps/api/praetor_api/routers/hooks.py`.

- [ ] **Step 1: failing test** posts a Hook (kind=mcp, direction=both, endpoint=`http://localhost:9101/sse`, scopes=["repo:read","repo:pr:write"], effect_radius="external_trusted"); asserts row inserted, GET returns it, `:test` opens an MCP session and pings.

- [ ] **Step 2: implement** the routes per master plan §2.3. `:test` calls `MCPClient.list_resources()` with a 3s timeout and returns `{ok: bool, resources_count: int, latency_ms: int}`.

- [ ] **Step 3: tests pass.** Commit.

## Task 3: HookLayer — `call_in` / `call_out`

**Files:** `apps/api/praetor_api/services/hook_layer.py`.

- [ ] **Step 1: failing tests**
  - `call_in("github_mcp", "repo:read", {"url":"...","paths":["**/*.py"]})` returns canned files, writes a `HookCall` row, emits `hook.in.called`.
  - `call_out("github_mcp", "create_pull_request", {...})` writes a HookCall, emits `hook.out.called`, returns the stub's PR URL.
  - `call_out` to a hook with `effect_radius="external_trusted"` without an upstream approval marker raises `EffectGated`.

- [ ] **Step 2: implement**

```python
async def call_in(self, hook_id, scope, args, workflow_run_id=None, step_run_id=None):
    hook = await self.registry.get(hook_id)
    started = time.perf_counter()
    try:
        async with self._client_for(hook) as cli:
            if scope.endswith(":read"):
                resp = await cli.list_resources(filter=args)
            elif ":" in scope:
                resp = await cli.call_tool(scope.split(":")[0], args)
            else:
                raise UnknownScope(scope)
        await self._record_call(hook, "in", args, resp, workflow_run_id, step_run_id, started)
        return resp
    except Exception as e:
        await self._record_failed(hook, "in", args, e, workflow_run_id, step_run_id, started)
        raise

async def call_out(self, hook_id, tool, args, workflow_run_id=None, step_run_id=None):
    hook = await self.registry.get(hook_id)
    if hook.effect_radius != "internal":
        if not await self._has_upstream_approval(workflow_run_id, hook_id):
            raise EffectGated(hook_id, hook.effect_radius)
    ...
```

- [ ] **Step 3: tests pass.** Commit.

## Task 4: Stub GitHub MCP server

**Files:** `packages/hooks/mcp_client/stubs/github_mcp_stub/{server.py, canned_files.py, Dockerfile}`.

This is what the demo's `code_compliance_scan` will hit. It must serve files where `send_email` lacks domain validation so the scan finds something.

- [ ] **Step 1: canned_files.py** — a Python dict `{path: content}` for a fake `northwind/support-bot` repo. Include `tools/send_email.py` with the deliberately broken validator.

```python
# tools/send_email.py
def send_email(recipient, subject, body):
    smtp.sendmail("noreply@northwind.health", recipient, _format(subject, body))
```

- [ ] **Step 2: server.py** — FastAPI app speaking MCP over SSE. Resources: each canned file as `file://<path>`. Tools: `list_files(url, paths)` returning matching files; `create_pull_request(repo, base, head, title, changes)` returning a fake PR URL `https://github.example.com/northwind/support-bot/pull/<n>`.

- [ ] **Step 3: Dockerfile** + compose entry on port 9101 on `praetor-net`.

- [ ] **Step 4: integration test** — `MCPClient` against this stub returns the expected files. Commit.

## Task 5: Stub Slack MCP server

**Files:** `packages/hooks/mcp_client/stubs/slack_mcp_stub/{server.py, Dockerfile}`.

- [ ] Tools: `post_message(channel, text)` (returns `{ts}`), `await_approval(approval_id, timeout_s)` (long-polls; flips to approved when the platform's UI hits `POST /approvals/{id}:decide`).
- [ ] Used by `gate.human` executor so the demo can show "approval requested" in a fake Slack channel even if no one looks at it.
- [ ] Compose entry on port 9102.
- [ ] Commit.

## Task 6: Stub local-files MCP server

**Files:** `packages/hooks/mcp_client/stubs/localfiles_mcp_stub/{server.py, Dockerfile}`.

- [ ] Mounts `content/corpora_seed/` and a small "process artefacts" folder. Resource per file. Used for `process_compliance_scan` and corpus ingestion via hook reference.
- [ ] Compose entry on port 9103.
- [ ] Commit.

## Task 7: HTTP fallback proxy

**Files:** `packages/hooks/http_proxy/proxy.py`.

- [ ] For `kind=http` hooks, treat the hook config as `{base_url, auth_header, request_template}`. `call_in/out` renders the template with `args`, fires the request via httpx, returns parsed JSON.
- [ ] Test against `httpbin.org/post` (mocked).
- [ ] Commit.

## Task 8: Hook governance — `effect_radius` enforcement

**Files:** `apps/api/praetor_api/services/hook_layer.py` (additions), `content/controls/hook_out_gate.rego`.

- [ ] OPA policy `hook_out_gate.rego`: `external_trusted` requires `input.has_upstream_approval == true` OR workflow has `risk_tier ≤ L2` AND step explicitly declares `low_risk: true`. `external_public` always requires approval.
- [ ] `_has_upstream_approval` queries `step_run` rows in the run for any `gate.human` step whose `outcome=approved` and whose `targets[]` includes the hook id.
- [ ] Tests cover both branches.
- [ ] Commit.

## Task 9: Health checks

**Files:** `apps/api/praetor_api/services/hook_layer.py`.

- [ ] Background task: every 60s, ping each enabled hook, update `last_health_check`. Surface in Hooks UI as a green/red dot.
- [ ] Commit.

## Task 10: Platform-as-MCP-server export

**Files:** `apps/api/praetor_api/services/platform_mcp.py`, route mounted under `/mcp/sse`.

The platform itself is an MCP server so external agents can read Praetor state.

- [ ] **Step 1: implement** an MCP server with:
  - **Resources** (read-only): `praetor://assets`, `praetor://obligations`, `praetor://controls`, `praetor://evidence`, `praetor://findings`.
  - **Tools** (safe): `open_audit_packet(packet_id)` → presigned URL; `list_findings(filter)` → JSON; **no** mutating tools at hackathon scope.
- [ ] **Step 2: smoke test** — connect Claude Desktop or another MCP client and list resources. Document in `docs/MCP_SERVER.md`.
- [ ] Commit.

## Task 11: Hooks UI

**Files:** `apps/web/app/hooks/page.tsx`, `apps/web/components/hook-config/`.

- [ ] List of registered hooks with health dot, kind, direction, scopes, effect_radius.
- [ ] "Add hook" form (kind dropdown, endpoint, auth_ref picker, scopes, effect_radius).
- [ ] "Recent calls" panel filtered by hook → `GET /hook-calls?hook_id=...` showing direction, status, latency, redacted args.
- [ ] "Test" button calls `POST /hooks/{id}:test`.
- [ ] Commit.

---

## Self-review

- All three hook directions covered (`in`, `out`, `supervise` — supervise is just a long-lived `in` for telemetry).
- All three implementations covered (MCP, HTTP, native scaffold present but no native adapters at hackathon scope).
- Effect-radius gating prevents an outbound `hook.out` from firing without upstream approval (Task 8).
- Every call hash-chained via the platform event chain on the relevant `workflow_run` Asset.
- Platform-as-MCP-server export means downstream tools (Claude Desktop, other agents) can read Praetor state without UI scraping.

## Out of scope for this sub-plan

- Native adapters for Vanta/Drata/Linear/Jira/Notion/Confluence/Drive (post-hackathon).
- Token rotation, OAuth flows (auth_ref resolves env vars only at hackathon scope).
- MCP server marketplace / community contributions (post-hackathon).
