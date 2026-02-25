# -*- coding: utf-8 -*-
"""
Pydantic schemas for IDP (Intelligent Document Processing)
Валидация Intermediate JSON и результатов извлечения
"""
from typing import List, Optional, Dict, Any, Literal
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, validator, root_validator
import re


# ============================================================
# Intermediate JSON Schemas
# ============================================================

class PartySchema(BaseModel):
    """Сторона договора"""
    role: Literal['buyer', 'seller', 'guarantor', 'agent']
    name: str = Field(..., min_length=2, max_length=500)
    inn: Optional[str] = Field(None, regex=r'^\d{10}|\d{12}$')
    ogrn: Optional[str] = Field(None, regex=r'^\d{13}|\d{15}$')
    legal_address: Optional[str] = None
    actual_address: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    bank_details: Optional[Dict[str, Any]] = None

    @validator('inn')
    def validate_inn_checksum(cls, v):
        """Валидация контрольной суммы ИНН"""
        if v is None:
            return v

        if len(v) not in [10, 12]:
            raise ValueError('INN must be 10 or 12 digits')

        # Проверка контрольной суммы для 10-значного ИНН
        if len(v) == 10:
            coefficients = [2, 4, 10, 3, 5, 9, 4, 6, 8]
            check_digit = sum(int(v[i]) * coefficients[i] for i in range(9)) % 11 % 10
            if check_digit != int(v[9]):
                raise ValueError('Invalid INN checksum')

        # Проверка контрольной суммы для 12-значного ИНН
        elif len(v) == 12:
            coefficients1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
            coefficients2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]

            check_digit1 = sum(int(v[i]) * coefficients1[i] for i in range(10)) % 11 % 10
            check_digit2 = sum(int(v[i]) * coefficients2[i] for i in range(11)) % 11 % 10

            if check_digit1 != int(v[10]) or check_digit2 != int(v[11]):
                raise ValueError('Invalid INN checksum')

        return v


class ContractItemSchema(BaseModel):
    """Позиция спецификации"""
    line_number: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=1000)
    description: Optional[str] = None
    quantity: Decimal = Field(..., gt=0, max_digits=15, decimal_places=3)
    unit: Optional[str] = Field(None, max_length=20)
    price: Decimal = Field(..., ge=0, max_digits=15, decimal_places=2)
    total: Decimal = Field(..., ge=0, max_digits=15, decimal_places=2)
    sku: Optional[str] = Field(None, max_length=100)
    vat_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    vat_amount: Optional[Decimal] = Field(None, ge=0)
    attributes: Optional[Dict[str, Any]] = None

    @root_validator
    def validate_total(cls, values):
        """Валидация: total должна быть близка к quantity * price"""
        quantity = values.get('quantity')
        price = values.get('price')
        total = values.get('total')

        if quantity and price and total:
            expected_total = quantity * price
            # Допускаем погрешность 1% (из-за округления)
            if abs(total - expected_total) > expected_total * Decimal('0.01'):
                raise ValueError(
                    f'Total {total} does not match quantity {quantity} * price {price} = {expected_total}'
                )

        return values


class PaymentScheduleSchema(BaseModel):
    """Условие оплаты"""
    type: Literal['prepayment', 'postpayment', 'milestone', 'recurring', 'on_delivery']
    amount: Decimal = Field(..., ge=0, max_digits=15, decimal_places=2)
    percentage: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=2)
    due_date: Optional[date] = None
    condition: Optional[str] = None
    days_offset: Optional[int] = None
    trigger: Optional[str] = None

    @root_validator
    def validate_due_info(cls, values):
        """Должна быть указана либо абсолютная дата, либо условие"""
        due_date = values.get('due_date')
        condition = values.get('condition')

        if not due_date and not condition:
            raise ValueError('Either due_date or condition must be specified')

        return values


class RuleFormulaSchema(BaseModel):
    """Формула расчета для правила"""
    type: Literal['penalty', 'termination', 'compensation', 'sla']
    rate: Optional[Decimal] = Field(None, ge=0, le=1, decimal_places=6)
    base: Optional[str] = None  # outstanding_balance, contract_value, item_price
    period: Optional[Literal['daily', 'weekly', 'monthly', 'one_time']] = None
    cap: Optional[Decimal] = Field(None, ge=0, le=1)  # Максимум (например, 10% = 0.10)
    min_amount: Optional[Decimal] = Field(None, ge=0)
    notice_period_days: Optional[int] = Field(None, ge=0)
    compensation_type: Optional[str] = None


class ContractRuleSchema(BaseModel):
    """Правило ответственности (штрафы, расторжение и т.д.)"""
    rule_type: Literal['penalty', 'termination', 'sla', 'force_majeure', 'dispute', 'confidentiality']
    title: str = Field(..., min_length=5, max_length=200)
    trigger_condition: Optional[str] = None
    formula: RuleFormulaSchema
    original_text: str = Field(..., min_length=10)
    xpath: Optional[str] = None
    affected_party: Optional[Literal['buyer', 'seller', 'both']] = None
    legal_basis: Optional[str] = None
    confidence: Optional[Decimal] = Field(None, ge=0, le=1, decimal_places=2)


