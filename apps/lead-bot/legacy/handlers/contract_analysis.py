"""
Обработчик анализа договоров через Contract-AI-System.

Flow:
1. Пользователь нажимает "Проверить договор" или отправляет документ в режиме анализа
2. Бот скачивает файл из Telegram
3. Отправляет через core-api proxy в Contract-AI-System
4. Поллит прогресс и обновляет сообщение
5. Возвращает краткий отчёт + ссылку на веб-кабинет
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import urllib.error
import urllib.request
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

import database
import utils
from config import get_config

logger = logging.getLogger(__name__)
config = get_config()

# Поддерживаемые форматы файлов для анализа
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".rtf", ".odt"}
SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "application/rtf",
    "application/vnd.oasis.opendocument.text",
}

# Ключ в user_data для отслеживания режима ожидания документа
CONTRACT_ANALYSIS_WAITING_KEY = "contract_analysis_waiting"


def _bridge_url(path: str) -> str:
    """Строит URL к contract-ai bridge через core-api."""
    base = config.CORE_API_URL.rstrip("/")
    return f"{base}/api/v1/contract-ai{path}"


def _api_headers() -> dict[str, str]:
    return {
        "X-API-Key": config.API_KEY_BOT,
    }


def _api_get(path: str, timeout: float = 10) -> dict[str, Any] | None:
    """GET-запрос к contract-ai bridge."""
    url = _bridge_url(path)
    request = urllib.request.Request(url=url, method="GET", headers=_api_headers())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        logger.warning("Contract AI GET %s failed: %s", path, e)
        return None


def _api_post_file(
    path: str,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    form_fields: dict[str, str],
    timeout: float = 60,
) -> dict[str, Any] | None:
    """POST multipart/form-data запрос с файлом к contract-ai bridge."""
    boundary = "----ContractAIBoundary"
    body = io.BytesIO()

    # Form fields
    for key, value in form_fields.items():
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        body.write(f"{value}\r\n".encode())

    # File field
    body.write(f"--{boundary}\r\n".encode())
    body.write(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    )
    body.write(f"Content-Type: {content_type}\r\n\r\n".encode())
    body.write(file_bytes)
    body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())

    url = _bridge_url(path)
    headers = _api_headers()
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

    request = urllib.request.Request(
        url=url,
        data=body.getvalue(),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")[:500]
        logger.warning("Contract AI POST %s failed [%s]: %s", path, e.code, error_body)
        return None
    except Exception as e:
        logger.warning("Contract AI POST %s error: %s", path, e)
        return None


def is_contract_ai_available() -> bool:
    """Проверяет доступность Contract-AI-System через bridge."""
    if not config.CORE_API_URL or not config.API_KEY_BOT:
        return False
    result = _api_get("/status", timeout=5)
    if not result:
        return False
    return result.get("mode") in ("online", "busy")


def is_supported_document(message: Message) -> bool:
    """Проверяет, является ли файл поддерживаемым для анализа."""
    doc = message.document
    if not doc:
        return False

    filename = (doc.file_name or "").lower()
    mime = (doc.mime_type or "").lower()

    # Проверка по расширению
    for ext in SUPPORTED_EXTENSIONS:
        if filename.endswith(ext):
            return True

    # Проверка по MIME type
    if mime in SUPPORTED_MIME_TYPES:
        return True

    return False


def contract_analysis_markup() -> InlineKeyboardMarkup:
    """Клавиатура для запуска анализа договора."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Отправить договор на проверку", callback_data="contract_upload")],
        [InlineKeyboardButton("Отмена", callback_data="contract_cancel")],
    ])


def contract_result_markup(web_url: str | None = None, *, job_id: str | None = None) -> InlineKeyboardMarkup:
    """Клавиатура после получения результата."""
    buttons = []
    if web_url:
        callback_data = f"contract_result:{job_id}" if job_id else "open_web:contract_ai"
        buttons.append([InlineKeyboardButton("Открыть в веб-кабинете", callback_data=callback_data)])
    buttons.append([InlineKeyboardButton("Проверить ещё договор", callback_data="contract_upload")])
    return InlineKeyboardMarkup(buttons)


