import httpx
from fastapi.testclient import TestClient

from app import auth
from app.main import app
from tests.test_prices import chart

client = TestClient(app)


def test_config_and_health():
    j = client.get("/api/health").json()
    assert j["ok"] is True and j["version"]
    cfg = client.get("/api/config").json()
    assert {b["id"] for b in cfg["brokers"]} >= {"zerodha", "groww", "upstox", "indmoney", "generic"}


def test_quotes_endpoint(mock_http):
    mock_http.add("RELIANCE.NS", httpx.Response(200, json=chart(110, 100)))
    mock_http.add("INR%3DX", httpx.Response(200, json=chart(84.2, 84.0)))
    mock_http.add("INR=X", httpx.Response(200, json=chart(84.2, 84.0)))
    r = client.post("/api/quotes", json={"keys": ["IN_EQ:NSE:RELIANCE", "garbage", "OTHER:abc"]})
    j = r.json()
    assert r.status_code == 200
    assert round(j["quotes"]["IN_EQ:NSE:RELIANCE"]["changePct"], 2) == 10.0
    assert j["invalid"] == ["garbage"] and j["fx"]["USDINR"] == 84.2 and j["missing"] == []


def test_import_file_endpoint(seed_master):
    r = client.post("/api/import/file?broker=generic&filename=a.csv",
                    data=b"symbol,qty,avg price\nTCS,2,3000\n",
                    headers={"content-type": "application/octet-stream"})
    assert r.status_code == 200, r.text
    assert r.json()["holdings"][0]["key"] == "IN_EQ:NSE:TCS"
    assert client.post("/api/import/file?broker=nope", data=b"x").status_code == 400
    assert client.post("/api/import/cas", data=b"notapdf").status_code == 422


def test_state_requires_auth_and_lww():
    assert client.get("/api/state").status_code == 401
    uid = auth.upsert_user("sub-1", "a@example.com", "A")
    c = TestClient(app)
    c.cookies.set(auth.COOKIE, auth.make_session(uid))
    assert c.get("/api/auth/me").json()["user"]["id"] == uid
    assert c.put("/api/state", json={"state": {"holdings": [1]}, "updatedAt": 10}).status_code == 200
    assert c.put("/api/state", json={"state": {"holdings": []}, "updatedAt": 5}).status_code == 409
    assert c.get("/api/state").json() == {"state": {"holdings": [1]}, "updatedAt": 10}
    forged = TestClient(app)
    forged.cookies.set(auth.COOKIE, "x" + auth.make_session(uid))
    assert forged.get("/api/state").status_code == 401


def test_broker_request():
    assert client.post("/api/broker-requests", json={"broker": "Angel One"}).json() == {"ok": True}
    assert client.post("/api/broker-requests", json={"broker": "  "}).status_code == 400


def test_spa_fallback_without_build():
    r = client.get("/connect/kite?request_token=abc")
    assert r.status_code in (200, 404)
    assert client.get("/api/nope").status_code == 404


def test_bearer_token_auth():
    uid = auth.upsert_user("sub-2", "b@example.com", "B")
    tok = auth.make_session(uid)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()["user"]["id"] == uid
    assert client.get("/api/state", headers={"Authorization": "Bearer x" + tok}).status_code == 401
