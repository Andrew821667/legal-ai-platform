# 🚀 Детальный план реализации Contract AI System v2.0 (ОБНОВЛЕННЫЙ)

**Версия:** 2.1 (с учетом дополнительных требований)
**Дата обновления:** 2026-01-09
**Общая длительность:** 20 недель (5 этапов)
**Методология:** Итеративная разработка с тестированием после каждого этапа

---

## 📊 Общая структура плана

```
Stage 0: Инфраструктура           [Недели 1-2]   ████░░░░░░░░░░░░░░░░ 10%
Stage 1: Post-Execution MVP       [Недели 3-6]   ░░░░████████░░░░░░░░ 30%
Stage 2: Pre-Execution            [Недели 7-10]  ░░░░░░░░░░░░████████ 40%
Stage 3: Smart Router Production  [Недели 11-14] ░░░░░░░░░░░░░░░░████ 60%
Stage 4: Интеграции + UI          [Недели 15-20] ░░░░░░░░░░░░░░░░░░░░ 100%
```

---

## 🔴 ОБЯЗАТЕЛЬНЫЕ требования для ВСЕХ этапов

1. **UI для тестирования:** Для КАЖДОГО Stage создавать интерфейс тестирования (ручной режим + визуальное отображение результатов)
2. **Человек в цикле:** Все действия системы - только после одобрения пользователем
3. **Рекомендации + Расхождения:** Система выдает не только расхождения, но и свои рекомендации
4. **Админ-консоль:** Streamlit dashboard + основной UI с максимумом показателей
5. **RAG на каждом этапе:** RAG как фильтр на всех этапах обработки

---

## 🤖 Расширенная матрица моделей

| Модель | Роль | Стоимость (вход) | Применение |
|--------|------|------------------|------------|
| **DeepSeek-V3** | Primary Worker | $0.14 / 1M токенов | 90% задач, основной worker |
| **Claude 4.5 Sonnet** | Expert Fallback | $3.00 / 1M токенов | Сложные сканы, плохое качество, Vision |
| **GPT-4o** | Reserve Channel | $2.50 / 1M токенов | Резервный канал при недоступности |
| **GPT-4o-mini** | Testing & Validation | $0.15 / 1M токенов | Тестирование системы, валидация результатов |

**Зачем GPT-4o-mini:**
- Дешевая, но умная модель для проверки работоспособности пайплайна
- Быстрое тестирование без больших затрат
- Валидация результатов других моделей

---

## 🎛️ Режимы работы системы

Система поддерживает три режима работы, настраиваемые через UI:

### 1. Полная нагрузка (Production Mode)
- Все модули пайплайна работают параллельно
- Максимальная скорость обработки
- Для компаний с высоким потоком документов

### 2. Последовательный режим (Economy Mode)
- Модули включаются по очереди
- Этап прошел → модуль отключился → следующий включился
- Для малых компаний с небольшим потоком документов
- Экономия ресурсов сервера

### 3. Ручной режим (Custom Mode)
- Пользователь выбирает какие модули включить
- Максимальная гибкость для специфичных задач
- Настройка через админ-панель

---

## 🔍 RAG Strategy

RAG (Retrieval-Augmented Generation) используется на каждом этапе как фильтр:

1. **Pre-Execution:**
   - Поиск похожих договоров из истории
   - Извлечение best practices из базы знаний
   - Контекстные рекомендации на основе прошлых кейсов

2. **Post-Execution:**
   - Проверка извлеченных данных против эталонных значений
   - Автодополнение пропущенных полей из похожих договоров
   - Валидация правил и формул

3. **Risk Scoring:**
   - Контекст из базы прецедентов (какие риски материализовались)
   - Отраслевые стандарты и нормативы

**Технический стек RAG:**
- **Vector Store:** pgvector (для договоров) + ChromaDB (для базы знаний)
- **Embedding Model:** text-embedding-3-small или multilingual-e5-large
- **Retrieval:** Hybrid search (semantic + keyword)

---

# Stage 0: Инфраструктура и подготовка (Недели 1-2)

**Цель:** Подготовить фундамент системы - база данных, API ключи, базовая архитектура.

## Задачи

### 0.1 Миграция базы данных (День 1-3)

**Файлы для создания:**
- `alembic/versions/002_create_contracts_core.py` - Основная таблица
- `alembic/versions/003_create_related_tables.py` - Связанные таблицы
- `alembic/versions/004_enable_pgvector.py` - Векторное расширение
- `alembic/versions/005_create_system_config.py` - Таблица конфигурации режимов

