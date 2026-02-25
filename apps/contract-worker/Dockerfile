FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY --link pyproject.toml /app/pyproject.toml
COPY --link packages/shared /app/packages/shared
COPY --link apps/contract-worker /app/apps/contract-worker

RUN uv sync --package contract-worker

CMD ["uv", "run", "python", "-m", "contract_worker.run"]
