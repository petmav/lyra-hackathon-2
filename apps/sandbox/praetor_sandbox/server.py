from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from typing import Any

from praetor_sandbox.orchestrator import DockerSandboxOrchestrator, SandboxManifest


ORCHESTRATOR = DockerSandboxOrchestrator()


class Handler(BaseHTTPRequestHandler):
    server_version = "praetor-sandbox/0.1"

    def do_GET(self) -> None:
        if self.path != "/health":
            self._send(404, {"detail": "not found"})
            return
        self._send(200, {"ok": True, "service": "sandbox"})

    def do_POST(self) -> None:
        if self.path != "/launch":
            self._send(404, {"detail": "not found"})
            return
        payload = self._read_json()
        manifest = SandboxManifest.from_payload(payload)
        self._send(200, ORCHESTRATOR.launch(manifest))

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(os.getenv("SANDBOX_PORT", "8700"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"praetor sandbox orchestrator listening on {port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