**Таблицы для создания:**

```sql
1. contracts_core
   - id (UUID, PK)
   - doc_number (VARCHAR(100), NOT NULL, UNIQUE)
   - signed_date (DATE)
   - status (VARCHAR(20), CHECK IN 'negotiating'/'active'/'closed')
   - total_amount (NUMERIC(15,2))
   - currency (CHAR(3), DEFAULT 'RUB')
   - attributes (JSONB) -- Гибкие поля
   - raw_data (JSONB)   -- Полный результат IDP
   - embedding (vector(1536)) -- Для поиска
   - created_at, updated_at (TIMESTAMP)

2. contract_parties
   - id (UUID, PK)
   - contract_id (UUID, FK → contracts_core)
   - role (VARCHAR(20): 'client'/'supplier'/'guarantor')
   - name (VARCHAR(255))
   - inn (VARCHAR(12))
   - kpp (VARCHAR(9))
   - address (TEXT)

3. contract_items
   - id (UUID, PK)
   - contract_id (UUID, FK)
   - item_number (INTEGER)
   - description (TEXT)
   - quantity (NUMERIC(10,2))
   - unit (VARCHAR(20))
   - price (NUMERIC(15,2))

4. payment_schedule
   - id (UUID, PK)
   - contract_id (UUID, FK)
   - payment_type (VARCHAR(50): 'prepayment'/'postpayment'/'milestone')
   - amount (NUMERIC(15,2))
   - percent (NUMERIC(5,2))
   - due_date (DATE)

5. contract_rules
   - id (UUID, PK)
   - contract_id (UUID, FK)
   - rule_type (VARCHAR(50): 'penalty'/'sla'/'termination')
   - trigger_condition (TEXT)
   - formula (JSONB) -- { "rate": 0.001, "base": "total_amount", "cap": 0.1 }
   - original_text (TEXT)

6. negotiation_sessions
   - id (UUID, PK)
   - uploaded_doc_path (TEXT)
   - status (VARCHAR(20): 'analyzing'/'awaiting_approval'/'approved'/'rejected'/'archived')
   - template_id (UUID, nullable) -- Ссылка на шаблон для сравнения
   - risk_score (NUMERIC(3,2))
   - ai_recommendations (JSONB) -- Рекомендации системы
   - created_at (TIMESTAMP)

7. disagreements
   - id (UUID, PK)
   - session_id (UUID, FK → negotiation_sessions)
   - section (VARCHAR(100))
   - their_clause (TEXT)
   - our_standard (TEXT)
   - risk_level (VARCHAR(20): 'critical'/'high'/'medium'/'low')
   - suggested_wording (TEXT)
   - ai_recommendation (TEXT) -- НОВОЕ: рекомендация системы для текущей ситуации
   - user_approved (BOOLEAN DEFAULT FALSE) -- НОВОЕ: одобрение пользователя

8. system_config (НОВАЯ ТАБЛИЦА)
   - id (UUID, PK)
   - config_key (VARCHAR(100), UNIQUE)
   - config_value (JSONB)
   - description (TEXT)
   - updated_at (TIMESTAMP)
   -- Хранит: режим работы системы, включенные модули, настройки RAG

9. user_approvals (НОВАЯ ТАБЛИЦА)
   - id (UUID, PK)
   - entity_type (VARCHAR(50): 'negotiation'/'extraction'/'protocol')
   - entity_id (UUID) -- ID сессии или контракта
   - action (VARCHAR(100): 'approve_protocol'/'reject_extraction'/'approve_digitization')
   - approved_by (VARCHAR(100)) -- User ID
   - approved_at (TIMESTAMP)
   - comment (TEXT)

10. knowledge_base (НОВАЯ ТАБЛИЦА для RAG)
    - id (UUID, PK)
    - content_type (VARCHAR(50): 'best_practice'/'regulation'/'precedent')
    - title (VARCHAR(255))
    - content (TEXT)
    - embedding (vector(1536))
    - metadata (JSONB)
    - created_at (TIMESTAMP)
```

**Тестирование:**
```bash
# Применить миграции
alembic upgrade head

# Проверить структуру
psql -d contract_ai -c "\d contracts_core"
psql -d contract_ai -c "\d system_config"
psql -d contract_ai -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

### 0.2 Конфигурация API ключей (День 3-4)

**Файлы для создания/изменения:**
- `src/config/llm_config.py` - Конфигурация моделей

```python
from pydantic_settings import BaseSettings

