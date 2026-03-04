FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/lead-bot/legacy/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY apps/lead-bot/legacy /app

RUN mkdir -p /app/data /app/logs

CMD ["python", "-u", "bot.py"]