async def handle_contract_result_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Warn before opening a contract analysis web result."""
    _ = context
    query = update.callback_query
    if not query:
        return

    job_id = (query.data or "").split(":", 1)[1].strip()
    summary = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: _api_get(f"/result/{job_id}/summary", timeout=15),
    )
    web_url = str((summary or {}).get("web_url") or "").strip()
    if not web_url:
        await utils.safe_answer_callback(
            query,
            action="contract_result_web_missing",
            text="Ссылка на веб-кабинет временно недоступна.",
            show_alert=True,
        )
        return

    await utils.safe_answer_callback(
        query,
        action="contract_result_web_notice",
        text=content.web_transition_alert(web_url),
        show_alert=True,
    )
    if query.message is not None:
        await utils.safe_reply_html(
            query.message,
            "<b>Переход в веб-кабинет</b>\n\n"
            f"Адрес: <code>{content._e(web_url)}</code>\n\n"
            "Отключите VPN/прокси в Telegram, затем нажмите кнопку ниже.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Открыть результат", url=web_url)]]),
            action="contract_result_web_open",
        )


async def handle_contract_analysis_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Начало сценария анализа договора.
    Вызывается по callback_data='contract_upload'.
    """
    query = update.callback_query
    if query:
        await query.answer()

    message = update.effective_message
    if not message:
        return

    # Проверяем доступность системы
    available = await asyncio.get_event_loop().run_in_executor(
        None, is_contract_ai_available
    )

    if not available:
        await utils.safe_reply_text(
            message,
            "Система анализа договоров временно недоступна.\n\n"
            "Contract_AI_System — сервис AI-анализа договоров:\n"
            "- полный анализ рисков за минуты\n"
            "- проверка на соответствие стандартам\n"
            "- рекомендации по правкам\n\n"
            "Попробуйте позже или обратитесь за консультацией.",
            action="contract_ai_unavailable",
        )
        return

    # Ставим флаг ожидания документа
    context.user_data[CONTRACT_ANALYSIS_WAITING_KEY] = True

    await utils.safe_reply_text(
        message,
        "Contract_AI_System — AI-анализ договоров\n\n"
        "Отправьте файл договора, и я проведу полный анализ:\n"
        "- выявлю ключевые риски\n"
        "- проверю на соответствие стандартам\n"
        "- подготовлю рекомендации по правкам\n\n"
        "Поддерживаемые форматы: PDF, DOCX, DOC, TXT\n"
        "Максимальный размер: 20 МБ",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Отмена", callback_data="contract_cancel")],
        ]),
        action="contract_waiting_document",
    )