class LLMConfig(BaseSettings):
    # DeepSeek
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-v3"
    DEEPSEEK_MAX_TOKENS: int = 4096

    # Anthropic Claude
    ANTHROPIC_API_KEY: str
    ANTHROPIC_MODEL: str = "claude-4-5-sonnet-20250929"
    ANTHROPIC_MAX_TOKENS: int = 4096

    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MODEL_MINI: str = "gpt-4o-mini"  # НОВОЕ: для тестирования

    # Router Config
    ROUTER_DEFAULT_MODEL: str = "deepseek-v3"
    ROUTER_COMPLEXITY_THRESHOLD: float = 0.8

    # RAG Config
    RAG_ENABLED: bool = True
    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.7

    class Config:
        env_file = ".env"
```

**Файл `.env.example`:**
```bash
# LLM API Keys
DEEPSEEK_API_KEY=your_deepseek_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/contract_ai

# RAG
RAG_ENABLED=true
RAG_TOP_K=5
```

### 0.3 Базовый Smart Router + RAG (День 4-5)

**Файл:** `src/services/model_router.py`

```python
class ModelRouter:
    def __init__(self, rag_service: Optional[RAGService] = None):
        self.rag = rag_service

    def select_model(
        self,
        doc_complexity_score: float = 0.0,
        is_scanned_image: bool = False,
        force_model: Optional[str] = None,
        use_rag_context: bool = True
    ) -> str:
        """
        Выбор модели для обработки документа с учетом RAG.

        Args:
            doc_complexity_score: 0.0-1.0, оценка сложности документа
            is_scanned_image: True если документ - скан/фото
            force_model: Принудительный выбор модели
            use_rag_context: Использовать ли RAG для выбора модели

        Returns:
            Название модели для использования
        """
        if force_model:
            return force_model

        # RAG: проверка похожих документов и их успешной обработки
        if use_rag_context and self.rag:
            similar_docs = self.rag.find_similar_processed_docs(doc_complexity_score)
            if similar_docs:
                # Если похожие документы успешно обработаны дешевой моделью
                if all(doc["model"] == "deepseek-v3" and doc["success"] for doc in similar_docs):
                    return "deepseek-v3"

        if is_scanned_image and doc_complexity_score > 0.8:
            return "claude-4-5-sonnet"

        return "deepseek-v3"
```

### 0.4 RAG Service (День 5-6)

**Файл:** `src/services/rag_service.py`

```python
class RAGService:
    def __init__(self, vector_store, embedding_model):
        self.vector_store = vector_store
        self.embedding_model = embedding_model

    async def retrieve_context(
        self,
        query: str,
        context_type: str,  # 'contract' | 'best_practice' | 'regulation'
        top_k: int = 5
    ) -> List[Dict]:
        """
        Извлечение релевантного контекста из векторной базы.
        """
        embedding = await self.embedding_model.encode(query)

        results = await self.vector_store.search(
            embedding=embedding,
            filter={"content_type": context_type},
            top_k=top_k
        )

        return results

    async def filter_with_context(
        self,
        extracted_data: Dict,
        context: List[Dict]
    ) -> Dict:
        """
        Фильтрация и улучшение извлеченных данных с помощью контекста.
        """
        # Проверка извлеченных данных против эталонных значений из контекста
        # Автодополнение пропущенных полей
        # Валидация формул и правил
        pass
```

### 0.5 System Config Service (День 6-7)

**Файл:** `src/services/system_config_service.py`

```python
class SystemMode(Enum):
    FULL_LOAD = "full_load"          # Все модули параллельно
    SEQUENTIAL = "sequential"         # Последовательно
    MANUAL = "manual"                 # Ручной выбор модулей

class SystemConfigService:
    async def get_current_mode(self) -> SystemMode:
        """Получить текущий режим работы системы."""
        config = await self.db.get_config("system_mode")
        return SystemMode(config["value"])

    async def set_mode(self, mode: SystemMode, enabled_modules: List[str] = None):
        """Установить режим работы системы."""
        await self.db.update_config("system_mode", {"value": mode.value})

        if mode == SystemMode.MANUAL and enabled_modules:
            await self.db.update_config("enabled_modules", {"modules": enabled_modules})

    async def is_module_enabled(self, module_name: str) -> bool:
        """Проверить, включен ли модуль."""
        mode = await self.get_current_mode()

        if mode == SystemMode.FULL_LOAD:
            return True
        elif mode == SystemMode.MANUAL:
            config = await self.db.get_config("enabled_modules")
            return module_name in config["modules"]
        else:  # SEQUENTIAL
            # Логика последовательного включения модулей
            return await self._check_sequential_module(module_name)
