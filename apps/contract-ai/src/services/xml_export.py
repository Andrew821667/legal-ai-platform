# -*- coding: utf-8 -*-
"""
XML Export Service
Экспорт договоров в XML формат
"""
from typing import Dict, Any
from datetime import datetime
from lxml import etree


class XMLExportService:
    """Сервис для экспорта договоров в XML"""

    @staticmethod
    def export_contract_to_xml(contract_data: Dict[str, Any]) -> str:
        """
        Экспорт договора в XML формат

        Args:
            contract_data: Словарь с данными договора

        Returns:
            str: XML string
        """
        # Создаем корневой элемент
        root = etree.Element("contract")
        root.set("version", "1.0")
        root.set("xmlns", "http://contract-ai-system.com/schema/v1")

        # Метаданные
        metadata = etree.SubElement(root, "metadata")
        etree.SubElement(metadata, "contract_id").text = str(contract_data.get('id', ''))
        etree.SubElement(metadata, "contract_type").text = contract_data.get('contract_type', '')
        etree.SubElement(metadata, "creation_date").text = datetime.now().isoformat()
        etree.SubElement(metadata, "status").text = contract_data.get('status', 'draft')

        # Стороны договора
        parties = etree.SubElement(root, "parties")

        for party_key in ['party_1', 'party_2']:
            party_data = contract_data.get(party_key, {})
            if party_data:
                party = etree.SubElement(parties, "party")
                party.set("role", "party_1" if party_key == "party_1" else "party_2")

                etree.SubElement(party, "type").text = party_data.get('type', '')
                etree.SubElement(party, "name").text = party_data.get('name', '')
                etree.SubElement(party, "inn").text = party_data.get('inn', '')

                if party_data.get('kpp'):
                    etree.SubElement(party, "kpp").text = party_data.get('kpp', '')
                if party_data.get('ogrn'):
                    etree.SubElement(party, "ogrn").text = party_data.get('ogrn', '')

                etree.SubElement(party, "address").text = party_data.get('address', '')

                # Банковские реквизиты
                bank_details = etree.SubElement(party, "bank_details")
                etree.SubElement(bank_details, "bank").text = party_data.get('bank', '')
                etree.SubElement(bank_details, "bik").text = party_data.get('bik', '')
                etree.SubElement(bank_details, "account").text = party_data.get('account', '')
                etree.SubElement(bank_details, "corr_account").text = party_data.get('corr_account', '')

                # Представитель
                representative = etree.SubElement(party, "representative")
                etree.SubElement(representative, "name").text = party_data.get('director', '')
                etree.SubElement(representative, "basis").text = party_data.get('basis', '')

        # Финансовые условия
        financial = contract_data.get('financial', {})
        if financial:
            terms = etree.SubElement(root, "financial_terms")
            etree.SubElement(terms, "amount").text = str(financial.get('amount', 0))
            etree.SubElement(terms, "currency").text = financial.get('currency', 'RUB')
            etree.SubElement(terms, "vat_included").text = str(financial.get('vat_included', False))
            etree.SubElement(terms, "vat_rate").text = str(financial.get('vat_rate', 0))
            etree.SubElement(terms, "payment_terms").text = str(financial.get('payment_terms', 0))
            etree.SubElement(terms, "prepayment").text = str(financial.get('prepayment', 0))
            etree.SubElement(terms, "payment_method").text = financial.get('payment_method', '')

        # Даты и сроки
        dates = contract_data.get('dates', {})
        if dates:
            timeline = etree.SubElement(root, "timeline")
            etree.SubElement(timeline, "start_date").text = str(dates.get('start_date', ''))
            etree.SubElement(timeline, "end_date").text = str(dates.get('end_date', ''))
            etree.SubElement(timeline, "auto_renewal").text = str(dates.get('auto_renewal', False))

        # Ответственность
        liability = contract_data.get('liability', {})
        if liability:
            liability_section = etree.SubElement(root, "liability")
            etree.SubElement(liability_section, "penalty_rate").text = str(liability.get('penalty_rate', 0))
            etree.SubElement(liability_section, "max_penalty").text = str(liability.get('max_penalty', 0))
            if liability.get('liability_limit'):
                etree.SubElement(liability_section, "liability_limit").text = str(liability.get('liability_limit'))
            etree.SubElement(liability_section, "force_majeure").text = str(liability.get('force_majeure', False))

        # Условия поставки (если применимо)
        delivery = contract_data.get('delivery', {})
        if delivery:
            delivery_section = etree.SubElement(root, "delivery")
            etree.SubElement(delivery_section, "method").text = delivery.get('method', '')
            etree.SubElement(delivery_section, "terms").text = delivery.get('terms', '')
            etree.SubElement(delivery_section, "address").text = delivery.get('address', '')
            etree.SubElement(delivery_section, "time_days").text = str(delivery.get('time_days', 0))

        # Подписание
        signature = contract_data.get('signature', {})
        if signature:
            signature_section = etree.SubElement(root, "signature")
            etree.SubElement(signature_section, "method").text = signature.get('method', '')
            etree.SubElement(signature_section, "copies").text = str(signature.get('copies', 2))

        # Дополнительные условия
        if contract_data.get('additional_terms'):
            additional = etree.SubElement(root, "additional_terms")
            additional.text = contract_data.get('additional_terms')

        # Генерируем красивый XML с отступами
        xml_string = etree.tostring(
            root,
            pretty_print=True,
            encoding='UTF-8',
            xml_declaration=True
        ).decode('utf-8')

        return xml_string

    @staticmethod
    def export_analysis_to_xml(analysis_data: Dict[str, Any]) -> str:
        """
        Экспорт результатов анализа в XML

        Args:
            analysis_data: Данные анализа

        Returns:
            str: XML string
        """
        root = etree.Element("contract_analysis")
        root.set("version", "1.0")

        # Метаданные
        metadata = etree.SubElement(root, "metadata")
        etree.SubElement(metadata, "analysis_id").text = str(analysis_data.get('id', ''))
        etree.SubElement(metadata, "contract_id").text = str(analysis_data.get('contract_id', ''))
        etree.SubElement(metadata, "analysis_date").text = datetime.now().isoformat()

        # Риски
        risks_section = etree.SubElement(root, "risks")
        for risk in analysis_data.get('risks', []):
            risk_elem = etree.SubElement(risks_section, "risk")
            etree.SubElement(risk_elem, "category").text = risk.get('category', '')
            etree.SubElement(risk_elem, "severity").text = risk.get('severity', '')
            etree.SubElement(risk_elem, "description").text = risk.get('description', '')

        # Рекомендации
        recommendations_section = etree.SubElement(root, "recommendations")
        for rec in analysis_data.get('recommendations', []):
            rec_elem = etree.SubElement(recommendations_section, "recommendation")
            etree.SubElement(rec_elem, "priority").text = rec.get('priority', '')
            etree.SubElement(rec_elem, "description").text = rec.get('description', '')

        xml_string = etree.tostring(
            root,
            pretty_print=True,
            encoding='UTF-8',
            xml_declaration=True
        ).decode('utf-8')

        return xml_string

    @staticmethod
    def validate_xml(xml_string: str) -> bool:
        """
        Валидация XML

        Args:
            xml_string: XML строка

        Returns:
            bool: True если валиден
        """
        try:
            etree.fromstring(xml_string.encode('utf-8'))
            return True
        except etree.XMLSyntaxError:
            return False
