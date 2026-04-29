from __future__ import annotations

import os
from dataclasses import dataclass


SECRET_ENV_MAP: dict[str, str] = {
    "secret:azure_devops_token": "AZURE_DEVOPS_TOKEN",
    "secret:confluence_oauth": "CONFLUENCE_OAUTH_TOKEN",
    "secret:datadog_api_key": "DATADOG_API_KEY",
    "secret:github_token": "GITHUB_TOKEN",
    "secret:gitlab_token": "GITLAB_TOKEN",
    "secret:google_drive_oauth": "GOOGLE_DRIVE_OAUTH_TOKEN",
    "secret:jira_oauth": "JIRA_OAUTH_TOKEN",
    "secret:linear_token": "LINEAR_TOKEN",
    "secret:microsoft_graph_oauth": "MICROSOFT_GRAPH_TOKEN",
    "secret:notion_token": "NOTION_TOKEN",
    "secret:okta_oauth": "OKTA_TOKEN",
    "secret:onetrust_oauth": "ONETRUST_TOKEN",
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
    return os.getenv(env_key) or None


def require_secret(auth_ref: str | None) -> str:
    env_key = env_key_for_auth_ref(auth_ref)
    if not env_key or not auth_ref:
        raise MissingSecretError(auth_ref or "secret:unknown", env_key or "UNKNOWN_SECRET")
    value = os.getenv(env_key)
    if not value:
        raise MissingSecretError(auth_ref, env_key)
    return value


def secret_status(auth_ref: str | None) -> dict[str, str | bool | None]:
    env_key = env_key_for_auth_ref(auth_ref)
    return {
        "auth_ref": auth_ref,
        "env_key": env_key,
        "configured": bool(env_key and os.getenv(env_key)),
    }


def list_secret_statuses(auth_refs: set[str]) -> list[dict[str, str | bool | None]]:
    return [
        secret_status(auth_ref)
        for auth_ref in sorted(auth_refs)
    ]