```

### 0.6 Streamlit Admin Dashboard (День 7)

**Файл:** `admin/streamlit_dashboard.py`

```python
import streamlit as st

st.set_page_config(page_title="Contract AI Admin", layout="wide")

# Sidebar: Настройки системы
st.sidebar.title("⚙️ Настройки системы")

mode = st.sidebar.selectbox(
    "Режим работы",
    ["Полная нагрузка", "Последовательный", "Ручной"]
)

if mode == "Ручной":
    modules = st.sidebar.multiselect(
        "Включенные модули",
        ["OCR", "Level1 Extraction", "LLM Extraction", "RAG Filter", "Validation"]
    )

# Main area: Метрики
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Документов обработано", "1,234", "+12%")
with col2:
    st.metric("Средняя стоимость", "$0.023", "-85%")
with col3:
    st.metric("Accuracy", "96.5%", "+2.3%")
with col4:
    st.metric("Ожидают одобрения", "7", "⚠️")

# Графики
st.subheader("📊 Использование моделей")
# Pie chart: DeepSeek vs Claude vs GPT-4o

st.subheader("💰 Стоимость по дням")
# Line chart: daily cost

st.subheader("🕒 Документы требующие одобрения")
# Table: список документов awaiting_approval
```

---

## ✅ Критерии завершения Stage 0

- [ ] База данных мигрирована, все 10 таблиц созданы
- [ ] pgvector расширение установлено и работает
- [ ] `.env` файл настроен с API ключами (DeepSeek + Anthropic + OpenAI)
- [ ] Тестовое подключение ко всем API работает (включая GPT-4o-mini)
- [ ] `ModelRouter` выбирает модель по логике (с учетом RAG)
- [ ] `RAGService` извлекает контекст из векторной базы
- [ ] `SystemConfigService` управляет режимами работы
- [ ] Streamlit dashboard отображает базовые метрики
- [ ] **UI тестирования:** Streamlit страница для проверки подключения API и режимов

**Время на тестирование:** 1 день
**Общее время Stage 0:** 2 недели

---

# Stage 1: Post-Execution MVP (Недели 3-6)

**Цель:** Научиться обрабатывать подписанные документы и превращать их в цифровые двойники.

## Задачи

### 1.1 Endpoint: Загрузка подписанного документа (Неделя 3, День 1-3)

**Файл:** `src/api/contracts/post_execution_routes.py`

```python
@router.post("/api/v1/contracts/digitize")
async def digitize_contract(
    file: UploadFile = File(...),
    force_model: Optional[str] = Query(None),
    request_approval: bool = Query(True),  # НОВОЕ: требовать одобрения
    background_tasks: BackgroundTasks
):
    """
    Загрузка подписанного документа для цифровизации.

    Args:
        file: PDF/DOCX файл подписанного договора
        force_model: Принудительный выбор модели
        request_approval: Требовать ли одобрение пользователя перед сохранением в БД

    Returns:
        { "task_id": "uuid", "status": "processing" | "awaiting_approval" }
    """
