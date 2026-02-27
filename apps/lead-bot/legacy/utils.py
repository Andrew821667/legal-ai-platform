"""
Вспомогательные функции
"""
import asyncio
import re
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable

from telegram.error import NetworkError, RetryAfter, TimedOut

logger = logging.getLogger(__name__)


def validate_email(email: str) -> bool:
    """
    Валидация email адреса
    """
    if not email:
        return False

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_phone(phone: str) -> bool:
    """
    Валидация номера телефона (российские форматы)
    """
    if not phone:
        return False

    # Убираем все кроме цифр и +
    cleaned = re.sub(r'[^\d+]', '', phone)

    # Проверяем длину (от 10 до 12 цифр для российских номеров)
    if len(cleaned) < 10 or len(cleaned) > 12:
        return False

    return True


def format_phone(phone: str) -> str:
    """
    Форматирование телефона в красивый вид
    """
    cleaned = re.sub(r'[^\d+]', '', phone)

    if cleaned.startswith('+7'):
        return cleaned
    elif cleaned.startswith('8') and len(cleaned) == 11:
        return '+7' + cleaned[1:]
    elif cleaned.startswith('7') and len(cleaned) == 11:
        return '+' + cleaned
    else:
        return phone


def mask_sensitive_data(text: str) -> str:
    """
    Маскирование чувствительных данных в логах
    """
    # Маскируем email
    text = re.sub(
        r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'\1***@\2',
        text
    )

    # Маскируем телефон
    text = re.sub(
        r'\+?[78][\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}',
        r'+7***-***-**-**',
        text
    )

    return text


