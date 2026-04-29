# Sandbox Orchestrator — Sub-Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Parent plan:** `2026-04-28-praetor-hackathon-build.md` — primarily Phase 3 Task 3.4, with the in-process Phase 2 fallback noted as throwaway.

**Goal:** Spin up isolated, network-restricted Docker containers on demand to run workflow agent steps and remediation tests. Stream events from inside the sandbox to the platform's event bus tagged with `workflow_run_id`/`step_id`/`asset_urn`. Provide a controlled MCP bridge so agents can talk to registered hooks without touching the public internet.

**Architecture:** A short-lived container per step. Read-only root with a writable overlay at `/sandbox/work`. Custom Docker bridge `praetor-mocks` is the only network reachable. The Praetor SDK is preinstalled and auto-configured via the manifest dropped at `/sandbox/inputs/manifest.json`. A sidecar `mcp-bridge` container mediates outbound MCP calls and applies per-step scope enforcement. Replay mode reads recorded events + result.json from disk instead of launching a container — used for demo resilience.

**Tech Stack:** Python 3.12, `aiodocker` (async Docker SDK), Pydantic v2, Redis Streams, gVisor (`runsc`) when available, `httpx`, `aiofiles`. Sandbox runtime image: Debian slim + Python 3.12 + Node 20 + preinstalled tools.

**Interface this sub-plan exposes:**

```python
class SandboxHandle:
    run_id: str
    async def stream(self) -> AsyncIterator[dict]: ...   # JSON events, line-delimited
    async def wait_for_result(self) -> dict: ...          # /sandbox/work/result.json
    async def kill(self) -> None: ...

class Orchestrator:
    async def launch(self, manifest: dict, tag: dict) -> SandboxHandle: ...
    async def replay(self, recording_path: Path) -> SandboxHandle: ...
```

---

## File map

```
apps/sandbox/
├── praetor_sandbox/
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── docker_runtime.py
│   ├── mcp_bridge.py
│   ├── replay.py
│   ├── manifest_loader.py        # reads /sandbox/inputs/manifest.json (used by harness)
│   └── harness/
│       ├── __init__.py
│       ├── entrypoint.py         # the in-container entrypoint
│       ├── tool_surface.py       # corpus_query / cite_obligation / emit_finding / propose_change
│       └── transport.py          # event stdout writer + result.json writer
├── images/runtime/
│   ├── Dockerfile
│   └── requirements.txt
└── Dockerfile                    # the orchestrator service itself

tests/sandbox/
├── test_orchestrator.py
├── test_docker_runtime.py
├── test_mcp_bridge.py
├── test_replay.py
└── fixtures/
    ├── recording_succeeded.json
    └── recording_failed.json
```

---

## Task 1: Sandbox runtime image

**Files:** `apps/sandbox/images/runtime/{Dockerfile, requirements.txt}`.

- [ ] **Step 1: write Dockerfile**

```dockerfile
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3-pip python3-venv nodejs npm git ripgrep ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1500 sandbox
USER sandbox
WORKDIR /sandbox
COPY --chown=sandbox requirements.txt /sandbox/requirements.txt
RUN pip install --user --break-system-packages -r /sandbox/requirements.txt
COPY --chown=sandbox harness/ /sandbox/harness/
ENV PYTHONPATH=/sandbox/harness
ENTRYPOINT ["python3", "-m", "harness.entrypoint"]
```

- [ ] **Step 2: requirements.txt** — anthropic, mcp, pydantic, httpx, tantivy, ast-grep-py, simpleeval, jinja2.

- [ ] **Step 3: build + smoke**

```bash
docker build -t praetor/sandbox-runtime:latest apps/sandbox/images/runtime/
docker run --rm praetor/sandbox-runtime:latest --help
```

Expected: harness usage banner. Commit.

## Task 2: Harness transport (events out, result out)

**Files:** `apps/sandbox/praetor_sandbox/harness/transport.py`.

- [ ] **Step 1: failing test** writes 3 events, asserts each line is valid JSON with `ts`, `type`, `payload`, `asset_urn` (passed through).

- [ ] **Step 2: implement**

```python
import json, sys, time
def emit(type: str, **payload):
    sys.stdout.write(json.dumps({"ts": time.time(), "type": type, **payload}) + "\n")
    sys.stdout.flush()
def write_result(obj: dict, path="/sandbox/work/result.json"):
    import os, tempfile
    os.makedirs("/sandbox/work", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir="/sandbox/work")
    with os.fdopen(fd, "w") as f: json.dump(obj, f)
    os.replace(tmp, path)
```

