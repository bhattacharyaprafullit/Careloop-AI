"""M0 smoke tests: app boots, /healthz works, request IDs and error envelope are in place."""
import logging

from fastapi.testclient import TestClient

from app.main import create_app

logger = logging.getLogger(__name__)


def _client() -> TestClient:
    return TestClient(create_app())


def test_healthz_ok() -> None:
    res = _client().get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_request_id_generated_and_echoed() -> None:
    client = _client()
    assert len(client.get("/healthz").headers["X-Request-ID"]) == 32
    res = client.get("/healthz", headers={"X-Request-ID": "abc123"})
    assert res.headers["X-Request-ID"] == "abc123"


def test_unknown_route_uses_error_envelope() -> None:
    res = _client().get("/api/v1/nope", headers={"X-Request-ID": "rid-1"})
    assert res.status_code == 404
    err = res.json()["error"]
    assert err == {"code": "not_found", "message": "Not Found", "request_id": "rid-1"}


def test_cors_only_allowed_origins() -> None:
    client = _client()
    ok = client.options(
        "/healthz",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    bad = client.options(
        "/healthz",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in bad.headers
