"""
Reader Bot Handlers.

Handles user interactions:
- Onboarding flow (/start)
- Commands (/today, /search, /saved, /settings)
- Feedback buttons (like/dislike)
- Save/unsave articles
"""

import re
from html import escape
from typing import Optional
from uuid import UUID
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, ForceReply, User
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import structlog
from app.bot.telegram_ui import inline_button as InlineKeyboardButton

logger = structlog.get_logger()

from app.services.reader_service import (
    get_user_profile,
    create_user_profile,
    update_user_profile,
    get_personalized_feed,
    get_weekly_digest_candidates,
    search_publications,
    save_user_feedback,
    save_article,
    unsave_article,
    get_saved_articles,
    get_user_stats,
    update_last_active,
    get_lead_profile,
    create_lead_profile,
    update_lead_profile,
    increment_questions_asked,
    calculate_lead_score,
    get_publication_by_id,
)
from app.models.reader_publications import ReaderPublication
from app.services.core_feedback import push_reader_feedback, reader_post_deeplink
from app.services.core_reader_bridge import (
    build_reader_miniapp_deeplink,
    fetch_reader_miniapp_profile,
    push_reader_cta_click,
    push_reader_lead_intent,
    push_reader_save_state,
)
from app.config import settings


router = Router()


# ==================== FSM States ====================

class OnboardingStates(StatesGroup):
    topics = State()
    expertise = State()
    digest = State()


class LeadMagnetStates(StatesGroup):
    """States for lead magnet flow: contacts ↔ personalized content."""
    start_lead_magnet = State()
    collect_email = State()
    collect_company = State()
    collect_position = State()
    choose_expertise = State()
    choose_business_focus = State()
    ask_questions = State()
    provide_digest = State()
    followup_questions = State()


class ArticleConsultationStates(StatesGroup):
    """State for article -> consultation transfer flow."""
    wait_question = State()


# ==================== Helper Functions ====================


async def _safe_get_saved_articles(user_id: int, db: AsyncSession, limit: int = 20) -> list[ReaderPublication]:
    """Never break handler flow if saved-articles query fails."""
    try:
        return await get_saved_articles(user_id, limit=limit, db=db)
    except Exception:
        logger.exception("saved_articles_fetch_failed", user_id=user_id)
        return []


def format_article_message(article: ReaderPublication, index: Optional[int] = None) -> str:
    """Format article for display."""
    if not article.draft:
        return "Статья не найдена"

    # Calculate engagement
    reactions_count = sum(article.reactions.values()) if article.reactions else 0
    engagement_rate = (reactions_count / article.views * 100) if article.views > 0 else 0

    # Format date
    published_date = article.published_at.strftime('%d.%m.%Y')

    prefix = f"{'📰 ' + str(index) + '. ' if index else '📰 '}"

    return (
        f"{prefix}<b>{article.draft.title}</b>\n\n"
        f"👁 {article.views:,} просмотров • "
        f"💬 {reactions_count} реакций • "
        f"📈 {engagement_rate:.1f}%\n"
        f"📅 {published_date}"
    )


def _trim_text(text: str, limit: int = 360) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "..."


async def _build_weekly_digest_text(articles: list[ReaderPublication], db: AsyncSession) -> str:
    """Build weekly digest text via LLM with deterministic fallback."""
    if not articles:
        return "📭 За неделю релевантных публикаций пока не найдено."

    source_lines = []
    for idx, article in enumerate(articles[:8], 1):
        source_lines.append(
            f"{idx}) {article.draft.title}\n"
            f"{_trim_text(article.draft.content, 260)}"
        )
    source_blob = "\n\n".join(source_lines)

    try:
        from app.modules.llm_provider import get_llm_provider

        llm = get_llm_provider(settings.default_llm_provider)
        digest = await llm.generate_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты редактор канала про AI в юридической функции. "
                        "Сделай короткий недельный дайджест по материалам. "
                        "Структура:\n"
                        "1) Главный тренд недели (1-2 предложения)\n"
                        "2) Что важно юристу/руководителю (3 пункта)\n"
                        "3) Какие внедрения имеет смысл пилотировать (2 пункта)\n"
                        "Пиши только по-русски, без Markdown-таблиц и без ссылок."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Материалы за неделю:\n\n{source_blob}",
                },
            ],
            max_tokens=650,
            temperature=0.35,
            operation="reader_weekly_digest",
            db=db,
        )
        digest_text = " ".join((digest or "").split()).strip()
        if digest_text:
            return (
                "📆 <b>Недельный дайджест для вас</b>\n\n"
                f"{escape(digest_text)}\n\n"
                "Ниже добавил карточки ключевых публикаций."
            )
    except Exception:
        logger.exception("reader_weekly_digest_generation_failed")

    # Fallback if LLM unavailable
    lines = []
    for idx, article in enumerate(articles[:6], 1):
        lines.append(
            f"{idx}. <b>{escape(_trim_text(article.draft.title, 110))}</b>\n"
            f"{escape(_trim_text(article.draft.content, 170))}"
        )
    return (
        "📆 <b>Недельный дайджест для вас</b>\n\n"
        "Ключевые материалы недели:\n\n"
        + "\n\n".join(lines)
    )


def _build_helper_link(payload: str | None = None) -> str:
    helper_username = (settings.news_helper_bot_username or "").strip().lstrip("@")
    if not helper_username:
        return ""
    if payload:
        return f"https://t.me/{helper_username}?start={payload}"
    return f"https://t.me/{helper_username}"


def _guess_miniapp_screen(last_action: str | None) -> str:
    action = (last_action or "").strip().lower()
    if "content" in action:
        return "content"
    if "tool" in action:
        return "tools"
    if "solution" in action:
        return "solutions"
    if "profile" in action or "onboarding" in action:
        return "profile"
    return "home"


def _humanize_miniapp_action(last_action: str | None) -> str:
    value = (last_action or "").strip()
    if not value:
        return "нет данных"
    if len(value) > 60:
        return value[:57] + "..."
    return value


