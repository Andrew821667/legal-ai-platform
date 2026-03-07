"""
Telegram Bot Handlers
Обработчики команд и модерация драфтов.
"""

import asyncio
import html
from datetime import datetime
from typing import Optional, Dict, List

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, FSInputFile, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import (
    PostDraft, Publication, RawArticle,
    FeedbackLabel, PersonalPost, PostComment, get_db, APIUsage
)
from app.bot.keyboards import (
    get_draft_review_keyboard,
    get_confirm_keyboard,
    get_reader_keyboard,
    get_main_menu_keyboard,
    get_rejection_reasons_keyboard,
    get_opinion_keyboard,
    get_edit_mode_keyboard,
    get_llm_selection_keyboard
)
from app.bot.middleware import DbSessionMiddleware
from app.modules.llm_provider import get_llm_provider
from app.modules.vector_search import get_vector_search
from app.modules.analytics import AnalyticsService
from app.modules.channel_moderation import ChannelModeration
from app.services.core_reader_bridge import fetch_reader_conversion_funnel
import structlog

logger = structlog.get_logger()

# Глобальные переменные (Bot создается лениво чтобы избежать создания aiohttp клиента при импорте)
_bot: Optional[Bot] = None
_selected_llm_provider: str = settings.default_llm_provider  # Хранение выбранного LLM провайдера
_channel_moderator: Optional[ChannelModeration] = None  # Модератор канала
dp = Dispatcher()
router = Router()


def get_bot() -> Bot:
    """
    Получить экземпляр бота (ленивая инициализация).

    Bot создается только при первом вызове, чтобы избежать создания aiohttp клиента
    при импорте модуля (важно для Celery worker).
    """
    global _bot
    if _bot is None:
        _bot = Bot(token=settings.telegram_bot_token)
    return _bot


# FSM States для редактирования
class EditDraft(StatesGroup):
    waiting_for_manual_edit = State()
    waiting_for_llm_edit = State()


# ====================
# Channel Moderation
# ====================

def get_channel_moderator() -> ChannelModeration:
    """
    Получить экземпляр модератора канала (ленивая инициализация).

    Модератор создается только при первом вызове.
    """
    global _channel_moderator
    if _channel_moderator is None:
        _channel_moderator = ChannelModeration()
        _channel_moderator.set_bot(get_bot())
        logger.info("Channel moderator initialized")
    return _channel_moderator


@router.channel_post()
async def moderate_channel_comment(message: Message):
    """
    Модерация комментариев к постам в канале @legal_ai_pro.

    Обрабатывает все новые комментарии и применяет правила модерации:
    - Фильтрация спама и запрещенных слов
    - AI анализ релевантности и тональности
    - Автоматические действия (удаление/предупреждение)
    """
    try:
        # Проверяем, что это комментарий к нашему каналу
        if str(message.chat.id) != str(settings.telegram_channel_id_numeric):
            return  # Не наш канал

        # Проверяем, что это текстовое сообщение
        if not message.text:
            return  # Пропускаем медиа и другие типы сообщений

        logger.info(
            f"Moderating comment from user {message.from_user.id} in channel {message.chat.id}: {message.text[:100]}..."
        )

        # Получаем модератор
        moderator = get_channel_moderator()

        # Анализируем комментарий
        moderation_result = await moderator.moderate_comment(message, str(message.chat.id))

        # Принимаем решение о модерации
        if moderation_result['moderated']:
            await moderator.take_moderation_action(message, moderation_result)

            # Логируем модерацию
            logger.info(
                f"Comment moderated: action={moderation_result['action']}, "
                f"reason={moderation_result['reason']}, "
                f"confidence={moderation_result['confidence']:.2f}"
            )

            # Сохраняем статистику модерации в базу данных
            try:
                from app.models.database import PostComment, get_db
                async with get_db() as db:
                    # Ищем публикацию по message_id или reply_to_message
                    publication_id = None
                    if message.reply_to_message:
                        # Это ответ на сообщение, найдем публикацию
                        from sqlalchemy import select
                        result = await db.execute(
                            select(PostComment.publication_id).where(
                                PostComment.telegram_message_id == message.reply_to_message.message_id
                            )
                        )
                        publication_id = result.scalar()

                    if publication_id:
                        comment = PostComment(
                            publication_id=publication_id,
                            telegram_message_id=message.message_id,
                            user_id=message.from_user.id,
                            username=message.from_user.username,
                            text=message.text,
                            moderated=True,
                            moderation_action=moderation_result['action'],
                            moderation_reason=moderation_result['reason'],
                            moderation_confidence=moderation_result['confidence']
                        )
                        db.add(comment)
                        await db.commit()

            except Exception as e:
                logger.error(f"Failed to save moderation data: {e}")

    except Exception as e:
        logger.error(f"Error in channel comment moderation: {e}")


# ====================
# Middleware для проверки прав
# ====================

async def check_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь администратором."""
    return user_id == settings.telegram_admin_id


# ====================
# Команды
# ====================

@router.message(CommandStart())
async def cmd_start(message: Message):
    logger.info(f"Start command received from user {message.from_user.id}")
    logger.info(f"Message text: {message.text}")
    """Обработчик команды /start."""
    if not await check_admin(message.from_user.id):
        await message.answer("⛔️ У вас нет прав доступа к этому боту.")
        return

    await message.answer(
        "👋 Добро пожаловать в AI-News Aggregator!\n\n"
        "Этот бот помогает модерировать новости о внедрении ИИ в юриспруденцию.\n\n"
        "Доступные команды:\n"
        "/drafts - показать новые драфты\n"
        "/stats - показать статистику\n"
        "/help - помощь",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(Command("drafts"))
async def cmd_drafts(message: Message, db: AsyncSession):
    """Показать новые драфты для модерации."""
    if not await check_admin(message.from_user.id):
        return

    # Получаем ВСЕ драфты в статусе pending_review (без фильтра по дате)
    result = await db.execute(
        select(PostDraft)
        .where(PostDraft.status == 'pending_review')
        .order_by(PostDraft.created_at.desc())
    )
    drafts = list(result.scalars().all())

    if not drafts:
        await message.answer("📭 Нет новых драфтов для модерации.")
        return

    await message.answer(f"📝 Найдено {len(drafts)} драфтов. Отправляю...")

    # Отправляем каждый драфт (ограничиваем настройкой publisher_max_posts_per_day)
    max_drafts = min(len(drafts), settings.publisher_max_posts_per_day)
    for index, draft in enumerate(drafts[:max_drafts], start=1):
        await send_draft_for_review(message.chat.id, draft, db, draft_number=index)


async def get_statistics(db: AsyncSession) -> str:
    """Собрать и отформатировать статистику системы."""
    from datetime import datetime, timedelta
    from sqlalchemy import extract

    now = datetime.utcnow()
    current_month_start = datetime(now.year, now.month, 1)
    current_year_start = datetime(now.year, 1, 1)

    # Статистика по контенту
    articles_count = (await db.execute(select(func.count(RawArticle.id)))).scalar()
    drafts_count = (await db.execute(select(func.count(PostDraft.id)))).scalar()
    pubs_count = (await db.execute(select(func.count(Publication.id)))).scalar()

    # Драфты по статусам
    pending_drafts = (await db.execute(
        select(func.count(PostDraft.id)).where(PostDraft.status == 'pending')
    )).scalar()
    approved_drafts = (await db.execute(
        select(func.count(PostDraft.id)).where(PostDraft.status == 'approved')
    )).scalar()
    rejected_drafts = (await db.execute(
        select(func.count(PostDraft.id)).where(PostDraft.status == 'rejected')
    )).scalar()

    # Последняя публикация
    last_pub = (await db.execute(
        select(Publication).order_by(Publication.published_at.desc()).limit(1)
    )).scalar_one_or_none()
    last_pub_text = ""
    if last_pub:
        last_pub_text = f"\n📅 Последняя публикация: {last_pub.published_at.strftime('%d.%m.%Y %H:%M')}"

    # ============ API USAGE СТАТИСТИКА ============

    # За текущий месяц
    month_stats = await db.execute(
        select(
            APIUsage.provider,
            func.sum(APIUsage.total_tokens).label('tokens'),
            func.sum(APIUsage.cost_usd).label('cost')
        ).where(
            APIUsage.created_at >= current_month_start
        ).group_by(APIUsage.provider)
    )
    month_by_provider = {row.provider: {'tokens': row.tokens or 0, 'cost': float(row.cost or 0)}
                         for row in month_stats}

    # За текущий год
    year_stats = await db.execute(
        select(
            APIUsage.provider,
            func.sum(APIUsage.total_tokens).label('tokens'),
            func.sum(APIUsage.cost_usd).label('cost')
        ).where(
            APIUsage.created_at >= current_year_start
        ).group_by(APIUsage.provider)
    )
    year_by_provider = {row.provider: {'tokens': row.tokens or 0, 'cost': float(row.cost or 0)}
                        for row in year_stats}

    # По операциям (за текущий месяц)
    operation_stats = await db.execute(
        select(
            APIUsage.operation,
            func.sum(APIUsage.total_tokens).label('tokens'),
            func.sum(APIUsage.cost_usd).label('cost')
        ).where(
            APIUsage.created_at >= current_month_start
        ).group_by(APIUsage.operation)
    )
    by_operation = {row.operation: {'tokens': row.tokens or 0, 'cost': float(row.cost or 0)}
                   for row in operation_stats}

    # Последний запрос
    last_api_call = (await db.execute(
        select(APIUsage).order_by(APIUsage.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    # Формируем статистику API
    api_stats_text = ""

    # Текущий месяц
    month_total_cost = sum(p['cost'] for p in month_by_provider.values())
    month_total_tokens = sum(p['tokens'] for p in month_by_provider.values())

    if month_total_tokens > 0:
        api_stats_text += f"\n\n💰 <b>API расходы (текущий месяц):</b>"
        api_stats_text += f"\n├─ Всего токенов: {month_total_tokens:,}"
        # Используем адаптивное форматирование для маленьких сумм
        cost_fmt = f"${month_total_cost:.6f}" if month_total_cost < 0.01 else f"${month_total_cost:.4f}"
        api_stats_text += f"\n├─ Общая стоимость: {cost_fmt}"

        # Бюджет и процент использования
        from app.modules.settings_manager import get_setting
        budget_max = await get_setting("budget.max_per_month", db, default=0.6)
        if budget_max > 0:
            budget_pct = (month_total_cost / budget_max) * 100
            budget_emoji = "🟢" if budget_pct < 50 else "🟡" if budget_pct < 80 else "🔴"
            api_stats_text += f"\n├─ Бюджет: {budget_pct:.1f}% использовано {budget_emoji}"

        if month_by_provider:
            api_stats_text += "\n└─ <b>По провайдерам:</b>"
            for provider, data in sorted(month_by_provider.items()):
                provider_name = {"deepseek": "DeepSeek", "openai": "OpenAI", "perplexity": "Perplexity"}.get(provider, provider)
                cost_fmt = f"${data['cost']:.6f}" if data['cost'] < 0.01 else f"${data['cost']:.4f}"
                api_stats_text += f"\n   ├─ {provider_name}: {data['tokens']:,} токенов ({cost_fmt})"

    # Текущий год
    year_total_cost = sum(p['cost'] for p in year_by_provider.values())
    year_total_tokens = sum(p['tokens'] for p in year_by_provider.values())

    if year_total_tokens > 0:
        api_stats_text += f"\n\n📈 <b>API расходы (текущий год):</b>"
        api_stats_text += f"\n├─ Всего токенов: {year_total_tokens:,}"
        cost_fmt = f"${year_total_cost:.6f}" if year_total_cost < 0.01 else f"${year_total_cost:.4f}"
        api_stats_text += f"\n└─ Общая стоимость: {cost_fmt}"

    # По операциям
    if by_operation:
        api_stats_text += f"\n\n⚙️ <b>По операциям (месяц):</b>"
        for operation, data in sorted(by_operation.items(), key=lambda x: x[1]['cost'], reverse=True):
            op_name = {"ranking": "Ранжирование", "draft_generation": "Генерация драфтов",
                      "analysis": "Анализ", "editing": "Редактирование", "completion": "Общие"}.get(operation, operation)
            cost_fmt = f"${data['cost']:.6f}" if data['cost'] < 0.01 else f"${data['cost']:.4f}"
            api_stats_text += f"\n├─ {op_name}: {data['tokens']:,} токенов ({cost_fmt})"

    # Последний запрос
    if last_api_call:
        provider_name = {"deepseek": "DeepSeek", "openai": "OpenAI", "perplexity": "Perplexity"}.get(last_api_call.provider, last_api_call.provider)
        api_stats_text += f"\n\n🔄 <b>Последний API запрос:</b>"
        api_stats_text += f"\n├─ Провайдер: {provider_name}"
        api_stats_text += f"\n├─ Модель: {last_api_call.model}"
        api_stats_text += f"\n├─ Операция: {last_api_call.operation or 'не указана'}"
        api_stats_text += f"\n├─ Токены: {last_api_call.total_tokens:,}"
        api_stats_text += f"\n└─ Стоимость: ${last_api_call.cost_usd:.6f}"

    stats_text = f"""
📊 <b>Статистика системы</b>

📰 <b>Контент:</b>
├─ Статей собрано: {articles_count}
├─ Драфтов создано: {drafts_count}
└─ Опубликовано: {pubs_count}{last_pub_text}

✍️ <b>Драфты по статусам:</b>
├─ На модерации: {pending_drafts}
├─ Одобрено: {approved_drafts}
└─ Отклонено: {rejected_drafts}{api_stats_text}
"""

    return stats_text.strip()


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: AsyncSession):
    """Показать статистику."""
    if not await check_admin(message.from_user.id):
        return

    # Собираем статистику
    stats_text = await get_statistics(db)
    await message.answer(stats_text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Показать помощь."""
    if not await check_admin(message.from_user.id):
        return

    help_text = """
📚 <b>Помощь по боту</b>

<b>Команды:</b>
/start - Главное меню
/drafts - Показать новые драфты
/stats - Статистика системы
/fetch - Запустить сбор новостей вручную
/help - Эта справка

<b>Модерация драфтов:</b>
✅ Опубликовать - опубликовать пост в канал
✏️ Редактировать - редактировать текст поста
❌ Отклонить - отклонить драфт

<b>Workflow:</b>
1. Система автоматически собирает новости (09:00 MSK)
2. AI анализирует и генерирует драфты
3. Вы получаете уведомление о новых драфтах
4. Вы модерируете каждый драфт
5. Одобренные посты публикуются в канал

⚠️ <b>Важно:</b> Все драфты требуют модерации перед публикацией!
"""
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("fetch"))
async def cmd_fetch(message: Message):
    """Запустить сбор новостей вручную."""
    if not await check_admin(message.from_user.id):
        return

    await message.answer("🔄 Запускаю сбор новостей...")

    try:
        # Импортируем и запускаем задачу Celery
        from app.tasks.celery_tasks import manual_workflow
        task = manual_workflow.delay()

        await message.answer(
            f"✅ Задача запущена!\n"
            f"ID задачи: <code>{task.id}</code>\n\n"
            f"Процесс займет 5-10 минут.\n"
            f"Используйте /drafts чтобы проверить новые драфты.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error("fetch_error", error=str(e))
        await message.answer(f"❌ Ошибка запуска: {str(e)}")


# ====================
# Callback обработчики
# ====================

@router.callback_query(F.data.startswith("publish:"))
async def callback_publish(callback: CallbackQuery, db: AsyncSession):
    """Обработчик кнопки публикации."""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет прав доступа", show_alert=True)
        return

    draft_id = int(callback.data.split(":")[1])

    # Запрашиваем подтверждение
    await callback.message.edit_reply_markup(
        reply_markup=get_confirm_keyboard("publish", draft_id)
    )
    await callback.answer("Подтвердите публикацию")


@router.callback_query(F.data.startswith("confirm_publish:"))
async def callback_confirm_publish(callback: CallbackQuery, db: AsyncSession):
    """Подтверждение публикации."""
    # ВАЖНО: отвечаем сразу, чтобы кнопка не зависала
    await callback.answer("Публикую...")

    if not await check_admin(callback.from_user.id):
        logger.warning("confirm_publish_no_access", user_id=callback.from_user.id)
        return

    draft_id = int(callback.data.split(":")[1])
    logger.info("confirm_publish_start", draft_id=draft_id, user_id=callback.from_user.id)

    # Публикуем пост
    success = await publish_draft(draft_id, db, callback.from_user.id)
    logger.info("confirm_publish_result", draft_id=draft_id, success=success)

    try:
        logger.info("confirm_publish_updating_message", draft_id=draft_id, has_photo=bool(callback.message.photo))
        if success:
            # Проверяем тип сообщения (photo или text)
            if callback.message.photo:
                logger.info("confirm_publish_edit_caption", draft_id=draft_id)
                await callback.message.edit_caption(
                    caption=f"✅ Драфт #{draft_id} успешно опубликован!",
                    reply_markup=None  # Убираем кнопки
                )
            else:
                logger.info("confirm_publish_edit_text", draft_id=draft_id)
                await callback.message.edit_text(
                    text=f"✅ Драфт #{draft_id} успешно опубликован!",
                    reply_markup=None  # Убираем кнопки
                )
            logger.info("confirm_publish_message_updated", draft_id=draft_id)
        else:
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=f"❌ Ошибка при публикации драфта #{draft_id}",
                    reply_markup=None
                )
            else:
                await callback.message.edit_text(
                    text=f"❌ Ошибка при публикации драфта #{draft_id}",
                    reply_markup=None
                )
    except Exception as e:
        logger.error("callback_message_edit_error", error=str(e), draft_id=draft_id, error_type=type(e).__name__)
        # Если не получилось отредактировать, отправим новое сообщение
        status_msg = f"✅ Драфт #{draft_id} успешно опубликован!" if success else f"❌ Ошибка при публикации драфта #{draft_id}"
        await callback.message.answer(status_msg)


@router.callback_query(F.data.startswith("reject:"))
async def callback_reject(callback: CallbackQuery, db: AsyncSession):
    """Обработчик кнопки отклонения."""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет прав доступа", show_alert=True)
        return

    draft_id = int(callback.data.split(":")[1])

    # Показываем причины отклонения
    await callback.message.edit_reply_markup(
        reply_markup=get_rejection_reasons_keyboard(draft_id)
    )
    await callback.answer("Выберите причину отклонения")


@router.callback_query(F.data.startswith("reject_reason:"))
async def callback_reject_reason(callback: CallbackQuery, db: AsyncSession):
    """Обработка выбора причины отклонения."""
    # ВАЖНО: отвечаем сразу, чтобы кнопка не зависала
    await callback.answer("Отклоняю...")

    if not await check_admin(callback.from_user.id):
        return

    parts = callback.data.split(":")
    draft_id = int(parts[1])
    reason = parts[2]

    # Отклоняем драфт
    success = await reject_draft(draft_id, reason, db, callback.from_user.id)

    if success:
        # Проверяем тип сообщения (photo или text)
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=f"❌ Драфт #{draft_id} отклонен\nПричина: {reason}"
            )
        else:
            await callback.message.edit_text(
                f"❌ Драфт #{draft_id} отклонен\nПричина: {reason}"
            )
    else:
        await callback.message.answer("❌ Ошибка при отклонении драфта", show_alert=True)


