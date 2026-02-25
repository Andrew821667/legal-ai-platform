# -*- coding: utf-8 -*-
"""
Streamlit UI for Contract AI System
"""
import streamlit as st
import os
import atexit
from datetime import datetime
from typing import Optional

# Configure page
st.set_page_config(
    page_title="Contract AI System",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import settings first
from config.settings import settings

# Configure Loguru для видимости логов в терминале
from loguru import logger
import sys

# Добавляем stdout handler для отображения логов в консоли
logger.remove()  # Удаляем дефолтный handler
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True
)
# Также сохраняем логи в файл
logger.add(
    "streamlit.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG"
)

logger.info("🚀 Contract AI System starting...")

# Import auth utilities
from src.utils.auth import (
    init_session_state as init_auth_state,
    show_user_info,
    show_login_form,
    get_current_user,
    check_feature_access,
    show_upgrade_message,
    create_demo_users
)
from src.utils.contract_types import (
    get_all_contract_names,
    get_contract_type_code,
    get_contracts_by_category,
    get_all_categories
)
from src.utils.knowledge_base import (
    KnowledgeBaseManager,
    KnowledgeBaseCategory,
    initialize_knowledge_base
)

# Import improved pages
from app_pages_improved import page_generator_improved, page_knowledge_base

# Import agents and services
try:
    from src.agents import (
        OrchestratorAgent,
        OnboardingAgent,
        ContractGeneratorAgent,
        ContractAnalyzerAgent,
        DisagreementProcessorAgent,
        ChangesAnalyzerAgent,
        QuickExportAgent
    )
    from src.services.llm_gateway import LLMGateway
    from src.models import SessionLocal
    AGENTS_AVAILABLE = True
except ImportError as e:
    st.error(f"Ошибка импорта: {e}")
    AGENTS_AVAILABLE = False


def cleanup_db_session():
    """Cleanup database session on exit to prevent memory leaks"""
    try:
        if 'db_session' in st.session_state:
            logger.info("Closing database session...")
            st.session_state.db_session.close()
            logger.info("Database session closed successfully")
    except Exception as e:
        logger.error(f"Error closing database session: {e}")


def init_session_state():
    """Initialize session state"""
    # Initialize auth state
    init_auth_state()

    # Initialize page state
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'

    # Initialize services
    if 'llm_gateway' not in st.session_state and AGENTS_AVAILABLE:
        from config.settings import settings
        st.session_state.llm_gateway = LLMGateway(model=settings.llm_quick_model)
    if 'db_session' not in st.session_state and AGENTS_AVAILABLE:
        st.session_state.db_session = SessionLocal()
        # Register cleanup handler for database session
        if 'db_cleanup_registered' not in st.session_state:
            atexit.register(cleanup_db_session)
            st.session_state.db_cleanup_registered = True

    # Initialize knowledge base
    if 'kb_manager' not in st.session_state:
        st.session_state.kb_manager = initialize_knowledge_base()

    # Create demo users on first run
    if 'demo_users_created' not in st.session_state:
        create_demo_users()
        st.session_state.demo_users_created = True


def sidebar_navigation():
    """Sidebar navigation"""
    st.sidebar.title("📄 Contract AI System")
    st.sidebar.markdown("---")

    pages = {
        'home': '🏠 Главная',
        'onboarding': '📥 Обработка запросов',
        'generator': '✍️ Генератор договоров',
        'analyzer': '🔍 Анализ договоров',
        'disagreements': '⚖️ Возражения',
        'changes': '📊 Анализ изменений',
        'export': '📤 Экспорт',
        'knowledge_base': '📚 База знаний',
        'settings': '⚙️ Настройки'
    }

    # Add logs page for admins
    if check_feature_access('can_view_logs'):
        pages['logs'] = '📋 Логи системы'

    for key, label in pages.items():
        if st.sidebar.button(label, key=f"nav_{key}"):
            st.session_state.current_page = key

    st.sidebar.markdown("---")

    # Show user info
    show_user_info()

    st.sidebar.markdown("---")
    st.sidebar.info(f"**Версия:** 1.0.0\n**LLM провайдер:** {settings.default_llm_provider}")


def page_home():
    """Home page"""
    st.title("🏠 Contract AI System")
    st.markdown("### Интеллектуальная система для автоматизации работы с договорами")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("**📥 Onboarding Agent**\n\nАнализ входящих запросов, классификация типов договоров, извлечение параметров")
    
    with col2:
        st.success("**✍️ Generator Agent**\n\nГенерация договоров по шаблонам XML с LLM-заполнением переменных")
    
    with col3:
        st.warning("**🔍 Analyzer Agent**\n\nАнализ договоров контрагентов, идентификация рисков, рекомендации")
    
    col4, col5, col6 = st.columns(3)
    
    with col4:
        st.error("**⚖️ Disagreement Agent**\n\nГенерация возражений с правовыми обоснованиями, экспорт в ЭДО")
    
    with col5:
        st.info("**📊 Changes Analyzer**\n\nСравнение версий договора, анализ влияния изменений")
    
    with col6:
        st.success("**📤 Quick Export**\n\nБыстрый экспорт в DOCX, PDF, TXT, JSON")
    
    st.markdown("---")
    st.markdown("**Статус системы:** ✅ Все агенты активны")


def page_onboarding():
    """Onboarding Agent page"""
    st.title("📥 Обработка входящих запросов")

    # Check access
    if not check_feature_access('can_use_onboarding'):
        show_upgrade_message('Обработка запросов')
        return

    user = get_current_user()
    user_id = user['id'] if user else 'demo_user'

    st.markdown("### Введите запрос пользователя")
    user_query = st.text_area(
        "Запрос",
        placeholder="Например: Нужен договор поставки товара на 500 000 рублей с ООО 'Поставщик'",
        height=150
    )
    
    if st.button("🚀 Обработать запрос", type="primary"):
        if not user_query:
            st.error("Введите запрос")
            return
        
        if not AGENTS_AVAILABLE:
            st.error("Агенты недоступны")
            return
        
        with st.spinner("Обработка запроса..."):
            try:
                agent = OnboardingAgent(
                    llm_gateway=st.session_state.llm_gateway,
                    db_session=st.session_state.db_session
                )
                
                result = agent.execute({
                    'user_query': user_query,
                    'user_id': user_id
                })
                
                if result.success:
                    st.success("✅ Запрос обработан")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("Классификация")
                        st.write(f"**Тип:** {result.data.get('contract_type', 'N/A')}")
                        st.write(f"**Действие:** {result.data.get('intent', 'N/A')}")
                    
                    with col2:
                        st.subheader("Параметры")
                        params = result.data.get('extracted_params', {})
                        for key, value in params.items():
                            st.write(f"**{key}:** {value}")
                    
                    if result.next_action:
                        st.info(f"**Рекомендуемое действие:** {result.next_action}")
                else:
                    st.error(f"Ошибка: {result.error}")
            
            except Exception as e:
                st.error(f"Ошибка: {e}")