- [ ] **Step 3: tests pass.** Commit.

## Task 3: Harness tool surface

**Files:** `apps/sandbox/praetor_sandbox/harness/tool_surface.py`.

The agent inside the sandbox sees these as Anthropic `tools`. Each one emits an event and either calls back to the platform via the MCP bridge (for `corpus_query`, `emit_finding`, `propose_change`) or operates locally (`grep`, `ast_parse`).

- [ ] **Step 1: tests** for each tool mock the MCP bridge, assert (a) input validation, (b) event emitted, (c) for finding/proposed_change, the returned id is a UUID-shaped string.

- [ ] **Step 2: implement** following the snippet in PDF §6.4:

```python
async def emit_finding(*, title, description, severity, obligations_cited,
                       documents_cited, confidence, target_asset_id=None) -> str:
    f = {"title": title, "description": description, "severity": severity,
         "obligations_cited": obligations_cited, "documents_cited": documents_cited,
         "confidence": confidence, "target_asset_id": target_asset_id}
    finding_id = await bridge.call("praetor", "create_finding", f)
    emit("finding.emitted", finding_id=finding_id, severity=severity,
         obligations_cited=obligations_cited)
    return finding_id

async def corpus_query(corpus_urn, query, k=8): ...
async def cite_obligation(obligation_urn): ...
async def propose_change(*, finding_id, kind, diff, diff_format, ...): ...

# Local tools (no bridge):
def grep(pattern, files): ...
def ast_parse(file): ...
def embed_search(corpus_urn, text, k=5): ...   # actually goes through bridge → corpus.query
```

- [ ] **Step 3: tests pass.** Commit.

## Task 4: Harness entrypoint

**Files:** `apps/sandbox/praetor_sandbox/harness/entrypoint.py`.

- [ ] **Step 1: failing test** uses a fixture `manifest.json` and a stubbed Anthropic client; asserts the entrypoint runs the agent loop, writes 1 event per tool call, writes a final `result.json`, exits 0.

- [ ] **Step 2: implement**

```python
import asyncio, json, sys
from .transport import emit, write_result
from . import tool_surface
from anthropic import AsyncAnthropic

async def main():
    manifest = json.load(open("/sandbox/inputs/manifest.json"))
    emit("sandbox.launched", asset_urn=manifest["asset_urn"], step_id=manifest["step_id"])
    client = AsyncAnthropic()
    sys_prompt = open(f"/sandbox/prompts/{manifest['agent']['system_prompt_ref'].split('/')[-1]}").read()
    tools = build_tool_specs(manifest["agent"]["tools"])
    history = [{"role":"user","content":json.dumps(manifest["inputs"])}]
    while True:
        emit("agent.thought.requested", model=manifest["agent"]["model"])
        resp = await client.messages.create(
            model=manifest["agent"]["model"],
            system=sys_prompt, tools=tools, messages=history, max_tokens=4096)
        if resp.stop_reason == "end_turn":
            break
        for block in resp.content:
            if block.type == "tool_use":
                emit("agent.tool.called", name=block.name, args=block.input)
                result = await tool_surface.dispatch(block.name, block.input)
                history.append({"role":"assistant","content":resp.content})
                history.append({"role":"user","content":[{"type":"tool_result",
                    "tool_use_id":block.id, "content":json.dumps(result)}]})
                break
    output = await tool_surface.collect_output(manifest["expected_output_schema"])
    write_result(output)
    emit("sandbox.exited", status="succeeded")

if __name__ == "__main__":
    try: asyncio.run(main())
    except Exception as e:
        emit("sandbox.exited", status="failed", error=str(e))
        sys.exit(1)
```

- [ ] **Step 3: tests pass.** Commit.

## Task 5: Docker runtime wrapper

**Files:** `apps/sandbox/praetor_sandbox/docker_runtime.py`.

- [ ] **Step 1: failing test** (with a real local Docker socket; `pytest.mark.docker`) launches `praetor/sandbox-runtime:latest` with `--help`, asserts output contains usage, container removed.

- [ ] **Step 2: implement**