@router.callback_query(F.data.startswith("edit:"))
async def callback_edit(callback: CallbackQuery):
    """Обработчик кнопки редактирования - показывает выбор способа."""
    await callback.answer()

    if not await check_admin(callback.from_user.id):
        await callback.message.answer("⛔️ Нет прав доступа")
        return

    draft_id = int(callback.data.split(":")[1])

    await callback.message.answer(
        "✏️ Выберите способ редактирования драфта:",
        reply_markup=get_edit_mode_keyboard(draft_id)
    )


@router.callback_query(F.data.startswith("edit_manual:"))
async def callback_edit_manual(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Обработчик ручного редактирования."""
    await callback.answer()

    if not await check_admin(callback.from_user.id):
        await callback.message.answer("⛔️ Нет прав доступа")
        return

    draft_id = int(callback.data.split(":")[1])

    # Получаем текущий драфт
    result = await db.execute(
        select(PostDraft).where(PostDraft.id == draft_id)
    )
    draft = result.scalar_one_or_none()

    if not draft:
        await callback.answer("❌ Драфт не найден", show_alert=True)
        return

    await state.update_data(draft_id=draft_id)
    await state.set_state(EditDraft.waiting_for_manual_edit)

    # Отправляем текущий текст отдельным сообщением для удобного копирования
    await callback.message.answer(
        "✍️ <b>ТЕКУЩИЙ ТЕКСТ ПОСТА</b>\n"
        "Скопируйте сообщение ниже ⬇️, отредактируйте и отправьте обратно:",
        parse_mode="HTML"
    )

    # Текст поста отдельным сообщением (легко копировать долгим нажатием)
    await callback.message.answer(draft.content)

    await callback.message.answer(
        "📌 Используйте HTML разметку:\n"
        "<b>жирный</b>, <i>курсив</i>, <code>код</code>\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("edit_llm:"))
async def callback_edit_llm(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Обработчик AI-редактирования."""
    await callback.answer()

    if not await check_admin(callback.from_user.id):
        await callback.message.answer("⛔️ Нет прав доступа")
        return

    draft_id = int(callback.data.split(":")[1])

    # Получаем текущий драфт
    result = await db.execute(
        select(PostDraft).where(PostDraft.id == draft_id)
    )
    draft = result.scalar_one_or_none()

    if not draft:
        await callback.answer("❌ Драфт не найден", show_alert=True)
        return

    # Сохраняем в state
    await state.update_data(
        draft_id=draft_id,
        original_content=draft.content,
        article_id=draft.article_id
    )
    await state.set_state(EditDraft.waiting_for_llm_edit)

    await callback.message.answer(
        f"<b>📝 Текущий драфт:</b>\n\n{draft.content}\n\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"🤖 <b>Опишите, что нужно изменить:</b>\n"
        f"Например:\n"
        f"• Сделай тон более деловым\n"
        f"• Убери упоминание о конкретной компании\n"
        f"• Добавь больше юридического контекста\n"
        f"• Сделай короче, без потери смысла\n\n"
        f"Отправьте /cancel для отмены.",
        parse_mode="HTML"
    )


@router.message(EditDraft.waiting_for_manual_edit, Command("cancel"))
@router.message(EditDraft.waiting_for_llm_edit, Command("cancel"))
async def cancel_edit(message: Message, state: FSMContext):
    """Отмена редактирования."""
    await state.clear()
    await message.answer("❌ Редактирование отменено.")


@router.message(EditDraft.waiting_for_manual_edit)
async def process_manual_edit(message: Message, state: FSMContext, db: AsyncSession):
    """Обработка вручную отредактированного текста."""
    data = await state.get_data()
    draft_id = data.get("draft_id")

    # Получаем драфт
    result = await db.execute(
        select(PostDraft).where(PostDraft.id == draft_id)
    )
    draft = result.scalar_one_or_none()

    if not draft:
        await message.answer(f"❌ Драфт #{draft_id} не найден")
        await state.clear()
        return

    # Обновляем драфт новым текстом
    draft.content = message.text
    draft.status = 'edited'
    await db.commit()

    await message.answer(f"✅ Драфт #{draft_id} обновлен!")

    # Отправляем обновленный драфт на проверку
    await send_draft_for_review(message.chat.id, draft, db)

    await state.clear()


@router.message(EditDraft.waiting_for_llm_edit, F.voice)
async def process_voice_edit(message: Message, state: FSMContext, db: AsyncSession):
    """Обработка голосовых инструкций по редактированию."""

    # Используем встроенное распознавание Telegram (БЕСПЛАТНО!)
    if message.voice.transcription:
        # Транскрипция доступна (Telegram Premium или бот запросил)
        edit_instructions = message.voice.transcription

        await message.answer(
            f"✅ <b>Распознал:</b>\n<i>{edit_instructions}</i>\n\n⏳ Генерирую новый вариант...",
            parse_mode="HTML"
        )
    else:
        # Транскрипция недоступна - предлагаем отправить текстом
        await message.answer(
            "❌ <b>Голосовое распознавание недоступно</b>\n\n"
            "Пожалуйста, отправьте инструкции по редактированию <b>текстом</b>.\n\n"
            "<i>💡 Совет: Telegram Premium пользователи получают автоматическое распознавание голоса!</i>",
            parse_mode="HTML"
        )
        return

    # Далее та же логика редактирования
    data = await state.get_data()
    draft_id = data.get("draft_id")
    original_content = data.get("original_content")
    article_id = data.get("article_id")

    try:
        # Получаем оригинальную статью
        result = await db.execute(
            select(RawArticle).where(RawArticle.id == article_id)
        )
        article = result.scalar_one_or_none()

        # Используем выбранный LLM провайдер для редактирования
        llm = get_llm_provider(_selected_llm_provider)

        prompt = f"""Ты профессиональный редактор Telegram-постов о юридических новостях в сфере AI.

📌 ИСХОДНЫЙ ПОСТ (который нужно отредактировать):
{original_content}

📰 ОРИГИНАЛЬНАЯ СТАТЬЯ (для справки):
{article.content[:1000] if article else 'Не доступна'}

✏️ ИНСТРУКЦИИ ПОЛЬЗОВАТЕЛЯ:
{edit_instructions}

🎯 ТВОЯ ЗАДАЧА:
Внимательно прочитай инструкции пользователя и ТОЧНО выполни их. Не добавляй ничего от себя, только то что просит пользователь.

ВАЖНО:
1. Выполни ТОЛЬКО то, что просит пользователь в инструкциях
2. Сохрани общую структуру поста (заголовок, текст, хештеги)
3. Используй HTML разметку (<b>, <i>, <code>)
4. Если пользователь просит сделать короче - убери лишние детали
5. Если просит добавить - добавь релевантную информацию
6. Если просит изменить тон - измени стиль написания
7. Не выдумывай факты, используй информацию из оригинальной статьи

ВЕРНИ ТОЛЬКО отредактированный текст поста, без комментариев и пояснений."""

        new_content = await llm.generate_completion(
            messages=[
                {"role": "system", "content": "Ты опытный редактор. Строго следуй инструкциям пользователя. Возвращай только финальный текст, без объяснений."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=3500
        )

        # Сохраняем новую версию в state
        await state.update_data(new_content=new_content)

        # Показываем новый вариант с кнопками
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Опубликовать",
                    callback_data=f"publish_edited:{draft_id}"
                ),
                InlineKeyboardButton(
                    text="✏️ Редактировать дальше",
                    callback_data=f"continue_edit:{draft_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"cancel_edit:{draft_id}"
                )
            ]
        ])

        await message.answer(
            f"<b>📝 Новый вариант:</b>\n\n{new_content}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error("voice_edit_generation_error", error=str(e), provider=_selected_llm_provider)
        await message.answer(
            f"❌ Ошибка при генерации: {str(e)}\n\nПопробуйте еще раз или отправьте /cancel"
        )


@router.message(EditDraft.waiting_for_llm_edit)
async def process_edit(message: Message, state: FSMContext, db: AsyncSession):
    """Обработка текстовых инструкций по редактированию через LLM."""
    data = await state.get_data()
    draft_id = data.get("draft_id")
    original_content = data.get("original_content")
    article_id = data.get("article_id")
    edit_instructions = message.text

    await message.answer("⏳ Генерирую новый вариант...")

    try:
        # Получаем оригинальную статью
        result = await db.execute(
            select(RawArticle).where(RawArticle.id == article_id)
        )
        article = result.scalar_one_or_none()

        # Используем выбранный LLM провайдер
        llm = get_llm_provider(_selected_llm_provider)

        prompt = f"""Ты профессиональный редактор Telegram-постов о юридических новостях в сфере AI.

📌 ИСХОДНЫЙ ПОСТ (который нужно отредактировать):
{original_content}

📰 ОРИГИНАЛЬНАЯ СТАТЬЯ (для справки):
{article.content[:1000] if article else 'Не доступна'}

✏️ ИНСТРУКЦИИ ПОЛЬЗОВАТЕЛЯ:
{edit_instructions}

🎯 ТВОЯ ЗАДАЧА:
Внимательно прочитай инструкции пользователя и ТОЧНО выполни их. Не добавляй ничего от себя, только то что просит пользователь.

ВАЖНО:
1. Выполни ТОЛЬКО то, что просит пользователь в инструкциях
2. Сохрани общую структуру поста (заголовок, текст, хештеги)
3. Используй HTML разметку (<b>, <i>, <code>)
4. Если пользователь просит сделать короче - убери лишние детали
5. Если просит добавить - добавь релевантную информацию
6. Если просит изменить тон - измени стиль написания
7. Не выдумывай факты, используй информацию из оригинальной статьи

ВЕРНИ ТОЛЬКО отредактированный текст поста, без комментариев и пояснений."""

        new_content = await llm.generate_completion(
            messages=[
                {"role": "system", "content": "Ты опытный редактор. Строго следуй инструкциям пользователя. Возвращай только финальный текст, без объяснений."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=3500
        )

        # Сохраняем новую версию в state
        await state.update_data(new_content=new_content)

        # Показываем новый вариант с кнопками
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Опубликовать",
                    callback_data=f"publish_edited:{draft_id}"
                ),
                InlineKeyboardButton(
                    text="✏️ Редактировать дальше",
                    callback_data=f"continue_edit:{draft_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"cancel_edit:{draft_id}"
                )
            ]
        ])

        await message.answer(
            f"<b>📝 Новый вариант:</b>\n\n{new_content}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error("edit_generation_error", error=str(e), provider=_selected_llm_provider)
        await message.answer(
            f"❌ Ошибка при генерации: {str(e)}\n\n"
            f"Попробуйте еще раз или отправьте /cancel"
        )


@router.callback_query(F.data.startswith("publish_edited:"))
async def callback_publish_edited(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Опубликовать отредактированную версию."""
    # ВАЖНО: отвечаем сразу, чтобы кнопка не зависала
    await callback.answer("Публикую...")

    if not await check_admin(callback.from_user.id):
        return

    draft_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    new_content = data.get("new_content")

    # Обновляем драфт
    result = await db.execute(
        select(PostDraft).where(PostDraft.id == draft_id)
    )
    draft = result.scalar_one_or_none()

    if draft and new_content:
        draft.content = new_content
        draft.status = 'edited'
        await db.commit()

        # Публикуем
        success = await publish_draft(draft_id, db, callback.from_user.id)

        try:
            if success:
                # Проверяем тип сообщения (photo или text)
                if callback.message.photo:
                    await callback.message.edit_caption(
                        caption=f"✅ Отредактированный драфт #{draft_id} успешно опубликован!",
                        reply_markup=None
                    )
                else:
                    await callback.message.edit_text(
                        text=f"✅ Отредактированный драфт #{draft_id} успешно опубликован!",
                        reply_markup=None
                    )
            else:
                if callback.message.photo:
                    await callback.message.edit_caption(
                        caption=f"❌ Ошибка при публикации драфта #{draft_id}",
                        reply_markup=None
                    )
                else:
                    await callback.message.edit_text(
                        text=f"❌ Ошибка при публикации драфта #{draft_id}",
                        reply_markup=None
                    )
        except Exception as e:
            logger.error("callback_publish_edited_error", error=str(e), draft_id=draft_id)
            # Fallback - отправляем новое сообщение если редактирование не удалось
            status_msg = f"✅ Отредактированный драфт #{draft_id} успешно опубликован!" if success else f"❌ Ошибка при публикации драфта #{draft_id}"
            await callback.message.answer(status_msg)
    else:
        await callback.answer("❌ Ошибка: драфт не найден", show_alert=True)

    await state.clear()


@router.callback_query(F.data.startswith("continue_edit:"))
async def callback_continue_edit(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Продолжить редактирование."""
    if not await check_admin(callback.from_user.id):
        return

    draft_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    new_content = data.get("new_content")

    # Обновляем original_content на новую версию для следующей итерации
    await state.update_data(original_content=new_content)

    text = (f"<b>📝 Текущая версия:</b>\n\n{new_content}\n\n"
            f"━━━━━━━━━━━━━━━━\n\n"
            f"✏️ <b>Опишите дополнительные изменения:</b>")

    # Проверяем тип сообщения (photo или text)
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, parse_mode="HTML")

    await callback.answer("Опишите дополнительные изменения")


@router.callback_query(F.data.startswith("cancel_edit:"))
async def callback_cancel_edit(callback: CallbackQuery, state: FSMContext):
    """Отменить редактирование."""
    if not await check_admin(callback.from_user.id):
        return

    await state.clear()

    # Проверяем тип сообщения (photo или text)
    if callback.message.photo:
        await callback.message.edit_caption(caption="❌ Редактирование отменено.")
    else:
        await callback.message.edit_text("❌ Редактирование отменено.")

    await callback.answer("Отменено")


@router.callback_query(F.data.startswith("cancel:"))
async def callback_cancel_action(callback: CallbackQuery, db: AsyncSession):
    """Обработчик кнопки 'Отмена' в диалогах подтверждения (publish/reject)."""
    await callback.answer("Отменено")

    if not await check_admin(callback.from_user.id):
        return

    draft_id = int(callback.data.split(":")[1])

    # Возвращаем исходную клавиатуру драфта (отменяем действие)
    await callback.message.edit_reply_markup(
        reply_markup=get_draft_review_keyboard(draft_id)
    )


@router.callback_query(F.data.startswith("back_to_draft:"))
async def callback_back_to_draft(callback: CallbackQuery, db: AsyncSession):
    """Обработчик кнопки 'Назад' - возвращает исходную клавиатуру драфта."""
    await callback.answer("Отменено")

    if not await check_admin(callback.from_user.id):
        return

    draft_id = int(callback.data.split(":")[1])

    # Возвращаем исходную клавиатуру драфта (не отправляем новое сообщение!)
    await callback.message.edit_reply_markup(
        reply_markup=get_draft_review_keyboard(draft_id)
    )


# ====================
# Обработчики кнопок главного меню
# ====================

@router.callback_query(F.data == "show_drafts")
async def callback_show_drafts(callback: CallbackQuery, db: AsyncSession):
    """Показать драфты через кнопку."""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет прав доступа", show_alert=True)
        return

    # Получаем ВСЕ драфты в статусе pending_review (без фильтра по дате)
    result = await db.execute(
        select(PostDraft)
        .where(PostDraft.status == 'pending_review')
        .order_by(PostDraft.created_at.desc())
    )
    drafts = list(result.scalars().all())

    if not drafts:
        await callback.message.answer("📭 Нет новых драфтов для модерации.")
        await callback.answer()
        return

    await callback.message.answer(f"📝 Найдено {len(drafts)} драфтов. Отправляю...")

    # Отправляем каждый драфт (ограничиваем настройкой publisher_max_posts_per_day)
    max_drafts = min(len(drafts), settings.publisher_max_posts_per_day)
    for index, draft in enumerate(drafts[:max_drafts], start=1):
        await send_draft_for_review(callback.message.chat.id, draft, db, draft_number=index)

    await callback.answer("Драфты отправлены")


@router.callback_query(F.data == "run_fetch")
async def callback_run_fetch(callback: CallbackQuery):
    """Запустить сбор новостей через кнопку."""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет прав доступа", show_alert=True)
        return

    await callback.message.answer("🔄 Запускаю сбор новостей...")

    try:
        from app.tasks.celery_tasks import manual_workflow
        task = manual_workflow.delay()

        await callback.message.answer(
            f"✅ Задача запущена!\n"
            f"ID задачи: <code>{task.id}</code>\n\n"
            f"Процесс займет 5-10 минут.\n"
            f"Используйте /drafts чтобы проверить новые драфты.",
            parse_mode="HTML"
        )
        await callback.answer("Сбор запущен")
    except Exception as e:
        logger.error("fetch_error", error=str(e))
        await callback.message.answer(f"❌ Ошибка запуска: {str(e)}")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data == "show_stats")
async def callback_show_stats(callback: CallbackQuery, db: AsyncSession):
    """Показать статистику через кнопку."""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет прав доступа", show_alert=True)
        return

    stats_text = await get_statistics(db)
    await callback.message.answer(stats_text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "show_settings")
async def callback_show_settings(callback: CallbackQuery, db: AsyncSession):
    """Показать настройки через кнопку."""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔️ Нет прав доступа", show_alert=True)
        return

    # Используем новую систему настроек
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📰 Источники новостей", callback_data="settings:sources")],
        [InlineKeyboardButton(text="🤖 Модели LLM", callback_data="settings:llm")],
        [InlineKeyboardButton(text="🎨 Генерация изображений (DALL-E)", callback_data="settings:dalle")],
        [InlineKeyboardButton(text="📅 Автопубликация", callback_data="settings:autopublish")],
        [InlineKeyboardButton(text="🔄 Сбор новостей", callback_data="settings:fetcher")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="settings:alerts")],
        [InlineKeyboardButton(text="🎯 Фильтрация и качество", callback_data="settings:quality")],
        [InlineKeyboardButton(text="💰 Бюджет API", callback_data="settings:budget")],
        [InlineKeyboardButton(text="« Назад", callback_data="back_to_main_menu")],
    ])

    await callback.message.edit_text(
        "⚙️ <b>Системные настройки</b>\n\n"
        "Все параметры сохраняются в базе данных и применяются автоматически.\n\n"
        "Выберите категорию:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "show_llm_selection")
async def callback_show_llm_selection(callback: CallbackQuery):
    """Показать выбор LLM провайдера."""
    await callback.answer()

    if not await check_admin(callback.from_user.id):
        return

    await callback.message.answer(
        "🤖 <b>Выберите LLM провайдера:</b>\n\n"
        "• <b>OpenAI</b> - GPT-4o-mini для быстрой генерации текста\n"
        "• <b>Perplexity</b> - Llama 3.1 с доступом к актуальной информации\n"
        "• <b>DeepSeek</b> - DeepSeek V3 (самый дешевый, рекомендуется)",
        parse_mode="HTML",
        reply_markup=get_llm_selection_keyboard(_selected_llm_provider)
    )




# ====================
# Утилитарные функции
# ====================

async def send_draft_for_review(chat_id: int, draft: PostDraft, db: AsyncSession, bot=None, draft_number: int = None):
    """
    Отправить драфт администратору на модерацию.

    Args:
        chat_id: ID чата для отправки
        draft: Драфт поста
        db: Сессия БД
        bot: Опциональный экземпляр Bot (для использования в Celery tasks)
        draft_number: Порядковый номер драфта за день (если None, используется draft.id)
    """
    try:
        if bot is None:
            bot = get_bot()

        # Получаем информацию об оригинальной статье
        result = await db.execute(
            select(RawArticle).where(RawArticle.id == draft.article_id)
        )
        article = result.scalar_one_or_none()

        # Используем порядковый номер или ID
        display_number = draft_number if draft_number is not None else draft.id

        # Формируем preview текст
        preview_header = f"🆕 <b>Новый драфт #{display_number}</b>"

        preview_footer = f"""
━━━━━━━━━━━━━━━━
📊 Confidence: {draft.confidence_score:.2f}
🔗 Источник: {article.source_name if article else 'Unknown'}
⏰ Создан: {draft.created_at.strftime('%d.%m.%Y %H:%M')}
"""

        full_preview_text = f"{preview_header}\n\n{draft.content}\n{preview_footer}"

        # Отправляем с изображением если есть
        if draft.image_path:
            # Отправляем двумя сообщениями для обхода лимита caption (1024 символа)
            photo = FSInputFile(draft.image_path)
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=preview_header
            )

            # Отправляем полный текст preview с кнопками
            await bot.send_message(
                chat_id=chat_id,
                text=f"{draft.content}\n{preview_footer}",
                reply_markup=get_draft_review_keyboard(draft.id),
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=full_preview_text,
                reply_markup=get_draft_review_keyboard(draft.id),
                parse_mode="HTML"
            )

        logger.info("draft_sent_for_review", draft_id=draft.id)

    except Exception as e:
        logger.error("draft_send_error", draft_id=draft.id, error=str(e))