def page_generator():
    """Generator Agent page"""
    st.title("✍️ Генератор договоров")
    
    st.markdown("### Генерация договора по шаблону")
    
    col1, col2 = st.columns(2)
    
    with col1:
        template_id = st.text_input("ID шаблона", value="tpl_supply_001")
        contract_type = st.selectbox(
            "Тип договора",
            ["supply", "service", "lease", "purchase", "confidentiality"]
        )
    
    with col2:
        party_a = st.text_input("Сторона A", value="ООО 'Компания'")
        party_b = st.text_input("Сторона B", value="ООО 'Контрагент'")
    
    amount = st.number_input("Сумма (руб)", min_value=0, value=100000)
    user_id = st.text_input("ID пользователя", value="user_001", key="gen_user")
    
    if st.button("🚀 Сгенерировать договор", type="primary"):
        if not AGENTS_AVAILABLE:
            st.error("Агенты недоступны")
            return
        
        with st.spinner("Генерация договора..."):
            try:
                agent = ContractGeneratorAgent(
                    llm_gateway=st.session_state.llm_gateway,
                    db_session=st.session_state.db_session
                )
                
                result = agent.execute({
                    'template_id': template_id,
                    'contract_type': contract_type,
                    'params': {
                        'party_a': party_a,
                        'party_b': party_b,
                        'amount': amount
                    },
                    'user_id': user_id
                })
                
                if result.success:
                    st.success("✅ Договор сгенерирован")
                    st.write(f"**Contract ID:** {result.data.get('contract_id')}")
                    st.write(f"**Путь к файлу:** {result.data.get('file_path')}")
                    
                    if result.data.get('validation_passed'):
                        st.success("✅ Валидация пройдена")
                    else:
                        st.warning("⚠️ Есть предупреждения валидации")
                else:
                    st.error(f"Ошибка: {result.error}")
            
            except Exception as e:
                st.error(f"Ошибка: {e}")


