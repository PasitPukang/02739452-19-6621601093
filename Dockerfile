# Keep the reference project's Airflow runtime for template compatibility.
FROM apache/airflow:2.11.2-python3.12
COPY requirements.txt /tmp/project-requirements.txt
RUN pip install --no-cache-dir -r /tmp/project-requirements.txt
