"""
Validation Service
Pydantic схемы для валидации извлеченных данных
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from enum import Enum

logger = logging.getLogger(__name__)


# Enums
class ContractType(str, Enum):
    SUPPLY = "supply"
    SERVICE = "service"
    WORK = "work"
    MIXED = "mixed"
    OTHER = "other"


class Currency(str, Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class PaymentType(str, Enum):
    PREPAYMENT = "prepayment"
    POSTPAYMENT = "postpayment"
    INSTALLMENT = "installment"
    FINAL_PAYMENT = "final_payment"
    ADVANCE = "advance"
    MILESTONE = "milestone"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    OTHER = "other"


class RiskSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Pydantic Models
class PartyInfo(BaseModel):
    """Информация о стороне договора"""
    name: str
    inn: Optional[str] = None
    ogrn: Optional[str] = None
    kpp: Optional[str] = None
    address: Optional[str] = None
    representative: Optional[str] = None  # ФИО подписанта


class ContractParties(BaseModel):
    """Стороны договора"""
    supplier: PartyInfo
    customer: PartyInfo


class ContractSubject(BaseModel):
    """Предмет договора"""
    description: str = Field(min_length=10)
    type: ContractType


class ContractTerm(BaseModel):
    """Срок действия договора"""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_days: Optional[int] = Field(None, gt=0)

    @field_validator('start_date', 'end_date', mode='before')
    @classmethod
    def parse_date(cls, v):
        """Обрабатывает невалидные даты от LLM"""
        if v is None:
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            v = v.strip()
            if not v or v.upper() in ('YYYY-MM-DD', 'N/A', 'NULL', 'NONE', 'TBD', 'НЕТ', ''):
                return None
            try:
                return date.fromisoformat(v[:10])
            except (ValueError, IndexError):
                return None
        return None

    @field_validator('end_date')
    @classmethod
    def end_after_start(cls, v, info):
        if v and info.data.get('start_date') and v < info.data['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class Financials(BaseModel):
    """Финансовые условия"""
    total_amount: Decimal = Field(gt=0)
    currency: Currency = Currency.RUB
    vat_included: bool = True
    vat_rate: Optional[int] = Field(None, ge=0, le=100)

    @field_validator('vat_included', mode='before')
    @classmethod
    def parse_bool(cls, v):
        """LLM может вернуть строку вместо bool"""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower().strip() in ('true', 'yes', 'да', '1', 'включен', 'включено')
        return bool(v)


class PaymentScheduleItem(BaseModel):
    """Элемент платежного графика"""
    type: PaymentType = PaymentType.OTHER

    @field_validator('type', mode='before')
    @classmethod
    def normalize_payment_type(cls, v):
        """Нормализует тип платежа от LLM в допустимый enum"""
        if isinstance(v, PaymentType):
            return v
        if isinstance(v, str):
            try:
                return PaymentType(v.lower().strip())
            except ValueError:
                return PaymentType.OTHER
        return PaymentType.OTHER
    amount: Decimal = Field(gt=0)
    due_date: Optional[date] = None
    description: Optional[str] = None

    @field_validator('due_date', mode='before')
    @classmethod
    def parse_due_date(cls, v):
        """Обрабатывает невалидные даты от LLM (например 'YYYY-MM-DD', 'N/A', '')"""
        if v is None:
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            v = v.strip()
            # Отбрасываем шаблонные/пустые значения
            if not v or v.upper() in ('YYYY-MM-DD', 'N/A', 'NULL', 'NONE', 'TBD', 'НЕТ', ''):
                return None
            try:
                return date.fromisoformat(v[:10])
            except (ValueError, IndexError):
                return None
        return None


class Payment(BaseModel):
    """Условия оплаты"""
    method: str  # "bank_transfer", "cash", etc.
    terms: Optional[str] = None
    schedule: List[PaymentScheduleItem] = []


class Penalty(BaseModel):
    """Штраф / санкция"""
    type: str  # "delay", "breach", "early_termination", etc.
    amount_formula: str  # "0.1% per day", "10000 RUB fixed"
    cap: Optional[str] = None  # "10% of contract"
    description: str


class Termination(BaseModel):
    """Условия расторжения"""
    grounds: List[str] = []
    notice_period_days: Optional[int] = Field(None, ge=0)


class Risk(BaseModel):
    """Риск"""
    type: str
    description: str
    severity: RiskSeverity


class ExtractedContractData(BaseModel):
    """
    Полная схема извлеченных данных из договора

    Используется для валидации результатов LLM extraction
    """
    parties: ContractParties
    subject: ContractSubject
    term: Optional[ContractTerm] = None
    financials: Financials
    payment: Optional[Payment] = None
    obligations: Optional[Dict[str, List[str]]] = None
    penalties: List[Penalty] = []
    termination: Optional[Termination] = None
    risks: List[Risk] = []

    # Metadata
    contract_number: Optional[str] = None
    contract_date: Optional[date] = None


class ValidationResult(BaseModel):
    """Результат валидации"""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    validated_data: Optional[Dict[str, Any]] = None


class ValidationService:
    """
    Сервис валидации извлеченных данных

    Использует Pydantic для валидации и нормализации
    """

    @staticmethod
    def _clean_meta_fields(data: Any) -> Any:
        """Удаляет служебные _meta поля из LLM-ответа рекурсивно"""
        if isinstance(data, dict):
            return {
                k: ValidationService._clean_meta_fields(v)
                for k, v in data.items()
                if not k.startswith('_')
            }
        elif isinstance(data, list):
            return [ValidationService._clean_meta_fields(item) for item in data]
        return data

    @staticmethod
    def validate(data: Dict[str, Any]) -> ValidationResult:
        """
        Валидирует извлеченные данные

        Args:
            data: Dict с данными от LLM

        Returns:
            ValidationResult с результатами валидации
        """
        errors = []
        warnings = []

        try:
            # Очищаем служебные поля от LLM
            cleaned_data = ValidationService._clean_meta_fields(data)

            # Пытаемся валидировать через Pydantic
            validated = ExtractedContractData(**cleaned_data)

            # Дополнительные business-logic проверки
            additional_warnings = ValidationService._business_logic_checks(validated)
            warnings.extend(additional_warnings)

            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=warnings,
                validated_data=validated.model_dump()
            )

        except Exception as e:
            logger.warning(f"Validation failed: {e}")

            # Парсим ошибки Pydantic
            if hasattr(e, 'errors'):
                for err in e.errors():
                    field = " -> ".join(str(x) for x in err['loc'])
                    msg = err['msg']
                    errors.append(f"{field}: {msg}")
            else:
                errors.append(str(e))

            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                validated_data=None
            )

    @staticmethod
    def _business_logic_checks(data: ExtractedContractData) -> List[str]:
        """
        Дополнительные проверки business-logic

        Returns:
            List of warnings
        """
        warnings = []

        # Проверка 1: Сумма платежей = общая сумма договора
        if data.payment and data.payment.schedule:
            total_payments = sum(item.amount for item in data.payment.schedule)
            if abs(total_payments - data.financials.total_amount) > Decimal('0.01'):
                warnings.append(
                    f"Сумма платежей ({total_payments}) не совпадает с "
                    f"суммой договора ({data.financials.total_amount})"
                )

        # Проверка 2: Срок договора разумный (не более 10 лет)
        if data.term and data.term.duration_days:
            if data.term.duration_days > 3650:  # 10 years
                warnings.append(
                    f"Срок договора очень большой: {data.term.duration_days} дней "
                    f"({data.term.duration_days / 365:.1f} лет)"
                )

        # Проверка 3: ИНН присутствует у обеих сторон
        if not data.parties.supplier.inn:
            warnings.append("У поставщика отсутствует ИНН")
        if not data.parties.customer.inn:
            warnings.append("У заказчика отсутствует ИНН")

        # Проверка 4: Наличие штрафов
        if not data.penalties:
            warnings.append("В договоре не указаны штрафные санкции")

        # Проверка 5: Высокие риски
        high_risks = [r for r in data.risks if r.severity == RiskSeverity.HIGH]
        if high_risks:
            warnings.append(
                f"Обнаружено {len(high_risks)} высоких рисков: "
                f"{', '.join(r.type for r in high_risks)}"
            )

        return warnings
