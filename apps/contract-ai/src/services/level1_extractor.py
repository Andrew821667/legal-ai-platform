"""
Level 1 Extractor - Baseline Entity Extraction
Извлечение базовых сущностей с помощью regex и SpaCy (бесплатно)

Извлекает:
- Даты (различные форматы)
- Денежные суммы
- ИНН, ОГРН, КПП
- Стороны договора (организации, ФИО)
- Предмет договора (keywords)
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# SpaCy для NER
try:
    import spacy
    from spacy.language import Language
except ImportError:
    spacy = None
    Language = None

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Извлеченная сущность"""
    type: str  # 'date', 'amount', 'inn', 'org', 'person', etc.
    value: str  # Само значение
    normalized: Any  # Нормализованное значение (datetime для дат, float для сумм)
    confidence: float  # 0.0 - 1.0
    position: int  # Позиция в тексте (start char)
    context: str  # Окружающий текст (± 50 символов)
    metadata: Dict[str, Any]  # Дополнительная информация


class Level1Extractor:
    """
    Baseline extractor для базовых сущностей

    Использует:
    - Regex для structured data (ИНН, суммы, даты)
    - SpaCy NER для организаций и персон
    """

    def __init__(self, spacy_model: str = 'ru_core_news_sm'):
        """
        Args:
            spacy_model: Модель SpaCy для русского языка
        """
        self.spacy_model_name = spacy_model
        self._nlp = None

        # Regex patterns
        self.patterns = {
            # Дат: dd.mm.yyyy, dd/mm/yyyy, dd-mm-yyyy
            'date': [
                r'\b(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})\b',
                r'\b(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})\b',
            ],

            # Денежные суммы: 100 000 руб., 1,500.00 USD, 1 234,56 ₽
            'amount': [
                r'(\d[\d\s,\.]*)\s*(руб\.|рублей|рубля|₽|USD|EUR|usd|eur)',
                r'(\d[\d\s,\.]+)\s+российских\s+рубл',
            ],

            # ИНН: 10 или 12 цифр
            'inn': [
                r'\bИНН:?\s*(\d{10}|\d{12})\b',
                r'\b(\d{10}|\d{12})\b',  # Просто 10/12 цифр
            ],

            # ОГРН: 13 цифр
            'ogrn': [
                r'\bОГРН:?\s*(\d{13})\b',
                r'\b(\d{13})\b',
            ],

            # КПП: 9 цифр
            'kpp': [
                r'\bКПП:?\s*(\d{9})\b',
            ],

            # Договор номер
            'contract_number': [
                r'[Дд]оговор\s+№?\s*([А-ЯA-Z0-9\-/]+)',
                r'[Кк]онтракт\s+№?\s*([А-ЯA-Z0-9\-/]+)',
            ],
        }

    @property
    def nlp(self) -> Optional[Language]:
        """Lazy loading SpaCy модели"""
        if self._nlp is None and spacy:
            try:
                self._nlp = spacy.load(self.spacy_model_name)
                logger.info(f"SpaCy model loaded: {self.spacy_model_name}")
            except OSError:
                logger.warning(f"SpaCy model {self.spacy_model_name} not found. "
                              "Run: python -m spacy download {self.spacy_model_name}")
                self._nlp = None
        return self._nlp

    def extract(self, text: str) -> Dict[str, List[Entity]]:
        """
        Извлекает все сущности из текста

        Returns:
            Dict с ключами: 'dates', 'amounts', 'inns', 'orgs', 'persons', etc.
        """
        results = {
            'dates': self._extract_dates(text),
            'amounts': self._extract_amounts(text),
            'inns': self._extract_by_pattern(text, 'inn', self.patterns['inn']),
            'ogrns': self._extract_by_pattern(text, 'ogrn', self.patterns['ogrn']),
            'kpps': self._extract_by_pattern(text, 'kpp', self.patterns['kpp']),
            'contract_numbers': self._extract_by_pattern(text, 'contract_number',
                                                          self.patterns['contract_number']),
        }

        # SpaCy NER для организаций и персон
        if self.nlp:
            ner_results = self._extract_with_spacy(text)
            results['orgs'] = ner_results.get('orgs', [])
            results['persons'] = ner_results.get('persons', [])
            results['locations'] = ner_results.get('locations', [])

        # Предмет договора (keywords-based)
        results['contract_subject'] = self._extract_contract_subject(text)

        logger.info(f"Level1 extraction complete: "
                   f"{sum(len(v) for v in results.values())} entities found")

        return results

    def _extract_dates(self, text: str) -> List[Entity]:
        """Извлекает даты"""
        entities = []

        for pattern in self.patterns['date']:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                raw_value = match.group(0)
                position = match.start()
                context = self._get_context(text, position)

                # Нормализуем дату
                try:
                    parts = re.findall(r'\d+', raw_value)
                    if len(parts) == 3:
                        # Пробуем dd.mm.yyyy
                        if len(parts[2]) == 4:
                            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                        else:
                            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])

                        normalized = datetime(year, month, day)
                        confidence = 0.95  # High confidence for regex

                        entities.append(Entity(
                            type='date',
                            value=raw_value,
                            normalized=normalized,
                            confidence=confidence,
                            position=position,
                            context=context,
                            metadata={'format': 'dd.mm.yyyy'}
                        ))
                except ValueError:
                    # Invalid date, skip
                    continue

        return entities

    def _extract_amounts(self, text: str) -> List[Entity]:
        """Извлекает денежные суммы"""
        entities = []

        for pattern in self.patterns['amount']:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                raw_value = match.group(0)
                position = match.start()
                context = self._get_context(text, position)

                # Извлекаем число и валюту
                num_str = match.group(1)
                currency = match.group(2) if len(match.groups()) > 1 else 'RUB'

                # Нормализуем число (удаляем пробелы, меняем запятую на точку)
                num_str = num_str.replace(' ', '').replace(',', '.')

                try:
                    normalized = float(num_str)

                    # Нормализуем валюту
                    currency_map = {
                        'руб.': 'RUB', 'рублей': 'RUB', 'рубля': 'RUB', '₽': 'RUB',
                        'usd': 'USD', 'USD': 'USD',
                        'eur': 'EUR', 'EUR': 'EUR'
                    }
                    currency = currency_map.get(currency, currency)

                    entities.append(Entity(
                        type='amount',
                        value=raw_value,
                        normalized=normalized,
                        confidence=0.90,
                        position=position,
                        context=context,
                        metadata={'currency': currency, 'raw_number': num_str}
                    ))
                except ValueError:
                    continue

        return entities

    def _extract_by_pattern(self, text: str, entity_type: str,
                           patterns: List[str]) -> List[Entity]:
        """Универсальное извлечение по regex паттернам"""
        entities = []

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                raw_value = match.group(1) if match.groups() else match.group(0)
                position = match.start()
                context = self._get_context(text, position)

                # Валидация
                confidence = self._validate_entity(entity_type, raw_value)

                if confidence > 0.5:
                    entities.append(Entity(
                        type=entity_type,
                        value=raw_value,
                        normalized=raw_value,  # Already normalized
                        confidence=confidence,
                        position=position,
                        context=context,
                        metadata={}
                    ))

        return entities

    def _clean_entity_value(self, value: str) -> str:
        """Очищает значение сущности от предлогов и лишних слов"""
        # Список предлогов и служебных слов для удаления
        stopwords = [
            'в', 'на', 'с', 'по', 'из', 'к', 'до', 'для', 'от', 'при',
            'о', 'об', 'за', 'над', 'под', 'через', 'между', 'перед',
            'лице', 'лица', 'имени', 'далее',
            'именуемый', 'именуемая', 'именуемое', 'именуемые'
        ]

        cleaned = value.strip()

        # Удаляем предлоги в начале
        words = cleaned.split()
        while words and words[0].lower() in stopwords:
            words.pop(0)

        # Удаляем предлоги в конце
        while words and words[-1].lower() in stopwords:
            words.pop()

        # Убираем кавычки вокруг
        cleaned = ' '.join(words).strip()
        cleaned = cleaned.strip('"«»""')

        return cleaned if cleaned else value  # Если всё удалили - вернем оригинал

    def _extract_with_spacy(self, text: str) -> Dict[str, List[Entity]]:
        """Извлекает именованные сущности с помощью SpaCy"""
        if not self.nlp:
            return {}

        doc = self.nlp(text)

        results = {
            'orgs': [],
            'persons': [],
            'locations': []
        }

        for ent in doc.ents:
            position = ent.start_char
            context = self._get_context(text, position)

            # Очищаем значение от предлогов и лишних слов
            cleaned_value = self._clean_entity_value(ent.text)

            # Пропускаем если после очистки осталось слишком короткое значение
            if len(cleaned_value) < 2:
                continue

            entity_type_map = {
                'ORG': 'orgs',
                'PERSON': 'persons',
                'PER': 'persons',
                'LOC': 'locations',
                'GPE': 'locations'
            }

            key = entity_type_map.get(ent.label_)
            if key:
                results[key].append(Entity(
                    type=ent.label_,
                    value=cleaned_value,  # Используем очищенное значение
                    normalized=cleaned_value.strip(),
                    confidence=0.75,  # SpaCy doesn't provide confidence
                    position=position,
                    context=context,
                    metadata={'label': ent.label_, 'original_value': ent.text}
                ))

        return results

    def _extract_contract_subject(self, text: str) -> List[Entity]:
        """
        Извлекает предмет договора по ключевым словам

        Ищет фразы типа:
        - "Предмет договора: ..."
        - "на поставку ..."
        - "по оказанию услуг ..."
        """
        entities = []

        patterns = [
            r'[Пп]редмет\s+договора:?\s*([^\.]+)',
            r'на\s+поставку\s+([^\.]{10,100})',
            r'по\s+оказанию\s+услуг\s+([^\.]{10,100})',
            r'по\s+выполнению\s+работ\s+([^\.]{10,100})',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                raw_value = match.group(1).strip()
                position = match.start()
                context = self._get_context(text, position, window=100)

                entities.append(Entity(
                    type='contract_subject',
                    value=raw_value,
                    normalized=raw_value,
                    confidence=0.70,
                    position=position,
                    context=context,
                    metadata={}
                ))

        return entities

    def _get_context(self, text: str, position: int, window: int = 50) -> str:
        """Возвращает контекст вокруг позиции"""
        start = max(0, position - window)
        end = min(len(text), position + window)
        return text[start:end]

    def _validate_entity(self, entity_type: str, value: str) -> float:
        """
        Валидирует извлеченную сущность

        Returns:
            confidence score (0.0 - 1.0)
        """
        if entity_type == 'inn':
            # ИНН должен быть 10 или 12 цифр
            if len(value) in [10, 12] and value.isdigit():
                return 0.95
            return 0.0

        elif entity_type == 'ogrn':
            # ОГРН - 13 цифр
            if len(value) == 13 and value.isdigit():
                return 0.95
            return 0.0

        elif entity_type == 'kpp':
            # КПП - 9 цифр
            if len(value) == 9 and value.isdigit():
                return 0.95
            return 0.0

        elif entity_type == 'contract_number':
            # Номер договора - буквы, цифры, символы
            if len(value) > 0:
                return 0.85
            return 0.0

        return 0.5  # Default confidence
