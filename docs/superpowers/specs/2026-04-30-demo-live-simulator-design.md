# `npm run demo` — Live Simulated E2E Flow

**Date:** 2026-04-30
**Status:** Approved (design)

## 1. Goal

`npm run demo` boots a Praetor stack that feels alive out of the box and lets a
viewer watch agentic workflow data tick through the UI in real time.

Three concrete deliverables:

1. **Populated dashboard on boot.** The Next.js app shows a non-empty state
   immediately — recent runs, open findings, proposed changes, evidence —
   sourced from the API's in-memory store, not from frontend fixtures alone.
2. **Live ticking on instantiate.** Clicking *instantiate run* on any workflow
   creates a run that progresses `pending → running → succeeded` over
   ~15–25 seconds, with per-step thoughts, tool calls, and findings appearing
   as the run unfolds.
3. **Live OpenAI call for one workflow.** When the user instantiates
   `code_compliance_scan_full` and `OPENAI_API_KEY` is set in the API
   process, that run's `scan` (agent) step makes a real OpenAI Responses API
   call, streams the model's thinking text into the activity feed, and uses
   the parsed findings as the run's findings. Without a key, it falls back to
   scripted output — still ticks live. **No other workflow ever calls
   OpenAI**, even with a key present.

## 2. Non-goals

- No changes to production-mode behavior.
- No sandbox-container involvement in demo mode (the live OpenAI call is made
  in-process from the API).
- No auto-relaunching demo loops or generated background traffic. Demo runs
  only when seeded at boot or instantiated by the user.
- No new visual design surface beyond a small "Activity" panel on the run
  page; existing pages and components stay as-is.

## 3. Architecture

```
                           npm run demo
                                 │
              ┌──────────────────┴──────────────────┐
              ▼                                     ▼
        Web (Next.js dev)                    API (FastAPI, in-memory)
        NEXT_PUBLIC_DATA_SOURCE=hybrid              │
                                                    ├─ on startup:
                                                    │     demo_seed.seed_all()
                                                    │       writes 4–6 historical
                                                    │       runs + findings + proposals
                                                    │       + sandbox runs + evidence
                                                    │       into in-memory state
                                                    │
                                                    ├─ POST /workflows/{id}:run
                                                    │     creates run (status=running)
                                                    │     asyncio.create_task(
                                                    │       demo_simulator.tick_run(...)
                                                    │     )
                                                    │     returns initial run immediately
                                                    │
                                                    └─ tick_run loop, per step:
                                                          mutate RUNS[run_id].step_runs[i]
                                                            pending → running
                                                          emit workflow.step.started
                                                          sleep 0.5–2s, emit
                                                            agent.thought / tool / corpus
                                                            / hook / finding.emitted
                                                          (agent step + full + key set →
                                                            real OpenAI Responses call,
                                                            stream rationale, parse findings)
                                                          mutate outputs_redacted
                                                          status running → succeeded
                                                          emit workflow.step.finished
                                                       end: status running → succeeded
                                                       emit workflow.run.finished
```

The frontend's existing 2.5-second polling on `/workflow-runs/[id]` picks up
status transitions; the existing WebSocket stream
(`/ws/v1/workflow-runs/{id}/stream`) carries every per-event detail.

## 4. Components

### 4.1 `apps/api/praetor_api/services/demo_simulator.py` (new)

A unified async tick engine. Public surface:

- `async def tick_run(run_id: str, *, asset_id: str, script: RunScript) -> None`
  — drives one run from creation to terminal state. Mutates the `RUNS` dict
  in `demo_workflows`, appends events through `event_stream.append_event`.
- `RunScript` — a frozen dataclass with: ordered list of `StepScript`
  entries (id, type, base duration, scripted thoughts, scripted tool calls,
  scripted outputs / findings / proposals), a flag `live_openai_step_id`
  pointing to the agent step that should attempt a live call.
- `async def maybe_call_openai(prompt_payload, model) -> LiveResult | None` —
  thin urllib-based caller. Returns `None` if no key / network failure /
  malformed response, in which case the simulator uses scripted findings.

Per-step-type default base durations (jittered ±25%):

