# Workflow Runtime — Sub-Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Parent plan:** `2026-04-28-praetor-hackathon-build.md` — primarily Phase 2 Task 2.5 and Phase 3 Tasks 3.1–3.2, 3.6–3.7.

**Goal:** Build the typed-DAG agentic workflow runtime that executes governed compliance workflows. Every agent step runs in a sandbox, is itself an Asset, and is governed by the same control plane that supervises customer production AI.

**Architecture:** A `WorkflowRun` is a state machine over a frozen DAG of typed steps. The runtime advances the frontier, dispatching to per-step-type executors. Every step start/end is hash-chained on the `workflow_run` Asset. Templating between steps uses Jinja-style references over a `world_state()` snapshot.

**Tech Stack:** Python 3.12, async SQLAlchemy, Pydantic v2, PyYAML, Jinja2 (sandboxed), Redis Streams, simpleeval (for `transform`), tenacity (retries), httpx (OPA + Hook Layer calls), Anthropic SDK.

**Interface this sub-plan exposes:**
- HTTP: `POST /workflows/{id}:run` → `{workflow_run_id}`; `POST /workflow-runs/{id}:cancel`; `GET /workflow-runs/{id}` (status + steps + emitted artefacts)
- WS: `/ws/v1/workflow-runs/{id}/stream` — relays `workflow.*` and `agent.*` events for the run
- Python: `Runtime(...).advance(run)` async loop driven by a worker

**Interfaces this sub-plan consumes (must exist as stubs by Phase 2):**
- `sandbox.orchestrator.launch(manifest, tag) -> SandboxHandle` — see sandbox-orchestrator sub-plan
- `hooks.call_in(hook_id, scope, args)` / `hooks.call_out(...)` — see hook-layer-mcp sub-plan
- `corpus_index.hybrid_search(corpus_id, query, filters, k)` — see corpus-management sub-plan
- `policy.evaluate_hot(package, input)` — OPA call

---

## File map

```
apps/workflow/
├── praetor_workflow/
│   ├── __init__.py
│   ├── runtime.py           # advance() loop, dispatch, state machine
│   ├── dag.py               # DAG, Step, frontier, world_state
│   ├── templating.py        # {{ inputs.x }} / {{ steps.y.z }} resolver
│   ├── manifest.py          # build_manifest() for agent steps
│   ├── schemas.py           # Pydantic types: Step, StepResult, WorldState
│   ├── concurrency.py       # frontier dispatcher with semaphore
│   ├── failure.py           # halt|branch|escalate policies
│   └── executors/
│       ├── __init__.py      # EXECUTORS registry
│       ├── agent_step.py
│       ├── corpus_query.py
│       ├── hook_in.py
│       ├── hook_out.py
│       ├── transform.py
│       ├── gate_policy.py
│       ├── gate_human.py
│       ├── finding_emit.py
│       └── change_propose.py
└── templates/               # YAML workflow definitions (5)
    ├── code_compliance_scan.yaml
    ├── process_compliance_scan.yaml
    ├── vendor_risk_assessment.yaml
    ├── policy_gap_analysis.yaml
    └── continuous_control_monitoring.yaml

apps/api/praetor_api/routers/workflows.py        # CRUD + :run
apps/api/praetor_api/routers/workflow_runs.py    # status + cancel
apps/api/praetor_api/ws/workflow_run_stream.py   # WS

tests/workflow/
├── test_dag.py
├── test_templating.py
├── test_runtime.py
├── test_executors_*.py
└── fixtures/
    ├── two_step.yaml
    └── parallel_branches.yaml
```

---

## Task 1: DAG model

**Files:** `apps/workflow/praetor_workflow/dag.py`, `tests/workflow/test_dag.py`, fixtures.

- [ ] **Step 1: failing test — parse + topo**

```python
# tests/workflow/test_dag.py
import yaml
from praetor_workflow.dag import DAG

def test_topo_order_simple():
    spec = yaml.safe_load(open("tests/workflow/fixtures/two_step.yaml"))
    dag = DAG.from_spec(spec)
    assert dag.topo_order() == ["pull", "scan"]

def test_frontier_advances():
    dag = DAG.from_spec(yaml.safe_load(open("tests/workflow/fixtures/parallel_branches.yaml")))
    assert {s.id for s in dag.ready_steps(completed=set())} == {"a"}
    assert {s.id for s in dag.ready_steps(completed={"a"})} == {"b1", "b2"}
    assert {s.id for s in dag.ready_steps(completed={"a","b1","b2"})} == {"c"}

def test_cycle_rejected():
    spec = {"steps":[{"id":"a","type":"transform","inputs":{"x":"{{ steps.b.x }}"}},
                     {"id":"b","type":"transform","inputs":{"x":"{{ steps.a.x }}"}}]}
    import pytest
    with pytest.raises(ValueError):
        DAG.from_spec(spec)
```

