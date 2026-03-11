# -*- coding: utf-8 -*-
"""
Improved pages for Contract AI System
Use these to replace functions in app.py
"""
import streamlit as st
from src.utils.auth import get_current_user, check_feature_access, show_upgrade_message, show_login_form
from src.utils.contract_types import get_all_contract_names, get_contract_type_code
from src.utils.knowledge_base import KnowledgeBaseCategory
from src.services.rag_system import RAGSystem
from src.models import get_db


def page_generator_improved():
    """Improved Generator Agent page"""
    st.title("✍️ Генератор договоров")

    # Check access
    if not check_feature_access('can_generate_contracts'):
        show_upgrade_message('Генерация договоров')
        return

    user = get_current_user()
    if not st.session_state.get('authenticated', False) or not user:
        st.warning("⚠️ Требуется авторизация")
        show_login_form()
        return
    user_id = user['id']

    st.markdown("### Создание нового договора")

    # Тип договора на русском
    contract_type_ru = st.selectbox(
        "📋 Тип договора",
        get_all_contract_names(),
        help="Выберите тип договора из списка"
    )
    contract_type = get_contract_type_code(contract_type_ru)

    # Template ID - опционально для продвинутых пользователей
    with st.expander("⚙️ Расширенные настройки (опционально)"):
        template_id = st.text_input(
            "ID шаблона",
            value="",
            help="Оставьте пустым для автоматического выбора шаблона"
        )
        use_llm_generation = st.checkbox(
            "Генерировать с помощью AI (без шаблона)",
            help="Использовать LLM для полной генерации договора"
        )

    st.markdown("---")

    # Стороны договора - expandable
    col1, col2 = st.columns(2)

    with col1:
        with st.expander("📋 Сторона 1 (Исполнитель/Поставщик)", expanded=True):
            party1_type = st.selectbox("Тип организации", ["ЮЛ", "ИП", "Физлицо"], key="p1_type")
            party1_name = st.text_input("Наименование *", key="p1_name")
            party1_inn = st.text_input("ИНН *", key="p1_inn")
            if party1_type == "ЮЛ":
                party1_kpp = st.text_input("КПП", key="p1_kpp")
                party1_ogrn = st.text_input("ОГРН", key="p1_ogrn")
            party1_address = st.text_area("Юридический адрес", key="p1_address")

            st.markdown("**Банковские реквизиты:**")
            party1_bank = st.text_input("Банк", key="p1_bank")
            party1_bik = st.text_input("БИК", key="p1_bik")
            party1_account = st.text_input("Расчётный счёт", key="p1_account")
            party1_corr_account = st.text_input("Корр. счёт", key="p1_corr")

            st.markdown("**Представитель:**")
            party1_director = st.text_input("Директор (ФИО)", key="p1_dir")
            party1_basis = st.text_input("Действует на основании", value="Устава", key="p1_basis")

    with col2:
        with st.expander("📋 Сторона 2 (Заказчик/Покупатель)", expanded=True):
            party2_type = st.selectbox("Тип организации", ["ЮЛ", "ИП", "Физлицо"], key="p2_type")
            party2_name = st.text_input("Наименование *", key="p2_name")
            party2_inn = st.text_input("ИНН *", key="p2_inn")
            if party2_type == "ЮЛ":
                party2_kpp = st.text_input("КПП", key="p2_kpp")
                party2_ogrn = st.text_input("ОГРН", key="p2_ogrn")
            party2_address = st.text_area("Юридический адрес", key="p2_address")

            st.markdown("**Банковские реквизиты:**")
            party2_bank = st.text_input("Банк", key="p2_bank")
            party2_bik = st.text_input("БИК", key="p2_bik")
            party2_account = st.text_input("Расчётный счёт", key="p2_account")
            party2_corr_account = st.text_input("Корр. счёт", key="p2_corr")

            st.markdown("**Представитель:**")
            party2_director = st.text_input("Директор (ФИО)", key="p2_dir")
            party2_basis = st.text_input("Действует на основании", value="Устава", key="p2_basis")

    st.markdown("---")

    # Условия договора
    st.subheader("📅 Сроки и даты")
    col1, col2, col3 = st.columns(3)
    with col1:
        start_date = st.date_input("Дата начала")
    with col2:
        end_date = st.date_input("Дата окончания")
    with col3:
        auto_renewal = st.checkbox("Автопролонгация")

    st.markdown("---")

    st.subheader("💰 Финансовые условия")
    col1, col2, col3 = st.columns(3)
    with col1:
        total_amount = st.number_input("Сумма договора (руб) *", min_value=0, value=100000)
        currency = st.selectbox("Валюта", ["RUB", "USD", "EUR"])
    with col2:
        vat_included = st.checkbox("НДС включен", value=True)
        vat_rate = st.number_input("Ставка НДС (%)", 0, 20, 20) if vat_included else 0
    with col3:
        payment_terms = st.number_input("Срок оплаты (дней)", 0, 365, 30)
        prepayment = st.number_input("Аванс (%)", 0, 100, 0)

    payment_method = st.selectbox(
        "Способ оплаты",
        ["Безналичный расчёт", "Наличный расчёт", "Смешанный"]
    )

    st.markdown("---")

    st.subheader("⚠️ Ответственность и санкции")
    col1, col2 = st.columns(2)
    with col1:
        penalty_rate = st.number_input(
            "Пеня за просрочку (% в день)",
            0.0, 1.0, 0.1, 0.01,
            help="Размер пени за каждый день просрочки"
        )
        max_penalty = st.number_input(
            "Максимальная неустойка (% от суммы договора)",
            0, 100, 10,
            help="Лимит неустойки"
        )
    with col2:
        liability_limit = st.number_input(
            "Лимит ответственности (руб)",
            0, 10000000, 0,
            help="0 = без ограничений"
        )
        force_majeure = st.checkbox("Включить форс-мажор", value=True)

    st.markdown("---")

    if contract_type in ['supply', 'purchase']:
        st.subheader("📦 Условия поставки")
        col1, col2 = st.columns(2)
        with col1:
            delivery_method = st.selectbox(
                "Способ доставки",
                ["Самовывоз", "Доставка продавцом", "Транспортная компания"]
            )
            delivery_terms = st.selectbox("Условия поставки (Incoterms)", ["EXW", "FCA", "DAP", "DDP"])
        with col2:
            delivery_address = st.text_area("Адрес доставки")
            delivery_time = st.number_input("Срок поставки (дней)", 1, 365, 14)

        st.markdown("---")

    st.subheader("✍️ Подписание и оформление")
    col1, col2 = st.columns(2)
    with col1:
        signature_method = st.selectbox(
            "Способ подписания",
            ["Бумажный документ", "Электронная подпись (ЭЦП)", "Простая электронная подпись"]
        )
    with col2:
        copies_count = st.number_input("Количество экземпляров", 1, 10, 2)

    st.markdown("---")

    # Дополнительные условия
    with st.expander("📝 Дополнительные условия"):
        additional_terms = st.text_area(
            "Особые условия",
            height=150,
            help="Укажите любые дополнительные условия, которые должны быть включены в договор"
        )

    st.markdown("---")

    # Кнопка генерации
    if st.button("🚀 Сгенерировать договор", type="primary", use_container_width=True):
        # Валидация
        if not party1_name or not party2_name:
            st.error("❌ Заполните наименования обеих сторон")
            return

        if not party1_inn or not party2_inn:
            st.error("❌ Заполните ИНН обеих сторон")
            return

        if total_amount <= 0:
            st.error("❌ Укажите сумму договора")
            return

        # Подготовка параметров
        params = {
            'contract_type': contract_type,
            'party_1': {
                'type': party1_type,
                'name': party1_name,
                'inn': party1_inn,
                'kpp': locals().get('party1_kpp', ''),
                'ogrn': locals().get('party1_ogrn', ''),
                'address': party1_address,
                'bank': party1_bank,
                'bik': party1_bik,
                'account': party1_account,
                'corr_account': party1_corr_account,
                'director': party1_director,
                'basis': party1_basis,
            },
            'party_2': {
                'type': party2_type,
                'name': party2_name,
                'inn': party2_inn,
                'kpp': locals().get('party2_kpp', ''),
                'ogrn': locals().get('party2_ogrn', ''),
                'address': party2_address,
                'bank': party2_bank,
                'bik': party2_bik,
                'account': party2_account,
                'corr_account': party2_corr_account,
                'director': party2_director,
                'basis': party2_basis,
            },
            'financial': {
                'amount': total_amount,
                'currency': currency,
                'vat_included': vat_included,
                'vat_rate': vat_rate if vat_included else 0,
                'payment_terms': payment_terms,
                'prepayment': prepayment,
                'payment_method': payment_method,
            },
            'dates': {
                'start_date': str(start_date),
                'end_date': str(end_date),
                'auto_renewal': auto_renewal,
            },
            'liability': {
                'penalty_rate': penalty_rate,
                'max_penalty': max_penalty,
                'liability_limit': liability_limit if liability_limit > 0 else None,
                'force_majeure': force_majeure,
            },
            'signature': {
                'method': signature_method,
                'copies': copies_count,
            },
            'additional_terms': additional_terms if additional_terms else None,
        }

        # Добавляем условия поставки если применимо
        if contract_type in ['supply', 'purchase']:
            params['delivery'] = {
                'method': delivery_method,
                'terms': delivery_terms,
                'address': delivery_address,
                'time_days': delivery_time,
            }

        with st.spinner("Генерация договора..."):
            try:
                if use_llm_generation or not template_id:
                    # Генерация с помощью LLM без шаблона
                    st.info("🤖 Генерация договора с помощью AI...")

                    from src.services.llm_contract_generator import LLMContractGenerator

                    llm_gen = LLMContractGenerator(st.session_state.llm_gateway)

                    # Формируем полные данные для генерации
                    full_params = params.copy()
                    full_params['contract_type'] = contract_type

                    # Генерируем договор
                    contract_text = llm_gen.generate_contract_from_scratch(full_params)

                    # Сохраняем результат
                    st.success("✅ Договор успешно сгенерирован с помощью AI!")

                    st.subheader("📄 Сгенерированный договор")
                    st.text_area("Текст договора", contract_text, height=400)

                    # Кнопка для скачивания
                    st.download_button(
                        "📥 Скачать договор",
                        data=contract_text,
                        file_name=f"contract_{contract_type}_{user_id}.txt",
                        mime="text/plain"
                    )

                    return
                else:
                    # Генерация по шаблону
                    from src.agents import ContractGeneratorAgent

                    agent = ContractGeneratorAgent(
                        llm_gateway=st.session_state.llm_gateway,
                        db_session=st.session_state.db_session
                    )

                    result = agent.execute({
                        'template_id': template_id if template_id else None,
                        'contract_type': contract_type,
                        'params': params,
                        'user_id': user_id
                    })

                if result and result.success:
                    st.success("✅ Договор успешно сгенерирован!")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("ID договора", result.data.get('contract_id', 'N/A'))
                    with col2:
                        st.metric("Статус", "Готов")

                    if result.data.get('file_path'):
                        st.info(f"📄 Файл сохранён: `{result.data.get('file_path')}`")

                    if result.data.get('validation_passed'):
                        st.success("✅ Валидация пройдена")
                    else:
                        st.warning("⚠️ Есть предупреждения валидации")
                        if result.data.get('validation_warnings'):
                            st.json(result.data.get('validation_warnings'))
                else:
                    # Если шаблон не найден - предложить LLM генерацию
                    st.error("❌ Не удалось сгенерировать договор по шаблону")

                    if st.button("🤖 Попробовать генерацию с помощью AI", type="primary"):
                        st.info("🤖 Генерируем договор с помощью AI...")

                        from src.services.llm_contract_generator import LLMContractGenerator

                        llm_gen = LLMContractGenerator(st.session_state.llm_gateway)

                        # Формируем полные данные для генерации
                        full_params = params.copy()
                        full_params['contract_type'] = contract_type

                        # Генерируем договор
                        contract_text = llm_gen.generate_contract_from_scratch(full_params)

                        # Сохраняем результат
                        st.success("✅ Договор успешно сгенерирован с помощью AI!")

                        st.subheader("📄 Сгенерированный договор")
                        st.text_area("Текст договора", contract_text, height=400)

                        # Кнопка для скачивания
                        st.download_button(
                            "📥 Скачать договор",
                            data=contract_text,
                            file_name=f"contract_{contract_type}_{user_id}.txt",
                            mime="text/plain"
                        )

            except Exception as e:
                st.error(f"❌ Ошибка: {str(e)}")

                # Предложить AI генерацию при ошибке
                if st.button("🤖 Попробовать генерацию с помощью AI", key="error_fallback", type="primary"):
                    try:
                        st.info("🤖 Генерируем договор с помощью AI...")

                        from src.services.llm_contract_generator import LLMContractGenerator

                        llm_gen = LLMContractGenerator(st.session_state.llm_gateway)

                        # Формируем полные данные для генерации
                        full_params = params.copy()
                        full_params['contract_type'] = contract_type

                        # Генерируем договор
                        contract_text = llm_gen.generate_contract_from_scratch(full_params)

                        # Сохраняем результат
                        st.success("✅ Договор успешно сгенерирован с помощью AI!")

                        st.subheader("📄 Сгенерированный договор")
                        st.text_area("Текст договора", contract_text, height=400)

                        # Кнопка для скачивания
                        st.download_button(
                            "📥 Скачать договор",
                            data=contract_text,
                            file_name=f"contract_{contract_type}_{user_id}.txt",
                            mime="text/plain"
                        )
                    except Exception as e2:
                        st.error(f"❌ Ошибка AI генерации: {str(e2)}")


