# Praetor — Platform Walkthrough

This is the operator's guide to Praetor. It documents every user-facing flow on
the site, how to navigate it, and what each page does. The last sections
catalogue the prefab compliance workflows the runtime ships with, plus how to
compose your own from the visual editor.

---

## 1. Site map

The platform is a single Next.js app served at `/`. The sidebar groups every
page into four sections. On desktop the sidebar is a fixed 224px column on the
left; on mobile it collapses to a sticky horizontal nav rail at the top.

| Group | Page | Path |
|---|---|---|
| Overview | Dashboard | `/` |
| Overview | Inventory | `/inventory` |
| Workflows | Workflows | `/workflows` |
| Workflows | Sandbox | `/sandbox` |
| Knowledge | Corpora | `/corpora` |
| Knowledge | Obligations | `/obligations` |
| Knowledge | Hooks | `/hooks` |
| Audit | Evidence | `/evidence` |

Detail pages (not in the sidebar):

- `/workflows/[id]` — view a workflow definition; instantiate a run
- `/workflows/new` — compose a new workflow visually
- `/workflows/[id]/edit` — edit an existing custom workflow
- `/workflow-runs/[id]` — live run detail with step trace
- `/findings/[id]` — finding case file (citations, obligations, confidence)
- `/proposed-changes/[id]` — review a remediation proposal
- `/corpora/[id]` — corpus detail with document list, upload, search
- `/hooks/[id]` — hook detail (config + operations)
- `/hooks/validate` — manifest validator + OpenAPI importer + stream probe

---

## 2. The shell — top bar and alerts tray

The sticky header at the top of every page shows three live readouts on the
left:

- **Clock** — current UTC, ticking every second
- **Governed assets** — total count from `GET /assets`
- **Live workflows** — count of runs whose status is `running` or `awaiting_approval`

All three refresh in the background every 30 seconds; failed fetches render as
em-dashes rather than throwing.

On the right:

- **Search** — keyboard-accessible search button (⌘K), wired into the global search surface
- **Alerts** — the bell icon. A small gold dot appears when there are alerts
  awaiting attention. Click it to open the alerts tray (slides in from the right):
  - Sourced from `GET /alerts`, which the backend derives from open
    high-severity findings + proposed changes awaiting approval
  - Each row links to the relevant finding or proposed change
  - Closes on Escape or backdrop click
- **User chip** — initials + email of the active operator

---

## 3. Page-by-page guide

### 3.1 Dashboard — `/`

Editorial summary of "today's filing":

- Five stats across the top: governed assets, live workflows, open findings,
  pending approvals, audit packets
- **Workflow runs · live** table of the five most recent runs (status, id,
  trigger, when); each row links to the run detail page
- **Open findings** cards (top 4) — severity, URN, title, snippet, confidence;
  each links to `/findings/[id]`
- **Packets in motion** table for audit packets; links to `/evidence?packet=…`
- The hero CTA at the top right resolves to a real run id from the available
  runs (or `/workflow-runs` if none exist), so the "View live run" button never
  hits a stale fixture id

### 3.2 Inventory — `/inventory`

Lists every Asset (workflow_agent, agent, tool, dataset, …) with owner, risk
tier, lifecycle, and parent. Used to navigate to asset-scoped events and runs.

### 3.3 Workflows — `/workflows`

Two sections:

- **Choose a workflow** — grid of the 6 prefab templates plus any custom
  workflows you've authored. Each card shows trigger badge, name, description,
  required hooks, required corpora. Hovering the card reveals an
  "instantiate" button (and an "edit" button on user-defined workflows).
  Clicking the card navigates to the workflow detail page.
- **Recent runs** — DataTable of recent runs across all workflows.

Top-right CTA: **New workflow** → `/workflows/new`.

### 3.4 Workflow detail — `/workflows/[id]`

Shows the workflow's full shape and lets you run it.

- **Header** — kicker (Template / Custom · trigger), title, description, URN,
  and an `instantiate run` button. User-defined workflows also have an
  `edit` link.
- **Graph · Pre · Assess · Post** — visual canvas (read-only) with all nodes
  and bezier edges in the three swimlane columns. Pan with drag, zoom with
  the scroll wheel, "Fit to view" / "+" / "−" controls bottom-right.
  Toggle "Show static swimlane render" for a deterministic SVG layout suitable
  for printing into an audit packet.
