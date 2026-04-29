from fastapi.testclient import TestClient

from praetor_api.main import app
from praetor_api.settings import Settings

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


def test_runtime_config_reports_model_defaults() -> None:
    response = TestClient(app).get("/runtime/config", headers=HEADERS)

    assert response.status_code == 200
    assert response.json()["default_model_provider"] == "openai"
    assert response.json()["workflow_execution_mode"] == "sync"


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
