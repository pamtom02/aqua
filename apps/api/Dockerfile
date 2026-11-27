FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 appgroup && useradd --uid 10001 --gid 10001 --no-create-home appuser
COPY requirements.lock .
RUN pip install --no-cache-dir --upgrade pip==26.3 && pip install --no-cache-dir --require-hashes -r requirements.lock
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 application ./application
COPY --chown=10001:10001 catalog ./catalog
COPY --chown=10001:10001 dataset ./dataset
COPY --chown=10001:10001 domain ./domain
COPY --chown=10001:10001 infrastructure ./infrastructure
COPY --chown=10001:10001 ingestion ./ingestion
COPY --chown=10001:10001 satellite ./satellite
COPY --chown=10001:10001 migrations ./migrations
RUN mkdir -p /app/data && chown 10001:10001 /app/data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health/live', timeout=3)"
CMD ["sh", "-c", "python -m app.start && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers --limit-concurrency 32 --backlog 64 --timeout-keep-alive 5"]
