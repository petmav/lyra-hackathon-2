"""Sandboxed agent harness.

Runs as the entrypoint of a Docker step container. Reads a manifest from
``PRAETOR_AGENT_MANIFEST_JSON`` (workflow context, prior step outputs, attached
documents, expected finding shape) and emits a structured ``agent_step_output``
dict back to the orchestrator via the ``PRAETOR_AGENT_STEP_OUTPUT=`` marker.

Two execution modes:

- **live**: when ``PRAETOR_AGENT_MODEL_MODE`` is ``live`` (or ``auto`` with a
  configured key) and the relevant provider key is present, the harness
  constructs a structured prompt and calls the model provider's API directly.
  The model is asked to return a JSON document with ``findings`` and a
  ``thinking`` rationale; we parse it, fall back to the deterministic stub if
  the call fails or the response is malformed.
- **deterministic stub**: the legacy fallback. Echoes the ``expected_finding``
  pre-computed by the workflow runtime and emits the standard tool-call
  envelope. Used when no key is configured, the mode forbids live calls, or
  the live path raises.

Live calls go through ``urllib`` to keep the sandbox image dependency-free.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MARKER = "PRAETOR_AGENT_STEP_OUTPUT="
DEFAULT_TIMEOUT = 30
MAX_PROMPT_DOCS = 6
MAX_DOC_CHARS = 4000
MAX_PRIOR_STEPS = 8


def main() -> None:
    payload = _manifest_payload()
    provider = str(payload.get("model_provider") or os.getenv("PRAETOR_MODEL_PROVIDER") or "openai").lower()
    model = str(payload.get("model") or os.getenv("PRAETOR_MODEL") or "gpt-4o-mini")
    mode = str(os.getenv("PRAETOR_AGENT_MODEL_MODE") or "auto").lower()
    api_key = _provider_key(provider)

    if _should_attempt_live(mode, api_key):
        live_output = _try_live(provider, model, payload, api_key)
        if live_output is not None:
            _emit(live_output)
            return

    _emit(_stub_output(payload, provider, model))


def _emit(output: dict[str, Any]) -> None:
    print("praetor sandbox agent harness completed", flush=True)
    print(f"{MARKER}{json.dumps(output, sort_keys=True)}", flush=True)


def _should_attempt_live(mode: str, api_key: str | None) -> bool:
    if not api_key:
        return False
    if mode == "live":
        return True
    if mode == "auto":
        return True
    return False


def _provider_key(provider: str) -> str | None:
    env_name = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
    }.get(provider)
    if not env_name:
        return None
    value = os.getenv(env_name)
    return value if value and value.strip() else None


# ─── live path ────────────────────────────────────────────────────────────

def _try_live(provider: str, model: str, payload: dict[str, Any], api_key: str) -> dict[str, Any] | None:
    try:
        prompt = _build_prompt(payload)
        if provider == "openai":
            raw = _call_openai(api_key, model, prompt)
        elif provider == "anthropic":
            raw = _call_anthropic(api_key, model, prompt)
        elif provider == "google":
            raw = _call_google(api_key, model, prompt)
        else:
            return None
        text = raw.get("text") or ""
        parsed = _parse_model_output(text)
        if parsed is None:
            return None
        findings = _normalize_findings(parsed.get("findings"), payload)
        thinking = str(parsed.get("thinking") or "").strip() or text.strip()[:600]
        return {
            "ok": True,
            "model_provider": provider,
            "model": model,
            "model_call": {
                "ok": True,
                "mode": "sandbox_live",
                "provider": provider,
                "model": model,
                "configured": True,
                "text": thinking,
                "usage": raw.get("usage", {}),
            },
            "findings": findings,
            "tools": [
                {"name": "corpus_query", "status": "ok", "items": _document_count(payload)},
                {"name": "cite_obligation", "status": "ok", "items": _obligation_count(findings)},
                {"name": "emit_finding", "status": "ok", "items": len(findings)},
            ],
            "memory_writes": [
                {
                    "key": f"{payload.get('workflow_run_id', 'workflow')}:{payload.get('step_id', 'agent')}:finding",
                    "provenance": "sandbox://agent_step:live",
                }
            ],
        }
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return None


def _build_prompt(payload: dict[str, Any]) -> str:
    workflow_inputs = payload.get("workflow_inputs", {}) or {}
    prior_steps = payload.get("prior_step_outputs", {}) or {}
    expected = payload.get("expected_finding", {}) or {}
    documents = payload.get("documents", []) or []

    context_blocks: list[str] = []

    if isinstance(workflow_inputs, dict) and workflow_inputs:
        context_blocks.append(
            "Workflow inputs:\n" + json.dumps(workflow_inputs, sort_keys=True, indent=2)
        )

    if isinstance(prior_steps, dict) and prior_steps:
        compact: dict[str, Any] = {}
        for step_id, step_output in list(prior_steps.items())[:MAX_PRIOR_STEPS]:
            compact[step_id] = _truncate(step_output, max_chars=2000)
        context_blocks.append(
            "Prior step outputs (truncated):\n" + json.dumps(compact, sort_keys=True, indent=2)
        )

    if isinstance(documents, list) and documents:
        excerpts: list[str] = []
        for doc in documents[:MAX_PROMPT_DOCS]:
            if not isinstance(doc, dict):
                continue
            title = str(doc.get("title") or doc.get("source_uri") or "document")
            text = _document_text(doc)[:MAX_DOC_CHARS]
            if not text.strip():
                continue
            excerpts.append(f"--- {title} ---\n{text}")
        if excerpts:
            context_blocks.append("Attached documents (truncated):\n" + "\n\n".join(excerpts))

    if isinstance(expected, dict) and expected:
        context_blocks.append(
            "Expected finding shape (use as schema reference, not content):\n"
            + json.dumps(expected, sort_keys=True, indent=2)
        )

    instructions = (
        "You are Praetor's governed compliance workflow agent running in a "
        "sandboxed step. Read the supplied workflow context and produce "
        "structured findings.\n\n"
        "Respond with a single JSON object inside a ```json fenced block "
        "with this shape:\n"
        "{\n"
        "  \"thinking\": \"short auditable rationale (one paragraph max)\",\n"
        "  \"findings\": [\n"
        "    {\n"
        "      \"title\": \"short title\",\n"
        "      \"description\": \"two or three sentences\",\n"
        "      \"severity\": \"low | medium | high | critical\",\n"
        "      \"confidence\": 0.0-1.0,\n"
        "      \"obligations_cited\": [\"urn:praetor:obligation:...\"],\n"
        "      \"documents_cited\": []\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Cite obligations from the workflow inputs or prior step outputs "
        "when relevant. If nothing is wrong, return findings: []."
    )
    return instructions + "\n\n" + "\n\n".join(context_blocks)


def _document_text(doc: dict[str, Any]) -> str:
    if isinstance(doc.get("text"), str):
        return doc["text"]
    parsed = doc.get("parsed_structure")
    if isinstance(parsed, dict) and isinstance(parsed.get("text"), str):
        return parsed["text"]
    if doc.get("base64"):
        try:
            import base64

            return base64.b64decode(str(doc["base64"]).encode("ascii")).decode("utf-8", errors="replace")
        except (ValueError, OSError):
            return ""
    return ""


def _document_count(payload: dict[str, Any]) -> int:
    docs = payload.get("documents")
    return len(docs) if isinstance(docs, list) else 0


def _obligation_count(findings: list[dict[str, Any]]) -> int:
    seen: set[str] = set()
    for finding in findings:
        for urn in finding.get("obligations_cited", []) or []:
            if isinstance(urn, str):
                seen.add(urn)
    return len(seen)


def _truncate(value: Any, *, max_chars: int) -> Any:
    encoded = json.dumps(value, sort_keys=True, default=str)
    if len(encoded) <= max_chars:
        return value
    return encoded[:max_chars] + "…"


_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _parse_model_output(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    match = _FENCE_RE.search(text)
    candidates = []
    if match:
        candidates.append(match.group(1))
    candidates.append(text)
    # Best-effort: look for the largest balanced { ... } slice.
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


def _normalize_findings(value: Any, payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    expected = payload.get("expected_finding") if isinstance(payload.get("expected_finding"), dict) else {}
    fallback_id = str(payload.get("finding_id") or expected.get("id") or "fnd_sandbox")
    if not isinstance(value, list):
        value = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            continue
        finding_id = str(raw.get("id") or f"{fallback_id}_{index}" if index else fallback_id)
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
                "id": finding_id,
                "title": str(raw.get("title") or "Compliance finding").strip()[:240],
                "description": str(raw.get("description") or "").strip()[:1200],
                "severity": severity,
                "confidence": confidence,
                "obligations_cited": [
                    str(urn) for urn in (raw.get("obligations_cited") or []) if isinstance(urn, str)
                ],
                "documents_cited": raw.get("documents_cited") if isinstance(raw.get("documents_cited"), list) else [],
                "status": "open",
            }
        )
    if not out and expected:
        out.append(_fallback_finding_from_expected(expected, fallback_id))
    return out


def _fallback_finding_from_expected(expected: dict[str, Any], fallback_id: str) -> dict[str, Any]:
    return {
        "id": str(expected.get("id") or fallback_id),
        "title": str(expected.get("title") or "Sandbox agent finding"),
        "description": str(expected.get("description") or "Live model returned no findings; emitting expected shape."),
        "severity": str(expected.get("severity") or "medium"),
        "confidence": float(expected.get("confidence", 0.6)),
        "obligations_cited": list(expected.get("obligations_cited") or []),
        "documents_cited": list(expected.get("documents_cited") or []),
        "status": "open",
    }


# ─── provider calls (urllib so the sandbox image stays dependency-free) ─────

def _call_openai(api_key: str, model: str, prompt: str) -> dict[str, Any]:
    body = json.dumps({"model": model, "input": prompt}).encode("utf-8")
    request = Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=DEFAULT_TIMEOUT) as response:  # noqa: S310 - https only, fixed host
        data = json.loads(response.read().decode("utf-8"))
    return {"text": _extract_openai_text(data), "usage": data.get("usage", {})}


def _extract_openai_text(data: dict[str, Any]) -> str:
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


def _call_anthropic(api_key: str, model: str, prompt: str) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")
    request = Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=DEFAULT_TIMEOUT) as response:  # noqa: S310
        data = json.loads(response.read().decode("utf-8"))
    text = "".join(
        block.get("text", "")
        for block in data.get("content", []) or []
        if isinstance(block, dict) and block.get("type") == "text"
    )
    return {"text": text, "usage": data.get("usage", {})}


def _call_google(api_key: str, model: str, prompt: str) -> dict[str, Any]:
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=DEFAULT_TIMEOUT) as response:  # noqa: S310
        data = json.loads(response.read().decode("utf-8"))
    parts: list[str] = []
    for candidate in data.get("candidates", []) or []:
        for part in (candidate.get("content") or {}).get("parts", []) or []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
    return {"text": "".join(parts), "usage": data.get("usageMetadata", {})}


# ─── deterministic stub ────────────────────────────────────────────────────

def _stub_output(payload: dict[str, Any], provider: str, model: str) -> dict[str, Any]:
    finding = payload.get("expected_finding") if isinstance(payload.get("expected_finding"), dict) else None
    if finding is None:
        finding = _fallback_finding(payload)
    return {
        "ok": True,
        "model_provider": provider,
        "model": model,
        "model_call": {
            "ok": True,
            "mode": "sandbox_dry_run",
            "provider": provider,
            "model": model,
            "configured": False,
            "text": "Sandbox harness produced a governed structured finding from supplied workflow context.",
            "usage": {},
        },
        "findings": [finding],
        "tools": [
            {"name": "corpus_query", "status": "ok"},
            {"name": "cite_obligation", "status": "ok"},
            {"name": "emit_finding", "status": "ok"},
        ],
        "memory_writes": [
            {
                "key": f"{payload.get('workflow_run_id', 'workflow')}:{payload.get('step_id', 'agent')}:finding",
                "provenance": "sandbox://agent_step",
            }
        ],
    }


def _manifest_payload() -> dict[str, Any]:
    raw = os.getenv("PRAETOR_AGENT_MANIFEST_JSON", "{}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _fallback_finding(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(payload.get("finding_id") or "fnd_sandbox"),
        "title": "Sandbox agent finding",
        "description": "The sandbox agent emitted a governed fallback finding.",
        "severity": "medium",
        "confidence": 0.5,
        "obligations_cited": [],
        "documents_cited": [],
        "status": "open",
    }


if __name__ == "__main__":
    main()
