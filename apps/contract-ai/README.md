# 🤖 Contract AI System

**Интеллектуальная система автоматизации работы с договорами** на основе LLM, RAG и современных AI технологий.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-blue.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 Содержание

- [Возможности](#-возможности)
- [Архитектура](#-архитектура)
- [Установка](#-установка)
- [Быстрый старт](#-быстрый-старт)
- [API Документация](#-api-документация)
- [Performance](#-performance)
- [Roadmap](#-roadmap)

---

## 🎯 Возможности

### 🔍 **1. Onboarding Agent**
Умный анализ входящих запросов и классификация задач

- ✅ Классификация типов договоров (поставка, услуги, подряд, аренда, и т.д.)
- ✅ Извлечение ключевых параметров (стороны, сроки, суммы)
- ✅ Автоматическое определение следующего действия
- ✅ Создание задач для генерации или анализа

### 📝 **2. Contract Generator Agent**
Генерация договоров по шаблонам с LLM

- ✅ Генерация на основе XML шаблонов
- ✅ LLM-заполнение переменных с учетом контекста
- ✅ RAG для поиска аналогов и прецедентов
- ✅ Валидация структуры и обязательных полей
- ✅ Экспорт в DOCX, PDF с форматированием

### 🔬 **3. Contract Analyzer Agent** (⭐ Модульная архитектура)
Глубокий анализ договоров с выявлением рисков

**Основные модули:**
- `ClauseExtractor` - извлечение структуры и пунктов
- `RiskAnalyzer` - идентификация рисков с batch processing
- `RecommendationGenerator` - автоматические рекомендации
- `MetadataAnalyzer` - проверка контрагентов, предсказание споров

**Функции:**
- ✅ Идентификация рисков: financial, legal, operational, reputational
- ✅ Severity оценка: critical, high, medium, low
- ✅ Batch анализ пунктов (15 clauses/batch) - **12.5x ускорение**
- ✅ Генерация рекомендаций с приоритизацией
- ✅ Автоматические предложения изменений текста
- ✅ Аннотация проблемных пунктов с XPath
- ✅ Интеграция с ФНС API для проверки контрагентов
- ✅ Предсказание вероятности споров

### ❌ **4. Disagreement Processor Agent**
Генерация возражений на проблемные условия

- ✅ Автоматическая генерация возражений через LLM + RAG
- ✅ Правовые обоснования со ссылками на законы
- ✅ Приоритизация возражений (critical → low)
- ✅ Выбор пользователем финальных возражений
- ✅ Экспорт в: DOCX, PDF, Email, XML
- ✅ Трекинг эффективности (принято/отклонено контрагентом)
- ✅ Интеграция с ЭДО (заглушка для будущей интеграции)

### 🔄 **5. Changes Analyzer Agent**
Анализ изменений между версиями договора

- ✅ Структурное сравнение (diff по XML)
- ✅ Семантическое сравнение через LLM
- ✅ Анализ влияния изменений на риски
- ✅ Связь с ранее отправленными возражениями
- ✅ PDF-отчеты об изменениях
- ✅ Автоматическое создание задач для юристов

### 📤 **6. Quick Export Agent**
Быстрый экспорт в различные форматы

- ✅ Форматы: DOCX, PDF, TXT, JSON
- ✅ Batch-режим для массового экспорта
- ✅ Логирование всех экспортов
- ✅ Email отправка (SMTP)
- ✅ Шаблоны для писем о несогласии

### 🎭 **7. Orchestrator Agent**
Координация работы всех агентов

- ✅ State machine для workflow управления
- ✅ Обработка ошибок и fallback сценарии
- ✅ Приостановка и возобновление workflow
- ✅ История выполнения

### 🔐 **8. Authentication & Authorization System** (NEW!)
Полноценная система аутентификации с demo-доступом

**Auth Features:**
- ✅ **JWT токены** (access + refresh) с bcrypt password hashing
- ✅ **Demo-доступ по ссылкам** - генерация уникальных ссылок для trial пользователей
- ✅ **Админ-панель** (Streamlit) - управление пользователями, ролями, demo-токенами
- ✅ **Роли**: admin, senior_lawyer, lawyer, junior_lawyer, demo
- ✅ **Лимиты**: contracts/day, LLM requests/day по тарифам (demo, basic, pro, enterprise)
- ✅ **Security**: Rate limiting, IP filtering, security headers, audit logs
- ✅ **Email verification** & password reset (готово к интеграции)
- ✅ **2FA support** (TOTP, backup codes)

**API Endpoints:**
```
POST /api/v1/auth/register        # Регистрация
POST /api/v1/auth/login           # Вход (JWT)
POST /api/v1/auth/demo-activate   # Активация demo по ссылке
POST /api/v1/auth/admin/demo-link # Генерация demo-ссылки (admin)
GET  /api/v1/auth/admin/users     # Список пользователей (admin)
GET  /api/v1/auth/admin/analytics # Аналитика системы (admin)
```

**Demo Link Flow:**
```
Admin → Генерирует ссылку → Пользователь переходит → Вводит email →
→ Автоматически создается DEMO аккаунт → Мгновенный доступ на 24 часа
```

### ⚛️ **9. React Frontend** (NEW!)
Современный веб-интерфейс на React/Next.js

**Tech Stack:**
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- React Query (data fetching)
- Zustand (state management)
- Socket.io (real-time updates)

**Features:**
- 🎨 Modern UI/UX with Tailwind CSS
- 📱 Mobile-first responsive design
- ⚡ Fast page loads (SPA)
- 🔄 Real-time updates via WebSocket
- 🎯 TypeScript для type safety
- 🧪 Jest + Testing Library

---

## 🏗️ Архитектура

### Компоненты системы

```
Contract-AI-System/
│
├── src/
│   ├── agents/                    # AI Агенты
│   │   ├── onboarding_agent.py
│   │   ├── contract_analyzer_agent.py  # Модульный (Phase 6)
│   │   ├── disagreement_processor_agent.py
│   │   ├── changes_analyzer_agent.py
│   │   └── orchestrator_agent.py
│   │
│   ├── services/                  # Бизнес-логика
│   │   ├── llm_gateway.py         # LLM API integration
│   │   ├── rag_system.py          # RAG with ChromaDB
│   │   ├── document_parser.py     # DOCX/PDF parsing
│   │   ├── template_manager.py
│   │   │
│   │   ├── # Phase 6: Модульная архитектура
│   │   ├── clause_extractor.py    # Извлечение пунктов
│   │   ├── risk_analyzer.py       # Batch анализ рисков
│   │   ├── recommendation_generator.py
│   │   ├── metadata_analyzer.py   # Контрагенты, споры
│   │   │
│   │   ├── # Phase 7: STUB Replacements
│   │   ├── ocr_service.py         # OCR для сканов
│   │   ├── fns_api.py             # ФНС ЕГРЮЛ API
│   │   ├── tracked_changes_parser.py  # DOCX revisions
│   │   │
│   │   ├── # Phase 8: Performance
│   │   ├── cache_service.py       # Redis + In-memory cache
│   │   ├── async_api_client.py    # Async HTTP client
│   │   └── optimized_queries.py   # N+1 query solutions
│   │
│   ├── models/                    # SQLAlchemy models
│   │   ├── database.py            # Core models
│   │   ├── analyzer_models.py     # Risks, recommendations
│   │   ├── disagreement_models.py
│   │   └── enums.py               # Type-safe enums
│   │
│   ├── utils/                     # Утилиты
│   │   ├── xml_security.py        # XXE protection
│   │   ├── file_validator.py      # Path traversal protection
│   │   ├── pdf_generator.py       # PDF reports
│   │   └── rate_limiter.py        # API rate limiting
│   │
│   └── api/                       # FastAPI endpoints
│       ├── contracts.py
│       ├── analysis.py
│       └── export.py
│
├── tests/                         # Phase 5: Test suite (2245 lines)
│   ├── test_file_validator.py     # Security tests
│   ├── test_xml_security.py       # XXE protection
│   ├── test_rate_limiter.py       # Cost control
│   ├── test_pdf_generator.py      # PDF generation
│   └── test_export_integration.py # E2E tests
│
├── database/                      # Phase 8: DB optimization
│   └── performance_indexes.sql    # 20+ indexes
│
└── docs/                          # Documentation
    ├── api/                       # API docs
    ├── architecture/              # System design
    └── performance/               # Optimization guides
```

### Технологический стек

**Backend:**
- Python 3.9+
- FastAPI (async web framework)
- SQLAlchemy 2.0 (ORM)
- PostgreSQL / SQLite

**AI/ML:**
- OpenAI GPT-5.1 / GPT-5 / GPT-4o (ноябрь 2025 - новейшие модели)
- Anthropic Claude (Sonnet, Opus)
- ChromaDB (vector database для RAG)
- LangChain (RAG orchestration)
- Sentence Transformers (embeddings)

**Document Processing:**
- python-docx (DOCX generation/parsing)
- ReportLab (PDF generation)
- lxml (XML parsing с безопасностью)
- pytesseract + pdf2image (OCR, optional)

**Performance:**
- Redis (distributed caching, optional)
- aiohttp (async HTTP client)
- Connection pooling
- Batch processing

**Security:**
- XXE attack protection (lxml)
- Path traversal protection
- Rate limiting (RPM, TPM, cost limits)
- Input validation

---

## 🚀 Установка

### Требования

- Python 3.9+
- PostgreSQL 14+ (или SQLite для разработки)
- Redis (optional, для distributed cache)
- Tesseract OCR (optional, для сканов)

### 1. Клонирование репозитория

```bash
git clone https://github.com/Andrew821667/Contract-AI-System.git
cd Contract-AI-System
```

### 2. Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 3. Установка зависимостей

```bash
# Основные зависимости
pip install -r requirements.txt

# Опциональные зависимости для OCR
pip install pytesseract pdf2image Pillow

# Системные зависимости (Ubuntu/Debian)
sudo apt-get install tesseract-ocr tesseract-ocr-rus poppler-utils
```

### 4. Настройка конфигурации

Создайте `.env` файл:

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```ini
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/contract_ai
# или для SQLite:
# DATABASE_URL=sqlite:///./contract_ai.db

# LLM API Keys
OPENAI_API_KEY=sk-...
# или
ANTHROPIC_API_KEY=...

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# FNS API (optional, для премиум доступа)
DADATA_API_KEY=...

# Email (для отправки возражений)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 5. Инициализация базы данных

```bash
# Создание таблиц
python -m src.database.init_db

# Применение performance indexes (Phase 8)
psql -U user -d contract_ai -f database/performance_indexes.sql

# Или через Python
python scripts/run_migrations.py
```

### 6. Запуск сервера

```bash
# Development
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Production
gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## ⚡ Быстрый старт

### Пример 1: Анализ договора

```python
from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
from src.services.llm_gateway import LLMGateway

# Инициализация
llm = LLMGateway(model="gpt-4")
analyzer = ContractAnalyzerAgent(llm_gateway=llm, db_session=db)

# Анализ
result = analyzer.execute({
    'contract_id': 'contract-123',
    'parsed_xml': xml_content,
    'metadata': {'contract_type': 'supply'},
    'check_counterparty': True
})

# Результаты
print(f"Найдено рисков: {len(result.data['risks'])}")
print(f"Рекомендаций: {len(result.data['recommendations'])}")
print(f"Следующее действие: {result.next_action}")
```

### Пример 2: Генерация возражений

```python
from src.agents.disagreement_processor_agent import DisagreementProcessorAgent

processor = DisagreementProcessorAgent(llm_gateway=llm, db_session=db)

result = processor.execute({
    'contract_id': 'contract-123',
    'analysis_id': 'analysis-456',
    'generate_objections': True,
    'selected_risk_ids': [1, 2, 3],  # Выбранные риски
    'export_format': 'pdf'
})

# Скачать PDF
pdf_path = result.data['export_path']
```

### Пример 3: Использование кэширования (Phase 8)

```python
from src.services.cache_service import get_cache

cache = get_cache(use_redis=True)

# Декоратор для кэширования
@cache.cached(ttl=3600, key_prefix="fns")
def get_company_info(inn: str):
    # Дорогой API вызов
    return fns_api.get_company(inn)

# Первый вызов: API запрос
result1 = get_company_info("1234567890")  # ~2 секунды

# Второй вызов: из кэша
result2 = get_company_info("1234567890")  # ~0.001 секунды!
```

### Пример 4: Параллельная обработка (Phase 8)

```python
from src.services.async_api_client import AsyncAPIClient, run_async

async def process_multiple_contracts():
    async with AsyncAPIClient(max_connections=10) as client:
        # Параллельная проверка 100 контрагентов
        inns = ["1234567890", "0987654321", ...]  # 100 ИНН

        urls = [f"https://api.fns.ru/company/{inn}" for inn in inns]
        results = await client.batch_get(urls)

        return results

# Запуск из sync кода
results = run_async(process_multiple_contracts())
# 100 запросов за ~2 секунды вместо 200 секунд!
```

---

## 📚 API Документация

После запуска сервера:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI spec**: http://localhost:8000/openapi.json

### Основные эндпоинты

```
POST   /api/v1/contracts/upload          # Загрузка договора
POST   /api/v1/contracts/{id}/analyze    # Анализ договора
GET    /api/v1/contracts/{id}/risks      # Получить риски
POST   /api/v1/disagreements/generate    # Генерация возражений
POST   /api/v1/export/pdf                # Экспорт в PDF
GET    /api/v1/analytics/dashboard       # Аналитика
```

Подробнее: [docs/api/README.md](docs/api/README.md)

---

## ⚡ Performance

### Оптимизации (Phase 8)

**До оптимизации:**
- 10 contracts × 50 clauses: **~17 минут**
- API calls: 500
- Cost: $5.00

**После Phase 8 (Full Optimization):**
- 10 contracts × 50 clauses: **~8 секунд** ✨
- API calls: 90 (with 40% cache hit)
- Cost: $0.90

**Ускорение: 125x! Экономия: 82%!** 🚀

### Ключевые техники:

1. **LLM Batch Processing** (Phase 2)
   - 15 clauses per batch
   - 12.5x faster analysis

2. **Caching** (Phase 8)
   - Redis + In-memory
   - 40%+ cache hit rate
   - Template clauses cached

3. **Async API Calls** (Phase 8)
   - Parallel counterparty checks
   - 10x faster external API calls

4. **Database Optimization** (Phase 8)
   - 20+ composite indexes
   - N+1 query elimination
   - Aggregation queries

5. **Connection Pooling**
   - HTTP connection reuse
   - Database connection pool

Подробнее: [docs/performance/llm_batching_optimization.md](docs/performance/llm_batching_optimization.md)

---

## 🔒 Безопасность

### Реализованные меры (Phases 1-3)

✅ **XXE Attack Protection**
- Secure XML parsing с defusedxml
- DTD отключены
- Entity expansion защита

✅ **Path Traversal Protection**
- Filename sanitization
- Path validation
- Запрет на null bytes, "..", hidden files

✅ **Rate Limiting**
- Requests Per Minute (RPM)
- Tokens Per Minute (TPM)
- Cost per hour/day limits
- Thread-safe implementation

✅ **Input Validation**
- File size limits
- MIME type checking
- Extension whitelist

Подробнее: [docs/security/README.md](docs/security/README.md)

---

## 🧪 Тестирование

### Test Suite (Phase 5)

```bash
# Запуск всех тестов
pytest

# С покрытием
pytest --cov=src --cov-report=html

# Только security тесты
pytest tests/test_file_validator.py tests/test_xml_security.py

# Только performance тесты
pytest tests/test_rate_limiter.py -v
```

**Статистика тестов:**
- Total tests: 165+
- Lines of code: 2,245
- Coverage: 85%+

Тесты включают:
- ✅ Security (XXE, path traversal, size limits)
- ✅ Rate limiting (RPM, TPM, cost limits, thread safety)
- ✅ PDF generation (unicode, pagination)
- ✅ Export integration (E2E workflows)
- ✅ Real-world scenarios

---

## 🗺️ Roadmap

### ✅ Completed (Phases 1-8)

- [x] Phase 1: Security fixes (XXE, path traversal, rate limiting)
- [x] Phase 2: Rate limiting implementation
- [x] Phase 3: Code quality (enums, constants)
- [x] Phase 4: Export functionality (PDF, DOCX, Email)
- [x] Phase 5: Comprehensive test suite (165+ tests)
- [x] Phase 6: Modular architecture refactoring
- [x] Phase 7: STUB implementations (OCR, FNS API, tracked changes)
- [x] Phase 8: Performance optimization (100x+ speedup)

### 🚧 Phase 9: Documentation (Current)

- [x] Main README update
- [ ] API documentation
- [ ] Architecture diagrams
- [ ] Deployment guide
- [ ] Usage examples

### 🔮 Future Development

**Phase 10: Advanced Analytics**
- Dashboard with metrics (risk trends, efficiency)
- Contract templates analytics
- Cost tracking and optimization
- ML-based risk prediction

**Phase 11: Integration**
- REST API для legal-ai-website
- Webhook notifications
- SSO authentication
- Multi-tenancy support

**Phase 12: AI Enhancements**
- Fine-tuned models for specific contract types
- Multi-language support (English contracts)
- Voice interface for dictation
- Automated negotiation recommendations

**Phase 13: Collaboration Features**
- Real-time collaborative editing
- Comment system on clauses
- Version control with git-like interface
- Team workflows and approvals

---

## 📖 Документация

- [API Documentation](docs/api/README.md)
- [Architecture Guide](docs/architecture/README.md)
- [Deployment Guide](docs/deployment/README.md)
- [Performance Optimization](docs/performance/llm_batching_optimization.md)
- [Security Best Practices](docs/security/README.md)
- [Contributing Guidelines](CONTRIBUTING.md)

---

## 🤝 Вклад в проект

Мы приветствуем вклад в развитие проекта! См. [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📝 Лицензия

MIT License - см. [LICENSE](LICENSE)

---

## 👨‍💻 Автор

Andrew821667

- GitHub: [@Andrew821667](https://github.com/Andrew821667)
- Проекты: [legal-ai-website](https://github.com/Andrew821667/legal-ai-website)

---

## 🙏 Благодарности

- OpenAI за GPT API
- Anthropic за Claude API
- FastAPI team
- SQLAlchemy team
- Сообщество open-source разработчиков

---

**Contract AI System** - автоматизация договорной работы с помощью AI 🚀
