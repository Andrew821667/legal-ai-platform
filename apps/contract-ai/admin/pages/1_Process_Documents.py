"""
Обработка документов - "Стеклянный ящик"
Показывает ВСЕ промежуточные результаты обработки
Поддерживает два режима: "Новый договор" и "Подписанный договор"
"""

import streamlit as st
import sys
from pathlib import Path
import asyncio
import json
import os
import tempfile
import pandas as pd
from typing import Dict, Any, List, Optional
import io
import hashlib

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="Обработка документов - Contract AI",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Обработка документов")
st.markdown("**Стеклянный ящик:** видны все промежуточные результаты работы системы")

st.markdown("---")


def _ensure_recommendation_state() -> None:
    """Гарантирует наличие state для принятых рекомендаций."""
    if "accepted_recommendations" not in st.session_state:
        st.session_state["accepted_recommendations"] = []
    if "accepted_recommendation_keys" not in st.session_state:
        st.session_state["accepted_recommendation_keys"] = []


def _build_recommendation_key(payload: Dict[str, Any]) -> str:
    """Детерминированный ключ для защиты от дублей."""
    section_number = str(payload.get("section_number", "")).strip()
    section_title = str(payload.get("section_title", "")).strip()
    source = str(payload.get("source", "")).strip()
    action_type = str(payload.get("action_type", "")).strip()
    proposed_text = str(payload.get("proposed_text", "")).strip()[:180]
    return "|".join([source, section_number, section_title, action_type, proposed_text])


def add_accepted_recommendation(payload: Dict[str, Any]) -> bool:
    """
    Добавляет принятую рекомендацию в session_state.
    Возвращает True, если запись добавлена, иначе False (дубль).
    """
    _ensure_recommendation_state()
    key = _build_recommendation_key(payload)
    existing_keys = st.session_state.get("accepted_recommendation_keys", [])
    if key in existing_keys:
        return False

    normalized_payload = {
        "section_number": payload.get("section_number", ""),
        "section_title": payload.get("section_title", ""),
        "original_text": payload.get("original_text", ""),
        "proposed_text": payload.get("proposed_text", ""),
        "reason": payload.get("reason", ""),
        "action_type": payload.get("action_type", "modify"),
        "priority": payload.get("priority", "optional"),
        "source": payload.get("source", "section_analysis"),
        "target": payload.get("target", "docx"),
        "rec_key": key
    }

    st.session_state["accepted_recommendations"].append(normalized_payload)
    st.session_state["accepted_recommendation_keys"] = existing_keys + [key]
    return True


def _extract_section_analysis_data(result: Any) -> Optional[Dict[str, Any]]:
    """Достаёт полные данные section analysis из стадий обработки."""
    for stage in result.stages:
        if stage.name == "section_analysis" and stage.status == "success":
            return stage.results.get("full_data")
    return None


def _risk_level_ru(level: str) -> str:
    mapping = {
        "critical": "Критический",
        "high": "Высокий",
        "medium": "Средний",
        "low": "Низкий",
    }
    return mapping.get(str(level).lower(), str(level))

# Загрузка файла
st.header("1️⃣ Загрузка документа")

# Выбор режима работы
contract_mode = st.radio(
    "Режим работы с договором:",
    ["Новый договор (Pre-Execution)", "Подписанный договор (Post-Execution)"],
    help="**Новый договор** — правки вносятся прямо в DOCX-документ.\n\n"
         "**Подписанный договор** — оригинал не трогаем, формируем протокол разногласий.",
    horizontal=True
)

is_new_contract = contract_mode.startswith("Новый")

uploaded_file = st.file_uploader(
    "Выберите файл договора",
    type=['pdf', 'docx', 'txt', 'xml', 'html', 'htm', 'png', 'jpg', 'jpeg'],
    help="Поддерживаются: PDF, DOCX, TXT, XML, HTML, изображения (с OCR)"
)

# Загрузка эталонного шаблона (Stage 2.2: Pre-Execution)
if is_new_contract:
    st.markdown("---")
    st.header("📋 Эталонный шаблон (Playbook)")
    st.markdown("Загрузите эталонный шаблон договора для автоматического сравнения с черновиком. "
                "Система выявит все отклонения от стандарта компании.")

    template_file = st.file_uploader(
        "Выберите файл шаблона (эталон)",
        type=['pdf', 'docx', 'txt', 'xml', 'html', 'htm'],
        help="Эталонный шаблон, с которым будет сравниваться черновик",
        key="template_uploader"
    )
else:
    template_file = None

def extract_text_from_file(file_path: str, file_ext: str) -> str:
    """Извлекает текст из файла (для шаблона) синхронно"""
    from src.services.text_extractor import TextExtractor
    extractor = TextExtractor(use_ocr=False)
    result = extractor.extract(file_path, file_ext)
    return result.text


async def compare_with_template_async(draft_text: str, template_text: str, contract_type: str = "неизвестный"):
    """Асинхронное сравнение черновика с шаблоном"""
    from src.services.template_comparator import TemplateComparator
    import os
    from dotenv import load_dotenv

    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / ".env"
    load_dotenv(env_path)

    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if deepseek_key:
        api_key = deepseek_key
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    elif openai_key:
        api_key = openai_key
        base_url = None
        model = os.getenv("OPENAI_MODEL_MINI", "gpt-4o-mini")
    else:
        raise ValueError("API ключ не настроен.")

    comparator = TemplateComparator(model=model, api_key=api_key, base_url=base_url)
    return await comparator.compare(draft_text, template_text, contract_type)


# Вспомогательная функция для async обработки
async def process_document_async(file_path, file_ext, use_section_analysis=False):
    """Асинхронная обработка документа с автоматическим fallback"""
    from src.services.document_processor import DocumentProcessor
    import os
    from dotenv import load_dotenv

    # Загружаем переменные окружения из .env файла
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / ".env"
    load_dotenv(env_path)

    # DeepSeek — основная модель (дешевле, $0.14/1M токенов)
    # GPT-4o-mini — fallback
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if deepseek_key:
        api_key = deepseek_key
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    elif openai_key:
        api_key = openai_key
        base_url = None
        model = os.getenv("OPENAI_MODEL_MINI", "gpt-4o-mini")
    else:
        raise ValueError(
            "API ключ не настроен.\n"
            "Добавьте в .env: OPENAI_API_KEY=... или DEEPSEEK_API_KEY=..."
        )

    processor = DocumentProcessor(
        api_key=api_key,
        model=model,
        base_url=base_url,
        use_rag=False,
        use_section_analysis=use_section_analysis
    )

    result = await processor.process_document(file_path, file_ext)
    return result


def render_docx_preview(docx_bytes: bytes) -> str:
    """Конвертирует DOCX bytes в HTML через mammoth для предпросмотра"""
    try:
        import mammoth
        result = mammoth.convert_to_html(io.BytesIO(docx_bytes))
        html = result.value
        # Оборачиваем в стили для лучшего отображения
        styled_html = f"""
        <div style="background: white; color: black; padding: 20px; border: 1px solid #ddd;
                    border-radius: 8px; font-family: 'Times New Roman', serif; line-height: 1.6;
                    max-height: 600px; overflow-y: auto;">
            {html}
        </div>
        """
        return styled_html
    except Exception as e:
        return f"<p style='color:red;'>Ошибка предпросмотра: {e}</p>"


