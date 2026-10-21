"""Data-quality checks for the invoice ETL pipeline.

Run after parse_pdf.py has loaded tdic_data.db:
    python validate.py            # prints a report, exit code 1 if issues found

NOTE: these checks catch internal inconsistencies. They cannot tell you that
header totals AND lines are wrong in the same way, so they are paired with
test_golden.py, which compares against totals read by a human from the PDFs.
"""
import sqlite3
import sys
from dataclasses import dataclass

TOL = 1  # VND
BUYER_MST = "0304769887"  # our own company; must never appear as a vendor


@dataclass
class Issue:
    invoice_no: str
    check: str
    message: str

    def __str__(self):
        return f"[{self.check}] {self.invoice_no}: {self.message}"


def check_invoice_totals(conn):
    """Header-level checks: grand total arithmetic and vendor fields."""
    conn.row_factory = sqlite3.Row
    issues = []
    for inv in conn.execute("SELECT * FROM invoices"):
        no = inv["Invoice_No"]

        if abs(inv["Pre_Tax_Total"] + inv["Tax_Amount"] - inv["Grand_Total"]) > TOL:
            issues.append(Issue(no, "grand_total", "pre-tax + tax != grand total"))

        if inv["Vendor_Name"] in (None, "", "Pending"):
            issues.append(Issue(no, "vendor", "vendor name was not parsed"))
        mst = inv["Vendor_MST"] or ""
        digits = mst.replace("-", "")
        if not digits.isdigit() or len(digits) not in (10, 13):
            issues.append(Issue(no, "vendor", f"vendor tax code looks invalid: {mst!r}"))
        elif mst == BUYER_MST:
            issues.append(Issue(no, "vendor", "vendor tax code is the buyer's own tax code"))
    return issues


def check_line_items(conn):
    """Line-level checks: do the parsed lines add up to the invoice header?"""
    conn.row_factory = sqlite3.Row
    issues = []
    for inv in conn.execute("SELECT * FROM invoices"):
        no = inv["Invoice_No"]
        lines = conn.execute(
            "SELECT * FROM invoice_details WHERE Invoice_No = ? ORDER BY Item_STT", (no,)
        ).fetchall()

        if not lines:
            issues.append(Issue(no, "lines", "invoice has no line items"))
            continue

        # 1. Lines must add up to the pre-tax total
        lines_sum = sum(l["Line_Total"] for l in lines)
        if abs(lines_sum - inv["Pre_Tax_Total"]) > TOL:
            if abs(lines_sum - inv["Grand_Total"]) <= TOL:
                msg = (f"line totals sum to {lines_sum} = the grand total, not the pre-tax total "
                       f"{inv['Pre_Tax_Total']}: line totals are probably tax-inclusive")
            else:
                msg = f"line totals sum to {lines_sum}, pre-tax total is {inv['Pre_Tax_Total']}"
            issues.append(Issue(no, "lines_sum", msg))

        # 2. Tax: sum of per-line tax (each line has its own rate) must match header tax
        expected_tax = sum(l["Line_Total"] * l["Tax_Rate"] for l in lines)
        if abs(expected_tax - inv["Tax_Amount"]) > max(TOL, len(lines)):
            issues.append(Issue(no, "tax", f"header tax {inv['Tax_Amount']} != sum of line tax {expected_tax:.0f}"))

        # 3. Quantity x unit price must equal line total (summarised per invoice)
        bad = [l for l in lines
               if abs(l["Quantity"] * l["Unit_Price"] - l["Line_Total"]) > max(TOL, 0.001 * l["Line_Total"])]
        if bad:
            ex = bad[0]
            issues.append(Issue(
                no, "qty_x_price",
                f"{len(bad)}/{len(lines)} lines: quantity x unit price != line total "
                f"(e.g. STT {ex['Item_STT']}: {ex['Quantity']:g} x {ex['Unit_Price']} = "
                f"{ex['Quantity'] * ex['Unit_Price']:.0f}, parsed {ex['Line_Total']})"))

        # 4. Line numbers must run 1..n with no gaps or repeats
        stt = [l["Item_STT"] for l in lines]
        if stt != list(range(1, len(lines) + 1)):
            missing = sorted(set(range(1, max(stt) + 1)) - set(stt))
            issues.append(Issue(no, "stt", f"line numbers not continuous, missing {missing[:10]}"))
    return issues


def validate(conn):
    return check_invoice_totals(conn) + check_line_items(conn)


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "tdic_data.db"
    conn = sqlite3.connect(db)
    n_inv = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
    n_lines = conn.execute("SELECT COUNT(*) FROM invoice_details").fetchone()[0]
    found = validate(conn)
    print(f"Checked {n_inv} invoices, {n_lines} line items")
    for issue in found:
        print(" ", issue)
    print("OK" if not found else f"{len(found)} issue(s) found")
    sys.exit(1 if found else 0)