def get_formatted_timestamp() -> str:
    """
    Получение форматированной метки времени
    """
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Обрезание текста с добавлением многоточия
    """
    if len(text) <= max_length:
        return text

    return text[:max_length] + '...'


def split_long_message(text: str, max_length: int = 4096) -> list:
    """
    Разбиение длинного сообщения на части с учетом лимита Telegram (4096 символов)
    Старается разбивать по абзацам или предложениям для красоты
    
    Args:
        text: Текст для разбиения
        max_length: Максимальная длина одной части (по умолчанию 4096 - лимит Telegram)
        
    Returns:
        Список частей текста
    """
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    
    # Разбиваем по абзацам
    paragraphs = text.split('\n\n')
    
    for paragraph in paragraphs:
        # Если параграф + текущая часть помещаются
        if len(current_part) + len(paragraph) + 2 <= max_length:
            if current_part:
                current_part += '\n\n'
            current_part += paragraph
        else:
            # Сохраняем текущую часть если она не пустая
            if current_part:
                parts.append(current_part)
                current_part = ""
            
            # Если параграф сам по себе слишком длинный - режем по предложениям
            if len(paragraph) > max_length:
                sentences = re.split(r'([.!?]\s+)', paragraph)
                temp_text = ""
                
                for i, sentence in enumerate(sentences):
                    if len(temp_text) + len(sentence) <= max_length:
                        temp_text += sentence
                    else:
                        if temp_text:
                            parts.append(temp_text)
                        temp_text = sentence
                
                if temp_text:
                    current_part = temp_text
            else:
                current_part = paragraph
    
    # Добавляем последнюю часть
    if current_part:
        parts.append(current_part)
    
    return parts


async def telegram_call_with_retry(
    call: Callable[[], Awaitable[Any]],
    action: str,
    max_retries: int = 2,
    base_delay: float = 0.8,
) -> Any:
    """
    Выполняет Telegram API-вызов с ограниченным retry для временных сбоев сети.
    """
    attempt = 0
    while True:
        try:
            return await call()
        except RetryAfter as error:
            if attempt >= max_retries:
                raise
            retry_after = float(getattr(error, "retry_after", base_delay))
            delay = max(retry_after, base_delay)
            attempt += 1
            logger.warning(
                "RetryAfter during %s (attempt %s/%s), sleeping %.2fs",
                action,
                attempt,
                max_retries,
                delay,
            )
            await asyncio.sleep(delay)
        except (TimedOut, NetworkError) as error:
            if attempt >= max_retries:
                raise
            delay = base_delay * (2 ** attempt)
            attempt += 1
            logger.warning(
                "Transient Telegram error during %s: %s (attempt %s/%s), retry in %.2fs",
                action,
                error,
                attempt,
                max_retries,
                delay,
            )
            await asyncio.sleep(delay)


async def safe_answer_callback(query, action: str = "callback_answer", **kwargs):
    """Безопасно отвечает на callback query с retry."""
    return await telegram_call_with_retry(
        lambda: query.answer(**kwargs),
        action=action,
    )


async def safe_reply_text(message, text: str, action: str = "reply_text", **kwargs):
    """
    Безопасно отправляет reply_text:
    - retry для временных сетевых ошибок;
    - авто-разбиение длинных сообщений.
    """
    parts = split_long_message(text, max_length=4000)
    sent_message = None
    total = len(parts)

    for index, part in enumerate(parts, start=1):
        part_kwargs = dict(kwargs)
        if index > 1 and "reply_markup" in part_kwargs:
            part_kwargs.pop("reply_markup")

        if total > 1:
            label = f"{action}[{index}/{total}]"
        else:
            label = action

        sent_message = await telegram_call_with_retry(
            lambda part=part, part_kwargs=part_kwargs: message.reply_text(part, **part_kwargs),
            action=label,
        )

    return sent_message


async def safe_edit_text(message, text: str, action: str = "edit_text", **kwargs):
    """
    Безопасно редактирует сообщение с retry.
    Для edit ограничиваем размер, чтобы не поймать Telegram лимит.
    """
    prepared_text = text if len(text) <= 4000 else f"{text[:3990]}…"
    return await telegram_call_with_retry(
        lambda: message.edit_text(prepared_text, **kwargs),
        action=action,
    )


def format_ai_text_as_plain_symbols(text: str) -> str:
    """
    Преобразует markdown-подобную разметку в plain-текст со спецсимволами.
    Это убирает сырые **/__ и делает ответы аккуратными в Telegram без parse_mode.
    """
    if not text:
        return text

    result = text

    # Заголовки markdown -> маркер пункта
    result = re.sub(r'^\s{0,3}#{1,6}\s*(.+)$', r'▸ \1', result, flags=re.MULTILINE)

    # Выделения -> спецсимволы
    result = re.sub(r'\*\*(.+?)\*\*', r'«\1»', result, flags=re.DOTALL)
    result = re.sub(r'__(.+?)__', r'«\1»', result, flags=re.DOTALL)
    result = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'‹\1›', result, flags=re.DOTALL)
    result = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'‹\1›', result, flags=re.DOTALL)
    result = re.sub(r'`(.+?)`', r'「\1」', result, flags=re.DOTALL)

    # Если модель вернула незакрытые маркеры, убираем их.
    result = result.replace("**", "").replace("__", "")

    return result.strip()


def is_hot_lead(lead_data: dict) -> bool:
    """
    Определение горячего лида по критериям
    """
    budget = lead_data.get('budget')
    urgency = lead_data.get('urgency')
    pain_point = lead_data.get('pain_point')
    team_size = lead_data.get('team_size')

    # Горячий лид если:
    # - Бюджет 300K+ И срочность high
    # - Или бюджет 500K+
    # - И есть четкая боль

    is_hot = False

    if budget in ['300-500K', '500K+']:
        if urgency == 'high':
            is_hot = True
        elif budget == '500K+':
            is_hot = True

    # Должна быть сформулирована боль
    if not pain_point or len(pain_point) < 10:
        is_hot = False

    return is_hot


def get_lead_temperature_emoji(temperature: str) -> str:
    """
    Получение эмодзи для температуры лида
    """
    emojis = {
        'hot': '🔥',
        'warm': '♨️',
        'cold': '❄️'
    }
    return emojis.get(temperature, '❓')


def format_lead_notification(lead_data: dict, user_data: dict) -> str:
    """
    Форматирование уведомления о лиде для админа
    """
    temperature = lead_data.get('temperature', 'cold')
    emoji = get_lead_temperature_emoji(temperature)

    # Заголовок в зависимости от температуры
    headers = {
        'hot': '🔥 ГОРЯЧИЙ ЛИД!',
        'warm': '♨️ ТЕПЛЫЙ ЛИД',
        'cold': '❄️ НОВЫЙ ЛИД'
    }
    header = headers.get(temperature, '📋 НОВЫЙ ЛИД')

    message = f"{header}\n\n"
    message += f"👤 {user_data.get('first_name', 'Неизвестно')}"

    if user_data.get('username'):
        message += f" (@{user_data['username']})"

    message += "\n"

    if lead_data.get('company'):
        message += f"🏢 {lead_data['company']}\n"

    if lead_data.get('email'):
        message += f"📧 {lead_data['email']}\n"

    if lead_data.get('phone'):
        message += f"📞 {lead_data['phone']}\n"

    message += "\nДетали:\n"

    if lead_data.get('team_size'):
        message += f"• Юристов в команде: {lead_data['team_size']}\n"

    if lead_data.get('contracts_per_month'):
        message += f"• Договоров/мес: {lead_data['contracts_per_month']}\n"

    if lead_data.get('budget'):
        message += f"• Бюджет: {lead_data['budget']}\n"

    if lead_data.get('urgency'):
        urgency_ru = {
            'high': 'высокая',
            'medium': 'средняя',
            'low': 'низкая'
        }
        message += f"• Срочность: {urgency_ru.get(lead_data['urgency'], lead_data['urgency'])}\n"

    if lead_data.get('pain_point'):
        message += f"• Боль: {lead_data['pain_point']}\n"

    if lead_data.get('industry'):
        message += f"• Отрасль: {lead_data['industry']}\n"

    if lead_data.get('interested_service'):
        message += f"\nИнтересует: {lead_data['interested_service']}\n"

    if lead_data.get('lead_magnet_type'):
        magnet_types = {
            'consultation': 'Консультация 30 мин',
            'checklist': 'Чек-лист по договорам',
            'demo_analysis': 'Демо-анализ договора'
        }
        message += f"\nLead Magnet: {magnet_types.get(lead_data['lead_magnet_type'], lead_data['lead_magnet_type'])}\n"

    return message