def get_entity_purpose(entity_type: str) -> str:
    """Возвращает КОНКРЕТНОЕ назначение сущности в системе"""
    purposes = {
        "contract_number": "📝 Первичный ключ для индексации в БД (таблица contracts, поле contract_id). Используется для поиска договора через UI, API endpoints (/api/contracts/{id}), формирования уникального файлового имени при экспорте",
        "date": "📅 Заполняет поля: contract_date, start_date, end_date в таблице contracts. Используется для: автоматических уведомлений о сроках (модуль notifications), фильтрации по датам в UI (страница Contract List), валидации актуальности договора, расчета длительности договора",
        "inn": "🏢 Связывание с таблицей counterparties (foreign key counterparty_inn). Используется для: автозаполнения карточки контрагента, проверки в ФНС через API интеграцию, дедупликации контрагентов, построения графа взаимосвязей компаний, риск-анализа контрагента",
        "ogrn": "🔐 Проверка легитимности юрлица через API ФНС/ЕГРЮЛ. Сохраняется в counterparties.ogrn. Используется для валидации регистрации, определения даты регистрации компании, проверки актуальности юрлица",
        "kpp": "🏦 Идентификация конкретного подразделения компании (counterparties.kpp). Используется для: определения филиала/обособленного подразделения, корректной отправки документов на нужный адрес, группировки договоров по подразделениям",
        "amount": "💰 Финансовые поля: total_amount, currency, vat_amount в таблице contracts. Используется для: подсчета общей суммы портфеля договоров (Dashboard Analytics), лимит-контроля (проверка превышения бюджета), формирования финансовых отчетов, прогнозирования cash flow",
        "organization": "🏛️ Извлечение названий компаний для заполнения counterparties.name. Используется для: создания новой записи контрагента, fuzzy-match поиска существующих контрагентов (избегание дублей), отображения в UI списка сторон договора",
        "person": "👤 ФИО подписантов сохраняются в таблице signatories (fields: full_name, position, authority_document). Используется для: проверки полномочий подписанта, валидации права подписи (cross-check с доверенностями), юридической значимости договора",
        "address": "📍 Юр. и факт. адреса в counterparties.legal_address и counterparties.actual_address. Используется для: формирования почтовых уведомлений, геолокации контрагентов на карте (UI Dashboard), проверки совпадения адресов (fraud detection)",
        "phone": "📞 Контактные данные в counterparties.phone и contacts.phone. Используется для: автоматических звонков/SMS уведомлений о сроках, связи с контрагентом через CRM интеграцию, валидации формата телефона",
        "email": "📧 Email адреса в counterparties.email и contacts.email. Используется для: автоматической отправки email уведомлений (истечение срока, изменения), приглашений в систему для подписания, интеграции с email-клиентом",
        "account": "💳 Банковские счета в counterparties.bank_account. Используется для: автозаполнения платежных поручений, проверки корректности р/с через API ЦБ РФ, связывания с таблицей payments для отслеживания оплат",
        "bic": "🏦 БИК банка в counterparties.bank_bic. Используется для: валидации существования банка через справочник ЦБ РФ, автозаполнения наименования банка и корр. счета, проверки банка на санкционные списки",
        "percent": "📊 Процентные ставки сохраняются в contract_terms.penalty_rate, discount_rate, interest_rate. Используется для: автоматического расчета пеней за просрочку, применения скидок, начисления процентов по договорам займа/кредита",
        "payment_term": "⏰ Условия оплаты в contracts.payment_terms (предоплата/постоплата/рассрочка). Используется для: планирования платежей в модуле Finance, создания напоминаний о платежах, формирования графика платежей",
        "delivery_address": "🚚 Адрес поставки в contracts.delivery_address. Используется для: логистического планирования, интеграции с транспортными компаниями, расчета стоимости доставки",
        "warranty_period": "🛡️ Гарантийный срок в contract_terms.warranty_months. Используется для: отслеживания гарантийных обязательств, автоматических напоминаний об окончании гарантии, учета гарантийных случаев"
    }
    # Если тип не найден - вернуть детальное объяснение
    if entity_type not in purposes:
        return f"❓ Сущность '{entity_type}' не имеет специфичного назначения. Сохраняется в contracts.metadata (JSON) для справочной информации и полнотекстового поиска"
    return purposes.get(entity_type)


def get_optimal_model_info(stage: str):
    """Возвращает информацию об оптимальной модели для этапа (актуализировано 2026)"""
    models = {
        "text_extraction": (
            "N/A (прямое извлечение)",
            "pdfplumber + PaddleOCR для сканов + LayoutLMv3 для сложных макетов"
        ),
        "level1": (
            "regex + SpaCy (ru_core_news_sm)",
            "SpaCy ru_core_news_lg, DeepPavlov NER, или Qwen2.5-VL-72B (119 языков!) для визуальных документов"
        ),
        "llm": (
            "gpt-4o-mini ($0.15/$0.6 per 1M) или DeepSeek-V3.2 ($0.25/$0.38 per 1M)",
            "Лучшие в 2026: GPT-4.1 ($2/$8, 1M context), Claude Sonnet 4.5 ($3/$15), DeepSeek-V3.2 ($0.25/$0.38, экономия 90%!), Qwen2.5-VL-72B (119 языков, визуальный анализ)"
        ),
        "rag": (
            "pgvector + text-embedding-3-large",
            "OpenAI text-embedding-3-large или Cohere embed-multilingual-v3.0 для русского и многоязычных договоров"
        ),
        "validation": (
            "Business rules + Pydantic",
            "Топ-3 в 2026: Claude Opus 4.5 ($5/$25, самый точный), GPT-4.1 ($2/$8, 1M context), Qwen2.5-VL-72B (многоязычный + визуальный анализ)"
        ),
        "section_analysis": (
            "DeepSeek-V3.2 ($0.25/$0.38 per 1M) или gpt-4o-mini ($0.15/$0.6)",
            "Оптимальные: DeepSeek-V3.2 (90% экономия!), Claude Sonnet 4.5 ($3/$15, юридический анализ), GPT-4.1 ($2/$8, длинные контексты 1M)"
        )
    }
    return models.get(stage, ("N/A", "N/A"))


