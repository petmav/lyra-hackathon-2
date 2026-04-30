# Two-Minute Demo Script: `code_compliance_scan`

## Setup

- Start the demo stack with `npm run demo`.
- Open `http://localhost:3000/workflows`.
- Use `code_compliance_scan` for the short findings-only path.
- If the audience asks for remediation, switch to `code_compliance_scan_full` after the main demo.

## Demo Goal

Show Praetor as a governed agentic compliance runtime, not a workflow router: it pulls source material, retrieves obligations, runs a governed agent scan, emits a cited finding, and leaves a live trace that can become audit evidence.

## Script

### 0:00-0:15 - Open On The Problem

"Most compliance work around AI is still after-the-fact evidence gathering: screenshots, tickets, and manual review. Praetor changes that by running the compliance work itself, while applying the same controls we expect production AI systems to follow."

On screen: Dashboard or Workflows page.

### 0:15-0:35 - Show The Workflow Catalog

"This is the workflow catalog. Praetor ships with prefab compliance workflows, and each one is a typed Directed Acyclic Graph rather than a black-box automation. For this demo I'm using `code_compliance_scan_full`: pull the repo, retrieve relevant controls, run an agent assessment, emit findings, and make an edit to fix."

Click `code_compliance_scan_full`.

Point out: required hooks, required corpora, and the Pre / Assess / Post workflow shape.

### 0:35-0:55 - Instantiate The Run

"The important distinction is that this agent does not just receive a prompt. The run starts with controlled inputs: a source-control hook pulls code, and a corpus query retrieves the relevant obligations from ISO 42001 and internal data-minimisation policy."

Click `instantiate run`.

On screen: workflow run detail.

### 0:55-1:25 - Narrate The Live Trace

"Now the run is executing as a governed asset. Each step produces structured events: hook calls, corpus retrieval, agent thoughts, memory writes, and tool calls. That means the platform can answer not just what the agent concluded, but why it concluded it, which obligations it used, and what data crossed the boundary."

Click the `scan` step drawer if useful.

Point out: agent thought lines, memory/provenance, retrieved controls, and redacted step I/O.

### 1:25-1:45 - Show The Finding

"Here the scan finds a high-severity issue: `send_email` accepts arbitrary recipients without a recipient-domain allowlist. The finding is not just a note in a chat transcript; it is a first-class record with severity, confidence, cited obligations, and a link back to the run that produced it."

Open the finding from the run if available.

Point out: severity, confidence, cited obligation URNs, and source/corpus citations.

### 1:45-2:00 - Close On Platform Advantage

"This is the advantage: Praetor turns compliance from periodic archaeology into live governed execution. Compared with automation tools, it proves every step. Compared with AI governance dashboards, it runs controls where work happens. And because events are hash-chained and feed evidence records and audit packets, the audit trail is built while the agent is doing the work."

Optional final click: Evidence page or recent run list.

## Backup Lines

- "The short workflow stops at findings. The full version adds proposed patch generation, policy gate, human approval, and an outbound pull-request hook."
- "Demo mode is deterministic so the presentation is reliable; production mode persists workflows, runs, step runs, findings, proposed changes, policy decisions, sandbox runs, evidence records, and audit packets in Postgres."
- "Praetor's moat is self-governance: workflow agents are governed assets using the same policy, event, sandbox, corpus, and evidence model as customer-facing agents."

## Code/Docs Basis

- Workflow definition: `apps/api/praetor_api/services/production_workflows.py`
- Demo simulator events: `apps/api/praetor_api/services/demo_simulator.py`
- Operator guide: `docs/WORKFLOWS.md`
- Runtime/demo notes: `docs/DEMO.md`
