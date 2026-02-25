# 🏗️ IDP Architecture Diagrams

## 1. Общая архитектура системы

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[React/Next.js UI]
        WS[WebSocket Client]
    end

    subgraph "API Layer - FastAPI"
        API["/api/v1/contracts/upload-idp"]
        STATUS["/api/v1/idp/status"]
        RESULT["/api/v1/idp/result"]
        WSS[WebSocket Server]
    end

    subgraph "IDP Core Services"
        ORCH[IDPOrchestrator<br/>Координация пайплайна]
        CLASSIFIER[DocumentClassifier<br/>Определение типа]
        LAYOUT[LayoutAnalyzer<br/>LayoutLMv3 ONNX]
        OCR[EnhancedOCRService<br/>PaddleOCR + Tesseract]
        EXTRACTOR[MultiLevelEntityExtractor<br/>3 уровня каскада]
        MAPPER[SchemaMapper<br/>JSON → Database]
    end

    subgraph "Extraction Levels"
        L1[Level 1: Regex + SpaCy<br/>INN, Dates, Amounts<br/>$0 cost]
        L2[Level 2: Llama-3-8B<br/>Tables, Payment Terms<br/>$0.08/doc]
        L3[Level 3: GPT-4o<br/>Liability, Complex Rules<br/>$0.35/doc]
    end

    subgraph "Storage Layer"
        PG[(PostgreSQL 16+<br/>Hybrid Star Schema)]
        REDIS[(Redis<br/>Cache + Queue)]
        FILES[File Storage<br/>MinIO / S3]
    end

    subgraph "Database Tables"
        CORE[contracts_core<br/>+ JSONB attributes]
        PARTIES[contract_parties]
        ITEMS[contract_items]
        PAYMENTS[payment_schedule]
        RULES[contract_rules<br/>Executable Logic]
        LOG[idp_extraction_log]
    end

    UI -->|Upload| API
    UI -->|Status Check| STATUS
    UI -->|Get Result| RESULT
    WS <-->|Real-time| WSS

    API --> ORCH
    STATUS --> LOG
    RESULT --> CORE

    ORCH --> CLASSIFIER
    CLASSIFIER -->|XML| MAPPER
    CLASSIFIER -->|PDF| LAYOUT
    CLASSIFIER -->|Scan| OCR

    LAYOUT --> EXTRACTOR
    OCR --> LAYOUT

    EXTRACTOR --> L1
    L1 -->|If insufficient| L2
    L2 -->|If complex| L3

    L1 --> MAPPER
    L2 --> MAPPER
    L3 --> MAPPER

    MAPPER --> CORE
    MAPPER --> PARTIES
    MAPPER --> ITEMS
    MAPPER --> PAYMENTS
    MAPPER --> RULES
    MAPPER --> LOG

    ORCH -.->|Cache| REDIS
    ORCH -.->|Store| FILES

    style CORE fill:#4CAF50
    style RULES fill:#FF9800
    style ORCH fill:#2196F3
    style L1 fill:#81C784
    style L2 fill:#FFB74D
    style L3 fill:#E57373