def page_analyzer():
    """Analyzer Agent page"""
    st.title("🔍 Анализ договоров")

    # Check access
    if not check_feature_access('can_analyze_contracts'):
        show_upgrade_message('Анализ договоров')
        return

    user = get_current_user()
    user_id = user['id'] if user else 'demo_user'

    st.markdown("### Анализ договора контрагента")

    uploaded_file = st.file_uploader("Загрузите договор", type=['docx', 'pdf', 'xml'])

    counterparty_tin = st.text_input("ИНН контрагента", value="7700000000")
    
    if st.button("🚀 Анализировать", type="primary"):
        if not uploaded_file:
            st.error("Загрузите файл")
            return
        
        if not AGENTS_AVAILABLE:
            st.error("Агенты недоступны")
            return
        
        with st.spinner("Анализ договора..."):
            try:
                from src.models import Contract
                from src.services.document_parser import DocumentParser
                from src.utils.file_validator import (
                    save_uploaded_file_securely,
                    FileValidationError
                )

                # Validate and save uploaded file securely
                try:
                    file_data = uploaded_file.getbuffer().tobytes()
                    file_path, safe_filename, file_size = save_uploaded_file_securely(
                        file_data=file_data,
                        filename=uploaded_file.name,
                        upload_dir="data/contracts"
                    )
                    st.success(f"✅ Файл загружен: {safe_filename} ({file_size / 1024:.1f} KB)")
                except FileValidationError as e:
                    st.error(f"❌ Ошибка валидации файла: {e}")
                    return

                # Parse document to XML
                st.info("📄 Парсинг документа...")
                parser = DocumentParser()
                parsed_xml = parser.parse(file_path)

                if not parsed_xml:
                    st.error("❌ Не удалось распарсить документ")
                    return

                # Create contract in database
                st.info("💾 Создание записи в БД...")
                contract = Contract(
                    file_name=safe_filename,
                    file_path=file_path,
                    document_type='contract',
                    contract_type='unknown',  # Will be determined by analyzer
                    status='pending',  # Valid values: pending, analyzing, reviewing, completed, error
                    assigned_to=user_id,
                    meta_info=parsed_xml  # Store XML in meta_info
                )
                st.session_state.db_session.add(contract)
                st.session_state.db_session.commit()
                st.session_state.db_session.refresh(contract)

                # Analyze contract
                # Update status to analyzing
                contract.status = 'analyzing'
                st.session_state.db_session.commit()

                # Создаем placeholder для прогресса
                progress_placeholder = st.empty()
                status_placeholder = st.empty()

                with status_placeholder.container():
                    st.info("🔍 **Начинаем анализ договора...**")
                    st.caption("⏳ Это может занять 10-30 секунд в зависимости от размера документа")

                agent = ContractAnalyzerAgent(
                    llm_gateway=st.session_state.llm_gateway,
                    db_session=st.session_state.db_session
                )

                # Показываем прогресс через progress bar
                progress_bar = progress_placeholder.progress(0)
                with status_placeholder.container():
                    st.info("🔍 **Извлечение структуры договора...**")
                progress_bar.progress(10)

                with status_placeholder.container():
                    st.info("🔍 **Анализ пунктов договора (батчинг по 5 пунктов)...**")
                    st.caption("📊 Используется gpt-4o-mini для быстрого анализа")
                progress_bar.progress(30)

                result = agent.execute({
                    'contract_id': contract.id,
                    'parsed_xml': parsed_xml,
                    'check_counterparty': True,
                    'metadata': {
                        'counterparty_tin': counterparty_tin,
                        'uploaded_by': user_id
                    }
                })

                progress_bar.progress(100)
                progress_placeholder.empty()  # Убираем прогресс-бар
                status_placeholder.empty()  # Убираем статус

                if result.success:
                    # Update status to completed
                    contract.status = 'completed'
                    st.session_state.db_session.commit()

                    st.success("✅ Анализ завершен успешно!")

                    # Get analysis data
                    analysis_id = result.data.get('analysis_id')
                    risks = result.data.get('risks', [])
                    recommendations = result.data.get('recommendations', [])
                    suggested_changes = result.data.get('suggested_changes', [])
                    annotations = result.data.get('annotations', [])
                    dispute_prediction = result.data.get('dispute_prediction', {})
                    counterparty_data = result.data.get('counterparty_data')
                    clause_analyses = result.data.get('clause_analyses', [])  # Детальный анализ пунктов

                    # === EXECUTIVE SUMMARY ===
                    st.markdown("---")
                    st.markdown("## 📊 Executive Summary")

                    # Подсчет рисков по критичности
                    critical_risks = sum(1 for r in risks if r.get('severity') in ['critical', 'high'])
                    medium_risks = sum(1 for r in risks if r.get('severity') == 'medium')
                    low_risks = sum(1 for r in risks if r.get('severity') == 'low')

                    # Подсчет рекомендаций по приоритету
                    critical_recs = sum(1 for r in recommendations if r.get('priority') in ['critical', 'high'])

                    # Средняя оценка пунктов
                    if clause_analyses:
                        avg_clarity = sum(c.get('clarity_score', 5) for c in clause_analyses) / len(clause_analyses)
                        avg_compliance = sum(c.get('legal_compliance', {}).get('score', 5) for c in clause_analyses) / len(clause_analyses)
                    else:
                        avg_clarity = 5
                        avg_compliance = 5

                    # Общая оценка
                    if critical_risks > 0:
                        risk_level = "🔴 КРИТИЧЕСКИЙ"
                        risk_color = "red"
                    elif medium_risks > 3 or critical_recs > 2:
                        risk_level = "🟡 ВЫСОКИЙ"
                        risk_color = "orange"
                    elif medium_risks > 0:
                        risk_level = "🟠 СРЕДНИЙ"
                        risk_color = "orange"
                    else:
                        risk_level = "🟢 НИЗКИЙ"
                        risk_color = "green"

                    # Отображение сводки
                    summary_col1, summary_col2 = st.columns([2, 1])

                    with summary_col1:
                        st.markdown(f"### Общая оценка: {risk_level}")
                        st.markdown(f"""
**Проанализировано пунктов:** {len(clause_analyses)}
**Средняя чёткость формулировок:** {avg_clarity:.1f}/10
**Среднее правовое соответствие:** {avg_compliance:.1f}/10
**Вероятность споров:** {dispute_prediction.get('level', 'N/A').upper()}
                        """)

                        # Ключевые проблемы
                        if critical_risks > 0:
                            st.warning(f"⚠️ **Обнаружено {critical_risks} критических риска(ов)!** Требуется срочная доработка договора.")
                        elif critical_recs > 0:
                            st.info(f"💡 Обнаружено {critical_recs} критически важных рекомендаций для улучшения договора.")

                    with summary_col2:
                        st.markdown("### 📈 Статистика")
                        st.metric("Всего рисков", len(risks), delta=None)
                        st.caption(f"🔴 Критических: {critical_risks}")
                        st.caption(f"🟡 Средних: {medium_risks}")
                        st.caption(f"🟢 Низких: {low_risks}")
                        st.metric("Рекомендаций", len(recommendations))
                        st.metric("Предложений изменений", len(suggested_changes))

                    # Топ-3 самых критичных проблем
                    if critical_risks > 0:
                        st.markdown("#### 🚨 Топ-3 критических риска:")
                        top_risks = [r for r in risks if r.get('severity') in ['critical', 'high']][:3]
                        for i, risk in enumerate(top_risks, 1):
                            st.markdown(f"**{i}.** {risk.get('title', 'Риск')} — {risk.get('description', '')[:100]}...")

                    st.markdown("---")
                    # === END EXECUTIVE SUMMARY ===

                    # Summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("📋 ID Анализа", f"...{analysis_id[-8:]}" if analysis_id else "N/A")
                    with col2:
                        st.metric("⚠️ Рисков найдено", len(risks))
                    with col3:
                        st.metric("💡 Рекомендаций", len(recommendations))
                    with col4:
                        st.metric("📑 Пунктов проанализировано", len(clause_analyses))

                    # Token usage and cost display
                    # Получаем статистику из агента (он использовал llm для анализа)
                    if agent and hasattr(agent, 'llm'):
                        try:
                            token_stats = agent.llm.get_token_stats()
                            
                            st.markdown("---")
                            st.markdown("### 💰 Использование токенов")
                            
                            col_t1, col_t2, col_t3, col_t4 = st.columns(4)
                            with col_t1:
                                st.metric("📥 Input токенов", f"{token_stats['input_tokens']:,}")
                            with col_t2:
                                st.metric("📤 Output токенов", f"{token_stats['output_tokens']:,}")
                            with col_t3:
                                st.metric("💵 Стоимость", f"${token_stats['total_cost_usd']:.4f}")
                            with col_t4:
                                st.metric("🤖 Модель", token_stats['model'])
                            
                            # Progress bar for cost visualization
                            cost = token_stats['total_cost_usd']
                            if cost < 0.01:
                                st.progress(min(cost / 0.01, 1.0))
                                st.caption(f"Расход: {cost / 0.01 * 100:.1f}% от $0.01")
                            else:
                                st.progress(min(cost / 0.10, 1.0))
                                st.caption(f"Расход: {cost / 0.10 * 100:.1f}% от $0.10")
                        except Exception as e:
                            st.warning(f"⚠️ Не удалось получить статистику токенов: {e}")

                    # Determine risk level from risks
                    high_risks = sum(1 for r in risks if r.get('severity') == 'high')
                    medium_risks = sum(1 for r in risks if r.get('severity') == 'medium')
                    low_risks = sum(1 for r in risks if r.get('severity') == 'low')

                    if high_risks > 0:
                        risk_level = 'КРИТИЧЕСКИЙ'
                        st.error(f"🔴 **Уровень риска:** {risk_level} ({high_risks} критичных рисков)")
                    elif medium_risks > 2:
                        risk_level = 'ВЫСОКИЙ'
                        st.warning(f"🟡 **Уровень риска:** {risk_level} ({medium_risks} средних рисков)")
                    elif medium_risks > 0:
                        risk_level = 'СРЕДНИЙ'
                        st.info(f"🟠 **Уровень риска:** {risk_level} ({medium_risks} средних, {low_risks} низких рисков)")
                    else:
                        risk_level = 'НИЗКИЙ'
                        st.success(f"🟢 **Уровень риска:** {risk_level} ({len(risks)} рисков обнаружено)")

                    st.markdown("---")

                    # Detailed results in tabs
                    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                        "📑 Анализ по пунктам",
                        "📊 Риски",
                        "💡 Рекомендации",
                        "✏️ Изменения",
                        "📝 Аннотации",
                        "📄 Полный отчёт"
                    ])

                    with tab1:
                        st.subheader("📑 Детальный анализ по каждому пункту договора")

                        if clause_analyses:
                            st.info(f"🔍 Проанализировано пунктов: **{len(clause_analyses)}**. Каждый пункт проверен через LLM на риски, соответствие законодательству и качество формулировки.")

                            for i, clause_analysis in enumerate(clause_analyses, 1):
                                clause_num = clause_analysis.get('clause_number', i)
                                clause_id = clause_analysis.get('clause_id', f'clause_{i}')

                                # Определяем приоритет по цвету
                                priority = clause_analysis.get('improvement_priority', 'medium')
                                priority_colors = {
                                    'critical': '🔴',
                                    'high': '🟡',
                                    'medium': '🟠',
                                    'low': '🟢'
                                }
                                priority_icon = priority_colors.get(priority, '⚪')

                                # Оценки
                                clarity_score = clause_analysis.get('clarity_score', 5)
                                legal_compliance = clause_analysis.get('legal_compliance', {})
                                legal_score = legal_compliance.get('score', 5)

                                # Заголовок с метриками
                                with st.expander(f"{priority_icon} **Пункт {clause_num}** | Чёткость: {clarity_score}/10 | Соответствие: {legal_score}/10", expanded=False):

                                    # Основная информация
                                    st.markdown("### 📋 Общая оценка")
                                    st.markdown(f"**Итоговая оценка:** {clause_analysis.get('overall_assessment', 'Не указана')}")
                                    st.markdown(f"**Приоритет улучшения:** {priority.upper()}")

                                    st.markdown("---")

                                    # Метрики в колонках
                                    col_a, col_b = st.columns(2)
                                    with col_a:
                                        st.metric("📝 Чёткость формулировки", f"{clarity_score}/10")
                                        st.caption(clause_analysis.get('clarity_assessment', 'Не указана'))
                                    with col_b:
                                        st.metric("⚖️ Правовое соответствие", f"{legal_score}/10")
                                        issues = legal_compliance.get('issues', [])
                                        if issues:
                                            st.caption(f"Проблем: {len(issues)}")
                                        else:
                                            st.caption("✅ Проблем не найдено")

                                    st.markdown("---")

                                    # Риски по пункту
                                    clause_risks = clause_analysis.get('risks', [])
                                    if clause_risks:
                                        st.markdown("### ⚠️ Риски в этом пункте")
                                        for j, risk in enumerate(clause_risks, 1):
                                            severity = risk.get('severity', 'minor')
                                            severity_icon = {"critical": "🔴", "significant": "🟡", "minor": "🟢"}.get(severity, "⚪")
                                            st.markdown(f"{severity_icon} **{j}. {risk.get('title', 'Риск')}** ({severity})")
                                            st.markdown(f"   - **Описание:** {risk.get('description', 'Нет описания')}")
                                            if risk.get('consequences'):
                                                st.markdown(f"   - **Последствия:** {risk.get('consequences')}")
                                            if risk.get('affected_party'):
                                                st.markdown(f"   - **Кто пострадает:** {risk.get('affected_party')}")
                                            st.markdown("")
                                    else:
                                        st.success("✅ Риски в этом пункте не обнаружены")

                                    st.markdown("---")

                                    # Рекомендации по пункту
                                    clause_recommendations = clause_analysis.get('recommendations', [])
                                    if clause_recommendations:
                                        st.markdown("### 💡 Рекомендации по улучшению")
                                        for j, rec in enumerate(clause_recommendations, 1):
                                            # Handle both string and dict recommendations
                                            if isinstance(rec, str):
                                                st.markdown(f"⚪ **{j}. {rec}**")
                                            elif isinstance(rec, dict):
                                                rec_priority = rec.get('priority', 'medium')
                                                rec_icon = priority_colors.get(rec_priority, '⚪')
                                                rec_title = rec.get('title', rec.get('recommendation', 'Рекомендация'))
                                                rec_desc = rec.get('description', rec.get('recommendation', ''))

                                                st.markdown(f"{rec_icon} **{j}. {rec_title}** ({rec_priority})")
                                                if rec_desc and rec_desc != rec_title:
                                                    st.markdown(f"   - **Описание:** {rec_desc}")
                                                if rec.get('reasoning'):
                                                    st.markdown(f"   - **Обоснование:** {rec.get('reasoning')}")
                                                if rec.get('expected_benefit'):
                                                    st.markdown(f"   - **Ожидаемая польза:** {rec.get('expected_benefit')}")
                                                if rec.get('category'):
                                                    category_ru = {
                                                        'legal_compliance': 'Правовое соответствие',
                                                        'risk_mitigation': 'Снижение рисков',
                                                        'financial_optimization': 'Финансовая оптимизация',
                                                        'clarity_improvement': 'Улучшение чёткости'
                                                    }.get(rec.get('category'), rec.get('category'))
                                                    st.caption(f"Категория: {category_ru}")
                                                if rec.get('suggested_text'):
                                                    st.markdown(f"   - **Предлагаемая формулировка:**")
                                                    st.code(rec.get('suggested_text'), language='text')
                                            st.markdown("")

                                    # Двусмысленности
                                    ambiguities = clause_analysis.get('ambiguities', [])
                                    if ambiguities:
                                        st.markdown("### ⚠️ Двусмысленности и неясности")
                                        for amb in ambiguities:
                                            st.markdown(f"- {amb}")

                                    # Недостающие элементы
                                    missing = clause_analysis.get('missing_elements', [])
                                    if missing:
                                        st.markdown("### ➕ Отсутствующие элементы")
                                        for miss in missing:
                                            st.markdown(f"- {miss}")

                                    # Правовые нормы
                                    relevant_laws = legal_compliance.get('relevant_laws', [])
                                    if relevant_laws:
                                        st.markdown("### 📚 Применимые правовые нормы")
                                        for law in relevant_laws:
                                            st.markdown(f"- {law}")

                                    # Прецеденты
                                    precedents = clause_analysis.get('precedents', [])
                                    if precedents:
                                        st.markdown("### ⚖️ Судебная практика")
                                        for prec in precedents:
                                            st.markdown(f"- {prec}")

                                    # Правовые проблемы
                                    if issues:
                                        st.markdown("### 🚨 Правовые проблемы")
                                        for issue in issues:
                                            st.error(f"⚠️ {issue}")

                        else:
                            st.warning("⚠️ Детальный анализ по пунктам не был выполнен. Возможно, использован упрощённый режим анализа.")
                            st.info("💡 Детальный анализ разбивает договор на отдельные пункты и проверяет каждый через LLM на риски, соответствие законодательству и качество формулировки.")

                        # Deep Analysis (Level 2) button
                        st.markdown("---")
                        st.markdown("### 🔬 Глубокий анализ (Уровень 2 - gpt-4o)")
                        st.info("Глубокий анализ использует модель **gpt-4o** для детальной экспертизы с судебными прецедентами, ссылками на законы и альтернативными формулировками. Стоимость: ~$0.01-0.05 за пункт.")
                        
                        if clause_analyses:
                            # Select clauses for deep analysis
                            clause_options = {f"Пункт {ca.get('clause_number', 'N/A')}: {ca.get('clause_title', '')[:50]}": ca.get('clause_number') 
                                            for ca in clause_analyses}
                            selected_clauses = st.multiselect(
                                "Выберите пункты для глубокого анализа",
                                options=list(clause_options.keys()),
                                help="Выберите 1-3 самых критичных пункта"
                            )
                            
                            if st.button("🚀 Запустить глубокий анализ", type="primary", disabled=len(selected_clauses) == 0):
                                if not AGENTS_AVAILABLE:
                                    st.error("Агенты недоступны")
                                else:
                                    with st.spinner(f"Выполняется глубокий анализ {len(selected_clauses)} пунктов с gpt-4o..."):
                                        try:
                                            clause_numbers = [clause_options[sc] for sc in selected_clauses]
                                            
                                            # Call deep analysis
                                            deep_results = agent.analyze_deep(
                                                clause_ids=clause_numbers,
                                                contract_id=contract.id,
                                                xml_content=parsed_xml,
                                                rag_context={}
                                            )
                                            
                                            # Display deep analysis results
                                            st.success(f"✅ Глубокий анализ завершён для {len(deep_results)} пунктов!")
                                            
                                            for deep_result in deep_results:
                                                clause_num = deep_result.get('clause_number')
                                                
                                                with st.expander(f"🔬 ГЛУБОКИЙ АНАЛИЗ - Пункт {clause_num}", expanded=True):
                                                    if 'error' in deep_result:
                                                        st.error(f"Ошибка: {deep_result['error']}")
                                                        continue
                                                    
                                                    # Summary
                                                    st.markdown(f"**Резюме:** {deep_result.get('summary', 'N/A')}")
                                                    st.metric("Общий балл риска", f"{deep_result.get('overall_risk_score', 0)}/100")
                                                    
                                                    # Legal analysis
                                                    legal = deep_result.get('deep_legal_analysis', {})
                                                    if legal:
                                                        st.markdown("#### ⚖️ Юридический анализ")
                                                        col1, col2 = st.columns(2)
                                                        with col1:
                                                            st.metric("Соответствие", f"{legal.get('compliance_score', 0)}/10")
                                                        with col2:
                                                            st.metric("Исполнимость", f"{legal.get('enforceability_score', 0)}/10")
                                                        
                                                        laws = legal.get('relevant_laws', [])
                                                        if laws:
                                                            st.markdown("**Применимые законы:**")
                                                            for law in laws:
                                                                st.markdown(f"- {law.get('law')} {law.get('article')}: {law.get('relevance')}")
                                                    
                                                    # Risks with precedents
                                                    risks = deep_result.get('risks_with_precedents', [])
                                                    if risks:
                                                        st.markdown("#### ⚠️ Риски с прецедентами")
                                                        for risk in risks:
                                                            st.markdown(f"**{risk.get('risk_type')}** ({risk.get('severity')})")
                                                            st.markdown(f"- Вероятность: {risk.get('probability_percent', 0)}%")
                                                            st.markdown(f"- Финансовое влияние: {risk.get('financial_impact_range', 'N/A')}")
                                                            
                                                            precedents = risk.get('precedents', [])
                                                            if precedents:
                                                                st.markdown("**Прецеденты:**")
                                                                for prec in precedents:
                                                                    st.info(f"📋 {prec.get('case_number')} ({prec.get('court')}, {prec.get('date')})")
                                                    
                                                    # Alternative formulations
                                                    alts = deep_result.get('alternative_formulations', [])
                                                    if alts:
                                                        st.markdown("#### 💡 Альтернативные формулировки")
                                                        for alt in alts:
                                                            st.markdown(f"**Вариант {alt.get('variant_number')}:**")
                                                            st.code(alt.get('formulation', ''), language='text')
                                                            st.caption(f"Обоснование: {alt.get('legal_basis', '')}")
                                        
                                        except Exception as e:
                                            st.error(f"Ошибка глубокого анализа: {e}")
                        else:
                            st.warning("Сначала выполните базовый анализ")

                    with tab2:
                        st.subheader("⚠️ Выявленные риски")
                        if risks:
                            for i, risk in enumerate(risks, 1):
                                severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(risk.get('severity', 'low'), "⚪")
                                with st.expander(f"{severity_icon} {i}. {risk.get('title', 'N/A')} ({risk.get('risk_type', 'N/A')})"):
                                    st.markdown(f"**Категория:** {risk.get('category', 'N/A')}")
                                    st.markdown(f"**Серьёзность:** {risk.get('severity', 'N/A').upper()}")
                                    st.markdown(f"**Описание:** {risk.get('description', 'N/A')}")
                                    if risk.get('consequences'):
                                        st.markdown(f"**Последствия:** {risk.get('consequences')}")
                                    if risk.get('section_name'):
                                        st.markdown(f"**Раздел договора:** {risk.get('section_name')}")
                        else:
                            st.info("✅ Риски не обнаружены")

                    with tab3:
                        st.subheader("💡 Рекомендации")
                        if recommendations:
                            for i, rec in enumerate(recommendations, 1):
                                priority_icon = {"critical": "🔴", "high": "🟡", "medium": "🟠", "low": "🟢"}.get(rec.get('priority', 'medium'), "⚪")
                                with st.expander(f"{priority_icon} {i}. {rec.get('title', 'Рекомендация')}"):
                                    st.markdown(f"**Приоритет:** {rec.get('priority', 'N/A').upper()}")
                                    st.markdown(f"**Категория:** {rec.get('category', 'N/A')}")
                                    st.markdown(f"**Рекомендация:** {rec.get('recommendation_text', 'N/A')}")
                                    if rec.get('expected_benefit'):
                                        st.markdown(f"**Ожидаемая выгода:** {rec.get('expected_benefit')}")
                                    if rec.get('implementation_complexity'):
                                        st.markdown(f"**Сложность внедрения:** {rec.get('implementation_complexity')}")
                        else:
                            st.info("Рекомендации отсутствуют")

                    with tab4:
                        st.subheader("✏️ Предложенные изменения")
                        if suggested_changes:
                            for i, change in enumerate(suggested_changes, 1):
                                with st.expander(f"{i}. {change.get('issue_description', 'Изменение')[:60]}..."):
                                    st.markdown(f"**Проблема:** {change.get('issue_description', 'N/A')}")
                                    st.markdown(f"**Тип изменения:** {change.get('change_type', 'N/A')}")

                                    col_a, col_b = st.columns(2)
                                    with col_a:
                                        st.markdown("**Оригинальный текст:**")
                                        st.code(change.get('original_text', 'N/A')[:200], language='text')
                                    with col_b:
                                        st.markdown("**Предлагаемый текст:**")
                                        st.code(change.get('suggested_text', 'N/A')[:200], language='text')

                                    st.markdown(f"**Обоснование:** {change.get('reasoning', 'N/A')}")
                                    if change.get('legal_basis'):
                                        st.markdown(f"**Правовая база:** {change.get('legal_basis')}")
                        else:
                            st.info("Предложенных изменений нет")

                    with tab5:
                        st.subheader("📝 Аннотации и комментарии")
                        if annotations:
                            for i, ann in enumerate(annotations, 1):
                                st.markdown(f"**{i}. {ann.get('section_name', 'Раздел')}** - {ann.get('annotation_text', 'N/A')}")
                        else:
                            st.info("Аннотации отсутствуют")

                    with tab6:
                        st.subheader("📄 Полный отчёт об анализе")

                        # Generate detailed report
                        report_lines = []
                        report_lines.append("=" * 80)
                        report_lines.append("ПОЛНЫЙ ОТЧЁТ ОБ АНАЛИЗЕ ДОГОВОРА")
                        report_lines.append("=" * 80)
                        report_lines.append(f"\n📋 ID Анализа: {analysis_id}")
                        report_lines.append(f"📄 ID Договора: {contract.id}")
                        report_lines.append(f"📁 Файл: {contract.file_name}")
                        report_lines.append(f"📅 Дата анализа: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
                        report_lines.append(f"🎚️ Уровень риска: {risk_level}")
                        report_lines.append(f"\n📊 СТАТИСТИКА:")
                        report_lines.append(f"  • Рисков обнаружено: {len(risks)} (высоких: {high_risks}, средних: {medium_risks}, низких: {low_risks})")
                        report_lines.append(f"  • Рекомендаций: {len(recommendations)}")
                        report_lines.append(f"  • Предложенных изменений: {len(suggested_changes)}")
                        report_lines.append(f"  • Аннотаций: {len(annotations)}")

                        if dispute_prediction:
                            report_lines.append(f"\n⚖️ ПРОГНОЗ СПОРОВ:")
                            report_lines.append(f"  • Вероятность спора: {dispute_prediction.get('probability', 'N/A')}")
                            report_lines.append(f"  • Оценка: {dispute_prediction.get('score', 'N/A')}")

                        if counterparty_data:
                            report_lines.append(f"\n🏢 ПРОВЕРКА КОНТРАГЕНТА:")
                            report_lines.append(f"  • Результат: {counterparty_data.get('status', 'N/A')}")

                        # Risks detail
                        if risks:
                            report_lines.append("\n" + "=" * 80)
                            report_lines.append("⚠️ ДЕТАЛЬНЫЙ СПИСОК РИСКОВ")
                            report_lines.append("=" * 80)
                            for i, risk in enumerate(risks, 1):
                                report_lines.append(f"\n{i}. {risk.get('title', 'N/A')}")
                                report_lines.append(f"   Тип: {risk.get('risk_type', 'N/A')}")
                                report_lines.append(f"   Серьёзность: {risk.get('severity', 'N/A').upper()}")
                                report_lines.append(f"   Описание: {risk.get('description', 'N/A')}")
                                if risk.get('consequences'):
                                    report_lines.append(f"   Последствия: {risk.get('consequences')}")
                                if risk.get('section_name'):
                                    report_lines.append(f"   Раздел: {risk.get('section_name')}")

                        # Recommendations detail
                        if recommendations:
                            report_lines.append("\n" + "=" * 80)
                            report_lines.append("💡 ДЕТАЛЬНЫЕ РЕКОМЕНДАЦИИ")
                            report_lines.append("=" * 80)
                            for i, rec in enumerate(recommendations, 1):
                                report_lines.append(f"\n{i}. {rec.get('title', 'Рекомендация')}")
                                report_lines.append(f"   Приоритет: {rec.get('priority', 'N/A').upper()}")
                                report_lines.append(f"   Рекомендация: {rec.get('recommendation_text', 'N/A')}")
                                if rec.get('expected_benefit'):
                                    report_lines.append(f"   Ожидаемая выгода: {rec.get('expected_benefit')}")

                        # Suggested changes detail
                        if suggested_changes:
                            report_lines.append("\n" + "=" * 80)
                            report_lines.append("✏️ ПРЕДЛОЖЕННЫЕ ИЗМЕНЕНИЯ")
                            report_lines.append("=" * 80)
                            for i, change in enumerate(suggested_changes, 1):
                                report_lines.append(f"\n{i}. {change.get('issue_description', 'Изменение')}")
                                report_lines.append(f"   Тип: {change.get('change_type', 'N/A')}")
                                report_lines.append(f"   Оригинал: {change.get('original_text', 'N/A')[:200]}")
                                report_lines.append(f"   Предложение: {change.get('suggested_text', 'N/A')[:200]}")
                                report_lines.append(f"   Обоснование: {change.get('reasoning', 'N/A')}")

                        # Detailed clause-by-clause analysis
                        if clause_analyses:
                            report_lines.append("\n" + "=" * 80)
                            report_lines.append("📑 ДЕТАЛЬНЫЙ АНАЛИЗ ПО ПУНКТАМ ДОГОВОРА")
                            report_lines.append("=" * 80)
                            report_lines.append(f"\nПроанализировано пунктов: {len(clause_analyses)}")
                            report_lines.append("")

                            for i, clause_analysis in enumerate(clause_analyses, 1):
                                clause_num = clause_analysis.get('clause_number', i)
                                report_lines.append(f"\n{'─' * 80}")
                                report_lines.append(f"ПУНКТ {clause_num}")
                                report_lines.append(f"{'─' * 80}")

                                # Scores
                                clarity = clause_analysis.get('clarity_score', 0)
                                legal_compliance = clause_analysis.get('legal_compliance', {})
                                legal_score = legal_compliance.get('score', 0)

                                report_lines.append(f"Чёткость формулировки: {clarity}/10")
                                report_lines.append(f"Правовое соответствие: {legal_score}/10")
                                report_lines.append(f"Приоритет улучшения: {clause_analysis.get('improvement_priority', 'N/A').upper()}")
                                report_lines.append("")

                                # Overall assessment
                                report_lines.append(f"ОБЩАЯ ОЦЕНКА:")
                                report_lines.append(f"  {clause_analysis.get('overall_assessment', 'Не указана')}")
                                report_lines.append("")

                                # Clarity assessment
                                report_lines.append(f"ОЦЕНКА ФОРМУЛИРОВКИ:")
                                report_lines.append(f"  {clause_analysis.get('clarity_assessment', 'Не указана')}")
                                report_lines.append("")

                                # Risks
                                clause_risks = clause_analysis.get('risks', [])
                                if clause_risks:
                                    report_lines.append(f"РИСКИ ({len(clause_risks)}):")
                                    for j, risk in enumerate(clause_risks, 1):
                                        report_lines.append(f"  {j}. {risk.get('title', 'Риск')} ({risk.get('severity', 'N/A')})")
                                        report_lines.append(f"     {risk.get('description', 'Нет описания')}")
                                        if risk.get('consequences'):
                                            report_lines.append(f"     Последствия: {risk.get('consequences')}")
                                    report_lines.append("")

                                # Recommendations
                                clause_recs = clause_analysis.get('recommendations', [])
                                if clause_recs:
                                    report_lines.append(f"РЕКОМЕНДАЦИИ ({len(clause_recs)}):")
                                    for j, rec in enumerate(clause_recs, 1):
                                        report_lines.append(f"  {j}. {rec.get('recommendation', 'Рекомендация')}")
                                        report_lines.append(f"     {rec.get('reasoning', 'Не указано')}")
                                    report_lines.append("")

                                # Ambiguities
                                ambiguities = clause_analysis.get('ambiguities', [])
                                if ambiguities:
                                    report_lines.append(f"ДВУСМЫСЛЕННОСТИ:")
                                    for amb in ambiguities:
                                        report_lines.append(f"  • {amb}")
                                    report_lines.append("")

                                # Missing elements
                                missing = clause_analysis.get('missing_elements', [])
                                if missing:
                                    report_lines.append(f"ОТСУТСТВУЮЩИЕ ЭЛЕМЕНТЫ:")
                                    for miss in missing:
                                        report_lines.append(f"  • {miss}")
                                    report_lines.append("")

                                # Legal issues
                                issues = legal_compliance.get('issues', [])
                                if issues:
                                    report_lines.append(f"ПРАВОВЫЕ ПРОБЛЕМЫ:")
                                    for issue in issues:
                                        report_lines.append(f"  ⚠️ {issue}")
                                    report_lines.append("")

                                # Relevant laws
                                laws = legal_compliance.get('relevant_laws', [])
                                if laws:
                                    report_lines.append(f"ПРИМЕНИМЫЕ ПРАВОВЫЕ НОРМЫ:")
                                    for law in laws:
                                        report_lines.append(f"  • {law}")
                                    report_lines.append("")

                        report_lines.append("\n" + "=" * 80)
                        report_lines.append("КОНЕЦ ОТЧЁТА")
                        report_lines.append("=" * 80)

                        report_text = "\n".join(report_lines)

                        # Display report
                        st.text_area("📄 Отчёт", report_text, height=400)

                        # Download button
                        report_filename = f"analysis_report_{contract.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                        st.download_button(
                            label="📥 Скачать полный отчёт",
                            data=report_text,
                            file_name=report_filename,
                            mime="text/plain",
                            use_container_width=True
                        )

                    st.markdown("---")

                    # Action buttons
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("🔄 Анализировать новый договор", use_container_width=True):
                            st.rerun()
                    with col2:
                        if st.button("⚖️ Генерация возражений", use_container_width=True, disabled=not check_feature_access('can_use_disagreements')):
                            st.session_state.current_page = 'disagreements'
                            st.session_state.analysis_id = analysis_id
                            st.rerun()
                    with col3:
                        if st.button("📤 Экспорт результатов", use_container_width=True, disabled=not check_feature_access('can_export_pdf')):
                            st.info("Функция экспорта в разработке")

                else:
                    # Update status to error
                    contract.status = 'error'
                    st.session_state.db_session.commit()

                    st.error(f"❌ Ошибка анализа: {result.error}")
                    logger.error(f"Analysis failed: {result.error}")

            except Exception as e:
                # Update status to error if contract exists
                if 'contract' in locals():
                    contract.status = 'error'
                    st.session_state.db_session.commit()

                st.error(f"❌ Ошибка анализа: {e}")
                logger.error(f"Analysis error: {type(e).__name__}: {e}", exc_info=True)