async def _vectorize_publication_background(pub_id: int, content: str, draft_id: int):
    """Фоновая векторизация публикации в Qdrant (не блокирует UI)."""
    try:
        vector_search = get_vector_search()
        await vector_search.add_publication(
            pub_id=pub_id,
            content=content,
            published_at=datetime.utcnow(),
            reactions={}
        )
        logger.info("publication_vectorized", pub_id=pub_id, draft_id=draft_id)
    except Exception as vec_error:
        logger.warning(
            "vectorization_failed",
            draft_id=draft_id,
            error=str(vec_error)
        )


async def publish_draft(draft_id: int, db: AsyncSession, admin_id: int) -> bool:
    """
    Опубликовать драфт в канал.

    Args:
        draft_id: ID драфта
        db: Сессия БД
        admin_id: ID администратора

    Returns:
        True если успешно, False иначе
    """
    try:
        # Получаем драфт
        result = await db.execute(
            select(PostDraft).where(PostDraft.id == draft_id)
        )
        draft = result.scalar_one_or_none()

        if not draft:
            return False

        # Получаем оригинальную статью для ссылки
        result = await db.execute(
            select(RawArticle).where(RawArticle.id == draft.article_id)
        )
        article = result.scalar_one_or_none()

        # Формируем финальный текст с интерактивными элементами
        final_text = draft.content
        logger.info("publish_draft_before_title_removal", draft_id=draft_id, has_image=bool(draft.image_path), title=draft.title[:50] if draft.title else None, content_start=final_text[:100])

        # Если есть изображение - убираем заголовок из текста (он уже на картинке)
        if draft.image_path and draft.title:
            # Сначала ищем маркеры международных новостей
            intl_markers = ["🌍 Международные новости:\n\n", "🌎 За рубежом:\n\n", "🌏 В мире:\n\n",
                           "🌐 Новости из-за рубежа:\n\n", "🗺️ Зарубежный опыт:\n\n"]

            intl_prefix = ""
            for marker in intl_markers:
                if final_text.startswith(marker):
                    intl_prefix = marker
                    final_text = final_text[len(marker):]  # Временно убираем маркер
                    break

            # Убираем заголовок (обычно в начале в тегах <b>...</b>)
            title_patterns = [
                f"<b>{draft.title}</b>\n\n",
                f"<b>{draft.title}</b>\n",
                f"{draft.title}\n\n",
                f"{draft.title}\n"
            ]
            for pattern in title_patterns:
                if final_text.startswith(pattern):
                    logger.info("publish_draft_title_pattern_matched", draft_id=draft_id, pattern=pattern[:50])
                    final_text = final_text[len(pattern):]
                    break

            # Возвращаем маркер международных новостей если был
            final_text = intl_prefix + final_text

            logger.info("publish_draft_after_title_removal", draft_id=draft_id, content_start=final_text[:100])

        # Добавляем разделитель и источник
        if article:
            final_text += f"\n\n━━━━━━━━━━━━━━━━"

            # Источник с attribution
            source_name = article.source_name if article.source_name else "Источник"
            final_text += f"\n📰 {source_name}"

        # Публикуем в канал
        if draft.image_path:
            # Публикуем двумя последовательными сообщениями для обхода лимита caption (1024 символа)
            # 1. Фото БЕЗ подписи (заголовок уже на изображении)
            photo = FSInputFile(draft.image_path)
            photo_message = await get_bot().send_photo(
                chat_id=settings.telegram_channel_id,
                photo=photo
            )

            # 2. Полный текст с интерактивными кнопками (до 4096 символов)
            text = final_text[:4096] if len(final_text) > 4096 else final_text
            message = await get_bot().send_message(
                chat_id=settings.telegram_channel_id,
                text=text,
                parse_mode="HTML",
                reply_markup=get_reader_keyboard(
                    article.url,
                    post_id=draft.id
                ) if article else None
            )
        else:
            # Telegram ограничивает text до 4096 символов
            text = final_text[:4096] if len(final_text) > 4096 else final_text
            message = await get_bot().send_message(
                chat_id=settings.telegram_channel_id,
                text=text,
                parse_mode="HTML",
                reply_markup=get_reader_keyboard(
                    article.url,
                    post_id=draft.id
                ) if article else None
            )

        # Сохраняем публикацию в БД
        publication = Publication(
            draft_id=draft.id,
            message_id=message.message_id,
            channel_id=settings.telegram_channel_id_numeric,
        )
        db.add(publication)

        # Обновляем статус драфта
        draft.status = 'approved'
        draft.reviewed_at = datetime.utcnow()
        draft.reviewed_by = admin_id

        # Сохраняем feedback
        feedback = FeedbackLabel(
            draft_id=draft.id,
            admin_action='published'
        )
        db.add(feedback)

        await db.commit()
        await db.refresh(publication)

        # Векторизация через Celery (не блокирует UI)
        if settings.qdrant_enabled:
            try:
                from app.tasks.celery_tasks import vectorize_publication_task
                vectorize_publication_task.delay(
                    pub_id=publication.id,
                    content=draft.content,
                    draft_id=draft.id
                )
                logger.info("vectorization_task_queued", pub_id=publication.id, draft_id=draft.id)
            except Exception as e:
                logger.warning("vectorization_task_queue_error", error=str(e))

        logger.info(
            "draft_published",
            draft_id=draft.id,
            message_id=message.message_id
        )

        return True

    except Exception as e:
        logger.error("publish_error", draft_id=draft_id, error=str(e))
        return False


async def reject_draft(
    draft_id: int,
    reason: str,
    db: AsyncSession,
    admin_id: int
) -> bool:
    """
    Отклонить драфт.

    Args:
        draft_id: ID драфта
        reason: Причина отклонения
        db: Сессия БД
        admin_id: ID администратора

    Returns:
        True если успешно, False иначе
    """
    try:
        result = await db.execute(
            select(PostDraft).where(PostDraft.id == draft_id)
        )
        draft = result.scalar_one_or_none()

        if not draft:
            return False

        draft.status = 'rejected'
        draft.rejection_reason = reason
        draft.reviewed_at = datetime.utcnow()
        draft.reviewed_by = admin_id

        # Сохраняем feedback
        feedback = FeedbackLabel(
            draft_id=draft.id,
            admin_action='rejected',
            rejection_reason=reason
        )
        db.add(feedback)

        await db.commit()

        logger.info("draft_rejected", draft_id=draft.id, reason=reason)

        return True

    except Exception as e:
        logger.error("reject_error", draft_id=draft_id, error=str(e))
        return False


@router.callback_query(F.data.startswith("opinion:"))
async def callback_opinion(callback: CallbackQuery, db: AsyncSession):
    """
    Показать клавиатуру для выбора мнения о посте (редактирует клавиатуру под постом).
    """
    try:
        # Извлекаем post_id из callback_data
        post_id = int(callback.data.split(":")[1])

        # Редактируем клавиатуру под постом (не создаем новое сообщение!)
        await callback.message.edit_reply_markup(
            reply_markup=get_opinion_keyboard(post_id)
        )

        # Показываем уведомление (не alert, просто тост)
        await callback.answer("📊 Выберите вашу реакцию ⬇️")

    except Exception as e:
        logger.error("opinion_callback_error", error=str(e))
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("react:"))
async def callback_react(callback: CallbackQuery, db: AsyncSession):
    """
    Обработать реакцию пользователя на пост.
    """
    try:
        # Извлекаем данные из callback_data: react:post_id:reaction_type
        parts = callback.data.split(":")
        if len(parts) != 3:
            await callback.answer("❌ Неверный формат данных", show_alert=True)
            return
            
        post_id = int(parts[1])
        reaction_type = parts[2]
        
        logger.info("callback_react_started", callback_data=callback.data)
        
        # Поиск публикации
        result = await db.execute(
            select(Publication)
            .join(PostDraft)
            .where(PostDraft.id == post_id)
        )
        publication = result.scalar_one_or_none()
        
        if not publication:
            logger.warning("publication_not_found", post_id=post_id)
            await callback.answer("❌ Публикация не найдена", show_alert=True)
            return
        
        # Обновляем реакции
        current_reactions = publication.reactions or {}
        current_count = current_reactions.get(reaction_type, 0)
        current_reactions[reaction_type] = current_count + 1
        publication.reactions = current_reactions
        
        await db.commit()
        
        # Получаем обновленные реакции для отображения
        reactions = publication.reactions or {}
        
        # Формируем текст с реакциями
        reaction_emoji = {
            "useful": "👍",
            "important": "🔥",
            "controversial": "🤔",
            "banal": "💤",
            "obvious": "🤷",
            "poor_quality": "👎",
            "low_content_quality": "📉",
            "bad_source": "📰"
        }
        
        reaction_text = {
            "useful": "Полезно",
            "important": "Важно",
            "controversial": "Спорно",
            "banal": "Банально",
            "obvious": "Очевидно",
            "poor_quality": "Плохое качество",
            "low_content_quality": "Низкое качество контента",
            "bad_source": "Плохой источник"
        }
        
        reaction_lines = []
        for reaction, emoji in reaction_emoji.items():
            count = reactions.get(reaction, 0)
            if count > 0:
                text = reaction_text.get(reaction, reaction)
                reaction_lines.append(f"{emoji} {text}: {count}")
        
        reaction_summary = "\n".join(reaction_lines) if reaction_lines else "Пока нет реакций"
        
        # Отправляем уведомление
        await callback.answer(f"✅ Спасибо! Ваша реакция учтена.\n\n📊 Текущая статистика:\n{reaction_summary}", show_alert=True)

        # Убираем кнопки реакций, оставляем только ссылку на источник (БЕЗ кнопки "Ваше мнение")
        try:
            # Получаем draft и article для клавиатуры
            draft_result = await db.execute(
                select(PostDraft).where(PostDraft.id == post_id)
            )
            draft = draft_result.scalar_one_or_none()

            article_url = ""
            if draft and draft.article_id:
                article_result = await db.execute(
                    select(RawArticle).where(RawArticle.id == draft.article_id)
                )
                article = article_result.scalar_one_or_none()
                if article:
                    article_url = article.url

            # Возвращаем клавиатуру БЕЗ кнопки "Ваше мнение" (post_id=None скрывает кнопку)
            await callback.message.edit_reply_markup(
                reply_markup=get_reader_keyboard(article_url, post_id=None)
            )
        except Exception as edit_error:
            logger.error("keyboard_restore_error", error=str(edit_error))

        logger.info("reaction_processed", post_id=post_id, reaction_type=reaction_type, total_reactions=sum(reactions.values()))

    except Exception as e:
        logger.error("react_callback_error", error=str(e))
        await callback.answer("❌ Произошла ошибка при обработке реакции", show_alert=True)
    pending_count = await db.scalar(
        select(func.count(PostDraft.id)).where(PostDraft.status == 'pending_review')
    )

    # Статистика личных постов
    personal_posts_count = await db.scalar(select(func.count(PersonalPost.id)))
    personal_published_count = await db.scalar(
        select(func.count(PersonalPost.id)).where(PersonalPost.published == True)
    )

    # Статистика views/reactions для личных постов
    personal_views_sum = await db.scalar(
        select(func.sum(PersonalPost.views_count)).where(PersonalPost.published == True)
    ) or 0
    personal_reactions_sum = await db.scalar(
        select(func.sum(PersonalPost.reactions_count)).where(PersonalPost.published == True)
    ) or 0

    # Получаем стоимость API за текущий месяц
    api_cost_data = await get_current_month_cost(db)

    # Получаем статистику AI анализа
    analytics = AnalyticsService(db)
    ai_stats = await analytics.get_ai_analysis_stats()

    stats_text = f"""
📊 <b>Статистика системы</b>

📰 Всего статей: {articles_count}
📝 Всего драфтов: {drafts_count}
✅ Опубликовано: {publications_count}
⏳ Ожидают модерации: {pending_count}

━━━━━━━━━━━━━━━━

✍️ <b>Личные заметки</b>

📔 Всего заметок: {personal_posts_count}
📤 Опубликовано: {personal_published_count}
👁 Всего просмотров: {personal_views_sum:,}
👍 Всего реакций: {personal_reactions_sum}

━━━━━━━━━━━━━━━━

💰 <b>Стоимость API за {api_cost_data['month_name']}</b>

💵 Общая стоимость: ${api_cost_data['total_cost_usd']:.4f}
📊 Всего токенов: {api_cost_data['total_tokens']:,}
🔢 Всего запросов: {api_cost_data['total_requests']}
"""

    # Добавляем статистику по провайдерам
    if api_cost_data['by_provider']:
        stats_text += "\n<b>По провайдерам:</b>\n"
        for provider, data in api_cost_data['by_provider'].items():
            provider_name = "OpenAI" if provider == "openai" else "Perplexity"
            stats_text += f"├─ {provider_name}:\n"
            stats_text += f"│  ├─ Стоимость: ${data['cost_usd']:.4f}\n"
            stats_text += f"│  ├─ Токенов: {data['tokens']:,}\n"
            stats_text += f"│  └─ Запросов: {data['requests']}\n"

    # Ссылка на проверку баланса Perplexity
    stats_text += "\n🔗 <a href='https://www.perplexity.ai/account/api/billing'>Проверить баланс Perplexity API</a>\n"

    # Добавляем статистику AI анализа
    stats_text += "\n━━━━━━━━━━━━━━━━\n\n"
    stats_text += "🤖 <b>AI Анализ аналитики</b>\n\n"

    if ai_stats['month']['count'] > 0 or ai_stats['year']['count'] > 0:
        stats_text += f"<b>За текущий месяц:</b>\n"
        stats_text += f"├─ Запросов: {ai_stats['month']['count']}\n"
        stats_text += f"├─ Токенов: {ai_stats['month']['total_tokens']:,}\n"
        stats_text += f"└─ Стоимость: ${ai_stats['month']['total_cost_usd']:.4f}\n"

        # Разбивка по моделям за месяц
        if ai_stats['month']['by_model']:
            for model, data in ai_stats['month']['by_model'].items():
                model_name = model.replace('gpt-', 'GPT-').upper()
                stats_text += f"   └─ {model_name}: {data['count']} запросов, ${data['cost_usd']:.4f}\n"

        stats_text += f"\n<b>За текущий год:</b>\n"
        stats_text += f"├─ Запросов: {ai_stats['year']['count']}\n"
        stats_text += f"├─ Токенов: {ai_stats['year']['total_tokens']:,}\n"
        stats_text += f"└─ Стоимость: ${ai_stats['year']['total_cost_usd']:.2f}\n"

        # Разбивка по моделям за год
        if ai_stats['year']['by_model']:
            for model, data in ai_stats['year']['by_model'].items():
                model_name = model.replace('gpt-', 'GPT-').upper()
                stats_text += f"   └─ {model_name}: {data['count']} запросов, ${data['cost_usd']:.2f}\n"
    else:
        stats_text += "Анализы ещё не запускались\n"

    stats_text += f"\n📅 Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"

    return stats_text


# ====================
# Analytics Dashboard
# ====================

