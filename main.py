import subprocess
import sys

print("=== STARTING AUTOMATED PIPELINE ===")

# Step 1: Execute PDF parsing script
print("\n[1/2] Processing PDF invoices...")
subprocess.run([sys.executable, "parse_pdf.py"], check=True)

# Step 2: Execute Excel report generation script
print("\n[2/2] Aggregating data and generating Excel financial report...")
subprocess.run([sys.executable, "generate_report.py"], check=True)

print("\n=== PIPELINE EXECUTION COMPLETED SUCCESSFULLY! ===")