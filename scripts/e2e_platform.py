from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_API_BASE = "http://localhost:8000"
DEFAULT_WEB_BASE = "http://localhost:3000"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


class Client:
    def __init__(self, base_url: str, bearer: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.bearer = bearer
        self.timeout = timeout

    def get(self, path: str, query: dict[str, Any] | None = None) -> Any:
        suffix = f"?{urlencode(query)}" if query else ""
        return self._request("GET", f"{path}{suffix}")

    def get_text(self, path: str) -> str:
        request = Request(
            f"{self.base_url}{path}",
            method="GET",
            headers={"Authorization": f"Bearer {self.bearer}"},
        )
        with urlopen(request, timeout=self.timeout) as response:
            return response.read().decode("utf-8")

    def post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return self._request("POST", path, payload or {})

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.bearer}",
                "Content-Type": "application/json",
            },
        )
        with urlopen(request, timeout=self.timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Praetor platform E2E checks against a live stack.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--web-base", default=DEFAULT_WEB_BASE)
    parser.add_argument("--bearer", default="dev")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--skip-web", action="store_true")
    args = parser.parse_args()

    client = Client(args.api_base, args.bearer, args.timeout)
    results: list[CheckResult] = []

    def check(name: str, fn) -> Any:
        started = time.perf_counter()
        try:
            value = fn()
        except Exception as exc:
            results.append(CheckResult(name, False, f"{exc.__class__.__name__}: {exc}"))
            print(f"FAIL {name}: {exc}", flush=True)
            return None
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        results.append(CheckResult(name, True, f"{elapsed_ms}ms"))
        print(f"PASS {name} ({elapsed_ms}ms)", flush=True)
        return value

    health = check("api health", lambda: require_keys(client.get("/health"), ["ok", "data_mode", "data_backend"]))
    check("runtime config", lambda: require_keys(client.get("/runtime/config"), ["workflow_execution_mode", "agent_model_mode"]))
    check("runtime readiness", lambda: require_keys(client.get("/runtime/readiness"), ["models", "integrations", "ok"]))
    check("model registry", lambda: require_minimum(client.get("/models/providers"), 3, "model providers"))
    check("model offline check", lambda: require_true(client.post("/models:check", {"provider": "openai", "live": False})["ok"]))
    check("inventory assets endpoint", lambda: require_list(client.get("/assets"), "assets"))
    check("obligations endpoint", lambda: require_minimum(client.get("/obligations"), 1, "obligations"))
    check("controls endpoint", lambda: require_minimum(client.get("/controls"), 1, "controls"))
    check("workflow catalog", lambda: require_workflows(client.get("/workflows")))
    check("hook catalog", lambda: require_minimum(client.get("/hooks"), 3, "hooks"))
    check("mcp json-rpc health", lambda: require_mcp_health(client.post("/hooks/github_stub:test")))
    check("json stack catalog", lambda: require_minimum(client.get("/hooks/json-stack/catalog"), 10, "json stack templates"))
    check("json stack preview", lambda: require_true(client.post(
        "/hooks/json-stack:preview",
        {
            "stack_id": "salesforce_json",
            "operation": "describe_sobject",
            "inputs": {
                "instance_url": "https://example.my.salesforce.com",
                "api_version": "v66.0",
                "object_name": "Task",
            },
        },
    )["ok"]))
    check("json stack missing-secret failure", lambda: require_hook_failure(client.post(
        "/hooks/datadog_json:call",
        {
            "operation": "query_events",
            "inputs": {"site": "datadoghq.com", "query": "source:praetor", "limit": 1},
            "dry_run": False,
        },
    )))
    check("corpus ingest", lambda: client.post(
        "/corpora/internal_data_min/documents:ingest",
        {
            "title": "E2E policy",
            "source_uri": "e2e://policy",
            "text": "Email tools must validate recipient domains before sending customer data.",
        },
    ))
    check("corpus search", lambda: require_minimum(client.post(
        "/corpora/internal_data_min:search",
        {"query": "recipient domains", "k": 3},
    ), 1, "corpus hits"))

    run_id = check("workflow run create", lambda: require_run_id(client.post(
        "/workflows/code_compliance_scan_full:run",
        {
            "inputs": {"repo_url": "stub://support-bot", "approved": True},
            "model_provider": "openai",
            "model": "gpt-5.4-mini",
        },
    )))
    if run_id:
        run = check("workflow run read", lambda: require_workflow_run(client.get(f"/workflow-runs/{run_id}")))
        check("workflow events hash chain", lambda: require_hash_chain(client.get("/events", {"workflow_run_id": run_id})))
        if run:
            proposal_id = first_proposal_id(run)
            if proposal_id:
                check("proposed change read", lambda: require_keys(client.get(f"/proposed-changes/{proposal_id}"), ["id", "diff", "status"]))
                check("sandbox run create", lambda: require_keys(client.post(f"/proposed-changes/{proposal_id}:sandbox-run"), ["id", "exit_code"]))
                sandbox_runs = check("sandbox run list", lambda: require_list(client.get("/sandbox-runs"), "sandbox runs"))
                if sandbox_runs:
                    check("sandbox log stream", lambda: require_log_stream(client.get_text(f"/sandbox-runs/{sandbox_runs[0]['id']}/logs")))
                check("proposed change approve", lambda: require_true(client.post(f"/proposed-changes/{proposal_id}:approve")["ok"]))
                check("proposed change apply", lambda: require_true(client.post(f"/proposed-changes/{proposal_id}:apply")["ok"]))
            else:
                results.append(CheckResult("proposed change lifecycle", False, "workflow emitted no proposed change id"))
                print("FAIL proposed change lifecycle: workflow emitted no proposed change id", flush=True)

    check("findings list", lambda: require_list(client.get("/findings"), "findings"))
    paused_run_id = check("workflow paused run create", lambda: require_run_id(client.post(
        "/workflows/code_compliance_scan_full:run",
        {
            "inputs": {"repo_url": "stub://support-bot", "approved": False},
            "model_provider": "openai",
            "model": "gpt-5.4-mini",
        },
    )))
    if paused_run_id:
        check("workflow paused run read", lambda: require_status(client.get(f"/workflow-runs/{paused_run_id}"), "awaiting_approval"))
        check("workflow resume", lambda: require_status(client.post(
            f"/workflow-runs/{paused_run_id}:resume",
            {"approved": True, "approver": "e2e"},
        ), "succeeded"))
        cancelled_run_id = check("workflow cancellable run create", lambda: require_run_id(client.post(
            "/workflows/code_compliance_scan_full:run",
            {
                "inputs": {"repo_url": "stub://support-bot", "approved": False},
                "model_provider": "openai",
                "model": "gpt-5.4-mini",
            },
        )))
        if cancelled_run_id:
            check("workflow cancel", lambda: require_true(client.post(f"/workflow-runs/{cancelled_run_id}:cancel")["ok"]))
            check("workflow cancelled run read", lambda: require_status(client.get(f"/workflow-runs/{cancelled_run_id}"), "cancelled"))
    check("evidence sweep", lambda: require_true(client.post("/evidence-records:sweep")["ok"]))
    check("evidence records", lambda: require_list(client.get("/evidence-records"), "evidence records"))
    check("audit packet generate", lambda: require_keys(client.post("/audit-packets:generate"), ["id", "packet_hash", "signature"]))
    check("workflow drain endpoint", lambda: require_keys(client.post("/workflow-runs:drain", {"limit": 1}), ["processed", "count"]))

    if not args.skip_web:
        for path in ["/", "/workflows", "/workflow-runs", "/hooks", "/hooks/validate", "/corpora", "/evidence", "/inventory", "/obligations", "/sandbox"]:
            check(f"web route {path}", lambda path=path: require_web_ok(args.web_base.rstrip("/") + path, args.timeout))

    failed = [result for result in results if not result.ok]
    print("\nPraetor E2E summary")
    print(f"  passed: {len(results) - len(failed)}")
    print(f"  failed: {len(failed)}")
    for result in failed:
        print(f"  - {result.name}: {result.detail}")
    if health:
        print(f"  data_mode: {health.get('data_mode')} / {health.get('data_backend')}")
    return 1 if failed else 0


def require_keys(payload: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    missing = [key for key in keys if key not in payload]
    if missing:
        raise AssertionError(f"missing keys: {missing}")
    return payload


def require_true(value: Any) -> bool:
    if value is not True:
        raise AssertionError(f"expected true, got {value!r}")
    return True


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise AssertionError(f"{label} is not a list")
    return value


def require_minimum(value: Any, minimum: int, label: str) -> list[Any]:
    rows = require_list(value, label)
    if len(rows) < minimum:
        raise AssertionError(f"expected at least {minimum} {label}, got {len(rows)}")
    return rows


def require_workflows(workflows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = {row.get("id") for row in workflows}
    required = {"code_compliance_scan", "code_compliance_scan_full", "policy_gap_analysis"}
    if not required <= ids:
        raise AssertionError(f"missing workflow ids: {sorted(required - ids)}")
    return workflows


def require_run_id(payload: dict[str, Any]) -> str:
    run_id = payload.get("workflow_run_id")
    if not isinstance(run_id, str) or not run_id:
        raise AssertionError("workflow_run_id missing")
    return run_id


def require_workflow_run(run: dict[str, Any]) -> dict[str, Any]:
    require_keys(run, ["id", "status", "step_runs", "outputs"])
    if run["status"] not in {"succeeded", "awaiting_approval"}:
        raise AssertionError(f"unexpected run status {run['status']}")
    step_ids = {step.get("step_id") for step in run["step_runs"]}
    if not {"pull", "scan", "emit"} <= step_ids:
        raise AssertionError(f"missing required steps in {step_ids}")
    scan_step = next((step for step in run["step_runs"] if step.get("step_id") == "scan"), {})
    if not str(scan_step.get("sandbox_run_id", "")).startswith("sbx_"):
        raise AssertionError("scan step did not expose sandbox_run_id")
    outputs = scan_step.get("outputs_redacted", {})
    if not isinstance(outputs, dict) or "workflow_agent_asset_urn" not in outputs:
        raise AssertionError("scan step did not expose workflow_agent_asset_urn")
    return run


def require_status(run: dict[str, Any], status: str) -> dict[str, Any]:
    if run.get("status") != status:
        raise AssertionError(f"expected status {status}, got {run.get('status')}")
    return run


def require_hash_chain(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    require_minimum(events, 3, "events")
    previous = None
    for event in events:
        current = event.get("hash_chain_self")
        if not current:
            raise AssertionError(f"event missing self hash: {event.get('id')}")
        if previous is not None and event.get("hash_chain_prev") != previous:
            raise AssertionError(f"broken hash chain at {event.get('id')}")
        previous = current
    return events


def require_hook_failure(call: dict[str, Any]) -> dict[str, Any]:
    if call.get("status") != "failed":
        raise AssertionError(f"expected failed hook call, got {call.get('status')}")
    outputs = call.get("outputs_redacted", {})
    if not isinstance(outputs, dict) or outputs.get("env_key") != "DATADOG_API_KEY":
        raise AssertionError("missing redacted missing-secret output")
    return call


def require_mcp_health(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("ok") is not True:
        raise AssertionError("MCP health was not ok")
    if result.get("mode") not in {"mcp-json-rpc", "deterministic-fallback", None}:
        raise AssertionError(f"unexpected MCP mode {result.get('mode')}")
    return result


def require_log_stream(text: str) -> str:
    rows = [line for line in text.splitlines() if line.strip()]
    if not rows:
        raise AssertionError("sandbox log stream was empty")
    for row in rows:
        parsed = json.loads(row)
        if "stream" not in parsed or "line" not in parsed:
            raise AssertionError("sandbox log row missing stream/line")
    return text


def first_proposal_id(run: dict[str, Any]) -> str | None:
    for step in run.get("step_runs", []):
        for proposal_id in step.get("emitted_proposal_ids", []) or []:
            if isinstance(proposal_id, str):
                return proposal_id
    return None


def require_web_ok(url: str, timeout: float) -> int:
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            status = response.status
    except HTTPError as exc:
        raise AssertionError(f"HTTP {exc.code}") from exc
    except URLError as exc:
        raise AssertionError(str(exc.reason)) from exc
    if status < 200 or status >= 400:
        raise AssertionError(f"HTTP {status}")
    return status


if __name__ == "__main__":
    sys.exit(main())
