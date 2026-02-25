"""
Media Factory Module
Генерация обложек и медиа контента для постов.

Функционал:
1. Генератор обложек с помощью PIL (3 шаблона)
2. Автоматический перенос строк для длинных заголовков
3. Водяной знак канала
4. DALL-E генерация (опционально для Phase 2+)
"""

import os
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import PostDraft, MediaFile
import structlog

logger = structlog.get_logger()


# Цветовые схемы для разных типов новостей
COLOR_SCHEMES = {
    'serious': {
        'background': (25, 42, 86),  # Темно-синий
        'text': (255, 255, 255),  # Белый
        'accent': (100, 149, 237),  # Cornflower blue
    },
    'light': {
        'background': (88, 57, 131),  # Фиолетовый
        'text': (255, 255, 255),  # Белый
        'accent': (186, 104, 200),  # Medium orchid
    },
    'urgent': {
        'background': (139, 0, 0),  # Темно-красный
        'text': (255, 255, 255),  # Белый
        'accent': (255, 99, 71),  # Tomato
    }
}


class ImageGenerator:
    """Генератор изображений для постов."""

    def __init__(self):
        """Инициализация генератора."""
        self.width = settings.media_image_width
        self.height = settings.media_image_height
        self.output_dir = Path(settings.media_output_dir)

        # Создаем директорию для медиа если не существует
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Загружаем шрифты с поддержкой кириллицы
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]

        font_loaded = False
        for font_path in font_paths:
            try:
                if os.path.exists(font_path):
                    self.font_title = ImageFont.truetype(font_path, settings.media_font_size_title)
                    self.font_date = ImageFont.truetype(font_path.replace("-Bold", ""), settings.media_font_size_date)
                    self.font_watermark = ImageFont.truetype(font_path.replace("-Bold", ""), 20)
                    logger.info("fonts_loaded_successfully", font_path=font_path)
                    font_loaded = True
                    break
            except Exception as e:
                logger.debug("font_load_attempt_failed", font_path=font_path, error=str(e))
                continue

        if not font_loaded:
            logger.error("no_fonts_found", message="Fallback to default - cyrillic may not work!")
            # ВАЖНО: load_default() не поддерживает кириллицу!
            # Используем минимальный PIL шрифт
            self.font_title = ImageFont.load_default()
            self.font_date = ImageFont.load_default()
            self.font_watermark = ImageFont.load_default()

    def _select_template(self, title: str, confidence: float) -> str:
        """
        Выбрать шаблон на основе заголовка и оценки.

        Args:
            title: Заголовок новости
            confidence: Оценка уверенности

        Returns:
            Имя шаблона ('serious', 'light', 'urgent')
        """
        title_lower = title.lower()

        # Срочные новости (высокий приоритет)
        urgent_keywords = ['срочно', 'breaking', 'суд', 'запрет', 'штраф', 'санкции']
        if any(keyword in title_lower for keyword in urgent_keywords):
            return 'urgent'

        # Легкие темы
        light_keywords = ['стартап', 'новый', 'запуск', 'презентац', 'анонс']
        if any(keyword in title_lower for keyword in light_keywords) and confidence < 0.7:
            return 'light'

        # По умолчанию серьезный стиль
        return 'serious'

    def _wrap_text(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int
    ) -> list:
        """
        Перенос текста по словам для заданной ширины.

        Args:
            text: Текст для переноса
            font: Шрифт
            max_width: Максимальная ширина

        Returns:
            Список строк
        """
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            # Проверяем ширину с новым словом
            test_line = ' '.join(current_line + [word])
            bbox = font.getbbox(test_line)
            width = bbox[2] - bbox[0]

            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    # Слово слишком длинное - разбиваем его
                    lines.append(word)

        if current_line:
            lines.append(' '.join(current_line))

        return lines

    def _draw_text_with_shadow(
        self,
        draw: ImageDraw.Draw,
        position: Tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont,
        fill: Tuple[int, int, int],
        shadow_offset: int = 2
    ):
        """
        Нарисовать текст с тенью для лучшей читаемости.

        Args:
            draw: Объект для рисования
            position: Позиция (x, y)
            text: Текст
            font: Шрифт
            fill: Цвет текста
            shadow_offset: Смещение тени
        """
        x, y = position

        # Рисуем тень (черный с прозрачностью)
        draw.text(
            (x + shadow_offset, y + shadow_offset),
            text,
            font=font,
            fill=(0, 0, 0)
        )

        # Рисуем основной текст
        draw.text((x, y), text, font=font, fill=fill)

    def generate_cover(
        self,
        title: str,
        template: Optional[str] = None,
        confidence: float = 0.5
    ) -> str:
        """
        Сгенерировать обложку для поста.

        Args:
            title: Заголовок новости
            template: Имя шаблона (или auto-select)
            confidence: Оценка уверенности

        Returns:
            Путь к сохраненному изображению
        """
        logger.info(
            "generating_cover",
            title=title[:50]
        )

        # Пытаемся загрузить базовое изображение
        use_template = False
        try:
            if os.path.exists(settings.media_template_image_path):
                img = Image.open(settings.media_template_image_path)
                # Изменяем размер если нужно
                if img.size != (self.width, self.height):
                    img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
                logger.info("base_template_loaded", path=settings.media_template_image_path)
                use_template = True
            else:
                raise FileNotFoundError("Template image not found")
        except Exception as e:
            # Fallback: создаем простой градиентный фон
            logger.warning("base_template_load_failed", error=str(e), fallback="gradient")

            # Выбираем цветовую схему
            if template is None or template not in COLOR_SCHEMES:
                template = self._select_template(title, confidence)
            colors = COLOR_SCHEMES[template]

            # Создаем изображение с градиентом
            img = Image.new('RGB', (self.width, self.height), colors['background'])
            draw_gradient = ImageDraw.Draw(img)

            for y in range(self.height):
                ratio = y / self.height
                r = int(colors['background'][0] * (1 - ratio) + colors['accent'][0] * ratio)
                g = int(colors['background'][1] * (1 - ratio) + colors['accent'][1] * ratio)
                b = int(colors['background'][2] * (1 - ratio) + colors['accent'][2] * ratio)
                draw_gradient.line([(0, y), (self.width, y)], fill=(r, g, b))

        # Создаем объект для рисования
        draw = ImageDraw.Draw(img)

        # Цвет текста (белый для базового шаблона, из схемы для градиента)
        text_color = (255, 255, 255) if use_template else colors['text']

        # Переносим заголовок
        padding = 50
        max_text_width = self.width - (padding * 2)
        title_lines = self._wrap_text(title, self.font_title, max_text_width)

        # Ограничиваем количество строк (максимум 4)
        if len(title_lines) > 4:
            title_lines = title_lines[:3]
            title_lines.append('...')

        # Вычисляем позицию для центрирования
        line_height = settings.media_font_size_title + 10
        total_text_height = len(title_lines) * line_height
        start_y = (self.height - total_text_height) // 2

        # Рисуем заголовок с тенью
        current_y = start_y
        for line in title_lines:
            # Центрируем каждую строку
            bbox = self.font_title.getbbox(line)
            text_width = bbox[2] - bbox[0]
            x = (self.width - text_width) // 2

            self._draw_text_with_shadow(
                draw,
                (x, current_y),
                line,
                self.font_title,
                text_color
            )

            current_y += line_height

        # Добавляем дату в правом верхнем углу
        date_text = datetime.now().strftime("%d.%m.%Y")
        bbox = self.font_date.getbbox(date_text)
        date_width = bbox[2] - bbox[0]

        self._draw_text_with_shadow(
            draw,
            (self.width - date_width - 30, 30),
            date_text,
            self.font_date,
            text_color
        )

        # Добавляем водяной знак (если включен)
        if settings.media_watermark_enabled:
            watermark_text = "AI Legal News"
            bbox = self.font_watermark.getbbox(watermark_text)
            wm_width = bbox[2] - bbox[0]

            # Цвет водяного знака (светло-серый для шаблона, accent для градиента)
            wm_color = (200, 200, 200) if use_template else colors['accent']

            self._draw_text_with_shadow(
                draw,
                (self.width - wm_width - 30, self.height - 50),
                watermark_text,
                self.font_watermark,
                wm_color
            )

        # Сохраняем изображение
        cover_type = "template" if use_template else template
        filename = f"cover_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{cover_type}.png"
        filepath = self.output_dir / filename

        img.save(filepath, 'PNG', quality=95)

        logger.info(
            "cover_generated",
            filepath=str(filepath),
            template=template
        )

        return str(filepath)