def format_analytics_report(
    stats: Dict,
    top_posts: List[Dict],
    worst_posts: List[Dict],
    sources: List[Dict],
    weekday_stats: Dict,
    vector_stats: Optional[Dict],
    source_recommendations: Optional[List[Dict]] = None,
    views_stats: Optional[Dict] = None,
    best_time: Optional[Dict] = None,
    trending_topics: Optional[List[Dict]] = None,
    alerts: Optional[List[Dict]] = None,
    conversion_funnel: Optional[Dict] = None,
) -> str:
    """
    Форматировать красивый отчёт аналитики.

    Args:
        stats: Общая статистика
        top_posts: Топ постов
        worst_posts: Худшие посты
        sources: Статистика источников
        weekday_stats: Статистика по дням недели
        vector_stats: Статистика векторной базы

    Returns:
        Отформатированный текст отчёта
    """
    period_days = stats.get("period_days", 7)

    report = f"""📊 <b>Аналитика канала @legal_ai_pro</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 <b>За последние {period_days} дней:</b>

<b>Публикации:</b>
├─ 📝 Опубликовано: {stats['total_publications']} постов
├─ ✅ Одобрено: {stats['approved_drafts']} из {stats['total_drafts']} драфтов ({stats['approval_rate']:.0f}%)
├─ ❌ Отклонено: {stats['rejected_drafts']} драфтов
└─ 📊 Avg quality score: {stats['avg_quality_score']}

<b>Реакции:</b>
├─ 👍 Полезно: {stats['reactions']['useful']} ({stats['reactions']['useful']/max(stats['total_reactions'],1)*100:.0f}%)
├─ 🔥 Важно: {stats['reactions']['important']} ({stats['reactions']['important']/max(stats['total_reactions'],1)*100:.0f}%)
├─ 🤔 Спорно: {stats['reactions']['controversial']} ({stats['reactions']['controversial']/max(stats['total_reactions'],1)*100:.0f}%)
├─ 💤 Банальщина: {stats['reactions']['banal']} ({stats['reactions']['banal']/max(stats['total_reactions'],1)*100:.0f}%)
├─ 🤷 Очевидно: {stats['reactions']['obvious']} ({stats['reactions']['obvious']/max(stats['total_reactions'],1)*100:.0f}%)
├─ 👎 Плохое: {stats['reactions']['poor_quality']} ({stats['reactions']['poor_quality']/max(stats['total_reactions'],1)*100:.0f}%)
├─ 📉 Низкое качество: {stats['reactions']['low_content_quality']} ({stats['reactions']['low_content_quality']/max(stats['total_reactions'],1)*100:.0f}%)
└─ 📰 Плохой источник: {stats['reactions']['bad_source']} ({stats['reactions']['bad_source']/max(stats['total_reactions'],1)*100:.0f}%)

<b>Engagement:</b>
├─ 📊 Всего реакций: {stats['total_reactions']}
├─ 💬 Постов с реакциями: {stats['engaged_publications']} из {stats['total_publications']}
└─ 🎯 Engagement rate: {stats['engagement_rate']}%
"""

    # Топ посты
    if top_posts:
        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "🔥 <b>Топ-3 поста:</b>\n\n"

        for i, post in enumerate(top_posts[:3], 1):
            title_raw = post['title'][:80] + "..." if len(post['title']) > 80 else post['title']
            title = html.escape(title_raw)
            date = post['published_at'].strftime('%d.%m.%Y %H:%M')
            reactions = post['reactions']

            report += f"{i}️⃣ <b>{title}</b>\n"
            report += f"   📅 {date}\n"
            report += f"   👍 {reactions.get('useful', 0)} | 🔥 {reactions.get('important', 0)} | 🤔 {reactions.get('controversial', 0)}\n"
            report += f"   📊 Quality: {post['quality_score']}\n"
            if post['telegram_message_id']:
                msg_id = post['telegram_message_id']
                report += f'   🔗 <a href="https://t.me/legal_ai_pro/{msg_id}">Перейти к посту</a>\n'
            report += "\n"

    # Худшие посты
    if worst_posts:
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "💤 <b>Худшие посты (учимся на ошибках):</b>\n\n"

        for i, post in enumerate(worst_posts[:3], 1):
            title_raw = post['title'][:80] + "..." if len(post['title']) > 80 else post['title']
            title = html.escape(title_raw)
            date = post['published_at'].strftime('%d.%m.%Y %H:%M')
            reactions = post['reactions']

            report += f"{i}️⃣ <b>{title}</b>\n"
            report += f"   📅 {date}\n"
            report += f"   💤 {reactions.get('banal', 0)} | 👎 {reactions.get('poor_quality', 0)} | 🤷 {reactions.get('obvious', 0)}\n"
            report += f"   📊 Quality: {post['quality_score']}\n"

            # Определить основную проблему
            if reactions.get('banal', 0) > 0:
                report += "   ⚠️ Проблема: Слишком общо, нет конкретики\n"
            elif reactions.get('obvious', 0) > 0:
                report += "   ⚠️ Проблема: Очевидные выводы\n"
            elif reactions.get('poor_quality', 0) > 0:
                report += "   ⚠️ Проблема: Низкое качество контента\n"
            elif reactions.get('low_content_quality', 0) > 0:
                report += "   ⚠️ Проблема: Плохая подача материала\n"
            elif reactions.get('bad_source', 0) > 0:
                report += "   ⚠️ Проблема: Ненадежный или некачественный источник\n"

            report += "\n"

    # Статистика по дням недели (если есть данные)
    if weekday_stats:
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "📅 <b>Статистика по дням недели:</b>\n\n"

        best_day = None
        best_score = -999.0

        for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]:
            if day in weekday_stats:
                day_data = weekday_stats[day]
                total = day_data['total_posts']
                avg_score = day_data['avg_quality_score']

                if avg_score > best_score:
                    best_score = avg_score
                    best_day = day

                marker = "⭐" if day == best_day and total > 0 else ""
                report += f"{day}: {total} постов | Avg quality: {avg_score} {marker}\n"

        if best_day:
            report += f"\n🏆 Лучший день: <b>{best_day}</b> (avg quality: {best_score})\n"

    # Эффективность источников
    if sources:
        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "📰 <b>Топ источников:</b>\n\n"

        for i, source in enumerate(sources[:5], 1):
            name_raw = source['source_name'][:40] + "..." if len(source['source_name']) > 40 else source['source_name']
            name = html.escape(name_raw)
            collected = source['total_collected']
            published = source['total_published']
            pub_rate = source['publication_rate']
            quality = source['avg_quality_score']

            status = ""
            if quality >= 0.6:
                status = "✅"
            elif quality >= 0.3:
                status = "⚠️"
            else:
                status = "❌"

            report += f"{i}. <b>{name}</b> {status}\n"
            report += f"   ├─ Отобрано: {collected} новостей\n"
            report += f"   ├─ Опубликовано: {published} ({pub_rate:.0f}%)\n"
            report += f"   └─ Avg quality: {quality}\n"
            report += "\n"

    # Статистика векторной базы
    if vector_stats:
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "🗄️ <b>Векторная база Qdrant:</b>\n\n"
        report += f"├─ 📦 Всего векторов: {vector_stats['total_vectors']}\n"
        report += f"├─ ✅ Позитивных примеров: {vector_stats['positive_examples']} (score &gt; 0.5)\n"
        report += f"├─ ❌ Негативных примеров: {vector_stats['negative_examples']} (score &lt; -0.3)\n"
        report += f"├─ ⚖️ Нейтральных: {vector_stats['neutral_examples']}\n"
        report += f"└─ 📊 Avg score всей базы: {vector_stats['avg_quality_score']}\n"

    # Рекомендации по источникам
    if source_recommendations:
        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "⚡ <b>Рекомендации по источникам:</b>\n\n"

        for rec in source_recommendations[:5]:  # Показываем топ-5
            source_name_escaped = html.escape(rec["source_name"])
            report += f"<b>{source_name_escaped}</b>\n"
            report += f"   {rec['recommendation']}\n"
            report += f"   ├─ Публикаций: {rec['total_publications']}\n"
            report += f"   ├─ Avg quality: {rec['avg_quality_score']}\n"
            report += f"   ├─ Реакций 'Плохой источник': {rec['bad_source_reactions']}\n"
            report += f"   └─ Реакций 'Низкое качество': {rec['low_quality_reactions']}\n"
            report += "\n"

        if not source_recommendations:
            report += "✅ Все источники работают хорошо!\n"

    # Views и Forwards статистика
    # Просмотры и форварды (Telegram metrics)
    report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    report += "📈 <b>Просмотры и Форварды:</b>\n\n"

    if views_stats and views_stats.get('total_views', 0) > 0:
        report += f"├─ 👁️ Всего просмотров: {views_stats['total_views']:,}\n"
        report += f"├─ 📤 Всего форвардов: {views_stats['total_forwards']:,}\n"
        report += f"├─ 📊 Avg просмотров/пост: {views_stats['avg_views']}\n"
        report += f"├─ 📊 Avg форвардов/пост: {views_stats['avg_forwards']}\n"
        report += f"├─ 🔥 Макс просмотров: {views_stats['max_views']:,}\n"
        report += f"├─ 🔥 Макс форвардов: {views_stats['max_forwards']:,}\n"
        report += f"└─ 🌊 Viral coefficient: {views_stats['viral_coefficient']}%\n"
    else:
        report += "⚠️ <b>Данные недоступны</b>\n"
        report += "├─ Метрики из Telegram еще не собраны\n"
        report += "├─ Celery задача запускается каждые 6 часов\n"
        report += "├─ Следующий запуск: 00:00 / 06:00 / 12:00 / 18:00 MSK\n"
        report += "└─ Или проверьте логи: docker compose logs celery_worker | grep collect_telegram_metrics\n"

    # A/B тестирование времени публикации
    report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    report += "⏰ <b>Лучшее время для публикации:</b>\n\n"

    if best_time and best_time.get('best_hour') is not None:
        report += f"🎯 {best_time['recommendation']}\n"
        report += f"├─ Engagement rate: {best_time['best_engagement_rate']}%\n"
        report += f"└─ На основе анализа за 30 дней\n"
    else:
        report += "⚠️ <b>Недостаточно данных</b>\n"
        report += "└─ Требуется хотя бы 1 публикация с views для анализа\n"

    # Трендовые темы
    report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    report += "🔥 <b>Трендовые темы:</b>\n\n"

    if trending_topics:
        for i, topic in enumerate(trending_topics[:5], 1):
            report += f"{i}. <b>{topic['topic']}</b>\n"
            report += f"   ├─ Упоминаний: {topic['mentions']}\n"
            report += f"   └─ Relevance: {topic['relevance_score']}%\n"
    else:
        report += "⚠️ <b>Не найдено</b>\n"
        report += "└─ Требуется больше публикаций с детальным контентом\n"

    # Алерты и предупреждения
    if alerts:
        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "🚨 <b>Алерты и предупреждения:</b>\n\n"
        for alert in alerts:
            report += f"{alert['message']}\n"
            report += f"   └─ {alert['details']}\n\n"

    if conversion_funnel:
        stages = conversion_funnel.get("stages") or []
        rates = conversion_funnel.get("rates") or []
        stage_map = {str(item.get("key")): int(item.get("users", 0)) for item in stages if isinstance(item, dict)}
        rate_map = {str(item.get("key")): float(item.get("value", 0.0)) for item in rates if isinstance(item, dict)}
        top_sources = conversion_funnel.get("top_miniapp_sources") or []
        top_actions = conversion_funnel.get("top_actions") or []
        leads_total = int(conversion_funnel.get("leads_total", 0) or 0)
        unique_total = int(conversion_funnel.get("unique_users_total", 0) or 0)
        hours = int(conversion_funnel.get("hours", 0) or 0)

        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "🔀 <b>Сквозная воронка Reader/Mini App</b>\n\n"
        report += f"Период: {hours}ч | Уникальных пользователей: {unique_total}\n"
        report += f"├─ 🧩 Mini App активные: {stage_map.get('miniapp_active', 0)}\n"
        report += f"├─ 🎯 CTA клики: {stage_map.get('cta_click', 0)}\n"
        report += f"├─ 📝 Lead intent: {stage_map.get('lead_intent', 0)}\n"
        report += f"└─ 👤 Создано лидов: {leads_total}\n\n"
        report += f"CR MiniApp → CTA: {rate_map.get('miniapp_to_cta', 0.0):.2f}%\n"
        report += f"CR CTA → Intent: {rate_map.get('cta_to_intent', 0.0):.2f}%\n"
        report += f"CR MiniApp → Intent: {rate_map.get('miniapp_to_intent', 0.0):.2f}%\n"

        if top_sources:
            report += "\nТоп источники Mini App:\n"
            for idx, item in enumerate(top_sources[:3], 1):
                label = html.escape(str(item.get("label", "unknown")))
                count = int(item.get("count", 0) or 0)
                report += f"{idx}. {label} — {count}\n"

        if top_actions:
            report += "\nТоп actions:\n"
            for idx, item in enumerate(top_actions[:5], 1):
                label = html.escape(str(item.get("label", "unknown")))
                count = int(item.get("count", 0) or 0)
                report += f"{idx}. {label} — {count}\n"

    report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    report += f"📅 Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"

    return report


