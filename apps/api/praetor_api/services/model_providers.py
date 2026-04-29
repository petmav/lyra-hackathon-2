from dataclasses import dataclass
import json
from collections.abc import AsyncIterator
from typing import Any, Literal

import httpx

from praetor_api.services.secrets import resolve_secret
from praetor_api.settings import get_settings

ProviderName = Literal["openai", "anthropic", "google"]


@dataclass(frozen=True)
class ModelProvider:
    id: ProviderName
    name: str
    default_model: str
    env_key: str
    models: tuple[str, ...]


class ModelProviderError(RuntimeError):
    def __init__(
        self,
        provider: str,
        model: str,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.status_code = status_code


PROVIDERS: dict[str, ModelProvider] = {
    "openai": ModelProvider(
        id="openai",
        name="OpenAI",
        default_model="gpt-5.4-mini",
        env_key="OPENAI_API_KEY",
        models=("gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-4.1"),
    ),
    "anthropic": ModelProvider(
        id="anthropic",
        name="Anthropic",
        default_model="claude-sonnet-4-20250514",
        env_key="ANTHROPIC_API_KEY",
        models=(
            "claude-opus-4-1-20250805",
            "claude-sonnet-4-20250514",
            "claude-3-7-sonnet-latest",
            "claude-3-5-haiku-latest",
        ),
    ),
    "google": ModelProvider(
        id="google",
        name="Google",
        default_model="gemini-2.0-flash",
        env_key="GOOGLE_API_KEY",
        models=("gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"),
    ),
}


def provider_api_key(provider_id: str) -> str | None:
    settings = get_settings()
    env_value = {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "google": settings.google_api_key,
    }.get(provider_id)
    if env_value:
        return env_value
    auth_ref = {
        "openai": settings.openai_api_key_ref,
        "anthropic": settings.anthropic_api_key_ref,
        "google": settings.google_api_key_ref,
    }.get(provider_id)
    return resolve_secret(auth_ref)


def provider_configured(provider_id: str) -> bool:
    return bool(provider_api_key(provider_id))


def list_providers() -> list[dict[str, Any]]:
    return [
        {
            "id": provider.id,
            "name": provider.name,
            "default_model": provider.default_model,
            "models": list(provider.models),
            "env_key": provider.env_key,
            "configured": provider_configured(provider.id),
            "status": "configured" if provider_configured(provider.id) else "missing_key",
        }
        for provider in PROVIDERS.values()
    ]


def normalize_choice(provider: str | None, model: str | None) -> tuple[ModelProvider, str]:
    settings = get_settings()
    provider_id = provider or settings.default_model_provider
    if provider_id not in PROVIDERS:
        raise KeyError(provider_id)
    selected_provider = PROVIDERS[provider_id]
    if model:
        selected_model = model
    elif provider is None and settings.default_model_name:
        selected_model = settings.default_model_name
    else:
        selected_model = selected_provider.default_model
    return selected_provider, selected_model


async def complete(
    prompt: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    system: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    selected_provider, selected_model = normalize_choice(provider, model)
    if dry_run:
        return {
            "provider": selected_provider.id,
            "model": selected_model,
            "text": f"[dry-run:{selected_provider.id}/{selected_model}] {prompt[:160]}",
            "usage": {"input_tokens": len(prompt.split()), "output_tokens": 1},
        }

    if not provider_configured(selected_provider.id):
        raise ModelProviderError(
            selected_provider.id,
            selected_model,
            f"{selected_provider.env_key} is not configured",
            status_code=400,
        )

    try:
        if selected_provider.id == "openai":
            return await _openai_complete(prompt, selected_model, system)
        if selected_provider.id == "anthropic":
            return await _anthropic_complete(prompt, selected_model, system)
        if selected_provider.id == "google":
            return await _google_complete(prompt, selected_model, system)
    except httpx.HTTPStatusError as exc:
        detail = _truncate_error_detail(exc.response.text)
        raise ModelProviderError(
            selected_provider.id,
            selected_model,
            f"{selected_provider.name} API returned HTTP {exc.response.status_code}: {detail}",
            status_code=502,
        ) from exc
    except httpx.HTTPError as exc:
        raise ModelProviderError(
            selected_provider.id,
            selected_model,
            f"{selected_provider.name} API request failed: {exc.__class__.__name__}",
            status_code=502,
        ) from exc
    raise KeyError(selected_provider.id)


async def stream_complete(
    prompt: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    system: str | None = None,
    dry_run: bool = True,
) -> AsyncIterator[dict[str, Any]]:
    selected_provider, selected_model = normalize_choice(provider, model)
    yield {"type": "start", "provider": selected_provider.id, "model": selected_model}

    if dry_run:
        text = f"[dry-run:{selected_provider.id}/{selected_model}] {prompt[:160]}"
        for chunk in _chunk_text(text, 32):
            yield {"type": "delta", "provider": selected_provider.id, "model": selected_model, "text": chunk}
        yield {
            "type": "done",
            "provider": selected_provider.id,
            "model": selected_model,
            "text": text,
            "usage": {"input_tokens": len(prompt.split()), "output_tokens": max(1, len(text.split()))},
        }
        return

    if not provider_configured(selected_provider.id):
        raise ModelProviderError(
            selected_provider.id,
            selected_model,
            f"{selected_provider.env_key} is not configured",
            status_code=400,
        )

    try:
        if selected_provider.id == "openai":
            async for event in _openai_stream_complete(prompt, selected_model, system):
                yield event
            return
        if selected_provider.id == "anthropic":
            async for event in _anthropic_stream_complete(prompt, selected_model, system):
                yield event
            return
        if selected_provider.id == "google":
            async for event in _google_stream_complete(prompt, selected_model, system):
                yield event
            return
    except httpx.HTTPStatusError as exc:
        detail = _truncate_error_detail(exc.response.text)
        raise ModelProviderError(
            selected_provider.id,
            selected_model,
            f"{selected_provider.name} API returned HTTP {exc.response.status_code}: {detail}",
            status_code=502,
        ) from exc
    except httpx.HTTPError as exc:
        raise ModelProviderError(
            selected_provider.id,
            selected_model,
            f"{selected_provider.name} API request failed: {exc.__class__.__name__}",
            status_code=502,
        ) from exc
    raise KeyError(selected_provider.id)


async def _openai_complete(prompt: str, model: str, system: str | None) -> dict[str, Any]:
    api_key = provider_api_key("openai")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    payload: dict[str, Any] = {"model": model, "input": prompt}
    if system:
        payload["instructions"] = system
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    return {
        "provider": "openai",
        "model": model,
        "text": _extract_openai_text(data),
        "usage": data.get("usage", {}),
        "raw": data,
    }


async def _openai_stream_complete(prompt: str, model: str, system: str | None) -> AsyncIterator[dict[str, Any]]:
    api_key = provider_api_key("openai")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    payload: dict[str, Any] = {"model": model, "input": prompt, "stream": True}
    if system:
        payload["instructions"] = system
    text_parts: list[str] = []
    yielded_done = False
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        ) as response:
            response.raise_for_status()
            async for event_name, data in _aiter_sse_events(response):
                event = _openai_stream_event(event_name, data, model)
                if event is None:
                    continue
                if event["type"] == "delta":
                    text_parts.append(event["text"])
                elif event["type"] == "done":
                    event["text"] = "".join(text_parts)
                    yielded_done = True
                yield event
    if not yielded_done:
        yield {"type": "done", "provider": "openai", "model": model, "text": "".join(text_parts), "usage": {}}


async def _anthropic_complete(prompt: str, model: str, system: str | None) -> dict[str, Any]:
    api_key = provider_api_key("anthropic")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
    return {
        "provider": "anthropic",
        "model": model,
        "text": text,
        "usage": data.get("usage", {}),
        "raw": data,
    }


async def _anthropic_stream_complete(prompt: str, model: str, system: str | None) -> AsyncIterator[dict[str, Any]]:
    api_key = provider_api_key("anthropic")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 1024,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system
    text_parts: list[str] = []
    latest_usage: dict[str, Any] = {}
    yielded_done = False
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            json=payload,
        ) as response:
            response.raise_for_status()
            async for event_name, data in _aiter_sse_events(response):
                event = _anthropic_stream_event(event_name, data, model)
                if event is None:
                    continue
                if event["type"] == "delta":
                    text_parts.append(event["text"])
                elif event["type"] == "usage":
                    latest_usage = event.get("usage", {})
                elif event["type"] == "done":
                    event["text"] = "".join(text_parts)
                    event["usage"] = latest_usage
                    yielded_done = True
                yield event
    if not yielded_done:
        yield {
            "type": "done",
            "provider": "anthropic",
            "model": model,
            "text": "".join(text_parts),
            "usage": latest_usage,
        }


