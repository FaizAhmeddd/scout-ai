from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_reports_dependencies():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] in {"ok", "unreachable"}
    assert body["gemini"] in {"configured", "missing key"}


def test_protected_routes_require_a_token():
    assert client.get("/api/v1/videos").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401
