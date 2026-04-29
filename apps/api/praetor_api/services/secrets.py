from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from praetor_api.settings import get_settings


SECRET_ENV_MAP: dict[str, str] = {
    "secret:anthropic_api_key": "ANTHROPIC_API_KEY",
    "secret:azure_devops_token": "AZURE_DEVOPS_TOKEN",
    "secret:confluence_oauth": "CONFLUENCE_OAUTH_TOKEN",
    "secret:datadog_api_key": "DATADOG_API_KEY",
    "secret:github_token": "GITHUB_TOKEN",
    "secret:google_api_key": "GOOGLE_API_KEY",
    "secret:gitlab_token": "GITLAB_TOKEN",
    "secret:google_drive_oauth": "GOOGLE_DRIVE_OAUTH_TOKEN",
    "secret:jira_oauth": "JIRA_OAUTH_TOKEN",
    "secret:linear_token": "LINEAR_TOKEN",
    "secret:microsoft_graph_oauth": "MICROSOFT_GRAPH_TOKEN",
    "secret:mcp_github_token": "MCP_GITHUB_TOKEN",
    "secret:mcp_localfiles_token": "MCP_LOCALFILES_TOKEN",
    "secret:mcp_slack_token": "MCP_SLACK_TOKEN",
    "secret:notion_token": "NOTION_TOKEN",
    "secret:okta_oauth": "OKTA_TOKEN",
    "secret:onetrust_oauth": "ONETRUST_TOKEN",
    "secret:openai_api_key": "OPENAI_API_KEY",
    "secret:power_platform_oauth": "POWER_PLATFORM_TOKEN",
    "secret:salesforce_oauth": "SALESFORCE_TOKEN",
    "secret:servicenow_oauth": "SERVICENOW_TOKEN",
    "secret:slack_bot_token": "SLACK_BOT_TOKEN",
    "secret:splunk_hec_token": "SPLUNK_HEC_TOKEN",
    "secret:zendesk_token": "ZENDESK_TOKEN",
}


@dataclass(frozen=True)
class SecretRefStatus:
    auth_ref: str
    env_key: str
    configured: bool

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "auth_ref": self.auth_ref,
            "env_key": self.env_key,
            "configured": self.configured,
        }


class MissingSecretError(RuntimeError):
    def __init__(self, auth_ref: str, env_key: str):
        super().__init__(f"{auth_ref} is not configured; set {env_key}")
        self.auth_ref = auth_ref
        self.env_key = env_key


class SecretBackendError(RuntimeError):
    def __init__(self, backend: str, message: str):
        super().__init__(message)
        self.backend = backend


def env_key_for_auth_ref(auth_ref: str | None) -> str | None:
    if not auth_ref:
        return None
    if auth_ref in SECRET_ENV_MAP:
        return SECRET_ENV_MAP[auth_ref]
    if auth_ref.startswith("secret:"):
        return auth_ref.removeprefix("secret:").upper()
    return auth_ref


def resolve_secret(auth_ref: str | None) -> str | None:
    env_key = env_key_for_auth_ref(auth_ref)
    if not env_key:
        return None
    settings = get_settings()
    if settings.secret_backend == "env":
        return _resolve_env(env_key)
    if settings.secret_backend == "vault":
        return _resolve_vault(auth_ref, env_key)
    if settings.secret_backend == "env_then_vault":
        return _resolve_env(env_key) or _resolve_vault(auth_ref, env_key)
    if settings.secret_backend == "vault_then_env":
        return _resolve_vault(auth_ref, env_key) or _resolve_env(env_key)
    return None


def require_secret(auth_ref: str | None) -> str:
    env_key = env_key_for_auth_ref(auth_ref)
    if not env_key or not auth_ref:
        raise MissingSecretError(auth_ref or "secret:unknown", env_key or "UNKNOWN_SECRET")
    value = resolve_secret(auth_ref)
    if not value:
        raise MissingSecretError(auth_ref, env_key)
    return value


def secret_status(auth_ref: str | None) -> dict[str, str | bool | None]:
    env_key = env_key_for_auth_ref(auth_ref)
    settings = get_settings()
    return {
        "auth_ref": auth_ref,
        "env_key": env_key,
        "backend": settings.secret_backend,
        "configured": bool(env_key and resolve_secret(auth_ref)),
    }


def list_secret_statuses(auth_refs: set[str]) -> list[dict[str, str | bool | None]]:
    return [
        secret_status(auth_ref)
        for auth_ref in sorted(auth_refs)
    ]


def _resolve_env(env_key: str) -> str | None:
    return os.getenv(env_key) or None


def _resolve_vault(auth_ref: str | None, env_key: str) -> str | None:
    if not auth_ref:
        return None
    settings = get_settings()
    if not settings.vault_addr or not settings.vault_token:
        return None
    path = _vault_secret_path(auth_ref)
    payload = _read_vault_kv2(settings.vault_addr, settings.vault_token, settings.vault_kv_mount, path)
    if not payload:
        return None
    for key in ("value", "token", "api_key", "secret", env_key):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _vault_secret_path(auth_ref: str) -> str:
    settings = get_settings()
    name = auth_ref.removeprefix("secret:") if auth_ref.startswith("secret:") else auth_ref
    prefix = settings.vault_path_prefix.strip("/")
    return f"{prefix}/{name}" if prefix else name


@lru_cache(maxsize=256)
def _read_vault_kv2(addr: str, token: str, mount: str, path: str) -> dict[str, object] | None:
    settings = get_settings()
    base = addr.rstrip("/")
    mount_path = mount.strip("/")
    secret_path = path.strip("/")
    url = f"{base}/v1/{mount_path}/data/{secret_path}"
    headers = {"X-Vault-Token": token}
    if settings.vault_namespace:
        headers["X-Vault-Namespace"] = settings.vault_namespace
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=settings.vault_timeout_seconds) as response:
            body = response.read()
    except (HTTPError, URLError, TimeoutError):
        return None
    parsed = json.loads(body)
    data = parsed.get("data", {}) if isinstance(parsed, dict) else {}
    nested = data.get("data", {}) if isinstance(data, dict) else {}
    return nested if isinstance(nested, dict) else None
