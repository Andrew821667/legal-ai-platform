# 🐳 Docker Setup для Contract AI System

## Быстрый старт

### 1. Подготовка

Создайте `.env` файл из примера:

```bash
cp .env.example .env
```

Отредактируйте `.env` и укажите:

```bash
# Обязательные параметры
SECRET_KEY=<сгенерируйте: python -c "import secrets; print(secrets.token_urlsafe(32))">
OPENAI_API_KEY=sk-...

# Базы данных (опционально, есть дефолты)
POSTGRES_PASSWORD=your_secure_password
REDIS_PASSWORD=your_redis_password

# Окружение
APP_ENV=production
```

### 2. Запуск всей системы

```bash
# Запуск всех сервисов (PostgreSQL, Redis, Backend, Streamlit)
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Проверка статуса
docker-compose ps
```

### 3. Доступ к сервисам

- **FastAPI Backend**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/api/docs
- **Streamlit Admin UI**: http://localhost:8501
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 4. Проверка работоспособности

```bash
# Health check для backend
curl http://localhost:8000/health

# Проверка API
curl http://localhost:8000/
```

## Архитектура Docker Setup

```
┌─────────────────────────────────────────┐
│   Docker Compose Network                │
│                                         │
│  ┌──────────┐      ┌──────────┐        │
│  │          │      │          │        │
│  │ Backend  │◄────►│ Postgres │        │
│  │  :8000   │      │  :5432   │        │
│  │          │      │          │        │
│  └────▲─────┘      └──────────┘        │
│       │                                 │
│       │            ┌──────────┐        │
│       │            │          │        │
│       └───────────►│  Redis   │        │
│                    │  :6379   │        │
│  ┌──────────┐      │          │        │
│  │          │      └──────────┘        │
│  │Streamlit │                           │
│  │  :8501   │                           │
│  │          │                           │
│  └──────────┘                           │
│                                         │
└─────────────────────────────────────────┘
```

## Команды управления

### Запуск и остановка

```bash
# Запустить все сервисы
docker-compose up -d

# Остановить все сервисы
docker-compose down

# Остановить и удалить volumes (очистка данных)
docker-compose down -v

# Перезапустить конкретный сервис
docker-compose restart backend

# Пересобрать образы
docker-compose build --no-cache
```

### Логи и мониторинг

```bash
# Все логи
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f backend
docker-compose logs -f postgres

# Последние 100 строк
docker-compose logs --tail=100 backend
```

### Выполнение команд в контейнере

```bash
# Bash в backend контейнере
docker-compose exec backend bash

# Выполнить Python скрипт
docker-compose exec backend python script.py

# Запустить тесты
docker-compose exec backend pytest

# Создать миграцию БД
docker-compose exec backend alembic revision --autogenerate -m "migration name"

# Применить миграции
docker-compose exec backend alembic upgrade head
```

### Работа с БД

```bash
# Подключиться к PostgreSQL
docker-compose exec postgres psql -U contract_user -d contract_ai

# Создать бэкап БД
docker-compose exec postgres pg_dump -U contract_user contract_ai > backup.sql

# Восстановить из бэкапа
cat backup.sql | docker-compose exec -T postgres psql -U contract_user -d contract_ai
```

## Production Deploy

### 1. Настройка для production

Создайте `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  backend:
    environment:
      - APP_ENV=production
      - LLM_TEST_MODE=false
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G

  postgres:
    environment:
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - /var/lib/postgresql/data:/var/lib/postgresql/data
```

Запуск:

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 2. Nginx reverse proxy

Создайте `nginx.conf`:

```nginx
upstream backend {
    server localhost:8000;
}

upstream streamlit {
    server localhost:8501;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /admin {
        proxy_pass http://streamlit;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 3. SSL с Let's Encrypt

```bash
# Установить certbot
apt-get install certbot python3-certbot-nginx

# Получить сертификат
certbot --nginx -d your-domain.com
```

## Troubleshooting

### Backend не стартует

```bash
# Проверить логи
docker-compose logs backend

# Проверить переменные окружения
docker-compose exec backend env | grep -E "SECRET_KEY|DATABASE_URL"

# Перезапустить
docker-compose restart backend
```

### Проблемы с БД

```bash
# Проверить подключение
docker-compose exec backend python -c "from src.models.database import engine; print(engine.connect())"

# Пересоздать БД
docker-compose down -v
docker-compose up -d postgres
docker-compose exec postgres psql -U contract_user -d contract_ai -f /docker-entrypoint-initdb.d/init.sql
```

### Недостаточно памяти

Увеличьте лимиты в `docker-compose.yml`:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 8G
```

### Конфликт портов

Измените порты в `docker-compose.yml`:

```yaml
services:
  backend:
    ports:
      - "8080:8000"  # Внешний:Внутренний
```

## Мониторинг и метрики

### Prometheus + Grafana (опционально)

Добавьте в `docker-compose.yml`:

```yaml
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

## Обновление системы

```bash
# 1. Сделать бэкап
docker-compose exec postgres pg_dump -U contract_user contract_ai > backup_$(date +%Y%m%d).sql

# 2. Остановить сервисы
docker-compose down

# 3. Обновить код
git pull origin main

# 4. Пересобрать образы
docker-compose build

# 5. Запустить
docker-compose up -d

# 6. Применить миграции
docker-compose exec backend alembic upgrade head
```

## Безопасность

### Чеклист безопасности для production:

- ✅ Изменить все дефолтные пароли (PostgreSQL, Redis)
- ✅ Сгенерировать уникальный SECRET_KEY
- ✅ Использовать HTTPS (nginx + certbot)
- ✅ Настроить firewall (ufw/iptables)
- ✅ Ограничить доступ к портам БД (только localhost)
- ✅ Включить автообновления (unattended-upgrades)
- ✅ Настроить мониторинг и алерты
- ✅ Регулярные бэкапы БД
- ✅ Логирование и ротация логов
- ✅ Rate limiting на nginx уровне

---

**Документация актуальна для Contract AI System v1.0.0**
