# Stage 12: Contract Generator Agent

## ✅ Реализовано

### 1. Contract Generator Agent (`src/agents/contract_generator_agent.py`)

**Функционал:**
- ✅ Извлечение параметров из запроса (LLM)
- ✅ Поиск шаблона (тип + семантический + правовой анализ через RAG)
- ✅ Генерация договора (LLM + шаблон + RAG context)
- ✅ Валидация сгенерированного договора
- ✅ Запрос пользователю при отсутствии шаблона

**Workflow:**
1. **Extract Parameters** - извлечение через LLM:
   - Тип договора, стороны (с реквизитами ИНН, КПП, адрес, банк)
   - Предмет, цена (сумма, валюта, НДС), сроки
   - Особые условия, штрафы, ответственность, условия оплаты

2. **Find Template** - поиск по типу + RAG semantic search
   - Если не найден → статус `template_selection_required` → review queue

3. **RAG Context (Комбинированный вариант D)**:
   - Лучшие формулировки из успешных договоров
   - Прецеденты по параметрам
   - Правовые нормы (ГК РФ, НК РФ, отраслевые)

4. **Generate Contract** - LLM с шаблоном + RAG контекст

5. **Validate**:
   - XML структура
   - Обязательные разделы (договор, стороны, предмет, цена, срок)
   - Наличие сторон и цены
   - Юридическая чистота (ГК РФ, НК РФ, антимонопольное)

6. **Route** - по умолчанию в review queue

### 2. Feedback System для ML

#### Database Schema (`database/migration_contract_feedback.sql`)
```sql
CREATE TABLE contract_feedback (
    id SERIAL PRIMARY KEY,
    contract_id INTEGER,
    user_id INTEGER,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    acceptance_status BOOLEAN,
    user_corrections JSONB,
    generation_params JSONB,
    template_id INTEGER,
    rag_context_used JSONB,
    validation_errors INTEGER,
    validation_warnings INTEGER,
    generation_duration FLOAT,
    user_comment TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### SQLAlchemy Model (`src/models/database.py`)
- ✅ Добавлена модель `ContractFeedback`
- ✅ Relationships с Contract, User, Template
- ✅ Валидация rating (1-5)
- ✅ JSON поля для corrections, params, RAG context

#### Feedback Service (`src/services/feedback_service.py`)

**Методы:**
- `create_feedback()` - создание записи feedback
- `update_feedback()` - обновление (rating, acceptance, corrections)
- `get_feedback()` - получение по contract_id
- `get_all_feedback()` - с фильтрами (min_rating, acceptance_status)
- `export_training_data()` - экспорт в JSONL/JSON для fine-tuning
- `get_statistics()` - статистика (total, accepted, rejected, avg_rating)

**Формат экспорта для обучения:**
```json
{
  "messages": [
    {"role": "system", "content": "You are a legal contract generation expert..."},
    {"role": "user", "content": "Generate contract with parameters: ..."},
    {"role": "assistant", "content": "<?xml version...>"}
  ],
  "metadata": {
    "contract_id": "...",
    "rating": 5,
    "template_id": "...",
    "validation_errors": 0
  }
}
```

### 3. Интеграция

- ✅ Обновлен `src/agents/__init__.py` - импорт Contract Generator
- ✅ Добавлен `ContractFeedback` в `__all__` моделей

## 🔄 Workflow

```
User Request
    ↓
Onboarding Agent (parse, classify)
    ↓
Contract Generator Agent
    ↓
1. Extract params (LLM)
2. Find template (DB + RAG)
    ├─→ Found: continue
    └─→ Not found: template_selection_required → Review Queue
3. Get RAG context (formulations + precedents + legal norms)
4. Generate contract (LLM + template + RAG)
5. Validate
6. Save to DB
    ↓
Review Queue (default)
    ↓
User reviews
    ├─→ Accept: feedback (rating 4-5)
    ├─→ Edit: feedback (corrections)
    └─→ Reject: feedback (rating 1-2)
    ↓
Feedback DB → Training Data Export (future fine-tuning)
```

## 📊 Юридическая чистота

Проверки:
- ✅ ГК РФ (общие положения, обязательства)
- ✅ Налоговый кодекс (НДС, налогообложение)
- ✅ Отраслевые нормы (зависит от типа)
- ✅ Антимонопольное законодательство
- ❌ Трудовой кодекс НЕ применяется для ГПХ

## 🎯 Fine-tuning Strategy

**Текущая реализация (Stage 12):**
- ✅ Сбор feedback в БД
- ✅ Хранение параметров генерации
- ✅ Функция `export_training_data()`
- ✅ Логирование всех операций

**Будущее (отдельный Stage):**
- ⏳ Автоматизация fine-tuning
- ⏳ Интеграция с OpenAI/Anthropic API
- ⏳ Budget control и мониторинг
- ⏳ A/B тестирование моделей

## 📁 Файлы

**Созданы:**
- `src/agents/contract_generator_agent.py` - агент генерации
- `src/services/feedback_service.py` - сервис feedback
- `database/migration_contract_feedback.sql` - миграция БД
- `STAGE_12_CONTRACT_GENERATOR.md` - документация

**Изменены:**
- `src/models/database.py` - добавлена модель ContractFeedback
- `src/agents/__init__.py` - импорт Contract Generator

## ✨ Особенности

1. **RAG Integration** - комбинированный подход D:
   - Semantic search для formulations
   - Precedent search по параметрам
   - Legal norms search (ГК РФ, НК РФ)

2. **Template Selection** - если шаблон не найден:
   - Создается request со статусом `template_selection_required`
   - Отправляется в review queue
   - Пользователь выбирает: новый шаблон ИЛИ адаптация существующего

3. **Validation** - многоуровневая:
   - XML structure
   - Mandatory sections
   - Parties & price presence
   - Legal compliance hints

4. **Feedback Loop** - готовность к обучению:
   - Все параметры генерации сохраняются
   - User corrections tracked
   - Rating system (1-5)
   - Export to JSONL for fine-tuning

## 🚀 Следующий этап

**Stage 13: Contract Analyzer Agent** - анализ существующих договоров
