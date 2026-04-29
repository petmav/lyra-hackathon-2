from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import uuid

PROTOCOL_VERSION = "2025-06-18"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in {"/health", "/resources"}:
            self.send_response(404)
            self.end_headers()
            return

        body = {
            "ok": True,
            "stub": os.environ.get("MCP_STUB_NAME", "mcp-stub"),
            "resources": ["stub://northwind/support-bot"],
        }
        payload = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        if self.path == "/mcp":
            self._handle_mcp()
            return
        if self.path != "/call":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("content-length") or "0")
        body = self.rfile.read(length) if length else b"{}"
        try:
            request = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            request = {}

        stub_name = os.environ.get("MCP_STUB_NAME", "mcp-stub")
        operation = request.get("operation", "unknown")
        inputs = request.get("inputs", {})
        if not isinstance(inputs, dict):
            inputs = {}

        response = {
            "ok": True,
            "stub": stub_name,
            "operation": operation,
            "outputs": output_for(stub_name, operation, inputs, bool(request.get("dry_run", True))),
        }
        payload = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _handle_mcp(self) -> None:
        expected_token = os.environ.get("MCP_STUB_TOKEN")
        if expected_token and self.headers.get("Authorization") != f"Bearer {expected_token}":
            self.send_response(401)
            self.send_header(
                "WWW-Authenticate",
                'Bearer resource_metadata="http://localhost/.well-known/oauth-protected-resource", scope="mcp:tools"',
            )
            self.end_headers()
            return

        length = int(self.headers.get("content-length") or "0")
        body = self.rfile.read(length) if length else b"{}"
        try:
            request = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            request = {}

        method = request.get("method")
        request_id = request.get("id")
        stub_name = os.environ.get("MCP_STUB_NAME", "mcp-stub")
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": {"name": stub_name, "version": "0.1.0"},
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"listChanged": False},
                    "prompts": {"listChanged": False},
                },
            }
        elif method == "tools/list":
            if not self._require_session(request_id):
                return
            result = {"tools": tool_catalog(stub_name)}
        elif method == "resources/list":
            if not self._require_session(request_id):
                return
            result = {"resources": [{"uri": "stub://northwind/support-bot", "name": "Northwind support bot"}]}
        elif method == "prompts/list":
            if not self._require_session(request_id):
                return
            result = {"prompts": [{"name": "review_change", "description": "Review a proposed change"}]}
        elif method == "tools/call":
            if not self._require_session(request_id):
                return
            if self.headers.get("Mcp-Method") != "tools/call":
                self._send_json({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32600, "message": "missing Mcp-Method"}})
                return
            params = request.get("params", {})
            if not isinstance(params, dict):
                params = {}
            name = params.get("name", "unknown")
            arguments = params.get("arguments", {})
            if not isinstance(arguments, dict):
                arguments = {}
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(output_for(stub_name, str(name), arguments, bool(arguments.get("dry_run", True)))),
                    }
                ],
                "isError": False,
            }
        else:
            self._send_json({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "method not found"}})
            return
        self._send_json({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _send_json(self, response: dict) -> None:
        payload = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        if response.get("result", {}).get("protocolVersion") == PROTOCOL_VERSION:
            self.send_header("MCP-Session-Id", f"sess-{uuid.uuid4()}")
            self.send_header("MCP-Protocol-Version", PROTOCOL_VERSION)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _require_session(self, request_id: object) -> bool:
        if not self.headers.get("MCP-Session-Id"):
            self._send_json({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": "missing MCP session"}})
            return False
        return True

    def log_message(self, format: str, *args: object) -> None:
        return


def output_for(stub_name: str, operation: str, inputs: dict, dry_run: bool) -> dict:
    if stub_name == "github" and operation == "open_pr":
        return {
            "pr_url": "https://github.example/northwind/support-bot/pull/42",
            "branch": inputs.get("branch", "praetor/send-email-domain-guard"),
            "dry_run": dry_run,
        }
    if stub_name == "github" and operation == "read_repo":
        return {
            "repo_url": inputs.get("repo_url", "stub://support-bot"),
            "files": ["agent.py", "tools.py"],
        }
    if stub_name == "slack" and operation == "request_approval":
        return {
            "approval_url": "https://slack.example/archives/C-demo/p-approval",
            "status": "requested",
        }
    if stub_name == "local-files" and operation == "read":
        return {
            "path": inputs.get("path", "/sandbox/work"),
            "content": "",
        }
    return {"status": "accepted", "dry_run": dry_run}


def tool_catalog(stub_name: str) -> list[dict]:
    if stub_name == "github":
        names = ["read_repo", "open_pr"]
    elif stub_name == "slack":
        names = ["request_approval"]
    elif stub_name == "local-files":
        names = ["read"]
    else:
        names = ["call"]
    return [
        {
            "name": name,
            "description": f"{stub_name} stub tool {name}",
            "inputSchema": {"type": "object", "additionalProperties": True},
        }
        for name in names
    ]


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8800"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
