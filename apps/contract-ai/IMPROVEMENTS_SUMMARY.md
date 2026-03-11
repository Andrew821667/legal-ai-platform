# 📋 ПЛАН УЛУЧШЕНИЙ CONTRACT AI SYSTEM

## ✅ РЕАЛИЗОВАНО

### 1. Система аутентификации и ролей ✅
**Файл:** `src/utils/auth.py`

**Роли пользователей:**
- **DEMO** - ограниченный функционал (3 договора/день, без PDF)
- **FULL** - полный функционал (50 договоров/день)
- **VIP** - расширенный (1000 договоров/день, приоритет)
- **ADMIN** - безлимит + управление

**Функции:**
- `login_user()` - авторизация
- `logout_user()` - выход
- `check_feature_access()` - проверка доступа к функциям
- `show_upgrade_message()` - сообщение об апгрейде
- Демо-пользователи создаются автоматически

**Тестовые аккаунты:**
- demo@example.com (DEMO)
- user@example.com (FULL)
- vip@example.com (VIP)
- admin@example.com (ADMIN)

---

### 2. Типы договоров на русском ✅
**Файл:** `src/utils/contract_types.py`

**20 типов договоров:**
- Договор поставки
- Договор оказания услуг
- Договор аренды
- Договор купли-продажи
- Соглашение о конфиденциальности (NDA)
- Трудовой договор
- Договор подряда
- И другие...

**Категории:**
- Торговые
- Услуги
- Недвижимость
- Финансовые
- Интеллектуальная собственность
- Трудовые
- Корпоративные

**Функции:**
- `get_contract_type_name()` - получить русское название
- `get_contracts_by_category()` - договоры по категории
- `get_all_contract_types()` - все типы

---

### 3. База знаний с категориями ✅
**Файл:** `src/utils/knowledge_base.py`

**5 категорий:**
1. 📄 **Формы договоров** - типовые формы и шаблоны
2. ⚖️ **Нормативная база** - ГК РФ, законы
3. 🏛️ **Судебная практика** - решения ВС РФ, постановления
4. ⭐ **Ключевые кейсы** - важные прецеденты
5. 📈 **Актуальные тенденции** - изменения законодательства

**Класс KnowledgeBaseManager:**
- `list_documents()` - список документов в категории
- `search_in_category()` - поиск в категории
- `search_all_categories()` - поиск по всем
- `add_document()` - добавить документ
- `get_category_statistics()` - статистика

**Структура:**
```
data/knowledge_base/
├── forms/          # Формы договоров
├── legal/          # Нормативная база
├── case_law/       # Судебная практика
├── key_cases/      # Ключевые кейсы
└── trends/         # Актуальные тенденции
```

---

## 📝 ТРЕБУЕТСЯ РЕАЛИЗОВАТЬ

### 4. Обработка ошибок с LLM fallback ⏳
**Когда шаблон не найден:**
```python
if template_not_found:
    # Предложить генерацию с помощью LLM
    st.warning("Шаблон не найден")
    if st.button("Создать договор с помощью AI"):
        # Использовать LLM для генерации с нуля
        llm_gateway.generate_contract_from_scratch(params)
```

**Требуется:**
- Добавить функцию `generate_contract_from_scratch()` в LLMGateway
- Создать промпт для генерации договора без шаблона
- Обработка ошибок в каждом агенте

---

### 5. Улучшенный UI генератора договоров ⏳

**Убрать:**
- ❌ Поле "ID пользователя" (использовать из session)
- ❌ Поле "ID шаблона" (сделать опциональным в expander)

**Добавить:**

#### A. Расширенная информация о сторонах
```python
with st.expander("📋 Сторона 1: Поставщик"):
    party1_type = st.selectbox("Тип", ["ЮЛ", "ИП", "Физлицо"])
    party1_name = st.text_input("Наименование")
    party1_inn = st.text_input("ИНН")
    party1_kpp = st.text_input("КПП")
    party1_ogrn = st.text_input("ОГРН")
    party1_address = st.text_area("Юр. адрес")
    party1_bank = st.text_input("Банк")
    party1_bik = st.text_input("БИК")
    party1_account = st.text_input("Расчётный счёт")
    party1_corr_account = st.text_input("Корр. счёт")
    party1_director = st.text_input("Директор (ФИО)")
    party1_basis = st.text_input("Действует на основании")
```

