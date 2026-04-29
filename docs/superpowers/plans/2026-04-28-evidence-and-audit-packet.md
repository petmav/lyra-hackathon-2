# Evidence Generator + Audit Packet — Sub-Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Parent plan:** `2026-04-28-praetor-hackathon-build.md` — primarily Phase 4 Tasks 4.1–4.2.

**Goal:** Continuously assemble `EvidenceRecord`s linking events ↔ controls ↔ obligations ↔ assets across **both** surfaces (workflow runs and customer-supervised assets). On demand, produce an `AuditPacket` PDF that an external auditor can read alongside a JSON sidecar they can verify cryptographically.

**Architecture:** A worker subscribes to the events bus and writes EvidenceRecords as policies fire and changes are applied. The Audit Packet generator queries Evidence + Findings + ProposedChanges + Approvals + HookCalls + workflow runs over a period and renders a single PDF with embedded obligation-chain graphs, an evidence appendix with hash-chained samples, and an Ed25519 signature over the JSON sidecar.

**Tech Stack:** Python 3.12, ReportLab (PDF), graphviz CLI (obligation graph render), pynacl (Ed25519 signing), Pillow (image manipulation), MinIO (artefact storage), async SQLAlchemy, Redis Streams consumer.

**Interface this sub-plan exposes:**

HTTP: `GET /evidence-records?asset_id=...`, `POST /audit-packets:generate` body `{period_start, period_end, scope: {asset_ids?, workflow_run_ids?, obligation_urns?}}`, `GET /audit-packets/{id}` → presigned URLs for PDF + JSON.

---

## File map

```
apps/api/praetor_api/
├── routers/evidence.py
├── services/
│   ├── evidence.py             # the worker + write logic
│   ├── audit_packet.py         # the PDF assembler
│   ├── obligation_graph.py     # graphviz render
│   ├── signing.py              # Ed25519 sign + verify
│   └── pdf_render/
│       ├── __init__.py
│       ├── cover.py
│       ├── exec_summary.py
│       ├── workflow_run_section.py
│       ├── supervision_section.py
│       ├── hook_ledger.py
│       ├── approvals.py
│       ├── evidence_appendix.py
│       └── styles.py
└── models/
    ├── evidence_record.py
    └── audit_packet.py

content/keys/
└── praetor-signing.key.example

tests/audit/
├── test_evidence_worker.py
├── test_audit_packet_pdf.py
├── test_signing.py
└── fixtures/
    └── canned_run.json
```

---

## Task 1: Evidence Generator worker

**Files:** `apps/api/praetor_api/services/evidence.py`, additions to `models/evidence_record.py`.

- [ ] **Step 1: failing test** — push three events to the bus (`policy.decision.hot`, `agent.tool.refused`, `change.applied`); start worker; assert one EvidenceRecord per event with correct obligation links derived from the control-to-obligation mapping in `content/controls/*.rego` metadata + `content/obligations/*.yaml`.

- [ ] **Step 2: implement**

```python
async def consume_loop():
    async for evt in bus.consume("events", group="evidence", name="worker-1"):
        try:
            await record(evt)
            await bus.ack("events", "evidence", evt["id"])
        except Exception as e:
            log.exception("evidence write failed", evt_id=evt["id"])

async def record(evt):
    if evt["type"] not in TRACKED_TYPES: return
    obligations = await obligations_for_control(evt.get("control_id"))
    er = EvidenceRecord(
        obligation_ids=obligations,
        control_id=evt.get("control_id"),
        asset_id=evt.get("asset_id"),
        workflow_run_id=evt.get("workflow_run_id"),
        event_ids=[evt["id"]],
        decision_ids=[evt.get("policy_decision_id")] if evt.get("policy_decision_id") else [],
        hash=hash_evidence(evt),
    )
    await session.add(er)
```

`TRACKED_TYPES = {"policy.decision.hot", "policy.decision.warm", "agent.tool.refused", "agent.tool.called", "workflow.step.finished", "change.applied", "change.proposed", "finding.emitted", "approval.decided"}`.

- [ ] **Step 3: tests pass.** Commit.

## Task 2: Obligation graph rendering

**Files:** `apps/api/praetor_api/services/obligation_graph.py`.