def page_disagreements():
    """Disagreement Processor page"""
    st.title("⚖️ Генерация возражений")

    # Check access
    if not check_feature_access('can_use_disagreements'):
        show_upgrade_message('Генерация возражений')
        return

    user = get_current_user()
    user_id = user['id'] if user else 'demo_user'

    st.markdown("### Создание документа с возражениями")

    contract_id = st.text_input("ID договора для анализа", value="contract_001")
    analysis_id = st.text_input("ID анализа", value="analysis_001")
    
    auto_prioritize = st.checkbox("Автоматическая приоритизация", value=True)
    
    if st.button("🚀 Генерировать возражения", type="primary"):
        if not AGENTS_AVAILABLE:
            st.error("Агенты недоступны")
            return
        
        with st.spinner("Генерация возражений..."):
            try:
                agent = DisagreementProcessorAgent(
                    llm_gateway=st.session_state.llm_gateway,
                    db_session=st.session_state.db_session
                )
                
                result = agent.execute({
                    'contract_id': contract_id,
                    'analysis_id': analysis_id,
                    'auto_prioritize': auto_prioritize,
                    'user_id': user_id
                })
                
                if result.success:
                    st.success("✅ Возражения сгенерированы")
                    st.write(f"**Disagreement ID:** {result.data.get('disagreement_id')}")
                    st.write(f"**Всего возражений:** {result.data.get('total_objections')}")
                    st.write(f"**Статус:** {result.data.get('status')}")
                    
                    # Show objections
                    st.subheader("Возражения")
                    objections = result.data.get('objections', [])
                    for obj in objections:
                        with st.expander(f"Возражение {obj.get('objection_number')} (Приоритет: {obj.get('priority')})"):
                            st.write(f"**Раздел:** {obj.get('section_reference')}")
                            st.write(f"**Текст:** {obj.get('objection_text')}")
                            st.write(f"**Обоснование:** {obj.get('legal_justification')}")
                else:
                    st.error(f"Ошибка: {result.error}")
            
            except Exception as e:
                st.error(f"Ошибка: {e}")