```

### 1.2 Orchestrator с RAG и одобрением (Неделя 3, День 3-7)

**Файл:** `src/services/post_execution_orchestrator.py`

```python
class PostExecutionOrchestrator:
    def __init__(
        self,
        model_router: ModelRouter,
        llm_client: LLMClient,
        rag_service: RAGService,
        config_service: SystemConfigService
    ):
        self.router = model_router
        self.llm = llm_client
        self.rag = rag_service
        self.config = config_service

    async def process_document(
        self,
        file_path: str,
        force_model: Optional[str] = None,
        request_approval: bool = True
    ):
        """
        Полный пайплайн обработки с RAG на каждом этапе.

        Этапы:
        1. Извлечение текста (если модуль включен)
        2. Level 1: Regex/SpaCy extraction (если модуль включен)
        3. RAG: Поиск похожих документов для контекста
        4. Level 2: LLM extraction (через Router)
        5. RAG Filter: Валидация извлеченных данных
        6. Сохранение в БД (если одобрено пользователем)
        7. Генерация embedding
        """
        # Проверка режима работы
        mode = await self.config.get_current_mode()

        # Stage 1: Text Extraction (если модуль включен)
        if await self.config.is_module_enabled("ocr"):
            text = await self.extract_text(file_path)
        else:
            return {"status": "waiting", "reason": "OCR module disabled"}

        # Stage 2: Level 1 Extraction
        if await self.config.is_module_enabled("level1_extraction"):
            level1_data = self.extract_level1(text)

        # Stage 3: RAG - Поиск похожих документов
        similar_docs = await self.rag.retrieve_context(
            query=text[:500],  # Первые 500 символов для поиска
            context_type="contract",
            top_k=5
        )

        # Stage 4: Select Model
        model = self.router.select_model(
            force_model=force_model,
            use_rag_context=True
        )

        # Stage 5: LLM Extraction с контекстом из RAG
        prompt_with_context = self._build_prompt_with_rag(text, similar_docs)
        intermediate_json = await self.llm.extract_structured_data(
            prompt_with_context, model
        )

        # Stage 6: RAG Filter - Валидация
        validated_data = await self.rag.filter_with_context(
            extracted_data=intermediate_json,
            context=similar_docs
        )

        # Stage 7: Запрос одобрения (если требуется)
        if request_approval:
            approval_id = await self.create_approval_request(
                entity_type="extraction",
                data=validated_data
            )
            return {
                "status": "awaiting_approval",
                "approval_id": approval_id,
                "preview": validated_data
            }

        # Stage 8: Save to DB
        contract_id = await self.save_to_db(validated_data)

        # Stage 9: Generate embedding
        await self.generate_embedding(contract_id, text)

        return {"status": "completed", "contract_id": contract_id}
```

### 1.3 Approval Service (Неделя 4, День 1-2)

**Файл:** `src/services/approval_service.py`

```python
class ApprovalService:
    async def create_approval_request(
        self,
        entity_type: str,
        entity_id: UUID,
        data: Dict
    ) -> UUID:
        """Создать запрос на одобрение."""
        approval = UserApproval(
            entity_type=entity_type,
            entity_id=entity_id,
            action=f"approve_{entity_type}",
            status="pending",
            data_preview=data
        )
        await self.db.save(approval)
        return approval.id

    async def approve(
        self,
        approval_id: UUID,
        user_id: str,
        comment: Optional[str] = None
    ):
        """Одобрить запрос."""
        approval = await self.db.get_approval(approval_id)
        approval.approved_by = user_id
        approval.approved_at = datetime.utcnow()
        approval.comment = comment
        approval.status = "approved"
        await self.db.update(approval)

        # Выполнить отложенное действие (например, сохранение в БД)
        await self.execute_approved_action(approval)

    async def reject(
        self,
        approval_id: UUID,
        user_id: str,
        reason: str
    ):
        """Отклонить запрос."""
        approval = await self.db.get_approval(approval_id)
        approval.approved_by = user_id
        approval.comment = reason
        approval.status = "rejected"
        await self.db.update(approval)
```

### 1.4 UI для тестирования Stage 1 (Неделя 4, День 3-5)

**Файл:** `admin/pages/1_Test_Post_Execution.py`

```python
import streamlit as st

st.title("🧪 Тестирование Post-Execution Pipeline")

# Upload section
uploaded_file = st.file_uploader("Загрузите подписанный договор", type=["pdf", "docx"])

col1, col2 = st.columns(2)
with col1:
    force_model = st.selectbox("Модель", ["Авто", "DeepSeek-V3", "Claude 4.5", "GPT-4o-mini"])
with col2:
    request_approval = st.checkbox("Требовать одобрение", value=True)