class MediaFactory:
    """Фабрика медиа контента."""

    def __init__(self, db_session: AsyncSession):
        """
        Инициализация Media Factory.

        Args:
            db_session: Асинхронная сессия базы данных
        """
        self.db = db_session
        self.image_generator = ImageGenerator()

        # Инициализируем OpenAI клиента для DALL-E если включено
        if settings.dalle_enabled:
            from openai import AsyncOpenAI
            self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        else:
            self.openai_client = None

    async def generate_dalle_image(
        self,
        title: str,
        content: str
    ) -> Optional[str]:
        """
        Сгенерировать изображение через DALL-E.

        Args:
            title: Заголовок новости
            content: Контент новости

        Returns:
            Путь к сохраненному изображению или None
        """
        if not settings.dalle_enabled or not self.openai_client:
            return None

        try:
            # Формируем промпт для DALL-E на основе контента
            # Извлекаем ключевые слова из заголовка и контента
            prompt_base = f"{title}. {content[:200]}"

            # Создаём тематический промпт для юридической AI тематики
            dalle_prompt = f"""Professional business illustration for legal tech news article: {title}

Style: Modern, professional, minimalist
Theme: AI and legal technology, business innovation
Color scheme: Corporate blues, teals, professional tones
Mood: Serious, trustworthy, forward-thinking
Elements: Abstract representation of AI, legal symbols, modern technology
Avoid: Text, logos, realistic faces, cluttered details

Focus on clean, magazine-quality illustration that conveys innovation in legal technology."""

            logger.info(
                "generating_dalle_image",
                title=title[:50],
                prompt_length=len(dalle_prompt)
            )

            # Генерируем изображение через DALL-E
            response = await self.openai_client.images.generate(
                model=settings.dalle_model,
                prompt=dalle_prompt,
                size=settings.dalle_size,
                quality=settings.dalle_quality,
                n=1
            )

            # Получаем URL изображения
            image_url = response.data[0].url

            # Скачиваем изображение
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        image_data = await resp.read()

                        # Сохраняем изображение
                        filename = f"dalle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        filepath = self.image_generator.output_dir / filename

                        with open(filepath, 'wb') as f:
                            f.write(image_data)

                        logger.info(
                            "dalle_image_generated",
                            filepath=str(filepath),
                            url=image_url
                        )

                        return str(filepath)
                    else:
                        logger.error(
                            "dalle_image_download_failed",
                            status=resp.status
                        )
                        return None

        except Exception as e:
            logger.error(
                "dalle_generation_error",
                error=str(e),
                title=title[:50]
            )
            return None

    async def create_cover_for_draft(
        self,
        draft: PostDraft
    ) -> Optional[str]:
        """
        Создать обложку для драфта.

        Args:
            draft: Драфт поста

        Returns:
            Путь к созданному изображению или None
        """
        try:
            cover_path = None

            # Пытаемся сгенерировать через DALL-E если включено
            if settings.dalle_enabled:
                cover_path = await self.generate_dalle_image(
                    title=draft.title,
                    content=draft.content
                )

                if cover_path:
                    logger.info(
                        "dalle_cover_created",
                        draft_id=draft.id,
                        cover_path=cover_path
                    )

            # Fallback на обычную графическую обложку если DALL-E не сработал
            if not cover_path:
                cover_path = self.image_generator.generate_cover(
                    title=draft.title,
                    confidence=draft.confidence_score or 0.5
                )
                logger.info(
                    "fallback_cover_created",
                    draft_id=draft.id,
                    cover_path=cover_path
                )

            # Сохраняем путь в драфте
            draft.image_path = cover_path

            # Создаем запись в media_files
            media_file = MediaFile(
                draft_id=draft.id,
                file_type='image',
                file_path=cover_path
            )
            self.db.add(media_file)

            await self.db.commit()

            logger.info(
                "cover_created_for_draft",
                draft_id=draft.id,
                cover_path=cover_path
            )

            return cover_path

        except Exception as e:
            logger.error(
                "cover_creation_error",
                draft_id=draft.id,
                error=str(e)
            )
            return None

    async def create_covers_for_pending_drafts(self) -> int:
        """
        Создать обложки для всех драфтов без изображений.

        Returns:
            Количество созданных обложек
        """
        from sqlalchemy import select

        # Получаем драфты без изображений
        result = await self.db.execute(
            select(PostDraft).where(
                PostDraft.status == 'pending_review',
                PostDraft.image_path.is_(None)
            )
        )
        drafts = list(result.scalars().all())

        created_count = 0

        for draft in drafts:
            cover_path = await self.create_cover_for_draft(draft)
            if cover_path:
                created_count += 1

        logger.info(
            "covers_creation_complete",
            total_drafts=len(drafts),
            created=created_count
        )

        return created_count


async def create_media_for_drafts(db_session: AsyncSession) -> int:
    """
    Удобная функция для создания медиа для драфтов.

    Args:
        db_session: Асинхронная сессия БД

    Returns:
        Количество созданных медиа файлов
    """
    factory = MediaFactory(db_session)
    return await factory.create_covers_for_pending_drafts()