@router.message(Command("analytics"))
async def cmd_analytics(message: Message, db: AsyncSession):
    """Показать аналитику канала."""

    if not await check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде")
        return

    # Клавиатура выбора периода
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 7 дней", callback_data="analytics:7"),
            InlineKeyboardButton(text="📅 30 дней", callback_data="analytics:30"),
        ],
        [
            InlineKeyboardButton(text="📅 Всё время", callback_data="analytics:all"),
        ],
        [
            InlineKeyboardButton(text="🤖 AI Анализ", callback_data="show_ai_analysis_menu"),
        ]
    ])

    await message.answer(
        "📊 <b>Выберите период для аналитики:</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.message(Command("moderation"))
async def cmd_moderation(message: Message):
    """Показать статистику модерации канала."""
    if not await check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде")
        return

    try:
        moderator = get_channel_moderator()
        stats = moderator.get_moderation_stats()

        # Рассчитываем проценты
        total = stats['total_comments']
        if total > 0:
            moderated_percent = (stats['moderated_comments'] / total) * 100
            blocked_percent = (stats['blocked_comments'] / total) * 100
            spam_percent = (stats['spam_detected'] / total) * 100
            off_topic_percent = (stats['off_topic'] / total) * 100
            negative_percent = (stats['negative_sentiment'] / total) * 100
        else:
            moderated_percent = blocked_percent = spam_percent = off_topic_percent = negative_percent = 0

        report = f"""🛡️ <b>Статистика модерации канала</b>

📊 <b>Общая статистика:</b>
• Всего комментариев: {total:,}
• Промодерировано: {stats['moderated_comments']:,} ({moderated_percent:.1f}%)

🚫 <b>Заблокировано:</b>
• Спам: {stats['spam_detected']:,} ({spam_percent:.1f}%)
• Запрещенные слова: {stats['blocked_comments']:,} ({blocked_percent:.1f}%)

⚠️ <b>Предупреждения:</b>
• Не по теме: {stats['off_topic']:,} ({off_topic_percent:.1f}%)
• Негативные: {stats['negative_sentiment']:,} ({negative_percent:.1f}%)

💡 <b>Модерация работает автоматически и:</b>
• Удаляет спам и запрещенный контент
• Предупреждает о нерелевантных комментариях
• Сохраняет статистику для анализа
• Улучшает качество обсуждений в канале"""

        # Клавиатура для управления
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Сбросить статистику", callback_data="moderation:reset_stats")],
            [InlineKeyboardButton(text="📋 Подробный отчет", callback_data="moderation:detailed_report")]
        ])

        await message.answer(
            report,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error getting moderation stats: {e}")
        await message.answer("❌ Ошибка при получении статистики модерации")


@router.callback_query(F.data.startswith("moderation:"))
async def handle_moderation_actions(callback: CallbackQuery):
    """Обработка действий модерации."""
    action = callback.data.split(":")[1]

    if action == "reset_stats":
        try:
            moderator = get_channel_moderator()
            moderator.reset_stats()

            await callback.message.edit_text(
                "✅ <b>Статистика модерации сброшена</b>\n\n"
                "Новая статистика начнет собираться с следующих комментариев.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error resetting moderation stats: {e}")
            await callback.answer("❌ Ошибка при сбросе статистики", show_alert=True)

    elif action == "detailed_report":
        # Показать детальную статистику
        try:
            moderator = get_channel_moderator()
            stats = moderator.get_moderation_stats()

            detailed_report = f"""📋 <b>Детальный отчет модерации</b>

🕐 <b>Текущая сессия:</b>
• Всего комментариев: {stats['total_comments']:,}
• Модерировано: {stats['moderated_comments']:,}
• Заблокировано: {stats['blocked_comments']:,}
• Спам обнаружен: {stats['spam_detected']:,}

🎯 <b>По категориям:</b>
• Нерелевантные: {stats['off_topic']:,}
• Негативные: {stats['negative_sentiment']:,}

🤖 <b>AI-модерация:</b>
Модуль использует гибридный подход:
• Базовая фильтрация (спам, запрещенные слова)
• AI-анализ тональности и релевантности
• Автоматические действия (удаление/предупреждение)

⚙️ <b>Настройки:</b>
• Канал: @{settings.telegram_channel_id.replace('@', '') if settings.telegram_channel_id else 'не настроен'}
• Автомодерация: ✅ Включена
• Уровень строгости: Средний"""

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="« Назад", callback_data="back_to_moderation")]
            ])

            await callback.message.edit_text(
                detailed_report,
                parse_mode="HTML",
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Error generating detailed moderation report: {e}")
            await callback.answer("❌ Ошибка при генерации отчета", show_alert=True)

    elif action == "back_to_moderation":
        # Имитация вызова команды moderation
        await callback.message.edit_text(
            "🛡️ <b>Модерация канала</b>\n\n"
            "Используйте /moderation для просмотра статистики.",
            parse_mode="HTML"
        )

    await callback.answer()


@router.message(Command("lead_analytics"))
async def cmd_lead_analytics(message: Message, db: AsyncSession):
    """Показать аналитику лидов."""
    if not await check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде")
        return

    try:
        from app.modules.analytics import AnalyticsService
        analytics = AnalyticsService(db)

        # Получаем аналитику за 30 дней
        lead_data = await analytics.get_lead_analytics(days=30)
        roi_data = await analytics.get_lead_magnet_roi(days=30)

        overview = lead_data["overview"]

        report = f"""🎯 <b>Аналитика лидов (30 дней)</b>

📊 <b>Обзор:</b>
• Всего лидов: {overview['total_leads']:,}
• Квалифицированных: {overview['qualified_leads']:,} ({overview['qualification_rate']}%)
• Конвертированных: {overview['converted_leads']:,} ({overview['conversion_rate']}%)
• Завершили лид-магнит: {overview['completed_magnet']:,} ({overview['magnet_completion_rate']}%)

📝 <b>Контактная информация:</b>
• С email: {overview['with_email']:,}
• С телефоном: {overview['with_phone']:,}
• С компанией: {overview['with_company']:,}

📈 <b>Средний скор лида:</b> {overview['avg_lead_score']}/100

💰 <b>ROI лид-магнита:</b>
• Затраты на API: ${roi_data['costs']['api_cost']:.2f}
• Оценочная выручка: ₽{roi_data['revenue']['estimated_revenue']:,}
• Прибыль: ₽{roi_data['metrics']['profit']:,}
• ROI: {roi_data['metrics']['roi_percent']:.1f}%

💵 <b>Экономика:</b>
• Стоимость лида: ₽{roi_data['metrics']['cost_per_lead']:.2f}
• Стоимость качественного лида: ₽{roi_data['metrics']['cost_per_quality_lead']:.2f}"""

        # Клавиатура для детального просмотра
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 Динамика", callback_data="leads:daily_stats"),
                InlineKeyboardButton(text="🏆 Топ лидов", callback_data="leads:top_leads")
            ],
            [
                InlineKeyboardButton(text="📊 По источникам", callback_data="leads:sources"),
                InlineKeyboardButton(text="💰 Детальный ROI", callback_data="leads:roi_details")
            ]
        ])

        await message.answer(
            report,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error getting lead analytics: {e}")
        await message.answer("❌ Ошибка при получении аналитики лидов")


@router.callback_query(F.data.startswith("leads:"))
async def handle_lead_analytics_callbacks(callback: CallbackQuery, db: AsyncSession):
    """Обработка callback-запросов аналитики лидов."""
    if not await check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    action = callback.data.split(":")[1]

    try:
        from app.modules.analytics import AnalyticsService
        analytics = AnalyticsService(db)

        if action == "daily_stats":
            # Динамика лидов по дням
            lead_data = await analytics.get_lead_analytics(days=30)
            daily_stats = lead_data["daily_stats"][:7]  # Последние 7 дней

            report = "📈 <b>Динамика лидов (7 дней)</b>\n\n"
            for stat in daily_stats:
                report += f"📅 {stat['date']}: +{stat['new_leads']} лидов, "
                report += f"✅ {stat['completed_magnet']} магнит, "
                report += f"🎯 {stat['qualified']} квалиф.\n"

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="« Назад", callback_data="leads:back_to_main")]
            ])

        elif action == "top_leads":
            # Топ лидов по скорингу
            lead_data = await analytics.get_lead_analytics(days=30)
            top_leads = lead_data["top_leads"][:5]

            report = "🏆 <b>Топ-5 лидов по скорингу</b>\n\n"
            for i, lead in enumerate(top_leads, 1):
                report += f"{i}. <b>{lead['full_name'] or lead['username'] or 'User'}</b>\n"
                report += f"   📧 {lead['email'] or 'нет'}\n"
                report += f"   🏢 {lead['company'] or 'нет'}\n"
                report += f"   📊 Скор: {lead['lead_score']}/100\n\n"

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="« Назад", callback_data="leads:back_to_main")]
            ])

        elif action == "sources":
            # Статистика по источникам
            lead_data = await analytics.get_lead_analytics(days=30)
            sources_stats = lead_data["sources_stats"]

            report = "📊 <b>Лиды по сферам бизнеса</b>\n\n"
            for source in sources_stats:
                report += f"🏗️ <b>{source['source']}</b>: {source['count']} лидов\n"
                report += f"   📈 Ср. скор: {source['avg_score']}/100\n"
                report += f"   ✅ Завершили: {source['completed_rate']}%\n\n"

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="« Назад", callback_data="leads:back_to_main")]
            ])

        elif action == "roi_details":
            # Детальный ROI
            roi_data = await analytics.get_lead_magnet_roi(days=30)

            report = f"""💰 <b>Детальный ROI лид-магнита</b>

💵 <b>Затраты:</b>
• API OpenAI/Perplexity: ${roi_data['costs']['api_cost']:.2f}
• Итого затрат: ${roi_data['costs']['total_cost']:.2f}

📈 <b>Результаты:</b>
• Всего лидов: {roi_data['revenue']['total_leads']:,}
• Качественных лидов: {roi_data['revenue']['quality_leads']:,}
• Оценка ценности лида: ₽{roi_data['revenue']['assumed_lead_value']:,}
• Оценочная выручка: ₽{roi_data['revenue']['estimated_revenue']:,}

📊 <b>Метрики:</b>
• Прибыль: ₽{roi_data['metrics']['profit']:,}
• ROI: {roi_data['metrics']['roi_percent']:.1f}%
• Стоимость лида: ₽{roi_data['metrics']['cost_per_lead']:.2f}
• Ср. скор лида: {roi_data['metrics']['avg_lead_score']:.1f}/100"""

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="« Назад", callback_data="leads:back_to_main")]
            ])

        elif action == "back_to_main":
            # Возврат к основной аналитике лидов
            lead_data = await analytics.get_lead_analytics(days=30)
            roi_data = await analytics.get_lead_magnet_roi(days=30)
            overview = lead_data["overview"]

            report = f"""🎯 <b>Аналитика лидов (30 дней)</b>

📊 <b>Обзор:</b>
• Всего лидов: {overview['total_leads']:,}
• Квалифицированных: {overview['qualified_leads']:,} ({overview['qualification_rate']}%)
• Конвертированных: {overview['converted_leads']:,} ({overview['conversion_rate']}%)
• Завершили лид-магнит: {overview['completed_magnet']:,} ({overview['magnet_completion_rate']}%)

💰 <b>ROI:</b> {roi_data['metrics']['roi_percent']:.1f}% (₽{roi_data['metrics']['profit']:,} прибыли)"""

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📈 Динамика", callback_data="leads:daily_stats"),
                    InlineKeyboardButton(text="🏆 Топ лидов", callback_data="leads:top_leads")
                ],
                [
                    InlineKeyboardButton(text="📊 По источникам", callback_data="leads:sources"),
                    InlineKeyboardButton(text="💰 Детальный ROI", callback_data="leads:roi_details")
                ]
            ])

        await callback.message.edit_text(
            report,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error in lead analytics callback: {e}")
        await callback.answer("❌ Ошибка при обработке запроса", show_alert=True)

    await callback.answer()


@router.message(Command("settings"))
async def cmd_settings(message: Message, db: AsyncSession):
    """Системные настройки."""

    if not await check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде")
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📰 Источники новостей", callback_data="settings:sources")],
        [InlineKeyboardButton(text="🤖 Модели LLM", callback_data="settings:llm")],
        [InlineKeyboardButton(text="🎨 Генерация изображений (DALL-E)", callback_data="settings:dalle")],
        [InlineKeyboardButton(text="📅 Автопубликация", callback_data="settings:autopublish")],
        [InlineKeyboardButton(text="🔄 Сбор новостей", callback_data="settings:fetcher")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="settings:alerts")],
        [InlineKeyboardButton(text="🎯 Фильтрация и качество", callback_data="settings:quality")],
        [InlineKeyboardButton(text="💰 Бюджет API", callback_data="settings:budget")],
    ])

    await message.answer(
        "⚙️ <b>Системные настройки</b>\n\n"
        "Все параметры сохраняются в базе данных и применяются автоматически.\n\n"
        "Выберите категорию:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "settings:sources")
async def callback_settings_sources(callback: CallbackQuery, db: AsyncSession):
    """Настройки источников новостей."""
    await callback.answer()

    from app.modules.settings_manager import get_category_settings

    # Получаем текущее состояние источников
    sources = await get_category_settings("sources", db)

    # Формируем клавиатуру с галочками
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    source_config = {
        "google_news_ru": "Google News RSS (RU)",
        "google_news_en": "Google News RSS (EN)",
        "google_news_rss_ru": "Google News RU",
        "google_news_rss_en": "Google News EN",
        "habr": "Habr - Новости",
        "perplexity_ru": "Perplexity Search (RU)",
        "perplexity_en": "Perplexity Search (EN)",
        "telegram_channels": "Telegram Channels",
        "interfax": "Interfax - Наука и технологии",
        "lenta": "Lenta.ru - Технологии",
        "rbc": "RBC - Технологии",
        "tass": "TASS - Наука и технологии",
    }

    buttons = []
    for key, name in source_config.items():
        is_enabled = sources.get(f"sources.{key}.enabled", True)
        icon = "✅" if is_enabled else "☐"
        buttons.append([
            InlineKeyboardButton(
                text=f"{icon} {name}",
                callback_data=f"toggle_source:{key}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="« Назад", callback_data="back_to_settings")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "📰 <b>Источники новостей</b>\n\n"
        "Нажмите на источник чтобы включить/выключить его.\n"
        "Изменения применяются мгновенно.\n\n"
        "✅ - включен\n"
        "☐ - выключен",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("toggle_source:"))
async def callback_toggle_source(callback: CallbackQuery, db: AsyncSession):
    """Переключить источник."""
    source_key = callback.data.split(":")[1]

    from app.modules.settings_manager import get_setting, set_setting

    # Получаем текущее значение
    setting_key = f"sources.{source_key}.enabled"
    current_value = await get_setting(setting_key, db, default=True)

    # Переключаем
    new_value = not current_value
    await set_setting(setting_key, new_value, db)

    # Обновляем UI
    await callback.answer(f"{'✅ Включен' if new_value else '☐ Выключен'}")
    await callback_settings_sources(callback, db)


@router.callback_query(F.data == "back_to_settings")
async def callback_back_to_settings(callback: CallbackQuery, db: AsyncSession):
    """Вернуться в главное меню настроек."""
    await callback.answer()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📰 Источники новостей", callback_data="settings:sources")],
        [InlineKeyboardButton(text="🤖 Модели LLM", callback_data="settings:llm")],
        [InlineKeyboardButton(text="🎨 Генерация изображений (DALL-E)", callback_data="settings:dalle")],
        [InlineKeyboardButton(text="📅 Автопубликация", callback_data="settings:autopublish")],
        [InlineKeyboardButton(text="🔄 Сбор новостей", callback_data="settings:fetcher")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="settings:alerts")],
        [InlineKeyboardButton(text="🎯 Фильтрация и качество", callback_data="settings:quality")],
        [InlineKeyboardButton(text="💰 Бюджет API", callback_data="settings:budget")],
        [InlineKeyboardButton(text="« Назад", callback_data="back_to_main_menu")],
    ])

    await callback.message.edit_text(
        "⚙️ <b>Системные настройки</b>\n\n"
        "Все параметры сохраняются в базе данных и применяются автоматически.\n\n"
        "Выберите категорию:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "settings:llm")
async def callback_settings_llm(callback: CallbackQuery, db: AsyncSession):
    """Настройки моделей LLM."""
    from app.modules.settings_manager import get_setting

    current_analysis = await get_setting("llm.analysis.model", db, default="deepseek-chat")
    current_draft = await get_setting("llm.draft_generation.model", db, default="deepseek-chat")
    current_ranking = await get_setting("llm.ranking.model", db, default="deepseek-chat")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔍 Анализ: {current_analysis}", callback_data="llm_select:analysis")],
        [InlineKeyboardButton(text=f"✍️ Генерация драфтов: {current_draft}", callback_data="llm_select:draft_generation")],
        [InlineKeyboardButton(text=f"📊 Ранжирование: {current_ranking}", callback_data="llm_select:ranking")],
        [InlineKeyboardButton(text="« Назад", callback_data="back_to_settings")],
    ])

    await callback.message.edit_text(
        "🤖 <b>Модели LLM</b>\n\n"
        "Настройте модели для разных операций:\n\n"
        "• <b>Анализ</b> - AI анализ статей и метрик\n"
        "• <b>Генерация драфтов</b> - создание текстов постов\n"
        "• <b>Ранжирование</b> - scoring и сортировка статей\n\n"
        "💡 Доступны модели от всех провайдеров (DeepSeek, OpenAI).\n"
        "Нажмите на операцию для выбора модели:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("llm_select:"))
async def callback_llm_select(callback: CallbackQuery, db: AsyncSession):
    """Выбор модели LLM для операции."""
    from app.modules.settings_manager import get_setting

    operation = callback.data.split(":")[1]

    operation_names = {
        "analysis": "Анализ",
        "draft_generation": "Генерация драфтов",
        "ranking": "Ранжирование"
    }

    # Получаем текущую модель
    current_model = await get_setting(f"llm.{operation}.model", db, default="deepseek-chat")

    # Все доступные модели от всех провайдеров
    all_models = [
        ("deepseek-chat", "DeepSeek Chat (дешевле всего)"),
        ("gpt-4o", "GPT-4o (самая умная)"),
        ("gpt-4o-mini", "GPT-4o-mini (быстрая)"),
    ]

    buttons = []
    for model_key, model_name in all_models:
        icon = "✅" if current_model == model_key else "☐"
        buttons.append([
            InlineKeyboardButton(
                text=f"{icon} {model_name}",
                callback_data=f"llm_set:{operation}:{model_key}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="« Назад", callback_data="settings:llm")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        f"🤖 <b>Выбор модели для: {operation_names.get(operation, operation)}</b>\n\n"
        "Доступные модели:\n\n"
        "• <b>DeepSeek Chat</b> - самая дешевая (~$0.14/1M токенов)\n"
        "• <b>GPT-4o</b> - самая продвинутая, точная, дорогая (~$15/1M токенов)\n"
        "• <b>GPT-4o-mini</b> - быстрая, дешевая (~$0.15/1M токенов)\n"
        ""
        "✅ - выбранная модель\n"
        "Нажмите для изменения:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("llm_set:"))
async def callback_llm_set(callback: CallbackQuery, db: AsyncSession):
    """Установить модель LLM."""
    _, operation, model = callback.data.split(":")
    from app.modules.settings_manager import set_setting

    setting_key = f"llm.{operation}.model"
    await set_setting(setting_key, model, db)

    await callback.answer(f"✅ {model}")

    # Возвращаемся в главное меню LLM настроек
    await callback_settings_llm(callback, db)


@router.callback_query(F.data == "settings:dalle")
async def callback_settings_dalle(callback: CallbackQuery, db: AsyncSession):
    """Настройки DALL-E генерации изображений."""
    from app.modules.settings_manager import get_dalle_config

    config = await get_dalle_config(db)

    enabled_icon = "✅" if config["enabled"] else "☐"
    auto_icon = "✅" if config["auto_generate"] else "☐"
    ask_icon = "✅" if config["ask_on_review"] else "☐"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{enabled_icon} Включить DALL-E", callback_data="toggle:dalle.enabled")],
        [InlineKeyboardButton(text=f"🎨 Модель: {config['model']}", callback_data="dalle_model_select")],
        [InlineKeyboardButton(text=f"💎 Качество: {config['quality']}", callback_data="dalle_quality_select")],
        [InlineKeyboardButton(text=f"📐 Размер: {config['size']}", callback_data="dalle_size_select")],
        [InlineKeyboardButton(text=f"{auto_icon} Авто-генерация для всех постов", callback_data="toggle:dalle.auto_generate")],
        [InlineKeyboardButton(text=f"{ask_icon} Спрашивать при модерации", callback_data="toggle:dalle.ask_on_review")],
        [InlineKeyboardButton(text="« Назад", callback_data="back_to_settings")],
    ])

    await callback.message.edit_text(
        "🎨 <b>Генерация изображений (DALL-E)</b>\n\n"
        f"Статус: {'🟢 Включено' if config['enabled'] else '🔴 Выключено'}\n\n"
        "• <b>Модель</b> - DALL-E 2 или DALL-E 3\n"
        "• <b>Качество</b> - standard (дешевле) или hd (детальнее)\n"
        "• <b>Размер</b> - 1024x1024, 1792x1024, 1024x1792\n"
        "• <b>Авто-генерация</b> - создавать для каждого поста\n"
        "• <b>Спрашивать</b> - запрос при модерации\n\n"
        "💰 Стоимость: ~$0.04-0.12 за изображение",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle:"))
async def callback_toggle_setting(callback: CallbackQuery, db: AsyncSession):
    """Переключить булевую настройку."""
    setting_key = callback.data.split(":")[1]
    from app.modules.settings_manager import get_setting, set_setting

    current_value = await get_setting(setting_key, db, default=False)
    new_value = not current_value
    await set_setting(setting_key, new_value, db)

    await callback.answer(f"{'✅ Включено' if new_value else '☐ Выключено'}")

    # Redirect back to appropriate menu
    if setting_key.startswith("dalle."):
        await callback_settings_dalle(callback, db)
    elif setting_key.startswith("auto_publish."):
        await callback_settings_autopublish(callback, db)
    elif setting_key.startswith("alerts."):
        await callback_settings_alerts(callback, db)
    elif setting_key.startswith("budget."):
        await callback_settings_budget(callback, db)


@router.callback_query(F.data == "dalle_model_select")
async def callback_dalle_model_select(callback: CallbackQuery, db: AsyncSession):
    """Выбор модели DALL-E."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="DALL-E 3 (лучшее качество)", callback_data="dalle_set:model:dall-e-3")],
        [InlineKeyboardButton(text="DALL-E 2 (дешевле)", callback_data="dalle_set:model:dall-e-2")],
        [InlineKeyboardButton(text="« Назад", callback_data="settings:dalle")],
    ])

    await callback.message.edit_text(
        "🎨 <b>Выбор модели DALL-E</b>\n\n"
        "• <b>DALL-E 3</b> - лучшее качество, детализация (~$0.04-0.12)\n"
        "• <b>DALL-E 2</b> - базовое качество, дешевле (~$0.02)\n\n"
        "Выберите модель:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "dalle_quality_select")
async def callback_dalle_quality_select(callback: CallbackQuery, db: AsyncSession):
    """Выбор качества DALL-E."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="HD (высокое качество)", callback_data="dalle_set:quality:hd")],
        [InlineKeyboardButton(text="Standard (базовое)", callback_data="dalle_set:quality:standard")],
        [InlineKeyboardButton(text="« Назад", callback_data="settings:dalle")],
    ])

    await callback.message.edit_text(
        "💎 <b>Качество изображений</b>\n\n"
        "• <b>HD</b> - высокая детализация (в 2x дороже)\n"
        "• <b>Standard</b> - базовое качество\n\n"
        "Выберите качество:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "dalle_size_select")
async def callback_dalle_size_select(callback: CallbackQuery, db: AsyncSession):
    """Выбор размера изображения DALL-E."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1024x1024 (квадрат)", callback_data="dalle_set:size:1024x1024")],
        [InlineKeyboardButton(text="1792x1024 (горизонт)", callback_data="dalle_set:size:1792x1024")],
        [InlineKeyboardButton(text="1024x1792 (вертикаль)", callback_data="dalle_set:size:1024x1792")],
        [InlineKeyboardButton(text="« Назад", callback_data="settings:dalle")],
    ])

    await callback.message.edit_text(
        "📐 <b>Размер изображения</b>\n\n"
        "• <b>1024x1024</b> - квадратный формат\n"
        "• <b>1792x1024</b> - горизонтальный (для постов)\n"
        "• <b>1024x1792</b> - вертикальный (для stories)\n\n"
        "Выберите размер:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dalle_set:"))
async def callback_dalle_set(callback: CallbackQuery, db: AsyncSession):
    """Установить параметр DALL-E."""
    _, param, value = callback.data.split(":")
    from app.modules.settings_manager import set_setting

    setting_key = f"dalle.{param}"
    await set_setting(setting_key, value, db)

    await callback.answer(f"✅ {param.capitalize()} обновлен: {value}")
    await callback_settings_dalle(callback, db)


@router.callback_query(F.data == "settings:autopublish")
async def callback_settings_autopublish(callback: CallbackQuery, db: AsyncSession):
    """Настройки автопубликации."""
    from app.modules.settings_manager import get_auto_publish_config

    config = await get_auto_publish_config(db)

    enabled_icon = "✅" if config["enabled"] else "☐"
    weekdays_icon = "✅" if config["weekdays_only"] else "☐"
    holidays_icon = "✅" if config["skip_holidays"] else "☐"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{enabled_icon} Включить автопубликацию", callback_data="toggle:auto_publish.enabled")],
        [InlineKeyboardButton(text=f"⏰ Режим: {config['mode']}", callback_data="autopublish_mode_select")],
        [InlineKeyboardButton(text=f"📊 Макс. постов/день: {config['max_per_day']}", callback_data="autopublish_max_select")],
        [InlineKeyboardButton(text=f"{weekdays_icon} Только в будни", callback_data="toggle:auto_publish.weekdays_only")],
        [InlineKeyboardButton(text=f"{holidays_icon} Пропускать праздники", callback_data="toggle:auto_publish.skip_holidays")],
        [InlineKeyboardButton(text="« Назад", callback_data="back_to_settings")],
    ])

    mode_desc = {
        "best_time": "Лучшее время (AI выбирает)",
        "schedule": "По расписанию",
        "even": "Равномерно в течение дня"
    }

    await callback.message.edit_text(
        "📅 <b>Автопубликация</b>\n\n"
        f"Статус: {'🟢 Включено' if config['enabled'] else '🔴 Выключено'}\n"
        f"Режим: {mode_desc.get(config['mode'], config['mode'])}\n\n"
        "• <b>Режим</b> - когда публиковать посты\n"
        "• <b>Макс. постов/день</b> - лимит публикаций\n"
        "• <b>Только в будни</b> - не публиковать в выходные\n"
        "• <b>Пропускать праздники</b> - не публиковать в праздники\n\n"
        "⚠️ Посты всё равно проходят модерацию!",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "autopublish_mode_select")
async def callback_autopublish_mode_select(callback: CallbackQuery, db: AsyncSession):
    """Выбор режима автопубликации."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ Лучшее время (AI)", callback_data="autopublish_set:mode:best_time")],
        [InlineKeyboardButton(text="📅 По расписанию", callback_data="autopublish_set:mode:schedule")],
        [InlineKeyboardButton(text="⏳ Равномерно", callback_data="autopublish_set:mode:even")],
        [InlineKeyboardButton(text="« Назад", callback_data="settings:autopublish")],
    ])

    await callback.message.edit_text(
        "⏰ <b>Режим автопубликации</b>\n\n"
        "• <b>Лучшее время</b> - AI анализирует метрики и выбирает\n"
        "  оптимальное время на основе engagement\n\n"
        "• <b>По расписанию</b> - фиксированное время (9:00, 14:00, 18:00)\n\n"
        "• <b>Равномерно</b> - распределить равномерно в течение дня\n\n"
        "Выберите режим:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "autopublish_max_select")
async def callback_autopublish_max_select(callback: CallbackQuery, db: AsyncSession):
    """Выбор максимального количества постов в день."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 пост/день", callback_data="autopublish_set:max_per_day:1")],
        [InlineKeyboardButton(text="2 поста/день", callback_data="autopublish_set:max_per_day:2")],
        [InlineKeyboardButton(text="3 поста/день", callback_data="autopublish_set:max_per_day:3")],
        [InlineKeyboardButton(text="5 постов/день", callback_data="autopublish_set:max_per_day:5")],
        [InlineKeyboardButton(text="« Назад", callback_data="settings:autopublish")],
    ])

    await callback.message.edit_text(
        "📊 <b>Максимум постов в день</b>\n\n"
        "Сколько постов разрешено публиковать автоматически в день?\n\n"
        "Рекомендация: 2-3 поста для качественного контента.\n\n"
        "Выберите лимит:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("autopublish_set:"))
async def callback_autopublish_set(callback: CallbackQuery, db: AsyncSession):
    """Установить параметр автопубликации."""
    _, param, value = callback.data.split(":")
    from app.modules.settings_manager import set_setting

    setting_key = f"auto_publish.{param}"
    # Convert to int if it's max_per_day
    if param == "max_per_day":
        value = int(value)

    await set_setting(setting_key, value, db)

    await callback.answer(f"✅ Обновлено: {value}")
    await callback_settings_autopublish(callback, db)


@router.callback_query(F.data == "settings:alerts")
async def callback_settings_alerts(callback: CallbackQuery, db: AsyncSession):
    """Настройки уведомлений."""
    from app.modules.settings_manager import get_category_settings

    alerts = await get_category_settings("alerts", db)

    low_eng_icon = "✅" if alerts.get("alerts.low_engagement.enabled", True) else "☐"
    viral_icon = "✅" if alerts.get("alerts.viral_post.enabled", True) else "☐"
    low_appr_icon = "✅" if alerts.get("alerts.low_approval.enabled", True) else "☐"
    fetch_err_icon = "✅" if alerts.get("alerts.fetch_errors.enabled", True) else "☐"
    api_lim_icon = "✅" if alerts.get("alerts.api_limits.enabled", True) else "☐"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{low_eng_icon} Падение engagement", callback_data="toggle:alerts.low_engagement.enabled")],
        [InlineKeyboardButton(text=f"  └ Порог: {alerts.get('alerts.low_engagement.threshold', 20)}%", callback_data="alert_threshold:low_engagement")],
        [InlineKeyboardButton(text=f"{viral_icon} Viral пост", callback_data="toggle:alerts.viral_post.enabled")],
        [InlineKeyboardButton(text=f"  └ Порог: {alerts.get('alerts.viral_post.threshold', 100)} просм.", callback_data="alert_threshold:viral_post")],
        [InlineKeyboardButton(text=f"{low_appr_icon} Низкий approval rate", callback_data="toggle:alerts.low_approval.enabled")],
        [InlineKeyboardButton(text=f"  └ Порог: {alerts.get('alerts.low_approval.threshold', 30)}%", callback_data="alert_threshold:low_approval")],
        [InlineKeyboardButton(text=f"{fetch_err_icon} Ошибки сбора новостей", callback_data="toggle:alerts.fetch_errors.enabled")],
        [InlineKeyboardButton(text=f"{api_lim_icon} Лимиты API", callback_data="toggle:alerts.api_limits.enabled")],
        [InlineKeyboardButton(text="« Назад", callback_data="back_to_settings")],
    ])

    await callback.message.edit_text(
        "🔔 <b>Уведомления и алерты</b>\n\n"
        "Настройте когда получать уведомления:\n\n"
        "• <b>Падение engagement</b> - если engagement ниже порога\n"
        "• <b>Viral пост</b> - если пост набрал много просмотров\n"
        "• <b>Низкий approval</b> - если отклонено много статей\n"
        "• <b>Ошибки сбора</b> - проблемы с источниками\n"
        "• <b>Лимиты API</b> - приближение к лимитам\n\n"
        "Нажмите для включения/отключения или настройки порогов:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("alert_threshold:"))
async def callback_alert_threshold(callback: CallbackQuery):
    """Настройка порогов уведомлений (заглушка)."""
    alert_type = callback.data.split(":")[1]

    alert_names = {
        "low_engagement": "Падение engagement",
        "viral_post": "Viral пост",
        "low_approval": "Низкий approval rate"
    }

    await callback.answer(
        f"⚠️ Настройка порога для '{alert_names.get(alert_type, alert_type)}' будет доступна в следующей версии",
        show_alert=True
    )


@router.callback_query(F.data.startswith("quality_param:"))
async def callback_quality_param(callback: CallbackQuery):
    """Настройка параметров качества (заглушка)."""
    param = callback.data.split(":")[1]

    param_names = {
        "min_score": "минимального quality score",
        "min_content_length": "минимальной длины текста",
        "similarity_threshold": "порога схожести",
        "languages": "языков"
    }

    await callback.answer(
        f"⚠️ Настройка {param_names.get(param, param)} будет доступна в следующей версии",
        show_alert=True
    )


@router.callback_query(F.data.startswith("budget_param:"))
async def callback_budget_param(callback: CallbackQuery):
    """Настройка параметров бюджета (заглушка)."""
    param = callback.data.split(":")[1]

    param_names = {
        "max_per_month": "максимального бюджета",
        "warning_threshold": "порога предупреждения"
    }

    await callback.answer(
        f"⚠️ Настройка {param_names.get(param, param)} будет доступна в следующей версии",
        show_alert=True
    )


@router.callback_query(F.data == "settings:quality")
async def callback_settings_quality(callback: CallbackQuery, db: AsyncSession):
    """Настройки фильтрации и качества."""
    from app.modules.settings_manager import get_category_settings

    quality = await get_category_settings("quality", db)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐ Мин. quality score: {quality.get('quality.min_score', 0.6)}", callback_data="quality_param:min_score")],
        [InlineKeyboardButton(text=f"📝 Мин. длина текста: {quality.get('quality.min_content_length', 300)}", callback_data="quality_param:min_content_length")],
        [InlineKeyboardButton(text=f"🔄 Порог схожести: {quality.get('quality.similarity_threshold', 0.85)}", callback_data="quality_param:similarity_threshold")],
        [InlineKeyboardButton(text=f"🌐 Языки: {', '.join(quality.get('quality.languages', ['ru', 'en']))}", callback_data="quality_param:languages")],
        [InlineKeyboardButton(text="« Назад", callback_data="back_to_settings")],
    ])

    await callback.message.edit_text(
        "🎯 <b>Фильтрация и качество</b>\n\n"
        "Настройки автоматической фильтрации статей:\n\n"
        "• <b>Quality score</b> - минимальный балл AI (0.0-1.0)\n"
        "• <b>Длина текста</b> - минимум символов в статье\n"
        "• <b>Порог схожести</b> - фильтр дубликатов (0.0-1.0)\n"
        "• <b>Языки</b> - разрешённые языки контента\n\n"
        "⚠️ Слишком строгие фильтры могут пропускать мало статей!",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "settings:budget")
async def callback_settings_budget(callback: CallbackQuery, db: AsyncSession):
    """Настройки бюджета API."""
    from app.modules.settings_manager import get_category_settings

    budget = await get_category_settings("budget", db)

    stop_icon = "✅" if budget.get("budget.stop_on_exceed", False) else "☐"
    switch_icon = "✅" if budget.get("budget.switch_to_cheap", True) else "☐"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 Макс. бюджет/месяц: ${budget.get('budget.max_per_month', 10)}", callback_data="budget_param:max_per_month")],
        [InlineKeyboardButton(text=f"⚠️ Предупреждение при: ${budget.get('budget.warning_threshold', 8)}", callback_data="budget_param:warning_threshold")],
        [InlineKeyboardButton(text=f"{stop_icon} Остановить при превышении", callback_data="toggle:budget.stop_on_exceed")],
        [InlineKeyboardButton(text=f"{switch_icon} Переключиться на дешевые модели", callback_data="toggle:budget.switch_to_cheap")],
        [InlineKeyboardButton(text="« Назад", callback_data="back_to_settings")],
    ])

    await callback.message.edit_text(
        "💰 <b>Бюджет API</b>\n\n"
        "Контроль расходов на OpenAI API:\n\n"
        "• <b>Макс. бюджет</b> - лимит в $ на месяц\n"
        "• <b>Предупреждение</b> - когда отправить алерт\n"
        "• <b>Остановить</b> - прекратить работу при превышении\n"
        "• <b>Переключиться</b> - использовать дешевые модели\n\n"
        f"📊 Текущий расход: отслеживается в БД\n"
        "💡 Рекомендуется включить 'Переключиться на дешевые модели'",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()



# ====================
# Personal Posts Handlers
# ====================

@router.callback_query(F.data == "show_personal_posts")
async def callback_show_personal_posts(callback: CallbackQuery, db: AsyncSession):
    """Показать меню личных постов."""
    await callback.answer()

    from app.modules.personal_posts_manager import get_user_posts

    # Получаем последние посты пользователя
    posts = await get_user_posts(callback.from_user.id, db, limit=5)

    posts_text = ""
    if posts:
        posts_text = "\n\n<b>Последние заметки:</b>\n"
        for post in posts:
            date_str = post.created_at.strftime("%d.%m.%Y")
            title = post.title or post.content[:50] + "..."
            posts_text += f"\n• {date_str}: {title}"
    else:
        posts_text = "\n\n<i>У вас пока нет заметок</i>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Создать новую заметку", callback_data="create_personal_post")],
        [InlineKeyboardButton(text="📚 Все мои заметки", callback_data="list_personal_posts")],
        [InlineKeyboardButton(text="« Назад", callback_data="back_to_main_menu")],
    ])

    await callback.message.edit_text(
        "✍️ <b>Мои заметки</b>\n\n"
        "Личный дневник работы с AI. Фиксируйте идеи, эксперименты, инсайты.\n"
        "Заметки автоматически анализируются и связываются с публикациями."
        f"{posts_text}",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "create_personal_post")
async def callback_create_personal_post(callback: CallbackQuery):
    """Выбор способа создания поста."""
    await callback.answer()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Написать самостоятельно", callback_data="post_manual")],
        [InlineKeyboardButton(text="🤖 Создать с помощью AI", callback_data="post_ai_assisted")],
        [InlineKeyboardButton(text="🎤 Надиктовать голосом", callback_data="post_voice")],
        [InlineKeyboardButton(text="« Назад", callback_data="show_personal_posts")],
    ])

    await callback.message.edit_text(
        "✍️ <b>Создать новую заметку</b>\n\n"
        "Выберите способ создания:\n\n"
        "• <b>Написать самостоятельно</b> - просто напишите текст\n"
        "• <b>Создать с AI</b> - опишите идеи, AI сформирует пост\n"
        "• <b>Надиктовать</b> - отправьте голосовое сообщение\n\n"
        "Все заметки сохраняются и индексируются для поиска связей.",
        parse_mode="HTML",
        reply_markup=keyboard
    )


# FSM States для создания постов
class PersonalPostStates(StatesGroup):
    waiting_manual_text = State()
    waiting_ai_ideas = State()
    waiting_ai_feedback = State()
    waiting_voice = State()
    waiting_edit_text = State()
    waiting_comment = State()


@router.callback_query(F.data == "post_manual")
async def callback_post_manual(callback: CallbackQuery, state: FSMContext):
    """Начать создание поста вручную."""
    await callback.answer()

    await state.set_state(PersonalPostStates.waiting_manual_text)

    await callback.message.edit_text(
        "📝 <b>Написать заметку</b>\n\n"
        "Напишите текст вашей заметки. Можно использовать Markdown форматирование.\n\n"
        "Отправьте текст сообщением, и я сохраню его.",
        parse_mode="HTML"
    )


@router.message(PersonalPostStates.waiting_manual_text)
async def process_manual_post(message: Message, state: FSMContext, db: AsyncSession):
    """Обработать текст ручного поста."""
    from app.modules.personal_posts_manager import create_personal_post, enrich_post_with_metadata

    content = message.text

    # Показываем индикатор typing
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Создаём пост
    post = await create_personal_post(
        user_id=message.from_user.id,
        content=content,
        db=db,
        creation_method="manual"
    )

    # Обогащаем метаданными в фоне
    await message.answer("⏳ Сохраняю и анализирую вашу заметку...")

    try:
        await enrich_post_with_metadata(post, db)

        tags_str = ", ".join(post.tags[:5]) if post.tags else "нет"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Опубликовать сейчас", callback_data=f"publish_post:{post.id}")],
            [InlineKeyboardButton(text="📝 Посмотреть заметку", callback_data=f"view_post:{post.id}")],
            [InlineKeyboardButton(text="« Главное меню", callback_data="back_to_main_menu")],
        ])

        await message.answer(
            f"✅ <b>Заметка сохранена!</b>\n\n"
            f"📊 Категория: {post.category or 'не определена'}\n"
            f"🏷 Теги: {tags_str}\n"
            f"😊 Настроение: {post.sentiment or 'neutral'}\n\n"
            f"ID: {post.id}",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error("post_enrichment_failed", error=str(e))
        await message.answer(
            f"✅ Заметка сохранена (ID: {post.id})\n\n"
            "⚠️ Не удалось проанализировать автоматически, но данные сохранены.",
            reply_markup=get_main_menu_keyboard()
        )

    await state.clear()


@router.callback_query(F.data == "post_ai_assisted")
async def callback_post_ai_assisted(callback: CallbackQuery, state: FSMContext):
    """Начать создание поста с AI."""
    await callback.answer()

    await state.set_state(PersonalPostStates.waiting_ai_ideas)
    await state.update_data(previous_attempts=[])

    await callback.message.edit_text(
        "🤖 <b>Создать заметку с помощью AI</b>\n\n"
        "Опишите свои идеи, мысли или то, о чём хотите написать.\n"
        "Это может быть просто набор тезисов или вольное описание.\n\n"
        "AI сформирует из этого структурированную заметку.\n\n"
        "Отправьте ваши идеи сообщением:",
        parse_mode="HTML"
    )


@router.message(PersonalPostStates.waiting_ai_ideas)
async def process_ai_ideas(message: Message, state: FSMContext, db: AsyncSession):
    """Обработать идеи для AI генерации."""
    from app.modules.personal_posts_manager import generate_post_with_ai, create_personal_post
    from app.modules.settings_manager import get_llm_model

    user_input = message.text

    # Показываем индикатор typing
    await message.bot.send_chat_action(message.chat.id, "typing")

    processing_msg = await message.answer("🤖 AI формирует вашу заметку...")

    try:
        # Получаем модель из настроек
        model = await get_llm_model("draft_generation", db)

        # Генерируем пост
        data = await state.get_data()
        previous_attempts = data.get("previous_attempts", [])

        generated_content = await generate_post_with_ai(
            user_input=user_input,
            model=model,
            previous_attempts=previous_attempts if previous_attempts else None
        )

        await processing_msg.delete()

        # Сохраняем сгенерированный контент для следующей итерации
        await state.update_data(
            current_content=generated_content,
            raw_input=user_input,
            model_used=model
        )
        await state.set_state(PersonalPostStates.waiting_ai_feedback)

        # Показываем результат с кнопками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сохранить", callback_data="ai_post_save")],
            [InlineKeyboardButton(text="🔄 Переделать", callback_data="ai_post_regenerate")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="ai_post_cancel")],
        ])

        await message.answer(
            f"🤖 <b>Вот что получилось:</b>\n\n"
            f"{generated_content}\n\n"
            "Вас устраивает результат?",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error("ai_generation_failed", error=str(e))
        await processing_msg.delete()
        await message.answer(
            "❌ Не удалось сгенерировать заметку. Попробуйте ещё раз или напишите вручную.",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


@router.callback_query(F.data == "ai_post_save")
async def callback_ai_post_save(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Сохранить AI-сгенерированный пост."""
    await callback.answer()

    from app.modules.personal_posts_manager import create_personal_post, enrich_post_with_metadata

    data = await state.get_data()
    content = data.get("current_content")
    raw_input = data.get("raw_input")
    model_used = data.get("model_used")

    if not content:
        await callback.message.answer("❌ Ошибка: контент не найден")
        await state.clear()
        return

    await callback.message.edit_text("⏳ Сохраняю и анализирую заметку...")

    # Создаём пост
    post = await create_personal_post(
        user_id=callback.from_user.id,
        content=content,
        db=db,
        creation_method="ai_assisted",
        raw_input=raw_input,
        ai_model_used=model_used
    )

    # Обогащаем метаданными
    try:
        await enrich_post_with_metadata(post, db)

        tags_str = ", ".join(post.tags[:5]) if post.tags else "нет"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Опубликовать сейчас", callback_data=f"publish_post:{post.id}")],
            [InlineKeyboardButton(text="📝 Посмотреть заметку", callback_data=f"view_post:{post.id}")],
            [InlineKeyboardButton(text="« Главное меню", callback_data="back_to_main_menu")],
        ])

        await callback.message.answer(
            f"✅ <b>Заметка сохранена!</b>\n\n"
            f"📊 Категория: {post.category or 'не определена'}\n"
            f"🏷 Теги: {tags_str}\n"
            f"🤖 Модель: {model_used}\n\n"
            f"ID: {post.id}",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error("post_enrichment_failed", error=str(e))
        await callback.message.answer(
            f"✅ Заметка сохранена (ID: {post.id})\n\n"
            "⚠️ Не удалось проанализировать автоматически.",
            reply_markup=get_main_menu_keyboard()
        )

    await state.clear()


@router.callback_query(F.data == "ai_post_regenerate")
async def callback_ai_post_regenerate(callback: CallbackQuery, state: FSMContext):
    """Переделать AI-сгенерированный пост."""
    await callback.answer("Отправьте уточнения или новые идеи")

    data = await state.get_data()
    current_content = data.get("current_content")

    # Добавляем текущую попытку в список предыдущих
    previous_attempts = data.get("previous_attempts", [])
    previous_attempts.append(current_content)
    await state.update_data(previous_attempts=previous_attempts)

    await state.set_state(PersonalPostStates.waiting_ai_ideas)

    await callback.message.edit_text(
        "🔄 <b>Переделаем заметку</b>\n\n"
        "Опишите что не понравилось или какие изменения внести.\n"
        "Можно просто отправить новые идеи.\n\n"
        "AI учтёт предыдущую версию и создаст новую:",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "ai_post_cancel")
async def callback_ai_post_cancel(callback: CallbackQuery, state: FSMContext):
    """Отменить создание AI поста."""
    await callback.answer("Отменено")
    await state.clear()

    await callback.message.edit_text(
        "❌ Создание заметки отменено.",
        reply_markup=get_main_menu_keyboard()
    )


@router.callback_query(F.data == "post_voice")
async def callback_post_voice(callback: CallbackQuery, state: FSMContext):
    """Начать создание поста голосом."""
    await callback.answer()

    await state.set_state(PersonalPostStates.waiting_voice)

    await callback.message.edit_text(
        "🎤 <b>Надиктовать заметку</b>\n\n"
        "Отправьте голосовое сообщение с вашими мыслями.\n\n"
        "Я расшифрую его и создам заметку.\n"
        "После расшифровки вы сможете выбрать:\n"
        "• Сохранить как есть\n"
        "• Дать AI отредактировать",
        parse_mode="HTML"
    )


@router.message(PersonalPostStates.waiting_voice, F.voice)
async def process_voice_post(message: Message, state: FSMContext, db: AsyncSession):
    """Обработать голосовое сообщение."""

    # Используем встроенное распознавание Telegram (БЕСПЛАТНО!)
    if message.voice.transcription:
        # Транскрипция доступна (Telegram Premium или бот запросил)
        transcribed_text = message.voice.transcription

        # Сохраняем транскрипт и предлагаем опции
        await state.update_data(transcribed_text=transcribed_text)
        await state.set_state(PersonalPostStates.waiting_ai_feedback)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сохранить как есть", callback_data="voice_save_raw")],
            [InlineKeyboardButton(text="🤖 Улучшить с AI", callback_data="voice_improve_ai")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="ai_post_cancel")],
        ])

        await message.answer(
            f"🎤 <b>Расшифровка:</b>\n\n"
            f"{transcribed_text}\n\n"
            "Что делаем дальше?",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        # Транскрипция недоступна - предлагаем отправить текстом
        await message.answer(
            "❌ <b>Голосовое распознавание недоступно</b>\n\n"
            "Пожалуйста, отправьте ваш пост <b>текстом</b>.\n\n"
            "<i>💡 Совет: Telegram Premium пользователи получают автоматическое распознавание голоса!</i>",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


@router.callback_query(F.data == "voice_save_raw")
async def callback_voice_save_raw(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Сохранить расшифровку голоса как есть."""
    await callback.answer()

    from app.modules.personal_posts_manager import create_personal_post, enrich_post_with_metadata

    data = await state.get_data()
    content = data.get("transcribed_text")

    if not content:
        await callback.message.answer("❌ Ошибка: текст не найден")
        await state.clear()
        return

    await callback.message.edit_text("⏳ Сохраняю заметку...")

    # Создаём пост
    post = await create_personal_post(
        user_id=callback.from_user.id,
        content=content,
        db=db,
        creation_method="voice"
    )

    # Обогащаем метаданными
    try:
        await enrich_post_with_metadata(post, db)

        tags_str = ", ".join(post.tags[:5]) if post.tags else "нет"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Опубликовать сейчас", callback_data=f"publish_post:{post.id}")],
            [InlineKeyboardButton(text="📝 Посмотреть заметку", callback_data=f"view_post:{post.id}")],
            [InlineKeyboardButton(text="« Главное меню", callback_data="back_to_main_menu")],
        ])

        await callback.message.answer(
            f"✅ <b>Заметка из голосового сохранена!</b>\n\n"
            f"📊 Категория: {post.category or 'не определена'}\n"
            f"🏷 Теги: {tags_str}\n\n"
            f"ID: {post.id}",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error("post_enrichment_failed", error=str(e))
        await callback.message.answer(
            f"✅ Заметка сохранена (ID: {post.id})",
            reply_markup=get_main_menu_keyboard()
        )

    await state.clear()


@router.callback_query(F.data == "voice_improve_ai")
async def callback_voice_improve_ai(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Улучшить расшифровку голоса с помощью AI."""
    await callback.answer()

    from app.modules.personal_posts_manager import generate_post_with_ai
    from app.modules.settings_manager import get_llm_model

    data = await state.get_data()
    transcribed_text = data.get("transcribed_text")

    if not transcribed_text:
        await callback.message.answer("❌ Ошибка: текст не найден")
        await state.clear()
        return

    await callback.message.edit_text("🤖 AI улучшает вашу заметку...")

    try:
        model = await get_llm_model("draft_generation", db)

        # Генерируем улучшенную версию
        improved_content = await generate_post_with_ai(
            user_input=transcribed_text,
            model=model
        )

        # Сохраняем для feedback
        await state.update_data(
            current_content=improved_content,
            raw_input=transcribed_text,
            model_used=model
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сохранить", callback_data="ai_post_save")],
            [InlineKeyboardButton(text="🔄 Переделать", callback_data="ai_post_regenerate")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="ai_post_cancel")],
        ])

        await callback.message.answer(
            f"🤖 <b>Улучшенная версия:</b>\n\n"
            f"{improved_content}\n\n"
            "Вас устраивает?",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error("ai_improvement_failed", error=str(e))
        await callback.message.answer(
            "❌ Не удалось улучшить. Сохраните оригинальный текст или попробуйте позже.",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()


@router.callback_query(F.data == "list_personal_posts")
async def callback_list_personal_posts(callback: CallbackQuery, db: AsyncSession):
    """Показать список всех личных постов."""
    await callback.answer()

    from app.modules.personal_posts_manager import get_user_posts

    posts = await get_user_posts(callback.from_user.id, db, limit=20)

    if not posts:
        await callback.message.edit_text(
            "📚 <b>Ваши заметки</b>\n\n"
            "У вас пока нет сохранённых заметок.\n"
            "Создайте первую!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✍️ Создать заметку", callback_data="create_personal_post")],
                [InlineKeyboardButton(text="« Назад", callback_data="show_personal_posts")],
            ])
        )
        return

    # Формируем кликабельный список
    posts_list = "📚 <b>Ваши заметки (дневник)</b>\n\n"
    posts_list += "<i>Нажмите на заметку чтобы открыть:</i>\n\n"

    buttons = []
    for i, post in enumerate(posts, 1):
        date_str = post.created_at.strftime("%d.%m %H:%M")
        title = post.title or post.content[:40] + "..."
        method_icon = {"manual": "✍️", "ai_assisted": "🤖", "voice": "🎤"}.get(post.creation_method, "📝")
        published_icon = "✅" if post.published else ""

        buttons.append([
            InlineKeyboardButton(
                text=f"{method_icon} {published_icon} {date_str}: {title}",
                callback_data=f"view_post:{post.id}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="✍️ Создать новую", callback_data="create_personal_post")])
    buttons.append([InlineKeyboardButton(text="« Назад", callback_data="show_personal_posts")])

    await callback.message.edit_text(
        posts_list + f"\n<i>Всего заметок: {len(posts)}</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("view_post:"))
async def callback_view_post(callback: CallbackQuery, db: AsyncSession):
    """Просмотр отдельной заметки."""
    await callback.answer()

    post_id = int(callback.data.split(":")[1])

    # Получаем заметку
    result = await db.execute(
        select(PersonalPost).where(
            PersonalPost.id == post_id,
            PersonalPost.user_id == callback.from_user.id
        )
    )
    post = result.scalar_one_or_none()

    if not post:
        await callback.answer("❌ Заметка не найдена", show_alert=True)
        return

    # Формируем текст
    date_str = post.created_at.strftime("%d.%m.%Y %H:%M")
    method_names = {"manual": "Вручную", "ai_assisted": "С помощью AI", "voice": "Голосом"}
    method = method_names.get(post.creation_method, post.creation_method)

    post_text = f"📝 <b>Заметка #{post.id}</b>\n"
    post_text += f"📅 {date_str}\n"
    post_text += f"🔧 Метод: {method}\n"

    if post.category:
        post_text += f"📂 Категория: {post.category}\n"
    if post.tags:
        post_text += f"🏷 Теги: {', '.join(post.tags[:5])}\n"
    if post.published:
        post_text += f"✅ <b>Опубликовано</b> {post.published_at.strftime('%d.%m.%Y')}\n"
        # Показываем статистику если есть
        if post.views_count or post.reactions_count:
            post_text += f"📊 Статистика: 👁 {post.views_count or 0} просмотров, 👍 {post.reactions_count or 0} реакций\n"

    post_text += f"\n{'─' * 30}\n\n"
    post_text += f"{post.content}\n"
    post_text += f"\n{'─' * 30}\n"

    # Кнопки
    buttons = []

    # Кнопка публикации всегда активна (можно публиковать повторно)
    if not post.published:
        buttons.append([InlineKeyboardButton(text="📤 Опубликовать", callback_data=f"publish_post:{post.id}")])
    else:
        buttons.append([InlineKeyboardButton(text="📤 Опубликовать снова", callback_data=f"publish_post:{post.id}")])

    # Подсчитываем комментарии
    comments_result = await db.execute(
        select(PostComment).where(PostComment.post_id == post.id)
    )
    comments_count = len(list(comments_result.scalars().all()))

    comments_text = f"💬 Комментарии ({comments_count})" if comments_count > 0 else "💬 Добавить комментарий"

    buttons.append([
        InlineKeyboardButton(text=comments_text, callback_data=f"view_comments:{post.id}")
    ])

    buttons.append([
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_post:{post.id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_post:{post.id}")
    ])
    buttons.append([InlineKeyboardButton(text="« К списку", callback_data="list_personal_posts")])

    await callback.message.edit_text(
        post_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("publish_post:"))
async def callback_publish_post(callback: CallbackQuery, db: AsyncSession):
    """Опубликовать личную заметку в канал (можно публиковать повторно)."""
    post_id = int(callback.data.split(":")[1])

    # Получаем заметку (без проверки published - разрешаем повторную публикацию)
    result = await db.execute(
        select(PersonalPost).where(
            PersonalPost.id == post_id,
            PersonalPost.user_id == callback.from_user.id
        )
    )
    post = result.scalar_one_or_none()

    if not post:
        await callback.answer("❌ Заметка не найдена", show_alert=True)
        return

    # Проверяем, это первая публикация или повторная
    is_republish = post.published

    # Публикуем в канал
    try:
        from app.config import settings
        import html
        import re

        # Очищаем текст от служебной информации
        clean_content = post.content

        # Убираем заголовки с служебными словами
        service_headers = [
            r'^#+\s*(Редактирование|Заметка|Черновик|Draft|Note|Edit).*?\n+',
            r'^\*\*\s*(Редактирование|Заметка|Черновик|Draft|Note|Edit).*?\*\*\n+',
            r'^(Редактирование|Заметка|Черновик):\s*\n+',
        ]
        for pattern in service_headers:
            clean_content = re.sub(pattern, '', clean_content, flags=re.IGNORECASE | re.MULTILINE)

        # Убираем лишние пустые строки в начале
        clean_content = clean_content.lstrip('\n ')

        # Форматируем пост для публикации
        # Экранируем HTML символы для безопасности
        publish_text = html.escape(clean_content)

        # Добавляем теги если есть
        if post.tags:
            escaped_tags = [html.escape(tag.replace(' ', '_')) for tag in post.tags[:5]]
            publish_text += f"\n\n🏷 {' '.join(['#' + tag for tag in escaped_tags])}"

        # Публикуем (теперь безопасно использовать HTML parse mode)
        message = await callback.bot.send_message(
            chat_id=settings.telegram_channel_id,
            text=publish_text,
            parse_mode="HTML"
        )

        # Обновляем статус
        post.published = True
        post.published_at = datetime.utcnow()
        post.telegram_message_id = message.message_id
        await db.commit()

        # Показываем разное сообщение для первой публикации и повторной
        success_msg = "✅ Опубликовано снова!" if is_republish else "✅ Опубликовано!"
        await callback.answer(success_msg, show_alert=True)

        # Обновляем просмотр заметки - создаём новый callback data
        callback.data = f"view_post:{post_id}"
        await callback_view_post(callback, db)

    except Exception as e:
        logger.error("post_publication_error", error=str(e), post_id=post_id)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("delete_post:"))
async def callback_delete_post(callback: CallbackQuery, db: AsyncSession):
    """Удалить заметку."""
    post_id = int(callback.data.split(":")[1])

    from app.modules.personal_posts_manager import delete_post

    success = await delete_post(post_id, callback.from_user.id, db)

    if success:
        await callback.answer("🗑 Заметка удалена", show_alert=True)
        await callback_list_personal_posts(callback, db)
    else:
        await callback.answer("❌ Не удалось удалить", show_alert=True)


@router.callback_query(F.data.startswith("view_comments:"))
async def callback_view_comments(callback: CallbackQuery, db: AsyncSession):
    """Показать комментарии к заметке."""
    post_id = int(callback.data.split(":")[1])

    # Получаем заметку
    result = await db.execute(
        select(PersonalPost).where(
            PersonalPost.id == post_id,
            PersonalPost.user_id == callback.from_user.id
        )
    )
    post = result.scalar_one_or_none()

    if not post:
        await callback.answer("❌ Заметка не найдена", show_alert=True)
        return

    # Получаем комментарии
    comments_result = await db.execute(
        select(PostComment)
        .where(PostComment.post_id == post.id)
        .order_by(PostComment.created_at.asc())
    )
    comments = list(comments_result.scalars().all())

    # Формируем текст
    text = f"💬 <b>Комментарии к заметке</b>\n\n"
    text += f"<b>Заметка:</b> {post.title or post.content[:50]}...\n"
    text += f"{'─' * 30}\n\n"

    if comments:
        for idx, comment in enumerate(comments, 1):
            date_str = comment.created_at.strftime("%d.%m %H:%M")
            comment_icon = {
                "reflection": "🤔",
                "idea": "💡",
                "question": "❓",
                "update": "📝"
            }.get(comment.comment_type, "💬")

            text += f"{comment_icon} <b>#{idx}</b> ({date_str})\n"
            text += f"{comment.content}\n\n"
    else:
        text += "<i>Комментариев пока нет</i>\n\n"

    # Кнопки
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить комментарий", callback_data=f"add_comment:{post.id}")],
        [InlineKeyboardButton(text="« К заметке", callback_data=f"view_post:{post.id}")]
    ]

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("add_comment:"))
async def callback_add_comment(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Начать добавление комментария."""
    post_id = int(callback.data.split(":")[1])

    # Проверяем что заметка существует
    result = await db.execute(
        select(PersonalPost).where(
            PersonalPost.id == post_id,
            PersonalPost.user_id == callback.from_user.id
        )
    )
    post = result.scalar_one_or_none()

    if not post:
        await callback.answer("❌ Заметка не найдена", show_alert=True)
        return

    # Сохраняем post_id в FSM
    await state.update_data(commenting_post_id=post_id)
    await state.set_state(PersonalPostStates.waiting_comment)

    # Показываем типы комментариев
    buttons = [
        [InlineKeyboardButton(text="🤔 Рефлексия", callback_data=f"comment_type:reflection:{post_id}")],
        [InlineKeyboardButton(text="💡 Идея", callback_data=f"comment_type:idea:{post_id}")],
        [InlineKeyboardButton(text="❓ Вопрос", callback_data=f"comment_type:question:{post_id}")],
        [InlineKeyboardButton(text="📝 Обновление", callback_data=f"comment_type:update:{post_id}")],
        [InlineKeyboardButton(text="« Отмена", callback_data=f"view_comments:{post_id}")]
    ]

    await callback.message.edit_text(
        "💬 <b>Добавить комментарий</b>\n\n"
        "Выберите тип комментария:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("comment_type:"))
async def callback_comment_type(callback: CallbackQuery, state: FSMContext):
    """Выбран тип комментария."""
    parts = callback.data.split(":")
    comment_type = parts[1]
    post_id = int(parts[2])

    # Сохраняем тип комментария
    await state.update_data(comment_type=comment_type)

    type_names = {
        "reflection": "🤔 Рефлексия",
        "idea": "💡 Идея",
        "question": "❓ Вопрос",
        "update": "📝 Обновление"
    }

    await callback.message.edit_text(
        f"{type_names.get(comment_type, 'Комментарий')}\n\n"
        f"Напишите ваш комментарий:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(PersonalPostStates.waiting_comment)
async def process_comment(message: Message, state: FSMContext, db: AsyncSession):
    """Обработать текст комментария."""
    # Получаем данные из FSM
    data = await state.get_data()
    post_id = data.get("commenting_post_id")
    comment_type = data.get("comment_type", "reflection")

    if not post_id:
        await message.answer("❌ Ошибка: не найден ID заметки")
        await state.clear()
        return

    # Создаём комментарий
    comment = PostComment(
        post_id=post_id,
        user_id=message.from_user.id,
        content=message.text,
        comment_type=comment_type
    )

    db.add(comment)
    await db.commit()

    logger.info(
        "comment_added",
        post_id=post_id,
        comment_id=comment.id,
        comment_type=comment_type,
        user_id=message.from_user.id
    )

    # Очищаем FSM
    await state.clear()

    # Показываем комментарии
    buttons = [
        [InlineKeyboardButton(text="💬 К комментариям", callback_data=f"view_comments:{post_id}")],
        [InlineKeyboardButton(text="« К заметке", callback_data=f"view_post:{post_id}")]
    ]

    type_icons = {
        "reflection": "🤔",
        "idea": "💡",
        "question": "❓",
        "update": "📝"
    }

    await message.answer(
        f"✅ <b>Комментарий добавлен!</b>\n\n"
        f"{type_icons.get(comment_type, '💬')} {message.text}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("edit_post:"))
async def callback_edit_post(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Начать редактирование заметки."""
    post_id = int(callback.data.split(":")[1])

    # Получаем заметку
    result = await db.execute(
        select(PersonalPost).where(
            PersonalPost.id == post_id,
            PersonalPost.user_id == callback.from_user.id
        )
    )
    post = result.scalar_one_or_none()

    if not post:
        await callback.answer("❌ Заметка не найдена", show_alert=True)
        return

    # Сохраняем ID поста в FSM для последующего обновления
    await state.update_data(editing_post_id=post_id)
    await state.set_state(PersonalPostStates.waiting_edit_text)

    await callback.message.edit_text(
        f"✏️ <b>Редактирование заметки</b>\n\n"
        f"<b>Текущий текст:</b>\n{post.content}\n\n"
        f"{'─' * 30}\n\n"
        f"Отправьте новый текст сообщением. Я заменю содержимое заметки и обновлю теги.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(PersonalPostStates.waiting_edit_text)
async def process_edit_post(message: Message, state: FSMContext, db: AsyncSession):
    """Обработать отредактированный текст."""
    from app.modules.personal_posts_manager import enrich_post_with_metadata

    # Получаем ID редактируемого поста из FSM
    data = await state.get_data()
    post_id = data.get("editing_post_id")

    if not post_id:
        await message.answer("❌ Ошибка: не найден ID редактируемого поста")
        await state.clear()
        return

    # Получаем пост из БД
    result = await db.execute(
        select(PersonalPost).where(
            PersonalPost.id == post_id,
            PersonalPost.user_id == message.from_user.id
        )
    )
    post = result.scalar_one_or_none()

    if not post:
        await message.answer("❌ Заметка не найдена")
        await state.clear()
        return

    # Обновляем контент
    post.content = message.text
    post.updated_at = datetime.utcnow()

    # Показываем индикатор typing
    await message.bot.send_chat_action(message.chat.id, "typing")
    await message.answer("⏳ Обновляю заметку и перегенерирую теги...")

    try:
        # Обогащаем метаданными заново
        await enrich_post_with_metadata(post, db)

        tags_str = ", ".join(post.tags[:5]) if post.tags else "нет"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👁 Посмотреть заметку", callback_data=f"view_post:{post.id}")],
            [InlineKeyboardButton(text="📋 К списку заметок", callback_data="list_personal_posts")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main_menu")]
        ])

        await message.answer(
            f"✅ <b>Заметка обновлена!</b>\n\n"
            f"📂 <b>Категория:</b> {post.category or 'нет'}\n"
            f"🏷 <b>Теги:</b> {tags_str}\n"
            f"😊 <b>Тон:</b> {post.sentiment or 'нет'}",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error("post_edit_enrichment_error", error=str(e), post_id=post.id)
        await message.answer(
            f"⚠️ Заметка обновлена, но не удалось обогатить метаданными.\n\nОшибка: {str(e)}",
            parse_mode="HTML"
        )

    await state.clear()


@router.callback_query(F.data == "noop")
async def callback_noop(callback: CallbackQuery):
    """No operation - просто ответ на callback."""
    await callback.answer()


@router.callback_query(F.data == "back_to_main_menu")
async def callback_back_to_main_menu(callback: CallbackQuery):
    """Вернуться в главное меню."""
    await callback.answer()

    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )


@router.callback_query(F.data == "show_ai_analysis_menu")
async def callback_show_ai_analysis_menu(callback: CallbackQuery):
    """Показать меню выбора периода для AI анализа."""
    await callback.answer()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤖 7 дней", callback_data="ai_analysis:7"),
            InlineKeyboardButton(text="🤖 30 дней", callback_data="ai_analysis:30"),
        ],
        [
            InlineKeyboardButton(text="« Назад", callback_data="back_to_analytics_menu"),
        ]
    ])

    await callback.message.edit_text(
        "🤖 <b>AI Анализ и Рекомендации</b>\n\n"
        "Выберите период для анализа:\n\n"
        "GPT-4 проанализирует все метрики и даст конкретные рекомендации "
        "по улучшению engagement, контент-стратегии и оптимизации источников.",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "back_to_analytics_menu")
