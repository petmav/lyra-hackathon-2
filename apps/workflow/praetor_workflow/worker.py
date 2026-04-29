from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request


def _post_json(url: str, payload: dict, token: str) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    api_base = os.getenv("PRAETOR_API_BASE", "http://api:8000").rstrip("/")
    token = os.getenv("DEV_BEARER", "dev")
    interval = float(os.getenv("PRAETOR_WORKFLOW_WORKER_INTERVAL_SECONDS", "2"))
    batch_size = int(os.getenv("PRAETOR_WORKFLOW_WORKER_BATCH_SIZE", "4"))
    evidence_sweep_every = max(1, int(os.getenv("PRAETOR_EVIDENCE_SWEEP_EVERY_TICKS", "15")))
    print(
        "praetor workflow worker started "
        f"api_base={api_base} interval={interval}s batch_size={batch_size} "
        f"evidence_sweep_every={evidence_sweep_every}",
        flush=True,
    )
    tick = 0
    while True:
        try:
            result = _post_json(
                f"{api_base}/workflow-runs:drain",
                {"limit": batch_size},
                token,
            )
            count = int(result.get("count", 0))
            if count:
                print(f"praetor workflow worker processed {count} run(s)", flush=True)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            print(f"praetor workflow worker drain failed: {exc}", flush=True)
        tick += 1
        if tick % evidence_sweep_every == 0:
            try:
                result = _post_json(f"{api_base}/evidence-records:sweep", {}, token)
                created = int(result.get("created", 0))
                if created:
                    print(f"praetor evidence worker materialized {created} record(s)", flush=True)
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                print(f"praetor evidence worker sweep failed: {exc}", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
