"""Tests for the transform/load stages of parse_pdf.py (no PDFs needed)."""
import sqlite3

import parse_pdf as p


def invoice(no="A1"):
    return {"Invoice_No": no, "Vendor_Name": "V", "Vendor_MST": "0123456789", "Buyer_Name": "B",
            "Pre_Tax_Total": 2000, "Tax_Rate": 0.1, "Tax_Amount": 200, "Grand_Total": 2200, "File_Name": "a.pdf"}


def item(stt, unit="Cái", no="A1"):
    return {"Invoice_No": no, "Item_STT": stt, "Item_Name": "x", "Unit": unit, "Quantity": 1.0,
            "Unit_Price": 1000, "Line_Total": 1000, "Tax_Rate": 0.1, "Tax_Amount": 100, "Grand_Total": 1100}


def test_transform_drops_duplicates_and_normalises_units():
    df_inv, df_det = p.transform([invoice(), invoice()], [item(2, " Cái "), item(1, "CÁI"), item(1, "cái")])
    assert len(df_inv) == 1
    assert list(df_det["Item_STT"]) == [1, 2]            # de-duplicated and sorted
    assert set(df_det["Unit"]) == {"cái"}                 # one spelling per unit
    assert list(df_inv.columns) == p.INVOICE_COLUMNS


def test_load_twice_does_not_duplicate_rows(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    df_inv, df_det = p.transform([invoice()], [item(1), item(2)])
    p.load(df_inv, df_det, db_url)
    p.load(df_inv, df_det, db_url)                        # second run replaces, never appends
    conn = sqlite3.connect(tmp_path / "test.db")
    assert conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM invoice_details").fetchone()[0] == 2


def test_find_pdf_files_fails_loudly_when_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    try:
        p.find_pdf_files()
    except FileNotFoundError as e:
        assert "No PDF files" in str(e)
    else:
        raise AssertionError("expected FileNotFoundError")