```

---

## 2. Пайплайн обработки документа

```mermaid
flowchart TD
    START([Загрузка файла]) --> SAVE[Сохранение в файловое хранилище]
    SAVE --> CLASS{Классификация<br/>типа документа}

    CLASS -->|XML| XML_PARSE[Детерминированный<br/>XML парсинг<br/>DocumentParser]
    CLASS -->|Searchable PDF| PDF_PARSE[Извлечение текста<br/>pdfplumber]
    CLASS -->|Scanned PDF/Image| OCR_PROC[OCR обработка<br/>PaddleOCR]

    XML_PARSE --> INTERMEDIATE[Intermediate JSON]

    PDF_PARSE --> LAYOUT[Layout Analysis<br/>LayoutLMv3 ONNX<br/>⏱️ 3-5 сек/страница]
    OCR_PROC --> LAYOUT

    LAYOUT --> BLOCKS[Document Blocks<br/>Header, Preamble,<br/>Terms, Tables,<br/>Signatures]

    BLOCKS --> CASCADE{Cascading<br/>Extraction}

    CASCADE --> L1_EXTRACT[Level 1: Regex + SpaCy<br/>💰 Бесплатно<br/>⏱️ <1 сек]
    L1_EXTRACT --> L1_RESULT{Достаточно<br/>данных?}

    L1_RESULT -->|Да| INTERMEDIATE
    L1_RESULT -->|Нет| L2_EXTRACT[Level 2: Llama-3-8B<br/>💰 $0.08/doc<br/>⏱️ 10-20 сек]

    L2_EXTRACT --> L2_RESULT{Достаточно<br/>данных?}
    L2_RESULT -->|Да| INTERMEDIATE
    L2_RESULT -->|Нет| L3_EXTRACT[Level 3: GPT-4o<br/>💰 $0.35/doc<br/>⏱️ 20-40 сек]

    L3_EXTRACT --> INTERMEDIATE

    INTERMEDIATE --> VALIDATE[Валидация<br/>Pydantic Models]

    VALIDATE -->|Ошибки| QUALITY[Создание<br/>Quality Issues]
    VALIDATE -->|OK| MAP[Schema Mapping]
    QUALITY --> MAP

    MAP --> DB_CORE[(contracts_core<br/>+ attributes JSONB)]
    MAP --> DB_PARTIES[(contract_parties)]
    MAP --> DB_ITEMS[(contract_items)]
    MAP --> DB_PAYMENTS[(payment_schedule)]
    MAP --> DB_RULES[(contract_rules)]
    MAP --> DB_LOG[(idp_extraction_log)]

    DB_CORE --> DONE([✅ Обработка<br/>завершена])
    DB_PARTIES --> DONE
    DB_ITEMS --> DONE
    DB_PAYMENTS --> DONE
    DB_RULES --> DONE
    DB_LOG --> DONE

    style START fill:#4CAF50
    style DONE fill:#4CAF50
    style L1_EXTRACT fill:#81C784
    style L2_EXTRACT fill:#FFB74D
    style L3_EXTRACT fill:#E57373
    style DB_RULES fill:#FF9800
    style INTERMEDIATE fill:#2196F3