def _build_reader_nav_keyboard(
    *,
    profile_ready: bool,
    lead_magnet_completed: bool = False,
    include_home: bool = True,
) -> InlineKeyboardMarkup:
    """Global navigation keyboard for reader bot screens."""
    if not profile_ready:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Настроить профиль", callback_data="rnav:start")],
            ]
        )

    rows = [
        [
            InlineKeyboardButton(text="📰 Сегодня", callback_data="rnav:today"),
            InlineKeyboardButton(text="📆 Неделя", callback_data="rnav:weekly"),
        ],
        [
            InlineKeyboardButton(text="🔍 Поиск", callback_data="rnav:search"),
            InlineKeyboardButton(text="🔖 Сохранённые", callback_data="rnav:saved"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="rnav:settings"),
            InlineKeyboardButton(text="🧩 Mini App", callback_data="rnav:miniapp"),
        ],
        [
            InlineKeyboardButton(
                text="🎯 Персональный дайджест" if not lead_magnet_completed else "✅ Лид-магнит",
                callback_data="rnav:lead_magnet",
            ),
        ],
    ]
    if include_home:
        rows.append([InlineKeyboardButton(text="🏠 Рабочий стол", callback_data="rnav:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_home_screen(target: Message, user: User, db: AsyncSession) -> None:
    """Render home screen for already onboarded user."""
    lead_profile = await get_lead_profile(user.id, db)
    saved_articles = await _safe_get_saved_articles(user.id, db=db)
    miniapp_profile = await fetch_reader_miniapp_profile(user_id=user.id)
    miniapp_last_action = (
        str((miniapp_profile or {}).get("last_action") or "").strip() if isinstance(miniapp_profile, dict) else ""
    )
    miniapp_onboarding_done = bool((miniapp_profile or {}).get("onboarding_done")) if miniapp_profile else False
    miniapp_interests_count = 0
    if isinstance(miniapp_profile, dict):
        interests = miniapp_profile.get("interests")
        if isinstance(interests, list):
            miniapp_interests_count = len([item for item in interests if isinstance(item, str) and item.strip()])

    miniapp_url = await build_reader_miniapp_deeplink(
        user_id=user.id,
        source="reader_bot",
        screen=_guess_miniapp_screen(miniapp_last_action),
        action="reader_home_continue_miniapp",
        payload={"entry": "home_screen"},
    )

    nav_markup = _build_reader_nav_keyboard(
        profile_ready=True,
        lead_magnet_completed=bool(lead_profile and lead_profile.lead_magnet_completed),
        include_home=False,
    )
    if miniapp_url:
        nav_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🧩 Продолжить в Mini App", url=miniapp_url)],
                *nav_markup.inline_keyboard,
            ]
        )

    lead_magnet_text = (
        "✅ Персональный дайджест уже активирован."
        if lead_profile and lead_profile.lead_magnet_completed
        else "🎯 Можно включить персональный дайджест за 2-3 шага."
    )
    miniapp_status = (
        "🧩 Mini App: профиль настроен"
        if miniapp_onboarding_done
        else "🧩 Mini App: профиль не настроен"
    )
    miniapp_state = (
        f"{miniapp_status} · интересов: {miniapp_interests_count} · последнее: {_humanize_miniapp_action(miniapp_last_action)}"
    )

    await target.answer(
        f"С возвращением, {escape(user.first_name or 'коллега')}! 👋\n\n"
        "Выберите действие кнопками ниже.\n\n"
        f"Сохранённых статей: <b>{len(saved_articles)}</b>\n"
        f"{lead_magnet_text}\n"
        f"{escape(miniapp_state)}",
        parse_mode="HTML",
        reply_markup=nav_markup,
    )


async def _show_search_prompt(target: Message) -> None:
    """Ask user for search query with ForceReply + quick nav."""
    await target.answer(
        "🔍 <b>Поиск по архиву</b>\n\n"
        "Введите поисковый запрос:\n"
        "Например: <i>GDPR</i>, <i>искусственный интеллект</i>, <i>налоги</i>",
        parse_mode="HTML",
        reply_markup=ForceReply(input_field_placeholder="Введите тему для поиска..."),
    )
    await target.answer(
        "Навигация:",
        reply_markup=_build_reader_nav_keyboard(profile_ready=True),
    )


def get_article_keyboard(publication_id: str, user_saved: bool = False, show_read_button: bool = True) -> InlineKeyboardMarkup:
    """Get keyboard for article with like/dislike/save buttons."""
    save_text = "❌ Удалить из сохранённых" if user_saved else "🔖 Сохранить"
    save_action = f"unsave:{publication_id}" if user_saved else f"save:{publication_id}"

    keyboard = []

    # Add "Read more" button if needed
    if show_read_button:
        keyboard.append([
            InlineKeyboardButton(text="📖 Читать полностью", callback_data=f"view:{publication_id}")
        ])

    keyboard.append([
        InlineKeyboardButton(text="💡 Идея внедрения", callback_data=f"idea:{publication_id}"),
        InlineKeyboardButton(text="❓ Вопрос по статье", callback_data=f"article_q:{publication_id}"),
    ])

    # Feedback buttons
    keyboard.append([
        InlineKeyboardButton(text="👍 Полезно", callback_data=f"feedback:like:{publication_id}"),
        InlineKeyboardButton(text="👎 Не интересно", callback_data=f"feedback:dislike:{publication_id}"),
    ])

    # Save button
    keyboard.append([
        InlineKeyboardButton(text=save_text, callback_data=save_action),
    ])

    # Quick navigation row
    keyboard.append([
        InlineKeyboardButton(text="🔍 Поиск", callback_data="rnav:search"),
        InlineKeyboardButton(text="🧩 Mini App", callback_data=f"mini:{publication_id}"),
    ])
    keyboard.append([
        InlineKeyboardButton(text="🏠 Рабочий стол", callback_data="rnav:home"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ==================== /start - Onboarding ====================

async def _handle_start(
    target: Message,
    user: User,
    state: FSMContext,
    db: AsyncSession,
    raw_text: str | None = None,
) -> None:
    """Shared /start flow for command and navigation callbacks."""
    user_id = user.id
    deep_link_post_id = _extract_start_post_id(raw_text)

    if deep_link_post_id:
        profile = await get_user_profile(user_id, db)
        if not profile:
            profile = await create_user_profile(
                user_id=user_id,
                username=user.username,
                full_name=user.full_name,
                db=db,
            )

        article = await get_publication_by_id(deep_link_post_id, db)
        if article:
            await update_last_active(user_id, db)
            deep_link_label = reader_post_deeplink(article.id)
            source_line = f"\n🔗 Ссылка на пост в ридере: {deep_link_label}" if deep_link_label else ""
            await target.answer(
                "Открыли пост из канала.\n\n"
                + format_article_message(article)
                + source_line,
                parse_mode="HTML",
                reply_markup=get_article_keyboard(str(article.id)),
            )
            await target.answer(
                "Открыт материал из канала. Дальше можно продолжить через навигацию:",
                reply_markup=_build_reader_nav_keyboard(profile_ready=True),
            )
            return

        await target.answer(
            "Пост по ссылке не найден. Возможно, он был удален.\n\n"
            "Откройте /today или /search, чтобы продолжить.",
            reply_markup=_build_reader_nav_keyboard(profile_ready=True),
        )
        return

    profile = await get_user_profile(user_id, db)

    if profile:
        await _show_home_screen(target, user, db)
    else:
        await start_onboarding(target, state, db)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, db: AsyncSession):
    """Handle /start command - onboarding for new users."""
    await _handle_start(message, message.from_user, state, db, raw_text=message.text)


@router.callback_query(F.data.startswith("rnav:"))
async def handle_reader_navigation(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Navigate across reader sections using inline buttons."""
    action = (callback.data or "").split(":", 1)[1]
    user_id = callback.from_user.id

    if action == "start":
        await state.clear()
        await _handle_start(callback.message, callback.from_user, state, db, raw_text="/start")
        await callback.answer()
        return

    profile = await get_user_profile(user_id, db)
    if not profile:
        await callback.answer("Сначала нужно настроить профиль", show_alert=True)
        await _handle_start(callback.message, callback.from_user, state, db, raw_text="/start")
        return

    await state.clear()
    if action == "home":
        await _show_home_screen(callback.message, callback.from_user, db)
    elif action == "today":
        await _show_today(callback.message, user_id, db)
    elif action == "weekly":
        await _show_weekly(callback.message, user_id, db)
    elif action == "search":
        await _show_search(callback.message, user_id, None, db)
    elif action == "saved":
        await _show_saved(callback.message, user_id, db)
    elif action == "settings":
        await _show_settings(callback.message, user_id, db)
    elif action == "miniapp":
        await _open_miniapp(
            callback.message,
            user_id,
            screen="home",
            action="reader_nav_open_miniapp",
            source="reader_nav",
        )
    elif action == "lead_magnet":
        await _open_lead_magnet(callback.message, user_id, state, db)
    else:
        await callback.answer("Неизвестный раздел", show_alert=True)
        return

    await callback.answer()


async def _open_lead_magnet(target: Message, user_id: int, state: FSMContext, db: AsyncSession) -> None:
    """Open lead-magnet section from command or navigation."""
    profile = await get_user_profile(user_id, db)
    if not profile:
        await target.answer(
            "❌ Сначала пройдите онбординг!\nИспользуйте /start для настройки профиля.",
            reply_markup=_build_reader_nav_keyboard(profile_ready=False),
        )
        return

    lead_profile = await get_lead_profile(user_id, db)
    if lead_profile and lead_profile.lead_magnet_completed:
        await target.answer(
            "✅ Вы уже прошли лид-магнит!\n\n"
            "Теперь у вас есть доступ к персональным дайджестам и вопросам по LegalTech.",
            reply_markup=_build_reader_nav_keyboard(
                profile_ready=True,
                lead_magnet_completed=True,
            ),
        )
        return

    await start_lead_magnet(target, state, db)


async def _open_miniapp(
    target: Message,
    user_id: int,
    *,
    screen: str = "home",
    action: str = "reader_open_miniapp",
    source: str = "reader_bot",
    post_id: str | None = None,
) -> None:
    """Open mini-app from reader bot with tracked deeplink."""
    miniapp_url = await build_reader_miniapp_deeplink(
        user_id=user_id,
        source=source,
        screen=screen,
        action=action,
        post_id=post_id,
        payload={"entry": source},
    )
    if not miniapp_url:
        await target.answer(
            "🧩 Mini App временно недоступен. Попробуйте чуть позже.",
            reply_markup=_build_reader_nav_keyboard(profile_ready=True),
        )
        return

    await push_reader_cta_click(
        user_id=user_id,
        publication_id=post_id,
        cta_type="miniapp_open",
        context=source,
        payload={"screen": screen, "action": action, "post_id": post_id},
    )

    await target.answer(
        "🧩 <b>Открыть Mini App Legal AI PRO</b>\n\n"
        "В mini-app доступен быстрый маршрут: контент -> инструменты -> внедрение.",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🧩 Открыть Mini App", url=miniapp_url)],
                [InlineKeyboardButton(text="🏠 Рабочий стол", callback_data="rnav:home")],
            ]
        ),
    )


@router.message(Command("lead_magnet"))
async def cmd_lead_magnet(message: Message, state: FSMContext, db: AsyncSession):
    """Handle /lead_magnet command - start lead magnet flow."""
    await _open_lead_magnet(message, message.from_user.id, state, db)


@router.message(Command("miniapp"))
async def cmd_miniapp(message: Message):
    """Open web mini-app."""
    await _open_miniapp(
        message,
        message.from_user.id,
        screen="home",
        action="reader_command_open_miniapp",
        source="reader_command",
    )


@router.callback_query(F.data.startswith("mini:"))
async def open_miniapp_from_article(callback: CallbackQuery, db: AsyncSession):
    """Open mini-app with article context."""
    if callback.message is None:
        await callback.answer("Откройте mini-app через меню", show_alert=True)
        return
    raw_post_id = (callback.data or "").split(":", 1)[1].strip()
    post_id = raw_post_id if raw_post_id else None
    if post_id:
        _ = await get_publication_by_id(post_id, db)
    await _open_miniapp(
        callback.message,
        callback.from_user.id,
        screen="content",
        action="reader_article_open_miniapp",
        source="reader_article",
        post_id=post_id,
    )
    await callback.answer()


@router.message(Command("ask_question"))
async def cmd_ask_question(message: Message, state: FSMContext, db: AsyncSession):
    """Handle /ask_question command - allow qualified leads to ask questions."""
    user_id = message.from_user.id

    # Check if lead magnet completed
    lead_profile = await get_lead_profile(user_id, db)
    if not lead_profile or not lead_profile.lead_magnet_completed:
        await message.answer(
            "❌ Сначала пройдите лид-магнит!\n\n"
            "Используйте /lead_magnet для получения персонального дайджеста "
            "и возможности задавать вопросы.",
            reply_markup=_build_reader_nav_keyboard(profile_ready=True),
        )
        return

    # Check questions limit
    if lead_profile.questions_asked >= 3:
        await message.answer(
            "📊 <b>Лимит вопросов исчерпан!</b>\n\n"
            "Вы уже задали 3 вопроса. Спасибо за участие!\n\n"
            "Продолжайте получать персональные дайджесты с /today",
            parse_mode="HTML",
            reply_markup=_build_reader_nav_keyboard(profile_ready=True),
        )
        return

    questions_left = 3 - lead_profile.questions_asked

    await message.answer(
        f"🤖 <b>Вопрос по LegalTech</b>\n\n"
        f"У вас осталось <b>{questions_left} вопроса</b>\n\n"
        "Задайте вопрос по темам:\n"
        "• ИИ в юриспруденции\n"
        "• LegalTech решения\n"
        "• Автоматизация юридических процессов\n\n"
        "<i>Вопрос должен быть связан с LegalTech. "
        "Если вопрос не по теме, бот вежливо откажет в ответе.</i>",
        parse_mode="HTML",
        reply_markup=_build_reader_nav_keyboard(profile_ready=True),
    )

    await state.set_state(LeadMagnetStates.ask_questions)


async def start_lead_magnet(message: Message, state: FSMContext, db: AsyncSession):
    """Start the lead magnet flow - offer value exchange."""
    user_id = message.from_user.id

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Да, хочу персональный дайджест!", callback_data="lead_magnet:accept")],
        [InlineKeyboardButton(text="❌ Пока не интересно", callback_data="lead_magnet:decline")]
    ])

    await message.answer(
        "🎯 <b>Получите персональный дайджест новостей об ИИ в юриспруденции!</b>\n\n"
        "Что вы получите:\n"
        "• 📧 Персонализированные новости по вашим интересам\n"
        "• 🤖 Ответы на 3-5 вопросов по LegalTech\n"
        "• 📊 Аналитика трендов в вашей сфере\n"
        "• 🎁 Специальные материалы для профессионалов\n\n"
        "Взамен мы попросим:\n"
        "• Ваш email для отправки дайджестов\n"
        "• Информацию о вашей компании и роли\n"
        "• Несколько вопросов для персонализации\n\n"
        "<i>Все данные конфиденциальны и используются только для улучшения сервиса.</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await state.set_state(LeadMagnetStates.start_lead_magnet)


async def start_onboarding(message: Message, state: FSMContext, db: AsyncSession):
    """Start onboarding flow - ask about topics."""
    # Create empty profile
    await create_user_profile(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        db=db
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="☐ Персональные данные (GDPR)", callback_data="topic:gdpr")],
        [InlineKeyboardButton(text="☐ ИИ в праве", callback_data="topic:ai_law")],
        [InlineKeyboardButton(text="☐ Криптовалюты и блокчейн", callback_data="topic:crypto")],
        [InlineKeyboardButton(text="☐ Корпоративное право", callback_data="topic:corporate")],
        [InlineKeyboardButton(text="☐ Налоги и финансы", callback_data="topic:tax")],
        [InlineKeyboardButton(text="☐ Интеллектуальная собственность", callback_data="topic:ip")],
        [InlineKeyboardButton(text="Далее →", callback_data="onboarding:expertise")],
    ])

    await message.answer(
        "👋 <b>Добро пожаловать в Legal AI News!</b>\n\n"
        "Давайте настроим вашу персональную ленту новостей.\n\n"
        "<b>1️⃣ Какие темы вас интересуют?</b> (выберите несколько)",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    # Save selected topics in FSM
    await state.update_data(topics=[])
    await state.set_state(OnboardingStates.topics)


@router.callback_query(F.data.startswith("topic:"), StateFilter(OnboardingStates.topics))
async def toggle_topic(callback: CallbackQuery, state: FSMContext):
    """Toggle topic selection during onboarding."""
    topic = callback.data.split(":")[1]

    # Get current topics
    data = await state.get_data()
    topics = data.get('topics', [])

    # Toggle
    if topic in topics:
        topics.remove(topic)
    else:
        topics.append(topic)

    await state.update_data(topics=topics)

    # Update keyboard
    topic_labels = {
        'gdpr': 'Персональные данные (GDPR)',
        'ai_law': 'ИИ в праве',
        'crypto': 'Криптовалюты и блокчейн',
        'corporate': 'Корпоративное право',
        'tax': 'Налоги и финансы',
        'ip': 'Интеллектуальная собственность'
    }

    buttons = []
    for topic_key, label in topic_labels.items():
        icon = "✅" if topic_key in topics else "☐"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {label}",
            callback_data=f"topic:{topic_key}"
        )])

    buttons.append([InlineKeyboardButton(text="Далее →", callback_data="onboarding:expertise")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "onboarding:expertise", StateFilter(OnboardingStates.topics))
async def ask_expertise(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Ask about expertise level."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Студент юрфака", callback_data="expertise:student")],
        [InlineKeyboardButton(text="⚖️ Практикующий юрист", callback_data="expertise:lawyer")],
        [InlineKeyboardButton(text="🏢 In-house юрист", callback_data="expertise:in_house")],
        [InlineKeyboardButton(text="💼 Бизнес/предприниматель", callback_data="expertise:business")],
    ])

    await callback.message.edit_text(
        "👋 <b>Добро пожаловать в Legal AI News!</b>\n\n"
        "Давайте настроим вашу персональную ленту новостей.\n\n"
        "<b>2️⃣ Ваш уровень экспертизы?</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await state.set_state(OnboardingStates.expertise)
    await callback.answer()


@router.callback_query(F.data.startswith("expertise:"), StateFilter(OnboardingStates.expertise))
async def save_expertise(callback: CallbackQuery, state: FSMContext):
    """Save expertise and ask about digest frequency."""
    expertise = callback.data.split(":")[1]
    await state.update_data(expertise=expertise)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="☀️ Ежедневно утром", callback_data="digest:daily")],
        [InlineKeyboardButton(text="📅 2 раза в неделю", callback_data="digest:twice_week")],
        [InlineKeyboardButton(text="📆 Еженедельно в пятницу", callback_data="digest:weekly")],
        [InlineKeyboardButton(text="🚫 Не нужно", callback_data="digest:never")],
    ])

    await callback.message.edit_text(
        "👋 <b>Добро пожаловать в Legal AI News!</b>\n\n"
        "Давайте настроим вашу персональную ленту новостей.\n\n"
        "<b>3️⃣ Как часто получать дайджесты?</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await state.set_state(OnboardingStates.digest)
    await callback.answer()


@router.callback_query(F.data.startswith("digest:"), StateFilter(OnboardingStates.digest))
async def complete_onboarding(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Complete onboarding and save profile."""
    digest = callback.data.split(":")[1]

    # Get all data
    data = await state.get_data()
    topics = data.get('topics', [])
    expertise = data.get('expertise')

    # Update profile
    await update_user_profile(
        user_id=callback.from_user.id,
        topics=topics,
        expertise_level=expertise,
        digest_frequency=digest,
        db=db
    )

    # Clear FSM
    await state.clear()

    # Success message
    topic_labels = {
        'gdpr': 'Персональные данные',
        'ai_law': 'ИИ в праве',
        'crypto': 'Криптовалюты',
        'corporate': 'Корпоративное право',
        'tax': 'Налоги',
        'ip': 'Интеллектуальная собственность'
    }
    topics_text = ', '.join([topic_labels.get(t, t) for t in topics]) if topics else 'все темы'

    digest_text = {
        'daily': 'ежедневно',
        'twice_week': '2 раза в неделю',
        'weekly': 'еженедельно',
        'never': 'не будете получать'
    }

    await callback.message.edit_text(
        f"✅ <b>Готово! Профиль настроен.</b>\n\n"
        f"📋 Ваши интересы: {topics_text}\n"
        f"📬 Дайджесты: {digest_text[digest]}\n\n"
        f"Теперь вы будете получать:\n"
        f"• Персональные рекомендации статей\n"
        f"• Дайджесты по вашим темам\n"
        f"• Доступ к поиску по архиву\n\n"
        f"<b>Попробуйте:</b>\n"
        f"/today - Что интересного сегодня\n"
        f"/search - Поиск статей\n"
        f"/saved - Сохранённые статьи",
        parse_mode="HTML",
        reply_markup=_build_reader_nav_keyboard(profile_ready=True, include_home=False),
    )

    await callback.answer("✅ Профиль настроен!")


async def _show_today(target: Message, user_id: int, db: AsyncSession) -> None:
    """Show personalized feed for today."""
    profile = await get_user_profile(user_id, db)

    if not profile:
        await target.answer(
            "Сначала завершите настройку профиля: /start",
            reply_markup=_build_reader_nav_keyboard(profile_ready=False),
        )
        return

    # Update last active
    await update_last_active(user_id, db)

    # Get personalized feed
    articles = await get_personalized_feed(user_id, limit=5, db=db)

    if not articles:
        await target.answer(
            "📭 Сегодня пока нет новых статей по вашим темам.\n\n"
            "Попробуйте:\n"
            "/search - Поиск по архиву\n"
            "/saved - Ваши сохранённые статьи",
            reply_markup=_build_reader_nav_keyboard(profile_ready=True),
        )
        return

    await target.answer(
        f"📬 <b>Ваши персональные новости за сегодня:</b>\n\n"
        f"Найдено {len(articles)} статей по вашим темам.",
        parse_mode="HTML"
    )

    # Send each article with keyboard
    for i, article in enumerate(articles, 1):
        text = format_article_message(article, index=i)
        keyboard = get_article_keyboard(str(article.id))

        await target.answer(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )


@router.message(Command("today"))
async def cmd_today(message: Message, db: AsyncSession):
    """Show personalized feed for today."""
    await _show_today(message, message.from_user.id, db)


async def _show_weekly(target: Message, user_id: int, db: AsyncSession) -> None:
    """Show weekly digest tailored to user interests."""
    profile = await get_user_profile(user_id, db)

    if not profile:
        await target.answer(
            "Сначала завершите настройку профиля: /start",
            reply_markup=_build_reader_nav_keyboard(profile_ready=False),
        )
        return

    await update_last_active(user_id, db)
    articles = await get_weekly_digest_candidates(user_id, limit=8, days=7, db=db)

    if not articles:
        await target.answer(
            "📭 За последнюю неделю пока нет новых релевантных материалов.\n\n"
            "Попробуйте /today или /search.",
            reply_markup=_build_reader_nav_keyboard(profile_ready=True),
        )
        return

    digest_text = await _build_weekly_digest_text(articles, db)
    await target.answer(
        digest_text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=_build_reader_nav_keyboard(profile_ready=True),
    )

    # Show top cards after digest summary
    for i, article in enumerate(articles[:3], 1):
        await target.answer(
            format_article_message(article, index=i),
            parse_mode="HTML",
            reply_markup=get_article_keyboard(str(article.id)),
        )

    await push_reader_feedback(
        publication_id=str(articles[0].id),
        user_id=user_id,
        source="reaction",
        signal_key="reader.weekly.opened",
        signal_value=1,
        text="Reader opened weekly digest",
        payload={"articles_count": len(articles)},
    )


@router.message(Command("weekly"))
async def cmd_weekly(message: Message, db: AsyncSession):
    """Show weekly digest tailored to user interests."""
    await _show_weekly(message, message.from_user.id, db)


# ==================== /search - Search ====================

async def _show_search(target: Message, user_id: int, query: str | None, db: AsyncSession) -> None:
    """Search publications or ask for a query."""
    profile_ready = bool(await get_user_profile(user_id, db))
    if not query:
        if not profile_ready:
            await target.answer(
                "Сначала завершите настройку профиля: /start",
                reply_markup=_build_reader_nav_keyboard(profile_ready=False),
            )
            return
        await _show_search_prompt(target)
        return

    results = await search_publications(query, user_id=user_id, limit=10, db=db)
    if not results:
        await target.answer(
            f"По запросу '<b>{escape(query)}</b>' ничего не найдено 😔\n\n"
            "Попробуйте другой запрос или используйте /today",
            parse_mode="HTML",
            reply_markup=_build_reader_nav_keyboard(profile_ready=profile_ready),
        )
        return

    await target.answer(
        f"🔍 Найдено <b>{len(results)}</b> статей по запросу '<b>{escape(query)}</b>':",
        parse_mode="HTML",
        reply_markup=_build_reader_nav_keyboard(profile_ready=profile_ready),
    )

    for i, article in enumerate(results, 1):
        await target.answer(
            format_article_message(article, index=i),
            parse_mode="HTML",
            reply_markup=get_article_keyboard(str(article.id)),
        )


@router.message(Command("search"))
async def cmd_search(message: Message, db: AsyncSession):
    """Search articles."""
    query = message.text.replace("/search", "").strip()
    await _show_search(message, message.from_user.id, query, db)


@router.message(F.reply_to_message, F.text)
async def handle_search_reply(message: Message, db: AsyncSession):
    """Handle reply to search prompt (ForceReply)."""
    # Check if replying to bot's search message
    if (message.reply_to_message and
        message.reply_to_message.from_user.is_bot and
        "Поиск по архиву" in message.reply_to_message.text):

        query = message.text.strip()
        user_id = message.from_user.id

        await _show_search(message, user_id, query, db)


# ==================== /saved - Saved Articles ====================

async def _show_saved(target: Message, user_id: int, db: AsyncSession) -> None:
    """Show saved articles list."""
    profile = await get_user_profile(user_id, db)
    if not profile:
        await target.answer(
            "Сначала завершите настройку профиля: /start",
            reply_markup=_build_reader_nav_keyboard(profile_ready=False),
        )
        return

    saved = await _safe_get_saved_articles(user_id, db=db, limit=20)

    if not saved:
        await target.answer(
            "🔖 У вас пока нет сохранённых статей.\n\n"
            "Используйте кнопку '🔖 Сохранить' под статьёй чтобы добавить в избранное.",
            reply_markup=_build_reader_nav_keyboard(profile_ready=True),
        )
        return

    await target.answer(
        f"🔖 <b>Ваши сохранённые статьи</b> ({len(saved)}):",
        parse_mode="HTML",
        reply_markup=_build_reader_nav_keyboard(profile_ready=True),
    )

    for i, article in enumerate(saved, 1):
        text = format_article_message(article, index=i)
        keyboard = get_article_keyboard(str(article.id), user_saved=True)

        await target.answer(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )


@router.message(Command("saved"))
async def cmd_saved(message: Message, db: AsyncSession):
    """Show saved articles."""
    await _show_saved(message, message.from_user.id, db)


# ==================== Feedback Callbacks ====================

@router.callback_query(F.data.startswith("feedback:"))
async def process_feedback(callback: CallbackQuery, db: AsyncSession):
    """Handle like/dislike feedback."""
    _, action, article_id = callback.data.split(":")
    user_id = callback.from_user.id

    is_useful = (action == "like")

    # Save feedback
    try:
        await save_user_feedback(
            user_id=user_id,
            publication_id=article_id,
            is_useful=is_useful,
            db=db,
        )
    except ValueError:
        await callback.answer("Статья устарела, откройте новую из /today", show_alert=True)
        return

    if is_useful:
        await push_reader_feedback(
            publication_id=article_id,
            user_id=user_id,
            source="comment",
            signal_key="reader.useful",
            signal_value=1,
            text="Reader marked post as useful",
            payload={"feedback_action": "like"},
        )
        await callback.answer("✅ Спасибо за отзыв!")
    else:
        # Ask for reason
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Слишком сложно", callback_data=f"feedback_type:too_complex:{article_id}")],
            [InlineKeyboardButton(text="Не по моей теме", callback_data=f"feedback_type:not_relevant:{article_id}")],
            [InlineKeyboardButton(text="Устаревшая информация", callback_data=f"feedback_type:outdated:{article_id}")],
            [InlineKeyboardButton(text="Слишком поверхностно", callback_data=f"feedback_type:shallow:{article_id}")],
        ])

        await callback.message.answer(
            "Что не понравилось?",
            reply_markup=keyboard
        )
        await callback.answer()


@router.callback_query(F.data.startswith("feedback_type:"))
async def save_feedback_type(callback: CallbackQuery, db: AsyncSession):
    """Save detailed feedback type."""
    _, feedback_type, article_id = callback.data.split(":")
    user_id = callback.from_user.id

    # Update feedback with type
    try:
        await save_user_feedback(
            user_id=user_id,
            publication_id=article_id,
            is_useful=False,
            feedback_type=feedback_type,
            db=db,
        )
    except ValueError:
        await callback.answer("Статья устарела, откройте новую из /today", show_alert=True)
        return

    reason_map = {
        "too_complex": "Слишком сложно",
        "not_relevant": "Не по моей теме",
        "outdated": "Устаревшая информация",
        "shallow": "Слишком поверхностно",
    }
    reason_text = reason_map.get(feedback_type, feedback_type)
    await push_reader_feedback(
        publication_id=article_id,
        user_id=user_id,
        source="comment",
        signal_key=f"reader.not_useful.{feedback_type}",
        signal_value=-1,
        text=f"Reader negative feedback: {reason_text}",
        payload={"feedback_type": feedback_type},
    )

    await callback.message.delete()
    await callback.answer("✅ Спасибо! Учтем в рекомендациях")


# ==================== Save/Unsave Callbacks ====================

@router.callback_query(F.data.startswith("save:"))
async def save_article_callback(callback: CallbackQuery, db: AsyncSession):
    """Save article to bookmarks."""
    article_id = callback.data.split(":")[1]
    user_id = callback.from_user.id

    try:
        await save_article(user_id, article_id, db)
    except ValueError:
        await callback.answer("Статья устарела, откройте новую из /today", show_alert=True)
        return
    await push_reader_save_state(user_id=user_id, publication_id=article_id, saved=True)

    # Update keyboard
    keyboard = get_article_keyboard(str(article_id), user_saved=True)
    await callback.message.edit_reply_markup(reply_markup=keyboard)

    await callback.answer("✅ Сохранено!")


@router.callback_query(F.data.startswith("unsave:"))
async def unsave_article_callback(callback: CallbackQuery, db: AsyncSession):
    """Remove article from bookmarks."""
    article_id = callback.data.split(":")[1]
    user_id = callback.from_user.id

    try:
        await unsave_article(user_id, article_id, db)
    except ValueError:
        await callback.answer("Статья устарела, откройте новую из /today", show_alert=True)
        return
    await push_reader_save_state(user_id=user_id, publication_id=article_id, saved=False)

    # Update keyboard
    keyboard = get_article_keyboard(str(article_id), user_saved=False)
    await callback.message.edit_reply_markup(reply_markup=keyboard)

    await callback.answer("❌ Удалено из сохранённых")


@router.callback_query(F.data.startswith("view:"))
async def view_article_callback(callback: CallbackQuery, db: AsyncSession):
    """Show full article text."""
    article_id = callback.data.split(":")[1]
    user_id = callback.from_user.id

    try:
        article_uuid = UUID(article_id)
    except ValueError:
        await callback.answer("❌ Некорректный ID статьи", show_alert=True)
        return

    result = await db.execute(
        select(ReaderPublication).where(ReaderPublication.id == article_uuid)
    )
    article = result.scalar_one_or_none()

    if not article or not article.draft:
        await callback.answer("❌ Статья не найдена", show_alert=True)
        return

    # Check if saved
    saved_articles = await _safe_get_saved_articles(user_id, db=db)
    user_saved = any(str(s.id) == str(article_uuid) for s in saved_articles)

    # Format full article
    published_date = article.published_at.strftime("%d.%m.%Y")

    full_text = (
        f"📰 <b>{article.draft.title}</b>\n\n"
        f"{article.draft.content}\n\n"
        f"👁 {article.views or 0} | 📅 {published_date}"
    )

    # Show full text with keyboard (without "Read more" button)
    keyboard = get_article_keyboard(str(article_uuid), user_saved=user_saved, show_read_button=False)

    await callback.message.edit_text(
        full_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await callback.answer()


@router.callback_query(F.data.startswith("idea:"))
async def generate_automation_idea_callback(callback: CallbackQuery, db: AsyncSession):
    """Generate practical automation idea based on selected article."""
    article_id = callback.data.split(":")[1]
    user_id = callback.from_user.id

    try:
        article_uuid = UUID(article_id)
    except ValueError:
        await callback.answer("❌ Некорректный ID статьи", show_alert=True)
        return

    result = await db.execute(
        select(ReaderPublication).where(ReaderPublication.id == article_uuid)
    )
    article = result.scalar_one_or_none()
    if not article or not article.draft:
        await callback.answer("❌ Статья не найдена", show_alert=True)
        return

    await callback.answer("⏳ Формирую идею внедрения...")

    try:
        from app.modules.llm_provider import get_llm_provider

        llm = get_llm_provider(settings.default_llm_provider)
        llm_text = await llm.generate_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты продуктовый консультант по Legal AI. "
                        "На основе новости предложи практическую идею внедрения для юрфункции. "
                        "Ответ только на русском, компактно, без воды. "
                        "Структура строго из трех блоков:\n"
                        "1) Где применить\n"
                        "2) Быстрый пилот (2 недели)\n"
                        "3) Риски и правовой контроль\n"
                        "Максимум 900 символов."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Заголовок: {article.draft.title}\n\n"
                        f"Текст:\n{article.draft.content[:3500]}"
                    ),
                },
            ],
            max_tokens=420,
            temperature=0.45,
            operation="reader_idea_generation",
            db=db,
        )
    except Exception:
        logger.exception("reader_idea_generation_failed", user_id=user_id, article_id=str(article_uuid))
        await callback.message.answer(
            "Не удалось сформировать идею автоматически. Попробуйте позже."
        )
        return

    helper_username = (settings.news_helper_bot_username or "").strip().lstrip("@")
    helper_line = ""
    if helper_username:
        helper_line = (
            f"\n\nЕсли хотите разобрать внедрение под ваш кейс, "
            f"напишите в <a href=\"https://t.me/{helper_username}\">Ассистент Legal AI PRO</a>."
        )

    await callback.message.answer(
        f"💡 <b>Идея внедрения по материалу:</b>\n"
        f"<b>{escape(article.draft.title[:120])}</b>\n\n"
        f"{escape(llm_text)}"
        f"{helper_line}",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

    await push_reader_feedback(
        publication_id=article_id,
        user_id=user_id,
        source="reaction",
        signal_key="reader.idea.requested",
        signal_value=1,
        text="Reader requested automation idea",
        payload={"event": "idea_requested"},
    )


@router.callback_query(F.data.startswith("article_q:"))
async def start_article_question_flow(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Start question transfer flow from an article to lead bot."""
    article_id = callback.data.split(":")[1]

    article = await get_publication_by_id(article_id, db)
    if not article:
        await callback.answer("❌ Статья не найдена", show_alert=True)
        return

    await state.update_data(
        article_id=str(article.id),
        article_title=article.draft.title,
    )
    await state.set_state(ArticleConsultationStates.wait_question)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="article_q_cancel")],
        ]
    )
    await callback.message.answer(
        "✍️ <b>Вопрос по статье</b>\n\n"
        "Напишите 1-2 предложения: что именно хотите разобрать по этому материалу.\n"
        "Я подготовлю структурированную формулировку для обращения в консультацию.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await push_reader_cta_click(
        user_id=callback.from_user.id,
        publication_id=str(article.id),
        cta_type="article_question",
        context="reader_article_card",
        payload={"screen": "article_q_start"},
    )
    await callback.answer("Готово, жду ваш вопрос")


@router.callback_query(F.data == "article_q_cancel", StateFilter(ArticleConsultationStates.wait_question))
async def cancel_article_question_flow(callback: CallbackQuery, state: FSMContext):
    """Cancel article question flow."""
    await state.clear()
    await callback.answer("Отменено")
    await callback.message.answer(
        "Окей, продолжаем. Откройте /today или /weekly.",
        reply_markup=_build_reader_nav_keyboard(profile_ready=True),
    )


@router.message(StateFilter(ArticleConsultationStates.wait_question), F.text)
async def handle_article_question_text(message: Message, state: FSMContext, db: AsyncSession):
    """Convert free-form question to consultation draft and route to helper bot."""
    user_id = message.from_user.id
    user_question = (message.text or "").strip()
    if len(user_question) < 6:
        await message.answer("Нужно чуть подробнее: хотя бы 6-8 символов.")
        return

    data = await state.get_data()
    article_id = str(data.get("article_id") or "").strip()
    article_title = str(data.get("article_title") or "Материал из канала").strip()
    article = await get_publication_by_id(article_id, db) if article_id else None

    consultation_text = ""
    try:
        from app.modules.llm_provider import get_llm_provider

        llm = get_llm_provider(settings.default_llm_provider)
        consultation_text = await llm.generate_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты помощник пресейла Legal AI. Переформулируй вопрос клиента для консультации. "
                        "Формат строго из 3 блоков:\n"
                        "Контекст:\n"
                        "Задача:\n"
                        "Ожидаемый результат:\n"
                        "Кратко, предметно, до 700 символов, русский язык."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Заголовок статьи: {article_title}\n"
                        f"Фрагмент статьи: {_trim_text(article.draft.content if article else '', 1000)}\n"
                        f"Вопрос пользователя: {user_question}"
                    ),
                },
            ],
            max_tokens=420,
            temperature=0.35,
            operation="reader_question_transfer",
            db=db,
        )
    except Exception:
        logger.exception("reader_question_transfer_generation_failed", user_id=user_id, article_id=article_id)

    if not consultation_text.strip():
        consultation_text = (
            f"Контекст: Обсуждаем материал «{article_title}».\n"
            f"Задача: {user_question}\n"
            "Ожидаемый результат: получить вариант внедрения и оценку рисков/этапов."
        )

    payload = f"readerq_{article_id}" if article_id else "readerq"
    helper_link = _build_helper_link(payload)
    keyboard_rows = []
    if helper_link:
        keyboard_rows.append(
            [InlineKeyboardButton(text="✉️ Написать в Ассистент Legal AI PRO", url=helper_link)]
        )
    keyboard_rows.append(
        [InlineKeyboardButton(text="🔁 Сформулировать заново", callback_data=f"article_q:{article_id}")]
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await message.answer(
        "🧭 <b>Подготовил черновик обращения</b>\n\n"
        "<b>Текст для отправки:</b>\n"
        f"<code>{escape(_trim_text(consultation_text, 1400))}</code>\n\n"
        "Если нужно, можно сформулировать заново.",
        parse_mode="HTML",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )

    if article_id:
        await push_reader_feedback(
            publication_id=article_id,
            user_id=user_id,
            source="comment",
            signal_key="reader.consultation.intent",
            signal_value=1,
            text=user_question,
            payload={"article_title": article_title},
        )
        await push_reader_lead_intent(
            user_id=user_id,
            publication_id=article_id,
            intent_type="article_question",
            message=user_question,
            name=(message.from_user.full_name if message.from_user else None),
            payload={"article_title": article_title},
        )

    await state.clear()


# ==================== /settings ====================

async def _show_settings(target: Message, user_id: int, db: AsyncSession) -> None:
    """Show user settings and stats."""
    profile = await get_user_profile(user_id, db)

    if not profile:
        await target.answer(
            "Сначала завершите настройку: /start",
            reply_markup=_build_reader_nav_keyboard(profile_ready=False),
        )
        return

    # Get stats
    stats = await get_user_stats(user_id, db)

    # Format topics
    topic_labels = {
        'gdpr': 'GDPR',
        'ai_law': 'ИИ в праве',
        'crypto': 'Криптовалюты',
        'corporate': 'Корпоративное право',
        'tax': 'Налоги',
        'ip': 'Интеллектуальная собственность'
    }
    topics_text = ', '.join([topic_labels.get(t, t) for t in profile.topics]) if profile.topics else 'не выбраны'

    expertise_labels = {
        'student': 'Студент',
        'lawyer': 'Практикующий юрист',
        'in_house': 'In-house юрист',
        'business': 'Бизнес'
    }

    digest_labels = {
        'daily': 'Ежедневно',
        'twice_week': '2 раза в неделю',
        'weekly': 'Еженедельно',
        'never': 'Не получать'
    }

    await target.answer(
        f"⚙️ <b>Ваши настройки</b>\n\n"
        f"<b>Профиль:</b>\n"
        f"📋 Темы: {topics_text}\n"
        f"🎓 Уровень: {expertise_labels.get(profile.expertise_level, 'не указан')}\n"
        f"📬 Дайджесты: {digest_labels[profile.digest_frequency]}\n\n"
        f"<b>Статистика:</b>\n"
        f"👁 Просмотрено статей: {stats.get('articles_viewed', 0)}\n"
        f"💬 Дано отзывов: {stats.get('feedback_given', 0)}\n"
        f"🔖 Сохранено: {stats.get('articles_saved', 0)}\n"
        f"👍 Понравилось: {stats.get('positive_feedback', 0)}\n\n"
        f"<i>Для изменения настроек используйте /start</i>",
        parse_mode="HTML",
        reply_markup=_build_reader_nav_keyboard(profile_ready=True),
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message, db: AsyncSession):
    """Show user settings and stats."""
    await _show_settings(message, message.from_user.id, db)


# ==================== Lead Magnet Callbacks ====================

@router.callback_query(F.data.startswith("lead_magnet:"), StateFilter(LeadMagnetStates.start_lead_magnet))
async def handle_lead_magnet_start(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Handle lead magnet acceptance/decline."""
    user_id = callback.from_user.id
    action = callback.data.split(":")[1]

    if action == "accept":
        # Create lead profile if doesn't exist
        lead_profile = await get_lead_profile(user_id, db)
        if not lead_profile:
            lead_profile = await create_lead_profile(user_id=user_id, db=db)

        # Start collecting contact info
        await callback.message.edit_text(
            "📧 <b>Шаг 1: Контактная информация</b>\n\n"
            "Укажите ваш email для получения персональных дайджестов:\n\n"
            "<i>Пример: your.email@company.com</i>",
            parse_mode="HTML"
        )

        await state.set_state(LeadMagnetStates.collect_email)

    elif action == "decline":
        await callback.message.edit_text(
            "👋 Понятно! Если передумаете, используйте /lead_magnet\n\n"
            "А пока можете ознакомиться с последними новостями: /today"
        )

    await callback.answer()


@router.message(StateFilter(LeadMagnetStates.collect_email))
async def collect_email(message: Message, state: FSMContext, db: AsyncSession):
    """Collect email address."""
    user_id = message.from_user.id
    email = message.text.strip()

    # Basic email validation
    if "@" not in email or "." not in email:
        await message.answer(
            "❌ Пожалуйста, укажите корректный email адрес.\n\n"
            "Пример: your.email@company.com"
        )
        return

    # Update lead profile
    await update_lead_profile(user_id=user_id, email=email, db=db)

    # Next step: company
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить компанию", callback_data="lead_magnet:skip_company")]
    ])

    await message.answer(
        "🏢 <b>Шаг 2: Компания</b>\n\n"
        "Укажите название вашей компании (опционально):\n\n"
        "<i>Это поможет персонализировать контент под вашу сферу деятельности.</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await state.set_state(LeadMagnetStates.collect_company)


@router.callback_query(F.data == "lead_magnet:skip_company", StateFilter(LeadMagnetStates.collect_company))
async def skip_company(callback: CallbackQuery, state: FSMContext):
    """Skip company collection."""
    await callback.message.edit_text(
        "👤 <b>Шаг 3: Ваша роль</b>\n\n"
        "Укажите вашу должность или роль в компании:\n\n"
        "<i>Примеры: юрист, CEO, IT-директор, консультант</i>",
        parse_mode="HTML"
    )

    await state.set_state(LeadMagnetStates.collect_position)
    await callback.answer()


@router.message(StateFilter(LeadMagnetStates.collect_company))
async def collect_company(message: Message, state: FSMContext, db: AsyncSession):
    """Collect company name."""
    user_id = message.from_user.id
    company = message.text.strip()

    # Update lead profile
    await update_lead_profile(user_id=user_id, company=company, db=db)

    # Next step: position
    await message.answer(
        "👤 <b>Шаг 3: Ваша роль</b>\n\n"
        "Укажите вашу должность или роль в компании:\n\n"
        "<i>Примеры: юрист, CEO, IT-директор, консультант</i>",
        parse_mode="HTML"
    )

    await state.set_state(LeadMagnetStates.collect_position)


@router.message(StateFilter(LeadMagnetStates.collect_position))
async def collect_position(message: Message, state: FSMContext, db: AsyncSession):
    """Collect position/role."""
    user_id = message.from_user.id
    position = message.text.strip()

    # Update lead profile
    await update_lead_profile(user_id=user_id, position=position, db=db)

    # Next step: expertise level
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Новичок в LegalTech", callback_data="expertise:beginner")],
        [InlineKeyboardButton(text="⚖️ Опытный специалист", callback_data="expertise:intermediate")],
        [InlineKeyboardButton(text="🏢 Руководитель/Владелец", callback_data="expertise:expert")],
        [InlineKeyboardButton(text="💼 Бизнес (не юрист)", callback_data="expertise:business_owner")]
    ])

    await message.answer(
        "🎯 <b>Шаг 4: Уровень экспертизы</b>\n\n"
        "Выберите вариант, который лучше всего описывает ваш опыт в LegalTech:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await state.set_state(LeadMagnetStates.choose_expertise)


@router.callback_query(F.data.startswith("expertise:"), StateFilter(LeadMagnetStates.choose_expertise))
async def choose_expertise(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Choose expertise level."""
    user_id = callback.from_user.id
    expertise_level = callback.data.split(":")[1]

    # Update lead profile
    await update_lead_profile(user_id=user_id, expertise_level=expertise_level, db=db)

    # Next step: business focus
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚖️ Юридическая фирма", callback_data="business:law_firm")],
        [InlineKeyboardButton(text="🏢 Корпорация", callback_data="business:corporate")],
        [InlineKeyboardButton(text="🚀 Стартап", callback_data="business:startup")],
        [InlineKeyboardButton(text="💼 Консалтинг", callback_data="business:consulting")],
        [InlineKeyboardButton(text="❓ Другое", callback_data="business:other")]
    ])

    await callback.message.edit_text(
        "🏗️ <b>Шаг 5: Сфера деятельности</b>\n\n"
        "Выберите сферу, в которой работает ваша компания:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await state.set_state(LeadMagnetStates.choose_business_focus)
    await callback.answer()


@router.callback_query(F.data.startswith("business:"), StateFilter(LeadMagnetStates.choose_business_focus))
async def choose_business_focus(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    """Choose business focus."""
    user_id = callback.from_user.id
    business_focus = callback.data.split(":")[1]

    # Update lead profile
    await update_lead_profile(user_id=user_id, business_focus=business_focus, db=db)

    # Calculate lead score
    lead_score = await calculate_lead_score(user_id, db)
    await update_lead_profile(user_id=user_id, lead_score=lead_score, db=db)

    # Mark lead magnet as completed and provide value
    await update_lead_profile(
        user_id=user_id,
        lead_magnet_completed=True,
        digest_requested=True,
        lead_status='qualified',
        db=db
    )

    # Provide personalized digest
    await provide_personalized_digest(callback, db)

    await state.clear()
    await callback.answer()


async def provide_personalized_digest(callback: CallbackQuery, db: AsyncSession):
    """Provide personalized digest to completed lead."""
    user_id = callback.from_user.id

    # Get user preferences
    profile = await get_user_profile(user_id, db)
    lead_profile = await get_lead_profile(user_id, db)

    if not profile or not lead_profile:
        await callback.message.edit_text("❌ Ошибка получения данных профиля")
        return

    # Get personalized feed
    personalized_articles = await get_personalized_feed(user_id, limit=3, db=db)

    if not personalized_articles:
        # Fallback to recent articles
        from app.services.reader_service import get_recent_publications
        personalized_articles = await get_recent_publications(limit=3, db=db)

    # Format digest
    digest_text = (
        "🎉 <b>Поздравляем! Лид-магнит выполнен!</b>\n\n"
        f"📊 Ваш lead score: <b>{lead_profile.lead_score}/100</b>\n\n"
        "📬 <b>Ваш персональный дайджест новостей:</b>\n\n"
    )

    for i, article in enumerate(personalized_articles[:3], 1):
        if article.draft:
            digest_text += f"{i}. <b>{article.draft.title[:60]}{'...' if len(article.draft.title) > 60 else ''}</b>\n"
            digest_text += f"   {article.draft.content[:100]}{'...' if len(article.draft.content) > 100 else ''}\n\n"

    digest_text += (
        "🤖 <b>Теперь вы можете задавать вопросы!</b>\n\n"
        "У вас есть возможность задать <b>3 вопроса</b> по темам:\n"
        "• ИИ в юриспруденции\n"
        "• LegalTech решения\n"
        "• Автоматизация юридических процессов\n\n"
        "Используйте /ask_question для вопросов.\n\n"
        "<i>Каждый вопрос поможет улучшить персонализацию контента.</i>"
    )

    await callback.message.edit_text(
        digest_text,
        parse_mode="HTML"
    )


@router.message(StateFilter(LeadMagnetStates.ask_questions))
async def handle_question(message: Message, state: FSMContext, db: AsyncSession):
    """Handle LegalTech questions from qualified leads."""
    user_id = message.from_user.id
    question = message.text.strip()

    # Get lead profile
    lead_profile = await get_lead_profile(user_id, db)
    if not lead_profile:
        await state.clear()
        await message.answer("❌ Профиль не найден")
        return

    # Check if question is about LegalTech/AI topics
    legaltech_keywords = [
        'ии', 'ai', 'искусственный интеллект', 'нейросеть', 'машинное обучение',
        'legaltech', 'legal tech', 'юридические технологии', 'автоматизация',
        'юрист', 'право', 'закон', 'суд', 'договор', 'комплаенс', 'compliance',
        'контракт', 'документ', 'норматив', 'регулирование'
    ]

    question_lower = question.lower()
    is_legaltech_related = any(keyword in question_lower for keyword in legaltech_keywords)

    if not is_legaltech_related:
        await message.answer(
            "❌ <b>Вопрос не по теме LegalTech</b>\n\n"
            "Я могу отвечать только на вопросы, связанные с:\n"
            "• ИИ в юриспруденции\n"
            "• LegalTech решениями\n"
            "• Автоматизацией юридических процессов\n\n"
            "Попробуйте переформулировать вопрос или используйте /today для новостей.",
            parse_mode="HTML"
        )
        return

    # Increment questions counter
    await increment_questions_asked(user_id, db)
    lead_profile = await get_lead_profile(user_id, db)  # Refresh data

    # Generate answer using AI
    try:
        from app.modules.llm_provider import get_llm_provider
        from app.config import settings

        # Используем дефолтный LLM provider (может быть DeepSeek, OpenAI или Perplexity)
        llm = get_llm_provider(settings.default_llm_provider)

        ai_response = await llm.generate_completion(
            messages=[
                {"role": "system", "content": "Ты - эксперт по LegalTech и ИИ в юриспруденции. Отвечай кратко, по делу и профессионально."},
                {"role": "user", "content": question}
            ],
            max_tokens=500,
            temperature=0.7,
            operation="question_answer",
            db=db
        )

        questions_left = 3 - (lead_profile.questions_asked or 0)

        response_text = (
            f"🤖 <b>Ответ на ваш вопрос:</b>\n\n"
            f"<i>Вопрос:</i> {question}\n\n"
            f"{ai_response}\n\n"
            f"📊 Осталось вопросов: <b>{questions_left}</b>\n\n"
        )

        if questions_left > 0:
            response_text += "Задайте следующий вопрос или используйте /today для новостей."
        else:
            response_text += (
                "🎉 Все вопросы использованы!\n"
                "Продолжайте получать персональные дайджесты."
            )

        await message.answer(response_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        await message.answer(
            "❌ Извините, произошла ошибка при обработке вопроса.\n"
            "Попробуйте позже или используйте /today для новостей."
        )

    # Clear state
    await state.clear()


@router.message(F.text)
async def fallback_text_message(message: Message, db: AsyncSession):
    """Fallback for plain text so the bot never looks silent."""
    text = (message.text or "").strip()
    if not text:
        return

    # Unknown slash-command hint
    if text.startswith("/"):
        await message.answer(
            "Неизвестная команда.\n\n"
            "Доступно: /start, /today, /weekly, /search, /saved, /settings, /lead_magnet",
            reply_markup=_build_reader_nav_keyboard(profile_ready=True),
        )
        return

    user_id = message.from_user.id
    profile = await get_user_profile(user_id, db)
    if not profile:
        await message.answer(
            "Сначала запустите /start, чтобы настроить профиль.\n"
            "После этого смогу подобрать релевантные новости.",
            reply_markup=_build_reader_nav_keyboard(profile_ready=False),
        )
        return

    results = await search_publications(text, user_id=user_id, limit=3, db=db)
    if not results:
        await message.answer(
            "По этому запросу пока ничего не найдено.\n"
            "Попробуйте /today или /search с другим запросом.",
            reply_markup=_build_reader_nav_keyboard(profile_ready=True),
        )
        return

    await message.answer(
        f"Найдено {len(results)} статей по запросу: <b>{text}</b>",
        parse_mode="HTML",
        reply_markup=_build_reader_nav_keyboard(profile_ready=True),
    )
    for i, article in enumerate(results, 1):
        await message.answer(
            format_article_message(article, index=i),
            parse_mode="HTML",
            reply_markup=get_article_keyboard(str(article.id)),
        )
# ==================== Deep-Link Helpers ====================

_START_POST_PAYLOAD_RE = re.compile(r"^(?:post_|p_)?(?P<post_id>[0-9a-fA-F-]{36})$")


def _extract_start_post_id(text: str | None) -> str | None:
    parts = (text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    payload = parts[1].strip()
    if not payload:
        return None
    match = _START_POST_PAYLOAD_RE.match(payload)
    if not match:
        return None
    return match.group("post_id")
