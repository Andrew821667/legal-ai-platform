FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY --link pyproject.toml /app/pyproject.toml
# Версии — из uv.lock, как в тестах: без него uv sync заново разрешал
# зависимости при сборке, и на прод уезжало не то, что проверено.
COPY --link uv.lock /app/uv.lock
COPY --link packages/shared /app/packages/shared
COPY --link packages/prompts /app/packages/prompts
COPY --link apps/news /app/apps/news

# UV_FROZEN: и sync при сборке, и uv run при старте берут lock как есть
# (в образе не все участники workspace — перепроверять lock нельзя).
ENV UV_FROZEN=1
RUN uv sync --package news

CMD ["uv", "run", "python", "-m", "news.publish"]