class IntermediateJSONSchema(BaseModel):
    """
    Промежуточный формат данных между извлечением и сохранением в БД
    Это "контракт" между IDP процессором и SchemaMapper
    """
    # Обязательные поля
    doc_number: str = Field(..., min_length=1, max_length=100)

    # Опциональные стандартные поля
    signed_date: Optional[date] = None
    contract_type: Optional[str] = Field(None, max_length=50)
    total_amount: Optional[Decimal] = Field(None, ge=0, max_digits=15, decimal_places=2)
    currency: Optional[str] = Field('RUB', regex=r'^[A-Z]{3}$')

    # Структурированные данные
    parties: Optional[List[PartySchema]] = []
    items: Optional[List[ContractItemSchema]] = []
    payment_schedule: Optional[List[PaymentScheduleSchema]] = []
    rules: Optional[List[ContractRuleSchema]] = []

    # Гибкие атрибуты (все остальное)
    attributes: Optional[Dict[str, Any]] = {}

    # Метаданные обработки
    processing_metadata: Optional[Dict[str, Any]] = {}

    @validator('parties')
    def validate_parties_count(cls, v):
        """Должно быть хотя бы 2 стороны (покупатель и продавец)"""
        if v and len(v) < 2:
            raise ValueError('Contract must have at least 2 parties')
        return v

    @root_validator
    def validate_payment_schedule_total(cls, values):
        """Сумма платежей должна быть близка к total_amount"""
        total_amount = values.get('total_amount')
        payment_schedule = values.get('payment_schedule', [])

        if total_amount and payment_schedule:
            payments_sum = sum(p.amount for p in payment_schedule)

            # Допускаем погрешность 2%
            if abs(payments_sum - total_amount) > total_amount * Decimal('0.02'):
                raise ValueError(
                    f'Sum of payments {payments_sum} does not match total_amount {total_amount}'
                )

        return values


# ============================================================
# API Request/Response Schemas
# ============================================================

class IDPUploadRequest(BaseModel):
    """Запрос на обработку документа"""
    enable_idp: bool = True
    idp_mode: Literal['auto', 'fast', 'deep'] = 'auto'


class IDPUploadResponse(BaseModel):
    """Ответ после загрузки документа"""
    contract_id: str
    file_name: str
    file_size: int
    status: str
    message: str


class IDPStageStatus(BaseModel):
    """Статус этапа обработки"""
    stage: Literal['classification', 'ocr', 'layout_analysis',
                   'entity_extraction', 'validation', 'storage']
    status: Literal['success', 'partial', 'failed', 'running']
    duration_ms: Optional[int] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class IDPProcessingStatus(BaseModel):
    """Общий статус IDP обработки"""
    contract_id: str
    status: Literal['processing', 'completed', 'failed']
    current_stage: str
    progress: float = Field(..., ge=0, le=100)
    stages: List[IDPStageStatus]
    total_cost_usd: Decimal
    total_tokens: int
    estimated_completion_sec: Optional[int] = None


class IDPQualityIssue(BaseModel):
    """Проблема качества извлечения"""
    issue_type: Literal['low_ocr_confidence', 'missing_field',
                        'ambiguous_value', 'validation_error', 'conflicting_data']
    severity: Literal['critical', 'warning', 'info']
    field_name: Optional[str] = None
    description: str
    suggested_action: Optional[str] = None
    requires_manual_review: bool = False


class ContractCoreResponse(BaseModel):
    """Ответ с данными из contracts_core"""
    id: str
    doc_number: str
    signed_date: Optional[date] = None
    status: str
    total_amount: Optional[Decimal] = None
    currency: str
    attributes: Dict[str, Any] = {}


class ContractPartyResponse(BaseModel):
    """Ответ со стороной договора"""
    role: str
    name: str
    tax_id: Optional[str] = None
    legal_address: Optional[str] = None


class ContractItemResponse(BaseModel):
    """Ответ с позицией спецификации"""
    line_number: int
    name: str
    quantity: Decimal
    unit: Optional[str] = None
    price_unit: Decimal
    total: Decimal


class PaymentScheduleResponse(BaseModel):
    """Ответ с условием оплаты"""
    type: str
    amount: Decimal
    due_date: Optional[date] = None
    condition: Optional[str] = None
    status: str


class ContractRuleResponse(BaseModel):
    """Ответ с правилом"""
    type: str
    name: str
    trigger: Optional[str] = None
    formula: Dict[str, Any]
    original_text: str
    confidence: Optional[Decimal] = None


class IDPResultResponse(BaseModel):
    """Полный результат IDP обработки"""
    contract: ContractCoreResponse
    parties: List[ContractPartyResponse]
    items: List[ContractItemResponse]
    payment_schedule: List[PaymentScheduleResponse]
    rules: List[ContractRuleResponse]
    quality_issues: List[IDPQualityIssue] = []

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            date: lambda v: v.isoformat()
        }


# ============================================================
# Validation Helpers
# ============================================================

def validate_intermediate_json(data: dict) -> IntermediateJSONSchema:
    """
    Валидация Intermediate JSON с детальными ошибками

    Raises:
        ValidationError: С детальным описанием проблем
    """
    try:
        return IntermediateJSONSchema(**data)
    except Exception as e:
        # Логируем детали ошибки
        from loguru import logger
        logger.error(f"Intermediate JSON validation failed: {e}")
        logger.debug(f"Invalid data: {data}")
        raise


def create_quality_issue_from_validation_error(
    contract_id: str,
    error: Exception,
    field_name: str
) -> Dict[str, Any]:
    """
    Создает IDPQualityIssue из ошибки валидации
    """
    return {
        'contract_id': contract_id,
        'issue_type': 'validation_error',
        'severity': 'warning',
        'field_name': field_name,
        'description': str(error),
        'suggested_action': 'Manual review required',
        'requires_manual_review': True
    }


# Экспорт
__all__ = [
    'PartySchema',
    'ContractItemSchema',
    'PaymentScheduleSchema',
    'ContractRuleSchema',
    'RuleFormulaSchema',
    'IntermediateJSONSchema',
    'IDPUploadRequest',
    'IDPUploadResponse',
    'IDPProcessingStatus',
    'IDPStageStatus',
    'IDPQualityIssue',
    'IDPResultResponse',
    'validate_intermediate_json',
    'create_quality_issue_from_validation_error',
]
