"""
Contract AI System v2.0 - Streamlit Admin Dashboard
Main admin console with system metrics and configuration
"""
import streamlit as st
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Page configuration
st.set_page_config(
    page_title="Админка Contract AI - v2.0",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .status-success {
        color: #28a745;
        font-weight: bold;
    }
    .status-warning {
        color: #ffc107;
        font-weight: bold;
    }
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("⚙️ Contract AI v2.0")
    st.markdown("---")

    # System Status
    st.subheader("🔌 Статус системы")
    st.success("✅ Онлайн")
    st.metric("Аптайм", "12ч 34м")

    st.markdown("---")

    # Navigation
    st.subheader("📂 Навигация")
    page = st.radio(
        "Перейти к:",
        ["Главная", "Настройки системы", "Метрики LLM", "Статистика RAG", "Тест подключений"],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.caption("Contract AI System v2.0")
    st.caption("Мульти-модельная маршрутизация | RAG | Human-in-the-Loop")

# Main content area
if page == "Главная":
    # Header
    st.markdown('<div class="main-header">📊 Панель управления</div>', unsafe_allow_html=True)

    # Row 1: Key Metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="📄 Документов сегодня",
            value="47",
            delta="+8",
            help="Обработано документов сегодня"
        )

    with col2:
        st.metric(
            label="💰 Стоимость/док",
            value="$0.019",
            delta="-91%",
            delta_color="inverse",
            help="Средняя стоимость за документ"
        )

    with col3:
        st.metric(
            label="🎯 Уверенность",
            value="94.2%",
            delta="+1.2%",
            help="Средний балл уверенности"
        )

    with col4:
        st.metric(
            label="⏳ Ожидает подтверждения",
            value="3",
            delta="",
            help="Документов в очереди на утверждение"
        )

    with col5:
        st.metric(
            label="📑 Активных договоров",
            value="1,842",
            delta="+23",
            help="Всего активных договоров"
        )

    st.markdown("---")

    # Row 2: Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Объём обработки (последние 7 дней)")
        # Placeholder for chart
        st.line_chart({
            "Пн": 35, "Вт": 42, "Ср": 38, "Чт": 45,
            "Пт": 52, "Сб": 28, "Вс": 47
        })

    with col2:
        st.subheader("🤖 Распределение использования моделей")
        # Placeholder for pie chart
        model_data = {
            "DeepSeek-V3": 87,
            "Claude 4.5": 10,
            "GPT-4o": 3
        }
        st.bar_chart(model_data)

    st.markdown("---")

    # Row 3: Current System Mode
    st.subheader("⚙️ Текущая конфигурация системы")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.info("**Режим системы:** Полная загрузка")
        st.caption("Все модули работают параллельно")

    with col2:
        st.info("**Модель по умолчанию:** DeepSeek-V3")
        st.caption("Основная модель для оптимизации затрат")

    with col3:
        st.info("**Статус RAG:** Включен")
        st.caption("Top-K: 5, Порог: 0.7")

    st.markdown("---")

    # Row 4: Recent Activity
    st.subheader("📋 Последняя активность")

    activity_data = [
        {"Время": "10:42", "Событие": "Документ оцифрован", "Детали": "Договор #2453", "Статус": "✅ Успешно"},
        {"Время": "10:38", "Событие": "Переговоры проанализированы", "Детали": "Сессия #891", "Статус": "⏳ Ожидает подтверждения"},
        {"Время": "10:35", "Событие": "Смена модели", "Детали": "DeepSeek → Claude (сложность: 0.85)", "Статус": "✅ Успешно"},
        {"Время": "10:30", "Событие": "RAG запрос", "Детали": "Найдено 5 прецедентов", "Статус": "✅ Успешно"},
        {"Время": "10:25", "Событие": "Протокол сформирован", "Детали": "12 разногласий", "Статус": "⏳ Ожидает подтверждения"},
    ]

    st.dataframe(activity_data, use_container_width=True)

elif page == "Настройки системы":
    st.markdown('<div class="main-header">⚙️ Настройки системы</div>', unsafe_allow_html=True)

    st.warning("⚠️ Изменения конфигурации требуют перезапуска системы")

    # System Mode
    st.subheader("🔧 Режим работы системы")

    current_mode = st.selectbox(
        "Выберите режим",
        ["Полная загрузка (Параллельно)", "Последовательный (Экономия)", "Ручной (Настраиваемый)"],
        help="Полная загрузка: Все модули работают параллельно (быстрее всего)\n"
             "Последовательный: Модули работают по очереди (экономия)\n"
             "Ручной: Выберите, какие модули включить"
    )

    if current_mode == "Ручной (Настраиваемый)":
        st.multiselect(
            "Включенные модули",
            ["OCR", "Извлечение Level1", "LLM извлечение", "RAG фильтр", "Валидация", "Генерация эмбеддингов"],
            default=["OCR", "LLM извлечение", "Валидация"]
        )

    if st.button("💾 Применить режим системы"):
        st.success("✅ Режим системы обновлён!")

    st.markdown("---")

    # Smart Router Config
    st.subheader("🤖 Конфигурация умного роутера")

    col1, col2 = st.columns(2)

    with col1:
        default_model = st.selectbox(
            "Модель по умолчанию",
            ["DeepSeek-V3", "Claude 4.5 Sonnet", "GPT-4o", "GPT-4o-mini"]
        )

    with col2:
        complexity_threshold = st.slider(
            "Порог сложности",
            min_value=0.0,
            max_value=1.0,
            value=0.8,
            step=0.05,
            help="Порог для переключения на Claude (выше = более избирательно)"
        )

    enable_fallback = st.checkbox("Включить резервный механизм", value=True)

    if st.button("💾 Применить настройки роутера"):
        st.success("✅ Конфигурация роутера обновлена!")

    st.markdown("---")

    # RAG Config
    st.subheader("🔍 Конфигурация RAG")

    col1, col2, col3 = st.columns(3)

    with col1:
        rag_enabled = st.checkbox("Включить RAG", value=True)

    with col2:
        rag_top_k = st.number_input("Количество результатов Top-K", min_value=1, max_value=20, value=5)

    with col3:
        rag_threshold = st.slider(
            "Порог схожести",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.05
        )

    if st.button("💾 Применить настройки RAG"):
        st.success("✅ Конфигурация RAG обновлена!")

elif page == "Метрики LLM":
    st.markdown('<div class="main-header">📊 Метрики использования LLM</div>', unsafe_allow_html=True)

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        date_range = st.date_input("Диапазон дат", value=[])

    with col2:
        model_filter = st.multiselect(
            "Модели",
            ["DeepSeek-V3", "Claude 4.5", "GPT-4o", "GPT-4o-mini"],
            default=["DeepSeek-V3", "Claude 4.5"]
        )

    with col3:
        status_filter = st.selectbox("Статус", ["Все", "Успешно", "Ошибка", "Частично"])

    st.markdown("---")

    # Metrics Table
    st.subheader("📋 Последние запросы к LLM")

    metrics_data = [
        {
            "Время": "2026-01-09 10:42:15",
            "Модель": "DeepSeek-V3",
            "Документ": "Договор #2453",
            "Токены (Вход/Выход)": "1,234 / 567",
            "Стоимость": "$0.00028",
            "Время (сек)": "1.8",
            "Уверенность": "0.95",
            "Статус": "✅ Успешно"
        },
        {
            "Время": "2026-01-09 10:38:22",
            "Модель": "Claude 4.5",
            "Документ": "Договор #2452",
            "Токены (Вход/Выход)": "2,456 / 892",
            "Стоимость": "$0.02058",
            "Время (сек)": "3.2",
            "Уверенность": "0.97",
            "Статус": "✅ Успешно"
        },
        {
            "Время": "2026-01-09 10:35:10",
            "Модель": "DeepSeek-V3",
            "Документ": "Сессия #891",
            "Токены (Вход/Выход)": "980 / 423",
            "Стоимость": "$0.00020",
            "Время (сек)": "1.5",
            "Уверенность": "0.89",
            "Статус": "⚠️ Резерв использован"
        },
    ]

    st.dataframe(metrics_data, use_container_width=True)

    st.markdown("---")

    # Cost Breakdown
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💰 Затраты по моделям (последние 30 дней)")
        cost_data = {
            "DeepSeek-V3": 12.45,
            "Claude 4.5": 38.92,
            "GPT-4o": 4.23,
            "GPT-4o-mini": 0.87
        }
        st.bar_chart(cost_data)

    with col2:
        st.subheader("📊 Количество запросов по моделям")
        request_data = {
            "DeepSeek-V3": 1250,
            "Claude 4.5": 145,
            "GPT-4o": 42,
            "GPT-4o-mini": 85
        }
        st.bar_chart(request_data)

elif page == "Статистика RAG":
    st.markdown('<div class="main-header">🔍 Статистика RAG</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("📚 Записей в базе знаний", "247")

    with col2:
        st.metric("🔍 Запросов сегодня", "184")

    with col3:
        st.metric("📊 Средний балл схожести", "0.82")

    st.markdown("---")

    # Most Used Knowledge
    st.subheader("📖 Наиболее используемые знания")

    knowledge_data = [
        {"Название": "Ограничение ответственности в договорах поставки", "Тип": "best_practice", "Использований": 47},
        {"Название": "Стандартная формулировка штрафа", "Тип": "template_clause", "Использований": 38},
        {"Название": "Компромисс по предоплате", "Тип": "negotiation_tactic", "Использований": 25},
        {"Название": "Иностранная подсудность", "Тип": "risk_pattern", "Использований": 19},
    ]

    st.dataframe(knowledge_data, use_container_width=True)

    st.markdown("---")

    # Add New Knowledge
    st.subheader("➕ Добавить новую запись")

    with st.form("add_knowledge"):
        col1, col2 = st.columns(2)

        with col1:
            title = st.text_input("Название")
            content_type = st.selectbox(
                "Тип",
                ["best_practice", "regulation", "precedent", "template_clause", "risk_pattern", "negotiation_tactic"]
            )

        with col2:
            source = st.text_input("Источник (необязательно)")

        content = st.text_area("Содержание", height=150)

        submitted = st.form_submit_button("💾 Добавить запись")

        if submitted:
            st.success("✅ Запись добавлена!")

elif page == "Тест подключений":
    st.markdown('<div class="main-header">🔌 Тест API подключений</div>', unsafe_allow_html=True)

    st.info("Тестирование подключения ко всем настроенным LLM API")

    if st.button("🚀 Запустить тесты подключений"):
        with st.spinner("Тестирование подключений..."):
            import time

            # Simulate API tests
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.markdown("### DeepSeek-V3")
                time.sleep(0.5)
                st.success("✅ Подключено")
                st.caption("Время ответа: 150мс")

            with col2:
                st.markdown("### Claude 4.5")
                time.sleep(0.5)
                st.success("✅ Подключено")
                st.caption("Время ответа: 220мс")

            with col3:
                st.markdown("### GPT-4o")
                time.sleep(0.5)
                st.success("✅ Подключено")
                st.caption("Время ответа: 180мс")

            with col4:
                st.markdown("### GPT-4o-mini")
                time.sleep(0.5)
                st.success("✅ Подключено")
                st.caption("Время ответа: 120мс")

        st.success("🎉 Все API успешно подключены!")

    st.markdown("---")

    # Configuration Preview
    st.subheader("📋 Просмотр конфигурации")

    config_preview = """
    Модель по умолчанию: DeepSeek-V3
    Порог сложности: 0.8
    RAG включен: Да
    RAG Top-K: 5
    Резервный механизм: Включен
    """

    st.code(config_preview)

# Footer
st.markdown("---")
st.caption("Contract AI System v2.0 | Мульти-модельная маршрутизация | Создано с помощью Streamlit")
