from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_rejects_oversized_and_compressed_auth_bodies():
    oversized = client.post("/auth/login", content=b"{}", headers={"Content-Length": str(3 * 1024 * 1024)})
    assert oversized.status_code == 413
    compressed = client.post("/auth/login", content=b"{}", headers={"Content-Encoding": "gzip"})
    assert compressed.status_code == 415


def test_blocks_foreign_browser_origin_and_sets_response_headers():
    denied = client.post("/auth/login", json={}, headers={"Origin": "https://foreign.example.invalid"})
    assert denied.status_code == 403
    response = client.get("/health/live")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_streamed_body_limit_does_not_depend_on_content_length():
    def body():
        yield b"x" * (1024 * 1024)
        yield b"x" * (1024 * 1024 + 1)
    response = client.post("/auth/login", content=body(), headers={"Content-Type": "application/json"})
    assert response.status_code == 413
