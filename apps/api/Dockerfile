FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY praetor_api ./praetor_api

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["python", "-m", "praetor_api.run_server"]