- [ ] **Step 2: write fixtures** (`two_step.yaml`, `parallel_branches.yaml`).

- [ ] **Step 3: minimal `dag.py`**

```python
from dataclasses import dataclass, field
from typing import Any
import re
TEMPLATE_RE = re.compile(r"{{\s*steps\.([a-zA-Z0-9_]+)")

@dataclass(frozen=True)
class Step:
    id: str
    type: str
    spec: dict[str, Any]
    deps: frozenset[str]

@dataclass
class DAG:
    steps: dict[str, Step]
    @classmethod
    def from_spec(cls, spec: dict) -> "DAG":
        steps = {}
        for s in spec["steps"]:
            deps = set(TEMPLATE_RE.findall(_dump(s)))
            deps.discard(s["id"])
            steps[s["id"]] = Step(s["id"], s["type"], s, frozenset(deps))
        cls._validate_acyclic(steps)
        return cls(steps)
    def topo_order(self) -> list[str]:
        order, seen = [], set()
        def visit(n):
            if n in seen: return
            for d in self.steps[n].deps: visit(d)
            seen.add(n); order.append(n)
        for n in self.steps: visit(n)
        return order
    def ready_steps(self, completed: set[str]) -> list[Step]:
        return [s for s in self.steps.values()
                if s.id not in completed and s.deps <= completed]
    @staticmethod
    def _validate_acyclic(steps):
        WHITE, GREY, BLACK = 0, 1, 2
        color = {k: WHITE for k in steps}
        def dfs(n):
            if color[n] == GREY: raise ValueError(f"cycle through {n}")
            if color[n] == BLACK: return
            color[n] = GREY
            for d in steps[n].deps: dfs(d)
            color[n] = BLACK
        for n in steps: dfs(n)

def _dump(obj) -> str:
    import json; return json.dumps(obj, sort_keys=True)
```

- [ ] **Step 4: tests pass.** Commit.

## Task 2: Templating

**Files:** `apps/workflow/praetor_workflow/templating.py`, `tests/workflow/test_templating.py`.

- [ ] **Step 1: failing tests** for `render(value, world)` resolving `{{ inputs.x }}`, `{{ steps.scan.findings }}`, `{{ run.id }}`. Reject any expression containing `__`, attribute access on dunder names, or function calls.

- [ ] **Step 2: implement** with `jinja2.sandbox.SandboxedEnvironment`, deny operators, register only `len`, `lower`, `upper` filters. Recursive descent over dicts/lists.

- [ ] **Step 3: tests pass.** Commit.

## Task 3: Pydantic schemas

**Files:** `apps/workflow/praetor_workflow/schemas.py`.

- [ ] `Step`, `StepResult` (`status: Literal["succeeded","failed","awaiting_approval","skipped"]`, `outputs: dict`, `errors: list[str]`, optional `sandbox_run_id`, `hook_call_id`, `policy_decision_id`, `approval_id`, `emitted_finding_ids`, `emitted_proposal_ids`).
- [ ] `WorldState` (`run_id`, `inputs`, `steps: dict[str, dict]`).
- [ ] Commit.

## Task 4: Runtime advance loop

**Files:** `apps/workflow/praetor_workflow/runtime.py`, `tests/workflow/test_runtime.py`.

- [ ] **Step 1: failing test** — fake executors registered for `transform`; run a 3-step DAG; assert events emitted in order, run.status ends `succeeded`, `world_state.steps["c"]` populated.

- [ ] **Step 2: implement** matching the snippet in PDF §6.4:

```python
async def advance(run: WorkflowRun) -> WorkflowRun:
    while not run.is_complete():
        frontier = run.dag.ready_steps(run.completed_step_ids)
        if not frontier:
            break
        results = await dispatcher.run_concurrent(frontier, run, cap=run.concurrency_cap)
        for step, result in zip(frontier, results):
            await emit("workflow.step.finished",
                       workflow_run_id=run.id, step_id=step.id,
                       status=result.status, outputs_redacted=redact(result.outputs))
            if result.status == "failed":
                policy = run.failure_policy_for(step.id)
                if policy.kind == "halt":
                    run.fail(); return run
                if policy.kind == "branch":
                    run.skip_to(policy.target)
                if policy.kind == "escalate":
                    run.await_approval(); return run
            run.record(step.id, result)
    if run.is_complete(): run.finish()
    return run
```

