from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import Request, WebSocket

from praetor_api.settings import get_settings

ROLE_ORDER = {"viewer": 0, "operator": 1, "admin": 2}


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    status_code: int = 401
    detail: str = "unauthorized"
    subject: str | None = None
    roles: tuple[str, ...] = ()


def authorize_request(request: Request) -> AuthResult:
    settings = get_settings()
    if settings.auth_mode == "disabled":
        return AuthResult(ok=True, subject="auth-disabled", roles=("admin",))
    authorization = request.headers.get("authorization", "")
    required_role = _required_role(request.method)
    if settings.auth_mode == "dev_bearer":
        return _authorize_dev_bearer(authorization, required_role)
    if settings.auth_mode == "jwt":
        return _authorize_jwt(authorization, required_role)
    return AuthResult(ok=False, status_code=500, detail="unsupported auth mode")


def authorize_websocket(websocket: WebSocket) -> AuthResult:
    settings = get_settings()
    if settings.auth_mode == "disabled":
        return AuthResult(ok=True, subject="auth-disabled", roles=("admin",))
    token = websocket.query_params.get("token")
    authorization = websocket.headers.get("authorization", "")
    if settings.auth_mode == "dev_bearer" and token:
        authorization = f"Bearer {token}"
    return _authorize_dev_bearer(authorization, "viewer") if settings.auth_mode == "dev_bearer" else _authorize_jwt(authorization, "viewer")


def _authorize_dev_bearer(authorization: str, required_role: str) -> AuthResult:
    settings = get_settings()
    if authorization != f"Bearer {settings.dev_bearer}":
        return AuthResult(ok=False, detail="missing or invalid bearer token")
    return AuthResult(ok=True, subject="dev", roles=("admin", required_role))


def _authorize_jwt(authorization: str, required_role: str) -> AuthResult:
    if not authorization.startswith("Bearer "):
        return AuthResult(ok=False, detail="missing bearer token")
    settings = get_settings()
    if not settings.jwt_secret:
        return AuthResult(ok=False, status_code=500, detail="PRAETOR_JWT_SECRET is not configured")
    try:
        claims = verify_hs256_jwt(
            authorization.removeprefix("Bearer ").strip(),
            settings.jwt_secret,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except ValueError as exc:
        return AuthResult(ok=False, detail=str(exc))
    roles = extract_roles(claims)
    if not has_role(roles, required_role):
        return AuthResult(ok=False, status_code=403, detail=f"missing required role: {required_role}")
    return AuthResult(ok=True, subject=str(claims.get("sub") or "unknown"), roles=tuple(sorted(roles)))


def verify_hs256_jwt(
    token: str,
    secret: str,
    *,
    issuer: str | None = None,
    audience: str | None = None,
) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid JWT shape")
    header = _json_b64decode(parts[0])
    claims = _json_b64decode(parts[1])
    if header.get("alg") != "HS256":
        raise ValueError("unsupported JWT algorithm")
    signing_input = f"{parts[0]}.{parts[1]}".encode()
    expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    actual = _b64decode(parts[2])
    if not hmac.compare_digest(expected, actual):
        raise ValueError("invalid JWT signature")
    now = int(time.time())
    if isinstance(claims.get("exp"), int | float) and now >= int(claims["exp"]):
        raise ValueError("JWT is expired")
    if isinstance(claims.get("nbf"), int | float) and now < int(claims["nbf"]):
        raise ValueError("JWT is not yet valid")
    if issuer and claims.get("iss") != issuer:
        raise ValueError("invalid JWT issuer")
    if audience and not _audience_matches(claims.get("aud"), audience):
        raise ValueError("invalid JWT audience")
    return claims


def extract_roles(claims: dict[str, Any]) -> set[str]:
    roles: set[str] = set()
    for key in ("roles", "role", "groups"):
        value = claims.get(key)
        if isinstance(value, str):
            roles.update(part for part in value.replace(",", " ").split() if part)
        elif isinstance(value, list):
            roles.update(str(part) for part in value if part)
    scope = claims.get("scope") or claims.get("scp")
    if isinstance(scope, str):
        roles.update(part.removeprefix("praetor:") for part in scope.split() if part)
    return roles


def has_role(roles: set[str], required_role: str) -> bool:
    if required_role in roles:
        return True
    required_rank = ROLE_ORDER.get(required_role, 999)
    return any(ROLE_ORDER.get(role, -1) >= required_rank for role in roles)


def _required_role(method: str) -> str:
    settings = get_settings()
    return settings.jwt_required_read_role if method in {"GET", "HEAD", "OPTIONS"} else settings.jwt_required_write_role


def _audience_matches(value: Any, expected: str) -> bool:
    if isinstance(value, str):
        return value == expected
    if isinstance(value, list):
        return expected in value
    return False


def _json_b64decode(value: str) -> dict[str, Any]:
    decoded = _b64decode(value)
    data = json.loads(decoded)
    if not isinstance(data, dict):
        raise ValueError("JWT segment is not an object")
    return data


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
