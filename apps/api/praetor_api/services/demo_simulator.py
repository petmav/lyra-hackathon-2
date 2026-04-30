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
import os
import re
from collections.abc import Awaitable, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from praetor_api.services.event_stream import append_event, make_event

logger = logging.getLogger(__name__)

SleepFn = Callable[[float], Awaitable[None]]


# ─── GitHub repo fetch (live mode) ────────────────────────────────────────
# When a run is instantiated with `inputs.repo = "owner/name"` AND a
# GITHUB_TOKEN is present in the API process env, the `pull` step actually
# downloads the repo's tarball and caches a slice of source files keyed by
# run_id. The `scan` step's prompt builder reads those files so the live
# OpenAI call reasons over real code.

_REPO_CACHE: dict[str, dict[str, Any]] = {}

_REPO_TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs",
    ".go", ".rs", ".java", ".kt", ".rb", ".php",
    ".c", ".cc", ".cpp", ".cs",
    ".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".ini", ".env", ".example",
}
_REPO_SKIP_PARTS = {".git", "node_modules", ".next", "dist", "build", "__pycache__", "vendor", ".venv", "venv"}
_REPO_MAX_FILE_BYTES = 64 * 1024
_REPO_MAX_FILES = 30


def _parse_repo_input(inputs: dict[str, Any]) -> tuple[str, str, str] | None:
    """Pull `(owner, repo, ref)` out of run inputs.

    Accepts:
    - `inputs.github = {owner, repo, ref}` (canonical)
    - `inputs.repo = "owner/name"` (short form)
    - `inputs.repo_url = "https://github.com/owner/name"` (form default)
    """
    gh = inputs.get("github") if isinstance(inputs.get("github"), dict) else None
    if gh:
        owner = str(gh.get("owner") or "").strip()
        repo = str(gh.get("repo") or "").strip().removesuffix(".git")
        ref = str(gh.get("ref") or "main").strip() or "main"
        if owner and repo:
            return owner, repo, ref

    raw = str(inputs.get("repo") or inputs.get("repo_url") or "").strip()
    if not raw or raw.startswith("stub://"):
        return None
    raw = (
        raw.removesuffix(".git")
        .removeprefix("https://github.com/")
        .removeprefix("http://github.com/")
        .removeprefix("git@github.com:")
        .strip("/")
    )
    parts = raw.split("/")
    if len(parts) < 2:
        return None
    owner, repo = parts[0].strip(), parts[1].strip()
    ref = (
        str(inputs.get("ref") or inputs.get("github_ref") or "main").strip()
        or "main"
    )
    if not owner or not repo:
        return None
    return owner, repo, ref


def _fetch_github_repo(owner: str, repo: str, ref: str, token: str) -> dict[str, Any]:
    """Synchronously download a GitHub tarball and extract a small slice of
    text files. Returns `{owner, repo, ref, files: [{path, text}], bytes}`."""
    import io
    import tarfile

    url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{ref}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "praetor-demo-simulator",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }
    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=45) as response:  # noqa: S310
        tar_bytes = response.read()

    files: list[dict[str, str]] = []
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isreg():
                continue
            parts = member.name.split("/", 1)
            relative = parts[1] if len(parts) > 1 else parts[0]
            if not relative:
                continue
            path = relative
            path_parts = path.split("/")
            if any(p in _REPO_SKIP_PARTS for p in path_parts):
                continue
            suffix = "." + path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
            if suffix not in _REPO_TEXT_SUFFIXES:
                continue
            if member.size > _REPO_MAX_FILE_BYTES:
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                continue
            try:
                text = extracted.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                continue
            files.append({"path": path, "text": text})
            if len(files) >= _REPO_MAX_FILES:
                break

    return {
        "owner": owner,
        "repo": repo,
        "ref": ref,
        "files": files,
        "bytes": len(tar_bytes),
    }