- [ ] **Step 3: tests pass.** Commit.

## Task 5: Concurrency dispatcher

**Files:** `apps/workflow/praetor_workflow/concurrency.py`.

- [ ] `asyncio.Semaphore(cap)`-bounded `run_concurrent(steps, run, cap)` that emits `workflow.step.started` before each executor and catches `StepFailed` as `StepResult(status="failed", errors=[...])`. Cap default 3 for agent steps; non-agent steps unlimited.
- [ ] Test: 5 sleeping `transform` steps with cap=2 finish in ~3 batches' time, not 5×.
- [ ] Commit.

## Task 6: Failure policies

**Files:** `apps/workflow/praetor_workflow/failure.py`.

- [ ] `FailurePolicy` union: `Halt`, `Branch(target_step_id)`, `Escalate(role)`. Parsed from each step's `on_failure` field.
- [ ] Tests for each branch.
- [ ] Commit.

## Task 7: Executors — one task per file

For each executor below: write a focused test in `tests/workflow/test_executors_<name>.py` that mocks the upstream dependency, then implement.

### 7.1 `transform`

- [ ] `simpleeval.SimpleEval(names=world)` with operators restricted to filtering/projection/merging. No imports, no attribute access on builtins. Tests cover filter, project, merge dicts. Commit.

### 7.2 `corpus.query`

- [ ] Calls `corpus_index.hybrid_search(corpus_id, query, filters, k)`; emits `corpus.query` event with `query`, `chunks_returned[].summary`, `top_score`. Output: `{chunks: list, top_score: float}`. Test mocks the index. Commit.

### 7.3 `hook.in`

- [ ] Calls `hooks.call_in(hook_id, scope, args)`. Renders `args` against world. Writes `step_run.hook_call_id`. Output: whatever the hook returns. Test mocks `hooks.call_in`. Commit.

### 7.4 `hook.out`

- [ ] Pre-flight: read `hook.effect_radius`. If `external_*`, require an upstream `gate.human` of `outcome=approved` (look back through `world.steps`). Otherwise call `hooks.call_out(hook_id, tool, args)`. Test covers both branches. Commit.

### 7.5 `gate.policy`

- [ ] Calls OPA `POST /v1/data/{policy_package}/decision`. Persists `policy_decision`. If outcome `block`, raises `StepBlocked` (which `runtime.advance` treats as `failed` unless step has `on_block: branch`). Test mocks OPA. Commit.

### 7.6 `gate.human`

- [ ] Writes `Approval` row with `subject_kind="workflow_step"`, `subject_id=step_run.id`, `role_required` from spec. Notifies via Slack stub MCP (`hooks.call_out(slack_mcp, "post_message", ...)`). Returns `StepResult(status="awaiting_approval")` so runtime parks the run; resumed by `POST /approvals/{id}:decide`. Test asserts run state transitions. Commit.

### 7.7 `finding.emit`

- [ ] Validates each `Finding` against schema (urn, severity, obligations_cited, documents_cited with citation_path, confidence ∈ [0,1]). Inserts rows; emits `finding.emitted` per finding. Returns `{finding_ids}`. Commit.

### 7.8 `change.propose`

- [ ] Validates `ProposedChange`: kind, diff, diff_format, target_asset_id|target_hook_id, residual_risk_estimate. Inserts; emits `change.proposed`. Returns `{proposed_change_ids}`. Commit.

### 7.9 `agent` step (the centerpiece)

**Files:** `apps/workflow/praetor_workflow/executors/agent_step.py`, `apps/workflow/praetor_workflow/manifest.py`.

- [ ] **Step 1: `manifest.py`** — `build_manifest(step, world)` produces the JSON payload from §2.4 of master plan. Resolves `system_prompt_ref` against `content/prompts/`, expands `corpora` URN list, captures `tools` list.

- [ ] **Step 2: failing test** mocks `orchestrator.launch` to return a fake handle that emits 3 events then resolves `wait_for_result()` with `{findings: [...]}`. Asserts events relayed, schema validated, `workflow_agent` Asset row created.

- [ ] **Step 3: implement**