def page_changes():
    """Changes Analyzer page"""
    st.title("📊 Анализ изменений")

    # Check access
    if not check_feature_access('can_use_changes_analyzer'):
        show_upgrade_message('Анализ изменений')
        return

    st.markdown("### Сравнение версий договора")

    col1, col2 = st.columns(2)

    with col1:
        from_version_id = st.number_input("От версии ID", min_value=1, value=1)

    with col2:
        to_version_id = st.number_input("До версии ID", min_value=1, value=2)

    contract_id = st.text_input("ID договора", value="contract_001", key="changes_contract")
    
    if st.button("🚀 Анализировать изменения", type="primary"):
        if not AGENTS_AVAILABLE:
            st.error("Агенты недоступны")
            return
        
        with st.spinner("Анализ изменений..."):
            try:
                agent = ChangesAnalyzerAgent(
                    llm_gateway=st.session_state.llm_gateway,
                    db_session=st.session_state.db_session
                )
                
                result = agent.execute({
                    'from_version_id': from_version_id,
                    'to_version_id': to_version_id,
                    'contract_id': contract_id
                })
                
                if result.success:
                    st.success("✅ Анализ изменений завершен")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Всего изменений", result.data.get('total_changes', 0))
                    
                    with col2:
                        assessment = result.data.get('overall_assessment', 'N/A')
                        st.metric("Общая оценка", assessment)
                    
                    with col3:
                        st.metric("Отчет", "Готов" if result.data.get('report_path') else "Нет")
                    
                    if result.data.get('report_path'):
                        st.download_button(
                            "📥 Скачать отчет",
                            data=open(result.data['report_path'], 'rb'),
                            file_name=os.path.basename(result.data['report_path'])
                        )
                else:
                    st.error(f"Ошибка: {result.error}")
            
            except Exception as e:
                st.error(f"Ошибка: {e}")


