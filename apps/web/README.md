# Praetor — Web Frontend

The user-facing surface of Praetor: the governed runtime for agentic GRC.

This app renders both Praetor surfaces in one UI:

1. **Workflow Runtime** — agentic compliance work executed against the
   customer's stack (governed by the same control plane it offers).
2. **Supervision** — runtime governance for the customer's own production AI.

Both surfaces share the same data model, hash chain, three-pane live view,
and audit packet output. That parity is enforced visually: the workflow agent
trace and a supervised production agent trace use the same component
(`<AgentDetail />`) — see `app/workflow-runs/[id]/page.tsx` for the
side-by-side rendering that delivers the "self-governance" demo moment.

## Stack

- Next.js 15 (App Router) + React 19
- Tailwind CSS 3 + bespoke design tokens (no shadcn — primitives are
  hand-written so the visual language stays cohesive)
- TypeScript 5 (strict)
- Lucide icons
- Hand-rendered SVG for DAG and obligation graphs (no React Flow — keeps
  the aesthetic terse and dependency footprint small)

## Visual language

"Editorial Archive Terminal." Dark, dense, typographic. Three faces:
**Fraunces** (display, variable serif), **General Sans** (body), **JetBrains
Mono** (data: hashes, URNs, latencies). Single gold accent. Hairline rules,
not boxed cards. Hash chains rendered as actual hairlines under events.

Tokens live in `app/globals.css` and `tailwind.config.ts`.

## Stubbed backend

The API client at `lib/api/index.ts` is a stub: rich in-memory fixtures
shaped to the data model in `docs/superpowers/plans/2026-04-28-praetor-hackathon-build.md`
§2.1, with simulated latency and "live" streams driven by `setInterval`.

To wire the real FastAPI gateway, replace `lib/api/index.ts` with a fetch
implementation that hits `NEXT_PUBLIC_API_BASE`. Every route in this app
calls the client through the named exports it exposes (`api.assets.list`,
`api.workflows.run`, etc.) — there is no rogue `fetch()` anywhere.

## Run

```bash
cd apps/web
pnpm install
pnpm dev
# open http://localhost:3000
```

## Routes

| Path | Purpose |
|---|---|
| `/` | Dashboard — counts, in-flight workflows, supervision violations, recent audit packets |
| `/inventory` | All Assets (production agents + workflow agents in one list) |
| `/assets/[id]` | Three-pane live view — used identically for both surfaces |
| `/workflows` | Templates + saved workflows; instantiate a run |
| `/workflows/[id]` | Workflow definition view |
| `/workflow-runs/[id]` | DAG live view + step drawer + self-governance side-by-side panel |
| `/corpora` | Corpora list, version chains, hybrid search |
| `/corpora/[id]` | Documents + chunk-level search |
| `/hooks` | MCP servers, native connectors, recent calls |
| `/obligations` | Obligation → control → asset graph |
| `/sandbox` | Active and historical sandbox runs |
| `/evidence` | Evidence records + audit packet builder |

## File map

```
app/                 # Next routes
components/
├── shell/           # sidebar, header, alerts tray
├── primitives/      # Card, Badge, Drawer, Tabs, etc. (hand-written)
├── data/            # Urn, Hash, HashChain, Citation, Confidence, Timestamp
├── agent-detail/    # the three-pane live view (used by both surfaces)
├── memory-inspector/
├── policy-feed/
├── workflow-graph/  # SVG DAG renderer
├── workflow-run/    # DagView, StepDrawer, SelfGovernancePanel
├── corpus-search/
├── hook-config/
├── finding-card/
├── proposed-change/ # diff viewer
├── audit-packet/    # builder + list + on-screen "PDF preview"
└── obligation-graph/  # SVG graph
lib/
├── api/             # stubbed client + entity types + fixtures
├── ws/              # event-stream simulation
└── utils/
```
