FROM python:3.12-slim

WORKDIR /app

COPY praetor_sandbox ./praetor_sandbox
COPY images ./images

EXPOSE 8700

CMD ["python", "-m", "praetor_sandbox.server"]
