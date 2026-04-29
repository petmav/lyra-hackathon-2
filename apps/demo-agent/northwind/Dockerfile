FROM python:3.12-slim

WORKDIR /app

COPY packages/sdk-py/praetor_sdk ./praetor_sdk
COPY apps/demo-agent/northwind ./northwind

RUN pip install --no-cache-dir httpx

ENV PYTHONPATH=/app

ENTRYPOINT ["python", "-m", "northwind.agent"]