def page_export():
    """Quick Export page"""
    st.title("📤 Быстрый экспорт")

    # Check access
    user = get_current_user()
    user_id = user['id'] if user else 'demo_user'

    st.markdown("### Экспорт договора")

    contract_id = st.text_input("ID договора", value="contract_001", key="export_contract")

    col1, col2 = st.columns(2)

    with col1:
        export_format = st.selectbox(
            "Формат экспорта",
            ["docx", "pdf", "txt", "json", "xml", "all"]
        )

    with col2:
        include_analysis = st.checkbox("Включить результаты анализа", value=False)

    # Check PDF export permission
    if export_format in ['pdf', 'all']:
        if not check_feature_access('can_export_pdf'):
            st.warning("⚠️ Экспорт в PDF доступен только в полной версии")
            if export_format == 'pdf':
                show_upgrade_message('Экспорт в PDF')
                return
    
    if st.button("🚀 Экспортировать", type="primary"):
        if not AGENTS_AVAILABLE:
            st.error("Агенты недоступны")
            return
        
        with st.spinner("Экспорт..."):
            try:
                agent = QuickExportAgent(
                    llm_gateway=st.session_state.llm_gateway,
                    db_session=st.session_state.db_session
                )
                
                result = agent.execute({
                    'contract_id': contract_id,
                    'export_format': export_format,
                    'include_analysis': include_analysis,
                    'user_id': user_id
                })
                
                if result.success:
                    st.success("✅ Экспорт завершен")
                    
                    file_paths = result.data.get('file_paths', {})
                    for fmt, path in file_paths.items():
                        if path and os.path.exists(path):
                            st.write(f"**{fmt.upper()}:** {path}")
                            with open(path, 'rb') as f:
                                st.download_button(
                                    f"📥 Скачать {fmt.upper()}",
                                    data=f,
                                    file_name=os.path.basename(path),
                                    key=f"download_{fmt}"
                                )
                else:
                    st.error(f"Ошибка: {result.error}")
            
            except Exception as e:
                st.error(f"Ошибка: {e}")


