from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tarfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MARKER = "PRAETOR_AGENT_STEP_OUTPUT="
MAX_FILE_BYTES = 512 * 1024
SOURCE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".mjs",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".ts",
    ".tsx",
}
TEXT_SUFFIXES = SOURCE_SUFFIXES | {".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".ini", ".env", ".example"}


def main() -> None:
    payload = _manifest_payload()
    github = payload.get("github") if isinstance(payload.get("github"), dict) else {}
    documents = _decode_documents(payload.get("documents", []))
    repo_dir = Path("/tmp/praetor/repo")
    repo_dir.mkdir(parents=True, exist_ok=True)

    try:
        repo_meta = _download_github_tarball(github, repo_dir)
        source_files = _read_repo_files(repo_dir)
        findings = _scan(source_files, documents, payload)
        status = "changes_requested" if findings else "approved"
        output = {
            "ok": True,
            "model_provider": str(payload.get("model_provider") or os.getenv("PRAETOR_MODEL_PROVIDER") or "openai"),
            "model": str(payload.get("model") or os.getenv("PRAETOR_MODEL") or "gpt-5.4-mini"),
            "model_call": {
                "ok": True,
                "mode": "sandbox_static_verifier",
                "provider": "praetor-sandbox",
                "model": "deterministic-code-compliance-rules",
                "configured": True,
                "text": f"Downloaded {repo_meta['owner']}/{repo_meta['repo']} and scanned {len(source_files)} files against {len(documents)} corpus documents.",
                "usage": {},
            },
            "repository": repo_meta | {"files_scanned": len(source_files)},
            "compliance_status": status,
            "verification_summary": {
                "corpus_documents_loaded": len(documents),
                "source_files_scanned": len(source_files),
                "rules_evaluated": _enabled_rule_names(documents),
                "findings_count": len(findings),
            },
            "findings": findings,
            "change_requests": [_change_request(finding) for finding in findings],
            "tools": [
                {"name": "github_download", "status": "ok", "items": 1},
                {"name": "corpus_load", "status": "ok", "items": len(documents)},
                {"name": "static_code_scan", "status": "ok", "items": len(source_files)},
                {"name": "emit_finding", "status": "ok", "items": len(findings)},
            ],
            "memory_writes": [
                {
                    "key": f"{payload.get('workflow_run_id', 'workflow')}:{payload.get('step_id', 'sandbox_verify')}:github_code_compliance",
                    "provenance": "sandbox://github_code_compliance",
                }
            ],
        }
    except Exception as exc:  # noqa: BLE001 - surfaced as structured sandbox failure.
        output = {
            "ok": False,
            "model_provider": str(payload.get("model_provider") or os.getenv("PRAETOR_MODEL_PROVIDER") or "openai"),
            "model": str(payload.get("model") or os.getenv("PRAETOR_MODEL") or "gpt-5.4-mini"),
            "model_call": {
                "ok": False,
                "mode": "sandbox_static_verifier",
                "provider": "praetor-sandbox",
                "model": "deterministic-code-compliance-rules",
                "configured": True,
                "error": f"{exc.__class__.__name__}: {exc}",
                "text": "",
                "usage": {},
            },
            "repository": github,
            "compliance_status": "verification_failed",
            "verification_summary": {"error": f"{exc.__class__.__name__}: {exc}"},
            "findings": [],
            "change_requests": [],
            "tools": [{"name": "github_download", "status": "failed"}],
            "memory_writes": [],
        }

    print("praetor github code compliance verifier completed", flush=True)
    print(f"{MARKER}{json.dumps(output, sort_keys=True)}", flush=True)
    if not output.get("ok"):
        raise SystemExit(2)


def _manifest_payload() -> dict[str, Any]:
    raw = os.getenv("PRAETOR_AGENT_MANIFEST_JSON", "{}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _download_github_tarball(github: dict[str, Any], target: Path) -> dict[str, Any]:
    owner = str(github.get("owner") or "").strip()
    repo = str(github.get("repo") or "").strip().removesuffix(".git")
    ref = str(github.get("ref") or "main").strip() or "main"
    if not owner or not repo:
        raise ValueError("github owner and repo are required")
    url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{ref}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "praetor-sandbox-code-compliance",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=45) as response:
            tar_bytes = response.read()
            resolved_url = response.geturl()
    except HTTPError as exc:
        raise RuntimeError(f"GitHub download failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub download failed: {exc.reason}") from exc

    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as archive:
        _safe_extract(archive, target)
    return {"owner": owner, "repo": repo, "ref": ref, "download_url": resolved_url, "bytes": len(tar_bytes)}


def _safe_extract(archive: tarfile.TarFile, target: Path) -> None:
    root = target.resolve()
    for member in archive.getmembers():
        name_parts = Path(member.name).parts
        relative = Path(*name_parts[1:]) if len(name_parts) > 1 else Path()
        if not relative or member.isdir():
            continue
        destination = (target / relative).resolve()
        if root not in destination.parents and destination != root:
            raise RuntimeError(f"tar member escapes target: {member.name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            continue
        destination.write_bytes(source.read())


def _decode_documents(raw_documents: Any) -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    if not isinstance(raw_documents, list):
        return documents
    for raw in raw_documents:
        if not isinstance(raw, dict):
            continue
        encoded = raw.get("base64")
        if not isinstance(encoded, str):
            continue
        try:
            text = base64.b64decode(encoded).decode("utf-8", errors="replace")
        except (ValueError, UnicodeDecodeError):
            continue
        documents.append(
            {
                "document_id": str(raw.get("document_id") or ""),
                "corpus_id": str(raw.get("corpus_id") or ""),
                "title": str(raw.get("title") or raw.get("source_uri") or "corpus document"),
                "text": text,
            }
        )
    return documents


def _read_repo_files(repo_dir: Path) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for path in repo_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in {".git", "node_modules", ".next", "dist", "build", "__pycache__"} for part in path.parts):
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files.append({"path": path.relative_to(repo_dir).as_posix(), "text": text})
    return files


def _scan(files: list[dict[str, str]], documents: list[dict[str, str]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    corpus_text = "\n".join(doc["text"] for doc in documents).lower()
    findings: list[dict[str, Any]] = []
    if _rule_enabled(corpus_text, ["email", "recipient", "domain", "allowlist"]):
        findings.extend(_scan_email_recipient_controls(files, documents, payload))
    if _rule_enabled(corpus_text, ["secret", "api key", "credential", "token"]):
        findings.extend(_scan_hardcoded_secrets(files, documents, payload))
    if _rule_enabled(corpus_text, ["input validation", "prompt injection", "eval", "command"]):
        findings.extend(_scan_dangerous_execution(files, documents, payload))
    return findings


def _rule_enabled(corpus_text: str, terms: list[str]) -> bool:
    if not corpus_text:
        return True
    return any(term in corpus_text for term in terms)


def _enabled_rule_names(documents: list[dict[str, str]]) -> list[str]:
    corpus_text = "\n".join(doc["text"] for doc in documents).lower()
    names = []
    if _rule_enabled(corpus_text, ["email", "recipient", "domain", "allowlist"]):
        names.append("email_recipient_domain_guard")
    if _rule_enabled(corpus_text, ["secret", "api key", "credential", "token"]):
        names.append("hardcoded_secret_detection")
    if _rule_enabled(corpus_text, ["input validation", "prompt injection", "eval", "command"]):
        names.append("dangerous_execution_detection")
    return names


def _scan_email_recipient_controls(files: list[dict[str, str]], documents: list[dict[str, str]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    for file in files:
        text = file["text"]
        lower = text.lower()
        if "send_email" not in lower and "sendmail" not in lower and "smtp" not in lower:
            continue
        has_recipient = "recipient" in lower or "to:" in lower or ".send(" in lower
        has_guard = any(term in lower for term in ("allowed_domain", "allowed_domains", "allowlist", "domain", "endswith(", "split('@')", "rsplit('@'"))
        if has_recipient and not has_guard:
            findings.append(
                _finding(
                    payload,
                    "email-recipient-domain-guard",
                    "Email sending path lacks an explicit recipient-domain guard",
                    f"{file['path']} appears to send email but no allowlist/domain validation pattern was found in that file.",
                    "high",
                    0.86,
                    documents,
                    [file["path"]],
                )
            )
    return findings


def _scan_hardcoded_secrets(files: list[dict[str, str]], documents: list[dict[str, str]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    secret_pattern = re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"\n]{12,}['\"]")
    findings = []
    for file in files:
        if file["path"].endswith((".md", ".txt")):
            continue
        if secret_pattern.search(file["text"]):
            findings.append(
                _finding(
                    payload,
                    "hardcoded-secret",
                    "Possible hardcoded credential in repository",
                    f"{file['path']} contains a token-like assignment that should be moved to managed secrets.",
                    "high",
                    0.8,
                    documents,
                    [file["path"]],
                )
            )
    return findings


def _scan_dangerous_execution(files: list[dict[str, str]], documents: list[dict[str, str]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    patterns = ["eval(", "exec(", "shell=True", "dangerouslySetInnerHTML"]
    findings = []
    for file in files:
        hits = [pattern for pattern in patterns if pattern in file["text"]]
        if hits:
            findings.append(
                _finding(
                    payload,
                    "dangerous-execution",
                    "Potentially dangerous execution primitive requires validation controls",
                    f"{file['path']} contains {', '.join(hits)}; verify input validation, sanitisation, and approval controls.",
                    "medium",
                    0.72,
                    documents,
                    [file["path"]],
                )
            )
    return findings


def _finding(
    payload: dict[str, Any],
    suffix: str,
    title: str,
    description: str,
    severity: str,
    confidence: float,
    documents: list[dict[str, str]],
    files: list[str],
) -> dict[str, Any]:
    base = str(payload.get("finding_id") or "fnd_sandbox")
    source_key = "|".join(files) or title
    source_hash = hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:10]
    return {
        "id": f"{base}_{suffix}_{source_hash}".replace("-", "_")[:120],
        "title": title,
        "description": description,
        "severity": severity,
        "confidence": confidence,
        "obligations_cited": [
            f"urn:praetor:corpus:{doc['corpus_id']}" for doc in documents[:3] if doc.get("corpus_id")
        ],
        "documents_cited": [
            _document_citation(doc)
            for doc in documents[:3]
            if doc.get("document_id") or doc.get("corpus_id") or doc.get("title")
        ],
        "status": "open",
        "source_files": files,
    }


def _change_request(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "finding_id": finding["id"],
        "title": f"Remediate: {finding['title']}",
        "body": finding["description"],
        "source_files": finding.get("source_files", []),
    }


def _document_citation(document: dict[str, str]) -> str:
    corpus_id = document.get("corpus_id") or "corpus"
    document_id = document.get("document_id") or document.get("title") or "document"
    return f"urn:praetor:document:{corpus_id}:{document_id}"


if __name__ == "__main__":
    main()
