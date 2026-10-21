"""Compare the parsed database with totals read by a human from the 7 PDFs.

Unlike validate.py (internal consistency), this catches errors where header and
lines are wrong in the same way, e.g. VAT column mistaken for the amount column.
"""
import os
import sqlite3

import pytest

# invoice_no: (pre_tax, vat, grand_total, n_lines, seller_mst)  -- read from the PDFs
GOLDEN = {
    "00000179": (106_417_800, 10_641_780, 117_059_580, 94, "0303832134"),
    "00000180": (107_847_700, 10_784_770, 118_632_470, 102, "0303832134"),
    "00000035": (182_662_330, 18_266_233, 200_928_563, 24, "0105489846"),
    "00001399": (535_925_300, 52_170_328, 588_095_628, 28, "0110212857"),
    "00001689": (5_274_080, 421_926, 5_696_006, 20, "0401229397"),
    "00001993": (85_130_000, 6_810_400, 91_940_400, 4, "0309918324"),
    "00041176": (25_116_000, 2_009_280, 27_125_280, 2, "0100736347"),
}

pytestmark = pytest.mark.skipif(not os.path.exists("tdic_data.db"), reason="local database not present")


@pytest.fixture(scope="module")
def conn():
    return sqlite3.connect("tdic_data.db")


@pytest.mark.parametrize("no", sorted(GOLDEN))
def test_invoice_header_matches_pdf(conn, no):
    pre, vat, grand, n_lines, mst = GOLDEN[no]
    row = conn.execute(
        "SELECT Pre_Tax_Total, Tax_Amount, Grand_Total, Vendor_MST FROM invoices WHERE Invoice_No=?", (no,)
    ).fetchone()
    assert row == (pre, vat, grand, mst)


@pytest.mark.parametrize("no", sorted(GOLDEN))
def test_line_items_match_pdf(conn, no):
    pre, _, _, n_lines, _ = GOLDEN[no]
    n, total = conn.execute(
        "SELECT COUNT(*), SUM(Line_Total) FROM invoice_details WHERE Invoice_No=?", (no,)
    ).fetchone()
    assert n == n_lines
    assert abs(total - pre) <= n_lines  # 1 VND of rounding per line


def test_spot_check_mixed_rate_invoice(conn):
    # Invoice 1399, line 1: 18 x 1,780,500 = 32,049,000 at 10% VAT; line 10 is at 8%
    l1 = conn.execute("SELECT Quantity, Unit_Price, Line_Total, Tax_Rate FROM invoice_details "
                      "WHERE Invoice_No='00001399' AND Item_STT=1").fetchone()
    assert l1 == (18.0, 1_780_500, 32_049_000, 0.1)
    l10 = conn.execute("SELECT Line_Total, Tax_Rate, Tax_Amount FROM invoice_details "
                       "WHERE Invoice_No='00001399' AND Item_STT=10").fetchone()
    assert l10 == (3_080_000, 0.08, 246_400)
