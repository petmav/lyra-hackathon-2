from __future__ import annotations

from typing import Any

from praetor_api.services.json_stack import JSON_STACK_CATALOG
from praetor_api.services.model_providers import list_providers, provider_configured
from praetor_api.services.secrets import list_secret_statuses
from praetor_api.settings import get_settings


def runtime_readiness() -> dict[str, Any]:
    settings = get_settings()
    integration_auth_refs = {
        spec.get("auth", {}).get("auth_ref")
        for spec in JSON_STACK_CATALOG.values()
        if spec.get("auth", {}).get("auth_ref")
    }
    integration_secret_statuses = list_secret_statuses(
        {auth_ref for auth_ref in integration_auth_refs if isinstance(auth_ref, str)}
    )
    configured_integrations = sum(1 for item in integration_secret_statuses if item["configured"])
    default_provider_ready = provider_configured(settings.default_model_provider)
    live_agents_ready = settings.agent_model_mode == "dry_run" or default_provider_ready

    return {
        "data_mode": settings.data_mode,
        "data_backend": settings.data_backend,
        "agent_model_mode": settings.agent_model_mode,
        "default_model_provider": settings.default_model_provider,
        "default_model_name": settings.default_model_name,
        "models": {
            "providers": list_providers(),
            "default_provider_configured": default_provider_ready,
            "live_agents_ready": live_agents_ready,
        },
        "integrations": {
            "json_stack_count": len(JSON_STACK_CATALOG),
            "auth_ref_count": len(integration_secret_statuses),
            "configured_auth_refs": configured_integrations,
            "secrets": integration_secret_statuses,
        },
        "ok": live_agents_ready,
    }