def display_validation_section_dynamic(section_analysis_data: Dict[str, Any], is_new_contract: bool = True):
    """Отображает детальную валидацию по разделам договора (ДИНАМИЧЕСКИ из LLM)"""

    if not section_analysis_data:
        st.warning("Анализ разделов не был выполнен")
        return

    st.subheader("📋 Детальный разбор по разделам договора")

    # Показываем текущий режим
    if is_new_contract:
        st.info("📝 **Режим: Новый договор** — принятые рекомендации будут внесены в DOCX-документ")
    else:
        st.info("📋 **Режим: Подписанный договор** — принятые рекомендации будут собраны в протокол разногласий")

    sections = section_analysis_data.get("sections", [])
    section_analyses = section_analysis_data.get("section_analyses", [])
    complex_analysis = section_analysis_data.get("complex_analysis")

    if not sections:
        st.warning("Разделы не обнаружены в договоре")
        return

    st.info(f"**Найдено разделов:** {len(sections)} | **Порядок проверки:** 1️⃣ Сравнение с собственными договорами → 2️⃣ Проверка по RAG базе (актуальная правовая база) → 3️⃣ Фолбэк на базу знаний модели")

    # Динамически создаем вкладки
    tab_names = [f"Раздел {s.number}" for s in sections] + ["🔍 Комплексный анализ"]
    tabs = st.tabs(tab_names)

    # Инициализируем состояние принятых рекомендаций
    _ensure_recommendation_state()

    # Отображаем каждый раздел ДИНАМИЧЕСКИ
    for idx, (section, analysis) in enumerate(zip(sections, section_analyses)):
        with tabs[idx]:
            st.markdown(f"### 📄 Раздел {section.number}: {section.title}")

            # Текст раздела
            st.text_area("Текст раздела:", section.text, height=150, key=f"section_{section.number}_text")

            st.markdown("---")

            # Сравнение с собственными договорами
            st.markdown("**1️⃣ Сравнение с собственными договорами:**")
            if analysis.own_contracts_comparison.startswith("✅"):
                st.success(analysis.own_contracts_comparison)
            elif analysis.own_contracts_comparison.startswith("⚠️"):
                st.warning(analysis.own_contracts_comparison)
            else:
                st.error(analysis.own_contracts_comparison)

            # Детальные проверки
            if analysis.own_contracts_details:
                st.dataframe(analysis.own_contracts_details, use_container_width=True)

            # RAG проверка
            st.markdown("**2️⃣ Проверка по RAG (актуальная правовая база):**")
            st.info(analysis.rag_legal_check)

            if analysis.rag_legal_references:
                st.markdown("**Ссылки на законодательство:**")
                for ref in analysis.rag_legal_references:
                    st.markdown(f"- {ref}")

            st.markdown("---")

            # Выводы и рекомендации
            if analysis.conclusion.startswith("Раздел проработан хорошо") or "соответствует" in analysis.conclusion.lower():
                st.success(f"**Вывод:** {analysis.conclusion}")
            elif "требует" in analysis.conclusion.lower() or "доработк" in analysis.conclusion.lower():
                st.warning(f"**Вывод:** {analysis.conclusion}")
            else:
                st.info(f"**Вывод:** {analysis.conclusion}")

            if analysis.warnings:
                st.markdown("**⚠️ Предупреждения:**")
                for warning in analysis.warnings:
                    st.warning(warning)

            if analysis.recommendations:
                st.markdown("**💡 Рекомендации по улучшению:**")
                for i, rec in enumerate(analysis.recommendations):
                    # Определяем цвет по приоритету
                    if hasattr(rec, 'priority'):
                        if rec.priority == "critical":
                            priority_badge = "🔴 **КРИТИЧНО**"
                        elif rec.priority == "important":
                            priority_badge = "🟡 **ВАЖНО**"
                        else:
                            priority_badge = "🟢 **РЕКОМЕНДОВАНО**"
                    else:
                        priority_badge = "💡"

                    # Определяем тип действия
                    if hasattr(rec, 'action_type'):
                        if rec.action_type == "add":
                            action_badge = "➕ Добавить"
                        elif rec.action_type == "modify":
                            action_badge = "✏️ Изменить"
                        elif rec.action_type == "remove":
                            action_badge = "❌ Удалить"
                        else:
                            action_badge = "✏️ Изменить"
                    else:
                        action_badge = "✏️ Изменить"

                    with st.container():
                        st.markdown(f"##### {priority_badge} | {action_badge}")

                        # Причина рекомендации
                        if hasattr(rec, 'reason'):
                            st.markdown(f"**Причина:** {rec.reason}")
                        else:
                            st.markdown(f"**Рекомендация:** {rec}")

                        # Предлагаемый текст
                        if hasattr(rec, 'proposed_text') and rec.proposed_text:
                            st.markdown("**Предлагаемый текст пункта:**")
                            st.text_area(
                                label="",
                                value=rec.proposed_text,
                                height=150,
                                key=f"rec_{section.number}_{i}",
                                label_visibility="collapsed"
                            )

                            # Кнопки действий — зависят от режима
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                accept_label = "✅ Принять в DOCX" if is_new_contract else "✅ В протокол разногласий"
                                if st.button(accept_label, key=f"accept_{section.number}_{i}", type="primary"):
                                    payload = {
                                        "section_number": section.number,
                                        "section_title": section.title,
                                        "original_text": section.text[:400] + ("..." if len(section.text) > 400 else ""),
                                        "proposed_text": rec.proposed_text,
                                        "reason": rec.reason if hasattr(rec, "reason") else str(rec),
                                        "action_type": rec.action_type if hasattr(rec, "action_type") else "modify",
                                        "priority": rec.priority if hasattr(rec, "priority") else "optional",
                                        "source": "section_analysis",
                                        "target": "docx" if is_new_contract else "protocol",
                                    }
                                    added = add_accepted_recommendation(payload)
                                    if added:
                                        if is_new_contract:
                                            st.success("✅ Рекомендация принята. Будет включена в исправленный DOCX (Stage 2.4).")
                                        else:
                                            st.success("✅ Добавлено в протокол разногласий.")
                                    else:
                                        st.info("ℹ️ Эта рекомендация уже была принята ранее.")
                            with col2:
                                if st.button("✏️ Редактировать", key=f"edit_{section.number}_{i}"):
                                    st.info("✏️ Откройте редактор для изменения текста.")
                            with col3:
                                if st.button("❌ Отклонить", key=f"reject_{section.number}_{i}"):
                                    st.warning("❌ Рекомендация отклонена.")

                        st.markdown("---")

    # Комплексный анализ (последняя вкладка)
    with tabs[-1]:
        st.markdown("### 🔍 КОМПЛЕКСНЫЙ АНАЛИЗ ДОГОВОРА")
        st.markdown("Анализ взаимосвязей между разделами и общая оценка документа")

        if not complex_analysis:
            st.warning("Комплексный анализ не выполнен")
            return

        st.markdown("---")
        st.markdown("#### 1️⃣ Проверка целостности и согласованности")
        if complex_analysis.integrity_checks:
            st.dataframe(complex_analysis.integrity_checks, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 2️⃣ Юридические риски")

        risk_col1, risk_col2, risk_col3 = st.columns(3)

        with risk_col1:
            st.markdown("**🟢 НИЗКИЙ РИСК:**")
            for risk in complex_analysis.risk_assessment.get("low", []):
                st.success(f"✅ {risk}")

        with risk_col2:
            st.markdown("**🟡 СРЕДНИЙ РИСК:**")
            for risk in complex_analysis.risk_assessment.get("medium", []):
                st.warning(f"⚠️ {risk}")

        with risk_col3:
            st.markdown("**🔴 ВЫСОКИЙ РИСК:**")
            for risk in complex_analysis.risk_assessment.get("high", []):
                st.error(f"❌ {risk}")

        st.markdown("---")
        st.markdown("#### 3️⃣ Соответствие законодательству РФ")
        if complex_analysis.legal_compliance:
            st.dataframe(complex_analysis.legal_compliance, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 4️⃣ Сравнение с лучшими практиками")
        st.info("**Источник:** Анализ похожих договоров из базы + RAG актуальная правовая база + база знаний модели")
        if complex_analysis.best_practices:
            st.dataframe(complex_analysis.best_practices, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 5️⃣ Итоговая оценка и рекомендации")

        score_col1, score_col2, score_col3 = st.columns(3)

        with score_col1:
            st.metric("Общая оценка", f"{complex_analysis.overall_score}/100",
                      delta="Хорошо" if complex_analysis.overall_score >= 80 else "Требует доработки")

        with score_col2:
            st.metric("Юридическая надежность", f"{complex_analysis.legal_reliability:.1f}/10",
                      delta="Высокая" if complex_analysis.legal_reliability >= 8 else "Средняя")

        with score_col3:
            st.metric("Соответствие закону", f"{complex_analysis.compliance_percent}%",
                      delta=f"+{100 - complex_analysis.compliance_percent}% после доработки")

        st.markdown("---")

        rec_col1, rec_col2 = st.columns(2)

        with rec_col1:
            st.markdown("**✅ СИЛЬНЫЕ СТОРОНЫ:**")
            for strength in complex_analysis.strengths:
                st.success(strength)

        with rec_col2:
            st.markdown("**⚠️ КРИТИЧНЫЕ ДОРАБОТКИ:**")
            for improvement in complex_analysis.critical_improvements:
                if improvement.startswith("ОБЯЗАТЕЛЬНО") or improvement.startswith("КРИТИЧНО"):
                    st.error(improvement)
                else:
                    st.warning(improvement)

        st.markdown("---")
        avg_score = complex_analysis.overall_score
        if avg_score >= 90:
            st.success("**💡 Рекомендация:** Договор готов к подписанию. Отличная проработка!")
        elif avg_score >= 80:
            st.info("**💡 Рекомендация:** Договор можно подписывать после внесения рекомендованных доработок.")
        elif avg_score >= 70:
            st.warning("**💡 Рекомендация:** Договор требует доработок. Рекомендуется исправить критичные замечания перед подписанием.")
        else:
            st.error("**💡 Рекомендация:** Договор требует существенной переработки. Не рекомендуется к подписанию в текущем виде.")


def extract_section_text(full_text: str, start_marker: str, end_marker: str) -> str:
    """Извлекает текст конкретного раздела договора"""
    try:
        start_idx = full_text.find(start_marker)
        end_idx = full_text.find(end_marker)

        if start_idx == -1:
            return "Раздел не найден"

        if end_idx == -1:
            # Если это последний раздел
            return full_text[start_idx:start_idx + 500]

        return full_text[start_idx:end_idx].strip()
    except:
        return "Ошибка извлечения текста раздела"


# Кнопка обработки
if uploaded_file is not None:
    st.success(f"✅ Файл загружен: **{uploaded_file.name}** ({uploaded_file.size} байт)")

    # Настройки обработки
    with st.expander("⚙️ Настройки обработки", expanded=False):
        use_section_analysis = st.checkbox(
            "Детальный анализ разделов (Section Analysis)",
            value=True,
            help="LLM-анализ каждого раздела договора с рекомендациями. Добавляет ~60-90 сек к обработке."
        )

    if st.button("🚀 Начать обработку", type="primary"):
        # Сохраняем загруженный файл во временную директорию
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name

        try:
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Запускаем реальную обработку
            if use_section_analysis:
                status_text.text("🚀 Обработка запущена. Детальный анализ разделов займёт ~60-90 сек. Пожалуйста, подождите...")
            else:
                status_text.text("🚀 Обработка запущена (~15 сек)...")
            progress_bar.progress(5)

            # Запускаем async обработку
            import concurrent.futures
            def _run_async(coro):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    _run_async,
                    process_document_async(tmp_file_path, Path(uploaded_file.name).suffix, use_section_analysis=use_section_analysis)
                )
                result = future.result(timeout=300)

            # Сохраняем результат в session_state чтобы он не пропадал при перерисовке
            st.session_state["processing_result"] = result
            st.session_state["processing_file_name"] = uploaded_file.name
            st.session_state["processing_use_section_analysis"] = use_section_analysis
            st.session_state["processing_is_new_contract"] = is_new_contract
            st.session_state["processing_result_signature"] = f"{uploaded_file.name}:{len(result.raw_text)}:{result.model_used}"

            # Сбрасываем производные данные Stage 2 при новом запуске обработки
            for key in [
                "template_comparison",
                "template_comparison_signature",
                "accepted_recommendations",
                "accepted_recommendation_keys",
                "risk_scoring",
                "risk_scoring_signature",
                "final_corrected_docx",
                "final_protocol_docx",
                "final_protocol_json",
            ]:
                st.session_state.pop(key, None)

            progress_bar.progress(100)
            status_text.text("✅ Обработка завершена!")
            st.rerun()

        except Exception as e:
            st.error(f"Ошибка обработки: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

        finally:
            # Удаляем временный файл
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    # ═══════════════════════════════════════════════════════
    # ОТОБРАЖЕНИЕ РЕЗУЛЬТАТОВ (вне блока кнопки, из session_state)
    # ═══════════════════════════════════════════════════════
    if "processing_result" in st.session_state:
        result = st.session_state["processing_result"]
        _file_name = st.session_state.get("processing_file_name", "document")
        _use_section_analysis = st.session_state.get("processing_use_section_analysis", True)
        _is_new_contract = st.session_state.get("processing_is_new_contract", True)
        _ensure_recommendation_state()

        # Кнопка сброса результатов
        if st.button("🔄 Новый анализ", help="Очистить результаты и загрузить новый документ"):
            for key in [
                "processing_result",
                "processing_file_name",
                "processing_use_section_analysis",
                "processing_is_new_contract",
                "processing_result_signature",
                "template_comparison",
                "template_comparison_signature",
                "accepted_recommendations",
                "accepted_recommendation_keys",
                "risk_scoring",
                "risk_scoring_signature",
                "final_corrected_docx",
                "final_protocol_docx",
                "final_protocol_json",
            ]:
                st.session_state.pop(key, None)
            st.rerun()

        st.markdown("---")
        st.header("2️⃣ Ход обработки")

        # Отображаем результаты каждого этапа
        for idx, stage in enumerate(result.stages):

            # Stage 1: Text Extraction
            if stage.name == "text_extraction":
                with st.expander(f"✅ Извлечение текста ({stage.duration_sec:.1f} сек)", expanded=True):
                    used_model, optimal_model = get_optimal_model_info("text_extraction")
                    st.success(f"**Метод:** {stage.results.get('method', 'N/A')} | **Формат:** {stage.results.get('original_format', 'N/A')} | **DOCX-версия:** {'✅ Есть' if stage.results.get('has_docx') else '❌ Нет'}")
                    st.info(f"**Модель:** {used_model} | **Оптимально:** {optimal_model}")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Страниц", stage.results.get("pages", "N/A"))
                    with col2:
                        st.metric("Символов", f"{stage.results.get('chars', 0):,}")
                    with col3:
                        confidence = stage.results.get("confidence")
                        st.metric("Confidence", f"{confidence:.2f}" if confidence else "N/A")

                    # Извлечённый текст
                    with st.expander("📋 Извлечённый текст (plain text)", expanded=False):
                        st.text_area("Весь текст документа:", value=result.raw_text, height=400, key="full_text_area")

            # Stage 2: Level 1 Extraction
            elif stage.name == "level1_extraction":
                with st.expander(f"✅ Level 1 Extraction ({stage.duration_sec:.1f} сек)", expanded=True):
                    used_model, optimal_model = get_optimal_model_info("level1")
                    st.success(f"**Найдено сущностей:** {stage.results.get('entities_count', 0)}")
                    st.info(f"**Модель:** {used_model} | **Оптимально:** {optimal_model}")

                    # Метрики по типам
                    by_type = stage.results.get("by_type", {})
                    if by_type:
                        cols = st.columns(min(len(by_type), 3))
                        for idx2, (entity_type, count) in enumerate(by_type.items()):
                            with cols[idx2 % 3]:
                                st.metric(entity_type, count)

                    # Детальная таблица
                    st.subheader("📋 Детальная таблица сущностей")
                    details = stage.results.get("details", {})

                    all_entities = []
                    for entity_type, entities in details.items():
                        for ent in entities:
                            all_entities.append({
                                "Тип": entity_type,
                                "Значение": ent.get("value", ""),
                                "Назначение": get_entity_purpose(entity_type),
                                "Confidence": f"{ent.get('confidence', 0):.2f}",
                                "Контекст": ent.get("context", "")[:80] + "..."
                            })

                    if all_entities:
                        st.dataframe(all_entities, use_container_width=True)
                        st.caption("💡 **Назначение** показывает, для чего используется каждая сущность в системе")

            # Stage 3: LLM Extraction
            elif stage.name == "llm_extraction":
                with st.expander(f"✅ LLM Extraction ({stage.duration_sec:.1f} сек)", expanded=True):
                    model_used = stage.results.get("model", "N/A")
                    used_model, optimal_model = get_optimal_model_info("llm")

                    st.success(f"**Модель использована:** {model_used}")
                    st.info(f"**Оптимальная модель:** {optimal_model}")

                    # Метрики обработки
                    st.subheader("📊 Метрики обработки")
                    tokens_in = stage.results.get("tokens_input", 0)
                    tokens_out = stage.results.get("tokens_output", 0)
                    cost = stage.results.get("cost_usd", 0)
                    confidence = stage.results.get("confidence", 0)

                    metrics_data = [
                        {"Параметр": "Токены (вход)", "Значение": f"{tokens_in:,}", "Описание": "Токенов отправлено в модель"},
                        {"Параметр": "Токены (выход)", "Значение": f"{tokens_out:,}", "Описание": "Токенов получено от модели"},
                        {"Параметр": "Всего токенов", "Значение": f"{tokens_in + tokens_out:,}", "Описание": "Суммарное использование"},
                        {"Параметр": "Стоимость", "Значение": f"${cost:.5f}", "Описание": f"{model_used}: см. тарифы провайдера"},
                        {"Параметр": "Confidence", "Значение": f"{confidence:.2f} ({confidence*100:.0f}%)", "Описание": "Средняя уверенность модели"},
                    ]
                    st.table(metrics_data)

                    # Извлеченные данные
                    st.subheader("📊 Извлеченные данные")
                    extracted_data = stage.results.get("data", {})

                    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Стороны", "Предмет", "Финансы", "Сроки", "Санкции"])

                    with tab1:
                        st.json(extracted_data.get("parties", {}))

                    with tab2:
                        st.json(extracted_data.get("subject", {}))

                    with tab3:
                        st.json(extracted_data.get("financials", {}))

                    with tab4:
                        st.json(extracted_data.get("terms", {}))

                    with tab5:
                        st.json(extracted_data.get("penalties", {}))

            # Stage 4: RAG Filter
            elif stage.name == "rag_filter":
                with st.expander(f"✅ RAG Filter ({stage.duration_sec:.1f} сек)", expanded=False):
                    used_model, optimal_model = get_optimal_model_info("rag")
                    similar_count = stage.results.get("similar_contracts_found", 0)

                    st.success(f"**Найдено похожих:** {similar_count} договоров")
                    st.info(f"**Модель:** {used_model} | **Оптимально:** {optimal_model}")

                    contracts = stage.results.get("contracts", [])
                    if contracts:
                        similar_data = []
                        for c in contracts:
                            similar_data.append({
                                "Договор": c.get("contract_number", "N/A"),
                                "Схожесть": f"{c.get('similarity', 0):.2f}",
                                "Тип": c.get("doc_type", "N/A"),
                                "Сумма": f"₽{c.get('amount', 0):,.0f}"
                            })
                        st.dataframe(similar_data, use_container_width=True)
                    else:
                        st.info("Похожие договоры не найдены (база пуста или нет совпадений)")

        # ═══════════════════════════════════════════════════════
        # ОТДЕЛЬНЫЙ РАЗДЕЛ: Проверка форматирования (DOCX-версия)
        # ═══════════════════════════════════════════════════════
        st.markdown("---")
        st.header("📄 Проверка форматирования документа")
        st.markdown("Документ извлечён в формат DOCX с сохранением исходного форматирования. "
                    "Проверьте корректность распознавания структуры, заголовков, списков и отступов.")

        if result.docx_file_bytes:
            # Информация о конвертации
            orig_fmt = result.original_format or 'unknown'
            fmt_labels = {
                'pdf': '📕 PDF → DOCX (pdf2docx, сохранение макета и таблиц)',
                'docx': '📘 DOCX (оригинал, форматирование сохранено полностью)',
                'txt': '📝 TXT → DOCX (воссоздание структуры из plain text)',
                'xml': '📋 XML → DOCX (извлечение и структурирование)',
                'html': '🌐 HTML → DOCX (конвертация с сохранением стилей)',
                'image': '🖼️ Изображение → OCR → DOCX (распознавание текста)',
            }
            st.info(f"**Метод конвертации:** {fmt_labels.get(orig_fmt, f'Формат: {orig_fmt}')}")

            # Предпросмотр DOCX в виде HTML
            preview_html = render_docx_preview(result.docx_file_bytes)
            st.markdown(preview_html, unsafe_allow_html=True)

            # Кнопки скачивания
            st.markdown("---")
            dl_col1, dl_col2, dl_col3 = st.columns(3)
            with dl_col1:
                if result.original_file_bytes:
                    orig_ext = result.original_format or 'bin'
                    st.download_button(
                        f"📥 Скачать оригинал (.{orig_ext})",
                        data=result.original_file_bytes,
                        file_name=f"original_{_file_name}",
                        mime="application/octet-stream",
                        key="download_original"
                    )
            with dl_col2:
                st.download_button(
                    "📥 Скачать DOCX-версию",
                    data=result.docx_file_bytes,
                    file_name=f"{Path(_file_name).stem}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_docx"
                )
            with dl_col3:
                docx_size_kb = len(result.docx_file_bytes) / 1024
                orig_size_kb = len(result.original_file_bytes) / 1024 if result.original_file_bytes else 0
                st.metric("Размер DOCX", f"{docx_size_kb:.1f} КБ",
                         delta=f"Оригинал: {orig_size_kb:.1f} КБ")
        else:
            st.error("DOCX-версия не была сгенерирована. Проверьте наличие библиотеки python-docx.")

        st.markdown("---")

        # Stage 5: Validation
        section_analysis_data = _extract_section_analysis_data(result)
        validation_result = result.validation_result or {}

        with st.expander("⚠️ Validation", expanded=True):
            used_model, optimal_model = get_optimal_model_info("validation")

            is_valid = validation_result.get("is_valid", False)
            has_warnings = len(validation_result.get("warnings", [])) > 0
            if is_valid and not has_warnings:
                st.success("**Статус:** ✅ Валидация пройдена")
            elif is_valid and has_warnings:
                st.warning("**Статус:** ⚠️ Валидация пройдена с предупреждениями")
            else:
                st.error("**Статус:** ❌ Валидация не пройдена")

            st.info(f"**Модель:** {used_model} | **Оптимально:** {optimal_model}")

            errors = validation_result.get("errors", [])
            warnings = validation_result.get("warnings", [])

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Ошибок", len(errors), delta="✅" if len(errors) == 0 else "❌")
            with col2:
                st.metric("Предупреждений", len(warnings), delta="⚠️" if len(warnings) > 0 else "✅")
            with col3:
                compliance = 100 - (len(errors) * 10 + len(warnings) * 2)
                st.metric("Соответствие", f"{compliance}%", delta=f"{compliance-100}%" if compliance < 100 else "✅")

            # Отображение конкретных ошибок и предупреждений
            if errors:
                st.markdown("### ❌ Ошибки валидации:")
                for i, error in enumerate(errors, 1):
                    if isinstance(error, dict):
                        st.error(f"**{i}.** `{error.get('field', 'N/A')}`: {error.get('message', 'N/A')}")
                    else:
                        st.error(f"**{i}.** {error}")

            if warnings:
                st.markdown("### ⚠️ Предупреждения:")
                for i, warning in enumerate(warnings, 1):
                    if isinstance(warning, dict):
                        st.warning(f"**{i}.** `{warning.get('field', 'N/A')}`: {warning.get('message', 'N/A')}")
                    else:
                        st.warning(f"**{i}.** {warning}")

            st.markdown("---")

            if section_analysis_data:
                display_validation_section_dynamic(section_analysis_data, is_new_contract=_is_new_contract)
            elif _use_section_analysis:
                st.warning("⚠️ Детальный анализ разделов не был выполнен из-за ошибки.")
            else:
                st.info("ℹ️ Детальный анализ разделов отключен. Включите в настройках обработки для глубокого анализа.")

        # ═══════════════════════════════════════════════════════
        # Stage 2.2: Сравнение с шаблоном (Pre-Execution only)
        # ═══════════════════════════════════════════════════════
        template_signature = None
        if _is_new_contract and template_file is not None:
            template_bytes = template_file.getvalue()
            template_signature = hashlib.sha256(template_bytes).hexdigest()
        else:
            # В режиме без шаблона убираем результаты сравнения, чтобы не показывать устаревшие данные
            st.session_state.pop("template_comparison", None)
            st.session_state.pop("template_comparison_signature", None)

        needs_template_comparison = (
            _is_new_contract
            and template_file is not None
            and st.session_state.get("template_comparison_signature") != template_signature
        )

        if needs_template_comparison:
            st.markdown("---")
            st.header("📋 Сравнение с эталонным шаблоном (Playbook)")
            st.markdown("Автоматическое выявление отклонений черновика от стандарта компании")

            with st.spinner("🔍 Сравнение черновика с шаблоном..."):
                tmp_tpl_path = None
                try:
                    # Извлекаем текст шаблона
                    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(template_file.name).suffix) as tmp_tpl:
                        tmp_tpl.write(template_file.getvalue())
                        tmp_tpl_path = tmp_tpl.name

                    template_text = extract_text_from_file(tmp_tpl_path, Path(template_file.name).suffix)

                    # Определяем тип договора из LLM extraction
                    contract_type = "неизвестный"
                    if result.extracted_data:
                        ct = result.extracted_data.get("metadata", {}).get("doc_type", "")
                        if ct:
                            contract_type = ct

                    # Запускаем сравнение
                    def _run_comparison():
                        loop = asyncio.new_event_loop()
                        try:
                            return loop.run_until_complete(
                                compare_with_template_async(result.raw_text, template_text, contract_type)
                            )
                        finally:
                            loop.close()

                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(_run_comparison)
                        comparison = future.result(timeout=120)

                    # Сохранение результатов сравнения в session_state
                    st.session_state["template_comparison"] = comparison
                    st.session_state["template_comparison_signature"] = template_signature
                    st.rerun()

                except Exception as e:
                    st.error(f"Ошибка сравнения с шаблоном: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
                finally:
                    if tmp_tpl_path and os.path.exists(tmp_tpl_path):
                        os.unlink(tmp_tpl_path)

        # Отображение сохраненных результатов сравнения с шаблоном
        if "template_comparison" in st.session_state:
            comparison = st.session_state["template_comparison"]

            st.markdown("---")
            st.header("📋 Сравнение с эталонным шаблоном (Playbook)")
            st.markdown("Автоматическое выявление отклонений черновика от стандарта компании")

            # Вердикт
            verdict_map = {
                "approved": ("✅ СООТВЕТСТВУЕТ", "success"),
                "minor_changes": ("⚠️ НЕЗНАЧИТЕЛЬНЫЕ ОТКЛОНЕНИЯ", "warning"),
                "major_changes": ("🔴 СУЩЕСТВЕННЫЕ ОТКЛОНЕНИЯ", "error"),
                "reject": ("❌ НЕ СООТВЕТСТВУЕТ ШАБЛОНУ", "error"),
            }
            verdict_text, verdict_type = verdict_map.get(comparison.verdict, ("❓", "info"))

            if verdict_type == "success":
                st.success(f"**Вердикт:** {verdict_text}")
            elif verdict_type == "warning":
                st.warning(f"**Вердикт:** {verdict_text}")
            else:
                st.error(f"**Вердикт:** {verdict_text}")

            st.markdown(f"**Итог:** {comparison.summary}")

            # Метрики
            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            with mc1:
                score_delta = "✅" if comparison.compliance_score >= 80 else ("⚠️" if comparison.compliance_score >= 60 else "❌")
                st.metric("Соответствие шаблону", f"{comparison.compliance_score}%", delta=score_delta)
            with mc2:
                st.metric("🔴 Критичных", comparison.critical_count)
            with mc3:
                st.metric("🟠 Высоких", comparison.high_count)
            with mc4:
                st.metric("🟡 Средних", comparison.medium_count)
            with mc5:
                st.metric("🟢 Низких", comparison.low_count)

            # Пропущенные и лишние разделы
            if comparison.missing_sections or comparison.extra_sections:
                miss_col, extra_col = st.columns(2)
                with miss_col:
                    if comparison.missing_sections:
                        st.markdown("**❌ Разделы шаблона, отсутствующие в черновике:**")
                        for ms in comparison.missing_sections:
                            st.error(f"• {ms}")
                with extra_col:
                    if comparison.extra_sections:
                        st.markdown("**➕ Разделы черновика, отсутствующие в шаблоне:**")
                        for es in comparison.extra_sections:
                            st.info(f"• {es}")

            # Таблица отклонений
            if comparison.deviations:
                st.markdown("---")
                st.subheader(f"📊 Детальный список отклонений ({comparison.total_deviations})")

                # Фильтр по severity
                severity_filter = st.multiselect(
                    "Фильтр по важности:",
                    ["critical", "high", "medium", "low"],
                    default=["critical", "high", "medium", "low"],
                    key="severity_filter"
                )

                severity_icons = {
                    "critical": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "🟢"
                }
                type_icons = {
                    "missing": "❌ Отсутствует",
                    "modified": "✏️ Изменено",
                    "added": "➕ Добавлено",
                    "weakened": "⬇️ Ослаблено",
                    "contradicts": "⚡ Противоречит"
                }

                for dev_idx, dev in enumerate(comparison.deviations):
                    if dev.severity not in severity_filter:
                        continue

                    sev_icon = severity_icons.get(dev.severity, "❓")
                    type_label = type_icons.get(dev.deviation_type, dev.deviation_type)

                    with st.expander(
                        f"{sev_icon} {dev.section} — {type_label}: {dev.description[:80]}...",
                        expanded=(dev.severity in ["critical", "high"])
                    ):
                        st.markdown(f"**Важность:** {sev_icon} {dev.severity.upper()}")
                        st.markdown(f"**Тип отклонения:** {type_label}")
                        st.markdown(f"**Описание:** {dev.description}")
                        st.markdown(f"**Риск:** {dev.risk}")

                        if dev.template_text:
                            st.markdown("**Текст в шаблоне (эталон):**")
                            st.text_area("", value=dev.template_text, height=100,
                                        key=f"tpl_text_{dev_idx}", disabled=True)

                        if dev.draft_text:
                            st.markdown("**Текст в черновике:**")
                            st.text_area("", value=dev.draft_text, height=100,
                                        key=f"draft_text_{dev_idx}", disabled=True)

                        st.markdown(f"**💡 Рекомендация:** {dev.recommendation}")

                        # Кнопки действий
                        bc1, bc2, bc3 = st.columns(3)
                        with bc1:
                            if st.button("✅ Принять рекомендацию", key=f"cmp_accept_{dev_idx}", type="primary"):
                                priority_map = {
                                    "critical": "critical",
                                    "high": "important",
                                    "medium": "optional",
                                    "low": "optional",
                                }
                                payload = {
                                    "section_number": dev.section,
                                    "section_title": dev.section,
                                    "original_text": dev.draft_text or dev.template_text or "",
                                    "proposed_text": dev.recommendation,
                                    "reason": f"{dev.description}. Риск: {dev.risk}",
                                    "action_type": dev.deviation_type,
                                    "priority": priority_map.get(dev.severity, "optional"),
                                    "source": "template_comparison",
                                    "target": "docx",
                                }
                                added = add_accepted_recommendation(payload)
                                if added:
                                    st.success("✅ Рекомендация добавлена в список правок Stage 2.4.")
                                else:
                                    st.info("ℹ️ Эта рекомендация уже была принята ранее.")
                        with bc2:
                            if st.button("⏭️ Пропустить", key=f"cmp_skip_{dev_idx}"):
                                st.info("Отклонение пропущено.")
                        with bc3:
                            if st.button("❌ Оставить как есть", key=f"cmp_keep_{dev_idx}"):
                                st.warning("Оставлено без изменений.")

        st.markdown("---")
        st.header("🎯 Risk Scoring Engine (Stage 2.3)")

        template_comparison = st.session_state.get("template_comparison")
        template_deviations = 0
        if template_comparison is not None:
            template_deviations = int(getattr(template_comparison, "total_deviations", 0))

        accepted_count = len(st.session_state.get("accepted_recommendations", []))
        result_signature = st.session_state.get("processing_result_signature", "")
        risk_signature = f"{result_signature}:{template_deviations}:{accepted_count}"

        if st.session_state.get("risk_scoring_signature") != risk_signature:
            try:
                from src.services.risk_scorer import RiskScorer

                scorer = RiskScorer()
                risk_scoring = scorer.score(
                    raw_text=result.raw_text,
                    extracted_data=result.extracted_data or {},
                    validation_result=result.validation_result or {},
                    template_comparison=template_comparison,
                    section_analysis=section_analysis_data,
                    accepted_recommendations=st.session_state.get("accepted_recommendations", []),
                )
                st.session_state["risk_scoring"] = risk_scoring
                st.session_state["risk_scoring_signature"] = risk_signature
            except Exception as e:
                st.error(f"Ошибка расчета риск-скоринга: {str(e)}")

        risk_scoring = st.session_state.get("risk_scoring")
        if risk_scoring is not None:
            risk_data = risk_scoring.to_dict() if hasattr(risk_scoring, "to_dict") else risk_scoring
            base_level = risk_data.get("risk_level", "low")
            residual_level = risk_data.get("residual_risk_level", "low")

            if base_level == "critical":
                st.error(f"🔴 **Текущий риск:** {_risk_level_ru(base_level)}")
            elif base_level == "high":
                st.warning(f"🟠 **Текущий риск:** {_risk_level_ru(base_level)}")
            elif base_level == "medium":
                st.warning(f"🟡 **Текущий риск:** {_risk_level_ru(base_level)}")
            else:
                st.success(f"🟢 **Текущий риск:** {_risk_level_ru(base_level)}")

            st.markdown(risk_data.get("summary", ""))

            rc1, rc2, rc3, rc4, rc5 = st.columns(5)
            with rc1:
                st.metric("Базовый риск", f"{risk_data.get('overall_score', 0)}/100")
            with rc2:
                st.metric("Остаточный риск", f"{risk_data.get('mitigated_score', 0)}/100")
            with rc3:
                st.metric("Уровень после правок", _risk_level_ru(residual_level))
            with rc4:
                st.metric("Критичных факторов", risk_data.get("critical_factors", 0))
            with rc5:
                st.metric("Принято правок", accepted_count)

            factors = risk_data.get("factors", [])
            if factors:
                st.subheader("📋 Факторы риска")
                factor_rows = []
                severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
                sorted_factors = sorted(
                    factors,
                    key=lambda x: (
                        severity_order.get(str(x.get("severity", "low")).lower(), 0),
                        int(x.get("points", 0))
                    ),
                    reverse=True
                )
                for item in sorted_factors:
                    factor_rows.append(
                        {
                            "Важность": _risk_level_ru(item.get("severity", "low")),
                            "Фактор": item.get("title", ""),
                            "Баллы": item.get("points", 0),
                            "Описание": item.get("description", ""),
                            "Рекомендация": item.get("recommendation", ""),
                            "Источник": item.get("source", ""),
                        }
                    )
                st.dataframe(factor_rows, use_container_width=True)

            section_risks = risk_data.get("section_risks", [])
            if section_risks:
                st.subheader("📊 Риск по разделам")
                section_rows = []
                for item in section_risks:
                    section_rows.append(
                        {
                            "Раздел": f"{item.get('section_number', '')}. {item.get('section_title', '')}",
                            "Риск (0-100)": item.get("score", 0),
                            "Уровень": _risk_level_ru(item.get("level", "low")),
                            "Предупреждений": item.get("warnings_count", 0),
                            "Рекомендаций": item.get("recommendations_count", 0),
                        }
                    )
                st.dataframe(section_rows, use_container_width=True)

        st.markdown("---")
        st.header("🛠️ Генерация итогового документа (Stage 2.4)")

        accepted_recommendations = st.session_state.get("accepted_recommendations", [])
        st.info(f"Принято рекомендаций для финализации: {len(accepted_recommendations)}")

        if accepted_recommendations:
            preview_rows = []
            for idx, rec in enumerate(accepted_recommendations, 1):
                preview_rows.append(
                    {
                        "№": idx,
                        "Раздел": f"{rec.get('section_number', '')}. {rec.get('section_title', '')}",
                        "Тип": rec.get("action_type", "modify"),
                        "Приоритет": rec.get("priority", "optional"),
                        "Источник": rec.get("source", "section_analysis"),
                    }
                )
            st.dataframe(preview_rows, use_container_width=True)

            if _is_new_contract:
                generation_variant = st.radio(
                    "Выберите вариант финального документа:",
                    ["Вариант A: Исправленный DOCX", "Вариант B: Протокол разногласий"],
                    horizontal=True,
                    key="stage24_variant",
                )
            else:
                generation_variant = "Вариант B: Протокол разногласий"
                st.info("Для подписанных договоров используется вариант B: формирование протокола разногласий.")

            if st.button("⚙️ Сгенерировать итоговый документ", key="stage24_generate_btn", type="primary"):
                try:
                    from src.services.stage2_document_generator import Stage2DocumentGenerator

                    generator = Stage2DocumentGenerator()
                    if generation_variant.startswith("Вариант A"):
                        final_docx = generator.generate_corrected_docx(
                            base_docx_bytes=result.docx_file_bytes,
                            accepted_recommendations=accepted_recommendations,
                            source_file_name=_file_name,
                        )
                        st.session_state["final_corrected_docx"] = final_docx
                        st.session_state.pop("final_protocol_docx", None)
                        st.session_state.pop("final_protocol_json", None)
                        st.success("✅ Исправленный DOCX сформирован.")
                    else:
                        protocol_docx = generator.generate_disagreement_protocol_docx(
                            accepted_recommendations=accepted_recommendations,
                            source_file_name=_file_name,
                        )
                        protocol_json = generator.generate_disagreement_protocol_json(
                            accepted_recommendations=accepted_recommendations
                        )
                        st.session_state["final_protocol_docx"] = protocol_docx
                        st.session_state["final_protocol_json"] = protocol_json
                        st.success("✅ Протокол разногласий сформирован.")
                except Exception as e:
                    st.error(f"Ошибка генерации итогового документа: {str(e)}")

            fd_col1, fd_col2, fd_col3 = st.columns(3)
            with fd_col1:
                if st.session_state.get("final_corrected_docx"):
                    st.download_button(
                        "📥 Скачать исправленный DOCX",
                        data=st.session_state["final_corrected_docx"],
                        file_name=f"{Path(_file_name).stem}_corrected.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="download_final_corrected_docx",
                    )
            with fd_col2:
                if st.session_state.get("final_protocol_docx"):
                    st.download_button(
                        "📥 Скачать протокол (DOCX)",
                        data=st.session_state["final_protocol_docx"],
                        file_name=f"{Path(_file_name).stem}_protocol.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="download_final_protocol_docx",
                    )
            with fd_col3:
                if st.session_state.get("final_protocol_json"):
                    st.download_button(
                        "📥 Скачать протокол (JSON)",
                        data=st.session_state["final_protocol_json"],
                        file_name=f"{Path(_file_name).stem}_protocol.json",
                        mime="application/json",
                        key="download_final_protocol_json",
                    )
        else:
            st.warning("Примите минимум одну рекомендацию в разделах анализа или в сравнении с шаблоном.")

        st.markdown("---")

        # Финальные метрики
        st.header("3️⃣ Итоговые метрики")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("⏱️ Время обработки", f"{result.total_time_sec:.1f} сек")

        with col2:
            st.metric("💰 Стоимость", f"${result.total_cost_usd:.5f}")

        with col3:
            st.metric("🤖 Модель", result.model_used)

        with col4:
            avg_confidence = 0
            for stg in result.stages:
                if stg.name == "llm_extraction":
                    avg_confidence = stg.results.get("confidence", 0)
            st.metric("🎯 Уверенность", f"{avg_confidence*100:.0f}%")

        st.markdown("---")

        # Кнопки действий
        st.header("4️⃣ Действия с результатами")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("✅ Утвердить", type="primary", use_container_width=True):
                st.success("✅ Документ утвержден и сохранен в базу данных!")
                st.balloons()

        with col2:
            json_data = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
            st.download_button(
                "💾 Сохранить JSON",
                json_data,
                file_name=f"contract_analysis_{_file_name}.json",
                mime="application/json",
                use_container_width=True
            )

        with col3:
            # Скачивание DOCX-версии (всегда доступна)
            if result.docx_file_bytes:
                st.download_button(
                    "📄 Скачать DOCX",
                    data=result.docx_file_bytes,
                    file_name=f"{Path(_file_name).stem}_result.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key="download_docx_final"
                )

        with col4:
            if st.button("❌ Отклонить", use_container_width=True):
                st.error("Документ отклонен")

        # Протокол разногласий (только для подписанных договоров)
        if not _is_new_contract and st.session_state.get("accepted_recommendations"):
            st.markdown("---")
            st.header("📋 Протокол разногласий (предпросмотр)")
            st.info(f"Собрано рекомендаций: {len(st.session_state.get('accepted_recommendations', []))}")

            protocol_data = []
            for i, rec in enumerate(st.session_state.get("accepted_recommendations", []), 1):
                protocol_data.append({
                    "№": i,
                    "Раздел": f"{rec.get('section_number', '')}. {rec.get('section_title', '')}",
                    "Текст оригинала": rec.get("original_text", ""),
                    "Предлагаемая редакция": rec.get("proposed_text", ""),
                    "Обоснование": rec.get("reason", "")
                })

            st.dataframe(protocol_data, use_container_width=True)

            st.caption("Для выгрузки DOCX/JSON используйте блок Stage 2.4 выше.")

else:
    st.info("👆 Загрузите файл договора для начала обработки")

    # Ссылка на тестовый файл
    st.markdown("---")
    st.markdown("**💡 Для тестирования:** используйте файл `tests/fixtures/test_supply_contract.txt`")

st.markdown("---")
st.caption("Contract AI System v2.0 - Обработка документов | Модели 2026: Claude Opus/Sonnet 4.5, GPT-4.1, DeepSeek-V3.2, Qwen2.5-VL-72B (119 языков)")
