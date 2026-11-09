import httpx
import pytest

from app.brokers import kite, upstox
from app.brokers.kite import BrokerError
from tests.conftest import run


def test_checksum():
    import hashlib

    assert kite.checksum("k", "r", "s") == hashlib.sha256(b"krs").hexdigest()


def test_kite_flow(mock_http, seed_master):
    def session(req):
        body = req.content.decode()
        assert "checksum=" + kite.checksum("key", "rt", "sec") in body
        return httpx.Response(200, json={"status": "success", "data": {"access_token": "AT"}})

    mock_http.add("/session/token", session)
    mock_http.add("/portfolio/holdings", lambda r: (
        httpx.Response(200, json={"data": [
            {"tradingsymbol": "INFY", "exchange": "NSE", "isin": "INE009A01021", "quantity": 3,
             "t1_quantity": 1, "average_price": 1400},
            {"tradingsymbol": "SOLD", "exchange": "NSE", "quantity": 0, "average_price": 1}]})
        if r.headers["authorization"] == "token key:AT" else httpx.Response(403)))
    mock_http.add("/mf/holdings", httpx.Response(200, json={"data": [
        {"tradingsymbol": "INF846K01EW2", "fund": "Axis ELSS", "quantity": 10, "average_price": 50}]}))
    res = run(kite.fetch_holdings("key", "sec", "rt"))
    by = {h.type: h for h in res.holdings}
    assert len(res.holdings) == 2
    assert by["IN_EQ"].qty == 4 and by["IN_EQ"].sector == "Information Technology"
    assert by["MF"].symbol == "120503"


def test_kite_bad_login(mock_http):
    mock_http.add("/session/token", httpx.Response(403, json={"status": "error", "message": "Invalid checksum"}))
    with pytest.raises(BrokerError, match="Invalid checksum"):
        run(kite.fetch_holdings("k", "s", "r"))


def test_upstox_flow(mock_http, seed_master):
    mock_http.add("/login/authorization/token", httpx.Response(200, json={"access_token": "UT"}))
    mock_http.add("/portfolio/long-term-holdings", httpx.Response(200, json={"data": [
        {"tradingsymbol": "TCS", "exchange": "NSE", "isin": "INE467B01029", "quantity": 2,
         "average_price": 3000, "company_name": "TCS"}]}))
    res = run(upstox.fetch_holdings("cid", "cs", "code", "http://localhost/connect/upstox"))
    assert res.holdings[0].symbol == "TCS" and res.holdings[0].broker == "Upstox"
    assert "client_id=cid" in upstox.login_url("cid", "http://x")
