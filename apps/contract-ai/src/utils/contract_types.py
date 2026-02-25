# -*- coding: utf-8 -*-
"""
Справочник типов договоров и их переводов
"""

# Словарь типов договоров
CONTRACT_TYPES = {
    "supply": "Договор поставки",
    "service": "Договор оказания услуг",
    "lease": "Договор аренды",
    "purchase": "Договор купли-продажи",
    "confidentiality": "Соглашение о конфиденциальности (NDA)",
    "employment": "Трудовой договор",
    "contract_work": "Договор подряда",
    "agency": "Агентский договор",
    "commission": "Договор комиссии",
    "loan": "Договор займа",
    "credit": "Кредитный договор",
    "insurance": "Договор страхования",
    "franchise": "Договор франчайзинга",
    "partnership": "Договор о совместной деятельности",
    "licensing": "Лицензионный договор",
    "distribution": "Дистрибьюторский договор",
    "transportation": "Договор перевозки",
    "storage": "Договор хранения",
    "warranty": "Договор поручительства",
    "pledge": "Договор залога",
}

# Обратный словарь (русское название -> английский код)
CONTRACT_TYPES_REVERSE = {v: k for k, v in CONTRACT_TYPES.items()}

# Категории договоров
CONTRACT_CATEGORIES = {
    "Торговые": ["supply", "purchase", "distribution", "commission"],
    "Услуги": ["service", "contract_work", "agency", "transportation", "storage"],
    "Недвижимость": ["lease", "pledge"],
    "Финансовые": ["loan", "credit", "warranty", "insurance"],
    "Интеллектуальная собственность": ["licensing", "franchise", "confidentiality"],
    "Трудовые": ["employment"],
    "Корпоративные": ["partnership"],
}


def get_contract_type_name(code: str) -> str:
    """Получить русское название типа договора"""
    return CONTRACT_TYPES.get(code, code)


def get_contract_type_code(name: str) -> str:
    """Получить код типа договора по русскому названию"""
    return CONTRACT_TYPES_REVERSE.get(name, name)


def get_contracts_by_category(category: str) -> list:
    """Получить список договоров по категории"""
    codes = CONTRACT_CATEGORIES.get(category, [])
    return [(code, CONTRACT_TYPES[code]) for code in codes if code in CONTRACT_TYPES]


def get_all_contract_types() -> list:
    """Получить все типы договоров в виде списка (код, название)"""
    return [(code, name) for code, name in CONTRACT_TYPES.items()]


def get_all_contract_names() -> list:
    """Получить все названия договоров на русском"""
    return list(CONTRACT_TYPES.values())


def get_all_categories() -> list:
    """Получить все категории договоров"""
    return list(CONTRACT_CATEGORIES.keys())
