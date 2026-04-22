# Руководство по развертыванию в продакшен - Сервер 2GB RAM

Полное руководство по развертыванию AI Verdict News Bot на production сервере с 2GB RAM.

## 📋 Требования

- **Сервер**: 1 vCPU / 2GB RAM / 20GB SSD
- **OS**: Ubuntu 20.04+ / Debian 11+
- **Docker**: 24.0+
- **Docker Compose**: 2.20+
- **Swap**: 2GB (настраивается автоматически)

**Рекомендуемые провайдеры:**
- Hetzner CX11: €4.15/мес
- DigitalOcean Basic: $6/мес
- Vultr Regular: $5/мес

## 🚀 Быстрый старт

### 1. Настройка Swap (2GB)

```bash
# Проверяем текущий swap
sudo swapon --show
free -h

# Создаем swap файл 2GB
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Делаем постоянным (добавляем в /etc/fstab)
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Настраиваем swappiness (как часто использовать swap)
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Проверяем
free -h
```

**Результат должен показывать:**
```
              total        used        free
Mem:           2.0Gi       800Mi       1.2Gi
Swap:          2.0Gi         0B       2.0Gi
```

### 2. Клонирование репозитория

```bash
git clone https://github.com/your-repo/Telegram_channel_auto.git
cd Telegram_channel_auto
```

### 3. Настройка Environment Variables

Создайте `.env` файл:

```bash
cp .env.example .env
nano .env
```

**Обязательные переменные:**

```env
# Database
POSTGRES_DB=legal_ai_news
POSTGRES_USER=legal_user
POSTGRES_PASSWORD=your_secure_password_here

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=@your_channel
TELEGRAM_ADMIN_ID=your_user_id
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# OpenAI
OPENAI_API_KEY=sk-your-key

# Perplexity (опционально)
PERPLEXITY_API_KEY=pplx-your-key
PERPLEXITY_SEARCH_ENABLED=true

# Telegram Fetcher (опционально)
TELEGRAM_FETCH_ENABLED=true
```

### 4. Запуск базовых сервисов

**Без celery_beat (рекомендуется для 2GB):**

```bash
# Запускаем основные сервисы (БЕЗ celery_worker)
docker compose -f docker-compose.production.yml up -d postgres redis qdrant app bot

# Проверяем статус
docker compose -f docker-compose.production.yml ps

# Проверяем логи
docker compose -f docker-compose.production.yml logs -f
```

### 5. Настройка автоматического запуска через Cron

```bash
# Делаем скрипты исполняемыми
chmod +x scripts/run_daily_workflow.sh
chmod +x scripts/setup_cron.sh

# Устанавливаем cron jobs (3 раза в день: 09:00, 14:00, 18:00 MSK)
./scripts/setup_cron.sh

# Проверяем установленные задачи
crontab -l
```

### 6. Первый запуск (ручной тест)

```bash
# Запускаем workflow вручную для теста
./scripts/run_daily_workflow.sh

# Смотрим логи
tail -f logs/cron_workflow_*.log
```

## 📊 Мониторинг памяти

### Проверка потребления памяти

```bash
# Общее потребление
free -h

# По контейнерам
docker stats --no-stream

# Детальная статистика
docker compose -f docker-compose.production.yml ps -a
docker system df
```

**Ожидаемое потребление:**

| Сервис | Базовое | Пиковое |
|--------|---------|---------|
| PostgreSQL | 100-150 MB | 150-200 MB |
| Redis | 50-100 MB | 100-150 MB |
| Qdrant | 100-200 MB | 200-300 MB |
| Bot | 150-250 MB | 250-350 MB |
| App | 150-250 MB | 250-350 MB |
| **Celery Worker** | **200-300 MB** | **400-500 MB** |
| **ИТОГО (база)** | **550-950 MB** | **950-1350 MB** |
| **ИТОГО (с worker)** | **750-1250 MB** | **1350-1850 MB** |

### Автоматическая очистка

```bash
# Очистка старых Docker образов и логов
docker system prune -af --volumes
find logs/ -name "*.log" -mtime +7 -delete
```

## 🔧 Оптимизация для 2GB

### 1. Агрессивная сборка мусора Python

В `docker-compose.production.yml` уже настроено:
```yaml
environment:
  - PYTHON_GC_THRESHOLD=700,10,10  # Для bot/app
  - PYTHON_GC_THRESHOLD=500,5,5    # Для celery worker
```