async def callback_back_to_analytics_menu(callback: CallbackQuery):
    """Вернуться к меню аналитики."""
    await callback.answer()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 7 дней", callback_data="analytics:7"),
            InlineKeyboardButton(text="📅 30 дней", callback_data="analytics:30"),
        ],
        [
            InlineKeyboardButton(text="📅 Всё время", callback_data="analytics:all"),
        ],
        [
            InlineKeyboardButton(text="🤖 AI Анализ", callback_data="show_ai_analysis_menu"),
        ]
    ])

    await callback.message.edit_text(
        "📊 <b>Выберите период для аналитики:</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("analytics:"))
async def callback_analytics(callback: CallbackQuery, db: AsyncSession):
    """Отобразить аналитику за период."""

    await callback.answer()

    if not await check_admin(callback.from_user.id):
        await callback.message.answer("⛔ У вас нет доступа")
        return

    try:
        period = callback.data.split(":")[1]
        days = int(period) if period != "all" else 9999

        # Показываем loading сообщение
        loading_msg = await callback.message.answer(
            "⏳ <b>Собираю аналитику...</b>\n\n"
            "Анализирую публикации, метрики и источники...",
            parse_mode="HTML"
        )

        logger.info("analytics_requested", period=period, days=days, user_id=callback.from_user.id)

        # Создаём сервис аналитики
        analytics = AnalyticsService(db)

        # Собираем все данные (базовые + новые)
        stats = await analytics.get_period_stats(days)
        top_posts = await analytics.get_top_posts(3, days)
        worst_posts = await analytics.get_worst_posts(3, days)
        sources = await analytics.get_source_stats(days)
        weekday_stats = await analytics.get_weekday_stats(min(days, 30))  # Максимум 30 дней для статистики по дням
        vector_stats = await analytics.get_vector_db_stats()
        source_recommendations = await analytics.get_source_recommendations(min(days, 30))

        # НОВЫЕ методы аналитики
        views_stats = await analytics.get_views_and_forwards_stats(days)
        best_time = await analytics.get_best_publish_time(min(days, 30))
        trending_topics = await analytics.get_trending_topics(days, top_n=5)
        alerts = await analytics.get_performance_alerts(days)
        funnel_hours = min(max(days * 24, 24), 24 * 30)
        conversion_funnel = await fetch_reader_conversion_funnel(hours=funnel_hours)

        # Форматируем отчёт
        report = format_analytics_report(
            stats=stats,
            top_posts=top_posts,
            worst_posts=worst_posts,
            sources=sources,
            weekday_stats=weekday_stats,
            vector_stats=vector_stats,
            source_recommendations=source_recommendations,
            views_stats=views_stats,
            best_time=best_time,
            trending_topics=trending_topics,
            alerts=alerts,
            conversion_funnel=conversion_funnel,
        )


        # Удаляем loading сообщение
        await loading_msg.delete()

        # Telegram ограничивает сообщения до 4096 символов
        # Если отчёт длинный - разбиваем на части
        if len(report) > 4096:
            # Разбиваем по разделителям
            parts = report.split("━━━━━━━━━━━━━━━━━━━━━━━━━━")

            current_part = ""
            for part in parts:
                if len(current_part + part) > 4000:
                    # Отправляем текущую часть
                    await callback.message.answer(current_part, parse_mode="HTML", disable_web_page_preview=True)
                    current_part = part
                else:
                    current_part += "━━━━━━━━━━━━━━━━━━━━━━━━━━" + part if current_part else part

            # Отправляем последнюю часть
            if current_part:
                await callback.message.answer(current_part, parse_mode="HTML", disable_web_page_preview=True)
        else:
            # Отправляем целиком
            await callback.message.answer(report, parse_mode="HTML", disable_web_page_preview=True)

        logger.info("analytics_sent", period=period, report_length=len(report))

    except Exception as e:
        logger.error("analytics_error", error=str(e), period=callback.data)
        # Удаляем loading сообщение если оно существует
        try:
            await loading_msg.delete()
        except:
            pass
        await callback.message.answer(
            "❌ Произошла ошибка при сборе аналитики. Попробуйте позже.",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("ai_analysis:"))
async def callback_ai_analysis(callback: CallbackQuery, db: AsyncSession):
    """AI-анализ аналитики с рекомендациями от GPT-4."""

    await callback.answer()

    if not await check_admin(callback.from_user.id):
        await callback.message.answer("⛔ У вас нет доступа")
        return

    try:
        period = callback.data.split(":")[1]
        days = int(period) if period != "all" else 30  # Ограничиваем для AI анализа

        loading_msg = await callback.message.answer(
            "🤖 <b>AI Анализ запущен...</b>\n\n"
            "⏳ Собираю данные и анализирую метрики...\n"
            "⏳ Отправляю запрос к GPT-4...",
            parse_mode="HTML"
        )

        logger.info("ai_analysis_requested", period=period, days=days, user_id=callback.from_user.id)

        # Собираем данные аналитики
        analytics = AnalyticsService(db)

        stats = await analytics.get_period_stats(days)
        top_posts = await analytics.get_top_posts(3, days)
        worst_posts = await analytics.get_worst_posts(3, days)
        sources = await analytics.get_source_stats(days)
        views_stats = await analytics.get_views_and_forwards_stats(days)
        best_time = await analytics.get_best_publish_time(min(days, 30))
        trending_topics = await analytics.get_trending_topics(days, top_n=5)
        alerts = await analytics.get_performance_alerts(days)
        source_recommendations = await analytics.get_source_recommendations(min(days, 30))

        # Формируем данные для GPT
        analytics_data = f"""
ПЕРИОД АНАЛИЗА: {days} дней

ОСНОВНЫЕ МЕТРИКИ:
- Публикаций: {stats['total_publications']}
- Одобрено драфтов: {stats['approved_drafts']} из {stats['total_drafts']} ({stats['approval_rate']:.1f}%)
- Engagement rate: {stats['engagement_rate']:.1f}%
- Avg quality score: {stats['avg_quality_score']}

РЕАКЦИИ:
- Полезно: {stats['reactions']['useful']}
- Важно: {stats['reactions']['important']}
- Спорно: {stats['reactions']['controversial']}
- Банально: {stats['reactions']['banal']}
- Плохое качество: {stats['reactions']['poor_quality']}

VIEWS И FORWARDS:
- Всего просмотров: {views_stats.get('total_views', 0)}
- Avg просмотров/пост: {views_stats.get('avg_views', 0)}
- Всего форвардов: {views_stats.get('total_forwards', 0)}
- Viral coefficient: {views_stats.get('viral_coefficient', 0)}%

ЛУЧШЕЕ ВРЕМЯ ПУБЛИКАЦИИ:
{best_time.get('recommendation', 'Нет данных')}

ТРЕНДОВЫЕ ТЕМЫ:
{chr(10).join([f"- {t['topic']} ({t['mentions']} упоминаний)" for t in trending_topics[:5]]) if trending_topics else 'Нет данных'}

ТОП-3 ПОСТА:
{chr(10).join([f"- {p['title'][:60]}... (quality: {p['quality_score']})" for p in top_posts[:3]]) if top_posts else 'Нет данных'}

ХУДШИЕ ПОСТЫ:
{chr(10).join([f"- {p['title'][:60]}... (quality: {p['quality_score']})" for p in worst_posts[:3]]) if worst_posts else 'Нет данных'}

ПРОБЛЕМНЫЕ ИСТОЧНИКИ:
{chr(10).join([f"- {s['source_name']}: {s['recommendation']}" for s in source_recommendations[:3]]) if source_recommendations else 'Нет проблем'}

АЛЕРТЫ:
{chr(10).join([f"[{a['severity'].upper()}] {a['message']}" for a in alerts]) if alerts else 'Нет алертов'}
"""

        # Вызываем GPT-4 для анализа
        from app.modules.ai_core import call_openai_chat

        prompt = f"""Ты - эксперт по аналитике Telegram каналов и контент-маркетингу.

Проанализируй следующие данные аналитики канала @legal_ai_pro (новости о внедрении ИИ в юриспруденцию и бизнес):

{analytics_data}

Дай детальный анализ и конкретные рекомендации:

1. **АНАЛИЗ СИТУАЦИИ** (2-3 предложения):
   - Общая оценка производительности канала
   - Ключевые проблемы и возможности

2. **ПРИОРИТЕТНЫЕ РЕКОМЕНДАЦИИ** (топ-3, нумерованный список):
   - Конкретные действия для улучшения метрик
   - Фокус на engagement, quality score, и viral coefficient

3. **КОНТЕНТ-СТРАТЕГИЯ**:
   - Какие темы работают лучше всего (на основе trending topics)
   - Рекомендации по улучшению худших постов
   - Как повысить viral coefficient

4. **ИСТОЧНИКИ КОНТЕНТА**:
   - Какие источники стоит оптимизировать/отключить
   - Рекомендации по поиску новых источников

5. **ТАЙМИНГ ПУБЛИКАЦИЙ**:
   - Оптимальное время на основе данных
   - Рекомендации по частоте публикаций

Формат ответа: структурированный, с эмодзи, конкретными цифрами и actionable советами. Не более 800 слов."""

        ai_response, usage_stats = await call_openai_chat(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",  # Используем GPT-4o для качественного анализа и рекомендаций
            temperature=0.7,
            max_tokens=2000,
            db=db,
            operation="ai_analysis"
        )

        # Получаем общую статистику AI анализов
        ai_stats = await analytics.get_ai_analysis_stats()

        # Форматируем ответ
        report = f"""🤖 <b>AI АНАЛИЗ АНАЛИТИКИ</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━

{ai_response}

━━━━━━━━━━━━━━━━━━━━━━━━━━

<i>Анализ выполнен GPT-4 на основе данных за {days} дней</i>
📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}

💰 <b>Стоимость анализа:</b>
📊 Токенов: {usage_stats['total_tokens']:,} (prompt: {usage_stats['prompt_tokens']:,}, completion: {usage_stats['completion_tokens']:,})
💵 Стоимость: ${usage_stats['cost_usd']:.4f}

📈 <b>Общая статистика AI анализов:</b>
• За месяц: {ai_stats['month']['count']} запросов, {ai_stats['month']['total_tokens']:,} токенов, ${ai_stats['month']['total_cost_usd']:.2f}
• За год: {ai_stats['year']['count']} запросов, {ai_stats['year']['total_tokens']:,} токенов, ${ai_stats['year']['total_cost_usd']:.2f}"""

        # Удаляем loading сообщение
        await loading_msg.delete()

        # Отправляем ответ (может быть длинным, поэтому разбиваем если нужно)
        if len(report) > 4096:
            # Разбиваем на части
            parts = report.split("━━━━━━━━━━━━━━━━━━━━━━━━━━")
            for i, part in enumerate(parts):
                if part.strip():
                    await callback.message.answer(
                        part if i == 0 else "━━━━━━━━━━━━━━━━━━━━━━━━━━" + part,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
        else:
            await callback.message.answer(report, parse_mode="HTML", disable_web_page_preview=True)

        logger.info("ai_analysis_sent", period=period, response_length=len(ai_response))

    except Exception as e:
        logger.error("ai_analysis_error", error=str(e), period=callback.data)
        # Удаляем loading сообщение если оно существует
        try:
            await loading_msg.delete()
        except:
            pass
        await callback.message.answer(
            "❌ Произошла ошибка при AI анализе. Попробуйте позже.\n\n"
            f"Ошибка: {str(e)}",
            parse_mode="HTML"
        )


@router.message(Command("alerts"))
async def cmd_alerts(message: Message, db: AsyncSession):
    """Проверить алерты и предупреждения о проблемах."""

    if not await check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде")
        return

    await message.answer("🔍 Проверяю метрики...")

    try:
        analytics = AnalyticsService(db)

        # Проверяем за последние 7 дней
        alerts = await analytics.get_performance_alerts(days=7)

        if not alerts:
            await message.answer(
                "✅ <b>Всё в порядке!</b>\n\n"
                "Проблем не обнаружено. Система работает нормально.",
                parse_mode="HTML"
            )
        else:
            # Формируем отчёт с алертами
            report = "🚨 <b>Обнаружены проблемы:</b>\n\n"

            # Группируем по severity
            critical = [a for a in alerts if a.get('severity') == 'critical']
            warnings = [a for a in alerts if a.get('severity') == 'warning']
            info = [a for a in alerts if a.get('severity') == 'info']

            if critical:
                report += "🔴 <b>КРИТИЧЕСКИЕ:</b>\n"
                for alert in critical:
                    report += f"{alert['message']}\n"
                    report += f"   └─ {alert['details']}\n\n"

            if warnings:
                report += "⚠️ <b>ПРЕДУПРЕЖДЕНИЯ:</b>\n"
                for alert in warnings:
                    report += f"{alert['message']}\n"
                    report += f"   └─ {alert['details']}\n\n"

            if info:
                report += "💡 <b>ИНФОРМАЦИЯ:</b>\n"
                for alert in info:
                    report += f"{alert['message']}\n"
                    report += f"   └─ {alert['details']}\n\n"

            report += f"\n📅 Проверено: {datetime.now().strftime('%d.%m.%Y %H:%M')}"

            await message.answer(report, parse_mode="HTML")

        logger.info("alerts_checked", user_id=message.from_user.id, alerts_count=len(alerts))

    except Exception as e:
        logger.error("alerts_error", error=str(e))
        await message.answer(
            "❌ Произошла ошибка при проверке алертов. Попробуйте позже.",
            parse_mode="HTML"
        )


# ====================
# Настройка команд бота
# ====================

async def setup_bot_commands():
    """Установить меню команд бота (кнопка меню слева внизу)."""
    commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="drafts", description="📝 Новые драфты"),
        BotCommand(command="fetch", description="🔄 Запустить сбор новостей"),
        BotCommand(command="analytics", description="📊 Аналитика канала"),
        BotCommand(command="moderation", description="🛡️ Статистика модерации"),
        BotCommand(command="lead_analytics", description="🎯 Аналитика лидов"),
        BotCommand(command="alerts", description="🚨 Проверить проблемы"),
        BotCommand(command="stats", description="📈 Статистика системы"),
        BotCommand(command="help", description="❓ Помощь"),
    ]
    await get_bot().set_my_commands(commands)
    logger.info("bot_commands_set", count=len(commands))


