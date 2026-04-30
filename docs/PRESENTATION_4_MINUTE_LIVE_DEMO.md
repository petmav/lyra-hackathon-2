# Praetor 4-Minute Presentation With Live Demo

## Goal

Position Praetor as a governed agentic GRC runtime: it does compliance work with agents, governs those agents while they run, and turns the execution trace into evidence and audit packets.

Primary demo path: `code_compliance_scan_full`.

Backup path: use the seeded run from the dashboard if the live run is slow.

## Setup

Start the deterministic demo stack:

```powershell
npm run demo
```

Open:

```text
http://localhost:3000
```

Keep these tabs ready:

- Dashboard: `http://localhost:3000`
- Workflows: `http://localhost:3000/workflows`
- Evidence: `http://localhost:3000/evidence`
- Backup seeded run: click "View live run" from the dashboard

Optional production-shaped demo:

```powershell
npm run prod
```

Use demo mode for the judged presentation unless the environment is already warmed up. It is deterministic and still shows the full product narrative.

## Four-Minute Structure

### 0:00-0:35 - Problem And Thesis

Screen: Dashboard.

Talk track:

"AI compliance is usually handled after the fact: screenshots, tickets, spreadsheets, and manual evidence gathering. That breaks down when agents are making tool calls, using memory, and changing production systems.

Praetor is a governed runtime for agentic GRC. The same platform that supervises production agents can also run compliance workflows as governed agents, with policy checks, citations, sandboxing, and hash-chained evidence built in."

Point to:

- Governed assets
- Live workflows
- Open findings
- Audit packets

### 0:35-1:10 - Workflow Catalog

Screen: `/workflows`.

Click: `code_compliance_scan_full`.

Talk track:

"This is the workflow catalog. These are not chat prompts hidden behind buttons; each workflow is a typed DAG. For the demo I am using `code_compliance_scan_full`.

It pulls a repo through a hook, retrieves relevant obligations from the compliance corpus, runs a sandboxed agent assessment, emits a cited finding, proposes a fix, gates it through policy and human approval, and can dispatch the remediation through an outbound integration."

Point to:

- Required hooks
- Required corpora
- Pre / Assess / Post workflow shape
- The workflow `open` action and the `run` button on the detail page

### 1:10-2:10 - Live Run Trace

Click: choose `Immediate`, then click `run`.

Screen: `/workflow-runs/{id}`.

Talk track:

"When the run starts, the agent becomes a governed asset. Praetor records structured runtime events: hook calls, corpus retrievals, sandboxed agent execution, agent rationale summaries, policy decisions, findings, proposals, and final outputs.

That matters because the platform can answer more than 'what did the model say?' It can answer which source system was touched, which obligations were retrieved, what policy decisions were made, what data crossed the boundary, and why the result is defensible."

Click:

- Open the `pull` or `retrieve_controls` step drawer.
- Open the `scan` step drawer.

Point to:

- Runtime trace
- Redacted inputs and outputs
- Corpus citations
- Sandbox run id
- Hash-chained activity

### 2:10-3:05 - Finding And Remediation

Click: linked finding or proposed change from the run.

Talk track:

"The scan finds a high-severity issue in the Northwind support bot: the `send_email` tool accepts arbitrary recipients without an approved-domain allowlist.

This is not just a note in a transcript. It is a first-class finding with severity, confidence, cited obligations, and a link back to the run that produced it. The full workflow also creates a proposed remediation and requires approval before any external write like a pull request, Jira issue, Slack message, or ServiceNow record."

Point to:

- Finding severity and confidence
- Cited obligations such as internal data minimisation, GDPR, ISO 42001, or OWASP Agent risks
- Proposed change diff
- Approval state

### 3:05-3:40 - Evidence And Audit Packet

Screen: `/evidence`.

Click: Generate packet, or show the most recent ready packet.

Talk track:

"The payoff is that evidence is produced while the work happens. Praetor consumes the runtime event stream, binds events to obligations and controls, and packages them into audit records.

Audit packets include the workflow run, findings, proposed changes, policy decisions, evidence records, hashes, and an Ed25519 signature. So the audit trail is not reconstructed later; it is a product of governed execution."

Point to:

- Evidence ledger
- Packet status
- Packet hash
- Signature / public-key fingerprint
- Packet preview counts

### 3:40-4:00 - Close

Screen: Dashboard or workflow run detail.

Talk track:

"The core idea is simple: if agents are going to do compliance work, they need to be governed like production systems. Praetor gives teams one control plane for both surfaces: the AI they ship and the AI they use to govern it.

That turns compliance from periodic archaeology into live, policy-governed execution with evidence by default."

## Demo Click Path

1. Start at `/`.
2. Click `/workflows`.
3. Open `code_compliance_scan_full`.
4. Select `Immediate`, then click `run`.
5. Open step drawer for `retrieve_controls` or `scan`.
6. Wait for the human gate, then click `approve`.
7. Open the linked finding and proposed change.
8. Go to `/evidence`.
9. Generate or show an audit packet.
10. End on dashboard or the run trace.

## One-Slide Version

Title: Praetor - governed agentic GRC.

Three bullets:

- Runs compliance workflows as typed, governed agent DAGs.
- Supervises every hook, corpus query, sandbox step, policy gate, finding, and remediation.
- Converts hash-chained runtime events into signed evidence and audit packets.

Demo promise:

"I will run a code compliance workflow live: repo pull, obligation retrieval, sandboxed agent scan, cited finding, proposed fix, approval gate, and audit evidence."

## Backup Lines

- "Demo mode is deterministic for reliability; production mode persists the same objects in Postgres and streams events through Redis."
- "The runtime supports six seeded workflows: code compliance, full remediation, vendor risk review, policy gap analysis, evidence collection, and AI system intake."
- "External writes are guarded: effectful hook calls require approval, secret resolution, and idempotency keys; agent execution is sandboxed."
- "Praetor is not a dashboard around a model. The model is only one step inside a governed workflow runtime."

## If The Live Run Is Slow

Use one of these recovery moves:

- Click "View live run" from the dashboard and narrate the seeded trace.
- Open `/workflow-runs` and pick the newest run.
- Say: "I will switch to the seeded run so we can inspect the same trace without waiting on the local runtime."

## If The API Is Down

Use fixture mode:

```powershell
$env:NEXT_PUBLIC_DATA_SOURCE='fixtures'
npm run demo:web
```

Then show:

- Dashboard
- `/workflows`
- Seeded workflow run
- Finding detail
- Proposed change detail
- Evidence packet preview

## What To Avoid Saying

- Do not imply every external integration is live in demo mode. Say "hook layer" or "dispatch path", and call out dry-run/deterministic behavior when relevant.
- Do not claim this replaces auditors. It creates a defensible evidence trail for auditors.
- Do not over-index on the UI. The core claim is governed execution plus evidence generation.

## Repo Anchors

- Runtime and demo guide: `docs/DEMO.md`
- Operator walkthrough: `docs/WORKFLOWS.md`
- API surface: `docs/API.md`
- Implementation state: `docs/IMPLEMENTATION_HANDOFF.md`
- Workflow definitions: `apps/api/praetor_api/services/production_workflows.py`
- Demo simulator: `apps/api/praetor_api/services/demo_simulator.py`
- Frontend routes: `apps/web/app`
