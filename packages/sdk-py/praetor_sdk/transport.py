import os
from typing import Any

import httpx


class PolicyDenied(RuntimeError):
    def __init__(self, rationale: str) -> None:
        super().__init__(rationale)
        self.rationale = rationale


class PraetorClient:
    def __init__(self, base_url: str | None = None, bearer: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("PRAETOR_API_BASE") or "http://localhost:8000").rstrip("/")
        self.bearer = bearer or os.environ.get("PRAETOR_DEV_BEARER") or "dev"

    def evaluate_policy(self, policy_input: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/policy:evaluate",
            headers={"Authorization": f"Bearer {self.bearer}"},
            json={"input": policy_input},
            timeout=5,
        )
        response.raise_for_status()
        return response.json()