@router.callback_query(F.data == "settings:fetcher")
async def callback_settings_fetcher(callback: CallbackQuery, db: AsyncSession):
    """Настройки сбора новостей."""
    from app.modules.settings_manager import get_setting

    max_articles = await get_setting("fetcher.max_articles_per_source", db, 300)

    await callback.message.edit_text(
        f"🔄 <b>Настройки сбора новостей</b>\n\n"
        f"📊 <b>Максимум статей на источник:</b> {max_articles}\n\n"
        f"🎯 <b>Источники:</b> 12 активных\n\n"
        f"💡 <b>Максимум за сборку:</b> {max_articles * 12} статей\n\n"
        f"⚙️ Используйте кнопки ниже для настройки",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="- 50", callback_data="fetcher:dec:50"),
                InlineKeyboardButton(text="- 10", callback_data="fetcher:dec:10"),
                InlineKeyboardButton(text="+ 10", callback_data="fetcher:inc:10"),
                InlineKeyboardButton(text="+ 50", callback_data="fetcher:inc:50"),
            ],
            [InlineKeyboardButton(text="« Назад", callback_data="back_to_settings")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fetcher:inc:") | F.data.startswith("fetcher:dec:"))
async def callback_fetcher_adjust(callback: CallbackQuery, db: AsyncSession):
    """Изменить настройки сбора новостей."""
    from app.modules.settings_manager import get_setting, set_setting
    from aiogram.exceptions import TelegramBadRequest

    # Parse action and value
    parts = callback.data.split(":")
    action = parts[1]  # "inc" or "dec"
    value = int(parts[2])

    # Get current value
    max_articles = await get_setting("fetcher.max_articles_per_source", db, 300)

    # Update value
    if action == "inc":
        new_value = max_articles + value
    else:
        new_value = max(10, max_articles - value)  # Minimum 10 articles

    # Save new value
    await set_setting("fetcher.max_articles_per_source", new_value, db)

    # Update message - always try to update
    try:
        await callback.message.edit_text(
            f"🔄 <b>Настройки сбора новостей</b>\n\n"
            f"📊 <b>Максимум статей на источник:</b> {new_value}\n\n"
            f"🎯 <b>Источники:</b> 12 активных\n\n"
            f"💡 <b>Максимум за сборку:</b> {new_value * 12} статей\n\n"
            f"⚙️ Используйте кнопки ниже для настройки",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="- 50", callback_data="fetcher:dec:50"),
                    InlineKeyboardButton(text="- 10", callback_data="fetcher:dec:10"),
                    InlineKeyboardButton(text="+ 10", callback_data="fetcher:inc:10"),
                    InlineKeyboardButton(text="+ 50", callback_data="fetcher:inc:50"),
                ],
                [InlineKeyboardButton(text="« Назад", callback_data="back_to_settings")]
            ])
        )
    except TelegramBadRequest:
        # Message not modified - ignore
        pass

    # Show notification
    if new_value != max_articles:
        await callback.answer(f"✅ Установлено: {new_value} статей на источник")
    else:
        await callback.answer(f"⚠️ Минимальное значение: 10 статей")


# ====================
# Запуск бота
# ====================

async def start_bot():
    """Запустить бота."""
    # Инициализация базы данных (создаём таблицы если их нет)
    from app.models.database import init_db, get_db
    from app.modules.settings_manager import init_default_settings
    try:
        await init_db()
        logger.info("database_initialized")

        # Инициализация дефолтных настроек
        async for db in get_db():
            await init_default_settings(db)
            logger.info("default_settings_initialized")
            break

    except Exception as e:
        logger.error("database_init_error", error=str(e))

    # Регистрируем middleware для БД сессий
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())

    # Регистрируем роутер
    dp.include_router(router)

    logger.info("bot_starting")

    # Удаляем вебхуки если есть
    logger.info("deleting_webhook")
    await get_bot().delete_webhook(drop_pending_updates=True)

    # Устанавливаем меню команд
    await setup_bot_commands()

    # Запускаем polling
    await dp.start_polling(get_bot())


if __name__ == "__main__":
    asyncio.run(start_bot())