def page_login():
    """Login page"""
    st.title("🔐 Вход в систему")
    show_login_form()


def page_logs():
    """System logs page (admin only)"""
    st.title("📋 Логи системы")

    # Check admin access
    if not check_feature_access('can_view_logs'):
        st.error("⛔ Доступ запрещён. Только для администраторов.")
        return

    st.markdown("### Мониторинг активности системы")

    # Tabs for different log types
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Системные логи", "🤖 LLM запросы", "👥 Активность пользователей", "⚠️ Ошибки"])

    with tab1:
        st.subheader("Системные логи")

        # Real-time toggle
        realtime = st.checkbox("Режим реального времени", value=False)

        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            log_level = st.selectbox("Уровень", ["ALL", "INFO", "WARNING", "ERROR"])
        with col2:
            lines = st.number_input("Показать строк", 10, 1000, 100)

        if st.button("🔄 Обновить логи") or realtime:
            try:
                # Read log file
                log_file = "streamlit.log"
                if os.path.exists(log_file):
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        all_lines = f.readlines()
                        # Get last N lines
                        recent_lines = all_lines[-lines:]

                        # Filter by level
                        if log_level != "ALL":
                            recent_lines = [l for l in recent_lines if log_level in l]

                        log_text = ''.join(recent_lines)
                        st.text_area("Логи", log_text, height=400)
                else:
                    st.warning("Файл логов не найден")
            except Exception as e:
                st.error(f"Ошибка чтения логов: {e}")

    with tab2:
        st.subheader("LLM запросы")

        if AGENTS_AVAILABLE:
            st.info("История запросов к LLM")
            # This would query database for LLM requests
            st.markdown("""
            **Статистика:**
            - Всего запросов сегодня: -
            - Успешных: -
            - Ошибок: -
            - Средняя задержка: - мс
            """)
        else:
            st.warning("Данные недоступны")

    with tab3:
        st.subheader("Активность пользователей")

        if AGENTS_AVAILABLE:
            from src.models import User
            db = SessionLocal()
            try:
                users = db.query(User).all()

                st.markdown(f"**Всего пользователей:** {len(users)}")

                # User table
                user_data = []
                for u in users:
                    user_data.append({
                        "Email": u.email,
                        "Имя": u.name,
                        "Роль": u.role,
                        "Активен": "✅" if u.active else "❌"
                    })

                if user_data:
                    import pandas as pd
                    df = pd.DataFrame(user_data)
                    st.dataframe(df, use_container_width=True)
            finally:
                db.close()
        else:
            st.warning("База данных недоступна")

    with tab4:
        st.subheader("Журнал ошибок")

        # Last errors
        st.markdown("**Последние ошибки:**")
        try:
            log_file = "streamlit.log"
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    all_lines = f.readlines()
                    error_lines = [l for l in all_lines if 'ERROR' in l or 'Exception' in l]
                    recent_errors = error_lines[-50:]

                    if recent_errors:
                        error_text = ''.join(recent_errors)
                        st.text_area("Ошибки", error_text, height=400)
                    else:
                        st.success("✅ Ошибок не обнаружено")
            else:
                st.warning("Файл логов не найден")
        except Exception as e:
            st.error(f"Ошибка чтения логов: {e}")


