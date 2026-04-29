from typing import Any


def call_hook_in(args: dict[str, Any]) -> dict[str, Any]:
    repo_url = str(args.get("repo_url", "stub://support-bot"))
    return {
        "repo_url": repo_url,
        "files": {
            "tools.py": (
                "def send_email(recipient, subject, body):\n"
                "    return smtp.send(recipient, subject, body)\n"
            )
        },
    }
