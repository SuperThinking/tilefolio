"""MF Central detailed CAS parser. Fixture text is synthetic (made-up investor, folios and amounts)."""
import pytest

from app.importers import mfcentral_import as mfc

TEXT = """Consolidated Account Statement
( From Date : 01-Apr-2026 To Date : 08-Nov-2026 )
MFCentralDetailCAS_v1.0_0000000000-000000000_01-Apr-2026_08-Nov-2026 _-08/11/2026 1:00:00pm Page 1 of 3
Test Investor  ABCDE1234F  test@example.com
SoA Holdings Demat Holdings
Transaction Amount (INR) Units Price
(INR) Date Unit Balance
Axis Fund House
FOLIO NO: 1111111111
Axis ELSS Tax Saver Fund - Direct Plan - Growth (Advisor: INZ000031633/ZERODHA BROKING LIMITED ISIN: INF846K01EW2 Opening Unit Balance: 0.000
05-APR-2026 Purchase - Systematic Instalment No - 1/12 1,000.00 10.000 100.00 10.000
05-MAY-2026 Purchase - Systematic Instalment No - 2/12 1,100.00 10.000 110.00 20.000
05-JUN-2026 Redemption - Electronic Credit less STT (1,200.00) (5.000) 120.00 15.000
05-JUL-2026 SIPCancelled 0.00 0.000 0.00 15.000
Closing Unit Balance: 15.000 Nav as on 07-NOV-2026: INR 130.0000 Valuation on 07-Nov-2026 : INR 1,950.00
Consolidated Account Statement
MFCentralDetailCAS_v1.0_0000000000-000000000_01-Apr-2026_08-Nov-2026 _-08/11/2026 1:00:00pm Page 2 of 3
FOLIO NO: 2222222222
Parag Parikh Flexi Cap Fund - Direct Plan Growth (formerly Parag Parikh Long Term Value Fund)
(Advisor: INZ000208032/NEXTBILLION TECHNOLOGY PRIVATE LIMITED ISIN: INF879O01027 Opening Unit Balance: 50.000
--- --- No Transaction during this statement period --- --- --- --- ---
Closing Unit Balance: 50.000 Nav as on 07-NOV-2026: INR 90.0000 Valuation on 07-Nov-2026 : INR 4,500.00
FOLIO NO: 3333333333
Unknown Scheme - Direct Plan (Advisor: XYZ/DIRECT ISIN: INF000X00000 Opening Unit Balance: 0.000
10-AUG-2026 Purchase 500.00 5.000 100.00 5.000
Closing Unit Balance: 5.000 Nav as on 07-NOV-2026: INR 101.0000 Valuation on 07-Nov-2026 : INR 505.00
FOLIO NO: 4444444444
Axis ELSS Tax Saver Fund - Direct Plan - Growth (Advisor: INZ000208032/DIRECT ISIN: INF846K01EW2 Opening Unit Balance: 0.000
05-APR-2026 Purchase 900.00 10.000 90.00 10.000
05-MAY-2026 Redemption - NSE-REDEMPTION less STT (1,000.00) (10.000) 100.00 0.000
Closing Unit Balance: 0.000 Nav as on 07-NOV-2026: INR 130.0000 Valuation on 07-Nov-2026 : INR 0.00
"""


def test_detect():
    assert mfc.is_mfcentral(TEXT)
    assert not mfc.is_mfcentral("CAMSCASWS something")


def test_parse(seed_master):
    res = mfc.parse_text(TEXT)
    by = {h.name.split(" -")[0]: h for h in res.holdings}
    assert len(res.holdings) == 3  # fully-redeemed folio dropped

    axis = by["Axis ELSS Tax Saver Fund"]
    assert axis.type == "MF" and axis.symbol == "120503" and axis.broker == "Zerodha"
    # FIFO: bought 10@100 + 10@110, sold 5 from the first lot → 5@100 + 10@110 = 1600 / 15
    assert axis.qty == 15 and axis.avg_price == pytest.approx(1600 / 15)

    ppfas = by["Parag Parikh Flexi Cap Fund"]  # header wrapped across two lines
    assert ppfas.symbol == "122639" and ppfas.broker == "Groww"
    assert ppfas.avg_price == 0  # opening units → cost unknown

    unk = by["Unknown Scheme"]
    assert unk.type == "OTHER" and unk.price_override == 101.0 and unk.broker == "MF (CAS)"

    assert any("Cost basis unknown for 1 fund" in w and "01-Apr-2026" in w for w in res.warnings)
    # PII never leaks into output
    blob = repr(res.to_dict())
    assert "ABCDE1234F" not in blob and "test@example.com" not in blob and "1111111111" not in blob


def test_platform_mapping():
    assert mfc.platform("INZ000031633/DIRECT") == "Zerodha"
    assert mfc.platform("INZ000208032/NEXTBILLION TECHNOLOGIES PRIVATE LIMITED") == "Groww"
    assert mfc.platform("ARN-0000/SOMEONE") == "MF (CAS)"


def test_num():
    assert mfc.num("(1,200.50)") == -1200.5 and mfc.num("1,234.567") == 1234.567
