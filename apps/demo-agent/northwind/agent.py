import argparse
import json
import re
from typing import Any

from praetor_sdk import PolicyDenied

from northwind.tools import lookup_kb, send_email

EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")


def run(prompt: str) -> dict[str, Any]:
    lookup = lookup_kb(query=prompt)
    recipient_match = EMAIL_RE.search(prompt)
    recipient = recipient_match.group(0) if recipient_match else "buyer@customer.example"

    try:
        email = send_email(
            recipient=recipient,
            subject="Northwind support follow-up",
            body=f"Customer-visible response derived from: {prompt}",
        )
        return {
            "ok": True,
            "thought": "Customer request required an outbound email.",
            "lookup": lookup,
            "tool": "send_email",
            "result": email,
        }
    except PolicyDenied as exc:
        return {
            "ok": False,
            "thought": "Outbound email was blocked by hot-path policy.",
            "lookup": lookup,
            "tool": "send_email",
            "refusal": exc.rationale,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.prompt), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
