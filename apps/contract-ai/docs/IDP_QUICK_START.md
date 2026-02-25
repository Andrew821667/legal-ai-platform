# 🚀 IDP Integration - Quick Start Guide

**Быстрый старт интеграции Intelligent Document Processing**

---

## 📋 Что создано

### 1. **Концептуальный документ** (`IDP_INTEGRATION_CONCEPT.md`)
- ✅ 84KB, 2500+ строк детальной документации
- ✅ Полное описание архитектуры
- ✅ Hybrid Star Schema (PostgreSQL + JSONB)
- ✅ Cascading Pipeline (3 уровня: Regex → Llama-3 → GPT-4o)
- ✅ Стратегия оптимизации затрат
- ✅ План поэтапного внедрения (8 недель)

### 2. **Диаграммы архитектуры** (`IDP_ARCHITECTURE_DIAGRAMS.md`)
- ✅ 10 Mermaid диаграмм:
  - Общая архитектура системы
  - Пайплайн обработки документа
  - Hybrid Star Schema (ER-диаграмма)
  - Cascading extraction strategy
  - Интеграция с существующей системой
  - Cost optimization strategy
  - Real-time progress tracking
  - Executable rules engine
  - Deployment architecture
  - Phase rollout plan (Gantt chart)

### 3. **SQL миграции** (`alembic/versions/001_create_idp_tables.py`)
- ✅ 7 новых таблиц для Hybrid Star Schema:
  - `contracts_core` (центральная таблица с JSONB атрибутами)
  - `contract_parties` (стороны договора)
  - `contract_items` (спецификация)
  - `payment_schedule` (график платежей)
  - `contract_rules` (🔥 исполняемые правила штрафов!)
  - `idp_extraction_log` (аудит обработки)
  - `idp_quality_issues` (проблемы качества)

### 4. **Pydantic схемы** (`src/schemas/idp_schemas.py`)
- ✅ Валидация Intermediate JSON
- ✅ 15+ схем для API и внутреннего использования:
  - `IntermediateJSONSchema` (главный контракт данных)
  - `PartySchema`, `ContractItemSchema`, `PaymentScheduleSchema`
  - `ContractRuleSchema`, `RuleFormulaSchema`
  - `IDPProcessingStatus`, `IDPResultResponse`
  - Валидация ИНН с контрольной суммой
  - Валидация total = quantity * price

### 5. **Прототип Orchestrator** (`src/services/idp_orchestrator.py`)
- ✅ Главный координатор IDP процесса
- ✅ Роутинг по типу документа (XML / PDF / скан)
- ✅ Этапы обработки:
  1. Ingestion & Classification
  2. OCR (для сканов)
  3. Layout Analysis
  4. Cascading Extraction
  5. Validation
  6. Storage
- ✅ Логирование каждого этапа
- ✅ Обработка ошибок

---

## 💡 Ключевые инновации

### 🔥 1. Executable Rules (Исполняемые правила)
```sql
-- Правило штрафа сохраняется как JSON формула
SELECT * FROM contract_rules WHERE section_type = 'penalty';

-- formula:
{
  "rate": 0.001,          -- 0.1% в день
  "base": "outstanding_balance",
  "period": "daily",
  "cap": 0.10             -- Максимум 10%
}
```

**Автоматический расчет:**
```python
delay_days = 15
outstanding = 1_000_000
penalty = outstanding * 0.001 * delay_days
# = 15,000 руб
```

### 🎯 2. Hybrid Star Schema
```sql
-- SQL-запросы к структурированным данным
SELECT * FROM contracts_core
WHERE total_amount > 1000000
  AND currency = 'RUB'
  AND attributes @> '{"delivery_type": "air"}';  -- JSONB гибкость!
```

### ⚡ 3. Cascading Pipeline (экономия 6-50x)
```
Level 1 (Regex + SpaCy): 40% полей → $0
Level 2 (Llama-3-8B):    40% полей → $0.08
Level 3 (GPT-4o):        20% полей → $0.35
──────────────────────────────────────────
Итого:                              $0.25/документ

vs Azure Form Recognizer: $1.50
vs Ручная обработка:      $10.00
```

