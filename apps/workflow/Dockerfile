FROM python:3.12-slim

WORKDIR /app

COPY praetor_workflow ./praetor_workflow
COPY templates ./templates

CMD ["python", "-c", "import time; print('praetor workflow worker placeholder'); time.sleep(10**9)"]
