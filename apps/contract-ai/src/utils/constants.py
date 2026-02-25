# -*- coding: utf-8 -*-
"""
Constants для Contract AI System

Централизованное определение всех магических чисел и строк
"""

# ============================================================================
# ФАЙЛЫ И ЗАГРУЗКА
# ============================================================================

# Размеры файлов
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MIN_FILE_SIZE_BYTES = 10  # 10 bytes
MAX_FILENAME_LENGTH = 255  # characters

# Размеры для обработки
MAX_XML_DEPTH = 100  # Максимальная глубина XML дерева
MAX_XML_ELEMENTS = 10000  # Максимальное количество элементов в XML

# ============================================================================
# LLM И АНАЛИЗ
# ============================================================================

# Батчинг и лимиты
DEFAULT_BATCH_SIZE = 15  # Оптимально для gpt-4o-mini
MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 30

# Длины для обработки LLM
MIN_CLAUSE_LENGTH = 5  # Минимальная длина пункта для анализа
MIN_TEXT_LENGTH = 10  # Минимальная длина текста
MAX_CLAUSES_TO_ANALYZE = 50  # Максимум пунктов для анализа за раз

# Токены
CHARS_PER_TOKEN_ESTIMATE = 4  # Примерное количество символов на токен
DEFAULT_MAX_TOKENS = 4000
DEFAULT_TEMPERATURE = 0.0

# Семплирование XML для LLM
XML_SAMPLE_LENGTH_FOR_METADATA = 3000  # chars
XML_SAMPLE_LENGTH_FOR_CLASSIFICATION = 2000  # chars
XML_SAMPLE_LENGTH_FOR_PARAMETERS = 4000  # chars

# ============================================================================
# RATE LIMITING
# ============================================================================

# Дефолтные лимиты
DEFAULT_REQUESTS_PER_MINUTE = 60
DEFAULT_TOKENS_PER_MINUTE = 100000  # 100k TPM (50% от gpt-4o-mini)
DEFAULT_COST_PER_HOUR = 5.0  # $5/hour
DEFAULT_COST_PER_DAY = 50.0  # $50/day

# ============================================================================
# БАЗА ДАННЫХ
# ============================================================================

# Лимиты для сохранения в БД
MAX_PROMPT_LENGTH_IN_CACHE = 5000  # chars
MAX_SYSTEM_PROMPT_LENGTH_IN_CACHE = 2000  # chars
MAX_RESPONSE_LENGTH_IN_CACHE = 10000  # chars

# ============================================================================
# РИСКИ И ОЦЕНКИ
# ============================================================================

# Пороги для рисков
RISK_SCORE_CRITICAL = 8.0  # >= 8.0 - критический
RISK_SCORE_HIGH = 6.0  # >= 6.0 - высокий
RISK_SCORE_MEDIUM = 4.0  # >= 4.0 - средний
RISK_SCORE_LOW = 2.0  # >= 2.0 - низкий
# < 2.0 - информационный

# Веса для расчета общего риска
RISK_WEIGHT_FINANCIAL = 0.35
RISK_WEIGHT_LEGAL = 0.30
RISK_WEIGHT_OPERATIONAL = 0.20
RISK_WEIGHT_REPUTATIONAL = 0.15

# ============================================================================
# ВРЕМЕННЫЕ ИНТЕРВАЛЫ
# ============================================================================

# Таймауты
DEFAULT_LLM_TIMEOUT = 120  # seconds
DEFAULT_API_TIMEOUT = 30  # seconds
DEFAULT_DB_TIMEOUT = 10  # seconds

# Retry
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_WAIT_MIN = 2  # seconds
DEFAULT_RETRY_WAIT_MAX = 10  # seconds

# Кэш
CACHE_CLEANUP_INTERVAL = 3600  # 1 hour in seconds
CACHE_MAX_AGE = 86400  # 24 hours in seconds

# ============================================================================
# ЭКСПОРТ И ФОРМАТИРОВАНИЕ
# ============================================================================

# Размеры для экспорта
PDF_PAGE_WIDTH = 210  # mm (A4)
PDF_PAGE_HEIGHT = 297  # mm (A4)
PDF_MARGIN = 20  # mm

# Лимиты для отчетов
MAX_RISKS_IN_REPORT = 100
MAX_RECOMMENDATIONS_IN_REPORT = 50
MAX_CHANGES_IN_REPORT = 200

# ============================================================================
# ВАЛИДАЦИЯ
# ============================================================================

# Регулярные выражения (компилированные для производительности)
import re

DANGEROUS_FILENAME_PATTERNS = [
    re.compile(r'\.\.'),  # Path traversal
    re.compile(r'[\\/]'),  # Path separators
    re.compile(r'[<>:"|?*]'),  # Invalid Windows chars
    re.compile(r'^\.'),  # Hidden files
    re.compile(r'\x00'),  # Null bytes
]

# ИНН и другие идентификаторы
INN_LENGTH_INDIVIDUAL = 12  # ИНН физлица
INN_LENGTH_LEGAL = 10  # ИНН юрлица
OGRN_LENGTH = 13  # ОГРН
KPP_LENGTH = 9  # КПП

# ============================================================================
# RAG СИСТЕМА
# ============================================================================

# Параметры поиска
DEFAULT_RAG_TOP_K = 5  # Количество результатов
DEFAULT_RAG_SIMILARITY_THRESHOLD = 0.7  # Порог схожести
MAX_RAG_RESULTS = 20  # Максимум результатов

