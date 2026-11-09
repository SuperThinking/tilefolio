import httpx

from app.models import Instrument
from app.prices import mfnav, service, yahoo
from tests.conftest import run

NAVALL = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - ELSS)

Axis Mutual Fund

120503;INF846K01EW2;-;Axis ELSS Tax Saver Fund - Direct Plan - Growth;95.1234;07-Nov-2026
999999;-;-;Broken Fund;N.A.;07-Nov-2026
"""


def chart(price, prev, ccy="INR"):
    return {"chart": {"result": [{"meta": {"regularMarketPrice": price, "chartPreviousClose": prev,
                                           "currency": ccy, "regularMarketTime": 1}}]}}


def test_parse_chart():
    assert yahoo.parse_chart(chart(10, 8))["prev_close"] == 8
    assert yahoo.parse_chart({"chart": {"result": None}}) is None


def test_yahoo_symbols():
    assert yahoo.yahoo_symbol(Instrument("IN_EQ", "TCS", "NSE")) == "TCS.NS"
    assert yahoo.yahoo_symbol(Instrument("IN_EQ", "TCS", "BSE")) == "TCS.BO"
    assert yahoo.yahoo_symbol(Instrument("US_EQ", "BRK.B")) == "BRK-B"


def test_navall_parse_and_day_change():
    rows = mfnav.parse_navall(NAVALL)
    assert rows[0][:2] == ("120503", "Axis ELSS Tax Saver Fund - Direct Plan - Growth")
    assert rows[0][2] == "INF846K01EW2" and rows[0][3] is None and rows[0][5] == "2026-11-07"
    assert rows[1][4] is None
    mfnav.store_navall(rows)
    mfnav.store_navall(mfnav.parse_navall(NAVALL.replace("95.1234;07-Nov-2026", "96.0;08-Nov-2026")))
    q = run(mfnav.fetch_quotes([Instrument("MF", "120503")]))["MF:120503"]
    assert q.price == 96.0 and q.prev_close == 95.1234 and q.as_of == "2026-11-08"
    assert mfnav.code_for_isin("INF846K01EW2") == "120503"


def test_mfapi_backfill(mock_http):
    mock_http.add("api.mfapi.in/mf/122639", httpx.Response(200, json={
        "meta": {"scheme_name": "PPFAS"},
        "data": [{"date": "07-11-2026", "nav": "80.5"}, {"date": "06-11-2026", "nav": "80.0"}]}))
    q = run(mfnav.fetch_quotes([Instrument("MF", "122639")]))["MF:122639"]
    assert q.price == 80.5 and round(q.change_pct, 3) == 0.625


def test_service_caches_and_routes(mock_http):
    mock_http.add("RELIANCE.NS", httpx.Response(200, json=chart(2500, 2450)))
    mock_http.add("/AAPL", httpx.Response(200, json=chart(200, 190, "USD")))
    insts = [Instrument.parse("IN_EQ:NSE:RELIANCE"), Instrument.parse("US_EQ:AAPL"),
             Instrument.parse("IN_EQ:NSE:NOPE")]
    got = run(service.get_quotes(insts))
    assert set(got) == {"IN_EQ:NSE:RELIANCE", "US_EQ:AAPL"}
    assert got["US_EQ:AAPL"].currency == "USD"
    n = len(mock_http.calls)
    run(service.get_quotes(insts[:2]))
    assert len(mock_http.calls) == n  # served from cache


def test_finnhub_falls_back_to_yahoo(mock_http, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "finnhub_api_key", "k")
    mock_http.add("finnhub.io/api/v1/quote", lambda r: httpx.Response(
        200, json={"c": 150, "pc": 100, "t": 1} if r.url.params["symbol"] == "MSFT" else {"c": 0, "pc": 0}))
    mock_http.add("/GOOG", httpx.Response(200, json=chart(50, 40, "USD")))
    got = run(service.get_quotes([Instrument.parse("US_EQ:MSFT"), Instrument.parse("US_EQ:GOOG")]))
    assert got["US_EQ:MSFT"].source == "finnhub" and got["US_EQ:GOOG"].source == "yahoo"


def test_yahoo_backs_off_on_429(mock_http):
    yahoo.backoff.until = 0
    mock_http.add("finance/chart", httpx.Response(429, headers={"retry-after": "60"}))
    assert run(yahoo.fetch_quotes([Instrument.parse("IN_EQ:NSE:TCS")])) == {}
    n = len(mock_http.calls)
    assert run(yahoo.fetch_quotes([Instrument.parse("IN_EQ:NSE:INFY")])) == {}
    assert len(mock_http.calls) == n  # no further calls while backed off
    yahoo.backoff.until = 0
