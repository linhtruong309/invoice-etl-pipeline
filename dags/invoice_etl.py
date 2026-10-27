"""Airflow DAG: PDF invoices -> SQLite -> validation -> Excel report.

    find_pdfs -> extract -> transform_and_load -> validate_data -> generate_report

* Each stage calls the same functions as `python main.py` (parse_pdf.py, validate.py).
* Safe to re-run: `load` rebuilds both tables, so a retry or a manual re-trigger
  never duplicates rows.
* If validation fails the task fails and no report is generated.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow.exceptions import AirflowSkipException
from airflow.sdk import dag, task

# dags/ lives inside the project folder, so the project root is one level up.
PROJECT_DIR = Path(__file__).resolve().parent.parent
STAGING_DIR = PROJECT_DIR / "staging"


def _enter_project():
  """parse_pdf.py uses relative paths (inbox/, tdic_data.db), so run from the project root."""
  os.chdir(PROJECT_DIR)
  if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


@dag(
    dag_id="invoice_etl",
    description="Parse PDF invoices, validate them, and build the Excel report",
    schedule="@daily",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},
    tags=["etl", "invoices"],
)
def invoice_etl():

  @task
  def find_pdfs() -> list[str]:
    _enter_project()
    import parse_pdf

    try:
      return parse_pdf.find_pdf_files()
    except FileNotFoundError as e:
      # Nothing to process today: skip the run instead of failing it.
      raise AirflowSkipException(str(e))

  @task
  def extract(pdf_files: list[str]) -> dict:
    _enter_project()
    import parse_pdf

    invoices, line_items = parse_pdf.extract(pdf_files)
    if len(invoices) != len(pdf_files):
      raise ValueError(
          f"{len(pdf_files) - len(invoices)} of {len(pdf_files)} PDFs failed to parse"
      )

    # Stage the raw extraction as JSON so the next task can pick it up.
    STAGING_DIR.mkdir(exist_ok=True)
    (STAGING_DIR / "invoices.json").write_text(
        json.dumps(invoices, ensure_ascii=False), encoding="utf-8"
    )
    (STAGING_DIR / "line_items.json").write_text(
        json.dumps(line_items, ensure_ascii=False), encoding="utf-8"
    )
    return {"invoices": len(invoices), "line_items": len(line_items)}

  @task
  def transform_and_load(extracted: dict) -> dict:
    _enter_project()
    import parse_pdf

    invoices = json.loads((STAGING_DIR / "invoices.json").read_text(encoding="utf-8"))
    line_items = json.loads((STAGING_DIR / "line_items.json").read_text(encoding="utf-8"))
    df_invoices, df_details = parse_pdf.transform(invoices, line_items)
    parse_pdf.load(df_invoices, df_details)
    return {"invoices": len(df_invoices), "line_items": len(df_details)}

  @task
  def validate_data(loaded: dict) -> dict:
    _enter_project()
    import sqlite3

    import validate as validator

    issues = validator.validate(sqlite3.connect("tdic_data.db"))
    if issues:
      raise ValueError(
          f"{len(issues)} validation issue(s):\n" + "\n".join(str(i) for i in issues)
      )
    return loaded

  @task
  def generate_report(validated: dict) -> str:
    _enter_project()
    subprocess.run([sys.executable, "generate_report.py"], cwd=PROJECT_DIR, check=True)
    return "TDIC_Financial_Report.xlsx"

  pdfs = find_pdfs()
  extracted = extract(pdfs)
  loaded = transform_and_load(extracted)
  validated = validate_data(loaded)
  generate_report(validated)


invoice_etl()
