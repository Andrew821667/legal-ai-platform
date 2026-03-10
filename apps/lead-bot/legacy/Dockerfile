FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/lead-bot/legacy/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN addgroup --system appgroup && adduser --system --ingroup appgroup --home /app appuser

COPY apps/lead-bot/legacy /app

RUN mkdir -p /app/data /app/logs && chown -R appuser:appgroup /app

CMD ["sh", "-lc", "chown -R appuser:appgroup /app/data /app/logs && exec su appuser -s /bin/sh -c 'python -u /app/bot.py'"]