```python
import aiodocker, json, asyncio, uuid
from pathlib import Path

class DockerRuntime:
    def __init__(self, client: aiodocker.Docker):
        self.client = client
    async def launch(self, *, image, network, mounts, env, manifest, tag, mem_mb, wall_s):
        run_id = str(uuid.uuid4())
        work = Path("/var/praetor/sandbox") / run_id
        work.mkdir(parents=True, exist_ok=True)
        (work / "inputs").mkdir(); (work / "work").mkdir()
        (work / "inputs" / "manifest.json").write_text(json.dumps(manifest))
        cfg = {
            "Image": image,
            "HostConfig": {
                "NetworkMode": network,
                "Memory": mem_mb * 1024 * 1024,
                "NanoCpus": 2 * 1_000_000_000,
                "ReadonlyRootfs": True,
                "Binds": [f"{work}:/sandbox:rw", *mounts],
                "AutoRemove": False,
                "Runtime": "runsc" if env.get("USE_GVISOR") else None,
            },
            "Env": [f"{k}={v}" for k, v in env.items()],
            "Labels": {"praetor.run_id": run_id, **{f"praetor.{k}": v for k,v in tag.items()}},
        }
        container = await self.client.containers.create(config=cfg)
        await container.start()
        return run_id, container, work
```

Plus helpers: `stream_logs(container)` async-iterates JSON-decoded stdout lines; `wait_with_timeout(container, wall_s)` enforces wall clock and kills on timeout.

- [ ] **Step 3: tests pass.** Commit.

## Task 6: MCP bridge sidecar

**Files:** `apps/sandbox/praetor_sandbox/mcp_bridge.py`.

The bridge runs as its own container (or in-process for hackathon scope) on `praetor-mocks` network. The sandbox calls it via `http://praetor-mcp-bridge:8800/call`. The bridge looks up the registered Hook by name, validates the call against the step's declared `scopes`, then invokes the upstream MCP server. Every call writes a HookCall row + emits `hook.in/out.called`.

- [ ] **Step 1: failing test** posts a call to the bridge for a hook the step has scope for → upstream stub returns canned data → response relayed; second test denies a call outside declared scope.

- [ ] **Step 2: implement**

```python
from fastapi import FastAPI, HTTPException
app = FastAPI()
SCOPES_BY_RUN: dict[str, dict[str, set[str]]] = {}    # run_id -> hook -> scopes

@app.post("/call")
async def call(body: dict):
    run_id = body["run_id"]; hook = body["hook"]; tool = body["tool"]
    allowed = SCOPES_BY_RUN.get(run_id, {}).get(hook, set())
    if tool not in allowed:
        raise HTTPException(403, f"scope {tool} not granted")
    return await hook_layer.call_out(hook, tool, body.get("args", {}),
                                     workflow_run_id=run_id, step_run_id=body.get("step_run_id"))
```

The orchestrator populates `SCOPES_BY_RUN` when launching a step, drops the entry when the step ends.

- [ ] **Step 3: tests pass.** Commit.

## Task 7: Orchestrator main loop

**Files:** `apps/sandbox/praetor_sandbox/orchestrator.py`.

- [ ] **Step 1: failing test** mocks `DockerRuntime.launch` to return a fake container that emits 3 events to its log stream then writes `result.json`. Asserts:
  - `SandboxHandle.stream()` yields 3 events with `workflow_run_id`/`step_id` injected.
  - `wait_for_result()` returns the dict.
  - On exit, container removed and `SCOPES_BY_RUN` entry cleared.

- [ ] **Step 2: implement**

```python
class Orchestrator:
    def __init__(self, runtime: DockerRuntime, bridge: MCPBridge, bus: Bus):
        self.runtime, self.bridge, self.bus = runtime, bridge, bus
    async def launch(self, manifest, tag) -> SandboxHandle:
        scopes = derive_scopes(manifest)   # per-tool scope enforcement
        run_id, container, work = await self.runtime.launch(
            image=settings.SANDBOX_IMAGE,
            network="praetor-mocks",
            mounts=[f"{settings.PROMPTS_HOST_DIR}:/sandbox/prompts:ro"],
            env={"PRAETOR_RUN_ID": run_id, "PRAETOR_BRIDGE_URL":"http://praetor-mcp-bridge:8800"},
            manifest=manifest, tag=tag,
            mem_mb=manifest["sandbox"]["mem_mb"], wall_s=manifest["sandbox"]["wall_s"])
        self.bridge.grant(run_id, scopes)
        return DockerSandboxHandle(run_id, container, work, tag, self.bridge)

class DockerSandboxHandle:
    def __init__(self, run_id, container, work, tag, bridge):
        self.run_id, self.container, self.work, self.tag, self.bridge = \
            run_id, container, work, tag, bridge
    async def stream(self):
        async for line in self.container.log(stdout=True, follow=True):
            try: evt = json.loads(line)
            except ValueError: continue
            evt.update(self.tag)
            yield evt
    async def wait_for_result(self):
        await self.container.wait()
        result = json.loads((self.work / "work" / "result.json").read_text())
        await self.container.delete(force=True)
        self.bridge.revoke(self.run_id)
        return result
```

