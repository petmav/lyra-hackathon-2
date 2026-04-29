from __future__ import annotations

import json
import re
from typing import Any

import yaml

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


class OpenApiImportError(ValueError):
    pass


def import_openapi_to_json_stack(
    document: str,
    *,
    stack_id: str,
    provider: str,
    auth_ref: str | None = None,
    selected_operations: list[str] | None = None,
) -> dict[str, Any]:
    doc = _parse_document(document)
    selected = set(selected_operations or [])
    operations = _extract_operations(doc, selected)
    if not operations:
        raise OpenApiImportError("no OpenAPI operations found")
    security = _security_from_doc(doc, operations, provider, auth_ref)
    return {
        "id": stack_id,
        "name": _string_at(doc, ["info", "title"]) or stack_id,
        "provider": provider,
        "version": _string_at(doc, ["info", "version"]) or "2026-04",
        "base_url": _first_server_url(doc),
        "auth": security,
        "operations": {operation["name"]: operation["spec"] for operation in operations},
    }


def _parse_document(document: str) -> dict[str, Any]:
    try:
        parsed = json.loads(document)
    except json.JSONDecodeError:
        parsed = yaml.safe_load(document)
    if not isinstance(parsed, dict):
        raise OpenApiImportError("OpenAPI document must be an object")
    if "paths" not in parsed:
        raise OpenApiImportError("OpenAPI document must include paths")
    return parsed


def _extract_operations(doc: dict[str, Any], selected: set[str]) -> list[dict[str, Any]]:
    paths = _dict_at(doc, ["paths"]) or {}
    out: list[dict[str, Any]] = []
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            key = f"{method.upper()} {path}"
            if selected and key not in selected and str(operation.get("operationId")) not in selected:
                continue
            input_schema = _collect_input_schema(path_item, operation)
            has_body = _dict_at(operation, ["requestBody", "content", "application/json"]) is not None
            if has_body:
                input_schema["body"] = "object"
            out.append(
                {
                    "key": key,
                    "name": _sanitize_name(str(operation.get("operationId") or f"{method}_{path}")),
                    "security": _security_requirements(doc, operation),
                    "spec": {
                        "direction": "in" if method == "get" else "out",
                        "effect_radius": "internal" if method == "get" else "external_trusted",
                        "method": method.upper(),
                        "path": path,
                        "input_schema": input_schema,
                        **({"body_template": "{body}"} if has_body else {}),
                        **({"output_map": output_map} if (output_map := _guess_output_map(operation)) else {}),
                    },
                }
            )
    return out


def _security_from_doc(
    doc: dict[str, Any],
    operations: list[dict[str, Any]],
    provider: str,
    auth_ref: str | None,
) -> dict[str, Any]:
    schemes = _dict_at(doc, ["components", "securitySchemes"]) or {}
    requirements = [requirement for operation in operations for requirement in operation["security"]]
    scheme_name = next((name for requirement in requirements for name in requirement if name in schemes), None)
    if scheme_name is None and schemes:
        scheme_name = next(iter(schemes))
    scheme = schemes.get(scheme_name, {}) if isinstance(schemes.get(scheme_name), dict) else {}
    kind = _auth_kind(scheme)
    scopes = sorted({scope for requirement in requirements for scope_list in requirement.values() for scope in scope_list})
    if not scopes:
        scopes = ["write"] if any(op["spec"]["direction"] == "out" for op in operations) else ["read"]
    return {
        "kind": kind,
        "auth_ref": auth_ref or (f"secret:{provider}_{_sanitize_name(str(scheme_name or kind))}" if kind != "none" else None),
        "scopes": scopes,
        **_auth_metadata(scheme_name, scheme),
    }


def _auth_kind(scheme: dict[str, Any]) -> str:
    scheme_type = str(scheme.get("type") or "").lower()
    if scheme_type in {"oauth2", "openidconnect"}:
        return "oauth2"
    if scheme_type == "apikey":
        return "api_key"
    if scheme_type == "http":
        http_scheme = str(scheme.get("scheme") or "").lower()
        if http_scheme == "basic":
            return "basic"
        if http_scheme == "bearer":
            return "bearer"
    return "none"


def _auth_metadata(scheme_name: str | None, scheme: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if scheme_name:
        metadata["scheme_name"] = scheme_name
    if scheme.get("type") == "apiKey":
        metadata["api_key_in"] = scheme.get("in")
        metadata["api_key_name"] = scheme.get("name")
    if isinstance(scheme.get("flows"), dict):
        metadata["flows"] = scheme["flows"]
    if scheme.get("openIdConnectUrl"):
        metadata["openIdConnectUrl"] = scheme["openIdConnectUrl"]
    return metadata


def _security_requirements(doc: dict[str, Any], operation: dict[str, Any]) -> list[dict[str, list[str]]]:
    raw = operation.get("security", doc.get("security", []))
    if not isinstance(raw, list):
        return []
    requirements: list[dict[str, list[str]]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        requirements.append(
            {
                str(name): [str(scope) for scope in scopes] if isinstance(scopes, list) else []
                for name, scopes in item.items()
            }
        )
    return requirements


def _collect_input_schema(path_item: dict[str, Any], operation: dict[str, Any]) -> dict[str, str]:
    schema: dict[str, str] = {}
    for param in [*path_item.get("parameters", []), *operation.get("parameters", [])]:
        if not isinstance(param, dict):
            continue
        name = str(param.get("name") or "")
        if not name:
            continue
        param_schema = param.get("schema") if isinstance(param.get("schema"), dict) else {}
        schema[name] = str(param_schema.get("type") or "string")
    return schema


def _guess_output_map(operation: dict[str, Any]) -> dict[str, str] | None:
    schema = (
        _dict_at(operation, ["responses", "200", "content", "application/json", "schema"])
        or _dict_at(operation, ["responses", "201", "content", "application/json", "schema"])
    )
    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        return None
    mapped = {key: f"$.{key}" for key in ("id", "key", "url", "web_url", "html_url", "number", "status") if key in properties}
    return mapped or None


def _first_server_url(doc: dict[str, Any]) -> str:
    servers = doc.get("servers", [])
    if isinstance(servers, list) and servers and isinstance(servers[0], dict) and isinstance(servers[0].get("url"), str):
        return servers[0]["url"]
    return "https://api.example.com"


def _string_at(value: Any, path: list[str]) -> str | None:
    found: Any = value
    for key in path:
        found = found.get(key) if isinstance(found, dict) else None
    return found if isinstance(found, str) else None


def _dict_at(value: Any, path: list[str]) -> dict[str, Any] | None:
    found: Any = value
    for key in path:
        found = found.get(key) if isinstance(found, dict) else None
    return found if isinstance(found, dict) else None


def _sanitize_name(value: str) -> str:
    return re.sub(r"(^_+|_+$)", "", re.sub(r"[^a-zA-Z0-9_]+", "_", value)).lower() or "operation"
