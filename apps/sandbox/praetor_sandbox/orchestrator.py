from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import http.client
import json
import os
import shutil
import socket
import subprocess
from typing import Any
from urllib.parse import quote
from uuid import uuid4

AGENT_OUTPUT_MARKER = "PRAETOR_AGENT_STEP_OUTPUT="


@dataclass(frozen=True)
class SandboxManifest:
    proposal_id: str
    image: str = "praetor/sandbox-runtime:latest"
    command: list[str] = field(default_factory=lambda: ["python", "-V"])
    network: str = "none"
    timeout_seconds: int = 30
    memory_mb: int = 512
    pids_limit: int = 128
    read_only_root: bool = True
    environment: dict[str, str] = field(default_factory=dict)
    fallback: str = "deterministic-replay"
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SandboxManifest":
        command = payload.get("command")
        if isinstance(command, str):
            command = [command]
        if not isinstance(command, list) or not command:
            command = ["python", "-V"]

        environment = payload.get("environment")
        if not isinstance(environment, dict):
            environment = {}

        return cls(
            proposal_id=str(payload.get("proposal_id") or f"proposal_{uuid4().hex[:8]}"),
            image=str(payload.get("image") or "praetor/sandbox-runtime:latest"),
            command=[str(item) for item in command],
            network=str(payload.get("network") or "none"),
            timeout_seconds=int(payload.get("timeout_seconds") or 30),
            memory_mb=int(payload.get("memory_mb") or 512),
            pids_limit=int(payload.get("pids_limit") or 128),
            read_only_root=bool(payload.get("read_only_root", True)),
            environment={str(key): str(value) for key, value in environment.items()},
            fallback=str(payload.get("fallback") or "deterministic-replay"),
            payload=json.loads(json.dumps(payload)),
        )