- [ ] **Step 1: failing test** — given a list of `(obligation, control, asset)` triples, asserts `render_png(triples)` produces a PNG ≥ 50KB with non-trivial content.

- [ ] **Step 2: implement**

```python
def render_png(triples) -> bytes:
    dot_lines = ["digraph G {", "rankdir=LR;",
                 'node [shape=box, fontname="Helvetica"];']
    for o, c, a in triples:
        dot_lines.append(f'"{o.urn}" [label="{o.framework}\\n{o.citation}"];')
        dot_lines.append(f'"{c.id}" [label="{c.name}", shape=ellipse];')
        dot_lines.append(f'"{a.urn}" [label="{a.name}", style=filled, fillcolor=lightblue];')
        dot_lines.append(f'"{o.urn}" -> "{c.id}";')
        dot_lines.append(f'"{c.id}" -> "{a.urn}";')
    dot_lines.append("}")
    p = subprocess.run(["dot", "-Tpng"], input="\n".join(dot_lines).encode(),
                       capture_output=True, check=True)
    return p.stdout
```

- [ ] **Step 3: test passes.** Commit.

## Task 3: Ed25519 signing

**Files:** `apps/api/praetor_api/services/signing.py`.

- [ ] **Step 1: failing test** — sign a JSON dict, verify with the public key, mutate one byte → verify fails.

- [ ] **Step 2: implement**

```python
from nacl.signing import SigningKey, VerifyKey
import json

def sign_canonical(payload: dict, sk: SigningKey) -> dict:
    body = json.dumps(payload, sort_keys=True, separators=(",",":")).encode()
    sig = sk.sign(body).signature
    return {"payload": payload, "sig": sig.hex(),
            "pubkey": sk.verify_key.encode().hex(),
            "alg": "ed25519"}

def verify(envelope: dict) -> bool:
    body = json.dumps(envelope["payload"], sort_keys=True, separators=(",",":")).encode()
    vk = VerifyKey(bytes.fromhex(envelope["pubkey"]))
    try: vk.verify(body, bytes.fromhex(envelope["sig"])); return True
    except Exception: return False
```

Generate a dev key at startup if `content/keys/praetor-signing.key` is absent (write to disk, log fingerprint).

- [ ] **Step 3: tests pass.** Commit.

## Task 4: PDF section renderers

**Files:** `apps/api/praetor_api/services/pdf_render/*.py`.

Each section is a function taking ReportLab `Story` and a section context, appending flowables. Style sheet (`styles.py`) defines: `H1`, `H2`, `H3`, `Mono`, `Body`, `Small`, plus a `Cell` for table cells.

- [ ] `cover.py` — title (`Praetor Audit Packet`), period, scope (asset URNs / workflow_run URNs / obligation URNs), packet hash, generated_at, signing pubkey fingerprint.
- [ ] `exec_summary.py` — counts: workflow runs, findings (by severity), proposed changes (by status), supervision violations, evidence records.
- [ ] `workflow_run_section.py` — for each run: name, trigger, inputs (redacted), step timeline (table: step_id, type, status, duration_ms), findings list (with citations), proposed changes (with sandbox results), approver chain.
- [ ] `supervision_section.py` — for each supervised asset: controls tested, decisions, violations, applied remediations.
- [ ] `hook_ledger.py` — table of HookCalls in period (hook, direction, status, latency, redacted args).
- [ ] `approvals.py` — table of approvals (subject, requester, role, decided_by, outcome, timestamp).
- [ ] `evidence_appendix.py` — sample of EvidenceRecords with hash chain rendered (prev → self).

Each has its own focused test that asserts rendered Story length and that key strings appear in the rendered PDF text. Commit after each.

## Task 5: Audit Packet assembler

**Files:** `apps/api/praetor_api/services/audit_packet.py`.

- [ ] **Step 1: failing test** loads a fixture `canned_run.json` (one full workflow run + one supervision violation), generates a packet, asserts:
  - PDF saved to MinIO at `audit-packets/{id}.pdf` with size > 50KB.
  - JSON sidecar saved at `audit-packets/{id}.json` and is valid JSON.
  - JSON sidecar passes `signing.verify`.
  - DB row in `audit_packet` table with `packet_hash` and `signature` populated.
  - Cover page + a workflow run section + a supervision section + an obligation graph PNG embedded.

