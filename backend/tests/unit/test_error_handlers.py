"""Tests for the global exception handlers + uniform error schema."""
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import install_exception_handlers, request_id_middleware


def _build_app() -> FastAPI:
    app = FastAPI()
    install_exception_handlers(app)
    app.middleware("http")(request_id_middleware)

    class Body(BaseModel):
        n: int

    @app.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    @app.get("/forbidden")
    def forbidden():
        raise HTTPException(status_code=403, detail="nope")

    @app.post("/echo")
    def echo(b: Body):
        return {"n": b.n}

    return app


def test_unhandled_exception_returns_uniform_500():
    client = TestClient(_build_app(), raise_server_exceptions=False)
    r = client.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "internal_error"
    assert "request_id" in body["error"]
    # Internal details must NOT leak to the client.
    assert "kaboom" not in body["error"]["message"]
    assert r.headers["x-request-id"] == body["error"]["request_id"]


def test_http_exception_preserves_status_and_detail():
    client = TestClient(_build_app())
    r = client.get("/forbidden")
    assert r.status_code == 403
    body = r.json()
    assert body["error"]["code"] == "http_403"
    assert body["error"]["message"] == "nope"
    assert "request_id" in body["error"]


def test_validation_error_lists_field_errors():
    client = TestClient(_build_app())
    r = client.post("/echo", json={"n": "not-a-number"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"]["errors"], list)
    assert body["error"]["details"]["errors"][0]["loc"][-1] == "n"


def test_incoming_request_id_is_preserved():
    client = TestClient(_build_app())
    r = client.get("/forbidden", headers={"x-request-id": "test-rid-123"})
    assert r.headers["x-request-id"] == "test-rid-123"
    assert r.json()["error"]["request_id"] == "test-rid-123"