def page_settings():
    """Settings page"""
    st.title("⚙️ Настройки")

    st.markdown("### Конфигурация системы")

    st.subheader("LLM Provider")
    provider = st.selectbox(
        "Провайдер",
        ["openai", "anthropic", "yandex"],
        index=0
    )

    api_key = st.text_input("API Key", type="password", value="")

    st.subheader("База данных")
    db_url = st.text_input("Database URL", value=settings.database_url)

    st.subheader("RAG System")
    chroma_path = st.text_input("ChromaDB Path", value=settings.chroma_persist_directory)

    if st.button("💾 Сохранить настройки"):
        st.success("Настройки сохранены (функциональность в разработке)")


def main():
    """Main application"""
    init_session_state()
    sidebar_navigation()

    # Route to page
    page = st.session_state.current_page

    if page == 'login':
        page_login()
    elif page == 'home':
        page_home()
    elif page == 'onboarding':
        page_onboarding()
    elif page == 'generator':
        page_generator_improved()  # Use improved version
    elif page == 'analyzer':
        page_analyzer()
    elif page == 'disagreements':
        page_disagreements()
    elif page == 'changes':
        page_changes()
    elif page == 'export':
        page_export()
    elif page == 'knowledge_base':
        page_knowledge_base()  # Add knowledge base page
    elif page == 'logs':
        page_logs()  # Admin logs page
    elif page == 'settings':
        page_settings()


if __name__ == "__main__":
    main()
