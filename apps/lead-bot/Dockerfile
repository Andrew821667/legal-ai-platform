FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY --link pyproject.toml /app/pyproject.toml
COPY --link packages/shared /app/packages/shared
COPY --link apps/lead-bot /app/apps/lead-bot

RUN uv sync --package lead-bot

CMD ["uv", "run", "python", "-m", "lead_bot.run"]
