import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any

ALLOWED_EMAIL_DOMAINS = {"northwind.test", "customer.example"}
INJECTION_PATTERN = re.compile(r"ignore previous|jailbreak|reset system", re.IGNORECASE)


@dataclass(frozen=True)
class PolicyResult:
    outcome: str
    rationale: str
    latency_ms: float
    input_hash: str

    @property
    def allowed(self) -> bool:
        return self.outcome == "allow"


def _hash_input(policy_input: dict[str, Any]) -> str:
    body = json.dumps(policy_input, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def evaluate(policy_input: dict[str, Any]) -> PolicyResult:
    started = time.perf_counter()
    tool = str(policy_input.get("tool") or policy_input.get("tool_name") or "")
    args = policy_input.get("args") or policy_input.get("arguments") or {}

    outcome = "allow"
    rationale = "tool call is within hot-path policy"

    if tool == "send_email":
        recipient = str(args.get("recipient", ""))
        domain = recipient.rsplit("@", 1)[-1].lower() if "@" in recipient else ""
        subject = str(args.get("subject", ""))
        body = str(args.get("body", ""))

        if domain not in ALLOWED_EMAIL_DOMAINS:
            outcome = "deny"
            rationale = f"recipient domain '{domain or 'missing'}' is not allowlisted"
        elif INJECTION_PATTERN.search(subject) or INJECTION_PATTERN.search(body):
            outcome = "deny"
            rationale = "email content matches prompt-injection refusal pattern"

    return PolicyResult(
        outcome=outcome,
        rationale=rationale,
        latency_ms=(time.perf_counter() - started) * 1000,
        input_hash=_hash_input(policy_input),
    )