| step_type        | base duration |
|------------------|---------------|
| `hook.in`        | 1.5s          |
| `corpus.query`   | 2.0s          |
| `transform`      | 0.6s          |
| `agent` (scripted)| 5.0s         |
| `agent` (live)   | however long the model takes |
| `gate.policy`    | 0.6s          |
| `gate.human`     | 6.0s (auto-resumes) |
| `finding.emit`   | 0.6s          |
| `change.propose` | 1.2s          |
| `hook.out`       | 1.5s          |

The simulator emits a sequence of events per step that mirrors what a real
agent run would produce, so existing UI components (StepDrawer, agent panes,
WS event consumers) render naturally:

- `workflow.step.started` (always)
- `corpus.query.called` (for `corpus.query` steps)
- `hook.in.called` / `hook.out.called` (for hook steps)
- `agent.thought` (for `agent` steps — one per "phase" of the scripted
  rationale, or chunked from the live OpenAI response)
- `agent.tool.called` (for `agent` steps — emit_finding, cite_obligation,
  etc.)
- `policy.decision.hot` (for `gate.policy` steps)
- `human.gate.opened` and `human.gate.resolved` (for `gate.human` steps)
- `finding.emitted` (one per finding)
- `change.proposed` (for `change.propose`)
- `workflow.step.finished` (always)
- `workflow.run.started` and `workflow.run.finished` bracket the whole run.

If a tick task crashes for any reason, the simulator marks the run `failed`
and emits `workflow.run.failed` with the error class + message; the run
becomes terminal so polling stops.

### 4.2 `apps/api/praetor_api/services/demo_seed.py` (new)

Boot-time seeder. Public surface:

- `async def seed_all() -> None` — idempotent. Populates the in-memory state
  with 4–6 historical succeeded runs across the six workflow types, plus
  their attendant findings, proposed changes, sandbox runs, and evidence
  records. Timestamps spread realistically over the past 7 days.

Writes into:
- `demo_workflows.RUNS`
- `demo_state.FINDINGS`, `PROPOSED_CHANGES`, `SANDBOX_RUNS`, `EVIDENCE_RECORDS`
- **`event_stream.EVENTS`** — for every seeded run, the seeder must also emit
  the full per-step event trace (`workflow.run.started`,
  `workflow.step.started`, scripted thoughts/tools/findings,
  `workflow.step.finished`, `workflow.run.finished`) by calling the same
  helpers the simulator uses (`make_event` + `append_event`). Each seeded
  event carries the run's `workflow_run_id`, the step's `workflow_step_id`,
  and a backdated `ts` matching the run's step timeline. The seeder calls
  the helpers serially per asset to keep the hash chain valid. **Without
  this, the activity panel and `StepDrawer` are empty when a user opens any
  seeded run.**

Seed contents (the "few other unique flows already on the site"):

| seed run                          | workflow id                  | findings | proposals | evidence |
|-----------------------------------|------------------------------|----------|-----------|----------|
| Northwind support-bot scan        | `code_compliance_scan`       | 1 high   | 0         | 0        |
| Acme vendor SOC2 review           | `vendor_risk_review`         | 2        | 1         | 0        |
| EU AI Act gap analysis            | `policy_gap_analysis`        | 1        | 1         | 0        |
| Q1 evidence sweep                 | `evidence_collection`        | 0        | 0         | 6        |
| New chat-summary AI intake        | `ai_system_intake`           | 1        | 0         | 0        |
| (optional 6th, polish)            | `code_compliance_scan_full`  | 1 high   | 1         | 0        |

All seeded runs have `status = succeeded`. None call OpenAI. Their
`step_runs` arrays already contain the realistic per-step trace (so the
DAG renders fully when a viewer drills in).

### 4.3 `apps/api/praetor_api/services/demo_workflows.py` (modify)

Currently exposes only `code_compliance_scan` with a synchronous-return run.
Changes:

- Add definitions for the 5 missing prefabs
  (`code_compliance_scan_full`, `vendor_risk_review`, `policy_gap_analysis`,
  `evidence_collection`, `ai_system_intake`). Each has the right
  `required_hooks`, `required_corpora`, `definition` text, and a step graph
  that mirrors the production prefab in `production_workflows.py`.
- `list_workflows()` returns all 6.
- `get_workflow(id_or_urn)` resolves any of them.
- New `async def run_workflow(workflow_id, inputs, *, model_provider, model)`
  — replaces the special-cased `run_code_compliance_scan`. Builds the run
  shell with all step_runs as `pending`, registers it in `RUNS`, schedules
  `demo_simulator.tick_run(run_id, …)` via `asyncio.create_task`, and
  returns the initial run immediately.