```python
async def run(step, world) -> StepResult:
    asset_urn = f"urn:praetor:asset:workflow_agent:{world.run_id}:{step.id}"
    await inventory.upsert_asset(asset_urn, type="workflow_agent",
                                 owner_id="praetor:platform",
                                 parent_asset_id=world.run_asset_id)
    manifest = build_manifest(step, world)
    handle = await orchestrator.launch(manifest, tag={
        "workflow_run_id": world.run_id,
        "step_id": step.id,
        "asset_urn": asset_urn,
    })
    async for evt in handle.stream():
        evt["asset_urn"] = asset_urn
        evt["workflow_run_id"] = world.run_id
        evt["workflow_step_id"] = step.id
        await bus.publish("events", evt)
    raw = await handle.wait_for_result()
    validated = validate_against_schema(raw, step.spec["expected_output_schema"])
    return StepResult(status="succeeded", outputs=validated, sandbox_run_id=handle.run_id)
```

- [ ] **Step 4: tests pass.** Commit.

## Task 8: Run state machine + persistence

**Files:** `apps/api/praetor_api/services/workflow_run_service.py`, additions in models.

- [ ] `start(workflow_id, inputs, triggered_by) -> workflow_run_id`: insert WorkflowRun row, insert paired `workflow_run` Asset, hash-chain initial event, push to `workflow.runs` Redis stream.
- [ ] `cancel(run_id)`: set status, emit `workflow.run.finished` with `status=cancelled`.
- [ ] `resume_after_approval(approval_id, outcome)`: looks up parked StepRun, records approval outcome on world_state, re-enqueues run for advance.
- [ ] Commit.

## Task 9: Workflow worker process

**Files:** `apps/workflow/praetor_workflow/worker.py`, Dockerfile in `apps/workflow/`.

- [ ] Consumes `workflow.runs` stream with consumer group `workflow-runners`. For each run id, loads run + DAG, calls `runtime.advance`, persists progress, ACKs.
- [ ] Idempotent: if run is already in `awaiting_approval` or terminal, skip.
- [ ] Commit.

## Task 10: HTTP routers

**Files:** `apps/api/praetor_api/routers/{workflows.py, workflow_runs.py}`, `apps/api/praetor_api/ws/workflow_run_stream.py`.

- [ ] `POST /workflows` (upsert, body = YAML); `GET /workflows`; `POST /workflows/{id}:run` (calls `start`); `GET /workflow-runs/{id}`; `POST /workflow-runs/{id}:cancel`.
- [ ] `WS /ws/v1/workflow-runs/{id}/stream` reads from `events` Redis Stream filtered by `workflow_run_id`, fans out to clients.
- [ ] Commit.

## Task 11: Five workflow templates

**Files:** `apps/workflow/templates/*.yaml`.

- [ ] `code_compliance_scan.yaml` — full version per PDF §8.1 (pull → scan → gate → emit → propose → approve → open_pr).
- [ ] `process_compliance_scan.yaml` — `hook.in: localfiles_mcp` (BPM doc) → `agent` (process scanner with GDPR/sector corpora) → `gate.policy` → `finding.emit`.
- [ ] `vendor_risk_assessment.yaml` — ingest a vendor SOC 2 PDF → agent maps gaps against customer obligation set → emits findings.
- [ ] `policy_gap_analysis.yaml` — ingest new regulation → diff against existing controls → propose new controls.
- [ ] `continuous_control_monitoring.yaml` — `trigger: schedule (cron daily)` → loops controls → produces evidence batch.
- [ ] Each template must instantiate cleanly via `POST /workflows/{id}:run` even if the demo only fires `code_compliance_scan`.
- [ ] Commit.

---

## Self-review

- All 9 step types implemented and tested.
- Hash chain per `workflow_run` Asset: every `workflow.*` event chains. Verified by Task 8 test.
- Self-governance literal: agent step Task 7.9 creates `workflow_agent` Asset before launching sandbox. Asset Detail UI works on it unchanged (no extra wiring needed in frontend).
- Failure modes: halt / branch / escalate covered (Task 6).
- Parallelism + cap covered (Task 5).
- Approvals park-and-resume covered (Task 7.6 + Task 8).

## Open dependencies blocking this sub-plan

- Sandbox `orchestrator.launch` interface stable by Phase 2 → see `2026-04-28-sandbox-orchestrator.md`.
- Hook Layer `call_in/call_out` stable by Phase 2 → see `2026-04-28-hook-layer-mcp.md`.
- Corpus `hybrid_search` stable by Phase 2 → see `2026-04-28-corpus-management.md`.
