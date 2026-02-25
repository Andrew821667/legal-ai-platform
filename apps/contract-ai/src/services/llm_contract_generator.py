# -*- coding: utf-8 -*-
"""
LLM Contract Generator Service
Генерация договоров с помощью LLM без использования шаблонов
"""
from typing import Dict, Any
from src.services.llm_gateway import LLMGateway


class LLMContractGenerator:
    """Сервис для генерации договоров с помощью LLM"""

    def __init__(self, llm_gateway: LLMGateway):
        """
        Инициализация

        Args:
            llm_gateway: LLM Gateway для работы с моделями
        """
        self.llm_gateway = llm_gateway

    def generate_contract_from_scratch(self, contract_data: Dict[str, Any]) -> str:
        """
        Генерация договора с нуля с помощью LLM

        Args:
            contract_data: Данные договора

        Returns:
            str: Текст договора
        """
        contract_type = contract_data.get('contract_type', 'supply')
        party_1 = contract_data.get('party_1', {})
        party_2 = contract_data.get('party_2', {})
        financial = contract_data.get('financial', {})
        dates = contract_data.get('dates', {})
        liability = contract_data.get('liability', {})
        delivery = contract_data.get('delivery', {})
        signature = contract_data.get('signature', {})
        additional_terms = contract_data.get('additional_terms', '')

        # Формируем промпт для генерации договора
        prompt = self._build_contract_prompt(
            contract_type,
            party_1,
            party_2,
            financial,
            dates,
            liability,
            delivery,
            signature,
            additional_terms
        )

        # Генерируем договор с помощью LLM
        contract_text = self.llm_gateway.call(
            prompt=prompt,
            temperature=0.3,  # Низкая температура для более консистентной генерации
            max_tokens=4000
        )

        return contract_text

    def _build_contract_prompt(
        self,
        contract_type: str,
        party_1: Dict,
        party_2: Dict,
        financial: Dict,
        dates: Dict,
        liability: Dict,
        delivery: Dict,
        signature: Dict,
        additional_terms: str
    ) -> str:
        """
        Построение промпта для генерации договора

        Args:
            contract_type: Тип договора
            party_1: Данные первой стороны
            party_2: Данные второй стороны
            financial: Финансовые условия
            dates: Сроки
            liability: Ответственность
            delivery: Условия поставки
            signature: Подписание
            additional_terms: Дополнительные условия

        Returns:
            str: Промпт для LLM
        """
        # Определяем название типа договора
        contract_type_names = {
            'supply': 'Договор поставки',
            'service': 'Договор оказания услуг',
            'lease': 'Договор аренды',
            'purchase': 'Договор купли-продажи',
            'confidentiality': 'Соглашение о конфиденциальности (NDA)',
            'employment': 'Трудовой договор',
            'contracting': 'Договор подряда',
            'agency': 'Агентский договор',
            'commission': 'Договор комиссии',
            'loan': 'Договор займа',
            'license': 'Лицензионный договор',
            'franchise': 'Договор франчайзинга',
            'partnership': 'Договор о партнёрстве',
            'investment': 'Инвестиционный договор',
            'joint_activity': 'Договор о совместной деятельности',
            'shareholders': 'Акционерное соглашение',
            'pledge': 'Договор залога',
            'insurance': 'Договор страхования',
            'transportation': 'Договор перевозки',
            'storage': 'Договор хранения'
        }

        contract_name = contract_type_names.get(contract_type, 'Договор')

        prompt = f"""Создай полный текст юридически корректного договора на русском языке.

ТИП ДОГОВОРА: {contract_name}

СТОРОНЫ ДОГОВОРА:

Сторона 1 ({party_1.get('type', 'ЮЛ')}):
- Наименование: {party_1.get('name', '')}
- ИНН: {party_1.get('inn', '')}
- КПП: {party_1.get('kpp', '')}
- ОГРН: {party_1.get('ogrn', '')}
- Адрес: {party_1.get('address', '')}
- Банк: {party_1.get('bank', '')}
- БИК: {party_1.get('bik', '')}
- Расчётный счёт: {party_1.get('account', '')}
- Корр. счёт: {party_1.get('corr_account', '')}
- Представитель: {party_1.get('director', '')}, действующий на основании {party_1.get('basis', 'Устава')}

Сторона 2 ({party_2.get('type', 'ЮЛ')}):
- Наименование: {party_2.get('name', '')}
- ИНН: {party_2.get('inn', '')}
- КПП: {party_2.get('kpp', '')}
- ОГРН: {party_2.get('ogrn', '')}
- Адрес: {party_2.get('address', '')}
- Банк: {party_2.get('bank', '')}
- БИК: {party_2.get('bik', '')}
- Расчётный счёт: {party_2.get('account', '')}
- Корр. счёт: {party_2.get('corr_account', '')}
- Представитель: {party_2.get('director', '')}, действующий на основании {party_2.get('basis', 'Устава')}

ФИНАНСОВЫЕ УСЛОВИЯ:
- Сумма договора: {financial.get('amount', 0):,.2f} {financial.get('currency', 'RUB')}
- НДС: {'включён' if financial.get('vat_included') else 'не включён'} ({financial.get('vat_rate', 0)}%)
- Срок оплаты: {financial.get('payment_terms', 0)} дней
- Аванс: {financial.get('prepayment', 0)}%
- Способ оплаты: {financial.get('payment_method', 'Безналичный расчёт')}

СРОКИ:
- Дата начала: {dates.get('start_date', '')}
- Дата окончания: {dates.get('end_date', '')}
- Автопролонгация: {'Да' if dates.get('auto_renewal') else 'Нет'}

ОТВЕТСТВЕННОСТЬ:
- Пеня за просрочку: {liability.get('penalty_rate', 0)}% в день
- Максимальная неустойка: {liability.get('max_penalty', 0)}% от суммы договора
- Лимит ответственности: {liability.get('liability_limit', 'Без ограничений')}
- Форс-мажор: {'Предусмотрен' if liability.get('force_majeure') else 'Не предусмотрен'}
"""

        if delivery:
            prompt += f"""
УСЛОВИЯ ПОСТАВКИ:
- Способ доставки: {delivery.get('method', '')}
- Условия: {delivery.get('terms', '')}
- Адрес доставки: {delivery.get('address', '')}
- Срок поставки: {delivery.get('time_days', 0)} дней
"""

        prompt += f"""
ПОДПИСАНИЕ:
- Способ подписания: {signature.get('method', 'Бумажный документ')}
- Количество экземпляров: {signature.get('copies', 2)}
"""

        if additional_terms:
            prompt += f"""
ДОПОЛНИТЕЛЬНЫЕ УСЛОВИЯ:
{additional_terms}
"""

        prompt += """

ТРЕБОВАНИЯ К ГЕНЕРАЦИИ:
1. Договор должен быть полным и юридически корректным
2. Включи все обязательные разделы для данного типа договора:
   - Преамбула с указанием сторон
   - Предмет договора
   - Права и обязанности сторон
   - Цена и порядок расчётов
   - Сроки действия договора
   - Ответственность сторон
   - Порядок разрешения споров
   - Прочие условия
   - Реквизиты и подписи сторон
3. Используй профессиональный юридический язык
4. Ссылайся на соответствующие статьи Гражданского кодекса РФ
5. Все суммы указывай цифрами и прописью
6. Нумеруй пункты и подпункты
7. Договор должен быть готов к подписанию

НАЧНИ ГЕНЕРАЦИЮ ДОГОВОРА:
"""

        return prompt

    def generate_contract_analysis_prompt(self, contract_text: str) -> str:
        """
        Генерация промпта для анализа договора

        Args:
            contract_text: Текст договора

        Returns:
            str: Промпт для анализа
        """
        prompt = f"""Проанализируй следующий договор и выдай заключение:

ТЕКСТ ДОГОВОРА:
{contract_text}

ТРЕБОВАНИЯ К АНАЛИЗУ:
1. Проверь полноту и корректность всех разделов
2. Выяви потенциальные риски
3. Дай рекомендации по улучшению
4. Проверь соответствие законодательству РФ

Предоставь анализ в структурированном виде.
"""
        return prompt
