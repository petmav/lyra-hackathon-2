from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal
from urllib.request import Request, urlopen

from fastapi import Request, WebSocket

from praetor_api.settings import get_settings

try:
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives import hashes
except ModuleNotFoundError:  # pragma: no cover - production image includes cryptography through audit deps
    padding = None
    rsa = None
    hashes = None

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
    try:
        token = authorization.removeprefix("Bearer ").strip()
        if settings.jwt_jwks_uri or settings.oidc_discovery_url:
            claims = verify_oidc_jwt(token)
        else:
            if not settings.jwt_secret:
                return AuthResult(ok=False, status_code=500, detail="PRAETOR_JWT_SECRET is not configured")
            claims = verify_hs256_jwt(
                token,
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


def verify_oidc_jwt(token: str) -> dict[str, Any]:
    settings = get_settings()
    header, claims, signing_input, signature = _split_jwt(token)
    if header.get("alg") not in {"RS256"}:
        raise ValueError("unsupported JWT algorithm")
    jwks_uri = settings.jwt_jwks_uri or _oidc_metadata()["jwks_uri"]
    key = _select_jwk(_jwks(jwks_uri), str(header.get("kid") or ""))
    _verify_rs256(signing_input, signature, key)
    _validate_claims(claims, issuer=settings.jwt_issuer, audience=settings.jwt_audience)
    return claims


def verify_hs256_jwt(
    token: str,
    secret: str,
    *,
    issuer: str | None = None,
    audience: str | None = None,
) -> dict[str, Any]:
    header, claims, signing_input, signature = _split_jwt(token)
    if header.get("alg") != "HS256":
        raise ValueError("unsupported JWT algorithm")
    expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError("invalid JWT signature")
    _validate_claims(claims, issuer=issuer, audience=audience)
    return claims


def _validate_claims(
    claims: dict[str, Any],
    *,
    issuer: str | None = None,
    audience: str | None = None,
) -> None:
    now = int(time.time())
    if isinstance(claims.get("exp"), int | float) and now >= int(claims["exp"]):
        raise ValueError("JWT is expired")
    if isinstance(claims.get("nbf"), int | float) and now < int(claims["nbf"]):
        raise ValueError("JWT is not yet valid")
    if issuer and claims.get("iss") != issuer:
        raise ValueError("invalid JWT issuer")
    if audience and not _audience_matches(claims.get("aud"), audience):
        raise ValueError("invalid JWT audience")


def _split_jwt(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid JWT shape")
    header = _json_b64decode(parts[0])
    claims = _json_b64decode(parts[1])
    return header, claims, f"{parts[0]}.{parts[1]}".encode(), _b64decode(parts[2])


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


@lru_cache(maxsize=8)
def _oidc_metadata_cached(discovery_url: str, issuer: str | None, cache_bucket: int) -> dict[str, Any]:
    metadata = _fetch_json(discovery_url)
    if not isinstance(metadata.get("jwks_uri"), str):
        raise ValueError("OIDC discovery metadata missing jwks_uri")
    if issuer and metadata.get("issuer") != issuer:
        raise ValueError("OIDC discovery issuer mismatch")
    return metadata


def _oidc_metadata() -> dict[str, Any]:
    settings = get_settings()
    if not settings.oidc_discovery_url:
        raise ValueError("PRAETOR_OIDC_DISCOVERY_URL is not configured")
    return _oidc_metadata_cached(
        settings.oidc_discovery_url,
        settings.jwt_issuer,
        _cache_bucket(settings.oidc_cache_seconds),
    )


@lru_cache(maxsize=16)
def _jwks_cached(jwks_uri: str, cache_bucket: int) -> dict[str, Any]:
    jwks = _fetch_json(jwks_uri)
    keys = jwks.get("keys")
    if not isinstance(keys, list):
        raise ValueError("JWKS missing keys")
    return jwks


def _jwks(jwks_uri: str) -> dict[str, Any]:
    return _jwks_cached(jwks_uri, _cache_bucket(get_settings().oidc_cache_seconds))


def _cache_bucket(seconds: int) -> int:
    return int(time.time()) // max(1, seconds)


def _fetch_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    with urlopen(request, timeout=5) as response:
        parsed = json.loads(response.read())
    if not isinstance(parsed, dict):
        raise ValueError("metadata response must be an object")
    return parsed


def _select_jwk(jwks: dict[str, Any], kid: str) -> dict[str, Any]:
    keys = jwks.get("keys", [])
    for key in keys:
        if isinstance(key, dict) and (not kid or key.get("kid") == kid) and key.get("kty") == "RSA":
            return key
    raise ValueError("matching JWKS key not found")


def _verify_rs256(signing_input: bytes, signature: bytes, jwk: dict[str, Any]) -> None:
    if rsa is None or padding is None or hashes is None:
        raise ValueError("cryptography package is required for JWKS verification")
    if jwk.get("alg") not in {None, "RS256"}:
        raise ValueError("unsupported JWKS key algorithm")
    modulus = int.from_bytes(_b64decode(str(jwk.get("n") or "")), "big")
    exponent = int.from_bytes(_b64decode(str(jwk.get("e") or "")), "big")
    public_key = rsa.RSAPublicNumbers(exponent, modulus).public_key()
    try:
        public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
    except Exception as exc:
        raise ValueError("invalid JWT signature") from exc


def _json_b64decode(value: str) -> dict[str, Any]:
    decoded = _b64decode(value)
    data = json.loads(decoded)
    if not isinstance(data, dict):
        raise ValueError("JWT segment is not an object")
    return data


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