async def handle_contract_analysis_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Отмена сценария анализа."""
    query = update.callback_query
    if query:
        await query.answer("Отменено")

    context.user_data.pop(CONTRACT_ANALYSIS_WAITING_KEY, None)

    message = update.effective_message
    if message:
        await utils.safe_reply_text(
            message,
            "Анализ договора отменён.",
            action="contract_cancel",
        )


async def handle_contract_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_data: dict,
) -> bool:
    """
    Обработка загруженного документа для анализа.
    Возвращает True если документ обработан как договор.
    """
    message = update.effective_message
    if not message or not message.document:
        return False

    # Проверяем что мы ждём документ
    if not context.user_data.get(CONTRACT_ANALYSIS_WAITING_KEY):
        return False

    # Проверяем формат
    if not is_supported_document(message):
        await utils.safe_reply_text(
            message,
            "Неподдерживаемый формат файла.\n"
            "Отправьте файл в формате PDF, DOCX, DOC или TXT.",
            action="contract_unsupported_format",
        )
        return True

    # Снимаем флаг ожидания
    context.user_data.pop(CONTRACT_ANALYSIS_WAITING_KEY, None)

    # Отправляем индикатор обработки
    progress_msg = await message.reply_text("Загружаю файл...")

    try:
        # Скачиваем файл из Telegram
        tg_file = await message.document.get_file()
        file_bytes = await tg_file.download_as_bytearray()

        filename = message.document.file_name or "contract.pdf"
        content_type = message.document.mime_type or "application/octet-stream"

        # Получаем email пользователя (из лида или Telegram)
        user = update.effective_user
        lead = database.db.get_local_lead_by_user_id(user_data["id"]) if user_data else None
        user_email = ""
        user_name = ""
        if lead:
            user_email = lead.get("email", "") or ""
        if user:
            user_name = user.first_name or ""
            if not user_email and user.username:
                user_email = f"{user.username}@telegram.user"

        await progress_msg.edit_text("Отправляю на анализ...")

        # Отправляем файл через core-api bridge
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _api_post_file(
                "/analyze",
                bytes(file_bytes),
                filename,
                content_type,
                {
                    "user_email": user_email or "anonymous@telegram.user",
                    "user_name": user_name,
                    "document_type": "contract",
                },
                timeout=60,
            ),
        )

        if not result or "job_id" not in result:
            await progress_msg.edit_text(
                "Не удалось отправить договор на анализ. Попробуйте позже."
            )
            return True

        job_id = result["job_id"]
        logger.info("Contract analysis started: job_id=%s for user %s", job_id, user_data.get("id"))

        # Поллим прогресс
        await _poll_and_report(progress_msg, job_id)

    except Exception as e:
        logger.error("Contract analysis error: %s", e)
        try:
            await progress_msg.edit_text(
                "Произошла ошибка при анализе. Попробуйте позже."
            )
        except Exception:
            pass

    return True


async def _poll_and_report(progress_msg: Message, job_id: str) -> None:
    """Поллит прогресс анализа и обновляет сообщение."""
    max_polls = 60  # максимум 5 минут (60 * 5 сек)
    last_text = ""

    for i in range(max_polls):
        await asyncio.sleep(5)

        progress = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _api_get(f"/progress/{job_id}", timeout=10),
        )

        if not progress:
            continue

        percent = progress.get("percent", 0)
        msg = progress.get("message", "Анализирую...")
        status = progress.get("status", "processing")

        # Обновляем сообщение если текст изменился
        bar = _progress_bar(percent)
        new_text = f"Анализ договора...\n\n{bar} {percent}%\n{msg}"

        if new_text != last_text:
            try:
                await progress_msg.edit_text(new_text)
                last_text = new_text
            except Exception:
                pass

        # Проверяем завершение
        if status in ("completed", "done", "finished") or percent >= 100:
            break

        if status in ("error", "failed"):
            await progress_msg.edit_text(
                "Анализ завершился с ошибкой. Попробуйте позже."
            )
            return

    # Получаем краткий отчёт
    summary = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: _api_get(f"/result/{job_id}/summary", timeout=15),
    )

    if summary and summary.get("summary"):
        summary_text = summary["summary"]
        # Telegram ограничивает 4096 символов
        if len(summary_text) > 4000:
            summary_text = summary_text[:3997] + "..."

        await progress_msg.edit_text(
            summary_text,
            parse_mode="Markdown",
            reply_markup=contract_result_markup(summary.get("web_url"), job_id=job_id),
        )
    else:
        # Если summary не получен — показываем что анализ завершён
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _api_get(f"/result/{job_id}", timeout=15),
        )

        if result:
            risk_score = result.get("risk_score", "N/A")
            risks_count = len(result.get("risks", []))
            recs_count = len(result.get("recommendations", []))
            await progress_msg.edit_text(
                f"Анализ завершён!\n\n"
                f"Оценка риска: {risk_score}/100\n"
                f"Найдено рисков: {risks_count}\n"
                f"Рекомендаций: {recs_count}\n\n"
                f"Для детального просмотра откройте веб-кабинет.",
                reply_markup=contract_result_markup(),
            )
        else:
            await progress_msg.edit_text(
                "Анализ завершён. Откройте веб-кабинет для просмотра результатов.",
                reply_markup=contract_result_markup(),
            )


def _progress_bar(percent: int) -> str:
    """Визуальный прогресс-бар для Telegram."""
    filled = min(percent // 10, 10)
    empty = 10 - filled
    return "[" + "=" * filled + " " * empty + "]"
