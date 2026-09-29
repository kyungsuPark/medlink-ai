import pytest
from fastapi.testclient import TestClient

from medlink.api import app, embedding_dependency
from medlink.db import get_session
from medlink.sample import AS_OF


@pytest.fixture
def client(seeded_session, embedder):
    app.dependency_overrides[get_session] = lambda: seeded_session
    app.dependency_overrides[embedding_dependency] = lambda: embedder
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_structured_api_returns_evidence(client):
    response = client.post("/search/structured", json={"as_of": AS_OF})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    assert data["hits"][0]["latest"]["id"] == "L-A001-2"
    assert data["elapsed_ms"] >= 0


@pytest.mark.parametrize(
    "payload",
    [
        {"query": " "},
        {"query": "infection", "top_k": 51},
        {"query": "infection", "as_of": "2026-09-28T12:00:00"},
        {"query": "infection", "lookback_hours": 0},
        {"query": "infection", "patient_id": "P001'; DROP TABLE patients;--"},
        {"query": "infection", "sql": "SELECT 1"},
    ],
)
def test_request_validation(client, payload):
    assert client.post("/search/vector", json=payload).status_code == 422


def test_liveness_and_model_mismatch_readiness(client):
    assert client.get("/health/live").status_code == 200
    # Unit fixtures intentionally use a different model from application config.
    assert client.get("/health/ready").status_code == 503