- [ ] **Step 3: tests pass.** Commit.

## Task 8: Pre-warm pool

**Files:** `apps/sandbox/praetor_sandbox/orchestrator.py` (additions).

- [ ] On orchestrator startup, pre-pull `SANDBOX_IMAGE` and create one paused container. On first `launch()`, unpause and feed it the manifest. Cuts cold-start latency for the demo (PDF §7 risk).
- [ ] Test: time-to-first-event < 2s on a warm pool, > 6s on a cold start (skip in CI; manual perf check).
- [ ] Commit.

## Task 9: Replay mode

**Files:** `apps/sandbox/praetor_sandbox/replay.py`.

- [ ] **Step 1: failing test** loads a JSON recording `{events: [...], result: {...}, latency_profile: [...]}`, builds a `ReplaySandboxHandle`, asserts `stream()` yields events with the recorded gaps (compressed by `PRAETOR_REPLAY_SPEED`), `wait_for_result()` returns the recorded result.

- [ ] **Step 2: implement**

```python
class ReplaySandboxHandle:
    def __init__(self, recording, tag, speed=1.0):
        self.recording, self.tag, self.speed = recording, tag, speed
    async def stream(self):
        last = self.recording["events"][0]["ts"]
        for evt in self.recording["events"]:
            await asyncio.sleep((evt["ts"] - last) / self.speed)
            last = evt["ts"]
            evt.update(self.tag)
            yield evt
    async def wait_for_result(self):
        return self.recording["result"]

class Orchestrator:
    async def launch(self, manifest, tag):
        if os.environ.get("PRAETOR_REPLAY"):
            return ReplaySandboxHandle(load_recording_for(manifest), tag,
                                       speed=float(os.environ.get("PRAETOR_REPLAY_SPEED","1.0")))
        ...
```

Recording format produced by a `--record` flag on a real launch: capture all events + result.json + timestamps to MinIO under `recordings/<workflow>/<step_id>.json`.

- [ ] **Step 3: tests pass.** Commit.

## Task 10: Resource caps + wall clock enforcement

**Files:** `apps/sandbox/praetor_sandbox/orchestrator.py`.

- [ ] If `wait_for_result` exceeds `manifest["sandbox"]["wall_s"]`, kill container, emit `sandbox.exited` with `status=timeout`, raise `SandboxTimeout`.
- [ ] Memory caps and cpu caps already on `HostConfig`. Test: a container that allocates >2GB gets OOM-killed, surface as `status=oom`.
- [ ] Commit.

## Task 11: Compose service wiring

**Files:** `infra/compose/docker-compose.yml` (additions).

- [ ] Add `sandbox-orchestrator` service mounting `/var/run/docker.sock` (or DinD if security review demands). Add `praetor-mcp-bridge` service. Add `praetor-mocks` network (separate from `praetor-net`).
- [ ] Test: `docker compose up -d` brings both up healthy.
- [ ] Commit.

## Task 12: Replay recordings for demo

**Files:** `scripts/record_demo_runs.py`, `recordings/code_compliance_scan/{scan,propose}.json`.

- [ ] Run `code_compliance_scan` end-to-end with `--record`. Save the recordings to MinIO.
- [ ] Verify `PRAETOR_REPLAY=1 make demo` reproduces identical UI flow with zero LLM calls.
- [ ] Commit.

---

## Self-review

- All sandbox primitives covered: image, harness, runtime wrapper, MCP bridge, orchestrator, pre-warm, replay, caps.
- The interface declared at top is the only thing the workflow runtime depends on; everything else is internal.
- Replay mode is a hard demo dependency (PDF §7 risk + §6.5 backup story).
- gVisor is opt-in via `USE_GVISOR=1`; default is plain Docker since gVisor on Mac/Win laptops is unreliable.

## Out of scope for this sub-plan

- Firecracker microVM pool (post-hackathon, PDF §6.6).
- Multi-tenant sandbox quotas (post-hackathon).
- Sandbox warm-pool autoscaling beyond the single pre-warmed container.