- The existing `run_code_compliance_scan` is removed; callers use
  `run_workflow("code_compliance_scan", …)`.

Each workflow gets a static `RunScript` constant assembled from the prefab
graph plus the scripted content from §3 of the brainstorming summary.

### 4.4 `apps/api/praetor_api/routers/workflows.py` (modify)

The demo branch of `POST /workflows/{id}:run` switches from the
single-workflow special case to a generic dispatch that calls
`demo_workflows.run_workflow(id, …)` and returns the initial running run.

`GET /workflows` in demo mode returns the 6 from `list_workflows()`.

### 4.5 `apps/api/praetor_api/main.py` (modify)

Add a startup hook in demo mode that calls `demo_seed.seed_all()`. Idempotent
— safe to call on Uvicorn reload. Skipped entirely in production mode.

### 4.6 `scripts/run-stack.mjs` (modify)

Change the demo-mode default for `NEXT_PUBLIC_DATA_SOURCE` from `fixtures`
to `hybrid` so the web app hits the API but still tolerates a brief API
outage by falling back to fixtures. `production` mode default stays `api`.

### 4.7 `apps/web/app/workflow-runs/[id]/page.tsx` (modify)

Add an Activity panel under the Findings/Proposed-changes column, driven by
the existing `useEventStream` hook against
`/ws/v1/workflow-runs/{run.id}/stream`. Renders the latest ~30 events
chronologically with type badge, actor, and a one-line payload summary.
Auto-scrolls to the bottom when the run is still `running`.

The hook is invoked unconditionally with `live: true` (not gated on a
drawer-open flag like `StepDrawer` does), so the panel ticks for the
entire visit. No filtering by `workflow_step_id` — this panel shows the
whole run's stream. Skipped in pure-fixtures mode (no API base configured)
so there are no console errors.

For event types the panel does not have a dedicated row format for, it
renders a generic line. No design overhaul — purely a small read-only
ticker.

**Activity-log correctness gates** (must hold in both seeded and
instantiated cases):

1. The hook's history fetch (`/events?workflow_run_id=X`) returns
   non-empty for any run that has been seeded or has finished ticking.
2. The WebSocket (`/ws/v1/workflow-runs/{run_id}/stream`) emits new events
   within ~0.25s of `event_stream.append_event` being called by either the
   seeder or the simulator.
3. Every event has `workflow_run_id` set to the externally-visible run id
   (e.g. `wfr_abc123`), and every step-scoped event has `workflow_step_id`
   set, so `StepDrawer`'s `e.workflow_step_id === step.step_id` filter
   yields rows when the user clicks any step on a seeded *or*
   currently-ticking run.

## 5. Live OpenAI path

When `tick_run` reaches the `scan` (agent) step of `code_compliance_scan_full`:

1. Build a prompt similar to the one `apps/sandbox/praetor_sandbox/harness/agent_step.py:_build_prompt`
   constructs — workflow inputs, attached corpus excerpts (sourced from the
   in-memory corpus state), the scripted "expected finding" shape as a
   schema reference.
2. Read `OPENAI_API_KEY` from the API process env. If absent, skip step 3 and
   use the scripted thoughts + findings.
