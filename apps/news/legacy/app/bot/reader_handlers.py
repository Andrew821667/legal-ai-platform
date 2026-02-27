"""
Reader Bot Handlers.

Handles user interactions:
- Onboarding flow (/start)
- Commands (/today, /search, /saved, /settings)
- Feedback buttons (like/dislike)
- Save/unsave articles
"""

from typing import Optional
from uuid import UUID
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import structlog

logger = structlog.get_logger()

from app.services.reader_service import (
    get_user_profile,
    create_user_profile,
    update_user_profile,
    get_personalized_feed,
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
    calculate_lead_score
)
from app.models.reader_publications import ReaderPublication


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

    # Feedback buttons
    keyboard.append([
        InlineKeyboardButton(text="👍 Полезно", callback_data=f"feedback:like:{publication_id}"),
        InlineKeyboardButton(text="👎 Не интересно", callback_data=f"feedback:dislike:{publication_id}"),
    ])

    # Save button
    keyboard.append([
        InlineKeyboardButton(text=save_text, callback_data=save_action),
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ==================== /start - Onboarding ====================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, db: AsyncSession):
    """Handle /start command - onboarding for new users."""
    user_id = message.from_user.id
    profile = await get_user_profile(user_id, db)

    if profile:
        # Existing user - show main menu
        lead_profile = await get_lead_profile(user_id, db)
        saved_articles = await _safe_get_saved_articles(user_id, db=db)
        lead_magnet_text = ""
        if lead_profile and lead_profile.lead_magnet_completed:
            lead_magnet_text = "✅ Лид-магнит выполнен"
        else:
            lead_magnet_text = "/lead_magnet - 🎯 Получить персональный дайджест"

        await message.answer(
            f"С возвращением, {message.from_user.first_name}! 👋\n\n"
            f"Что хотите сделать?\n\n"
            f"/today - Персональные новости за сегодня\n"
            f"/search - Поиск по архиву\n"
            f"/saved - Сохранённые статьи ({len(saved_articles)})\n"
            f"/settings - Настройки профиля\n"
            f"{lead_magnet_text}"
        )
    else:
        # New user - start onboarding
        await start_onboarding(message, state, db)


@router.message(Command("lead_magnet"))
async def cmd_lead_magnet(message: Message, state: FSMContext, db: AsyncSession):
    """Handle /lead_magnet command - start lead magnet flow."""
    user_id = message.from_user.id

    # Check if user completed onboarding
    profile = await get_user_profile(user_id, db)
    if not profile:
        await message.answer(
            "❌ Сначала пройдите онбординг!\n"
            "Используйте /start для настройки профиля."
        )
        return

    # Check if lead magnet already completed
    lead_profile = await get_lead_profile(user_id, db)
    if lead_profile and lead_profile.lead_magnet_completed:
        await message.answer(
            "✅ Вы уже прошли лид-магнит!\n\n"
            "Теперь у вас есть доступ к:\n"
            "• Персональным дайджестам новостей\n"
            "• Возможности задавать вопросы по LegalTech\n"
            "• Специальным предложениям\n\n"
            "Используйте /today для получения новостей."
        )
        return

    # Start lead magnet flow
    await start_lead_magnet(message, state, db)


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
            "и возможности задавать вопросы."
        )
        return

    # Check questions limit
    if lead_profile.questions_asked >= 3:
        await message.answer(
            "📊 <b>Лимит вопросов исчерпан!</b>\n\n"
            "Вы уже задали 3 вопроса. Спасибо за участие!\n\n"
            "Продолжайте получать персональные дайджесты с /today",
            parse_mode="HTML"
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
        parse_mode="HTML"
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
        parse_mode="HTML"
    )

    await callback.answer("✅ Профиль настроен!")


# ==================== /today - Personalized Feed ====================

@router.message(Command("today"))
async def cmd_today(message: Message, db: AsyncSession):
    """Show personalized feed for today."""
    user_id = message.from_user.id
    profile = await get_user_profile(user_id, db)

    if not profile:
        await message.answer(
            "Сначала завершите настройку профиля: /start"
        )
        return

    # Update last active
    await update_last_active(user_id, db)

    # Get personalized feed
    articles = await get_personalized_feed(user_id, limit=5, db=db)

    if not articles:
        await message.answer(
            "📭 Сегодня пока нет новых статей по вашим темам.\n\n"
            "Попробуйте:\n"
            "/search - Поиск по архиву\n"
            "/saved - Ваши сохранённые статьи"
        )
        return

    await message.answer(
        f"📬 <b>Ваши персональные новости за сегодня:</b>\n\n"
        f"Найдено {len(articles)} статей по вашим темам.",
        parse_mode="HTML"
    )

    # Send each article with keyboard
    for i, article in enumerate(articles, 1):
        text = format_article_message(article, index=i)
        keyboard = get_article_keyboard(str(article.id))

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )


# ==================== /search - Search ====================

@router.message(Command("search"))
async def cmd_search(message: Message, db: AsyncSession):
    """Search articles."""
    query = message.text.replace("/search", "").strip()

    if not query:
        await message.answer(
            "🔍 <b>Поиск по архиву</b>\n\n"
            "Введите поисковый запрос:\n"
            "Например: <i>GDPR</i>, <i>искусственный интеллект</i>, <i>налоги</i>",
            parse_mode="HTML",
            reply_markup=ForceReply(input_field_placeholder="Введите тему для поиска...")
        )
        return

    # Search
    user_id = message.from_user.id
    results = await search_publications(query, user_id=user_id, limit=10, db=db)

    if not results:
        await message.answer(
            f"По запросу '<b>{query}</b>' ничего не найдено 😔\n\n"
            "Попробуйте другой запрос или используйте /today",
            parse_mode="HTML"
        )
        return

    # Show results
    await message.answer(
        f"🔍 Найдено <b>{len(results)}</b> статей по запросу '<b>{query}</b>':",
        parse_mode="HTML"
    )

    for i, article in enumerate(results, 1):
        text = format_article_message(article, index=i)
        keyboard = get_article_keyboard(str(article.id))

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )


@router.message(F.reply_to_message, F.text)
async def handle_search_reply(message: Message, db: AsyncSession):
    """Handle reply to search prompt (ForceReply)."""
    # Check if replying to bot's search message
    if (message.reply_to_message and
        message.reply_to_message.from_user.is_bot and
        "Поиск по архиву" in message.reply_to_message.text):

        query = message.text.strip()
        user_id = message.from_user.id

        # Perform search
        results = await search_publications(query, user_id=user_id, limit=10, db=db)

        if not results:
            await message.answer(
                f"По запросу '<b>{query}</b>' ничего не найдено 😔\n\n"
                "Попробуйте другой запрос или используйте /today",
                parse_mode="HTML"
            )
            return

        # Show results
        await message.answer(
            f"🔍 Найдено <b>{len(results)}</b> статей по запросу '<b>{query}</b>':",
            parse_mode="HTML"
        )

        for i, article in enumerate(results, 1):
            text = format_article_message(article, index=i)
            keyboard = get_article_keyboard(str(article.id))

            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=keyboard
            )


# ==================== /saved - Saved Articles ====================

@router.message(Command("saved"))
async def cmd_saved(message: Message, db: AsyncSession):
    """Show saved articles."""
    user_id = message.from_user.id
    saved = await _safe_get_saved_articles(user_id, db=db, limit=20)

    if not saved:
        await message.answer(
            "🔖 У вас пока нет сохранённых статей.\n\n"
            "Используйте кнопку '🔖 Сохранить' под статьёй чтобы добавить в избранное."
        )
        return

    await message.answer(
        f"🔖 <b>Ваши сохранённые статьи</b> ({len(saved)}):",
        parse_mode="HTML"
    )

    for i, article in enumerate(saved, 1):
        text = format_article_message(article, index=i)
        keyboard = get_article_keyboard(str(article.id), user_saved=True)

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )


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


# ==================== /settings ====================

@router.message(Command("settings"))
async def cmd_settings(message: Message, db: AsyncSession):
    """Show user settings and stats."""
    user_id = message.from_user.id
    profile = await get_user_profile(user_id, db)

    if not profile:
        await message.answer("Сначала завершите настройку: /start")
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

    await message.answer(
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
        parse_mode="HTML"
    )


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
            "Доступно: /start, /today, /search, /saved, /settings, /lead_magnet"
        )
        return

    user_id = message.from_user.id
    profile = await get_user_profile(user_id, db)
    if not profile:
        await message.answer(
            "Сначала запустите /start, чтобы настроить профиль.\n"
            "После этого смогу подобрать релевантные новости."
        )
        return

    results = await search_publications(text, user_id=user_id, limit=3, db=db)
    if not results:
        await message.answer(
            "По этому запросу пока ничего не найдено.\n"
            "Попробуйте /today или /search с другим запросом."
        )
        return

    await message.answer(
        f"Найдено {len(results)} статей по запросу: <b>{text}</b>",
        parse_mode="HTML",
    )
    for i, article in enumerate(results, 1):
        await message.answer(
            format_article_message(article, index=i),
            parse_mode="HTML",
            reply_markup=get_article_keyboard(str(article.id)),
        )
