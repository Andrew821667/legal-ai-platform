FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY --link pyproject.toml /app/pyproject.toml
COPY --link packages/shared /app/packages/shared
COPY --link apps/core-api /app/apps/core-api

RUN uv sync --package core-api

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "core_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
