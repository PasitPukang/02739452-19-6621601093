FROM python:3.12-slim
WORKDIR /project
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY pipeline ./pipeline
COPY web ./web
EXPOSE 8091
CMD ["python", "-m", "web.app"]
