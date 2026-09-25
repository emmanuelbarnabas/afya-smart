"""Tests za health endpoint — hazihitaji database."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "afya-smart-api"


def test_openapi_schema():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "Afya Smart API" in response.json()["info"]["title"]