3. Call `https://api.openai.com/v1/responses` via `urllib`. Default model
   `gpt-4o-mini` (overridable via the run's `model` field). 30-second
   timeout. On any failure (HTTP, JSON parse, missing fields), fall back to
   scripted output.
4. Parse `output_text` as a JSON object with `thinking` + `findings` (same
   shape as the existing harness expects). Normalise findings into the
   demo-state shape and use them as the run's `outputs.findings`.
5. Chunk the rationale into 3–5 `agent.thought` events spaced ~0.4s apart
   to give the activity panel a "thinking" cadence; final
   `agent.tool.called` event reports `emit_finding` with the live count.

The simulator does **not** branch on the workflow id for any other step or
any other workflow — every other agent step runs the scripted path
unconditionally.

## 5.1 Why the activity log has been silent until now

Two compounding bugs in the existing setup masked the event stream
entirely:

1. The default demo `NEXT_PUBLIC_DATA_SOURCE=fixtures` causes
   `apps/web/lib/ws/stream.ts` to skip the WebSocket and fall back to a
   hardcoded continuation tape. That tape pins every synthetic event's
   `workflow_step_id` to the literal string `"scan"` and `actor` to
   `"scan-agent"`, so `StepDrawer`'s
   `events.filter(e => e.workflow_step_id === step.step_id)` returned
   nothing for any step *not* called `scan` — i.e. almost every step
   in every workflow.
2. The current synchronous demo `run_code_compliance_scan` does emit
   events into `EVENTS`, but no historical run is seeded into `RUNS` on
   boot, so the only thing the user has to look at is the lone run they
   just kicked themselves — and only for as long as the in-memory state
   survives reload.

The §4.6 switch to `hybrid` and the §4.2 seeded historical event traces
are what unblock both axes. The §4.7 correctness gates exist so we don't
silently regress them again.

## 6. Failure modes

| Cause                                  | Behavior                                                      |
|----------------------------------------|---------------------------------------------------------------|
| `OPENAI_API_KEY` missing               | Live step falls back to scripted findings; run still ticks.   |
| OpenAI HTTP / parse error              | Same as above. Error logged at `info`, not `error`.           |
| Background tick task crashes           | Run marked `failed`; `workflow.run.failed` event emitted.     |
| API restart mid-run                    | In-memory `RUNS` dict resets; the run page polls 404, shows the run as gone. Acceptable in demo. |
| User instantiates 5 runs in 10s        | All five tick concurrently; events interleave. Acceptable.    |

## 7. Testing

**Unit (`apps/api/tests/test_demo_simulator.py`):**

- `tick_run` advances a 4-step scripted run from `pending` to `succeeded` and
  emits at least one event per step type. Assert hash chain remains valid.
- Timing patched to ~zero so the test runs fast.
- Seeded run renders the right number of step_runs and findings.
- OpenAI live path: monkeypatch `urlopen` to return a canned response; assert
  the parsed findings end up on the run. Monkeypatch to raise; assert
  fallback to scripted findings.

**Manual smoke:**

- `npm run demo` → `/` shows ≥4 recent runs, ≥3 open findings, dashboard
  numbers non-zero.
- Click `/workflows` → 6 prefab cards visible. Click `code_compliance_scan_full`
  → instantiate run → land on `/workflow-runs/{id}`. Watch DAG nodes turn
  amber (running) then ink (succeeded) over ~25–35s. Activity panel scrolls
  thoughts and tool calls live.
- With `OPENAI_API_KEY` set: rationale text in the activity panel is
  recognisably model-written, not the scripted lines.
- With key unset: rationale text is the scripted strings; run still finishes.

**Activity-log smoke (both paths must work):**

- Open any **seeded** historical run from the dashboard → the Activity panel
  on `/workflow-runs/{id}` is populated with events on first paint (history
  fetch, no WS streaming required since the run is terminal). Click each
  step → `StepDrawer` shows step-scoped rows for that step.
- **Instantiate** a non-OpenAI workflow (e.g. `vendor_risk_review`) → the
  Activity panel is empty for ~0.3s, then ticks events in real time as the
  simulator advances. Click the running step → `StepDrawer` shows the
  events for that step as they arrive.
- **Instantiate** `code_compliance_scan_full` with `OPENAI_API_KEY` set →
  during the `scan` step, the Activity panel shows `agent.thought` events
  whose text is the live model rationale, in 3–5 chunks.
- Same workflow, key unset → Activity panel shows the scripted thought
  strings during `scan`; everything else identical.

## 8. File-level inventory

**New (3):**
- `apps/api/praetor_api/services/demo_simulator.py`
- `apps/api/praetor_api/services/demo_seed.py`
- `apps/api/tests/test_demo_simulator.py`

**Modified (5):**
- `apps/api/praetor_api/services/demo_workflows.py`
- `apps/api/praetor_api/routers/workflows.py`
- `apps/api/praetor_api/main.py` (startup hook)
- `scripts/run-stack.mjs` (demo `NEXT_PUBLIC_DATA_SOURCE` default)
- `apps/web/app/workflow-runs/[id]/page.tsx` (Activity panel)

**Untouched:** sandbox runtime, workflow worker, production runtime,
existing frontend pages, existing API routes other than the workflow run
dispatch.