# Embedding
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_VECTOR_SIZE = 384  # Размер вектора для MiniLM

# ============================================================================
# СТОИМОСТЬ (pricing per 1M tokens)
# ============================================================================

# Цены актуальны на момент создания
PRICING_GPT4O_MINI_INPUT = 0.15  # $0.15 per 1M input tokens
PRICING_GPT4O_MINI_OUTPUT = 0.60  # $0.60 per 1M output tokens

PRICING_GPT4O_INPUT = 2.50  # $2.50 per 1M input tokens
PRICING_GPT4O_OUTPUT = 10.00  # $10.00 per 1M output tokens

PRICING_GPT4_TURBO_INPUT = 10.00  # $10.00 per 1M input tokens
PRICING_GPT4_TURBO_OUTPUT = 30.00  # $30.00 per 1M output tokens

# ============================================================================
# ПРОЧИЕ КОНСТАНТЫ
# ============================================================================

# Форматы дат
DATE_FORMAT_ISO = "%Y-%m-%d"
DATETIME_FORMAT_ISO = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT_RU = "%d.%m.%Y"
DATETIME_FORMAT_RU = "%d.%m.%Y %H:%M:%S"

# Кодировки
DEFAULT_ENCODING = "utf-8"
FALLBACK_ENCODING = "cp1251"  # Windows Cyrillic

# Логирование
LOG_ROTATION_SIZE = "10 MB"
LOG_RETENTION_DAYS = 7
LOG_LEVEL_DEFAULT = "INFO"
LOG_LEVEL_DEBUG = "DEBUG"


__all__ = [
    # File limits
    "MAX_FILE_SIZE_BYTES",
    "MIN_FILE_SIZE_BYTES",
    "MAX_FILENAME_LENGTH",
    "MAX_XML_DEPTH",
    "MAX_XML_ELEMENTS",

    # LLM limits
    "DEFAULT_BATCH_SIZE",
    "MIN_BATCH_SIZE",
    "MAX_BATCH_SIZE",
    "MIN_CLAUSE_LENGTH",
    "MIN_TEXT_LENGTH",
    "MAX_CLAUSES_TO_ANALYZE",
    "CHARS_PER_TOKEN_ESTIMATE",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TEMPERATURE",
    "XML_SAMPLE_LENGTH_FOR_METADATA",
    "XML_SAMPLE_LENGTH_FOR_CLASSIFICATION",
    "XML_SAMPLE_LENGTH_FOR_PARAMETERS",

    # Rate limiting
    "DEFAULT_REQUESTS_PER_MINUTE",
    "DEFAULT_TOKENS_PER_MINUTE",
    "DEFAULT_COST_PER_HOUR",
    "DEFAULT_COST_PER_DAY",

    # Database
    "MAX_PROMPT_LENGTH_IN_CACHE",
    "MAX_SYSTEM_PROMPT_LENGTH_IN_CACHE",
    "MAX_RESPONSE_LENGTH_IN_CACHE",

    # Risks
    "RISK_SCORE_CRITICAL",
    "RISK_SCORE_HIGH",
    "RISK_SCORE_MEDIUM",
    "RISK_SCORE_LOW",
    "RISK_WEIGHT_FINANCIAL",
    "RISK_WEIGHT_LEGAL",
    "RISK_WEIGHT_OPERATIONAL",
    "RISK_WEIGHT_REPUTATIONAL",

    # Timeouts
    "DEFAULT_LLM_TIMEOUT",
    "DEFAULT_API_TIMEOUT",
    "DEFAULT_DB_TIMEOUT",
    "DEFAULT_RETRY_ATTEMPTS",
    "DEFAULT_RETRY_WAIT_MIN",
    "DEFAULT_RETRY_WAIT_MAX",
    "CACHE_CLEANUP_INTERVAL",
    "CACHE_MAX_AGE",

    # Export
    "PDF_PAGE_WIDTH",
    "PDF_PAGE_HEIGHT",
    "PDF_MARGIN",
    "MAX_RISKS_IN_REPORT",
    "MAX_RECOMMENDATIONS_IN_REPORT",
    "MAX_CHANGES_IN_REPORT",

    # Validation
    "DANGEROUS_FILENAME_PATTERNS",
    "INN_LENGTH_INDIVIDUAL",
    "INN_LENGTH_LEGAL",
    "OGRN_LENGTH",
    "KPP_LENGTH",

    # RAG
    "DEFAULT_RAG_TOP_K",
    "DEFAULT_RAG_SIMILARITY_THRESHOLD",
    "MAX_RAG_RESULTS",
    "DEFAULT_EMBEDDING_MODEL",
    "EMBEDDING_VECTOR_SIZE",

    # Pricing
    "PRICING_GPT4O_MINI_INPUT",
    "PRICING_GPT4O_MINI_OUTPUT",
    "PRICING_GPT4O_INPUT",
    "PRICING_GPT4O_OUTPUT",
    "PRICING_GPT4_TURBO_INPUT",
    "PRICING_GPT4_TURBO_OUTPUT",

    # Formats
    "DATE_FORMAT_ISO",
    "DATETIME_FORMAT_ISO",
    "DATE_FORMAT_RU",
    "DATETIME_FORMAT_RU",
    "DEFAULT_ENCODING",
    "FALLBACK_ENCODING",
    "LOG_ROTATION_SIZE",
    "LOG_RETENTION_DAYS",
    "LOG_LEVEL_DEFAULT",
    "LOG_LEVEL_DEBUG",
]