# ─── human-gate pause registry ────────────────────────────────────────────
# Per-run asyncio.Event used by `tick_run` to block on a `gate.human` step
# until the API receives `POST /workflow-runs/{id}:resume`. The router
# imports `signal_resume` to flip the event.

_GATE_EVENTS: dict[str, asyncio.Event] = {}
_GATE_DECISIONS: dict[str, bool] = {}


def signal_resume(run_id: str, *, approved: bool) -> bool:
    """Mark the run's pending human gate as resolved. Returns True if a
    matching pause was registered, False otherwise."""
    event = _GATE_EVENTS.get(run_id)
    if event is None:
        return False
    _GATE_DECISIONS[run_id] = approved
    event.set()
    return True


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

    # Best-effort live GitHub pull: only on workflows that have a `pull`
    # step and only when both a token and a parseable repo input exist.
    github_token = os.environ.get("GITHUB_TOKEN")
    repo_target = _parse_repo_input(run.get("inputs") or {})
    if (
        github_token
        and repo_target
        and any(s.step_id == "pull" for s in script.steps)
    ):
        try:
            fetched = await asyncio.to_thread(
                _fetch_github_repo, *repo_target, github_token
            )
            _REPO_CACHE[run_id] = fetched
            logger.info(
                "live github pull for %s: %s/%s@%s — %d files, %d bytes",
                run_id, fetched["owner"], fetched["repo"], fetched["ref"],
                len(fetched["files"]), fetched["bytes"],
            )
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            logger.warning(
                "github pull failed for %s (%s); falling back to scripted: %s",
                run_id, repo_target, exc,
            )

    def _agent_asset_id(step: ScriptedStep) -> str:
        """Per-step workflow_agent asset id.

        The workflow-run page synthesises an asset for each agent step
        (`asset_wfa_<run>_<step>`) and the SelfGovernancePanel queries
        events by that id. Tag agent in-step events with it so the
        three-pane panel actually shows thoughts / tools / memory.
        """
        return f"asset_wfa_{run_id}_{step.step_id}"

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

            # Human gate: pause the run, wait for the API to signal resume.
            if step.step_type == "gate.human":
                step_record["status"] = "awaiting_approval"
                run["status"] = "awaiting_approval"
                run["updated_at"] = _iso_now()
                await append_event(
                    make_event(
                        asset_id=asset_id,
                        workflow_run_id=run_id,
                        workflow_step_id=step.step_id,
                        event_type="human.gate.opened",
                        actor="praetor:runtime",
                        payload={
                            "reason": "awaiting reviewer approval",
                            "step_id": step.step_id,
                            "step_type": step.step_type,
                        },
                    )
                )
                event = asyncio.Event()
                _GATE_EVENTS[run_id] = event
                try:
                    await event.wait()
                finally:
                    _GATE_EVENTS.pop(run_id, None)
                approved = _GATE_DECISIONS.pop(run_id, True)
                run["status"] = "running"
                step_record["status"] = "succeeded" if approved else "failed"
                run["updated_at"] = _iso_now()
                await append_event(
                    make_event(
                        asset_id=asset_id,
                        workflow_run_id=run_id,
                        workflow_step_id=step.step_id,
                        event_type="human.gate.resolved",
                        actor="demo:reviewer",
                        payload={
                            "approved": approved,
                            "approver": "demo:reviewer",
                            "step_id": step.step_id,
                            "step_type": step.step_type,
                        },
                    )
                )
                step_record["outputs_redacted"] = {"approved": approved}
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
                            "status": step_record["status"],
                            "outputs_redacted": step_record["outputs_redacted"],
                        },
                    )
                )
                if not approved:
                    run["status"] = "cancelled"
                    run["finished_at"] = _iso_now()
                    run["updated_at"] = run["finished_at"]
                    await append_event(
                        make_event(
                            asset_id=asset_id,
                            workflow_run_id=run_id,
                            event_type="workflow.run.finished",
                            actor="workflow_runtime",
                            payload={"status": "cancelled"},
                        )
                    )
                    return
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
                    asset_id=_agent_asset_id(step),
                    run_id=run_id,
                    step=step,
                    inputs=run.get("inputs", {}),
                    model=str(run.get("model") or "gpt-4o-mini"),
                    openai_api_key=openai_api_key,
                    sleep=sleep,
                )

            # Live propose step: when the run already has live findings
            # carrying file_path + proposed_change, surface a real-looking
            # proposed change instead of the scripted patch.
            if step.step_type == "change.propose":
                live_proposals = _live_proposals_from_run(run)
                if live_proposals:
                    await sleep(1.0)
                    for proposal in live_proposals:
                        await append_event(
                            make_event(
                                asset_id=asset_id,
                                workflow_run_id=run_id,
                                workflow_step_id=step.step_id,
                                event_type="change.proposed",
                                actor="workflow_runtime",
                                payload={
                                    "proposed_change": proposal,
                                    "step_id": step.step_id,
                                    "step_type": step.step_type,
                                },
                            )
                        )
                    step_record["outputs_redacted"] = {
                        "proposed": list(live_proposals),
                        "live": True,
                    }
                    run.setdefault("outputs", {}).setdefault(
                        "proposed_changes", []
                    ).extend(live_proposals)
                    step_record["status"] = "succeeded"
                    run["updated_at"] = _iso_now()
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
                    continue

            # Live hook.out (open_pr) step: emit a real-looking URL
            # tied to the fetched repo instead of the hardcoded fake.
            if (
                step.step_type == "hook.out"
                and run_id in _REPO_CACHE
            ):
                fetched = _REPO_CACHE[run_id]
                pr_number = abs(hash(run_id)) % 9000 + 1000
                pr_url = (
                    f"https://github.com/{fetched['owner']}/{fetched['repo']}/pull/{pr_number}"
                )
                await sleep(1.0)
                await append_event(
                    make_event(
                        asset_id=asset_id,
                        workflow_run_id=run_id,
                        workflow_step_id=step.step_id,
                        event_type="hook.out.called",
                        actor="praetor:hooks",
                        payload={
                            "target": f"github://{fetched['owner']}/{fetched['repo']}#open_pr",
                            "pr_url": pr_url,
                            "ok": True,
                            "note": (
                                "Demo: PR not actually pushed (read-only token). "
                                "URL points at the live repo for review only."
                            ),
                            "step_id": step.step_id,
                            "step_type": step.step_type,
                        },
                    )
                )
                step_record["outputs_redacted"] = {
                    "pr_url": pr_url,
                    "live": True,
                    "note": "Demo open_pr surface — no actual PR pushed.",
                }
                step_record["status"] = "succeeded"
                run["updated_at"] = _iso_now()
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
                continue

            # Live pull step: replace the scripted hook.in.called with a
            # real summary of the fetched repo when available.
            if (
                step.step_id == "pull"
                and step.step_type == "hook.in"
                and run_id in _REPO_CACHE
            ):
                fetched = _REPO_CACHE[run_id]
                await sleep(0.8)
                await append_event(
                    make_event(
                        asset_id=asset_id,
                        workflow_run_id=run_id,
                        workflow_step_id=step.step_id,
                        event_type="hook.in.called",
                        actor="praetor:hooks",
                        payload={
                            "repo_url": f"https://github.com/{fetched['owner']}/{fetched['repo']}",
                            "ref": fetched["ref"],
                            "files_fetched": len(fetched["files"]),
                            "bytes": fetched["bytes"],
                            "summary": (
                                f"Pulled {len(fetched['files'])} source files "
                                f"from {fetched['owner']}/{fetched['repo']}@{fetched['ref']}."
                            ),
                            "step_id": step.step_id,
                            "step_type": step.step_type,
                        },
                    )
                )
                step_record["outputs_redacted"] = {
                    "repo_url": f"https://github.com/{fetched['owner']}/{fetched['repo']}",
                    "ref": fetched["ref"],
                    "files_fetched": len(fetched["files"]),
                    "bytes": fetched["bytes"],
                    "live": True,
                }
                step_record["status"] = "succeeded"
                run["updated_at"] = _iso_now()
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
                continue

            if live_findings is None:
                if not step.events:
                    # Steps with no scripted in-step events still get a small
                    # dwell so the DAG visibly progresses.
                    await sleep(0.8)
                for scripted in step.events:
                    if scripted.delay_before > 0:
                        await sleep(scripted.delay_before)
                    # Agent in-step events are tagged with the workflow_agent
                    # asset id so the three-pane SelfGovernancePanel renders
                    # them; everything else stays on the run's main asset.
                    event_asset_id = (
                        _agent_asset_id(step)
                        if step.step_type == "agent"
                        and scripted.type.startswith(("agent.", "sandbox."))
                        else asset_id
                    )
                    await append_event(
                        make_event(
                            asset_id=event_asset_id,
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

            if step.step_type == "agent":
                # Surface the workflow_agent asset id on the step so
                # workflowAgentFromRun on the run page renders the
                # SelfGovernancePanel against the right asset.
                wfa_id = _agent_asset_id(step)
                step_record["outputs_redacted"]["workflow_agent_asset_id"] = wfa_id
                step_record["outputs_redacted"]["workflow_agent_asset_urn"] = (
                    f"urn:praetor:asset:workflow_agent:{run_id}:{step.step_id}"
                )

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
        _REPO_CACHE.pop(run_id, None)

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
        _REPO_CACHE.pop(run_id, None)


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
    prompt = _build_live_prompt(inputs, run_id=run_id)
    logger.info("live OpenAI call starting for %s model=%s", run_id, model)
    try:
        text = await asyncio.to_thread(_call_openai_responses, openai_api_key, model, prompt)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("live OpenAI call failed for %s: %s: %s", run_id, exc.__class__.__name__, exc)
        return None

    parsed = _parse_response_text(text)
    if not parsed:
        logger.warning("live OpenAI parse failed for %s; raw start: %r", run_id, text[:200])
        return None

    rationale = str(parsed.get("thinking") or text).strip()
    findings = _normalise_findings(parsed.get("findings"))
    logger.info(
        "live OpenAI for %s: rationale=%d chars, %d findings",
        run_id, len(rationale), len(findings),
    )
    if not findings:
        # Model produced live thinking but no findings (often because the
        # demo prompt is thin). Surface the scripted finding so the run
        # still shows a complete remediation flow, but keep the live
        # rationale so thoughts are recognisably model-written.
        findings = [dict(f) for f in step.findings]

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


_LIVE_PROMPT_FILE_BUDGET = 12_000  # chars; conservative for gpt-4o-mini context
_LIVE_PROMPT_PER_FILE_CHARS = 1500


def _format_repo_excerpt(fetched: dict[str, Any]) -> str:
    """Pick a few likely-interesting source files from the fetched repo and
    fence them so they fit comfortably in the prompt."""
    files = fetched.get("files", []) or []
    # Prefer source files over docs/configs.
    code_suffixes = {".py", ".ts", ".tsx", ".js", ".go", ".rs", ".java", ".rb", ".php"}

    def score(f: dict[str, Any]) -> tuple[int, int]:
        path = f.get("path", "")
        suffix = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        is_code = 0 if suffix in code_suffixes else 1
        # shorter paths first within their tier so we get top-level files
        return (is_code, len(path))

    ordered = sorted(files, key=score)
    used = 0
    blocks: list[str] = []
    for f in ordered:
        text = f.get("text", "") or ""
        slice_ = text[:_LIVE_PROMPT_PER_FILE_CHARS]
        if not slice_.strip():
            continue
        block = f"--- {f['path']} ---\n{slice_}"
        if used + len(block) > _LIVE_PROMPT_FILE_BUDGET:
            break
        blocks.append(block)
        used += len(block)
        if len(blocks) >= 8:
            break
    if not blocks:
        return ""
    header = (
        f"Repository: {fetched['owner']}/{fetched['repo']}@{fetched['ref']} "
        f"({len(files)} files, {fetched.get('bytes', 0)} bytes downloaded). "
        f"Source excerpt:\n"
    )
    return header + "\n\n".join(blocks)


def _build_live_prompt(inputs: dict[str, Any], *, run_id: str | None = None) -> str:
    inputs_block = json.dumps(inputs, sort_keys=True, indent=2) if inputs else "{}"
    fetched = _REPO_CACHE.get(run_id) if run_id else None
    repo_excerpt = _format_repo_excerpt(fetched) if fetched else ""

    if repo_excerpt:
        return (
            "You are Praetor's governed compliance workflow agent running a "
            "code compliance scan against the repository below. The files "
            "are real source pulled from GitHub via authenticated download.\n\n"
            f"{repo_excerpt}\n\n"
            "Relevant obligations:\n"
            "- ISO 42001 §8.3: Outbound communication primitives MUST validate "
            "the recipient against an allowlist before transmission.\n"
            "- Internal data-minimization policy: privileged tools MUST log a "
            "structured audit record per call.\n"
            "- OWASP A03 Injection: untrusted input must never reach `eval`, "
            "`exec`, `shell=True`, or unparameterised SQL.\n"
            "- Hardcoded secrets policy: never commit API keys, passwords, or "
            "tokens; always source from a managed secret store.\n\n"
            "Identify concrete compliance findings in this repository. Cite "
            "the relevant obligation by URN (e.g. "
            "`urn:praetor:obligation:demo:iso-42001-8-3`) and reference the "
            "exact file path + line range when describing each finding. If you "
            "see a remediation, propose a concrete change in the "
            "`proposed_change` field.\n\n"
            "Respond with a single JSON object inside a ```json fenced block:\n"
            "{\n"
            '  "thinking": "one-paragraph auditable rationale",\n'
            '  "findings": [\n'
            "    {\n"
            '      "title": "short title",\n'
            '      "description": "what is wrong, where, and why it violates the obligation",\n'
            '      "severity": "low | medium | high | critical",\n'
            '      "confidence": 0.0-1.0,\n'
            '      "obligations_cited": ["urn:praetor:obligation:demo:..."],\n'
            '      "file_path": "relative path",\n'
            '      "proposed_change": "short suggested patch or remediation"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"Workflow inputs:\n{inputs_block}"
        )

    # Fallback: no repo fetched (no token or no inputs.repo). Use the
    # synthetic Northwind example so the demo still produces real findings.
    return (
        "You are Praetor's governed compliance workflow agent running a "
        "code compliance scan against a small support-bot repository.\n\n"
        "Repository excerpt (`tools.py`):\n"
        "```python\n"
        "def send_email(recipient, subject, body):\n"
        "    # send an email through the configured SMTP relay\n"
        "    return smtp.send(recipient, subject, body)\n"
        "\n"
        "def issue_refund(customer_id, amount):\n"
        "    if amount > 1000:\n"
        "        raise ValueError('refund cap exceeded')\n"
        "    return billing.refund(customer_id, amount)\n"
        "```\n\n"
        "Relevant obligations:\n"
        "- ISO 42001 §8.3: Outbound communication primitives MUST validate "
        "the recipient against an allowlist before transmission.\n"
        "- Internal data-minimization policy: privileged tools MUST log a "
        "structured audit record per call.\n\n"
        "Identify any compliance gaps. Cite the relevant obligation by URN. "
        "Be specific about which line(s) violate which obligation.\n\n"
        "Respond with a single JSON object inside a ```json fenced block:\n"
        "{\n"
        '  "thinking": "one-paragraph rationale",\n'
        '  "findings": [\n'
        "    {\n"
        '      "title": "short title",\n'
        '      "description": "two or three sentences",\n'
        '      "severity": "low | medium | high | critical",\n'
        '      "confidence": 0.0-1.0,\n'
        '      "obligations_cited": ["urn:praetor:obligation:demo:..."]\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
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
        record = {
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
        if isinstance(raw.get("file_path"), str) and raw["file_path"].strip():
            record["file_path"] = raw["file_path"].strip()[:240]
        if isinstance(raw.get("proposed_change"), str) and raw["proposed_change"].strip():
            record["proposed_change"] = raw["proposed_change"].strip()[:1500]
        out.append(record)
    return out


def _live_proposals_from_run(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Build proposed_change records from any live findings on the run that
    carry `file_path` + `proposed_change`. Returns [] when none qualify."""
    findings = (run.get("outputs") or {}).get("findings") or []
    proposals: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        change_text = finding.get("proposed_change")
        file_path = finding.get("file_path")
        if not isinstance(change_text, str) or not change_text.strip():
            continue
        if not isinstance(file_path, str) or not file_path.strip():
            continue
        pid = f"pc_live_{finding.get('id', 'finding')}"[:120]
        diff_body = (
            f"--- a/{file_path}\n"
            f"+++ b/{file_path}\n"
            f"@@ remediation suggestion @@\n"
            + "\n".join(f"+ {line}" for line in change_text.splitlines() if line.strip())
        )
        proposals.append(
            {
                "id": pid,
                "urn": f"urn:praetor:proposed_change:demo:{pid}",
                "finding_id": finding.get("id"),
                "kind": "code",
                "diff_format": "unified",
                "diff": diff_body,
                "obligations_addressed": list(finding.get("obligations_cited") or []),
                "residual_risk_estimate": "Medium until reviewed and merged.",
                "status": "proposed",
                "live": True,
            }
        )
    return proposals


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


def _memory(key: str, *, taint: float = 0.05, provenance: str = "corpus", delay: float = 0.8) -> ScriptedEvent:
    return ScriptedEvent(
        type="agent.memory.write",
        actor="workflow_agent",
        payload={"key": key, "taint_score": taint, "provenance": provenance},
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
                    _memory("source.tools.send_email", provenance="repo://support-bot/tools.py"),
                    _thought("send_email accepts arbitrary recipients with no allowlist check."),
                    _memory("obligation.iso-42001-8-3", taint=0.0, provenance="corpus://iso_42001#8.3"),
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
                    _memory("source.tools.send_email", provenance="repo://support-bot/tools.py"),
                    _thought("send_email is missing the recipient-domain guard required by ISO 42001 §8.3."),
                    _memory("obligation.iso-42001-8-3", taint=0.0, provenance="corpus://iso_42001#8.3"),
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
                    _memory("vendor.acme.soc2.cc6-1", provenance="hook://acme-attestation"),
                    _thought("CC6.1 access logging is partial; A.9.4.5 lacks segregation evidence."),
                    _memory("vendor.acme.iso27001.a945", provenance="corpus://iso_42001"),
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
                    _memory("regulation.eu_ai_act.art10", provenance="corpus://eu-ai-act"),
                    _thought("Existing controls cover bias monitoring; data lineage attestation is missing."),
                    _memory("control.gap.data_lineage", provenance="corpus://internal_data_min"),
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
                    _memory("evidence.q1.bundle", provenance="hook://evidence-q1"),
                    _thought("6 evidence records bound; 8 artefacts uncategorised — flagged for review."),
                    _memory("evidence.q1.bound_count", provenance="agent.organize"),
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
                    _memory("intake.chat-summary-v2.form", provenance="hook://intake"),
                    _thought("Customer-facing summary tool with PII access — classified high-risk."),
                    _memory("classification.high-risk", provenance="agent.classify"),
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
