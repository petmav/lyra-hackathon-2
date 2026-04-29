from fastapi.testclient import TestClient

from praetor_api.main import app
from praetor_api.services.auth import extract_roles, has_role, verify_hs256_jwt
from praetor_api.services.secrets import resolve_secret, secret_status
from praetor_api.settings import Settings, get_settings

import base64
import hashlib
import hmac
import json
import time

HEADERS = {"Authorization": "Bearer dev"}


def test_health_reports_demo_data_backend() -> None:
    response = TestClient(app).get("/health", headers=HEADERS)

    assert response.status_code == 200
    assert response.json()["data_mode"] == "demo"
    assert response.json()["data_backend"] == "in_memory"
    assert response.headers["X-Praetor-Data-Mode"] == "demo"


def test_settings_maps_production_to_postgres_backend() -> None:
    settings = Settings(PRAETOR_DATA_MODE="production")

    assert settings.data_mode == "production"
    assert settings.data_backend == "postgres"
    assert settings.workflow_execution_mode == "sync"


def test_settings_accepts_queued_workflow_execution() -> None:
    settings = Settings(PRAETOR_WORKFLOW_EXECUTION_MODE="queued")

    assert settings.workflow_execution_mode == "queued"


def test_settings_accepts_jwt_auth_and_vault_secret_backend() -> None:
    settings = Settings(PRAETOR_AUTH_MODE="jwt", PRAETOR_SECRET_BACKEND="vault")

    assert settings.auth_mode == "jwt"
    assert settings.secret_backend == "vault"
    assert settings.openai_api_key_ref == "secret:openai_api_key"


def test_runtime_config_reports_model_defaults() -> None:
    response = TestClient(app).get("/runtime/config", headers=HEADERS)

    assert response.status_code == 200
    assert response.json()["default_model_provider"] == "openai"
    assert response.json()["workflow_execution_mode"] == "sync"
    assert response.json()["auth_mode"] == "dev_bearer"
    assert response.json()["secret_backend"] == "env"


def test_demo_workflow_drain_is_noop() -> None:
    response = TestClient(app).post(
        "/workflow-runs:drain",
        headers=HEADERS,
        json={"limit": 3},
    )

    assert response.status_code == 200
    assert response.json() == {"processed": [], "count": 0}


def test_runtime_readiness_reports_models_and_integrations() -> None:
    response = TestClient(app).get("/runtime/readiness", headers=HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_model_mode"] == "auto"
    assert payload["models"]["providers"]
    assert payload["integrations"]["json_stack_count"] >= 1


def test_jwt_auth_mode_enforces_rbac(monkeypatch) -> None:
    monkeypatch.setenv("PRAETOR_AUTH_MODE", "jwt")
    monkeypatch.setenv("PRAETOR_JWT_SECRET", "unit-secret")
    monkeypatch.setenv("PRAETOR_JWT_ISSUER", "issuer")
    monkeypatch.setenv("PRAETOR_JWT_AUDIENCE", "praetor")
    get_settings.cache_clear()

    token = _jwt(
        {
            "sub": "alice",
            "iss": "issuer",
            "aud": "praetor",
            "roles": ["viewer"],
            "exp": int(time.time()) + 120,
        },
        "unit-secret",
    )
    response = TestClient(app).get("/health", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.headers["X-Praetor-Subject"] == "alice"

    denied = TestClient(app).post("/models:check", headers={"Authorization": f"Bearer {token}"}, json={"live": False})
    assert denied.status_code == 403

    get_settings.cache_clear()


def test_hs256_jwt_verification_and_role_hierarchy() -> None:
    token = _jwt({"sub": "alice", "roles": ["operator"], "exp": int(time.time()) + 120}, "secret")

    claims = verify_hs256_jwt(token, "secret")

    assert claims["sub"] == "alice"
    assert has_role(extract_roles(claims), "viewer") is True
    assert has_role(extract_roles(claims), "admin") is False


def test_secret_resolution_reports_backend(monkeypatch) -> None:
    monkeypatch.setenv("PRAETOR_SECRET_BACKEND", "env")
    monkeypatch.setenv("UNIT_TEST_TOKEN", "secret-value")
    get_settings.cache_clear()

    assert resolve_secret("secret:unit_test_token") == "secret-value"
    status = secret_status("secret:unit_test_token")
    assert status["backend"] == "env"
    assert status["configured"] is True
    get_settings.cache_clear()


def _jwt(claims: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _b64json(header)
    encoded_claims = _b64json(claims)
    signing_input = f"{encoded_header}.{encoded_claims}".encode()
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_claims}.{_b64(signature)}"


def _b64json(value: dict) -> str:
    return _b64(json.dumps(value, separators=(",", ":")).encode())


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")