#### B. Расширенные условия договора
```python
st.subheader("📅 Сроки")
start_date = st.date_input("Дата начала")
end_date = st.date_input("Дата окончания")
duration = st.number_input("Срок действия (мес.)")
auto_renewal = st.checkbox("Автопролонгация")

st.subheader("💰 Финансовые условия")
total_amount = st.number_input("Сумма договора")
currency = st.selectbox("Валюта", ["RUB", "USD", "EUR"])
vat_included = st.checkbox("НДС включен")
payment_terms = st.number_input("Срок оплаты (дней)")
payment_method = st.selectbox("Способ оплаты", ["Безналичный", "Наличный"])
prepayment = st.number_input("Аванс (%)", 0, 100)

st.subheader("⚠️ Ответственность")
penalty_rate = st.number_input("Пеня за просрочку (% в день)", 0.0, 1.0, 0.1)
max_penalty = st.number_input("Максимальная неустойка (% от суммы)", 0, 100, 10)
liability_limit = st.number_input("Лимит ответственности")

st.subheader("📦 Условия поставки")
delivery_method = st.selectbox("Способ доставки", ["Самовывоз", "Доставка продавцом", "ТК"])
delivery_address = st.text_input("Адрес доставки")
delivery_terms = st.selectbox("Условия", ["EXW", "FCA", "DAP", "DDP"])

st.subheader("✍️ Подписание")
signature_method = st.selectbox("Способ подписания", ["Бумажный", "ЭЦП", "СМС-код"])
signatory_1 = st.text_input("Подписант от стороны 1")
signatory_2 = st.text_input("Подписант от стороны 2")
```

---

### 6. XML Export ⏳
**Добавить в Quick Export Agent:**
```python
def export_to_xml(self, contract_data: dict) -> str:
    """Экспорт в XML"""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <contract>
        <metadata>
            <id>{id}</id>
            <type>{type}</type>
            <date>{date}</date>
        </metadata>
        <parties>...</parties>
        <terms>...</terms>
        <clauses>...</clauses>
    </contract>
    """
    return xml_content
```

---

## 🔧 ТЕХНИЧЕСКИЕ ДЕТАЛИ

### Интеграция auth в app.py
```python
from src.utils.auth import (
    init_session_state as init_auth,
    show_user_info,
    get_current_user,
    check_feature_access,
    show_upgrade_message
)

# В начале app.py
def init_session_state():
    init_auth()  # Инициализация аутентификации
    # ... остальное

def sidebar_navigation():
    # ... меню
    show_user_info()  # Показать инфо о пользователе

# В page_generator():
def page_generator():
    # Проверка доступа
    if not check_feature_access('can_generate_contracts'):
        show_upgrade_message('Генерация договоров')
        return

    # ... остальной код
```

### Использование contract_types
```python
from src.utils.contract_types import (
    get_all_contract_names,
    get_contract_type_code,
    get_contracts_by_category,
    get_all_categories
)

# В UI:
contract_type_ru = st.selectbox(
    "Тип договора",
    get_all_contract_names()
)
contract_type_code = get_contract_type_code(contract_type_ru)
```

### Использование knowledge_base
```python
from src.utils.knowledge_base import (
    KnowledgeBaseManager,
    KnowledgeBaseCategory,
    initialize_knowledge_base
)

# Инициализация
kb_manager = initialize_knowledge_base()

# Поиск
results = kb_manager.search_in_category(
    KnowledgeBaseCategory.LEGAL,
    "договор поставки"
)

# Статистика
stats = kb_manager.get_category_statistics()
```

---

## 📊 ПРИОРИТЕТЫ

### Высокий приоритет:
1. ✅ Auth система
2. ✅ Русские названия договоров
3. ⏳ Убрать user_id из форм
4. ⏳ Расширить форму сторон договора
5. ⏳ Добавить условия договоров

### Средний приоритет:
6. ✅ База знаний по категориям
7. ⏳ XML export
8. ⏳ LLM fallback для отсутствующих шаблонов

### Низкий приоритет:
9. ⏳ Опциональный template_id (для advanced users)
10. ⏳ Интеграция RAG с категориями БЗ

---

## 🚀 СЛЕДУЮЩИЕ ШАГИ

1. Обновить `app.py`:
   - Добавить импорты auth, contract_types, knowledge_base
   - Интегрировать показ пользователя в sidebar
   - Убрать user_id из всех форм
   - Перевести типы договоров на русский

2. Обновить `page_generator()`:
   - Расширить форму сторон (expandable)
   - Добавить все условия договора
   - Сделать template_id опциональным

3. Обновить `QuickExportAgent`:
   - Добавить export_to_xml()

4. Создать `LLMContractGenerator`:
   - Генерация договора без шаблона
   - Обработка ошибок

5. Протестировать всё
6. Commit + Push

---

**Дата:** 13 октября 2025
**Статус:** В разработке
**Прогресс:** 30%
