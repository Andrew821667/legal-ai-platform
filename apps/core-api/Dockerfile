FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv
# Шрифт с кириллицей для PDF договоров (core_api/pdf_document.py).
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY --link pyproject.toml /app/pyproject.toml
# Версии — из uv.lock, как в тестах: без него uv sync заново разрешал
# зависимости при сборке, и на прод уезжало не то, что проверено.
COPY --link uv.lock /app/uv.lock
COPY --link packages/shared /app/packages/shared
COPY --link apps/core-api /app/apps/core-api

# UV_FROZEN: и sync при сборке, и uv run при старте берут lock как есть
# (в образе не все участники workspace — перепроверять lock нельзя).
ENV UV_FROZEN=1
RUN uv sync --package core-api
RUN addgroup --system appgroup && adduser --system --ingroup appgroup --home /app appuser && \
    chown -R appuser:appgroup /app

EXPOSE 8000
USER appuser
CMD ["sh", "-lc", "cd /app/apps/core-api && uv run --package core-api alembic upgrade head && cd /app && uv run --package core-api uvicorn core_api.main:app --host 0.0.0.0 --port 8000 --workers ${CORE_API_WORKERS:-4}"]
