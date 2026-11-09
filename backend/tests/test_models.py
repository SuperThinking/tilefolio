import pytest

from app.models import Holding, Instrument, Quote


def test_instrument_roundtrip():
    for key in ["IN_EQ:NSE:RELIANCE", "US_EQ:AAPL", "MF:119551"]:
        assert Instrument.parse(key).key == key


@pytest.mark.parametrize("bad", ["", "XX:1", "IN_EQ:NSE", "US_EQ:", "IN_EQ:NSE:"])
def test_instrument_bad(bad):
    with pytest.raises(ValueError):
        Instrument.parse(bad)


def test_holding_dict_is_camel():
    d = Holding(type="US_EQ", symbol="AAPL", qty=1, avg_price=10).to_dict()
    assert d["key"] == "US_EQ:AAPL" and d["avgPrice"] == 10 and "priceOverride" in d


def test_change_pct():
    q = Quote(key="k", price=110, prev_close=100, currency="INR", source="t", ts=0)
    assert q.change_pct == pytest.approx(10.0)
    assert Quote(key="k", price=1, prev_close=None, currency="INR", source="t", ts=0).change_pct is None
