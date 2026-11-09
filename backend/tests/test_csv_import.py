import io

from openpyxl import Workbook

from app.importers.csv_import import import_file, norm_header, parse_number


def test_norm_and_numbers():
    assert norm_header("Avg. cost") == "avg cost"
    assert norm_header("Average Price (₹)") == "average price"
    assert norm_header("Qty.") == "qty"
    assert parse_number("₹1,23,456.50") == 123456.5
    assert parse_number("-") is None


def test_kite_web_csv(seed_master):
    csv = (
        '"Instrument","Qty.","Avg. cost","LTP","Cur. val","P&L","Net chg.","Day chg."\n'
        '"RELIANCE","10","2400.5","2500","25000","995","4.1","0.5"\n'
        '"INFY-BE","5","1500","1600","8000","500","6.6","-0.2"\n'
        '"UNKNOWNCO","3","100","110","330","30","10","1"\n'
    )
    res = import_file(csv.encode(), "holdings.csv", "zerodha")
    by = {h.symbol: h for h in res.holdings}
    assert set(by) == {"RELIANCE", "INFY", "UNKNOWNCO"}
    assert by["RELIANCE"].qty == 10 and by["RELIANCE"].avg_price == 2400.5
    assert by["RELIANCE"].sector == "Oil Gas & Consumable Fuels"
    assert by["INFY"].broker == "Zerodha" and by["INFY"].type == "IN_EQ"
    assert by["UNKNOWNCO"].type == "IN_EQ"  # unknown to master, still quotable on Yahoo


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_console_xlsx_with_preamble(seed_master):
    data = _xlsx([
        ["Client ID", "AB1234"],
        ["Holdings statement as on 2026-11-07"],
        [],
        ["Symbol", "ISIN", "Sector", "Quantity Available", "Quantity Discrepant", "Average Price",
         "Previous Closing Price", "Unrealized P&L"],
        ["TCS", "INE467B01029", "IT", 4, 0, 3500.25, 3600, 400],
        ["INFY", "INE009A01021", "IT", 0, 0, 1500, 1600, 0],
    ])
    res = import_file(data, "console.xlsx", "zerodha")
    assert [h.symbol for h in res.holdings] == ["TCS"]
    assert res.holdings[0].qty == 4 and res.holdings[0].avg_price == 3500.25


def test_groww_names_and_isin(seed_master):
    data = _xlsx([
        ["Stock Name", "ISIN", "Quantity", "Average buy price", "Buying value"],
        ["Reliance Industries Ltd", "INE002A01018", 2, 2000, 4000],
        ["Infosys Limited", "", 1, "", 1450],
        ["Mystery Corp", "", 1, 10, 10],
    ])
    res = import_file(data, "groww.xlsx", "groww")
    by = {h.name: h for h in res.holdings}
    assert by["Reliance Industries Ltd"].symbol == "RELIANCE"
    assert by["Infosys Limited"].symbol == "INFY" and by["Infosys Limited"].avg_price == 1450
    assert by["Mystery Corp"].type == "OTHER"
    assert any("Mystery Corp" in w for w in res.warnings)


def test_generic_template(seed_master):
    from app.importers.presets import TEMPLATE_CSV

    res = import_file(TEMPLATE_CSV.encode(), "t.csv", "generic")
    types = {h.type for h in res.holdings}
    assert types == {"IN_EQ", "US_EQ", "MF", "OTHER"}
    us = [h for h in res.holdings if h.type == "US_EQ"][0]
    assert us.currency == "USD" and us.broker == "INDmoney"


def test_mf_by_isin_and_name(seed_master):
    csv = (
        "Scheme Name,ISIN,Units,Invested Value\n"
        "Axis ELSS,INF846K01EW2,100,5000\n"
        "Parag Parikh Flexi Cap Fund - Direct Plan - Growth,,10,700\n"
    )
    res = import_file(csv.encode(), "mf.csv", "groww")
    codes = sorted(h.symbol for h in res.holdings)
    assert codes == ["120503", "122639"]
    assert all(h.type == "MF" for h in res.holdings)
    assert res.holdings[0].avg_price == 50


def test_semicolon_csv(seed_master):
    res = import_file(b"symbol;qty;avg price\nRELIANCE;1;100\n", "x.csv", "generic")
    assert res.holdings[0].symbol == "RELIANCE"


def test_no_header_raises():
    import pytest

    with pytest.raises(ValueError):
        import_file(b"foo,bar\n1,2\n", "x.csv", "generic")
