from fastapi.testclient import TestClient

from praetor_api.main import app


def test_health_requires_bearer() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 401


def test_health() -> None:
    response = TestClient(app).get(
        "/health",
        headers={"Authorization": "Bearer dev"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
