"""
Telegram Bot Keyboards
Клавиатуры для модерации и управления ботом.
"""

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.bot.telegram_ui import inline_button as InlineKeyboardButton


def add_utm_params(
    url: str,
    source: str = "telegram",
    medium: str = "social",
    campaign: str = "legal_ai_news"
) -> str:
    """
    Добавить UTM-метки к URL для отслеживания трафика.

    Args:
        url: Исходный URL
        source: UTM source (по умолчанию: telegram)
        medium: UTM medium (по умолчанию: social)
        campaign: UTM campaign (по умолчанию: legal_ai_news)

    Returns:
        URL с добавленными UTM-метками
    """
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        # Добавляем UTM-метки
        query_params['utm_source'] = [source]
        query_params['utm_medium'] = [medium]
        query_params['utm_campaign'] = [campaign]

        # Формируем новый query string
        new_query = urlencode(query_params, doseq=True)

        # Собираем URL обратно
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
    except Exception:
        # Если не удалось распарсить - возвращаем оригинал
        return url


def get_draft_review_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для модерации драфта.

    Args:
        draft_id: ID драфта

    Returns:
        InlineKeyboardMarkup с кнопками одобрения/отклонения
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ Опубликовать",
            callback_data=f"publish:{draft_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data=f"edit:{draft_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"reject:{draft_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 Статистика",
            callback_data=f"stats:{draft_id}"
        )
    )

    return builder.as_markup()


def get_confirm_keyboard(action: str, draft_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения действия.

    Args:
        action: Действие (publish, reject)
        draft_id: ID драфта

    Returns:
        InlineKeyboardMarkup с кнопками подтверждения
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ Да, подтвердить",
            callback_data=f"confirm_{action}:{draft_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"cancel:{draft_id}"
        )
    )

    return builder.as_markup()


def get_reader_keyboard(
    source_url: str,
    channel_username: str = "legal_ai_pro",
    post_id: int = None
) -> InlineKeyboardMarkup:
    """
    Клавиатура для читателей в опубликованном посте.

    Args:
        source_url: URL источника новости
        channel_username: Username канала для кнопки "Поделиться"
        post_id: ID поста для кнопки мнения (опционально)

    Returns:
        InlineKeyboardMarkup с интерактивными кнопками
    """
    builder = InlineKeyboardBuilder()

    # Добавляем UTM-метки к ссылке на источник
    tracked_url = add_utm_params(
        source_url,
        source="telegram",
        medium="legal_ai_channel",
        campaign="ai_news_post"
    )

    # Кнопка "Читать полностью" с UTM-метками
    builder.row(
        InlineKeyboardButton(
            text="📖 Читать полностью",
            url=tracked_url
        )
    )

    # Кнопка "Поделиться" (открывает диалог выбора чата)
    builder.row(
        InlineKeyboardButton(
            text="📤 Поделиться",
            url=f"https://t.me/share/url?url=https://t.me/{channel_username}"
        )
    )

    # Кнопка "Ваше мнение" для сбора feedback (если указан post_id)
    if post_id:
        builder.row(
            InlineKeyboardButton(
                text="📊 Ваше мнение",
                callback_data=f"opinion:{post_id}"
            )
        )

    return builder.as_markup()


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Главное меню админ панели.

    Returns:
        InlineKeyboardMarkup с главными командами
    """
    from aiogram.types import WebAppInfo
    import os

    builder = InlineKeyboardBuilder()

    # Mini App button (if URL is configured)
    mini_app_url = os.getenv("MINI_APP_URL")
    if mini_app_url:
        builder.row(
            InlineKeyboardButton(
                text="🚀 Открыть Mini App",
                web_app=WebAppInfo(url=mini_app_url)
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="📝 Новые драфты",
            callback_data="show_drafts"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✍️ Мои заметки",
            callback_data="show_personal_posts"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔄 Запустить сбор",
            callback_data="run_fetch"
        ),
        InlineKeyboardButton(
            text="📊 Статистика",
            callback_data="show_stats"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⚙️ Настройки",
            callback_data="show_settings"
        )
    )

    return builder.as_markup()


def get_opinion_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для сбора мнения читателей о посте.

    Args:
        post_id: ID драфта/поста

    Returns:
        InlineKeyboardMarkup с вариантами мнения
    """
    builder = InlineKeyboardBuilder()

    # Позитивные реакции
    builder.row(
        InlineKeyboardButton(
            text="👍 Полезно",
            callback_data=f"react:{post_id}:useful"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔥 Важно",
            callback_data=f"react:{post_id}:important"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🤔 Спорно",
            callback_data=f"react:{post_id}:controversial"
        )
    )

    # Негативные реакции для улучшения контента
    builder.row(
        InlineKeyboardButton(
            text="💤 Банальщина",
            callback_data=f"react:{post_id}:banal"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🤷 Очевидный вывод",
            callback_data=f"react:{post_id}:obvious"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="👎 Плохое качество",
            callback_data=f"react:{post_id}:poor_quality"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📉 Низкое качество контента",
            callback_data=f"react:{post_id}:low_content_quality"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📰 Плохой источник",
            callback_data=f"react:{post_id}:bad_source"
        )
    )

    return builder.as_markup()


def get_edit_mode_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора способа редактирования.

    Args:
        draft_id: ID драфта

    Returns:
        InlineKeyboardMarkup с вариантами редактирования
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✍️ Редактировать вручную",
            callback_data=f"edit_manual:{draft_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🤖 Редактировать с помощью AI",
            callback_data=f"edit_llm:{draft_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="« Назад",
            callback_data=f"back_to_draft:{draft_id}"
        )
    )

    return builder.as_markup()


def get_rejection_reasons_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура с причинами отклонения.

    Args:
        draft_id: ID драфта

    Returns:
        InlineKeyboardMarkup с типовыми причинами отклонения
    """
    builder = InlineKeyboardBuilder()

    reasons = [
        ("Нерелевантно", "irrelevant"),
        ("Низкое качество", "low_quality"),
        ("Дубликат", "duplicate"),
        ("Неточная информация", "inaccurate"),
        ("Другое", "other"),
    ]

    for text, reason in reasons:
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"reject_reason:{draft_id}:{reason}"
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="« Назад",
            callback_data=f"back_to_draft:{draft_id}"
        )
    )

    return builder.as_markup()


def get_llm_selection_keyboard(current_provider: str = "openai") -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора LLM провайдера.

    Args:
        current_provider: Текущий выбранный провайдер

    Returns:
        InlineKeyboardMarkup с вариантами LLM
    """
    builder = InlineKeyboardBuilder()

    # OpenAI
    openai_text = "✅ OpenAI (GPT-4o-mini)" if current_provider == "openai" else "OpenAI (GPT-4o-mini)"
    builder.row(
        InlineKeyboardButton(
            text=openai_text,
            callback_data="llm_select:openai"
        )
    )

    # Perplexity
    perplexity_text = "✅ Perplexity (Llama 3.1)" if current_provider == "perplexity" else "Perplexity (Llama 3.1)"
    builder.row(
        InlineKeyboardButton(
            text=perplexity_text,
            callback_data="llm_select:perplexity"
        )
    )

    # DeepSeek
    deepseek_text = "✅ DeepSeek (V3 - дешевле)" if current_provider == "deepseek" else "DeepSeek (V3 - дешевле)"
    builder.row(
        InlineKeyboardButton(
            text=deepseek_text,
            callback_data="llm_select:deepseek"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="« Назад",
            callback_data="show_settings"
        )
    )

    return builder.as_markup()
