from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "legal-ai-core-api"
    environment: str = "dev"
    database_url: str = "postgresql+psycopg://legalai_app:change_me_local_only@localhost:5432/legalai_platform"
    cors_origins: str = "http://localhost:3000"
    alert_bot_token: str | None = None
    # Аккаунты владельца практики в Telegram: основной и дополнительные
    # (через запятую) — те же переменные, что у бота и сайта. Обращения с
    # них — проверка системы, а не клиенты: помечаются «Тест» и не попадают
    # в деньги, счётчики и уведомления о новых лидах.
    admin_telegram_id: str = ""
    lawyer_telegram_ids: str = ""
    # Аккаунты, с которых владелец проверяет систему как клиент. Прав
    # владельца у них нет (бот и сайт о них не знают), но для рабочего места
    # это тоже «Тест», а не клиент.
    test_telegram_ids: str = ""
    # Прокси до Telegram — тот же, что у бота-ассистента и сайта
    # (xray-balancer на хосте). Напрямую api.telegram.org с прод-хоста
    # недоступен: без прокси каждая отправка из ядра — договор, акт, ответ
    # клиенту, уведомление — висела до таймаута и падала.
    legal_ai_https_proxy: str = ""
    # Sentry: пусто по умолчанию — мониторинг включается явным заданием
    # DSN, а не молчаливым переходом в SaaS вне РФ.
    sentry_dsn: str | None = None
    alert_chat_id: str | None = None
    lead_notify_bot_token: str | None = None
    # Токен бота-ассистента: им ядро пишет клиенту напрямую — например,
    # отправляет подготовленный договор из рабочего места юриста. Раньше
    # отправлял только бот, и любая доставка из другого места означала вторую
    # копию текста и кнопок.
    lead_bot_token: str | None = None
    # Оплата по выбору владельца: перевод по телефону, без эквайринга.
    lawyer_payment_sbp_phone: str | None = None
    lawyer_payment_bank: str | None = None
    # Сколько дней после отправки акта оплата считается вовремя. Срока в
    # самом акте нет (порядок оплаты — текстом в договоре), а без границы
    # «просрочено» не отличить от «только что выставлено».
    act_payment_days: int = 7
    # Сводка за неделю владельцу в Telegram по понедельникам (weekly_digest).
    weekly_digest_enabled: bool = True
    # Через сколько дней молчания клиента ядро само напоминает о неподписанном
    # договоре. Второе и последнее напоминание — в последние сутки перед
    # окончанием предложения. 0 — не напоминать.
    agreement_remind_after_days: int = 3
    lawyer_payment_recipient: str | None = None
    # Реквизиты счёта для платёжного QR (ГОСТ Р 56042, «ST00012»): его
    # сканирует приложение любого крупного банка, и реквизиты, сумма и
    # назначение заполняются сами. Официальный QR СБП самозанятому без
    # торгового договора с банком недоступен — это стандартная замена. Пока
    # счёт не задан, QR не показывается и остаётся перевод по телефону.
    lawyer_payment_account: str | None = None
    lawyer_payment_bic: str | None = None
    lawyer_payment_corr_account: str | None = None
    lawyer_payment_inn: str | None = None
    # Имя владельца счёта полностью, как в банке: в QR банк сверяет его со
    # счётом. LAWYER_PAYMENT_RECIPIENT — для текста «Получатель: …» и может
    # быть коротким.
    lawyer_payment_account_holder: str | None = None
    # Начало назначения платежа, которое просит банк получателя, например у
    # Т-Банка «Перевод средств по договору № … ФИО». Дальше — номер акта.
    lawyer_payment_purpose_prefix: str | None = None
    lead_notify_chat_id: str | None = None
    lead_notify_web_base_url: str = "https://ai-verdict.ru"
    api_key_cache_ttl_seconds: int = 60
    health_worker_active_minutes: int = 10
    news_retry_failed_after_minutes: int = 15
    miniapp_public_base_url: str = "https://ai-verdict.ru"
    db_pool_size: int = 8
    db_max_overflow: int = 8
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800
    contract_ai_bridge_enabled_default: bool = False
    contract_ai_bridge_deployment: str = "docker_local_macbook"
    contract_ai_bridge_mode: str = "offline"
    contract_ai_bridge_secret: str = ""
    contract_ai_bridge_status_url: str = ""
    contract_ai_bridge_analysis_url: str = ""
    contract_ai_bridge_progress_url: str = ""
    contract_ai_bridge_result_url: str = ""
    contract_ai_bridge_sso_url: str = ""
    contract_ai_bridge_demo_link_url: str = ""

    # Эти значения копируются в неизменяемый экземпляр договора.
    operator_name: str = "Попов Андрей Викторович"
    operator_status: str = "самозанятый"
    operator_inn: str = "683302758241"
    operator_details: str = ""
    privacy_contact_email: str = "privacy@ai-verdict.ru"

    # Разбор юридических обращений моделью.
    # Отдельные переменные, а не OPENAI_*: те исторически указывают на другого
    # провайдера (OPENAI_BASE_URL ведёт на api.deepseek.com), и переиспользовать
    # их значило бы сломать генерацию новостей.
    intake_analysis_enabled: bool = True
    intake_analysis_api_key: str = ""
    intake_analysis_base_url: str = "https://api.openai.com/v1"
    intake_analysis_model: str = "gpt-5.6-sol"
    # Прямой доступ к вендору с production-хоста закрыт по региону.
    intake_analysis_proxy_url: str = ""
    intake_analysis_timeout_seconds: float = 90.0

    # Помощник, ведущий первичный разговор с клиентом.
    #
    # Ключ и прокси берутся из разбора обращений: это тот же вендор и тот же
    # канал. Отдельно вынесены имя, модель и таймаут — помощник отвечает
    # человеку, который ждёт в переписке, поэтому ждать он может заметно
    # меньше, чем фоновой разбор.
    intake_assistant_enabled: bool = True
    intake_assistant_name: str = "Никита"
    intake_assistant_model: str = "gpt-5.6-sol"
    intake_assistant_timeout_seconds: float = 45.0


def telegram_proxies() -> dict[str, str] | None:
    """Прокси для запросов к api.telegram.org или None, если не задан."""
    url = (get_settings().legal_ai_https_proxy or "").strip()
    return {"https": url, "http": url} if url else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
