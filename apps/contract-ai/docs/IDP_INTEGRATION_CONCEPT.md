# 🚀 Концепция интеграции IDP (Intelligent Document Processing) в Contract AI System

**Дата:** 2026-01-08
**Статус:** Концепция для обсуждения
**Цель:** Превращение неструктурированных договоров в "Вычислимые контракты" (Computable Contracts)

---

## 📋 Содержание

1. [Исполнительное резюме](#исполнительное-резюме)
2. [Текущее состояние системы](#текущее-состояние-системы)
3. [Целевая архитектура IDP](#целевая-архитектура-idp)
4. [Гибридная схема базы данных](#гибридная-схема-базы-данных)
5. [Технологический стек IDP](#технологический-стек-idp)
6. [Пайплайн обработки документов](#пайплайн-обработки-документов)
7. [Интеграция с существующей системой](#интеграция-с-существующей-системой)
8. [API контракт](#api-контракт)
9. [Стратегия оптимизации затрат](#стратегия-оптимизации-затрат)
10. [План поэтапного внедрения](#план-поэтапного-внедрения)
11. [Метрики успеха](#метрики-успеха)

---

## 1. Исполнительное резюме

### 🎯 Ключевая цель

Переход от архивного хранения текстов договоров к **хранению структурированных данных и исполняемых правил** в реляционной БД. Это позволит:

- **Автоматизировать** расчет штрафов, пеней, сроков
- **Создавать** dashboard с KPI по портфелю договоров
- **Предсказывать** риски на основе исторических данных
- **Интегрироваться** с ERP/1C для автоматического обмена данными

### 💡 Ключевая инновация

**Гибридная архитектура**: жесткие сущности (стороны, суммы, даты) → PostgreSQL таблицы, гибкие атрибуты → JSONB с GIN-индексами.

### 📊 Ожидаемые результаты

| Метрика | До IDP | После IDP | Улучшение |
|---------|--------|-----------|-----------|
| Точность извлечения данных | 60-70% (regex) | 90-95% (LLM + cascading) | +30-35% |
| Время обработки договора | 5-10 мин (ручная) | 1-3 мин (автоматическая) | 5x ускорение |
| Стоимость обработки | $5-10 (человек) | $0.10-0.50 (AI) | 10-50x снижение |
| Глубина анализа | Поверхностная | Пункт-за-пунктом с прецедентами | 10x глубже |

---

## 2. Текущее состояние системы

### ✅ Что уже есть

#### 2.1 Архитектура
- **Framework:** FastAPI 0.109+ (Python 3.9+)
- **БД:** SQLAlchemy ORM (SQLite default, PostgreSQL-ready)
- **AI Stack:** LangChain, Multi-agent system
- **LLM Providers:** Claude, GPT-4, Perplexity, YandexGPT, DeepSeek, Qwen

#### 2.2 Обработка документов
**DocumentParser** (`src/services/document_parser.py`):
- Форматы: DOCX, PDF → XML
- Базовое извлечение: parties, dates, amounts, INN
- OCR: Tesseract (базовый уровень)
- Таблицы: Извлечение из DOCX

**Ограничения текущей системы:**
- ❌ Нет layout analysis (не понимает визуальную структуру)
- ❌ Низкая точность OCR для сканов (Tesseract CPU)
- ❌ Нет извлечения подписей/печатей
- ❌ Нет классификации типов документов
- ❌ Regex-based extraction (не semantic)
- ❌ Нет хранения structured data в БД (только XML в JSONB)

#### 2.3 База данных
**Модель `Contract`** (`src/models/database.py`):
```python
class Contract(Base):
    id = String(36, PK)
    file_path = Text  # Путь к файлу
    document_type = String(50)  # contract, disagreement, tracked_changes
    contract_type = String(50)  # supply, service, lease
    status = String(50)  # pending, analyzing, completed
    meta_info = Text  # JSON (сейчас хранится XML)
    ...
```

**Проблема:** Данные хранятся как неструктурированный XML в `meta_info`. Невозможно делать SQL-запросы типа:
```sql
-- ❌ Невозможно сейчас
SELECT * FROM contracts
WHERE total_amount > 1000000
  AND currency = 'RUB'
  AND payment_terms LIKE '%prepayment%';
```

#### 2.4 AI-агенты
**ContractAnalyzerAgent** (`src/agents/contract_analyzer_agent.py`):
- ✅ Batch analysis (15 clauses/batch)
- ✅ Risk identification
- ✅ RAG integration (ChromaDB)
- ✅ Counterparty checking (FNS API)
- ✅ Cascading LLM (quick model → deep model)

**Что работает хорошо:**
- Модульная архитектура агентов
- Batch processing для экономии токенов
- Каскадный подход (Level 1: regex, Level 2: Llama-3, Level 3: GPT-4)

---

## 3. Целевая архитектура IDP

### 🏗️ Архитектурная диаграмма

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (React/Next.js)                     │
│          Document Upload → Real-time Progress → Results         │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                     FASTAPI BACKEND                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  API Layer (src/api/contracts/routes.py)                │  │
│  │  POST /api/v1/contracts/upload                           │  │
│  │  POST /api/v1/idp/process                                │  │
│  └─────────────────────┬────────────────────────────────────┘  │
│                        │                                         │
│  ┌─────────────────────▼────────────────────────────────────┐  │
│  │  🆕 IDP Orchestrator (src/services/idp_orchestrator.py)  │  │
│  │  - Document classification                               │  │
│  │  - Router to appropriate pipeline                        │  │
│  │  - Result normalization                                  │  │
│  │  - Error handling & fallback                             │  │
│  └──┬────────┬──────────┬─────────────┬─────────────────────┘  │
│     │        │          │             │                         │
│  ┌──▼──┐ ┌──▼──┐ ┌─────▼─────┐ ┌────▼────────────────────┐   │
│  │XML  │ │ AI  │ │ Hybrid    │ │ Local Processing       │   │
│  │Det  │ │Cloud│ │ (XML+AI)  │ │ (CPU-based models)     │   │
│  │     │ │ IDP │ │           │ │                         │   │
│  └──┬──┘ └──┬──┘ └─────┬─────┘ └────┬────────────────────┘   │
│     │       │          │             │                         │
│  ┌──▼───────▼──────────▼─────────────▼─────────────────────┐  │
│  │  🆕 IDP Data Processor (src/services/idp_processor.py)   │  │
│  │  - Layout analysis (LayoutLMv3 ONNX)                     │  │
│  │  - Entity extraction (BERT NER + LLM cascading)          │  │
│  │  - Table extraction (PaddleOCR + structure analysis)     │  │
│  │  - Signature detection                                   │  │
│  │  - Field validation (Pydantic)                           │  │
│  └───────────────────┬──────────────────────────────────────┘  │
│                      │                                          │
│  ┌───────────────────▼──────────────────────────────────────┐  │
│  │  🆕 Hybrid Star Schema Mapper                            │  │
│  │  (src/services/schema_mapper.py)                         │  │
│  │  - Standard fields → DB columns                          │  │
│  │  - Dynamic fields → JSONB attributes                     │  │
│  │  - Rules → contract_rules table                          │  │
│  └───────────────────┬──────────────────────────────────────┘  │
│                      │                                          │
│  ┌───────────────────▼──────────────────────────────────────┐  │
│  │  PostgreSQL Database                                     │  │
│  │  📊 contracts_core (fact table)                          │  │
│  │  📊 contract_parties, contract_items, payment_schedule   │  │
│  │  📊 contract_rules (executable logic)                    │  │
│  │  📊 idp_extraction_log (audit trail)                     │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 🔧 Ключевые компоненты

#### 3.1 IDP Orchestrator
**Местоположение:** `src/services/idp_orchestrator.py`

**Ответственность:**
- Классификация документа (XML vs PDF vs скан)
- Выбор оптимального пайплайна обработки
- Координация асинхронных задач (Celery/Redis)
- Мониторинг прогресса и ошибок

**Логика роутинга:**
```python
if document.is_xml:
    pipeline = DeterministicXMLParser()
elif document.is_searchable_pdf:
    pipeline = HybridPipeline(ocr=False, llm_level=2)
elif document.is_scanned_pdf:
    pipeline = FullAIPipeline(ocr=True, llm_level=3)
```

#### 3.2 IDP Data Processor
**Местоположение:** `src/services/idp_processor.py`

**Этапы обработки:**
1. **Segmentation** (LayoutLMv3): Header, Preamble, Terms, Payment_Table, Signatures
2. **Cascading Extraction:**
   - Level 1 (CPU, бесплатно): Regex + SpaCy NER → INN, даты, суммы
   - Level 2 (API, дешево): Llama-3-8B → таблицы, условия оплаты
   - Level 3 (API, дорого): GPT-4o → штрафы, форс-мажор, сложные пункты
3. **Normalization:** Слияние результатов в Intermediate JSON
4. **Validation:** Pydantic models

#### 3.3 Schema Mapper
**Местоположение:** `src/services/schema_mapper.py`

**Логика маппинга:**
```python
def map_to_db(intermediate_json: dict) -> DatabaseRecord:
    # Стандартные поля → колонки
    contract_core = {
        'doc_number': extract_field('contract_number'),
        'signed_date': extract_field('signature_date'),
        'total_amount': extract_field('total_amount'),
        'currency': extract_field('currency', default='RUB')
    }

    # Гибкие поля → JSONB attributes
    contract_core['attributes'] = {
        'delivery_type': extract_field('delivery_type'),
        'project_manager': extract_field('project_manager'),
        'special_conditions': extract_field('special_conditions'),
        # ... любые уникальные поля
    }

    # Правила → contract_rules
    rules = extract_rules(intermediate_json)

    return contract_core, rules
```

---

## 4. Гибридная схема базы данных

### 📊 Hybrid Star Schema (PostgreSQL 16+)

#### 4.1 Центральная таблица (Fact Table)

```sql
CREATE TABLE contracts_core (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Стандартные поля (жесткая схема)
    doc_number VARCHAR(100) NOT NULL,
    signed_date DATE,
    status VARCHAR(20) CHECK (status IN ('draft', 'active', 'closed', 'dispute')),
    total_amount NUMERIC(15, 2),
    currency CHAR(3) DEFAULT 'RUB',

    -- 🔑 КЛЮЧЕВАЯ ИННОВАЦИЯ: Гибкие атрибуты
    attributes JSONB,  -- GIN index для быстрого поиска

    -- Полный "сырой" результат парсинга (для истории)
    raw_data JSONB,

    -- Метаданные
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    processed_by VARCHAR(50),  -- 'xml_parser', 'ai_pipeline', 'manual'

    -- Foreign keys
    source_file_id UUID REFERENCES contracts(id),

    -- Индексы
    CONSTRAINT check_amount CHECK (total_amount >= 0)
);

-- GIN индекс для быстрого поиска в JSONB
CREATE INDEX idx_contracts_attributes ON contracts_core USING GIN (attributes);
CREATE INDEX idx_contracts_doc_number ON contracts_core (doc_number);
CREATE INDEX idx_contracts_signed_date ON contracts_core (signed_date);
CREATE INDEX idx_contracts_status ON contracts_core (status);
```

**Пример запроса с JSONB:**
```sql
-- Найти все договоры с доставкой авиатранспортом
SELECT * FROM contracts_core
WHERE attributes @> '{"delivery_type": "air"}';

-- Найти договоры, где project_manager = 'Ivanov'
SELECT * FROM contracts_core
WHERE attributes->>'project_manager' = 'Ivanov';

-- Комбинированный запрос
SELECT * FROM contracts_core
WHERE total_amount > 1000000
  AND currency = 'RUB'
  AND attributes @> '{"priority": "high"}';
```

#### 4.2 Измерения (Dimension Tables)

```sql
-- ============================================================
-- Стороны договора
-- ============================================================
CREATE TABLE contract_parties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID NOT NULL REFERENCES contracts_core(id) ON DELETE CASCADE,

    -- Роль стороны
    role VARCHAR(50) CHECK (role IN ('buyer', 'seller', 'guarantor', 'agent')),

    -- Идентификация
    entity_id UUID,  -- Ссылка на справочник контрагентов (если есть ERP)
    name VARCHAR(500) NOT NULL,
    tax_id VARCHAR(20),  -- ИНН/VAT
    registration_number VARCHAR(50),  -- ОГРН

    -- Контактные данные
    legal_address TEXT,
    actual_address TEXT,
    contact_person VARCHAR(200),
    email VARCHAR(100),
    phone VARCHAR(50),

    -- Банковские реквизиты
    bank_details JSONB,  -- {account, bank_name, bik, correspondent_account}

    -- Метаданные
    created_at TIMESTAMP DEFAULT NOW(),

    -- Индексы
    CONSTRAINT unique_contract_party UNIQUE (contract_id, role, tax_id)
);

CREATE INDEX idx_parties_contract ON contract_parties (contract_id);
CREATE INDEX idx_parties_tax_id ON contract_parties (tax_id);
CREATE INDEX idx_parties_entity ON contract_parties (entity_id);


-- ============================================================
-- Спецификация (позиции договора)
-- ============================================================
CREATE TABLE contract_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID NOT NULL REFERENCES contracts_core(id) ON DELETE CASCADE,

    -- Идентификация позиции
    line_number INTEGER NOT NULL,
    sku_code VARCHAR(100),  -- Артикул для маппинга с номенклатурой

    -- Описание
    name TEXT NOT NULL,
    description TEXT,

    -- Количество и единицы
    quantity NUMERIC(15, 3) NOT NULL,
    unit VARCHAR(20),  -- шт, кг, м, час, etc.

    -- Финансы
    price_unit NUMERIC(15, 2) NOT NULL,
    total_line NUMERIC(15, 2) NOT NULL,
    vat_rate NUMERIC(5, 2),  -- 20%, 10%, 0%
    vat_amount NUMERIC(15, 2),

    -- Дополнительные атрибуты (гибкие)
    attributes JSONB,  -- {color, size, model, delivery_date, etc.}

    created_at TIMESTAMP DEFAULT NOW(),

    -- Ограничения
    CONSTRAINT check_quantity CHECK (quantity > 0),
    CONSTRAINT check_price CHECK (price_unit >= 0),
    CONSTRAINT unique_contract_line UNIQUE (contract_id, line_number)
);

CREATE INDEX idx_items_contract ON contract_items (contract_id);
CREATE INDEX idx_items_sku ON contract_items (sku_code);
CREATE INDEX idx_items_attributes ON contract_items USING GIN (attributes);


-- ============================================================
-- График платежей
-- ============================================================
CREATE TABLE payment_schedule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID NOT NULL REFERENCES contracts_core(id) ON DELETE CASCADE,

    -- Тип платежа
    payment_type VARCHAR(50) CHECK (payment_type IN (
        'prepayment', 'postpayment', 'milestone', 'recurring', 'on_delivery'
    )),

    -- Сумма
    amount NUMERIC(15, 2) NOT NULL,
    percentage NUMERIC(5, 2),  -- % от общей суммы

    -- Сроки
    due_date DATE,  -- Абсолютная дата (если известна)
    due_condition TEXT,  -- Относительная дата: "5 дней после подписания акта"
    days_offset INTEGER,  -- Количество дней от события
    trigger_event VARCHAR(100),  -- Триггер: 'contract_signing', 'delivery', 'act_signing'

    -- Статус
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'overdue', 'cancelled')),
    paid_date DATE,
    paid_amount NUMERIC(15, 2),

    -- Метаданные
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_payment_amount CHECK (amount >= 0)
);

CREATE INDEX idx_payment_contract ON payment_schedule (contract_id);
CREATE INDEX idx_payment_status ON payment_schedule (status);
CREATE INDEX idx_payment_due_date ON payment_schedule (due_date);


-- ============================================================
-- 🔥 ДВИЖОК ПРАВИЛ (Executable Logic)
-- ============================================================
CREATE TABLE contract_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID NOT NULL REFERENCES contracts_core(id) ON DELETE CASCADE,

    -- Тип правила
    section_type VARCHAR(50) CHECK (section_type IN (
        'liability',        -- Ответственность
        'penalty',          -- Штрафы
        'termination',      -- Расторжение
        'sla',              -- SLA/гарантии
        'force_majeure',    -- Форс-мажор
        'dispute',          -- Разрешение споров
        'confidentiality'   -- Конфиденциальность
    )),

    -- Правило (исполняемая логика)
    rule_name VARCHAR(200) NOT NULL,
    trigger_condition TEXT,  -- "delay_days > 0", "quality_defects > 0"

    -- Формула расчета (JSON структура)
    formula JSONB NOT NULL,
    /* Примеры formula:
    {
        "type": "penalty",
        "rate": 0.001,          // 0.1% в день
        "base": "outstanding_balance",  // От чего считаем
        "period": "daily",      // daily, weekly, monthly
        "cap": 0.10,            // Максимум 10%
        "min_amount": 1000      // Минимум 1000 руб
    }

    {
        "type": "termination",
        "trigger": "delay_days > 30",
        "notice_period_days": 10,
        "compensation": "return_prepayment"
    }
    */

    -- Исходный текст из договора (для юридического обоснования)
    original_text TEXT NOT NULL,
    clause_location VARCHAR(200),  -- XPath или номер пункта

    -- Приоритет и активность
    priority INTEGER DEFAULT 0,  -- Для разрешения конфликтов правил
    is_active BOOLEAN DEFAULT TRUE,

    -- Метаданные
    created_at TIMESTAMP DEFAULT NOW(),
    extracted_by VARCHAR(50),  -- 'llm_gpt4', 'manual', 'xml_parser'
    confidence_score NUMERIC(3, 2),  -- 0.00-1.00

    CONSTRAINT check_confidence CHECK (confidence_score BETWEEN 0 AND 1)
);

CREATE INDEX idx_rules_contract ON contract_rules (contract_id);
CREATE INDEX idx_rules_section_type ON contract_rules (section_type);
CREATE INDEX idx_rules_active ON contract_rules (is_active);
CREATE INDEX idx_rules_formula ON contract_rules USING GIN (formula);
```

#### 4.3 Аудит и логирование IDP

```sql
-- ============================================================
-- Лог обработки IDP (для отладки и аудита)
-- ============================================================
CREATE TABLE idp_extraction_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID REFERENCES contracts_core(id) ON DELETE SET NULL,

    -- Этап обработки
    stage VARCHAR(50) CHECK (stage IN (
        'classification', 'ocr', 'layout_analysis',
        'entity_extraction', 'table_extraction',
        'rule_extraction', 'validation'
    )),

    -- Статус
    status VARCHAR(20) CHECK (status IN ('success', 'partial', 'failed')),

    -- Детали
    input_data JSONB,   -- Входные данные этапа
    output_data JSONB,  -- Результат этапа
    error_message TEXT,

    -- Метрики производительности
    duration_ms INTEGER,  -- Время выполнения в мс
    tokens_used INTEGER,  -- Токены LLM (если применимо)
    cost_usd NUMERIC(10, 4),  -- Стоимость этапа

    -- Конфигурация
    processor_type VARCHAR(50),  -- 'layoutlm', 'gpt4o', 'llama3', 'regex'
    model_version VARCHAR(50),

    -- Метаданные
    created_at TIMESTAMP DEFAULT NOW(),

    -- Индексы
    CREATE INDEX idx_idp_log_contract ON idp_extraction_log (contract_id);
    CREATE INDEX idx_idp_log_stage ON idp_extraction_log (stage);
    CREATE INDEX idx_idp_log_status ON idp_extraction_log (status);
);


-- ============================================================
-- Таблица ошибок и предупреждений IDP
-- ============================================================
CREATE TABLE idp_quality_issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID NOT NULL REFERENCES contracts_core(id) ON DELETE CASCADE,
    extraction_log_id UUID REFERENCES idp_extraction_log(id),

    -- Тип проблемы
    issue_type VARCHAR(50) CHECK (issue_type IN (
        'low_ocr_confidence',    -- Низкая уверенность OCR
        'missing_field',          -- Отсутствует обязательное поле
        'ambiguous_value',        -- Неоднозначное значение
        'validation_error',       -- Ошибка валидации
        'conflicting_data'        -- Противоречивые данные
    )),

    -- Уровень серьезности
    severity VARCHAR(20) CHECK (severity IN ('critical', 'warning', 'info')),

    -- Описание
    field_name VARCHAR(100),
    expected_value TEXT,
    actual_value TEXT,
    description TEXT,

    -- Рекомендации
    suggested_action VARCHAR(200),
    requires_manual_review BOOLEAN DEFAULT FALSE,

    -- Статус обработки
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'ignored')),
    resolved_at TIMESTAMP,
    resolved_by UUID REFERENCES users(id),

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_quality_contract ON idp_quality_issues (contract_id);
CREATE INDEX idx_quality_severity ON idp_quality_issues (severity);
CREATE INDEX idx_quality_status ON idp_quality_issues (status);
```

### 🎯 Преимущества Hybrid Star Schema

| Преимущество | Описание | Пример |
|--------------|----------|--------|
| **Структурированные запросы** | Можно делать SQL-агрегации | `SELECT SUM(total_amount) FROM contracts_core WHERE signed_date > '2024-01-01'` |
| **Гибкость** | Новые поля без миграций БД | Добавили `{"delivery_by_train": true}` → автоматически в `attributes` |
| **Производительность** | GIN индексы для JSONB | Поиск по 1М договоров < 50мс |
| **Исполняемые правила** | Автоматический расчет штрафов | `formula: {"rate": 0.001, "period": "daily"}` → Python function |
| **ERP интеграция** | Прямой SQL-экспорт в 1C/SAP | `INSERT INTO 1c_contracts SELECT * FROM contracts_core` |

---

## 5. Технологический стек IDP

### 🧠 AI & ML Stack (Cascading Pipeline)

#### 5.1 Layout Analysis
**Модель:** LayoutLMv3 (Microsoft)
**Задача:** Сегментация документа на визуальные блоки
**Deployment:** ONNX Runtime (CPU inference)
**Производительность:** 3-5 сек/страницу на CPU

**Установка:**
```bash
pip install onnxruntime transformers
```

**Интеграция:**
```python
# src/services/layout_analyzer.py
from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
import onnxruntime

class LayoutAnalyzer:
    def __init__(self):
        self.session = onnxruntime.InferenceSession(
            "models/layoutlmv3-base-finetuned-contracts.onnx"
        )

    def segment_document(self, image_path: str) -> List[DocumentBlock]:
        """
        Разбивает документ на блоки:
        - Header (заголовок)
        - Preamble (преамбула)
        - Terms (условия)
        - Payment_Table (таблица оплаты)
        - Signatures (подписи)
        """
        # Inference через ONNX (CPU, 3-5 сек/страница)
        blocks = self.session.run(...)

        return [
            DocumentBlock(type='header', bbox=(x1,y1,x2,y2), text='...'),
            DocumentBlock(type='terms', bbox=(x1,y1,x2,y2), text='...'),
            ...
        ]
```

#### 5.2 OCR Engine
**Первичный выбор:** PaddleOCR (оптимален для таблиц, лучше чем Tesseract)
**Fallback:** Tesseract (уже интегрирован)
**Облачный fallback:** Azure AI Vision OCR (для сложных случаев)

**Установка PaddleOCR:**
```bash
pip install paddlepaddle paddleocr
```

**Интеграция:**
```python
# src/services/ocr_service.py (расширение существующего)
from paddleocr import PaddleOCR

class EnhancedOCRService:
    def __init__(self):
        # PaddleOCR (primary)
        self.paddle_ocr = PaddleOCR(
            use_angle_cls=True,
            lang='ru',
            use_gpu=False  # CPU mode для MVP
        )

        # Tesseract (fallback)
        self.tesseract = pytesseract

    def extract_text(self, image_path: str, prefer_structure: bool = False) -> OCRResult:
        """
        prefer_structure=True -> используем PaddleOCR (лучше для таблиц)
        prefer_structure=False -> Tesseract (быстрее для простого текста)
        """
        if prefer_structure:
            result = self.paddle_ocr.ocr(image_path, cls=True)
            return self._parse_paddle_result(result)
        else:
            text = self.tesseract.image_to_string(Image.open(image_path), lang='rus')
            return OCRResult(text=text, confidence=None)
```

**Стратегия выбора OCR:**
```
IF image_has_tables OR image_has_complex_layout:
    use PaddleOCR  # 5-10 сек, но точнее
ELSE:
    use Tesseract  # 1-2 сек, достаточно для простого текста
```

#### 5.3 Entity Extraction (Cascading)

##### Level 1: Regex + SpaCy NER (Бесплатно, CPU)
```python
# src/services/entity_extractor.py
import re
import spacy

class Level1EntityExtractor:
    def __init__(self):
        self.nlp = spacy.load("ru_core_news_lg")  # Русская модель

    def extract(self, text: str) -> Dict[str, Any]:
        """
        Извлекает базовые сущности без LLM:
        - ИНН (10/12 цифр с валидацией контрольной суммы)
        - Даты (regex: ДД.ММ.ГГГГ, ДД месяц ГГГГ)
        - Суммы (regex: цифры + 'рублей', 'руб', 'USD')
        - Имена организаций (SpaCy NER: ORG)
        - Имена людей (SpaCy NER: PER)
        """
        entities = {
            'inn': self._extract_inn(text),
            'dates': self._extract_dates(text),
            'amounts': self._extract_amounts(text),
        }

        # SpaCy NER
        doc = self.nlp(text)
        entities['organizations'] = [ent.text for ent in doc.ents if ent.label_ == 'ORG']
        entities['persons'] = [ent.text for ent in doc.ents if ent.label_ == 'PER']

        return entities

    def _extract_inn(self, text: str) -> List[str]:
        # Regex + checksum validation
        inn_pattern = r'\b\d{10}(?:\d{2})?\b'
        candidates = re.findall(inn_pattern, text)
        return [inn for inn in candidates if self._validate_inn_checksum(inn)]
```

##### Level 2: Llama-3-8B / Mistral-Nemo (Дешево, API)
```python
# src/services/entity_extractor.py (продолжение)
class Level2EntityExtractor:
    def __init__(self, llm_gateway: LLMGateway):
        # Используем дешевую модель через API (OpenRouter/DeepInfra)
        self.llm = llm_gateway
        self.llm.model = "meta-llama/llama-3-8b-instruct"  # $0.10/1M tokens

    def extract_tables(self, table_block: DocumentBlock) -> List[Dict]:
        """
        Извлекает таблицы спецификаций, условий оплаты
        """
        prompt = f"""Извлеки данные из таблицы в JSON.

Таблица:
{table_block.text}

Верни JSON массив:
[
  {{"item": "...", "quantity": ..., "price": ..., "total": ...}},
  ...
]"""

        result = self.llm.call(prompt, response_format="json", temperature=0.1)
        return result

    def extract_payment_terms(self, terms_block: DocumentBlock) -> Dict:
        """
        Извлекает условия оплаты
        """
        prompt = f"""Извлеки условия оплаты из текста.

Текст:
{terms_block.text}

Верни JSON:
{{
  "payment_type": "prepayment|postpayment|...",
  "schedule": [
    {{"percentage": 30, "condition": "при подписании", "days_offset": 0}},
    {{"percentage": 70, "condition": "после поставки", "days_offset": 30}}
  ]
}}"""

        result = self.llm.call(prompt, response_format="json", temperature=0.1)
        return result
```

##### Level 3: GPT-4o / Claude 3.5 Sonnet (Дорого, для сложных случаев)
```python
class Level3EntityExtractor:
    def __init__(self, llm_gateway: LLMGateway):
        # Используем SOTA модель через Router
        self.llm = llm_gateway
        self.llm.model = "gpt-4o"  # $2.50/1M input, $10/1M output

    def extract_liability_rules(self, liability_block: DocumentBlock) -> List[Dict]:
        """
        Извлекает правила ответственности и штрафов (самая сложная секция)

        Примеры:
        - "За каждый день просрочки Поставщик уплачивает неустойку 0,1% от стоимости непоставленного товара"
        - "При нарушении срока поставки более 30 дней Покупатель вправе расторгнуть договор"
        """
        prompt = f"""Ты - юрист-эксперт по договорам. Извлеки ВСЕ правила ответственности из текста.

ТЕКСТ РАЗДЕЛА "ОТВЕТСТВЕННОСТЬ СТОРОН":
{liability_block.text}

Для КАЖДОГО правила верни:
{{
  "rule_type": "penalty|termination|compensation",
  "trigger_condition": "описание условия срабатывания",
  "formula": {{
    "rate": 0.001,  // 0.1% = 0.001
    "base": "outstanding_balance|contract_value|...",
    "period": "daily|weekly|one_time",
    "cap": 0.10,  // максимум (если есть)
    "min_amount": 1000  // минимум (если есть)
  }},
  "original_text": "точная цитата из договора",
  "affected_party": "seller|buyer",
  "legal_basis": "ст. 330 ГК РФ"
}}

Будь ОЧЕНЬ внимателен к деталям формул! От этого зависит автоматический расчет штрафов."""

        result = self.llm.call(
            prompt,
            response_format="json",
            temperature=0.2,  # Низкая температура для точности
            use_cache=True,
            db_session=self.db
        )
        return result
```

#### 5.4 LLM Router (RouteLLM pattern)
**Цель:** Автоматически определять, какую модель использовать для каждого блока

```python
# src/services/llm_router.py
class LLMRouter:
    """
    Классифицирует сложность запроса и выбирает оптимальную модель
    """
    def __init__(self):
        self.classifier = self._load_classifier()

    def route(self, task_type: str, text_complexity: float) -> str:
        """
        Returns: model name ("llama-3-8b", "gpt-4o-mini", "gpt-4o")
        """
        if task_type in ['inn', 'dates', 'simple_amounts']:
            return None  # Используем regex (Level 1)

        if task_type in ['tables', 'payment_terms'] and text_complexity < 0.5:
            return "llama-3-8b"  # Level 2: дешево

        if task_type in ['liability', 'force_majeure', 'termination']:
            return "gpt-4o"  # Level 3: дорого, но точно

        # Default: средняя модель
        return "gpt-4o-mini"

    def estimate_complexity(self, text: str) -> float:
        """
        Оценка сложности текста (0.0 - 1.0)
        """
        features = {
            'length': len(text),
            'has_legal_terms': bool(re.search(r'неустойка|штраф|пеня|расторжение', text)),
            'has_formulas': bool(re.search(r'\d+%|\d+\.\d+%', text)),
            'sentence_complexity': self._calculate_sentence_complexity(text)
        }

        # Простая эвристика (можно заменить на ML-модель)
        complexity = (
            features['has_legal_terms'] * 0.4 +
            features['has_formulas'] * 0.3 +
            min(features['length'] / 1000, 1.0) * 0.3
        )

        return min(complexity, 1.0)
```

### 🗄️ Vector Search (для семантического поиска похожих договоров)

**Опции:**
1. **pgvector** (PostgreSQL extension) - проще, меньше зависимостей
2. **Qdrant** (отдельный сервис) - быстрее для больших объемов

**Рекомендация для MVP:** pgvector (уже есть PostgreSQL)

```sql
-- Установка pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Добавляем embedding колонку в contracts_core
ALTER TABLE contracts_core
ADD COLUMN embedding vector(1536);  -- OpenAI ada-002: 1536 dimensions

-- Индекс для быстрого поиска
CREATE INDEX idx_contracts_embedding
ON contracts_core
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

```python
# src/services/semantic_search.py
from sentence_transformers import SentenceTransformer

class SemanticContractSearch:
    def __init__(self, db_session):
        self.db = db_session
        # Многоязычная модель для русского и английского
        self.model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

    def index_contract(self, contract_id: str, text: str):
        """
        Создает embedding для договора и сохраняет в БД
        """
        # Генерируем embedding (384 dimensions)
        embedding = self.model.encode(text)

        # Сохраняем в БД
        self.db.execute(
            "UPDATE contracts_core SET embedding = :emb WHERE id = :id",
            {"emb": embedding.tolist(), "id": contract_id}
        )
        self.db.commit()

    def find_similar(self, query_text: str, limit: int = 10) -> List[Dict]:
        """
        Находит похожие договоры по семантике
        """
        query_embedding = self.model.encode(query_text)

        # Cosine similarity search в PostgreSQL
        results = self.db.execute("""
            SELECT
                id, doc_number,
                1 - (embedding <=> :query_emb) as similarity
            FROM contracts_core
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :query_emb
            LIMIT :limit
        """, {"query_emb": query_embedding.tolist(), "limit": limit})

        return [dict(row) for row in results]
```

### 📦 Storage (S3-compatible)

**Опции:**
1. **MinIO** (self-hosted S3-compatible)
2. **AWS S3** (если в облаке)
3. **Local filesystem** (для MVP)

**Рекомендация для MVP:** Local filesystem → MinIO (при росте)

```python
# src/services/file_storage.py
from pathlib import Path
import shutil

class FileStorage:
    """
    Абстракция хранения файлов (легко заменить на S3 позже)
    """
    def __init__(self, base_path: str = "data/contracts"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def store_original(self, contract_id: str, file_data: bytes, extension: str) -> str:
        """Сохраняет оригинал документа"""
        file_path = self.base_path / "originals" / f"{contract_id}{extension}"
        file_path.parent.mkdir(exist_ok=True)
        file_path.write_bytes(file_data)
        return str(file_path)

    def store_processed(self, contract_id: str, stage: str, data: dict):
        """Сохраняет промежуточные результаты обработки"""
        stage_path = self.base_path / "processed" / contract_id / f"{stage}.json"
        stage_path.parent.mkdir(parents=True, exist_ok=True)
        stage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
```

---

## 6. Пайплайн обработки документов

### 🔄 Полный цикл обработки

```
┌─────────────────────────────────────────────────────────────────┐
│ ЭТАП 1: INGESTION & ROUTING                                     │
│ (IDPOrchestrator)                                               │
└───────────────┬─────────────────────────────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ Classify file │
        │   type/format │
        └───────┬───────┘
                │
    ┌───────────┼───────────┬───────────┐
    │           │           │           │
    ▼           ▼           ▼           ▼
┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐
│ XML  │   │Search│   │Scan  │   │Image │
│ Doc  │   │ PDF  │   │ PDF  │   │/JPG  │
└──┬───┘   └──┬───┘   └──┬───┘   └──┬───┘
   │          │          │          │
   └──────────┴────┬─────┴──────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ ЭТАП 2: SEGMENTATION                                            │
│ (LayoutAnalyzer - LayoutLMv3)                                   │
│                                                                 │
│ Input:  PDF/Image pages                                        │
│ Output: Document blocks with types and bounding boxes          │
│                                                                 │
│ Blocks: [Header, Preamble, Terms, Payment_Table, Signatures]   │
└───────────────┬─────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│ ЭТАП 3: CASCADING EXTRACTION                                    │
│ (EntityExtractor - 3 levels)                                    │
└───────────────┬─────────────────────────────────────────────────┘
                │
    ┌───────────┼───────────┬───────────┐
    │           │           │           │
    ▼           ▼           ▼           ▼
┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐
│Level1│   │Level2│   │Level3│   │ OCR  │
│Regex │   │Llama3│   │GPT-4o│   │Paddle│
│SpaCy │   │ 8B   │   │Claude│   │Tess. │
└──┬───┘   └──┬───┘   └──┬───┘   └──┬───┘
   │          │          │          │
   │ INN,     │ Tables,  │Liability │ Text │
   │ Dates,   │ Payment  │ Rules,   │ from │
   │ Amounts  │ Terms    │ Complex  │Scans │
   │          │          │ Clauses  │      │
   └──────────┴────┬─────┴──────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ ЭТАП 4: NORMALIZATION & VALIDATION                              │
│ (IDPProcessor)                                                  │
│                                                                 │
│ 1. Merge results from all levels                               │
│ 2. Resolve conflicts (prefer Level 3 > Level 2 > Level 1)      │
│ 3. Validate with Pydantic models                               │
│ 4. Create Intermediate JSON                                    │
└───────────────┬─────────────────────────────────────────────────┘
                │
                ▼
        Intermediate JSON
        {
          "doc_number": "123/2024",
          "parties": [...],
          "items": [...],
          "payment_schedule": [...],
          "rules": [...]
        }
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│ ЭТАП 5: STORAGE (Hybrid Star Schema)                           │
│ (SchemaMapper)                                                  │
│                                                                 │
│ 1. Standard fields → contracts_core columns                    │
│ 2. Dynamic fields → contracts_core.attributes (JSONB)          │
│ 3. Parties → contract_parties table                            │
│ 4. Items → contract_items table                                │
│ 5. Payments → payment_schedule table                           │
│ 6. Rules → contract_rules table                                │
│ 7. Full JSON → contracts_core.raw_data (audit)                 │
└───────────────┬─────────────────────────────────────────────────┘
                │
                ▼
        ✅ CONTRACT STORED
        Ready for querying & analysis
```

### 📝 Детальная логика пайплайна

#### Этап 1: Ingestion & Routing
**Файл:** `src/services/idp_orchestrator.py`

```python
class IDPOrchestrator:
    """
    Координирует весь процесс IDP
    """
    def __init__(self, db_session, llm_gateway, file_storage):
        self.db = db_session
        self.llm = llm_gateway
        self.storage = file_storage

        # Компоненты пайплайна
        self.classifier = DocumentClassifier()
        self.layout_analyzer = LayoutAnalyzer()
        self.ocr_service = EnhancedOCRService()
        self.entity_extractor = MultiLevelEntityExtractor(llm_gateway)
        self.schema_mapper = SchemaMapper(db_session)

    async def process_document(
        self,
        contract_id: str,
        file_data: bytes,
        filename: str
    ) -> ProcessingResult:
        """
        Главный метод обработки документа
        """
        logger.info(f"Starting IDP processing for contract {contract_id}")

        # 1. Сохраняем оригинал
        file_path = self.storage.store_original(
            contract_id, file_data, Path(filename).suffix
        )

        # 2. Классифицируем тип документа
        doc_type = self.classifier.classify(file_path)
        self._log_stage(contract_id, 'classification', doc_type)

        # 3. Выбираем пайплайн обработки
        if doc_type.format == 'xml':
            result = await self._process_xml(contract_id, file_path)
        elif doc_type.format == 'pdf' and doc_type.is_searchable:
            result = await self._process_searchable_pdf(contract_id, file_path)
        elif doc_type.format in ['pdf', 'jpg', 'png']:
            result = await self._process_scanned_document(contract_id, file_path)
        else:
            raise UnsupportedFormatError(f"Format {doc_type.format} not supported")

        # 4. Сохраняем в БД
        await self.schema_mapper.save_to_database(contract_id, result)

        logger.info(f"IDP processing completed for contract {contract_id}")
        return result

    async def _process_xml(self, contract_id: str, file_path: str) -> IntermediateJSON:
        """
        Детерминированный парсинг XML (быстро, дешево)
        """
        from src.services.document_parser import DocumentParser

        parser = DocumentParser()
        xml_data = parser.parse(file_path)

        # Преобразуем XML → Intermediate JSON
        intermediate = self._xml_to_intermediate(xml_data)

        self._log_stage(contract_id, 'xml_parsing', {
            'success': True,
            'extracted_fields': len(intermediate.keys())
        })

        return intermediate

    async def _process_searchable_pdf(self, contract_id: str, file_path: str) -> IntermediateJSON:
        """
        PDF с текстовым слоем (средняя сложность)
        OCR не нужен, но нужна layout analysis
        """
        # 1. Layout segmentation
        pages = convert_pdf_to_images(file_path)
        blocks = []
        for page_num, page_img in enumerate(pages):
            page_blocks = self.layout_analyzer.segment_document(page_img)
            blocks.extend(page_blocks)

        self._log_stage(contract_id, 'layout_analysis', {
            'pages': len(pages),
            'blocks': len(blocks)
        })

        # 2. Cascading extraction
        intermediate = await self.entity_extractor.extract_all(blocks)

        return intermediate

    async def _process_scanned_document(self, contract_id: str, file_path: str) -> IntermediateJSON:
        """
        Скан или фото (максимальная сложность)
        Нужны OCR + layout analysis + LLM
        """
        pages = convert_pdf_to_images(file_path)

        # 1. OCR каждой страницы
        ocr_results = []
        for page_num, page_img in enumerate(pages):
            ocr_result = self.ocr_service.extract_text(
                page_img,
                prefer_structure=True  # PaddleOCR
            )
            ocr_results.append(ocr_result)

        self._log_stage(contract_id, 'ocr', {
            'pages': len(pages),
            'avg_confidence': sum(r.confidence for r in ocr_results) / len(ocr_results)
        })

        # 2. Layout segmentation
        blocks = []
        for page_num, page_img in enumerate(pages):
            page_blocks = self.layout_analyzer.segment_document(page_img)
            # Обогащаем блоки текстом из OCR
            for block in page_blocks:
                block.text = self._extract_text_from_ocr(
                    ocr_results[page_num], block.bbox
                )
            blocks.extend(page_blocks)

        self._log_stage(contract_id, 'layout_analysis', {
            'pages': len(pages),
            'blocks': len(blocks)
        })

        # 3. Cascading extraction
        intermediate = await self.entity_extractor.extract_all(blocks)

        return intermediate

    def _log_stage(self, contract_id: str, stage: str, output_data: dict):
        """Логирование этапа обработки"""
        log_entry = IDPExtractionLog(
            contract_id=contract_id,
            stage=stage,
            status='success',
            output_data=output_data,
            created_at=datetime.now()
        )
        self.db.add(log_entry)
        self.db.commit()
```

#### Этап 2: Segmentation (Layout Analysis)
**Файл:** `src/services/layout_analyzer.py`

```python
class LayoutAnalyzer:
    """
    Анализирует визуальную структуру документа с помощью LayoutLMv3
    """
    def __init__(self):
        self.model_path = "models/layoutlmv3-contract-segmentation.onnx"
        self.session = onnxruntime.InferenceSession(self.model_path)

        # Классы блоков
        self.block_types = [
            'header', 'preamble', 'subject',
            'terms', 'payment_table', 'liability',
            'signatures', 'footer', 'other'
        ]

    def segment_document(self, image_path: str) -> List[DocumentBlock]:
        """
        Разбивает страницу документа на блоки с типизацией

        Returns:
            List[DocumentBlock]: Список блоков с типами и координатами
        """
        # 1. Загружаем изображение
        image = Image.open(image_path).convert('RGB')

        # 2. Препроцессинг для LayoutLM
        inputs = self._preprocess_image(image)

        # 3. Inference через ONNX (CPU, ~3-5 сек)
        onnx_inputs = {self.session.get_inputs()[0].name: inputs}
        outputs = self.session.run(None, onnx_inputs)

        # 4. Постпроцессинг: извлекаем bounding boxes и типы
        blocks = self._postprocess_outputs(outputs, image.size)

        logger.info(f"Segmented page into {len(blocks)} blocks")
        return blocks

    def _preprocess_image(self, image: Image) -> np.ndarray:
        """Подготовка изображения для LayoutLM"""
        # Resize to 224x224 (LayoutLMv3 input size)
        image = image.resize((224, 224))
        image_array = np.array(image).astype(np.float32) / 255.0
        image_array = np.transpose(image_array, (2, 0, 1))  # HWC -> CHW
        image_array = np.expand_dims(image_array, axis=0)  # Add batch dim
        return image_array

    def _postprocess_outputs(self, outputs, image_size) -> List[DocumentBlock]:
        """Извлекает блоки из предсказаний модели"""
        predictions = outputs[0]  # Shape: (1, num_boxes, 4 + num_classes)

        blocks = []
        for pred in predictions[0]:
            # Извлекаем bbox и класс
            bbox = pred[:4]  # [x1, y1, x2, y2] normalized
            class_scores = pred[4:]
            class_id = np.argmax(class_scores)
            confidence = class_scores[class_id]

            if confidence > 0.5:  # Threshold
                # Денормализуем координаты
                x1, y1, x2, y2 = bbox
                width, height = image_size
                bbox_abs = (
                    int(x1 * width), int(y1 * height),
                    int(x2 * width), int(y2 * height)
                )

                block = DocumentBlock(
                    type=self.block_types[class_id],
                    bbox=bbox_abs,
                    confidence=float(confidence),
                    text=""  # Будет заполнен после OCR/extraction
                )
                blocks.append(block)

        return blocks
```

#### Этап 3: Cascading Extraction
**Файл:** `src/services/entity_extractor.py`

```python
class MultiLevelEntityExtractor:
    """
    Каскадное извлечение сущностей с 3 уровнями
    """
    def __init__(self, llm_gateway: LLMGateway):
        self.level1 = Level1EntityExtractor()  # Regex + SpaCy
        self.level2 = Level2EntityExtractor(llm_gateway)  # Llama-3-8B
        self.level3 = Level3EntityExtractor(llm_gateway)  # GPT-4o
        self.router = LLMRouter()

    async def extract_all(self, blocks: List[DocumentBlock]) -> IntermediateJSON:
        """
        Извлекает все данные из блоков документа
        """
        intermediate = IntermediateJSON()

        for block in blocks:
            logger.info(f"Processing block type: {block.type}")

            if block.type == 'header':
                # Level 1: Regex для номера и даты договора
                intermediate.update(self.level1.extract_header(block.text))

            elif block.type == 'preamble':
                # Level 1: Regex + SpaCy для сторон
                parties = self.level1.extract_parties(block.text)
                intermediate['parties'] = parties

            elif block.type == 'payment_table':
                # Level 2: Llama-3 для таблиц
                items = await self.level2.extract_tables(block)
                intermediate['items'] = items

            elif block.type == 'terms':
                # Level 2: Llama-3 для условий оплаты
                payment_schedule = await self.level2.extract_payment_terms(block)
                intermediate['payment_schedule'] = payment_schedule

            elif block.type == 'liability':
                # Level 3: GPT-4o для правил ответственности (сложно!)
                rules = await self.level3.extract_liability_rules(block)
                intermediate['rules'] = rules

            elif block.type == 'signatures':
                # Level 1: Детектор подписей (computer vision)
                signatures = self._detect_signatures(block)
                intermediate['signatures'] = signatures

        # Валидация и заполнение пропусков
        intermediate = self._validate_and_fill_gaps(intermediate)

        return intermediate

    def _validate_and_fill_gaps(self, data: IntermediateJSON) -> IntermediateJSON:
        """
        Валидация извлеченных данных и заполнение пропусков
        """
        from src.schemas.contract_schemas import ContractCoreSchema

        try:
            # Pydantic валидация
            validated = ContractCoreSchema(**data)
            return validated.dict()
        except ValidationError as e:
            # Логируем ошибки валидации
            logger.warning(f"Validation errors: {e}")

            # Помечаем проблемные поля для ручной проверки
            for error in e.errors():
                field = error['loc'][0]
                self._create_quality_issue(
                    field=field,
                    issue_type='validation_error',
                    severity='warning',
                    description=error['msg']
                )

            # Возвращаем данные как есть (с пропусками)
            return data
```

#### Этап 4: Normalization & Storage
**Файл:** `src/services/schema_mapper.py`

```python
class SchemaMapper:
    """
    Маппинг Intermediate JSON → Hybrid Star Schema
    """
    def __init__(self, db_session):
        self.db = db_session

    async def save_to_database(
        self,
        contract_id: str,
        intermediate: IntermediateJSON
    ) -> str:
        """
        Сохраняет договор в БД согласно Hybrid Star Schema
        """
        logger.info(f"Mapping contract {contract_id} to database schema")

        # 1. Центральная таблица contracts_core
        core_record = self._map_to_core(contract_id, intermediate)
        self.db.add(core_record)
        self.db.flush()  # Получаем ID

        # 2. Стороны договора
        for party_data in intermediate.get('parties', []):
            party = self._map_to_party(core_record.id, party_data)
            self.db.add(party)

        # 3. Спецификация
        for item_data in intermediate.get('items', []):
            item = self._map_to_item(core_record.id, item_data)
            self.db.add(item)

        # 4. График платежей
        for payment_data in intermediate.get('payment_schedule', []):
            payment = self._map_to_payment(core_record.id, payment_data)
            self.db.add(payment)

        # 5. Правила
        for rule_data in intermediate.get('rules', []):
            rule = self._map_to_rule(core_record.id, rule_data)
            self.db.add(rule)

        self.db.commit()

        logger.info(f"Contract {contract_id} saved to database: {core_record.id}")
        return core_record.id

    def _map_to_core(self, contract_id: str, data: dict) -> ContractCore:
        """
        Маппинг в contracts_core
        """
        # Стандартные поля
        standard_fields = {
            'doc_number': data.get('doc_number'),
            'signed_date': data.get('signed_date'),
            'status': 'active',
            'total_amount': data.get('total_amount'),
            'currency': data.get('currency', 'RUB'),
            'source_file_id': contract_id,
            'processed_by': 'idp_pipeline'
        }

        # Гибкие атрибуты (все остальное)
        known_keys = {'doc_number', 'signed_date', 'total_amount', 'currency',
                      'parties', 'items', 'payment_schedule', 'rules'}
        attributes = {
            k: v for k, v in data.items()
            if k not in known_keys and v is not None
        }

        # Сырые данные (для аудита)
        raw_data = data.copy()

        return ContractCore(
            **standard_fields,
            attributes=attributes,
            raw_data=raw_data
        )

    def _map_to_party(self, core_id: str, party_data: dict) -> ContractParty:
        """Маппинг стороны договора"""
        return ContractParty(
            contract_id=core_id,
            role=party_data.get('role', 'unknown'),
            name=party_data['name'],
            tax_id=party_data.get('inn'),
            registration_number=party_data.get('ogrn'),
            legal_address=party_data.get('address'),
            bank_details=party_data.get('bank_details', {})
        )

    def _map_to_item(self, core_id: str, item_data: dict) -> ContractItem:
        """Маппинг позиции спецификации"""
        return ContractItem(
            contract_id=core_id,
            line_number=item_data.get('line_number', 1),
            name=item_data['name'],
            description=item_data.get('description'),
            quantity=item_data['quantity'],
            unit=item_data.get('unit', 'шт'),
            price_unit=item_data['price'],
            total_line=item_data['total'],
            sku_code=item_data.get('sku'),
            attributes=item_data.get('attributes', {})
        )

    def _map_to_payment(self, core_id: str, payment_data: dict) -> PaymentSchedule:
        """Маппинг условий оплаты"""
        return PaymentSchedule(
            contract_id=core_id,
            payment_type=payment_data.get('type', 'postpayment'),
            amount=payment_data['amount'],
            percentage=payment_data.get('percentage'),
            due_date=payment_data.get('due_date'),
            due_condition=payment_data.get('condition'),
            days_offset=payment_data.get('days_offset'),
            trigger_event=payment_data.get('trigger'),
            status='pending'
        )

    def _map_to_rule(self, core_id: str, rule_data: dict) -> ContractRule:
        """Маппинг правил ответственности"""
        return ContractRule(
            contract_id=core_id,
            section_type=rule_data.get('rule_type', 'liability'),
            rule_name=rule_data['title'],
            trigger_condition=rule_data.get('trigger_condition'),
            formula=rule_data['formula'],
            original_text=rule_data['original_text'],
            clause_location=rule_data.get('xpath'),
            extracted_by='llm_' + rule_data.get('model', 'gpt4o'),
            confidence_score=rule_data.get('confidence', 0.9),
            is_active=True
        )
```

---

## 7. Интеграция с существующей системой

### 🔌 Точки интеграции

#### 7.1 Расширение API (FastAPI routes)
**Файл:** `src/api/contracts/routes.py` (расширение существующего)

```python
# ========== НОВЫЕ ЭНДПОИНТЫ IDP ==========

@router.post("/upload-idp", response_model=ContractUploadResponse)
async def upload_contract_idp(
    file: UploadFile = File(...),
    enable_idp: bool = Form(True),  # Включить IDP обработку
    idp_mode: str = Form("auto"),  # auto, fast, deep
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Загрузка договора с IDP обработкой

    idp_mode:
    - auto: Автоматический выбор пайплайна
    - fast: Быстрая обработка (без LLM Level 3)
    - deep: Глубокая обработка (все уровни LLM)
    """
    file_data = await file.read()

    # Сохраняем файл
    file_path, safe_filename, file_size = save_uploaded_file_securely(
        file_data, file.filename, "data/contracts"
    )

    # Создаем запись в старой таблице contracts
    contract = Contract(
        file_name=safe_filename,
        file_path=file_path,
        document_type='contract',
        status='processing',
        assigned_to=current_user.id
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)

    if enable_idp:
        # Запускаем IDP в фоне
        background_tasks.add_task(
            process_contract_idp_background,
            contract_id=contract.id,
            file_data=file_data,
            filename=safe_filename,
            idp_mode=idp_mode,
            db=db
        )

        return ContractUploadResponse(
            contract_id=contract.id,
            file_name=safe_filename,
            file_size=file_size,
            status='processing_idp',
            message='IDP processing started. Check /api/v1/idp/status/{contract_id}'
        )
    else:
        # Старый пайплайн (DocumentParser)
        background_tasks.add_task(
            analyze_contract_background,  # Существующая функция
            contract_id=contract.id,
            user_id=current_user.id,
            check_counterparty=True,
            counterparty_tin=None,
            db=db
        )

        return ContractUploadResponse(
            contract_id=contract.id,
            file_name=safe_filename,
            file_size=file_size,
            status='processing_legacy',
            message='Legacy processing started'
        )


@router.get("/idp/status/{contract_id}")
async def get_idp_status(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Проверка статуса IDP обработки
    """
    # Получаем записи из idp_extraction_log
    logs = db.query(IDPExtractionLog).filter(
        IDPExtractionLog.contract_id == contract_id
    ).order_by(IDPExtractionLog.created_at.desc()).all()

    if not logs:
        raise HTTPException(404, "IDP processing not found")

    # Статус последнего этапа
    latest_log = logs[0]

    # Вычисляем общий прогресс
    stages = ['classification', 'layout_analysis', 'entity_extraction',
              'validation', 'storage']
    completed_stages = {log.stage for log in logs if log.status == 'success'}
    progress = len(completed_stages) / len(stages) * 100

    return {
        'contract_id': contract_id,
        'status': latest_log.status,
        'current_stage': latest_log.stage,
        'progress': progress,
        'stages': [
            {
                'stage': log.stage,
                'status': log.status,
                'duration_ms': log.duration_ms,
                'completed_at': log.created_at.isoformat()
            }
            for log in logs
        ],
        'total_cost_usd': sum(log.cost_usd or 0 for log in logs),
        'total_tokens': sum(log.tokens_used or 0 for log in logs)
    }


@router.get("/idp/result/{contract_id}")
async def get_idp_result(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получение структурированных данных из IDP
    """
    # Получаем запись из contracts_core
    core = db.query(ContractCore).filter(
        ContractCore.source_file_id == contract_id
    ).first()

    if not core:
        raise HTTPException(404, "IDP result not found")

    # Загружаем связанные данные
    parties = db.query(ContractParty).filter(
        ContractParty.contract_id == core.id
    ).all()

    items = db.query(ContractItem).filter(
        ContractItem.contract_id == core.id
    ).all()

    payments = db.query(PaymentSchedule).filter(
        PaymentSchedule.contract_id == core.id
    ).all()

    rules = db.query(ContractRule).filter(
        ContractRule.contract_id == core.id
    ).all()

    return {
        'contract': {
            'id': core.id,
            'doc_number': core.doc_number,
            'signed_date': core.signed_date.isoformat() if core.signed_date else None,
            'status': core.status,
            'total_amount': float(core.total_amount) if core.total_amount else None,
            'currency': core.currency,
            'attributes': core.attributes  # Динамические поля
        },
        'parties': [
            {
                'role': p.role,
                'name': p.name,
                'tax_id': p.tax_id,
                'legal_address': p.legal_address
            }
            for p in parties
        ],
        'items': [
            {
                'line_number': i.line_number,
                'name': i.name,
                'quantity': float(i.quantity),
                'unit': i.unit,
                'price_unit': float(i.price_unit),
                'total': float(i.total_line)
            }
            for i in items
        ],
        'payment_schedule': [
            {
                'type': ps.payment_type,
                'amount': float(ps.amount),
                'due_date': ps.due_date.isoformat() if ps.due_date else None,
                'condition': ps.due_condition,
                'status': ps.status
            }
            for ps in payments
        ],
        'rules': [
            {
                'type': r.section_type,
                'name': r.rule_name,
                'trigger': r.trigger_condition,
                'formula': r.formula,
                'original_text': r.original_text,
                'confidence': float(r.confidence_score) if r.confidence_score else None
            }
            for r in rules
        ]
    }
```

#### 7.2 Интеграция с ContractAnalyzerAgent
**Файл:** `src/agents/contract_analyzer_agent.py` (модификация)

```python
class ContractAnalyzerAgent(BaseAgent):
    """
    Расширяем агент для работы с IDP данными
    """
    def execute(self, state: Dict[str, Any]) -> AgentResult:
        contract_id = state.get('contract_id')

        # НОВАЯ ЛОГИКА: Проверяем, есть ли IDP данные
        core = self.db.query(ContractCore).filter(
            ContractCore.source_file_id == contract_id
        ).first()

        if core:
            # 🆕 Используем структурированные данные из IDP
            logger.info(f"Contract {contract_id} has IDP data, using structured analysis")
            return self._analyze_with_idp_data(contract_id, core)
        else:
            # Старая логика: парсим XML
            logger.info(f"Contract {contract_id} has no IDP data, using legacy XML analysis")
            return self._analyze_legacy(contract_id, state)

    def _analyze_with_idp_data(self, contract_id: str, core: ContractCore) -> AgentResult:
        """
        Анализ договора на основе структурированных IDP данных
        """
        # Загружаем все связанные данные
        parties = self.db.query(ContractParty).filter(...).all()
        items = self.db.query(ContractItem).filter(...).all()
        rules = self.db.query(ContractRule).filter(...).all()

        # Анализ рисков на основе ПРАВИЛ (contract_rules)
        risks = []
        for rule in rules:
            if rule.section_type == 'penalty':
                # Проверяем формулу штрафа
                penalty_risk = self._analyze_penalty_rule(rule)
                if penalty_risk:
                    risks.append(penalty_risk)

            elif rule.section_type == 'termination':
                # Проверяем условия расторжения
                termination_risk = self._analyze_termination_rule(rule)
                if termination_risk:
                    risks.append(termination_risk)

        # Анализ финансовых рисков на основе ITEMS и PAYMENTS
        financial_risks = self._analyze_financial_structure(items, payments)
        risks.extend(financial_risks)

        # Генерируем рекомендации
        recommendations = self.recommendation_generator.generate_recommendations(
            risks, rag_context={}
        )

        # Сохраняем результаты
        analysis = AnalysisResult(
            contract_id=contract_id,
            risks=json.dumps([r.dict() for r in risks]),
            recommendations=json.dumps([rec.dict() for rec in recommendations])
        )
        self.db.add(analysis)
        self.db.commit()

        return AgentResult(
            success=True,
            data={
                'analysis_id': analysis.id,
                'risks': risks,
                'recommendations': recommendations,
                'structured_data_used': True  # Флаг IDP
            }
        )

    def _analyze_penalty_rule(self, rule: ContractRule) -> Optional[ContractRisk]:
        """
        Анализ правила штрафа из contract_rules
        """
        formula = rule.formula

        # Проверяем разумность формулы
        if formula.get('rate', 0) > 0.01:  # >1% в день
            return ContractRisk(
                risk_type='financial',
                severity='high',
                title='Excessive penalty rate',
                description=f"Penalty rate {formula['rate']*100}% per {formula['period']} is very high",
                original_text=rule.original_text,
                clause_location=rule.clause_location
            )

        return None
```

#### 7.3 Backwards Compatibility (Обратная совместимость)

**Стратегия:**
1. **Двойная запись:** При IDP обработке сохраняем данные И в старые таблицы (`contracts`), И в новые (`contracts_core`)
2. **Graceful fallback:** Если IDP не сработал, используем старый DocumentParser
3. **Миграция постепенная:** Старые договоры остаются в `contracts`, новые → `contracts_core`

```python
# src/services/backward_compatibility.py
class BackwardCompatibilityLayer:
    """
    Обеспечивает совместимость между старой и новой системами
    """
    def __init__(self, db_session):
        self.db = db_session

    def sync_old_to_new(self, contract_id: str):
        """
        Синхронизирует запись из contracts → contracts_core
        """
        old_contract = self.db.query(Contract).filter(Contract.id == contract_id).first()

        if not old_contract:
            return

        # Проверяем, есть ли уже в contracts_core
        core = self.db.query(ContractCore).filter(
            ContractCore.source_file_id == contract_id
        ).first()

        if core:
            return  # Уже синхронизировано

        # Парсим meta_info (XML)
        if old_contract.meta_info:
            try:
                xml_data = json.loads(old_contract.meta_info).get('xml', '')
                intermediate = self._xml_to_intermediate(xml_data)

                # Сохраняем в новую схему
                mapper = SchemaMapper(self.db)
                mapper.save_to_database(contract_id, intermediate)

                logger.info(f"Synced old contract {contract_id} to new schema")
            except Exception as e:
                logger.error(f"Failed to sync contract {contract_id}: {e}")
```

---

## 8. API контракт

### 📡 REST API Endpoints

```yaml
# ==================== IDP ENDPOINTS ====================

# Загрузка договора с IDP
POST /api/v1/contracts/upload-idp
  Body (multipart/form-data):
    - file: binary
    - enable_idp: boolean (default: true)
    - idp_mode: "auto" | "fast" | "deep"
  Response:
    {
      "contract_id": "uuid",
      "status": "processing_idp",
      "message": "IDP processing started"
    }

# Статус IDP обработки
GET /api/v1/contracts/idp/status/{contract_id}
  Response:
    {
      "contract_id": "uuid",
      "status": "success",
      "current_stage": "storage",
      "progress": 100,
      "stages": [
        {
          "stage": "classification",
          "status": "success",
          "duration_ms": 120,
          "completed_at": "2024-01-08T10:00:00"
        },
        ...
      ],
      "total_cost_usd": 0.25,
      "total_tokens": 5000
    }

# Получение структурированных данных
GET /api/v1/contracts/idp/result/{contract_id}
  Response:
    {
      "contract": {
        "id": "uuid",
        "doc_number": "123/2024",
        "signed_date": "2024-01-01",
        "total_amount": 1000000,
        "currency": "RUB",
        "attributes": {
          "delivery_type": "air",
          "project_manager": "Ivanov"
        }
      },
      "parties": [...],
      "items": [...],
      "payment_schedule": [...],
      "rules": [...]
    }

# Поиск похожих договоров (semantic search)
POST /api/v1/contracts/idp/search-similar
  Body:
    {
      "query": "договор поставки с предоплатой",
      "limit": 10,
      "filters": {
        "currency": "RUB",
        "min_amount": 100000
      }
    }
  Response:
    {
      "results": [
        {
          "contract_id": "uuid",
          "doc_number": "456/2024",
          "similarity": 0.92,
          "summary": "..."
        },
        ...
      ]
    }

# SQL-like запросы к договорам
POST /api/v1/contracts/idp/query
  Body:
    {
      "query": {
        "total_amount": {"$gt": 1000000},
        "currency": "RUB",
        "attributes.delivery_type": "air"
      },
      "sort": {"signed_date": -1},
      "limit": 20
    }
  Response:
    {
      "results": [...],
      "total": 150
    }

# Проблемы качества IDP
GET /api/v1/contracts/idp/quality-issues/{contract_id}
  Response:
    {
      "issues": [
        {
          "type": "missing_field",
          "severity": "warning",
          "field": "payment_schedule",
          "description": "Payment schedule not found in document",
          "suggested_action": "Manual review required"
        },
        ...
      ]
    }

# Экспорт в ERP (1C, SAP)
POST /api/v1/contracts/idp/export-to-erp
  Body:
    {
      "contract_ids": ["uuid1", "uuid2"],
      "erp_system": "1c",
      "mapping_profile": "default"
    }
  Response:
    {
      "exported": 2,
      "failed": 0,
      "export_log_id": "uuid"
    }
```

### 🔌 WebSocket для Real-time прогресса

```javascript
// Frontend: подключение к WebSocket
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/idp/{contract_id}');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  console.log(`Stage: ${data.stage}, Progress: ${data.progress}%`);

  if (data.stage === 'completed') {
    console.log('IDP processing completed!');
    // Загрузить результаты
    fetchIDPResult(contract_id);
  }
};

// Backend: WebSocket endpoint (FastAPI)
@app.websocket("/api/v1/ws/idp/{contract_id}")
async def idp_progress_websocket(websocket: WebSocket, contract_id: str):
    await websocket.accept()

    try:
        while True:
            # Проверяем статус IDP обработки
            status = await get_idp_status(contract_id)

            await websocket.send_json({
                'stage': status['current_stage'],
                'progress': status['progress'],
                'status': status['status']
            })

            if status['status'] in ['success', 'failed']:
                break

            await asyncio.sleep(2)  # Обновление каждые 2 секунды

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for contract {contract_id}")
```

---

## 9. Стратегия оптимизации затрат

### 💰 Принципы экономии для MVP

#### 9.1 Не покупать GPU-серверы
**Решение:** Используем CPU-inference + API-based LLM

| Компонент | Deployment | Стоимость |
|-----------|-----------|-----------|
| LayoutLMv3 | ONNX Runtime (CPU) | $0 (локально) |
| PaddleOCR | CPU mode | $0 (локально) |
| Llama-3-8B | OpenRouter/DeepInfra API | $0.10/1M tokens |
| GPT-4o | OpenAI API | $2.50/1M input |

**Экономия:** $5000-10000 на GPU-сервере → $0 капитальных затрат

#### 9.2 Каскадный подход (Cascading Pipeline)

```
┌─────────────────────────────────────────────────────────────────┐
│ Level 1: Regex + SpaCy (CPU, бесплатно)                        │
│ Извлекает: ИНН, даты, суммы, имена                             │
│ Покрытие: ~40% полей                                            │
│ Стоимость: $0                                                   │
└────────────────────────┬────────────────────────────────────────┘
                         │ Если недостаточно ↓
┌─────────────────────────────────────────────────────────────────┐
│ Level 2: Llama-3-8B (API, дешево)                              │
│ Извлекает: таблицы, условия оплаты                             │
│ Покрытие: +40% полей                                            │
│ Стоимость: $0.05-0.10 за договор                                │
└────────────────────────┬────────────────────────────────────────┘
                         │ Если сложная секция ↓
┌─────────────────────────────────────────────────────────────────┐
│ Level 3: GPT-4o (API, дорого)                                  │
│ Извлекает: штрафы, форс-мажор, сложные правила                 │
│ Покрытие: +20% полей                                            │
│ Стоимость: $0.20-0.50 за договор                                │
└─────────────────────────────────────────────────────────────────┘
```

**Итого:** $0.05-0.50 за договор вместо $5-10 (если использовать GPT-4o для всего)

#### 9.3 LLM Caching (уже есть в системе!)

**Существующий механизм:** `LLMCache` таблица (src/models/database.py)

**Улучшения для IDP:**
```python
# src/services/llm_gateway.py (расширение)
class LLMGateway:
    def call_with_smart_cache(self, prompt: str, **kwargs) -> Any:
        """
        Умное кэширование с учетом похожести промптов
        """
        # 1. Проверяем точное совпадение (SHA256)
        cache_hit = self._check_cache_exact(prompt)
        if cache_hit:
            logger.info("Cache hit (exact)")
            return cache_hit['response']

        # 2. Проверяем семантическую похожесть (cosine similarity)
        similar_cache = self._check_cache_semantic(prompt, threshold=0.95)
        if similar_cache:
            logger.info(f"Cache hit (semantic, similarity={similar_cache['similarity']})")
            return similar_cache['response']

        # 3. Вызываем LLM
        response = self._call_llm(prompt, **kwargs)

        # 4. Сохраняем в кэш
        self._save_to_cache(prompt, response, **kwargs)

        return response
```

**Экономия:** 50-70% запросов из кэша для типовых договоров

#### 9.4 Batch Processing (асинхронная очередь)

**Вместо Real-time → Background processing:**

```python
# src/services/batch_processor.py
from celery import Celery

celery_app = Celery('idp_tasks', broker='redis://localhost:6379/0')

@celery_app.task
def process_contract_batch(contract_ids: List[str]):
    """
    Обрабатывает батч договоров за один раз
    Экономит на повторяющихся операциях (загрузка модели, подключение к API)
    """
    # Загружаем модели один раз для всего батча
    layout_analyzer = LayoutAnalyzer()
    ocr_service = EnhancedOCRService()

    results = []
    for contract_id in contract_ids:
        result = process_single_contract(
            contract_id,
            layout_analyzer,
            ocr_service
        )
        results.append(result)

    return results
```

**Экономия:** 20-30% на overhead (загрузка моделей, соединения)

#### 9.5 Стоимостной анализ (Cost Breakdown)

**Пример: Обработка 1000 договоров/месяц**

| Компонент | Стоимость за договор | Итого/месяц |
|-----------|---------------------|-------------|
| **Layout Analysis (LayoutLMv3 CPU)** | $0 | $0 |
| **OCR (PaddleOCR CPU)** | $0 | $0 |
| **Level 1 (Regex + SpaCy)** | $0 | $0 |
| **Level 2 (Llama-3-8B, 60% договоров)** | $0.08 | $48 |
| **Level 3 (GPT-4o, 20% договоров)** | $0.35 | $70 |
| **Embeddings (OpenAI ada-002)** | $0.001 | $1 |
| **Storage (PostgreSQL + S3)** | $0.01 | $10 |
| **Redis (cache)** | - | $10 |
| **Сервер (CPU, 4 cores)** | - | $50 |
| **ИТОГО** | **$0.10-0.40** | **$189/месяц** |

**Сравнение с альтернативами:**
- Azure Form Recognizer: $1.50 за договор → $1500/месяц
- AWS Textract: $1.20 за договор → $1200/месяц
- Ручная обработка: $10 за договор → $10000/месяц

**Экономия: 6x-50x**

---

## 10. План поэтапного внедрения

### 🚀 Roadmap (4 фазы)

#### **Phase 1: Foundation (Недели 1-2)**
**Цель:** Базовая инфраструктура без AI

**Задачи:**
1. ✅ Создать новые таблицы БД (contracts_core, contract_parties, etc.)
2. ✅ Миграция Alembic
3. ✅ Написать SchemaMapper (без AI, только детерминированный маппинг)
4. ✅ Расширить FileStorage для IDP
5. ✅ Создать базовый IDPOrchestrator (без ML)
6. ✅ Unit-тесты для БД моделей

**Результат:** База данных готова, можно сохранять договоры в новую схему вручную

#### **Phase 2: Level 1 Extraction (Недели 3-4)**
**Цель:** Извлечение базовых полей без LLM

**Задачи:**
1. ✅ Реализовать Level1EntityExtractor (Regex + SpaCy)
   - ИНН с валидацией контрольной суммы
   - Даты (ДД.ММ.ГГГГ, ДД месяц ГГГГ)
   - Суммы с валютой
   - NER для организаций и людей
2. ✅ Интеграция с DocumentParser (XML → Intermediate JSON)
3. ✅ End-to-end тест: XML договор → contracts_core
4. ✅ API endpoint: POST /api/v1/contracts/upload-idp (без AI)

**Результат:** Система может обрабатывать простые XML договоры без AI

#### **Phase 3: Layout Analysis + OCR (Недели 5-6)**
**Цель:** Обработка PDF и сканов

**Задачи:**
1. ✅ Установить и настроить PaddleOCR
2. ✅ Обучить или fine-tune LayoutLMv3 на русских договорах (опционально)
3. ✅ Реализовать LayoutAnalyzer с ONNX Runtime
4. ✅ Интеграция OCR → Layout → Level1
5. ✅ End-to-end тест: Скан PDF → contracts_core
6. ✅ Логирование: idp_extraction_log, idp_quality_issues

**Результат:** Система может обрабатывать PDF и сканы (без LLM для сложных полей)

#### **Phase 4: Cascading LLM (Недели 7-8)**
**Цель:** Полный IDP с AI

**Задачи:**
1. ✅ Реализовать Level2EntityExtractor (Llama-3-8B)
   - Таблицы спецификаций
   - Условия оплаты
2. ✅ Реализовать Level3EntityExtractor (GPT-4o)
   - Правила ответственности
   - Форс-мажор
   - Условия расторжения
3. ✅ Реализовать LLMRouter (автоматический выбор модели)
4. ✅ Интеграция всех уровней в IDPOrchestrator
5. ✅ End-to-end тест: Сложный скан → contracts_core со всеми правилами
6. ✅ Интеграция с ContractAnalyzerAgent
7. ✅ WebSocket для прогресса
8. ✅ Monitoring dashboard (Streamlit)

**Результат:** Полнофункциональная IDP система с AI

### 📅 Дополнительные фазы (опционально)

#### **Phase 5: Optimization (Недели 9-10)**
1. Тюнинг производительности (индексы БД, query optimization)
2. Тестирование на большом объеме договоров (100+)
3. A/B тестирование: Legacy vs IDP точность
4. Semantic search (pgvector integration)
5. Мониторинг стоимости LLM и оптимизация

#### **Phase 6: Advanced Features (Недели 11-12)**
1. Automatic contract comparison (найти отличия между версиями)
2. Contract templates learning (ML для шаблонов)
3. Predictive analytics (вероятность спора, дефолта)
4. ERP integration (1C, SAP)
5. Multi-language support (английские договоры)

---

## 11. Метрики успеха

### 📊 KPI для оценки IDP системы

#### 11.1 Точность извлечения (Accuracy Metrics)

| Поле | Целевая точность | Критичность |
|------|------------------|-------------|
| **Номер договора** | 99% | Critical |
| **Дата подписания** | 98% | Critical |
| **Сумма договора** | 95% | Critical |
| **Стороны (имена)** | 95% | High |
| **ИНН** | 99% (с валидацией) | High |
| **Таблицы спецификаций** | 85% | Medium |
| **Условия оплаты** | 85% | High |
| **Правила штрафов** | 80% | Medium |

**Методика измерения:**
1. Собрать тестовый датасет: 100 договоров с ручной разметкой (ground truth)
2. Прогнать через IDP pipeline
3. Сравнить с ground truth: Precision, Recall, F1-score
4. Анализировать ошибки по категориям

#### 11.2 Производительность (Performance Metrics)

| Метрика | Целевое значение | Комментарий |
|---------|------------------|-------------|
| **Время обработки (XML)** | < 30 сек | Детерминированный парсинг |
| **Время обработки (PDF)** | < 2 мин | С layout analysis |
| **Время обработки (скан)** | < 5 мин | С OCR + full AI pipeline |
| **Throughput** | 20+ договоров/час | На 1 CPU worker |
| **Latency P95** | < 3 мин | 95 перцентиль |

#### 11.3 Стоимость (Cost Metrics)

| Метрика | Целевое значение |
|---------|------------------|
| **Средняя стоимость обработки** | < $0.50/договор |
| **LLM tokens (среднее)** | < 10K tokens/договор |
| **% кэш-хитов** | > 60% |
| **Level 3 usage** | < 30% договоров |

#### 11.4 Качество (Quality Metrics)

| Метрика | Целевое значение | Как измерять |
|---------|------------------|--------------|
| **% полностью извлеченных договоров** | > 70% | Все обязательные поля заполнены |
| **% с критическими ошибками** | < 5% | idp_quality_issues severity='critical' |
| **% требующих ручной проверки** | < 20% | requires_manual_review=True |
| **User satisfaction (юристы)** | > 4.0/5.0 | Survey после использования |

#### 11.5 Сравнение Legacy vs IDP

**A/B тест на 200 договорах:**

| Метрика | Legacy (DocumentParser) | IDP | Улучшение |
|---------|-------------------------|-----|-----------|
| Точность извлечения сумм | 65% | 92% | +27% |
| Точность извлечения дат | 70% | 95% | +25% |
| Извлечение правил штрафов | 0% (не умеет) | 75% | +75% |
| Время обработки | 5 мин (ручная) | 2 мин (авто) | 2.5x |
| Стоимость | $8 (человек) | $0.30 (AI) | 26x |

---

## 12. Риски и митигация

### ⚠️ Потенциальные риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| **Низкая точность OCR на плохих сканах** | High | High | 1. Использовать PaddleOCR (лучше Tesseract)<br>2. Fallback на Azure OCR для сложных случаев<br>3. Quality warning для пользователя |
| **Высокая стоимость LLM** | Medium | Medium | 1. Cascading pipeline (Level 1→2→3)<br>2. LLM caching<br>3. Router для выбора модели<br>4. Batch processing |
| **LayoutLM не работает на CPU** | Low | High | 1. ONNX quantization<br>2. Упростить модель<br>3. Использовать rule-based segmentation |
| **Сложность интеграции с legacy кодом** | Medium | Medium | 1. Backward compatibility layer<br>2. Постепенная миграция<br>3. Feature flag (enable_idp) |
| **Нехватка данных для обучения** | Medium | Low | 1. Использовать pre-trained модели<br>2. Zero-shot/few-shot prompting<br>3. Собирать feedback для fine-tuning |
| **Производительность БД (JSONB)** | Low | Medium | 1. GIN индексы<br>2. Партиционирование таблиц<br>3. Caching часто используемых запросов |

---

## 13. Следующие шаги (Action Items)

### ✅ Немедленные действия (эта неделя)

1. **Обсудить концепцию с командой**
   - Презентация на meeting
   - Обратная связь от разработчиков и юристов
   - Утверждение приоритетов

2. **Подготовка окружения**
   - Установить PostgreSQL 16+ (если еще SQLite)
   - Установить Redis (для Celery)
   - Установить библиотеки:
     ```bash
     pip install paddlepaddle paddleocr onnxruntime transformers
     ```

3. **Создать ветку разработки**
   ```bash
   git checkout -b feature/idp-integration
   ```

4. **Прототип БД**
   - Создать Alembic миграцию для новых таблиц
   - Протестировать на тестовых данных

### 📝 Решения, которые нужно принять

| Вопрос | Опции | Рекомендация |
|--------|-------|--------------|
| **Какой OCR использовать?** | Tesseract vs PaddleOCR vs Azure | PaddleOCR (better for tables) |
| **Где хостить LayoutLM?** | Local CPU vs Cloud GPU | Local CPU с ONNX (MVP) |
| **LLM provider для Level 2?** | OpenRouter vs DeepInfra vs Groq | OpenRouter (гибкость) |
| **База данных?** | SQLite vs PostgreSQL | PostgreSQL (для production) |
| **Message broker?** | Redis+Celery vs RabbitMQ | Redis+Celery (проще) |
| **Storage для файлов?** | Local FS vs MinIO vs S3 | Local FS (MVP) → MinIO |

### 🎯 Цель на 2 месяца

**К концу Phase 4 (8 недель):**
- ✅ Полностью работающая IDP система
- ✅ Обработка XML, PDF, сканов
- ✅ Cascading extraction (3 уровня)
- ✅ Hybrid Star Schema в production БД
- ✅ API endpoints готовы
- ✅ Интеграция с существующими агентами
- ✅ Тестовый датасет: 100 договоров с метриками точности
- ✅ Документация для юристов

---

## 📚 Приложения

### A. Примеры Intermediate JSON

```json
{
  "doc_number": "ДП-123/2024",
  "signed_date": "2024-01-15",
  "contract_type": "supply",
  "total_amount": 1500000.00,
  "currency": "RUB",

  "parties": [
    {
      "role": "seller",
      "name": "ООО \"Поставщик\"",
      "inn": "7701234567",
      "ogrn": "1027700123456",
      "legal_address": "г. Москва, ул. Ленина, д. 10",
      "bank_details": {
        "account": "40702810100000001234",
        "bank_name": "ПАО Сбербанк",
        "bik": "044525225",
        "correspondent_account": "30101810400000000225"
      }
    },
    {
      "role": "buyer",
      "name": "АО \"Покупатель\"",
      "inn": "7702345678",
      ...
    }
  ],

  "items": [
    {
      "line_number": 1,
      "name": "Товар А",
      "quantity": 100,
      "unit": "шт",
      "price": 10000.00,
      "total": 1000000.00,
      "sku": "SKU-001"
    },
    {
      "line_number": 2,
      "name": "Товар Б",
      "quantity": 50,
      "unit": "кг",
      "price": 10000.00,
      "total": 500000.00,
      "sku": "SKU-002"
    }
  ],

  "payment_schedule": [
    {
      "type": "prepayment",
      "percentage": 30,
      "amount": 450000.00,
      "condition": "в течение 5 рабочих дней с даты подписания",
      "days_offset": 5,
      "trigger": "contract_signing"
    },
    {
      "type": "postpayment",
      "percentage": 70,
      "amount": 1050000.00,
      "condition": "в течение 10 рабочих дней после подписания акта приемки",
      "days_offset": 10,
      "trigger": "act_signing"
    }
  ],

  "rules": [
    {
      "rule_type": "penalty",
      "title": "Неустойка за просрочку поставки",
      "trigger_condition": "delay_days > 0",
      "formula": {
        "type": "penalty",
        "rate": 0.001,
        "base": "outstanding_balance",
        "period": "daily",
        "cap": 0.10
      },
      "original_text": "За каждый день просрочки поставки Поставщик уплачивает неустойку в размере 0,1% от стоимости непоставленного товара за каждый день просрочки, но не более 10% от стоимости договора.",
      "affected_party": "seller",
      "legal_basis": "ст. 330 ГК РФ"
    },
    {
      "rule_type": "termination",
      "title": "Расторжение при существенной просрочке",
      "trigger_condition": "delay_days > 30",
      "formula": {
        "type": "termination",
        "notice_period_days": 10,
        "compensation": "return_prepayment"
      },
      "original_text": "При нарушении срока поставки более чем на 30 календарных дней Покупатель вправе в одностороннем порядке расторгнуть Договор, направив письменное уведомление не позднее чем за 10 дней.",
      "affected_party": "buyer",
      "legal_basis": "ст. 450 ГК РФ"
    }
  ],

  "attributes": {
    "delivery_type": "автотранспорт",
    "delivery_address": "г. Санкт-Петербург, ул. Невский, д. 100",
    "delivery_period": "30 календарных дней",
    "warranty_period": "12 месяцев",
    "quality_certificate": "required",
    "project_manager": "Иванов И.И.",
    "special_conditions": [
      "Товар должен быть новым, без следов эксплуатации",
      "Упаковка должна обеспечивать сохранность товара"
    ]
  }
}
```

### B. Пример SQL запросов к Hybrid Schema

```sql
-- 1. Найти все договоры с предоплатой > 50%
SELECT
    cc.id,
    cc.doc_number,
    cc.total_amount,
    ps.percentage as prepayment_pct
FROM contracts_core cc
JOIN payment_schedule ps ON ps.contract_id = cc.id
WHERE ps.payment_type = 'prepayment'
  AND ps.percentage > 50;

-- 2. Топ-10 контрагентов по объему договоров
SELECT
    cp.name,
    cp.tax_id,
    COUNT(*) as contract_count,
    SUM(cc.total_amount) as total_volume
FROM contract_parties cp
JOIN contracts_core cc ON cc.id = cp.contract_id
WHERE cp.role = 'seller'
  AND cc.status = 'active'
GROUP BY cp.name, cp.tax_id
ORDER BY total_volume DESC
LIMIT 10;

-- 3. Договоры с агрессивными штрафами (>0.5% в день)
SELECT
    cc.id,
    cc.doc_number,
    cr.rule_name,
    cr.formula->>'rate' as penalty_rate
FROM contracts_core cc
JOIN contract_rules cr ON cr.contract_id = cc.id
WHERE cr.section_type = 'penalty'
  AND (cr.formula->>'rate')::numeric > 0.005;

-- 4. Договоры с доставкой авиатранспортом (гибкие атрибуты)
SELECT
    id,
    doc_number,
    attributes->>'delivery_type' as delivery_type,
    attributes->>'delivery_address' as address
FROM contracts_core
WHERE attributes @> '{"delivery_type": "авиа"}';

-- 5. Расчет общего риска по портфелю договоров
WITH penalty_risks AS (
    SELECT
        cc.id,
        cc.doc_number,
        cc.total_amount,
        (cr.formula->>'rate')::numeric *
        EXTRACT(DAYS FROM (CURRENT_DATE - cc.signed_date))::numeric as potential_penalty
    FROM contracts_core cc
    JOIN contract_rules cr ON cr.contract_id = cc.id
    WHERE cr.section_type = 'penalty'
      AND cc.status = 'active'
)
SELECT
    SUM(potential_penalty) as total_risk_amount,
    COUNT(*) as contracts_at_risk
FROM penalty_risks
WHERE potential_penalty > 0;
```

### C. Глоссарий

| Термин | Определение |
|--------|-------------|
| **IDP** | Intelligent Document Processing - автоматизированная обработка документов с помощью AI |
| **Hybrid Star Schema** | Схема БД, комбинирующая жесткие колонки и JSONB для гибких атрибутов |
| **Computable Contract** | Договор, представленный как структурированные данные + исполняемые правила |
| **Cascading Extraction** | Многоуровневая обработка: простые методы (regex) → LLM средней сложности → SOTA LLM |
| **Layout Analysis** | Сегментация документа на визуальные блоки (header, terms, tables, signatures) |
| **Intermediate JSON** | Промежуточный формат данных между извлечением и сохранением в БД |
| **GIN Index** | Generalized Inverted Index - индекс PostgreSQL для быстрого поиска в JSONB |
| **ONNX Runtime** | Кроссплатформенный runtime для ML моделей (позволяет запускать на CPU) |
| **LayoutLMv3** | Microsoft модель для понимания визуальной структуры документов |
| **PaddleOCR** | OCR-система от Baidu, оптимизированная для таблиц |

---

## 📞 Контакты и вопросы

**Автор концепции:** AI Assistant
**Дата:** 2026-01-08
**Версия:** 1.0 (Draft for Discussion)

**Вопросы для обсуждения:**
1. Согласны ли со Hybrid Star Schema или предпочитаете полностью JSONB?
2. Какой приоритет фаз внедрения? (Можем сделать Phase 4 раньше Phase 3)
3. Budget на LLM API? (влияет на выбор моделей)
4. Есть ли доступ к размеченным данным для тестирования?
5. Требования по скорости обработки? (влияет на CPU vs GPU)

---

**СТАТУС:** 📋 Концепция готова к обсуждению
**СЛЕДУЮЩИЙ ШАГ:** Обсуждение и утверждение подхода → Начало Phase 1
