import httpx
from fastapi.testclient import TestClient

from app import auth, db
from app.config import settings
from app.main import app
from tests.test_prices import chart

client = TestClient(app)
CLIENT_UUID = "11111111-1111-4111-8111-111111111111"


def client_headers(**extra):
    return {"X-Client-UUID": CLIENT_UUID, **extra}


def test_config_and_health():
    j = client.get("/api/health").json()
    assert j["ok"] is True and j["version"]
    cfg = client.get("/api/config", headers=client_headers()).json()
    assert {b["id"] for b in cfg["brokers"]} >= {"zerodha", "groww", "upstox", "indmoney", "generic"}


def test_quotes_endpoint(mock_http):
    mock_http.add("RELIANCE.NS", httpx.Response(200, json=chart(110, 100)))
    mock_http.add("INR%3DX", httpx.Response(200, json=chart(84.2, 84.0)))
    mock_http.add("INR=X", httpx.Response(200, json=chart(84.2, 84.0)))
    mock_http.add("LIQUIDBEES.BO", httpx.Response(404, json={"chart": {"result": None}}))
    mock_http.add("LIQUIDBEES.NS", httpx.Response(200, json=chart(1000, 999)))
    r = client.post(
        "/api/quotes",
        json={"keys": ["IN_EQ:NSE:RELIANCE", "IN_EQ:BSE:LIQUIDBEES", "garbage", "OTHER:abc"]},
        headers=client_headers(),
    )
    j = r.json()
    assert r.status_code == 200
    assert round(j["quotes"]["IN_EQ:NSE:RELIANCE"]["changePct"], 2) == 10.0
    assert j["quotes"]["IN_EQ:BSE:LIQUIDBEES"]["price"] == 1000
    assert j["invalid"] == ["garbage"] and j["fx"]["USDINR"] == 84.2 and j["missing"] == []


def test_import_file_endpoint(seed_master):
    r = client.post("/api/import/file?broker=generic&filename=a.csv",
                    data=b"symbol,qty,avg price\nTCS,2,3000\n",
                    headers=client_headers(**{"content-type": "application/octet-stream"}))
    assert r.status_code == 200, r.text
    assert r.json()["holdings"][0]["key"] == "IN_EQ:NSE:TCS"
    assert client.post("/api/import/file?broker=nope", data=b"x", headers=client_headers()).status_code == 400
    assert client.post("/api/import/cas", data=b"notapdf", headers=client_headers()).status_code == 422


def test_state_requires_auth_and_lww():
    assert client.get("/api/state", headers=client_headers()).status_code == 401
    uid = auth.upsert_user("sub-1", "a@example.com", "A")
    c = TestClient(app)
    c.cookies.set(auth.COOKIE, auth.make_session(uid))
    assert c.get("/api/auth/me", headers=client_headers()).json()["user"]["id"] == uid
    assert c.put("/api/state", json={"state": {"holdings": [1]}, "updatedAt": 10}, headers=client_headers()).status_code == 200
    assert c.put("/api/state", json={"state": {"holdings": []}, "updatedAt": 5}, headers=client_headers()).status_code == 409
    assert c.get("/api/state", headers=client_headers()).json() == {"state": {"holdings": [1]}, "updatedAt": 10}
    forged = TestClient(app)
    forged.cookies.set(auth.COOKIE, "x" + auth.make_session(uid))
    assert forged.get("/api/state", headers=client_headers()).status_code == 401


def test_broker_request():
    assert client.post("/api/broker-requests", json={"broker": "Angel One"}, headers=client_headers()).json() == {"ok": True}
    assert client.post("/api/broker-requests", json={"broker": "  "}, headers=client_headers()).status_code == 400


def test_spa_fallback_without_build():
    r = client.get("/connect/kite?request_token=abc")
    assert r.status_code in (200, 404)
    assert client.get("/api/nope", headers=client_headers()).status_code == 404


def test_bearer_token_auth():
    uid = auth.upsert_user("sub-2", "b@example.com", "B")
    tok = auth.make_session(uid)
    assert client.get("/api/auth/me", headers=client_headers(Authorization=f"Bearer {tok}")).json()["user"]["id"] == uid
    assert client.get("/api/state", headers=client_headers(Authorization="Bearer x" + tok)).status_code == 401


def test_client_uuid_is_required():
    assert client.get("/api/config").status_code == 400
    assert client.get("/api/config", headers={"X-Client-UUID": "not-a-uuid"}).status_code == 400


def test_production_client_access_gate(monkeypatch):
    monkeypatch.setattr(settings, "client_token", "public-client-token")
    monkeypatch.setattr(settings, "cors_origins", ["https://app.example"])
    allowed = client_headers(**{"X-Tilefolio-Client": "public-client-token", "Origin": "https://app.example"})
    assert client.get("/api/config", headers=allowed).status_code == 200
    assert client.get("/api/config", headers=client_headers(**{"Origin": "https://app.example"})).status_code == 403
    assert client.get("/api/config", headers=client_headers(**{
        "X-Tilefolio-Client": "public-client-token", "Origin": "https://not-the-app.example"
    })).status_code == 403


def test_metrics_are_token_protected(monkeypatch):
    monkeypatch.setattr(settings, "metrics_token", "metrics-secret")
    assert client.get("/internal/metrics").status_code == 404
    assert client.get("/api/config", headers=client_headers()).status_code == 200
    r = client.get("/internal/metrics", headers={"X-Metrics-Token": "metrics-secret"})
    assert r.status_code == 200
    assert "tilefolio_api_requests_total" in r.text
    snapshot = db.metrics_snapshot()
    assert snapshot["requests"] > 0 and snapshot["uniqueClients"] >= 1
