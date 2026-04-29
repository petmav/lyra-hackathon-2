FROM python:3.12-slim

WORKDIR /app

COPY praetor_workflow ./praetor_workflow
COPY templates ./templates

CMD ["python", "-m", "praetor_workflow.worker"]
