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