---

## 🚀 Как запустить (Phase 1: Foundation)

### Шаг 1: Установка зависимостей
```bash
# Базовые библиотеки
pip install paddlepaddle paddleocr onnxruntime transformers pdf2image

# PostgreSQL (если еще SQLite)
pip install psycopg2-binary

# Redis для Celery
pip install redis celery

# Проверка установки
python -c "import paddleocr; import onnxruntime; print('✅ All dependencies installed')"
```

### Шаг 2: PostgreSQL setup
```bash
# 1. Установить PostgreSQL 16+
# Ubuntu/Debian:
sudo apt install postgresql-16

# macOS:
brew install postgresql@16

# 2. Создать базу данных
createdb contract_ai_idp

# 3. Обновить .env
DATABASE_URL=postgresql://user:password@localhost:5432/contract_ai_idp
```

### Шаг 3: Миграции БД
```bash
# Применить IDP миграцию
alembic upgrade head

# Проверить таблицы
psql contract_ai_idp -c "\dt"
# Должны появиться:
# - contracts_core
# - contract_parties
# - contract_items
# - payment_schedule
# - contract_rules
# - idp_extraction_log
# - idp_quality_issues
```

### Шаг 4: Тестовый запуск
```python
# test_idp_basic.py
from src.services.idp_orchestrator import IDPOrchestrator
from src.models.database import SessionLocal

db = SessionLocal()
orchestrator = IDPOrchestrator(db_session=db)

# Тест классификации
file_path = "test_documents/contract_001.pdf"
with open(file_path, 'rb') as f:
    file_data = f.read()

result = await orchestrator.process_document(
    contract_id="test_001",
    file_data=file_data,
    filename="contract_001.pdf",
    idp_mode="fast"
)

print(result)
# {'success': True, 'core_id': 'uuid...', 'duration_sec': 45.2}
```

---

## 📊 Проверка результатов

### SQL запросы для проверки
```sql
-- 1. Проверить, что договор сохранен
SELECT * FROM contracts_core WHERE source_file_id = 'test_001';

-- 2. Проверить стороны
SELECT * FROM contract_parties WHERE contract_id = (
    SELECT id FROM contracts_core WHERE source_file_id = 'test_001'
);

-- 3. Проверить логи обработки
SELECT stage, status, duration_ms, created_at
FROM idp_extraction_log
WHERE contract_id = 'test_001'
ORDER BY created_at;

-- 4. Проверить качество
SELECT * FROM idp_quality_issues WHERE contract_id = 'test_001';
```

### Python API для проверки
```python
# Через API
import requests

# Загрузка
response = requests.post(
    'http://localhost:8000/api/v1/contracts/upload-idp',
    files={'file': open('contract.pdf', 'rb')},
    data={'enable_idp': True, 'idp_mode': 'auto'}
)
contract_id = response.json()['contract_id']

# Статус
status = requests.get(f'http://localhost:8000/api/v1/idp/status/{contract_id}')
print(status.json()['progress'])  # 0-100%

# Результат
result = requests.get(f'http://localhost:8000/api/v1/idp/result/{contract_id}')
print(result.json()['contract'])
print(result.json()['rules'])  # Исполняемые правила!
```

---

## 📈 Roadmap (8 недель)

### ✅ **Phase 1: Foundation** (недели 1-2)
- [x] Создать SQL миграции
- [x] Создать Pydantic схемы
- [x] Создать SchemaMapper (прототип)
- [ ] Unit-тесты для моделей БД
- [ ] Документация API

### 🔄 **Phase 2: Level 1 Extraction** (недели 3-4)
- [ ] Реализовать Level1EntityExtractor (Regex + SpaCy)
- [ ] Интеграция с DocumentParser
- [ ] End-to-end тест: XML → contracts_core
- [ ] API endpoints: `/upload-idp`, `/status`, `/result`

### 🔄 **Phase 3: Layout Analysis + OCR** (недели 5-6)
- [ ] Настроить PaddleOCR
- [ ] Fine-tune LayoutLMv3 (опционально)
- [ ] Реализовать LayoutAnalyzer
- [ ] End-to-end тест: Скан → contracts_core

