# PDF Invoice ETL & Financial Reporting Pipeline

A Python pipeline that turns unstructured PDF invoices into a normalized SQLite database and a multi-sheet Excel financial report, with automated data-quality checks and tests verified against the source documents.

Built during a finance data engineering internship to replace manual invoice data entry.

## Results

| | |
|---|---|
| Invoices parsed | 7 (6 different vendor layouts) |
| Line items extracted | 274 |
| Parsed totals verified against source PDFs | 7 / 7 |
| Automated tests | 25 passing |

## Architecture

```text
[ PDF invoices ]  (inbox/)
        |
        v
[ parse_pdf.py ]     pdfplumber + regex: header fields, totals, line items
        |
        v
[ SQLite ]           invoices  +  invoice_details
        |
        v
[ validate.py ]      reconciliation checks, stops the pipeline on failure
        |
        v
[ generate_report.py ]   SQL aggregation (pandas) -> Excel (openpyxl)
```

## Tech Stack

* **Language:** Python 3.11+ (developed on 3.14)
* **Extraction:** `pdfplumber`, `re`
* **Processing:** `pandas`
* **Storage:** SQLite via `SQLAlchemy`
* **Reporting:** `openpyxl`
* **Testing:** `pytest`

## Key Challenges & Solutions

**1. Vendors use different table layouts.**
Column order, header wording and the number of amount columns vary by vendor. Instead of hardcoding column positions, the parser finds each column from its header text (`find_col`), with preferred and excluded keywords. When table extraction fails, regex fallbacks parse the text lines directly.

**2. Silent data errors in multi-column layouts.**
Two layouts exposed bugs that produced plausible-looking but wrong numbers:

* A header like `Tiền thuế GTGT (VAT Amount)` matched the keyword `amount`, so the VAT column was read as the line total.
* A layout with both "amount before tax" and "amount after tax" columns resolved to the wrong one.

Together with a missing summary-row rule, these understated total spend by about 46%. Internal consistency checks did not catch it, because the header totals were derived from the same wrong lines. The fix was a stricter column matcher, a rule for the three-amount summary row, and golden tests (see below).

**3. Mixed VAT rates.**
One invoice mixes 8% and 10% lines. The parser reads the rate per line, and the invoice-level rate is stored as the effective rate.

**4. Vietnamese number formats and layout quirks.**
Dot as thousands separator, comma as decimal separator, tax codes printed with spaces between digits, and the buyer's tax code appearing next to the seller's. The parser normalizes these and never accepts the buyer's own tax code as a vendor.

**5. Safe re-runs.**
Tables are dropped and rebuilt on every run, and duplicate rows (same `Invoice_No` + `Item_STT`) are removed, so running the pipeline twice never duplicates data.

## Validation & Testing

`validate.py` runs between parsing and reporting. If any check fails, the pipeline stops and no report is generated.

* Pre-tax + VAT = grand total
* Sum of line totals = invoice pre-tax total
* Header VAT = sum of per-line VAT (supports mixed rates)
* Quantity x unit price = line total
* Line numbers are continuous (no gaps or repeats)
* Vendor name parsed; vendor tax code is valid and is not the buyer's

Tests (`pytest`):

* `test_validate.py` (10 tests): builds small in-memory databases to prove each check catches the error it is meant to catch.
* `test_golden.py` (15 tests): compares the database against totals, line counts and vendor tax codes read by hand from the source PDFs. This catches errors where the header and the lines are wrong in the same way.

The golden tests are tied to the original 7 invoices and skip automatically when the database is not present.

## Project Structure

```text
├── inbox/                      # Input PDF invoices (not committed)
├── parse_pdf.py                # Extract + transform + load into SQLite
├── validate.py                 # Data-quality checks
├── generate_report.py          # SQL aggregation + Excel report
├── main.py                     # Runs the full pipeline
├── test_validate.py            # Unit tests for the validator
├── test_golden.py              # Tests against hand-verified PDF totals
├── requirements.txt
└── README.md
```

The database (`tdic_data.db`) and the Excel report are generated on each run and are not committed.

## How to Run

```bash
git clone <REPOSITORY_URL>
cd <REPOSITORY_FOLDER>

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create an `inbox/` folder and place text-based PDF invoices in it (invoice PDFs are not included in this repository), then run:

```bash
python main.py      # parse -> validate -> report
pytest              # run the tests
```

## Output Report

`TDIC_Financial_Report.xlsx` contains four sheets:

* **Executive summary:** invoice count, pre-tax total, VAT, grand total
* **Vendor analysis:** spend per vendor and percentage share of total cost
* **Top cost items:** the 15 highest-spend items with quantity and average unit price
* **VAT input declaration:** per-invoice seller tax code, pre-tax amount, rate, VAT and total

## Limitations

* Prototype validated on 7 invoices from 6 vendor layouts; a new layout may need keyword tuning.
* Text-based PDFs only (no OCR for scanned documents).
* Amounts are assumed to be in VND with Vietnamese number formatting.
* The buyer's tax code is a constant in `parse_pdf.py` and `validate.py`.

## Roadmap

* Orchestrate the pipeline with Apache Airflow (Docker), with retries and idempotent loads
* Add dbt models on top of the loaded data (staging, fact and dimension tables)
* Load into a cloud warehouse (Snowflake)
* Add CI to run the tests on every push
