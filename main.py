import subprocess
import sys

print("=== STARTING AUTOMATED PIPELINE ===")

# Step 1: Execute PDF parsing script
print("\n[1/3] Processing PDF invoices...")
subprocess.run([sys.executable, "parse_pdf.py"], check=True)

# Step 2: Validate parsed data (stops the pipeline if any check fails)
print("\n[2/3] Validating parsed data...")
subprocess.run([sys.executable, "validate.py"], check=True)

# Step 3: Execute Excel report generation script
print("\n[3/3] Aggregating data and generating Excel financial report...")
subprocess.run([sys.executable, "generate_report.py"], check=True)

print("\n=== PIPELINE EXECUTION COMPLETED SUCCESSFULLY! ===")
