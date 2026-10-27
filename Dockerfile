FROM apache/airflow:3.3.1

# Extra libraries the pipeline needs. Pinning apache-airflow to the image's own
# version stops pip from upgrading or downgrading Airflow itself.
RUN pip install --no-cache-dir "apache-airflow==3.3.1" pdfplumber openpyxl pandas
