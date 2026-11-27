FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir --upgrade pip==26.3 && pip install --no-cache-dir --require-hashes -r requirements.lock
COPY app ./app
USER 65534
EXPOSE 8003
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