- [ ] **Step 2: implement**

```python
async def generate(period_start, period_end, scope):
    ctx = await collect_context(period_start, period_end, scope)
    # ctx: dict of workflow_runs[], findings[], proposed_changes[], approvals[],
    #      hook_calls[], evidence_records[], supervision[], obligation_triples[]
    sidecar = canonical_sidecar(ctx)
    signed = sign_canonical(sidecar, signing_key)
    sidecar_bytes = json.dumps(signed, sort_keys=True).encode()
    sidecar_key = f"audit-packets/{uuid()}.json"
    await s3.put_object(Bucket=BUCKET, Key=sidecar_key, Body=sidecar_bytes)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Praetor Audit Packet")
    story = []
    cover.render(story, ctx, signed["pubkey"])
    exec_summary.render(story, ctx)
    obligation_graph_png = obligation_graph.render_png(ctx["obligation_triples"])
    story.append(Image(io.BytesIO(obligation_graph_png), width=480, height=300))
    for run in ctx["workflow_runs"]:
        workflow_run_section.render(story, run)
    supervision_section.render(story, ctx["supervision"])
    hook_ledger.render(story, ctx["hook_calls"])
    approvals.render(story, ctx["approvals"])
    evidence_appendix.render(story, ctx["evidence_records"])
    doc.build(story)
    pdf_bytes = buf.getvalue()
    pdf_key = f"audit-packets/{uuid()}.pdf"
    await s3.put_object(Bucket=BUCKET, Key=pdf_key, Body=pdf_bytes)
    packet_hash = sha256(pdf_bytes).hexdigest()
    row = await session.add(AuditPacket(
        period_start=period_start, period_end=period_end,
        scope=scope, pdf_path=pdf_key, json_sidecar_path=sidecar_key,
        packet_hash=packet_hash, signature=signed["sig"]))
    return row
```

- [ ] **Step 3: tests pass.** Commit.

## Task 6: HTTP route + Evidence UI

**Files:** `apps/api/praetor_api/routers/evidence.py`, `apps/web/app/evidence/page.tsx`, `apps/web/components/audit-packet/`.

- [ ] `POST /audit-packets:generate` queues generation (worker writes the row with status=`generating` then `ready`); returns `{packet_id, status}`.
- [ ] `GET /audit-packets/{id}` returns presigned URLs for PDF + JSON sidecar once `ready`.
- [ ] UI: list of past packets + "Generate Audit Packet" button → modal with period picker + scope picker → fires generation → polls `GET` → opens PDF in new tab when ready.
- [ ] Commit.

## Task 7: Evidence list UI

**Files:** `apps/web/app/evidence/page.tsx`.

- [ ] Filterable table of EvidenceRecords (by asset, by obligation, by period). Click → drawer showing the linked events, decisions, and the obligation chain.
- [ ] Commit.

## Task 8: External verification CLI

**Files:** `scripts/verify_audit_packet.py`.

- [ ] Standalone script: `python scripts/verify_audit_packet.py packet.json` reads the JSON sidecar, runs `signing.verify`, compares PDF SHA-256 against `packet_hash`. Prints pass/fail.
- [ ] Documented in README so an auditor can run it without the platform. This is the "verifiable evidence" claim made literal.
- [ ] Commit.

---

## Self-review

- Both surfaces (workflow runs + supervised assets) end up in one PDF (Task 5). Obligation chain diagram shows the cross-cutting view.
- JSON sidecar is what an auditor verifies; PDF is what they read. Signing covers the sidecar; the PDF hash is in the sidecar — so any tamper to either is detectable.
- Evidence Generator is event-driven and idempotent (Task 1). Replaying the bus from offset 0 produces the same EvidenceRecord set.
- The verification CLI (Task 8) closes the loop: customer's auditor can verify offline.

## Out of scope for this sub-plan

- HSM-backed signing keys (post-hackathon).
- Streaming PDF to client (we generate to MinIO then presigned URL).
- Diff between two audit packets (post-hackathon "delta packet" feature).
- WORM-storage retention guarantees (post-hackathon).
