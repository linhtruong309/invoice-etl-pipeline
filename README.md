# Automated PDF Invoice ETL & Financial Analytics Pipeline

An automated End-to-End ETL (Extract, Transform, Load) and Data Analytics pipeline built in Python. The system extracts structured and semi-structured invoice data from PDF files, normalizes and stores it into a relational SQLite database, and generates multi-sheet financial summary reports in Excel with dynamic formatting.

---

## Architecture Overview

[ Raw PDF Invoices ]
│
▼
[ Python Parser (pdfplumber + Regex) ]
│ (Extract Header & Dynamic Line-Items)
▼
[ SQLite Relational Database ] ──► (invoices & invoice_details tables)
│
▼
[ Data Aggregation & Analytics (Pandas) ]
│
▼
[ Excel Financial Report (openpyxl) ]
(Executive Summary, Line Items, Vendor Cost Distribution & Styling)

---

## Tech Stack

* **Language:** Python 3.14+
* **Data Extraction:** `pdfplumber`, `re` (Regular Expressions)
* **Data Processing & Analytics:** `pandas`
* **Database & ORM:** `sqlite3`, `SQLAlchemy`
* **Report Generation & Formatting:** `openpyxl`

---

## Key Technical Challenges & Solutions

1. **Dynamic Table Header & Column Offset Handling:**

   * *Challenge:* Different suppliers use varying table layouts, column ordering, and header naming conventions.
   * *Solution:* Implemented Dynamic Header Indexing to identify column positions (`Quantity`, `Unit Price`, `Amount`) dynamically per page rather than hardcoding index locations.
2. **Regex-Based Data Fallback Extraction:**

   * *Challenge:* Non-standard invoice forms where tables fail to parse properly using standard spatial extractors.
   * *Solution:* Developed text-line regex fallbacks to parse invoice metadata (Tax ID, Buyer/Vendor details) and itemized numerical values accurately.
3. **Database Normalization & Data Integrity:**

   * *Challenge:* Prevent duplicate invoice records during re-runs.
   * *Solution:* Enforced strict database table replacement and primary/foreign key relationships (`Invoice_No` and `Item_STT`) to ensure data consistency.

---

## Project Structure

├── TDIC's Invoices/           # Directory containing raw input PDF invoices
├── parse_pdf.py               # ETL script: Parses PDFs and loads data to SQLite
├── generate_report.py         # Analytics script: Queries SQLite & exports formatted Excel
├── main.py                    # Pipeline orchestrator (1-click execution)
├── tdic_data.db               # SQLite database instance
├── TDIC_Financial_Report.xlsx # Output multi-sheet financial report
├── requirements.txt           # Project dependencies
└── README.md                  # Project documentation

---


## How to Run

### 1. Prerequisites

Ensure you have Python 3.10+ installed on your system.

### 2. Setup Virtual Environment

```bash
# Clone repository
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd TDIC_Data_Pipeline

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate        # On macOS/Linux
# venv\Scripts\activate          # On Windows
```

### 3. Install Dependencies

pip install -r requirements.txt

### 4. Execute the Pipeline

Run the entire automated pipeline with a single command:

python main.py

## Output Report Features

The generated `TDIC_Financial_Report.xlsx` workbook contains three analytical sheets:

* Executive Summary:  Overall invoice totals, pre-tax amounts, VAT taxes, and vendor counts.
* Line-Item Breakdown: Granular breakdown of item quantities, unit prices, and line totals.
* Vendor Cost Analysis: Total spend per vendor and calculated percentage share (`Cost_Share_Pct`).
