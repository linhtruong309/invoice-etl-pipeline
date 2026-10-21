import sqlite3

from validate import check_invoice_totals, check_line_items, validate


def make_db(pre=2000, rate=0.1, tax=200, grand=2200, vendor="CONG TY A", mst="0123456789",
            lines=((1, 2, 500, 1000), (2, 1, 1000, 1000))):
    """Tiny in-memory DB with the same schema the pipeline writes."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE invoices (Invoice_No TEXT, Vendor_Name TEXT, Vendor_MST TEXT,
        Buyer_Name TEXT, Pre_Tax_Total INT, Tax_Rate REAL, Tax_Amount INT, Grand_Total INT, File_Name TEXT)""")
    conn.execute("""CREATE TABLE invoice_details (Invoice_No TEXT, Item_STT INT, Item_Name TEXT,
        Unit TEXT, Quantity REAL, Unit_Price INT, Line_Total INT, Tax_Rate REAL, Tax_Amount INT, Grand_Total INT)""")
    conn.execute("INSERT INTO invoices VALUES ('A1', ?, ?, 'B', ?, ?, ?, ?, 'a.pdf')",
                 (vendor, mst, pre, rate, tax, grand))
    for stt, qty, price, total in lines:
        conn.execute("INSERT INTO invoice_details VALUES ('A1', ?, 'item', 'cai', ?, ?, ?, ?, 0, 0)",
                     (stt, qty, price, total, rate))
    return conn


def checks(issues):
    return {i.check for i in issues}


def test_clean_invoice_passes():
    assert validate(make_db()) == []


def test_wrong_grand_total_is_caught():
    assert "grand_total" in checks(check_invoice_totals(make_db(grand=9999)))


def test_wrong_tax_is_caught():
    assert "tax" in checks(validate(make_db(tax=500, grand=2500)))


def test_mixed_rate_invoice_passes():
    # 1000 at 10% + 1000 at 8% = 100 + 80 = 180 tax
    conn = make_db(pre=2000, rate=0.09, tax=180, grand=2180)
    conn.execute("UPDATE invoice_details SET Tax_Rate = 0.08 WHERE Item_STT = 2")
    conn.execute("UPDATE invoice_details SET Tax_Rate = 0.10 WHERE Item_STT = 1")
    assert validate(conn) == []


def test_unparsed_vendor_is_caught():
    assert "vendor" in checks(check_invoice_totals(make_db(vendor="Pending", mst="N/A")))


def test_buyers_own_tax_code_as_vendor_is_caught():
    assert "vendor" in checks(check_invoice_totals(make_db(mst="0304769887")))


def test_lines_not_adding_up_are_caught():
    assert "lines_sum" in checks(check_line_items(make_db(lines=((1, 2, 500, 1000),))))


def test_tax_inclusive_line_totals_are_diagnosed():
    issues = check_line_items(make_db(lines=((1, 2, 500, 1100), (2, 1, 1000, 1100))))
    assert any("tax-inclusive" in i.message for i in issues)


def test_quantity_times_price_mismatch_is_caught():
    db = make_db(pre=200, tax=20, grand=220, lines=((1, 2, 500, 100), (2, 1, 1000, 100)))
    assert "qty_x_price" in checks(check_line_items(db))


def test_gap_in_line_numbers_is_caught():
    assert "stt" in checks(check_line_items(make_db(lines=((1, 2, 500, 1000), (3, 1, 1000, 1000)))))
