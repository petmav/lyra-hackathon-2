"""Demo-mode workflow simulator.

Drives an in-memory workflow run forward over time, emitting realistic
agentic events as it goes. The shape mirrors what a real run produces so
the existing UI components render naturally.

The simulator is reached through `demo_workflows.run_workflow`. Tests can
call `tick_run` directly with a zero-delay sleep callable for instant
completion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScriptedEvent:
    """A single event the simulator emits during a step."""

    type: str
    actor: str
    payload: dict[str, Any]
    delay_before: float = 0.5


@dataclass(frozen=True)
class ScriptedStep:
    """One step of a scripted run.

    `events` are emitted in order between `workflow.step.started` and
    `workflow.step.finished`. `final_outputs` is written into the step's
    `outputs_redacted` once the step succeeds. `findings` and `proposals`
    are appended to the run's `outputs.findings` / `outputs.proposed_changes`.

    `is_live_agent=True` marks the step the simulator should attempt to
    drive with a real OpenAI call (used by `code_compliance_scan_full`'s
    `scan` step). When the call succeeds, the live findings and a chunked
    `agent.thought` rationale replace the scripted ones for that step.
    """

    step_id: str
    step_type: str
    events: tuple[ScriptedEvent, ...]
    final_outputs: dict[str, Any]
    findings: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    proposals: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    is_live_agent: bool = False


@dataclass(frozen=True)
class ScriptedRun:
    """A full scripted workflow run."""

    workflow_id: str
    asset_id: str
    steps: tuple[ScriptedStep, ...]


import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from praetor_api.services.event_stream import append_event, make_event

logger = logging.getLogger(__name__)

SleepFn = Callable[[float], Awaitable[None]]


async def tick_run(
    run_id: str,
    *,
    script: ScriptedRun,
    sleep: SleepFn = asyncio.sleep,
    openai_api_key: str | None = None,
) -> None:
    """Drive the in-memory run forward, emitting events as it ticks.

    The run dict at `RUNS[run_id]` must already exist with all step_runs
    in `pending`. On return the run is in a terminal state
    (`succeeded` or `failed`) and `EVENTS` contains the full trace.
    """
    from praetor_api.services import demo_workflows  # local to avoid cycle

    run = demo_workflows.RUNS.get(run_id)
    if run is None:
        logger.warning("tick_run called for unknown run %s", run_id)
        return

    asset_id = script.asset_id

    try:
        await append_event(
            make_event(
                asset_id=asset_id,
                workflow_run_id=run_id,
                event_type="workflow.run.started",
                actor="workflow_runtime",
                payload={"workflow_id": script.workflow_id, "inputs": run.get("inputs", {})},
            )
        )

        for step in script.steps:
            step_record = _find_step_record(run, step.step_id)
            if step_record is None:
                continue
            step_record["status"] = "running"
            run["updated_at"] = _iso_now()

            await append_event(
                make_event(
                    asset_id=asset_id,
                    workflow_run_id=run_id,
                    workflow_step_id=step.step_id,
                    event_type="workflow.step.started",
                    actor="workflow_runtime",
                    payload={
                        "step": step.step_id,
                        "step_id": step.step_id,
                        "type": step.step_type,
                        "step_type": step.step_type,
                        "status": "running",
                    },
                )
            )

            live_findings: list[dict[str, Any]] | None = None
            if step.is_live_agent and openai_api_key:
                live_findings = await _emit_live_openai_thoughts(
                    asset_id=asset_id,
                    run_id=run_id,
                    step=step,
                    inputs=run.get("inputs", {}),
                    model=str(run.get("model") or "gpt-4o-mini"),
                    openai_api_key=openai_api_key,
                    sleep=sleep,
                )

            if live_findings is None:
                if not step.events:
                    # Steps with no scripted in-step events still get a small
                    # dwell so the DAG visibly progresses.
                    await sleep(0.8)
                for scripted in step.events:
                    if scripted.delay_before > 0:
                        await sleep(scripted.delay_before)
                    await append_event(
                        make_event(
                            asset_id=asset_id,
                            workflow_run_id=run_id,
                            workflow_step_id=step.step_id,
                            event_type=scripted.type,
                            actor=scripted.actor,
                            payload=dict(scripted.payload)
                            | {"step_id": step.step_id, "step_type": step.step_type},
                        )
                    )
                step_record["outputs_redacted"] = dict(step.final_outputs)
            else:
                step_record["outputs_redacted"] = {"findings": list(live_findings), "live": True}

            step_record["status"] = "succeeded"
            run["updated_at"] = _iso_now()

            if live_findings is not None:
                run.setdefault("outputs", {}).setdefault("findings", []).extend(live_findings)
            elif step.findings:
                run.setdefault("outputs", {}).setdefault("findings", []).extend(step.findings)
            if step.proposals:
                run.setdefault("outputs", {}).setdefault("proposed_changes", []).extend(step.proposals)

            await append_event(
                make_event(
                    asset_id=asset_id,
                    workflow_run_id=run_id,
                    workflow_step_id=step.step_id,
                    event_type="workflow.step.finished",
                    actor="workflow_runtime",
                    payload={
                        "step": step.step_id,
                        "step_id": step.step_id,
                        "step_type": step.step_type,
                        "status": "succeeded",
                        "outputs_redacted": step_record["outputs_redacted"],
                    },
                )
            )

        run["status"] = "succeeded"
        run["finished_at"] = _iso_now()
        run["updated_at"] = run["finished_at"]
        await append_event(
            make_event(
                asset_id=asset_id,
                workflow_run_id=run_id,
                event_type="workflow.run.finished",
                actor="workflow_runtime",
                payload={"status": "succeeded"},
            )
        )

    except Exception as exc:  # noqa: BLE001 - record + surface, don't crash the loop
        logger.exception("tick_run failed for %s", run_id)
        run["status"] = "failed"
        run["finished_at"] = _iso_now()
        run["updated_at"] = run["finished_at"]
        await append_event(
            make_event(
                asset_id=asset_id,
                workflow_run_id=run_id,
                event_type="workflow.run.failed",
                actor="workflow_runtime",
                payload={"error": f"{exc.__class__.__name__}: {exc}"},
            )
        )


def _find_step_record(run: dict[str, Any], step_id: str) -> dict[str, Any] | None:
    for step in run.get("step_runs", []):
        if step.get("step_id") == step_id:
            return step
    return None


def _iso_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


_OPENAI_URL = "https://api.openai.com/v1/responses"
_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


async def _emit_live_openai_thoughts(
    *,
    asset_id: str,
    run_id: str,
    step: ScriptedStep,
    inputs: dict[str, Any],
    model: str,
    openai_api_key: str,
    sleep: SleepFn,
) -> list[dict[str, Any]] | None:
    """Make a real OpenAI call. Emit chunked agent.thought events with the
    rationale and a final agent.tool.called(emit_finding). Return parsed
    findings, or None if the call failed for any reason (caller falls
    back to scripted)."""
    prompt = _build_live_prompt(inputs)
    try:
        text = await asyncio.to_thread(_call_openai_responses, openai_api_key, model, prompt)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.info("live OpenAI call failed for %s: %s", run_id, exc)
        return None

    parsed = _parse_response_text(text)
    if not parsed:
        return None

    rationale = str(parsed.get("thinking") or text).strip()
    findings = _normalise_findings(parsed.get("findings"))
    if not findings:
        return None

    chunks = _chunk_rationale(rationale, n=4)
    for chunk in chunks:
        await sleep(0.4)
        await append_event(
            make_event(
                asset_id=asset_id,
                workflow_run_id=run_id,
                workflow_step_id=step.step_id,
                event_type="agent.thought",
                actor="workflow_agent",
                payload={"text": chunk, "step_id": step.step_id, "step_type": step.step_type},
            )
        )

    await append_event(
        make_event(
            asset_id=asset_id,
            workflow_run_id=run_id,
            workflow_step_id=step.step_id,
            event_type="agent.tool.called",
            actor="workflow_agent",
            payload={
                "name": "emit_finding",
                "args": {"count": len(findings)},
                "step_id": step.step_id,
                "step_type": step.step_type,
            },
        )
    )

    return findings


def _build_live_prompt(inputs: dict[str, Any]) -> str:
    inputs_block = json.dumps(inputs, sort_keys=True, indent=2) if inputs else "{}"
    return (
        "You are Praetor's governed compliance workflow agent running a "
        "code compliance scan. Read the workflow inputs and produce "
        "structured findings.\n\n"
        "Respond with a single JSON object inside a ```json fenced block "
        "with this shape:\n"
        "{\n"
        '  "thinking": "short auditable rationale (one paragraph max)",\n'
        '  "findings": [\n'
        "    {\n"
        '      "title": "short title",\n'
        '      "description": "two or three sentences",\n'
        '      "severity": "low | medium | high | critical",\n'
        '      "confidence": 0.0-1.0,\n'
        '      "obligations_cited": []\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "If the repository looks clean, return findings: [].\n\n"
        f"Workflow inputs:\n{inputs_block}"
    )


def _call_openai_responses(api_key: str, model: str, prompt: str) -> str:
    body = json.dumps({"model": model, "input": prompt}).encode("utf-8")
    request = Request(
        _OPENAI_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https host
        data = json.loads(response.read().decode("utf-8"))
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    parts: list[str] = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if isinstance(content, dict):
                text = content.get("text")
                if isinstance(text, str):
                    parts.append(text)
                elif isinstance(text, dict) and isinstance(text.get("value"), str):
                    parts.append(text["value"])
    return "".join(parts)


def _parse_response_text(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    match = _FENCE_RE.search(text)
    candidates: list[str] = []
    if match:
        candidates.append(match.group(1))
    candidates.append(text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _normalise_findings(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return out
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            continue
        severity = str(raw.get("severity") or "medium").lower()
        if severity not in {"low", "medium", "high", "critical"}:
            severity = "medium"
        try:
            confidence = float(raw.get("confidence", 0.7))
        except (TypeError, ValueError):
            confidence = 0.7
        confidence = max(0.0, min(1.0, confidence))
        out.append(
            {
                "id": str(raw.get("id") or f"fnd_live_{index + 1}"),
                "title": str(raw.get("title") or "Compliance finding")[:240],
                "description": str(raw.get("description") or "")[:1200],
                "severity": severity,
                "confidence": confidence,
                "obligations_cited": [
                    str(urn) for urn in (raw.get("obligations_cited") or []) if isinstance(urn, str)
                ],
                "documents_cited": raw.get("documents_cited") if isinstance(raw.get("documents_cited"), list) else [],
                "status": "open",
            }
        )
    return out


def _chunk_rationale(text: str, *, n: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if n <= 1 or len(text) <= 120:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) <= n:
        return [s for s in sentences if s]
    size = max(1, len(sentences) // n)
    chunks: list[str] = []
    for i in range(0, len(sentences), size):
        chunk = " ".join(sentences[i : i + size]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks[:n] if len(chunks) > n else chunks


# ─── Scripted runs ────────────────────────────────────────────────────────


def _thought(text: str, *, actor: str = "workflow_agent", delay: float = 1.6) -> ScriptedEvent:
    return ScriptedEvent(type="agent.thought", actor=actor, payload={"text": text}, delay_before=delay)


def _tool(name: str, *, args: dict[str, Any] | None = None, delay: float = 1.0) -> ScriptedEvent:
    return ScriptedEvent(
        type="agent.tool.called",
        actor="workflow_agent",
        payload={"name": name, "args": args or {}},
        delay_before=delay,
    )


def _hook_in(repo: str, *, delay: float = 1.4) -> ScriptedEvent:
    return ScriptedEvent(
        type="hook.in.called",
        actor="praetor:hooks",
        payload={"repo_url": repo, "summary": f"Pulled artefacts from {repo}."},
        delay_before=delay,
    )


def _corpus_query(query: str, corpus_id: str, chunks: int, *, delay: float = 1.6) -> ScriptedEvent:
    return ScriptedEvent(
        type="corpus.query.called",
        actor="praetor:corpus",
        payload={"corpus_id": corpus_id, "query": query, "chunks_returned": chunks, "top_score": 0.78},
        delay_before=delay,
    )


def _policy_decision(package: str, outcome: str, *, delay: float = 0.7) -> ScriptedEvent:
    return ScriptedEvent(
        type="policy.decision.hot",
        actor="praetor:policy",
        payload={"package": package, "outcome": outcome, "latency_ms": 4},
        delay_before=delay,
    )


def _human_gate(*, delay: float = 0.8) -> ScriptedEvent:
    return ScriptedEvent(
        type="human.gate.opened",
        actor="praetor:runtime",
        payload={"reason": "awaiting reviewer approval"},
        delay_before=delay,
    )


def _human_resolve(approver: str = "demo:reviewer", *, delay: float = 5.0) -> ScriptedEvent:
    return ScriptedEvent(
        type="human.gate.resolved",
        actor=approver,
        payload={"approved": True, "approver": approver},
        delay_before=delay,
    )


def _hook_out(target: str, *, delay: float = 1.5) -> ScriptedEvent:
    return ScriptedEvent(
        type="hook.out.called",
        actor="praetor:hooks",
        payload={"target": target, "ok": True},
        delay_before=delay,
    )


def _finding_emitted(finding: dict[str, Any], *, delay: float = 0.8) -> ScriptedEvent:
    return ScriptedEvent(
        type="finding.emitted",
        actor="workflow_runtime",
        payload={"finding": finding},
        delay_before=delay,
    )


def _change_proposed(proposal: dict[str, Any], *, delay: float = 1.0) -> ScriptedEvent:
    return ScriptedEvent(
        type="change.proposed",
        actor="workflow_runtime",
        payload={"proposed_change": proposal},
        delay_before=delay,
    )


def _f(
    *,
    fid: str,
    title: str,
    description: str,
    severity: str = "high",
    confidence: float = 0.85,
    obligations: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "id": fid,
        "urn": f"urn:praetor:finding:demo:{fid}",
        "title": title,
        "description": description,
        "severity": severity,
        "confidence": confidence,
        "obligations_cited": list(obligations),
        "documents_cited": [],
        "status": "open",
    }


def _p(*, pid: str, finding_id: str, kind: str, diff: str, residual: str = "Low") -> dict[str, Any]:
    return {
        "id": pid,
        "urn": f"urn:praetor:proposed_change:demo:{pid}",
        "finding_id": finding_id,
        "kind": kind,
        "diff_format": "unified" if kind == "code" else "markdown",
        "diff": diff,
        "obligations_addressed": [],
        "residual_risk_estimate": residual,
        "status": "proposed",
    }


_SCAN_F = _f(
    fid="fnd_send_email_guard",
    title="send_email lacks recipient domain validation",
    description="The send_email path forwards messages without checking the recipient domain against an allowlist.",
    severity="high",
    confidence=0.9,
    obligations=("urn:praetor:obligation:demo:iso-42001-8-3",),
)
_SCAN_P = _p(
    pid="pc_send_email_validator",
    finding_id="fnd_send_email_guard",
    kind="code",
    diff=(
        "--- a/tools.py\n"
        "+++ b/tools.py\n"
        "@@\n"
        "+ALLOWED = {'northwind.test', 'customer.example'}\n"
        " def send_email(recipient, subject, body):\n"
        "+    assert recipient.rsplit('@', 1)[-1] in ALLOWED\n"
        "     return smtp.send(recipient, subject, body)\n"
    ),
)


SCRIPTS: dict[str, ScriptedRun] = {
    "code_compliance_scan": ScriptedRun(
        workflow_id="code_compliance_scan",
        asset_id="asset_northwind_support_bot",
        steps=(
            ScriptedStep(
                step_id="pull",
                step_type="hook.in",
                events=(_hook_in("stub://support-bot"),),
                final_outputs={"repo_url": "stub://support-bot"},
            ),
            ScriptedStep(
                step_id="retrieve_controls",
                step_type="corpus.query",
                events=(_corpus_query("recipient domain validation", "iso_42001", chunks=3),),
                final_outputs={"chunks_returned": 3},
            ),
            ScriptedStep(
                step_id="scan",
                step_type="agent",
                events=(
                    _thought("Reading source files for outbound email primitives."),
                    _thought("send_email accepts arbitrary recipients with no allowlist check."),
                    _tool("emit_finding", args={"count": 1}),
                ),
                final_outputs={"findings": [_SCAN_F]},
                findings=(_SCAN_F,),
            ),
            ScriptedStep(
                step_id="emit",
                step_type="finding.emit",
                events=(_finding_emitted(_SCAN_F),),
                final_outputs={"emitted": [_SCAN_F]},
            ),
        ),
    ),
    "code_compliance_scan_full": ScriptedRun(
        workflow_id="code_compliance_scan_full",
        asset_id="asset_northwind_support_bot",
        steps=(
            ScriptedStep(
                step_id="pull",
                step_type="hook.in",
                events=(_hook_in("stub://support-bot"),),
                final_outputs={"repo_url": "stub://support-bot"},
            ),
            ScriptedStep(
                step_id="retrieve_controls",
                step_type="corpus.query",
                events=(_corpus_query("recipient domain validation", "iso_42001", chunks=3),),
                final_outputs={"chunks_returned": 3},
            ),
            ScriptedStep(
                step_id="scan",
                step_type="agent",
                events=(
                    _thought("Inspecting outbound integrations and policy obligations."),
                    _thought("send_email is missing the recipient-domain guard required by ISO 42001 §8.3."),
                    _tool("emit_finding", args={"count": 1}),
                ),
                final_outputs={"findings": [_SCAN_F]},
                findings=(_SCAN_F,),
                is_live_agent=True,
            ),
            ScriptedStep(
                step_id="emit",
                step_type="finding.emit",
                events=(_finding_emitted(_SCAN_F),),
                final_outputs={"emitted": [_SCAN_F]},
            ),
            ScriptedStep(
                step_id="propose",
                step_type="change.propose",
                events=(_change_proposed(_SCAN_P),),
                final_outputs={"proposed": [_SCAN_P]},
                proposals=(_SCAN_P,),
            ),
            ScriptedStep(
                step_id="policy_gate",
                step_type="gate.policy",
                events=(_policy_decision("praetor.controls.workflow_findings_gate", "allow"),),
                final_outputs={"outcome": "allow"},
            ),
            ScriptedStep(
                step_id="human_gate",
                step_type="gate.human",
                events=(_human_gate(), _human_resolve(delay=4.0)),
                final_outputs={"approved": True},
            ),
            ScriptedStep(
                step_id="open_pr",
                step_type="hook.out",
                events=(_hook_out("github_stub#open_pr"),),
                final_outputs={"pr_url": "https://github.example/northwind/support-bot/pull/42"},
            ),
        ),
    ),
    "vendor_risk_review": ScriptedRun(
        workflow_id="vendor_risk_review",
        asset_id="asset_acme_vendor",
        steps=(
            ScriptedStep(
                step_id="load_attestation",
                step_type="hook.in",
                events=(_hook_in("stub://acme-soc2-attestation"),),
                final_outputs={"document": "soc2-2026-q1.pdf"},
            ),
            ScriptedStep(
                step_id="retrieve_obligations",
                step_type="corpus.query",
                events=(_corpus_query("SOC2 access control gaps", "iso_42001", chunks=4),),
                final_outputs={"chunks_returned": 4},
            ),
            ScriptedStep(
                step_id="analyze",
                step_type="agent",
                events=(
                    _thought("Cross-checking Acme's SOC2 controls against ISO 42001."),
                    _thought("CC6.1 access logging is partial; A.9.4.5 lacks segregation evidence."),
                    _tool("cite_obligation", args={"count": 2}),
                    _tool("emit_finding", args={"count": 2}),
                ),
                final_outputs={"findings_count": 2},
                findings=(
                    _f(
                        fid="fnd_acme_cc61",
                        title="Acme SOC2 CC6.1 — partial access logging",
                        description="Acme's evidence does not cover privileged user access. Request a remediation plan.",
                        severity="high",
                        confidence=0.82,
                        obligations=("urn:praetor:obligation:demo:soc2-cc6-1",),
                    ),
                    _f(
                        fid="fnd_acme_a945",
                        title="ISO 27001 A.9.4.5 segregation evidence missing",
                        description="No artefact demonstrates code-environment segregation for production releases.",
                        severity="medium",
                        confidence=0.74,
                        obligations=("urn:praetor:obligation:demo:iso-27001-a945",),
                    ),
                ),
            ),
            ScriptedStep(
                step_id="emit",
                step_type="finding.emit",
                events=(),
                final_outputs={"emitted_count": 2},
            ),
            ScriptedStep(
                step_id="propose_remediation",
                step_type="change.propose",
                events=(),
                final_outputs={"proposed_count": 1},
                proposals=(
                    _p(
                        pid="pc_acme_remediation",
                        finding_id="fnd_acme_cc61",
                        kind="process",
                        diff="Request a 30-day remediation plan covering CC6.1 access logging gaps; require evidence by next quarter's review.",
                        residual="Medium until evidence is supplied.",
                    ),
                ),
            ),
        ),
    ),
    "policy_gap_analysis": ScriptedRun(
        workflow_id="policy_gap_analysis",
        asset_id="asset_policy_corpus",
        steps=(
            ScriptedStep(
                step_id="load_regulation",
                step_type="hook.in",
                events=(_hook_in("stub://eu-ai-act-art10"),),
                final_outputs={"regulation": "eu_ai_act_art_10"},
            ),
            ScriptedStep(
                step_id="retrieve_existing_controls",
                step_type="corpus.query",
                events=(_corpus_query("data governance training data quality", "internal_data_min", chunks=5),),
                final_outputs={"chunks_returned": 5},
            ),
            ScriptedStep(
                step_id="analyze_gaps",
                step_type="agent",
                events=(
                    _thought("Mapping existing controls onto AI Act Article 10 obligations."),
                    _thought("Existing controls cover bias monitoring; data lineage attestation is missing."),
                    _tool("emit_finding", args={"count": 1}),
                ),
                final_outputs={"gaps": 1},
                findings=(
                    _f(
                        fid="fnd_eu_ai_act_lineage",
                        title="No data-lineage attestation for training datasets",
                        description="Article 10(2)(f) requires data lineage. Internal controls cover bias but not lineage attestation.",
                        severity="high",
                        confidence=0.81,
                        obligations=("urn:praetor:obligation:demo:eu-ai-act-art10",),
                    ),
                ),
            ),
            ScriptedStep(
                step_id="emit",
                step_type="finding.emit",
                events=(),
                final_outputs={"emitted_count": 1},
            ),
            ScriptedStep(
                step_id="propose_controls",
                step_type="change.propose",
                events=(),
                final_outputs={"proposed_count": 1},
                proposals=(
                    _p(
                        pid="pc_data_lineage_control",
                        finding_id="fnd_eu_ai_act_lineage",
                        kind="policy",
                        diff="## Control: Training-Data Lineage Attestation\n\nEvery training dataset MUST carry a signed lineage attestation linking source systems, transformation steps, and consent basis.",
                    ),
                ),
            ),
            ScriptedStep(
                step_id="policy_gate",
                step_type="gate.policy",
                events=(_policy_decision("praetor.controls.policy_gate", "allow"),),
                final_outputs={"outcome": "allow"},
            ),
            ScriptedStep(
                step_id="human_gate",
                step_type="gate.human",
                events=(_human_gate(), _human_resolve(delay=4.0)),
                final_outputs={"approved": True},
            ),
        ),
    ),
    "evidence_collection": ScriptedRun(
        workflow_id="evidence_collection",
        asset_id="asset_evidence_q1",
        steps=(
            ScriptedStep(
                step_id="read_files",
                step_type="hook.in",
                events=(_hook_in("stub://evidence-bundle-q1"),),
                final_outputs={"files": 14},
            ),
            ScriptedStep(
                step_id="retrieve_obligations",
                step_type="corpus.query",
                events=(_corpus_query("ISO 42001 evidence requirements", "iso_42001", chunks=4),),
                final_outputs={"chunks_returned": 4},
            ),
            ScriptedStep(
                step_id="organize",
                step_type="agent",
                events=(
                    _thought("Sorting raw artefacts by obligation URN."),
                    _thought("6 evidence records bound; 8 artefacts uncategorised — flagged for review."),
                    _tool("bind_evidence", args={"bound": 6, "unbound": 8}),
                ),
                final_outputs={"records_created": 6},
            ),
            ScriptedStep(
                step_id="emit",
                step_type="finding.emit",
                events=(),
                final_outputs={"emitted_count": 0},
            ),
        ),
    ),
    "ai_system_intake": ScriptedRun(
        workflow_id="ai_system_intake",
        asset_id="asset_chat_summary_v2",
        steps=(
            ScriptedStep(
                step_id="intake_form",
                step_type="hook.in",
                events=(_hook_in("stub://intake/chat-summary-v2"),),
                final_outputs={"form_id": "intake_chat_summary_v2"},
            ),
            ScriptedStep(
                step_id="retrieve_obligations",
                step_type="corpus.query",
                events=(_corpus_query("AI system risk classification", "iso_42001", chunks=3),),
                final_outputs={"chunks_returned": 3},
            ),
            ScriptedStep(
                step_id="classify",
                step_type="agent",
                events=(
                    _thought("Reviewing intake form against AI Act risk categories."),
                    _thought("Customer-facing summary tool with PII access — classified high-risk."),
                    _tool("emit_finding", args={"count": 1}),
                ),
                final_outputs={"classification": "high-risk"},
                findings=(
                    _f(
                        fid="fnd_chat_summary_classification",
                        title="Chat-summary v2 classified high-risk",
                        description="Customer-facing summarisation that accesses PII. Subject to AI Act high-risk obligations (Annex III).",
                        severity="high",
                        confidence=0.88,
                        obligations=("urn:praetor:obligation:demo:eu-ai-act-annex-iii",),
                    ),
                ),
            ),
            ScriptedStep(
                step_id="policy_gate",
                step_type="gate.policy",
                events=(_policy_decision("praetor.controls.intake_gate", "permit_with_conditions"),),
                final_outputs={"outcome": "permit_with_conditions"},
            ),
            ScriptedStep(
                step_id="emit",
                step_type="finding.emit",
                events=(),
                final_outputs={"emitted_count": 1},
            ),
        ),
    ),
}