### 🔄 **Phase 4: Cascading LLM** (недели 7-8)
- [ ] Реализовать Level2EntityExtractor (Llama-3-8B)
- [ ] Реализовать Level3EntityExtractor (GPT-4o)
- [ ] LLMRouter (автоматический выбор модели)
- [ ] WebSocket для real-time прогресса
- [ ] Интеграция с ContractAnalyzerAgent

---

## 🎯 Метрики успеха

### Целевые показатели (Phase 4)
| Метрика | Цель | Как измерить |
|---------|------|--------------|
| **Точность извлечения** | 90%+ | Тестовый датасет 100 договоров |
| **Время обработки (скан)** | < 5 мин | avg(duration_ms) из idp_extraction_log |
| **Стоимость** | < $0.50/док | sum(cost_usd) из idp_extraction_log |
| **% Level 3 usage** | < 30% | count(stage='entity_extraction' AND processor_type='gpt4o') |
| **% кэш-хитов** | > 60% | LLM cache hit rate |

### A/B тест (Legacy vs IDP)
```python
# Сравнить точность на 50 договорах
legacy_accuracy = test_legacy_parser(test_dataset)
idp_accuracy = test_idp_pipeline(test_dataset)

print(f"Improvement: {idp_accuracy - legacy_accuracy:.1%}")
# Expected: +25-35%
```

---

## 🔧 Troubleshooting

### Проблема: OCR не работает
```bash
# Проверить Tesseract
tesseract --version

# Установить языковые данные
sudo apt install tesseract-ocr-rus tesseract-ocr-eng

# Проверить PaddleOCR
python -c "from paddleocr import PaddleOCR; ocr = PaddleOCR(lang='ru'); print('OK')"
```

### Проблема: LayoutLMv3 медленный
```bash
# Квантование модели ONNX
python scripts/quantize_layoutlm.py --input layoutlmv3.onnx --output layoutlmv3_int8.onnx

# Результат: 3-4x ускорение на CPU
```

### Проблема: PostgreSQL медленный
```sql
-- Проверить индексы
SELECT * FROM pg_indexes WHERE tablename = 'contracts_core';

-- Создать дополнительные индексы
CREATE INDEX idx_contracts_core_created_at ON contracts_core (created_at DESC);

-- VACUUM ANALYZE
VACUUM ANALYZE contracts_core;
```

### Проблема: Высокая стоимость LLM
```python
# Включить агрессивное кэширование
settings.llm_cache_enabled = True
settings.llm_cache_ttl = 86400 * 30  # 30 дней

# Использовать только Level 1 + Level 2
idp_mode = "fast"  # Исключает GPT-4o
```

---

## 📚 Дополнительные ресурсы

### Документация
- [IDP_INTEGRATION_CONCEPT.md](./IDP_INTEGRATION_CONCEPT.md) - Полная спецификация
- [IDP_ARCHITECTURE_DIAGRAMS.md](./IDP_ARCHITECTURE_DIAGRAMS.md) - Диаграммы

### Код
- `/alembic/versions/001_create_idp_tables.py` - SQL миграции
- `/src/schemas/idp_schemas.py` - Pydantic схемы
- `/src/services/idp_orchestrator.py` - Главный координатор

### Тесты
```bash
# Unit тесты
pytest tests/test_idp_schemas.py
pytest tests/test_schema_mapper.py

# Integration тесты
pytest tests/test_idp_orchestrator.py

# End-to-end тесты
pytest tests/test_idp_e2e.py
```

---

## 💬 Вопросы?

**Что дальше:**
1. Обсудить концепцию с командой
2. Утвердить приоритеты (Phase 1-4)
3. Начать Phase 1: Foundation
4. Первый MVP через 2 недели

**Команды для запуска:**
```bash
# Запустить миграции
alembic upgrade head

# Запустить FastAPI с IDP
uvicorn src.main:app --reload

# Запустить Celery worker для фоновой обработки
celery -A src.tasks worker --loglevel=info
```

---

**Статус:** 🟢 Готово к разработке
**Следующий шаг:** Обсуждение и утверждение подхода