async def _google_complete(prompt: str, model: str, system: str | None) -> dict[str, Any]:
    api_key = provider_api_key("google")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not configured")
    payload: dict[str, Any] = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": api_key},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    candidates = data.get("candidates", [])
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    return {
        "provider": "google",
        "model": model,
        "text": "".join(part.get("text", "") for part in parts),
        "usage": data.get("usageMetadata", {}),
        "raw": data,
    }


async def _google_stream_complete(prompt: str, model: str, system: str | None) -> AsyncIterator[dict[str, Any]]:
    api_key = provider_api_key("google")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not configured")
    payload: dict[str, Any] = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    text_parts: list[str] = []
    latest_usage: dict[str, Any] = {}
    yielded_done = False
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent",
            params={"key": api_key, "alt": "sse"},
            json=payload,
        ) as response:
            response.raise_for_status()
            async for event_name, data in _aiter_sse_events(response):
                event = _google_stream_event(event_name, data, model)
                if event is None:
                    continue
                if event["type"] == "delta":
                    text_parts.append(event["text"])
                elif event["type"] == "done":
                    event["text"] = "".join(text_parts)
                    yielded_done = True
                latest_usage = event.get("usage", latest_usage)
                yield event
    if not yielded_done:
        yield {
            "type": "done",
            "provider": "google",
            "model": model,
            "text": "".join(text_parts),
            "usage": latest_usage,
        }