- **YAML** — the legacy textual definition with line numbers
- **Inputs · Required** — the inputs schema, required hooks (as badges),
  default policy set
- Clicking **instantiate run** calls `POST /workflows/{id}:run` and
  routes to `/workflow-runs/{run_id}`.

### 3.5 New workflow — `/workflows/new`

The visual graph editor.

- **Top form** — workflow name, description, required corpora (multi-select
  chip picker — only corpora you've created appear), required hooks
  (comma-separated ids).
- **Visual canvas** — pannable, zoomable; nodes are draggable, edges are
  drag-to-connect from the right port of one node to the left port of another.
  Click an edge to delete it. Cycle creation is blocked.
- **Add node** button (top-right of the canvas section) — opens a slide-in
  Drawer containing the **prefab catalog** grouped into Pre / Assess / Post.
  Each entry shows label + one-line summary; click to add. **Shift-click** to
  add multiple in a row without closing the drawer.
- **Phase sections below the canvas** — for each phase, a list of node cards
  with a property panel: label, id (slug), config keys derived from the
  catalog's `config_schema`, and Depends-on toggle chips for every other node
  (active = an edge exists; click to add or remove).
- Bottom right: **Cancel** / **Create workflow** buttons.

Saving calls `POST /workflows` with `{name, description, trigger,
required_corpora, required_hooks, graph: {nodes, edges}}`. The backend
validates the graph (no cycles, no duplicate node ids) before persisting.
Production data mode is required for create/edit/delete; demo mode rejects
with a clear error so you don't lose work to an in-memory restart.

### 3.6 Edit workflow — `/workflows/[id]/edit`

Same editor as `/workflows/new`, pre-populated from the existing workflow.
Built-in templates are read-only; only `template_origin === "user-defined"`
workflows can be edited or deleted.

### 3.7 Workflow run detail — `/workflow-runs/[id]`

Live trace of an execution.

- **Header** — workflow name, status (running, awaiting_approval, succeeded,
  failed, cancelled), triggered-by, triggered-at, finished-at
- **Steps** column — every step's id, type, status, duration, sandbox/finding
  links. Click a step → drawer opens with inputs (redacted), outputs (redacted),
  runtime trace events, sandbox run id, hook calls, policy decisions, evidence
  ids
- **Findings** + **Proposed changes** sub-lists — direct links into the
  case-file pages
- **Live event stream** (production data mode) — opens a WebSocket against
  `ws://…/ws/v1/workflow-runs/{id}/stream`; appends events as they arrive.
  Fixture mode skips the WS so there are no console errors

### 3.8 Finding detail — `/findings/[id]`

The "case file" for a single finding:

- Title, severity, status, confidence (numeric + bar)
- Cited obligations (URNs with hover tooltips) and document chunks (citation
  paths)
- Linked proposed changes (each with diff kind + residual risk)
- Reviewer + reviewed_at when applicable

### 3.9 Proposed change detail — `/proposed-changes/[id]`

- The unified diff (or json-patch / config / markdown), syntax-highlighted
- Sandbox run summary (image, command, exit code, logs preview)
- Linked finding, target asset/hook
- **Approve** and **Reject** buttons — POST to
  `/proposed-changes/{id}:approve` / `:reject`
- "Apply" only after approval, via `:apply`; the runtime fires the configured
  outbound hook with an idempotency key

### 3.10 Sandbox — `/sandbox`

A read-only ledger of every sandbox run launched on the platform: id, owner
(workflow run or proposed change), image, mode (docker / replay), exit code,
duration. Used to audit isolation posture and replay determinism.

### 3.11 Corpora — `/corpora`

- **New corpus** CTA at top-right opens a drawer: name, kind (regulation /
  standard / internal_policy / code_repo / process_artefact /
  evidence_reference), description, framework, jurisdiction, retention,
  source URL. Saves via `POST /corpora` and reloads the list
- **Catalogue** grid of corpora cards (kind badge, framework badge, name,
  description, URN, document count, indexed-at). Hovering reveals a delete
  button (production data mode only). Clicking a card → `/corpora/[id]`
- **Search across corpora** — query box + corpus picker; calls
  `POST /corpora/{id}:search` and renders ranked chunks with citation paths

### 3.12 Corpus detail — `/corpora/[id]`

- Header — name, kind, description, document count, indexed-at, URN
- **Upload documents** panel — multi-file picker. Accepts `.pdf, .md, .txt,
  .markdown, .csv, .json, .yaml, .yml`. Binaries (PDFs) are kept whole for
  workflow sandboxes; text-encoded files are also chunked for retrieval. Each
  upload shows progress + a success line with title, size, chunk count
- **Documents** list — title, citation, source URI, content hash (truncated),
  chunk count
- **Within {corpus}** — corpus-scoped search box (same shape as the global
  search)

### 3.13 Obligations — `/obligations`

- Top-right CTAs: **Import YAML** (drawer with sample, supports bulk import via
  `POST /obligations:import-yaml`) and **New obligation** (drawer with
  framework, citation, text, severity, version, high-risk toggle, jurisdictions,
  asset types — supports `POST /obligations`)
- **Graph · Obligations · Controls · Assets** — three-column SVG render of the
  full obligation chain (the same shape that appears in the audit packet)
- **Ledger** table — every obligation with framework badge, citation+excerpt
  cell, default severity, version, and per-row Edit / Delete actions (Edit
  reuses the same drawer; Delete confirms then `DELETE /obligations/{urn}`)

### 3.14 Hooks — `/hooks`

- Top-right CTAs: **New JSON Stack hook** (links to `/hooks/validate?new=1`
  with a fresh manifest scaffold) and **Validate manifest** (open validator
  with the sample)
- **Configured hooks** directory with two filter rows: kind (All / MCP / JSON
  Stack) and category (collaboration, source control, ticketing, etc.). Hooks
  are grouped by category
- Each row shows status dot, name, id, kind badge, direction + effect-radius
  badges, operation/scope count, an inline **Test** button (calls
  `POST /hooks/{id}:test` and shows ok-latency or fail inline), and a chevron
  to navigate to the detail page
- **Recent calls** ledger at the bottom — every hook call, idempotency key,
  duration, status

### 3.15 Hook detail — `/hooks/[id]`

- Connection panel — endpoint, auth ref, manifest provider, base URL, auth
  kind, effect radius, direction, scopes
- For JSON Stack hooks, an **Operations** section listing each operation with
  method, path, input schema, output map. Each operation has a "Run dry"
  button that calls `:preview`
- Auto-test banner when arrived at via `?test=1` (e.g. after persisting a new
  hook from the validator)

### 3.16 Hooks · Validate — `/hooks/validate`

Three stacked panels:

- **Manifest** — JSON validator. Paste or scaffold a JSON Stack manifest, hit
  Validate. On a green result, a **Save & enable** button appears that calls
  `POST /hooks/json-stack` and redirects to `/hooks/{id}?test=1`. The
  `?new=1` query param swaps in a fresh scaffold instead of the sample
- **Importer** — paste OpenAPI JSON or YAML, pick which operations to convert,
  Convert builds a manifest (with backend assistance for YAML) and shows
  the JSON. Save persists to `/hooks/json-stack`
- **Provider stream probe** — pick provider (openai / anthropic / google),
  prompt, dry-run. Streams via `POST /models:stream` and renders deltas

### 3.17 Evidence — `/evidence`

- **Generate audit packet** builder — period (7d / 14d / 30d / 90d), scope
  (all / workflow_only / supervision_only), Generate. Calls
  `POST /audit-packets:generate` with the chosen scope; the runtime stores
  the merged scope (label + asset_ids + workflow_run_ids + obligation_urns)
  on the persisted `AuditPacket` and signs the sidecar with ed25519
- **Recent packets** ledger — status, scope label, period, packet hash,
  generated-at
- **Preview** card (visible when a packet is `ready`) — paper-textured cover
  page rendering of the packet: period, generated-at, packet hash, pubkey
  fingerprint, scope detail, counts (workflow runs / findings / proposed
  changes / supervision events / evidence records). Lays out as a real
  printed audit packet
- **Evidence ledger** — every `EvidenceRecord` with timestamp, summary, hash,
  obligation count

---

## 4. End-to-end user journeys

### 4.1 Run an existing prefab end-to-end

1. `/workflows` → click a template card (e.g. **code_compliance_scan_full**)
2. On `/workflows/[id]`, click **instantiate run**
3. Lands on `/workflow-runs/[id]`. Watch the steps tick from `pending` →
   `running` → `succeeded`. Click any step for trace + redacted I/O
4. When the run hits **policy_gate** then **human_gate**, the run pauses at
   `awaiting_approval`. Approve via `POST /workflow-runs/{id}:resume?approved=true`
   (or via the proposed-change detail page)
5. After approval the run finishes; the **open_pr** step fires the configured
   outbound hook; finding + proposed change rows appear linked from the run

### 4.2 Compose a custom workflow

1. `/workflows` → **New workflow**
2. Fill name, description; select required corpora (only the ones you've
   already created are pickable)
3. Click **Add node** — drawer opens with the prefab catalog grouped by
   phase. Click a Pre node, then an Assess node, then one or more Post nodes
   (Shift-click to add several without closing the drawer)
4. Drag node headers to lay them out. Drag the right port of an upstream node
   to the left port of a downstream node to wire it. Click an edge to remove it
5. In the phase sections below the canvas, edit each node's label, id, and
   config-schema fields. The Depends-on chips are an alternative way to wire
   edges
6. Click **Create workflow**. On success you land on `/workflows/{id}`,
   ready to instantiate

### 4.3 Add a corpus and feed it into a workflow

1. `/corpora` → **New corpus** → fill name + kind (e.g. `regulation`) → save
2. On the new card, click through to `/corpora/[id]`
3. **Upload documents** → pick PDFs / markdown / text. Text files are also
   chunked for retrieval; binaries are stored whole and forwarded to the
   agent sandbox at run time
4. Author or edit a workflow; in the **Required corpora** picker, select your
   new corpus. Save
5. Instantiate the workflow. The agent step's manifest will include each
   document (`base64` inline up to per-doc and total caps; `binary_path`
   reference otherwise) so the agent reasons over the actual content

### 4.4 Manage obligations

1. `/obligations` → **New obligation** for individual entries, or **Import
   YAML** for bulk. Either populates the obligation graph at the top + the
   ledger below
2. Per-row Edit reopens the same drawer; Delete confirms then removes the
   obligation from the registry
3. Newly-created obligations are immediately citeable from agent findings —
   they appear in `corpus.query` retrieval and in the obligation chain on the
   audit packet

### 4.5 Persist a custom JSON Stack hook from an OpenAPI spec

1. `/hooks` → **New JSON Stack hook** → opens `/hooks/validate?new=1` with a
   fresh scaffold
2. Edit the scaffold or paste your own manifest, click **Validate**
3. On a clean validate, **Save & enable** persists via
   `POST /hooks/json-stack` and redirects to `/hooks/{id}?test=1` which
   automatically fires `:test`
4. Or use the Importer panel: paste OpenAPI JSON/YAML, pick operations,
   Convert, then **Save hook**
5. The new hook is now selectable in `required_hooks` for any workflow

### 4.6 Generate an audit packet

1. `/evidence` → pick period and scope → **generate packet**
2. The new row appears in **Recent packets** with status `generating`, then
   `ready`
3. The **Preview** section shows the cover page for the most-recent ready
   packet: period, hash, fingerprint, scope detail, counts. The PDF + JSON
   sidecar are rendered server-side; the sidecar is ed25519-signed and can be
   verified offline with `scripts/verify_audit_packet.py`

---

## 5. Prefab workflows reference

All six are seeded into the workflow table on first boot from
`apps/api/praetor_api/services/production_workflows.py:WORKFLOW_TEMPLATES`.
Each is a typed DAG of step types the runtime executes natively. Each step
falls into one of three phases — pre-assessment / assessment / post-assessment
— so the visual canvas can lay it out into swimlanes deterministically.

| Workflow id | Steps | Outcome |
|---|---|---|
| `code_compliance_scan` | 4 | Findings on a code repo |
| `code_compliance_scan_full` | 8 | Findings + sandboxed remediation PR |
| `vendor_risk_review` | 5 | Vendor SOC2/ISO gap analysis + remediation proposal |
| `policy_gap_analysis` | 7 | Gaps in existing controls + proposed new policy text |
| `evidence_collection` | 4 | Evidence sweep bound to obligations |
| `ai_system_intake` | 5 | New AI system classification + tier gate |

### `code_compliance_scan`

Lightweight scan, no remediation.

- Pre: `pull` (`hook.in`) → `retrieve_controls` (`corpus.query`)
- Assess: `scan` (`agent`)
- Post: `emit` (`finding.emit`)

### `code_compliance_scan_full`

Full remediation flow.

- Pre: `pull` → `retrieve_controls`
- Assess: `scan`
- Post: `emit` → `propose` (`change.propose`) → `policy_gate` (`gate.policy`)
  → `human_gate` (`gate.human`) → `open_pr` (`hook.out`)

### `vendor_risk_review`

SOC2/ISO mapping + remediation proposal.

- Pre: `load_attestation` (`hook.in`) → `retrieve_obligations` (`corpus.query`)
- Assess: `analyze` (`agent`)
- Post: `emit` → `propose_remediation` (`change.propose`)

### `policy_gap_analysis`

Onboard a new regulation; propose new control text.

- Pre: `load_regulation` → `retrieve_existing_controls`
- Assess: `analyze_gaps`
- Post: `emit` → `propose_controls` → `policy_gate` → `human_gate`

### `evidence_collection`

Sweep source systems, organise candidates, bind to obligations.

- Pre: `read_files` → `retrieve_obligations`
- Assess: `organize`
- Post: `emit`

### `ai_system_intake`

Classify a newly-registered AI system and gate the tier.

- Pre: `intake_form` → `retrieve_obligations`
- Assess: `classify`
- Post: `policy_gate` → `emit`

For the full step list (with `with` config blocks, dependencies, hooks, and
corpora) see `apps/api/praetor_api/services/production_workflows.py`.

---

## 6. Custom workflows — node catalog

The visual editor's drawer palette is sourced from
`GET /workflows/nodes/catalog`. The runtime currently executes these step
types end-to-end:

| Type | Phase | Purpose |
|---|---|---|
| `hook.in` | pre | Fetch from a connected integration (repo / ticket / doc / storage) |
| `corpus.query` | pre | Governed retrieval — returns chunks with citation paths |
| `transform` | pre/post | Deterministic data shaping |
| `agent` | assess | Sandboxed reasoning step (governed model agent) |
| `gate.policy` | post | OPA-style decision point |
| `gate.human` | post | Pause for approval; resumes via `/workflow-runs/{id}:resume` |
| `finding.emit` | post | Persist findings with citations + confidence |
| `change.propose` | post | Generate a remediation proposal |
| `hook.out` | post | Outbound integration call (PR / ticket / message) |

The catalog also exposes forward-looking types — `model.complete`, `agent.run`,
`sandbox.run`, `evidence.generate`, `audit.packet`, `notify`,
`trigger.{manual,schedule,webhook,event}` — that the editor accepts but the
runtime currently fails with `unsupported_step_type`. Treat them as scaffolding
for future runtime capability.

Custom workflow URNs are namespaced under
`urn:praetor:workflow:custom:{id}` so they never collide with the seeded
prefabs. Templates cannot be edited or deleted; if you want to evolve one,
clone its graph into a new custom workflow first.

---

## 7. Where things live

- **Prefab definitions + step executor** — `apps/api/praetor_api/services/production_workflows.py`
- **Node catalog endpoint** — same file (`NODE_CATALOG`); served by `GET /workflows/nodes/catalog`
- **Visual editor** — `apps/web/components/workflow-graph/WorkflowFormEditor.tsx`, `WorkflowCanvas.tsx`, `useWorkflowGraph.ts`
- **Read-only swimlane** — `apps/web/components/workflow-graph/WorkflowSwimlanes.tsx`
- **Drawer primitive** (used for forms + palette) — `apps/web/components/primitives/Drawer.tsx`
- **Sidebar + header shell** — `apps/web/components/shell/`
- **Architecture rationale for the node-based runtime** — `docs/INTEGRATIONS_AND_NODE_WORKFLOWS.md`
- **Implementation handoff snapshot** — `docs/IMPLEMENTATION_HANDOFF.md`
- **Auth / secrets boundary** — `docs/AUTH_AND_SECRETS.md`
- **Demo script** — `docs/DEMO.md`