### 2. Ограничение памяти PostgreSQL

```yaml
environment:
  POSTGRES_SHARED_BUFFERS: "64MB"
  POSTGRES_EFFECTIVE_CACHE_SIZE: "256MB"
  POSTGRES_WORK_MEM: "4MB"
```

### 3. Ограничение памяти Redis

```yaml
command: >
  redis-server
  --maxmemory 80mb
  --maxmemory-policy allkeys-lru
```

### 4. On-demand Celery Worker

Worker запускается только на время выполнения задач (1.5 часа в день) и останавливается после завершения.

## 📅 Расписание запусков

| Время (MSK) | Время (UTC) | Описание |
|-------------|-------------|----------|
| 09:00 | 06:00 | Утренний сбор новостей |
| 14:00 | 11:00 | Дневной сбор новостей |
| 18:00 | 15:00 | Вечерний сбор новостей |

**Итого:** 3 запуска в день, ~1.5 часа активной работы, 22.5 часа простоя.

## 🔍 Troubleshooting

### Out of Memory (OOM)

Если контейнер убивается из-за нехватки памяти:

```bash
# Проверяем логи ядра
sudo dmesg | grep -i "out of memory"

# Проверяем swap usage
free -h

# Увеличиваем swap до 3GB
sudo swapoff /swapfile
sudo dd if=/dev/zero of=/swapfile bs=1G count=3
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Celery Worker не останавливается

```bash
# Принудительная остановка
docker compose -f docker-compose.production.yml stop celery_worker
docker compose -f docker-compose.production.yml rm -f celery_worker

# Очистка Redis queue
docker compose -f docker-compose.production.yml exec redis redis-cli FLUSHDB
```

### Проблемы с cron

```bash
# Проверяем логи cron
sudo tail -f /var/log/syslog | grep CRON

# Проверяем права на скрипты
ls -la scripts/

# Тестируем скрипт вручную
bash -x scripts/run_daily_workflow.sh
```

## 📈 Мониторинг и алерты

### Настройка мониторинга памяти

Создайте скрипт `scripts/check_memory.sh`:

```bash
#!/bin/bash
THRESHOLD=90  # 90% использования памяти

MEMORY_USAGE=$(free | grep Mem | awk '{print ($3/$2) * 100.0}' | cut -d. -f1)

if [ "$MEMORY_USAGE" -gt "$THRESHOLD" ]; then
    echo "⚠️ High memory usage: ${MEMORY_USAGE}%"
    # Отправляем уведомление (опционально)
    curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_ADMIN_ID}" \
        -d "text=⚠️ Server memory usage: ${MEMORY_USAGE}%"
fi
```

Добавьте в cron (каждые 30 минут):
```bash
*/30 * * * * /path/to/scripts/check_memory.sh
```

## 🔄 Обновление

```bash
# Останавливаем сервисы
docker compose -f docker-compose.production.yml down

# Подтягиваем изменения
git pull origin main

# Пересобираем образы
docker compose -f docker-compose.production.yml build

# Запускаем
docker compose -f docker-compose.production.yml up -d postgres redis qdrant app bot
```

## 🗑️ Полная очистка и переустановка

```bash
# Останавливаем все
docker compose -f docker-compose.production.yml down -v

# Удаляем все Docker данные
docker system prune -af --volumes

# Удаляем базу данных
sudo rm -rf /var/lib/docker/volumes/telegram_channel_auto_postgres_data

# Переустановка с нуля
docker compose -f docker-compose.production.yml up -d postgres redis qdrant app bot
```

## 📞 Поддержка

Если возникли проблемы:
1. Проверьте логи: `docker compose -f docker-compose.production.yml logs`
2. Проверьте память: `free -h && docker stats --no-stream`
3. Проверьте cron: `crontab -l && tail -f logs/cron_workflow_*.log`
4. Создайте issue на GitHub

## 📚 Дополнительные ресурсы

- [Docker Memory Management](https://docs.docker.com/config/containers/resource_constraints/)
- [PostgreSQL Tuning](https://pgtune.leopard.in.ua/)
- [Redis Memory Optimization](https://redis.io/docs/manual/eviction/)
- [Linux Swap Management](https://www.kernel.org/doc/Documentation/sysctl/vm.txt)
