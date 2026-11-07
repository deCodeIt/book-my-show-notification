FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BMS_DB_PATH=/data/bms.db \
    BMS_TIMEZONE=Asia/Kolkata \
    TZ=Asia/Kolkata

WORKDIR /srv

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/*

COPY requirements-server.txt ./
RUN pip install --no-cache-dir -r requirements-server.txt

# Only the modules the service needs — the desktop CLI, alarms and TUI stay out.
COPY bmsTypes.py bms_api.py http_client.py search.py notifier.py ./
COPY app ./app

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