def page_knowledge_base():
    """Knowledge base page"""
    st.title("📚 База знаний")

    st.markdown("""
    База знаний содержит структурированную информацию для анализа договоров и юридической поддержки.
    """)

    # Статистика
    kb_manager = st.session_state.get('kb_manager')
    if kb_manager:
        stats = kb_manager.get_category_statistics()

        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            st.metric("Всего документов", stats.get('total', 0))

        categories_data = [
            (KnowledgeBaseCategory.FORMS, col2),
            (KnowledgeBaseCategory.LEGAL, col3),
            (KnowledgeBaseCategory.CASE_LAW, col4),
            (KnowledgeBaseCategory.KEY_CASES, col5),
            (KnowledgeBaseCategory.TRENDS, col6),
        ]

        for category, col in categories_data:
            cat_stats = stats.get(category.value, {})
            with col:
                st.metric(
                    f"{cat_stats.get('icon', '📄')} {cat_stats.get('name', '')}",
                    cat_stats.get('count', 0)
                )

    st.markdown("---")

    # Категории
    categories_info = kb_manager.get_all_categories_info() if kb_manager else []

    for cat_data in categories_info:
        category = cat_data['category']
        info = cat_data['info']
        doc_count = cat_data['document_count']

        with st.expander(f"{info['icon']} {info['name_ru']} ({doc_count} документов)"):
            st.markdown(f"**Описание:** {info['description']}")
            st.markdown(f"**Коллекция:** `{info['collection_name']}`")

            if doc_count > 0:
                documents = kb_manager.list_documents(category)
                st.markdown("**Документы:**")
                for doc in documents[:5]:  # Показываем первые 5
                    st.markdown(f"- {doc.name}")
                if doc_count > 5:
                    st.markdown(f"... и ещё {doc_count - 5} документов")

    st.markdown("---")

    # Поиск
    st.subheader("🔍 Поиск в базе знаний")

    search_query = st.text_input("Введите запрос", placeholder="Например: договор поставки статья 506 ГК РФ")

    col1, col2 = st.columns([3, 1])
    with col1:
        selected_categories = st.multiselect(
            "Категории для поиска",
            [info['name_ru'] for info in [cat_data['info'] for cat_data in categories_info]],
            default=[info['name_ru'] for info in [cat_data['info'] for cat_data in categories_info][:3]]
        )
    with col2:
        top_k = st.number_input("Макс. результатов", 1, 20, 5)

    if st.button("Искать", type="primary"):
        if search_query:
            with st.spinner("Поиск в базе знаний..."):
                try:
                    # Map category names to collection types
                    category_map = {
                        'Гражданский кодекс РФ': RAGSystem.COLLECTION_LAWS,
                        'Трудовой кодекс РФ': RAGSystem.COLLECTION_LAWS,
                        'Налоговый кодекс РФ': RAGSystem.COLLECTION_LAWS,
                        'Судебная практика': RAGSystem.COLLECTION_CASE_LAW,
                        'Шаблоны договоров': RAGSystem.COLLECTION_TEMPLATES
                    }

                    # Initialize RAG system
                    db = next(get_db())
                    rag = RAGSystem(db_session=db)

                    # Search in selected collections
                    all_results = []
                    for category in selected_categories:
                        collection = category_map.get(category, RAGSystem.COLLECTION_KNOWLEDGE)
                        try:
                            results = rag.search(
                                query=search_query,
                                collection=collection,
                                top_k=top_k,
                                use_reranking=True
                            )
                            for doc in results:
                                doc.metadata['category'] = category
                            all_results.extend(results)
                        except Exception as e:
                            st.warning(f"⚠️ Ошибка поиска в категории {category}: {e}")

                    if all_results:
                        # Sort by score
                        all_results.sort(key=lambda x: x.score, reverse=True)
                        all_results = all_results[:top_k]

                        st.success(f"✅ Найдено результатов: {len(all_results)}")

                        for i, doc in enumerate(all_results, 1):
                            with st.expander(f"📄 Результат {i} (релевантность: {doc.score:.2%})"):
                                st.markdown(f"**Категория:** {doc.metadata.get('category', 'Не указано')}")
                                st.markdown(f"**Источник:** {doc.metadata.get('source', 'Не указано')}")
                                st.markdown("---")
                                st.markdown(doc.content)

                                if doc.metadata.get('article'):
                                    st.info(f"📖 Статья: {doc.metadata['article']}")
                                if doc.metadata.get('date'):
                                    st.caption(f"🗓️ Дата: {doc.metadata['date']}")
                    else:
                        st.warning("❌ Ничего не найдено. Попробуйте изменить запрос.")

                except Exception as e:
                    st.error(f"❌ Ошибка поиска: {e}")
                    st.info("💡 Убедитесь, что база знаний инициализирована. Используйте раздел 'Администрирование' для загрузки документов.")
        else:
            st.warning("Введите запрос для поиска")