async def check_provider(
    *,
    provider: str | None = None,
    model: str | None = None,
    live: bool = False,
) -> dict[str, Any]:
    selected_provider, selected_model = normalize_choice(provider, model)
    configured = provider_configured(selected_provider.id)
    result: dict[str, Any] = {
        "provider": selected_provider.id,
        "model": selected_model,
        "env_key": selected_provider.env_key,
        "configured": configured,
        "live_checked": live,
        "ok": configured if live else True,
    }
    if not live:
        result["status"] = "configured" if configured else "missing_key"
        return result
    if not configured:
        result["status"] = "missing_key"
        result["ok"] = False
        return result
    try:
        completion = await complete(
            "Return exactly: ready",
            provider=selected_provider.id,
            model=selected_model,
            system="You are a terse runtime health checker.",
            dry_run=False,
        )
    except ModelProviderError as exc:
        result["status"] = "provider_error"
        result["ok"] = False
        result["error"] = str(exc)
        return result
    result["status"] = "ready"
    result["ok"] = True
    result["sample_text"] = completion.get("text", "")[:80]
    return result


def _extract_openai_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    text_parts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                text_parts.append(content["text"])
    return "".join(text_parts)


def _openai_stream_event(event_name: str | None, data: dict[str, Any], model: str) -> dict[str, Any] | None:
    event_type = data.get("type") or event_name
    if event_type == "response.output_text.delta" and isinstance(data.get("delta"), str):
        return {"type": "delta", "provider": "openai", "model": model, "text": data["delta"], "raw_type": event_type}
    if event_type == "response.completed":
        response = data.get("response") if isinstance(data.get("response"), dict) else {}
        return {
            "type": "done",
            "provider": "openai",
            "model": model,
            "usage": response.get("usage", {}),
            "raw_type": event_type,
        }
    if event_type == "error":
        return {"type": "error", "provider": "openai", "model": model, "error": data.get("error", data)}
    return None


def _anthropic_stream_event(event_name: str | None, data: dict[str, Any], model: str) -> dict[str, Any] | None:
    event_type = data.get("type") or event_name
    if event_type == "content_block_delta":
        delta = data.get("delta") if isinstance(data.get("delta"), dict) else {}
        if delta.get("type") == "text_delta" and isinstance(delta.get("text"), str):
            return {
                "type": "delta",
                "provider": "anthropic",
                "model": model,
                "text": delta["text"],
                "raw_type": event_type,
            }
    if event_type == "message_delta":
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return {"type": "usage", "provider": "anthropic", "model": model, "usage": usage, "raw_type": event_type}
    if event_type == "message_stop":
        return {"type": "done", "provider": "anthropic", "model": model, "usage": {}, "raw_type": event_type}
    if event_type == "error":
        return {"type": "error", "provider": "anthropic", "model": model, "error": data.get("error", data)}
    return None


def _google_stream_event(event_name: str | None, data: dict[str, Any], model: str) -> dict[str, Any] | None:
    candidates = data.get("candidates", [])
    text_parts: list[str] = []
    finish_reason: str | None = None
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            finish_reason = candidate.get("finishReason") or finish_reason
            content = candidate.get("content") if isinstance(candidate.get("content"), dict) else {}
            parts = content.get("parts", []) if isinstance(content, dict) else []
            if isinstance(parts, list):
                text_parts.extend(part.get("text", "") for part in parts if isinstance(part, dict))
    if text_parts:
        return {
            "type": "delta",
            "provider": "google",
            "model": model,
            "text": "".join(text_parts),
            "raw_type": event_name or "message",
        }
    if finish_reason:
        return {
            "type": "done",
            "provider": "google",
            "model": model,
            "usage": data.get("usageMetadata", {}),
            "raw_type": event_name or "message",
        }
    return None


async def _aiter_sse_events(response: httpx.Response) -> AsyncIterator[tuple[str | None, dict[str, Any]]]:
    event_name: str | None = None
    data_lines: list[str] = []
    async for line in response.aiter_lines():
        if line == "":
            parsed = _parse_sse_event(event_name, data_lines)
            if parsed is not None:
                yield parsed
            event_name = None
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())
    parsed = _parse_sse_event(event_name, data_lines)
    if parsed is not None:
        yield parsed


def _parse_sse_event(event_name: str | None, data_lines: list[str]) -> tuple[str | None, dict[str, Any]] | None:
    if not data_lines:
        return None
    raw = "\n".join(data_lines)
    if raw == "[DONE]":
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return event_name, {"type": event_name or "message", "text": raw}
    if not isinstance(data, dict):
        return event_name, {"type": event_name or "message", "data": data}
    return event_name, data


def _chunk_text(text: str, size: int) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)] or [""]


def _truncate_error_detail(detail: str) -> str:
    normalized = " ".join(detail.split())
    return normalized[:300] if normalized else "no response body"