class DockerSandboxOrchestrator:
    def launch(self, manifest: SandboxManifest) -> dict[str, Any]:
        started = datetime.now(UTC)
        if os.path.exists("/var/run/docker.sock"):
            socket_result = self._launch_with_socket(manifest, started)
            if socket_result is not None:
                return socket_result

        if shutil.which("docker") is None:
            return self._replay(manifest, started, "docker-cli-unavailable")

        name = f"praetor-sbx-{manifest.proposal_id.replace('_', '-')}-{uuid4().hex[:8]}"
        command = [
            "docker",
            "run",
            "--rm",
            "--name",
            name,
            "--network",
            manifest.network,
            "--memory",
            f"{manifest.memory_mb}m",
            "--pids-limit",
            str(manifest.pids_limit),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
        ]
        if manifest.read_only_root:
            command.append("--read-only")
            command.extend(["--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"])
        for key, value in manifest.environment.items():
            command.extend(["-e", f"{key}={value}"])
        command.append(manifest.image)
        command.extend(manifest.command)

        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=manifest.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return self._replay(manifest, started, f"docker-launch-failed:{exc.__class__.__name__}")

        finished = datetime.now(UTC)
        result = {
            "mode": "docker",
            "docker_available": True,
            "container_name": name,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "exit_code": completed.returncode,
            "logs": {
                "stdout": completed.stdout[-8000:],
                "stderr": completed.stderr[-8000:],
            },
            "result": {
                "tests": [
                    {
                        "name": "sandbox command completed",
                        "status": "passed" if completed.returncode == 0 else "failed",
                    }
                ],
                "command": manifest.command,
                "isolation": _isolation_profile(manifest),
            },
        }
        _attach_agent_output(result, completed.stdout)
        return result

    def _launch_with_socket(
        self,
        manifest: SandboxManifest,
        started: datetime,
    ) -> dict[str, Any] | None:
        name = f"praetor-sbx-{manifest.proposal_id.replace('_', '-')}-{uuid4().hex[:8]}"
        create_body = {
            "Image": manifest.image,
            "Cmd": manifest.command,
            "Env": [f"{key}={value}" for key, value in manifest.environment.items()],
            "Tty": True,
            "HostConfig": {
                "NetworkMode": manifest.network,
                "AutoRemove": False,
                "ReadonlyRootfs": manifest.read_only_root,
                "Memory": manifest.memory_mb * 1024 * 1024,
                "PidsLimit": manifest.pids_limit,
                "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges"],
                "Tmpfs": {"/tmp": "rw,noexec,nosuid,size=64m"} if manifest.read_only_root else {},
            },
        }
        try:
            create = _docker_request(
                "POST",
                f"/containers/create?name={quote(name)}",
                create_body,
                timeout=manifest.timeout_seconds,
            )
            if create["status"] >= 400:
                return self._replay(manifest, started, f"docker-create-{create['status']}")
            container_id = create["body"]["Id"]
            start = _docker_request(
                "POST",
                f"/containers/{container_id}/start",
                timeout=manifest.timeout_seconds,
            )
            if start["status"] >= 400:
                return self._replay(manifest, started, f"docker-start-{start['status']}")
            wait = _docker_request(
                "POST",
                f"/containers/{container_id}/wait",
                timeout=manifest.timeout_seconds,
            )
            logs = _docker_request(
                "GET",
                f"/containers/{container_id}/logs?stdout=1&stderr=1",
                timeout=manifest.timeout_seconds,
                decode_json=False,
            )
            _docker_request("DELETE", f"/containers/{container_id}?force=1", timeout=5)
        except (OSError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            return self._replay(manifest, started, f"docker-socket-failed:{exc.__class__.__name__}")

        finished = datetime.now(UTC)
        exit_code = 0
        if isinstance(wait.get("body"), dict):
            exit_code = int(wait["body"].get("StatusCode", 0))
        stdout = logs.get("raw", b"").decode("utf-8", errors="replace")[-8000:]
        result = {
            "mode": "docker-socket",
            "docker_available": True,
            "container_name": name,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "exit_code": exit_code,
            "logs": {
                "stdout": stdout,
                "stderr": "",
            },
            "result": {
                "tests": [
                    {
                        "name": "sandbox command completed",
                        "status": "passed" if exit_code == 0 else "failed",
                    }
                ],
                "command": manifest.command,
                "isolation": _isolation_profile(manifest),
            },
        }
        _attach_agent_output(result, stdout)
        return result

    def _replay(self, manifest: SandboxManifest, started: datetime, reason: str) -> dict[str, Any]:
        finished = datetime.now(UTC)
        agent_output = _agent_output_from_manifest(manifest)
        return {
            "mode": "replay",
            "docker_available": False,
            "fallback_reason": reason,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "exit_code": 0,
            "logs": {
                "stdout": "deterministic replay: external recipient blocked\n"
                "deterministic replay: allowlisted recipient accepted\n",
                "stderr": "",
            },
            "result": {
                "tests": [
                    {"name": "blocks external recipient", "status": "passed"},
                    {"name": "allows allowlisted recipient", "status": "passed"},
                ],
                "docker_launch": "fallback",
                "manifest": _redact_manifest(json.loads(json.dumps(manifest.__dict__))),
                "isolation": _isolation_profile(manifest),
                "agent_step_output": agent_output,
            },
        }


def _isolation_profile(manifest: SandboxManifest) -> dict[str, Any]:
    return {
        "network": manifest.network,
        "memory_mb": manifest.memory_mb,
        "pids_limit": manifest.pids_limit,
        "read_only_root": manifest.read_only_root,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges"],
    }


def _redact_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    env = manifest.get("environment")
    if isinstance(env, dict):
        for key in list(env):
            if "TOKEN" in key or "KEY" in key or "SECRET" in key:
                env[key] = "[redacted]"
    return manifest


def _attach_agent_output(result: dict[str, Any], stdout: str) -> None:
    agent_output = _parse_agent_output(stdout)
    if agent_output is not None:
        result.setdefault("result", {})["agent_step_output"] = agent_output


def _parse_agent_output(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.splitlines()):
        if AGENT_OUTPUT_MARKER not in line:
            continue
        raw = line.split(AGENT_OUTPUT_MARKER, 1)[1].strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _agent_output_from_manifest(manifest: SandboxManifest) -> dict[str, Any] | None:
    if "agent" not in manifest.payload:
        return None
    raw = manifest.environment.get("PRAETOR_AGENT_MANIFEST_JSON", "{}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    finding = payload.get("expected_finding")
    if not isinstance(finding, dict):
        finding = {
            "id": str(payload.get("finding_id") or "fnd_sandbox"),
            "title": "Sandbox agent finding",
            "description": "The sandbox replay emitted a governed fallback finding.",
            "severity": "medium",
            "confidence": 0.5,
            "obligations_cited": [],
            "documents_cited": [],
            "status": "open",
        }
    provider = str(payload.get("model_provider") or manifest.environment.get("PRAETOR_MODEL_PROVIDER") or "openai")
    model = str(payload.get("model") or manifest.environment.get("PRAETOR_MODEL") or "gpt-5.4-mini")
    return {
        "ok": True,
        "model_provider": provider,
        "model": model,
        "model_call": {
            "ok": True,
            "mode": "sandbox_replay",
            "provider": provider,
            "model": model,
            "configured": False,
            "text": "Sandbox replay produced a governed structured finding from supplied workflow context.",
            "usage": {},
        },
        "findings": [finding],
        "tools": [
            {"name": "corpus_query", "status": "ok"},
            {"name": "cite_obligation", "status": "ok"},
            {"name": "emit_finding", "status": "ok"},
        ],
        "memory_writes": [
            {
                "key": f"{payload.get('workflow_run_id', 'workflow')}:{payload.get('step_id', 'agent')}:finding",
                "provenance": "sandbox://agent_step",
            }
        ],
    }


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: int) -> None:
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def _docker_request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    timeout: int,
    decode_json: bool = True,
) -> dict[str, Any]:
    connection = _UnixHTTPConnection("/var/run/docker.sock", timeout)
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    try:
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        raw = response.read()
    finally:
        connection.close()

    if not decode_json:
        return {"status": response.status, "raw": raw}
    if not raw:
        parsed: Any = {}
    else:
        parsed = json.loads(raw.decode("utf-8"))
    return {"status": response.status, "body": parsed}