```

---

## 3. Hybrid Star Schema (База данных)

```mermaid
erDiagram
    contracts_core ||--o{ contract_parties : "has"
    contracts_core ||--o{ contract_items : "has"
    contracts_core ||--o{ payment_schedule : "has"
    contracts_core ||--o{ contract_rules : "has"
    contracts_core ||--o{ idp_extraction_log : "logged"
    contracts_core ||--o{ idp_quality_issues : "has issues"

    contracts_core {
        uuid id PK
        varchar doc_number
        date signed_date
        varchar status
        numeric total_amount
        char currency
        jsonb attributes "🔑 Гибкие поля"
        jsonb raw_data "Полный JSON"
        uuid source_file_id FK
        timestamp created_at
    }

    contract_parties {
        uuid id PK
        uuid contract_id FK
        varchar role "buyer/seller/guarantor"
        varchar name
        varchar tax_id "ИНН"
        varchar registration_number "ОГРН"
        text legal_address
        jsonb bank_details
    }

    contract_items {
        uuid id PK
        uuid contract_id FK
        int line_number
        varchar sku_code
        text name
        numeric quantity
        varchar unit
        numeric price_unit
        numeric total_line
        jsonb attributes "🔑 Гибкие поля"
    }

    payment_schedule {
        uuid id PK
        uuid contract_id FK
        varchar payment_type
        numeric amount
        date due_date
        text due_condition "Относительная дата"
        int days_offset
        varchar trigger_event
        varchar status
    }

    contract_rules {
        uuid id PK
        uuid contract_id FK
        varchar section_type "penalty/termination/sla"
        varchar rule_name
        text trigger_condition
        jsonb formula "🔥 Исполняемая формула"
        text original_text "Цитата из договора"
        varchar clause_location "XPath"
        numeric confidence_score
        boolean is_active
    }

    idp_extraction_log {
        uuid id PK
        uuid contract_id FK
        varchar stage
        varchar status
        jsonb output_data
        int duration_ms
        int tokens_used
        numeric cost_usd
        timestamp created_at
    }

    idp_quality_issues {
        uuid id PK
        uuid contract_id FK
        varchar issue_type
        varchar severity
        text description
        boolean requires_manual_review
        varchar status
    }
```

---

## 4. Cascading Extraction Strategy

```mermaid
graph LR
    subgraph "Document Blocks"
        B1[Header]
        B2[Preamble]
        B3[Terms]
        B4[Payment Table]
        B5[Liability]
        B6[Signatures]
    end

    subgraph "Level 1: CPU/Free"
        R1[Regex: doc_number, dates]
        R2[SpaCy NER: organizations]
        R3[Regex: amounts, INN]
        R4[Rule-based: structure]
    end

    subgraph "Level 2: API/Cheap"
        L2A[Llama-3-8B: Tables]
        L2B[Llama-3-8B: Payment]
        L2C[Llama-3-8B: Terms]
    end

    subgraph "Level 3: API/Expensive"
        L3A[GPT-4o: Liability Rules]
        L3B[GPT-4o: Force Majeure]
        L3C[GPT-4o: Termination]
    end

    B1 --> R1
    B2 --> R2
    B3 --> R3
    B6 --> R4

    B4 --> L2A
    B3 --> L2B
    B3 --> L2C

    B5 --> L3A
    B5 --> L3B
    B5 --> L3C

    R1 --> RESULT[Intermediate JSON]
    R2 --> RESULT
    R3 --> RESULT
    R4 --> RESULT
    L2A --> RESULT
    L2B --> RESULT
    L2C --> RESULT
    L3A --> RESULT
    L3B --> RESULT
    L3C --> RESULT

    style R1 fill:#81C784
    style R2 fill:#81C784
    style R3 fill:#81C784
    style R4 fill:#81C784
    style L2A fill:#FFB74D
    style L2B fill:#FFB74D
    style L2C fill:#FFB74D
    style L3A fill:#E57373
    style L3B fill:#E57373
    style L3C fill:#E57373
    style RESULT fill:#2196F3
```

---

## 5. Интеграция с существующей системой

```mermaid
graph TB
    subgraph "Existing System"
        OLD_API[OLD: /contracts/upload]
        OLD_PARSER[DocumentParser<br/>DOCX/PDF → XML]
        OLD_ANALYZER[ContractAnalyzerAgent<br/>XML analysis]
        OLD_DB[(contracts table<br/>meta_info: XML)]
    end

    subgraph "New IDP System"
        NEW_API[NEW: /contracts/upload-idp]
        IDP_ORCH[IDPOrchestrator]
        IDP_EXTRACTOR[Cascading Extraction]
        NEW_DB[(contracts_core<br/>Hybrid Schema)]
    end

    subgraph "Backward Compatibility Layer"
        COMPAT[BackwardCompatibilityLayer<br/>Sync old ↔ new]
    end

    USER[User Upload] -->|enable_idp=false| OLD_API
    USER -->|enable_idp=true| NEW_API

    OLD_API --> OLD_PARSER
    OLD_PARSER --> OLD_DB
    OLD_DB --> OLD_ANALYZER

    NEW_API --> IDP_ORCH
    IDP_ORCH --> IDP_EXTRACTOR
    IDP_EXTRACTOR --> NEW_DB

    OLD_DB -.->|Sync| COMPAT
    NEW_DB -.->|Sync| COMPAT

    OLD_ANALYZER -.->|Enhanced with| NEW_DB

    NEW_ANALYZER[Enhanced Analyzer<br/>Uses structured data] --> NEW_DB
    NEW_ANALYZER -.->|Fallback| OLD_DB

    style OLD_API fill:#FFC107
    style NEW_API fill:#4CAF50
    style NEW_DB fill:#4CAF50
    style COMPAT fill:#9E9E9E
```

---

## 6. Cost Optimization Strategy

```mermaid
graph TD
    START[Document Received] --> CACHE{Check LLM Cache}

    CACHE -->|Hit 60-70%| CACHED[Return Cached Result<br/>💰 $0]
    CACHE -->|Miss| COMPLEXITY{Estimate Complexity}

    COMPLEXITY -->|Simple 40%| L1[Level 1: Regex/SpaCy<br/>💰 $0<br/>⏱️ <1 sec]
    COMPLEXITY -->|Medium 40%| L2[Level 2: Llama-3-8B<br/>💰 $0.08<br/>⏱️ 10-20 sec]
    COMPLEXITY -->|Complex 20%| L3[Level 3: GPT-4o<br/>💰 $0.35<br/>⏱️ 20-40 sec]

    L1 --> SAVE_CACHE[Save to Cache]
    L2 --> SAVE_CACHE
    L3 --> SAVE_CACHE

    CACHED --> RESULT[Final Result]
    SAVE_CACHE --> RESULT

    RESULT --> COST_CALC[Average Cost Calculation]

    COST_CALC --> FINAL["Average: $0.10-0.30/doc<br/>vs $1.50 (Azure)<br/>vs $10 (Manual)<br/>🎯 Savings: 5-100x"]

    style CACHED fill:#4CAF50
    style L1 fill:#81C784
    style L2 fill:#FFB74D
    style L3 fill:#E57373
    style FINAL fill:#2196F3
```

---

## 7. Real-time Progress Tracking

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API
    participant IDPOrchestrator
    participant WebSocket
    participant Database

    User->>Frontend: Upload Document
    Frontend->>API: POST /upload-idp
    API->>Database: Create Contract Record
    API->>IDPOrchestrator: Start Processing (Background)
    API-->>Frontend: 202 Accepted {contract_id}

    Frontend->>WebSocket: Connect ws://idp/{contract_id}
    WebSocket-->>Frontend: Connection Established

    loop Processing Stages
        IDPOrchestrator->>Database: Log Stage: classification
        IDPOrchestrator->>WebSocket: Progress: 20% (classification)
        WebSocket-->>Frontend: Update UI: 20%

        IDPOrchestrator->>Database: Log Stage: layout_analysis
        IDPOrchestrator->>WebSocket: Progress: 40% (layout_analysis)
        WebSocket-->>Frontend: Update UI: 40%

        IDPOrchestrator->>Database: Log Stage: entity_extraction
        IDPOrchestrator->>WebSocket: Progress: 70% (extraction)
        WebSocket-->>Frontend: Update UI: 70%

        IDPOrchestrator->>Database: Save to contracts_core
        IDPOrchestrator->>WebSocket: Progress: 100% (completed)
        WebSocket-->>Frontend: Update UI: 100%
    end

    Frontend->>API: GET /idp/result/{contract_id}
    API->>Database: Query contracts_core
    Database-->>API: Structured Data
    API-->>Frontend: Display Results
    Frontend-->>User: Show Extracted Data
```

---

## 8. Executable Rules Engine

```mermaid
graph TB
    subgraph "Rule Storage (contract_rules table)"
        RULE1[Rule: Penalty for Delay<br/>trigger: delay_days > 0<br/>formula: rate=0.001, period=daily]
        RULE2[Rule: Termination<br/>trigger: delay_days > 30<br/>formula: notice_period=10]
        RULE3[Rule: Quality Defect<br/>trigger: defect_count > 0<br/>formula: rate=0.05, base=item_price]
    end

    subgraph "Event Triggers"
        EVENT1[Delivery Delayed<br/>delay_days = 15]
        EVENT2[Quality Issue<br/>defect_count = 5]
        EVENT3[Extreme Delay<br/>delay_days = 45]
    end

    subgraph "Rule Engine Executor"
        EVAL[Evaluate Conditions]
        CALC[Calculate Penalties]
        NOTIFY[Notify Stakeholders]
    end

    subgraph "Outputs"
        PENALTY1[Penalty: 15,000 RUB<br/>1,000,000 * 0.001 * 15]
        PENALTY2[Penalty: 50,000 RUB<br/>1,000,000 * 0.05]
        ACTION[Action: Send Termination<br/>Notice 10 days]
    end

    EVENT1 --> EVAL
    EVENT2 --> EVAL
    EVENT3 --> EVAL

    RULE1 -.-> EVAL
    RULE2 -.-> EVAL
    RULE3 -.-> EVAL

    EVAL --> CALC
    CALC --> PENALTY1
    CALC --> PENALTY2
    CALC --> ACTION

    PENALTY1 --> NOTIFY
    PENALTY2 --> NOTIFY
    ACTION --> NOTIFY

    style RULE1 fill:#FF9800
    style RULE2 fill:#FF9800
    style RULE3 fill:#FF9800
    style PENALTY1 fill:#E57373
    style PENALTY2 fill:#E57373
    style ACTION fill:#E57373
```

---

## 9. Deployment Architecture

```mermaid
graph TB
    subgraph "Production Environment"
        LB[Load Balancer<br/>Nginx]

        subgraph "Application Servers"
            APP1[FastAPI Instance 1]
            APP2[FastAPI Instance 2]
            APP3[FastAPI Instance 3]
        end

        subgraph "Worker Processes"
            W1[Celery Worker 1<br/>IDP Processing]
            W2[Celery Worker 2<br/>IDP Processing]
            W3[Celery Worker 3<br/>IDP Processing]
        end

        subgraph "Data Layer"
            PG[(PostgreSQL 16+<br/>Primary)]
            PG_REPLICA[(PostgreSQL<br/>Read Replica)]
            REDIS[(Redis<br/>Cache + Queue)]
            S3[MinIO / S3<br/>File Storage]
        end

        subgraph "Monitoring"
            PROM[Prometheus<br/>Metrics]
            GRAFANA[Grafana<br/>Dashboards]
            LOG[ELK Stack<br/>Logs]
        end
    end

    LB --> APP1
    LB --> APP2
    LB --> APP3

    APP1 --> REDIS
    APP2 --> REDIS
    APP3 --> REDIS

    REDIS --> W1
    REDIS --> W2
    REDIS --> W3

    W1 --> PG
    W2 --> PG
    W3 --> PG

    APP1 --> PG_REPLICA
    APP2 --> PG_REPLICA
    APP3 --> PG_REPLICA

    W1 --> S3
    W2 --> S3
    W3 --> S3

    APP1 -.-> PROM
    APP2 -.-> PROM
    APP3 -.-> PROM
    W1 -.-> PROM
    W2 -.-> PROM
    W3 -.-> PROM

    PROM --> GRAFANA

    APP1 -.-> LOG
    APP2 -.-> LOG
    APP3 -.-> LOG
    W1 -.-> LOG
    W2 -.-> LOG
    W3 -.-> LOG

    style PG fill:#4CAF50
    style REDIS fill:#FF5722
    style GRAFANA fill:#2196F3
```

---

## 10. Phase Rollout Plan

```mermaid
gantt
    title IDP Integration Roadmap (8 weeks)
    dateFormat  YYYY-MM-DD
    section Phase 1: Foundation
    Database Schema         :a1, 2024-01-15, 7d
    Alembic Migrations     :a2, after a1, 3d
    SchemaMapper (no AI)   :a3, after a1, 5d
    Unit Tests             :a4, after a3, 2d

    section Phase 2: Level 1
    Regex Extractors       :b1, after a4, 5d
    SpaCy Integration      :b2, after b1, 3d
    XML Processing         :b3, after b2, 4d
    API Endpoints          :b4, after b3, 2d

    section Phase 3: Layout + OCR
    PaddleOCR Setup        :c1, after b4, 3d
    LayoutLMv3 ONNX        :c2, after c1, 5d
    Layout Analyzer        :c3, after c2, 4d
    PDF Processing         :c4, after c3, 2d

    section Phase 4: Cascading LLM
    Level 2 (Llama-3)      :d1, after c4, 5d
    Level 3 (GPT-4o)       :d2, after d1, 5d
    LLM Router             :d3, after d2, 2d
    WebSocket Progress     :d4, after d3, 2d
    Full Integration       :d5, after d4, 3d

    section Testing & Launch
    End-to-end Tests       :e1, after d5, 3d
    Performance Tuning     :e2, after e1, 2d
    Documentation          :e3, after e2, 2d
    Production Deploy      :milestone, e4, after e3, 0d
```

---

**Все диаграммы можно открыть в Mermaid Live Editor:** https://mermaid.live/