if st.button("🚀 Запустить обработку") and uploaded_file:
    with st.spinner("Обрабатываем документ..."):
        result = api_client.digitize_contract(
            file=uploaded_file,
            force_model=force_model if force_model != "Авто" else None,
            request_approval=request_approval
        )

    if result["status"] == "awaiting_approval":
        st.success("✅ Данные извлечены! Ожидается одобрение.")

        # Показываем извлеченные данные
        st.subheader("📊 Извлеченные данные")
        st.json(result["preview"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Одобрить"):
                api_client.approve(result["approval_id"])
                st.success("Данные сохранены в БД!")
        with col2:
            if st.button("❌ Отклонить"):
                reason = st.text_input("Причина отклонения")
                api_client.reject(result["approval_id"], reason)
                st.warning("Отклонено")

    elif result["status"] == "completed":
        st.success(f"✅ Документ обработан! ID: {result['contract_id']}")

# Секция: RAG Context
st.subheader("🔍 RAG Context (похожие документы)")
if uploaded_file:
    similar = api_client.get_similar_contracts(uploaded_file)
    for doc in similar:
        st.info(f"📄 {doc['doc_number']} - Similarity: {doc['score']:.2f}")
```

### 1.5-1.7 (аналогично оригинальному плану, но с добавлением RAG и approval flow)

---

## ✅ Критерии завершения Stage 1

- [ ] Endpoint `/contracts/digitize` работает с PDF и DOCX
- [ ] Level 1 Extractor извлекает базовые данные
- [ ] RAG Service находит похожие документы и предоставляет контекст
- [ ] LLM Client использует контекст из RAG для улучшения извлечения
- [ ] ApprovalService создает запросы на одобрение
- [ ] **UI тестирования:** Streamlit страница позволяет загрузить документ, увидеть результат и одобрить/отклонить
- [ ] Данные сохраняются в БД только после одобрения
- [ ] Интеграционные тесты проходят для 3+ типов документов
- [ ] Стоимость обработки документа < $0.05 (через DeepSeek)

**Время на тестирование:** 3 дня
**Общее время Stage 1:** 4 недели

---

# Stage 2: Pre-Execution (Недели 7-10)

**Цель:** Создать систему анализа черновиков с рекомендациями, а не только расхождениями.

## Задачи

### 2.1-2.5 (аналогично оригинальному плану)

### 2.6 AI Recommendations Engine (Неделя 9, День 1-3) - НОВОЕ

**Файл:** `src/services/recommendations_engine.py`

```python
class RecommendationsEngine:
    def __init__(self, llm_client: LLMClient, rag_service: RAGService):
        self.llm = llm_client
        self.rag = rag_service

    async def generate_recommendations(
        self,
        disagreements: List[Disagreement],
        context: Dict
    ) -> List[Dict]:
        """
        Генерация рекомендаций для текущей ситуации.

        Не только "что не так", но и "что делать".
        """
        recommendations = []

        for disagreement in disagreements:
            # RAG: Поиск похожих кейсов
            similar_cases = await self.rag.retrieve_context(
                query=disagreement.their_clause,
                context_type="precedent",
                top_k=3
            )

            # LLM: Генерация рекомендации с учетом контекста
            prompt = f"""
            Ситуация: Контрагент предложил условие: "{disagreement.their_clause}"
            Наш стандарт: "{disagreement.our_standard}"
            Уровень риска: {disagreement.risk_level}

            Похожие прецеденты:
            {self._format_precedents(similar_cases)}

            Задача: Предложи конкретные действия и аргументы для переговоров.
            """

            recommendation = await self.llm.generate(
                prompt=prompt,
                model="gpt-4o-mini"  # Дешевая модель для рекомендаций
            )

            recommendations.append({
                "disagreement_id": disagreement.id,
                "recommendation": recommendation,
                "precedents": similar_cases,
                "suggested_actions": [
                    "Настаивать на нашей формулировке",
                    "Компромисс: добавить ограничение суммы",
                    "Согласиться, если добавят пункт X"
                ]
            })

        return recommendations
```

### 2.7 Обновленный endpoint с рекомендациями (Неделя 9, День 3-5)

```python
@router.get("/api/v1/negotiation/{session_id}/analysis")
async def get_negotiation_analysis(session_id: UUID):
    """
    Получить полный анализ: расхождения + рекомендации + прецеденты.

    Returns:
        {
            "disagreements": [...],
            "ai_recommendations": [...],  # НОВОЕ
            "overall_risk_score": 0.65,
            "status": "awaiting_approval"  # НОВОЕ
        }
    """
```

### 2.8 UI для тестирования Stage 2 (Неделя 10) - НОВОЕ

**Файл:** `admin/pages/2_Test_Pre_Execution.py`

```python
st.title("🧪 Тестирование Pre-Execution (Анализ черновиков)")

uploaded_draft = st.file_uploader("Загрузите черновик от контрагента", type=["pdf", "docx"])
template = st.selectbox("Выберите шаблон для сравнения", ["Договор поставки (стандарт)", "Договор услуг", "Агентский договор"])

if st.button("🔍 Анализировать") and uploaded_draft:
    with st.spinner("Анализируем черновик..."):
        result = api_client.analyze_draft(uploaded_draft, template)

    st.metric("Общий риск", f"{result['overall_risk_score']:.0%}",
              delta=f"{result['risk_level']}", delta_color="inverse")

    # Расхождения
    st.subheader("⚠️ Расхождения")
    for d in result["disagreements"]:
        with st.expander(f"{d['section']} - {d['risk_level'].upper()}"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Их формулировка:**")
                st.text(d["their_clause"])
            with col2:
                st.markdown("**Наш стандарт:**")
                st.text(d["our_standard"])

            st.markdown("**Предлагаемая формулировка:**")
            st.info(d["suggested_wording"])

    # Рекомендации (НОВОЕ)
    st.subheader("💡 Рекомендации системы")
    for rec in result["ai_recommendations"]:
        st.success(rec["recommendation"])

        st.markdown("**Возможные действия:**")
        for action in rec["suggested_actions"]:
            st.checkbox(action, key=action)

    # Прецеденты
    st.subheader("📚 Похожие прецеденты")
    for prec in result["precedents"]:
        st.info(f"Договор {prec['doc_number']}: {prec['outcome']}")

    # Одобрение протокола
    st.subheader("✅ Одобрение протокола разногласий")
    if st.button("Сгенерировать протокол разногласий"):
        protocol = api_client.generate_protocol(result["session_id"])
        st.download_button("📥 Скачать DOCX", protocol, "protocol.docx")

        if st.button("✅ Одобрить и отправить контрагенту"):
            api_client.approve_protocol(result["session_id"])
            st.success("Протокол одобрен!")
```

---

## ✅ Критерии завершения Stage 2

- [ ] Система шаблонов работает
- [ ] ClauseComparator находит расхождения
- [ ] RiskScorer правильно оценивает уровень риска
- [ ] **RecommendationsEngine генерирует рекомендации с учетом прецедентов (RAG)**
- [ ] **UI тестирования:** Streamlit страница показывает расхождения + рекомендации + прецеденты
- [ ] Экспорт в DOCX с комментариями работает
- [ ] **Протокол разногласий генерируется только после одобрения пользователем**
- [ ] Интеграционные тесты покрывают все сценарии

**Время на тестирование:** 2 дня
**Общее время Stage 2:** 4 недели

---

# Stage 3: Smart Router Production (Недели 11-14)

(Аналогично оригинальному плану + UI тестирования)

### 3.7 UI для тестирования Stage 3 (Неделя 14) - НОВОЕ

**Файл:** `admin/pages/3_Test_Model_Router.py`

```python
st.title("🧪 Тестирование Smart Model Router")

st.subheader("🔬 A/B тестирование моделей")

uploaded_test_doc = st.file_uploader("Загрузите тестовый документ", type=["pdf"])

if uploaded_test_doc:
    st.info("Запускаем обработку через ВСЕ модели для сравнения...")

    results = {}
    for model in ["deepseek-v3", "claude-4-5-sonnet", "gpt-4o", "gpt-4o-mini"]:
        with st.spinner(f"Обработка через {model}..."):
            result = api_client.digitize_contract(uploaded_test_doc, force_model=model)
            results[model] = result

    # Сравнительная таблица
    comparison_df = pd.DataFrame({
        "Модель": results.keys(),
        "Стоимость": [r["cost"] for r in results.values()],
        "Время (сек)": [r["time"] for r in results.values()],
        "Confidence": [r["confidence"] for r in results.values()],
        "Точность": [r["accuracy"] for r in results.values()]
    })

    st.dataframe(comparison_df)

    st.subheader("📊 Визуализация")
    st.bar_chart(comparison_df.set_index("Модель")["Стоимость"])
```

---

# Stage 4: Интеграции + UI (Недели 15-20)

### 4.7 Unified Admin Console (Неделя 19-20) - НОВОЕ

**Файл:** `admin/streamlit_main.py`

```python
st.set_page_config(page_title="Contract AI Admin Console", layout="wide")

# Главная страница с максимумом показателей
st.title("📊 Contract AI System - Admin Console")

# Row 1: Ключевые метрики
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Документов сегодня", "47", "+8")
with col2:
    st.metric("Стоимость/док", "$0.019", "-91%")
with col3:
    st.metric("Средний Confidence", "94.2%", "+1.2%")
with col4:
    st.metric("Ожидают одобрения", "3", "⚠️")
with col5:
    st.metric("Активных договоров", "1,842", "+23")

# Row 2: Графики
col1, col2 = st.columns(2)
with col1:
    st.subheader("📈 Обработка документов по дням")
    # Line chart
with col2:
    st.subheader("🤖 Использование моделей")
    # Pie chart: DeepSeek 87% | Claude 10% | GPT-4o 3%

# Row 3: Режим работы системы
st.subheader("⚙️ Текущий режим работы")
current_mode = api_client.get_system_mode()
st.info(f"Режим: {current_mode}")

new_mode = st.selectbox("Изменить режим", ["Полная нагрузка", "Последовательный", "Ручной"])
if new_mode != current_mode:
    if st.button("Применить"):
        api_client.set_system_mode(new_mode)
        st.success("Режим изменен!")

if new_mode == "Ручной":
    enabled_modules = st.multiselect(
        "Включенные модули",
        ["OCR", "Level1 Extraction", "LLM Extraction", "RAG Filter", "Validation"],
        default=["OCR", "LLM Extraction"]
    )
    if st.button("Сохранить модули"):
        api_client.set_enabled_modules(enabled_modules)

# Row 4: Ожидают одобрения
st.subheader("⏳ Документы, ожидающие одобрения")
pending = api_client.get_pending_approvals()
for item in pending:
    with st.expander(f"{item['entity_type']}: {item['doc_number']}"):
        st.json(item["data_preview"])
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Одобрить", key=f"approve_{item['id']}"):
                api_client.approve(item['id'])
                st.rerun()
        with col2:
            if st.button("❌ Отклонить", key=f"reject_{item['id']}"):
                api_client.reject(item['id'])
                st.rerun()

# Row 5: RAG Statistics
st.subheader("🔍 RAG Statistics")
rag_stats = api_client.get_rag_stats()
st.metric("Документов в векторной базе", rag_stats["total_docs"])
st.metric("Средний Similarity Score", f"{rag_stats['avg_similarity']:.2f}")

# Row 6: LLM Usage Breakdown
st.subheader("💰 Детализация использования LLM")
llm_usage = api_client.get_llm_usage_breakdown()
st.dataframe(llm_usage)
```

---

## ✅ Критерии завершения Stage 4

- [ ] Amendment flow работает
- [ ] Векторный поиск работает
- [ ] Интеграция с 1C работает
- [ ] **Unified Admin Console (Streamlit) с максимумом показателей**
- [ ] **Настройка режимов работы через UI**
- [ ] **UI тестирования для каждого модуля**
- [ ] Мониторинг сроков работает
- [ ] End-to-End тесты проходят
- [ ] Документация готова

**Время на тестирование:** 3 дня
**Общее время Stage 4:** 6 недель

---

# 📊 Резюме ОБНОВЛЕННОГО плана

## Ключевые дополнения

1. **GPT-4o-mini** для тестирования и валидации
2. **UI тестирования** для КАЖДОГО Stage (обязательное требование)
3. **Человек в цикле:** Approval flow на всех критичных операциях
4. **Рекомендации + Расхождения:** Система не только находит проблемы, но и предлагает решения
5. **RAG на каждом этапе:** Контекстная фильтрация для повышения точности
6. **Режимы работы:** Полная нагрузка / Последовательный / Ручной (настройка через UI)
7. **Unified Admin Console:** Streamlit dashboard с максимумом метрик

## Почему SQLAlchemy?

- **Безопасность:** Защита от SQL injection
- **Производительность:** Ленивая загрузка, кеширование запросов
- **Миграции:** Alembic для версионирования схемы БД
- **Type Safety:** Типизированные модели, автодополнение в IDE
- **Простота:** Работа с БД через Python объекты вместо сырого SQL
- **ORM Relationships:** Автоматическое управление связями (ForeignKey, One-to-Many)

## Таблица с новыми сущностями

| Таблица | Назначение |
|---------|-----------|
| `system_config` | Хранение режима работы и конфигурации модулей |
| `user_approvals` | Отслеживание одобрений пользователя |
| `knowledge_base` | RAG: база знаний (best practices, regulations, precedents) |
| `disagreements.ai_recommendation` | Рекомендации системы для конкретного расхождения |
| `negotiation_sessions.ai_recommendations` | Общие рекомендации для сессии переговоров |

---

**Готовы начинать Stage 0?** 🚀
