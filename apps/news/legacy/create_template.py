#!/usr/bin/env python3
"""
Скрипт для создания базового шаблона изображения для публикаций.
Создает профессиональный градиентный фон 1200x630 для Telegram постов.
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_base_template():
    """Создать базовое изображение-шаблон для публикаций."""

    # Размеры изображения
    width = 1200
    height = 630

    # Создаем изображение
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)

    # Профессиональная цветовая схема (темно-синий к фиолетовому)
    color_top = (25, 42, 86)      # Темно-синий
    color_middle = (88, 57, 131)  # Фиолетовый
    color_bottom = (100, 149, 237) # Cornflower blue

    # Создаем трехточечный градиент
    for y in range(height):
        if y < height // 2:
            # Верхняя половина: от темно-синего к фиолетовому
            ratio = y / (height // 2)
            r = int(color_top[0] * (1 - ratio) + color_middle[0] * ratio)
            g = int(color_top[1] * (1 - ratio) + color_middle[1] * ratio)
            b = int(color_top[2] * (1 - ratio) + color_middle[2] * ratio)
        else:
            # Нижняя половина: от фиолетового к синему
            ratio = (y - height // 2) / (height // 2)
            r = int(color_middle[0] * (1 - ratio) + color_bottom[0] * ratio)
            g = int(color_middle[1] * (1 - ratio) + color_bottom[1] * ratio)
            b = int(color_middle[2] * (1 - ratio) + color_bottom[2] * ratio)

        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Добавляем легкий виньет эффект (затемнение по краям)
    vignette = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    vignette_draw = ImageDraw.Draw(vignette)

    # Рисуем полупрозрачные прямоугольники по краям
    for i in range(100):
        alpha = int(i * 0.8)  # Градиент прозрачности
        vignette_draw.rectangle(
            [i, i, width - i, height - i],
            outline=(0, 0, 0, alpha)
        )

    # Применяем виньет
    img.paste(vignette, (0, 0), vignette)

    # Сохраняем
    output_path = 'templates/base_template.jpg'
    os.makedirs('templates', exist_ok=True)
    img.save(output_path, 'JPEG', quality=95)

    print(f"✅ Базовый шаблон создан: {output_path}")
    print(f"📐 Размер: {width}x{height}")
    print(f"🎨 Цветовая схема: Темно-синий → Фиолетовый → Светло-синий")
    print("\nТеперь вы можете:")
    print("1. Использовать этот шаблон как есть")
    print("2. Заменить его своим изображением с тем же именем")
    print("3. Указать другой путь в .env: MEDIA_TEMPLATE_IMAGE_PATH=...")

if __name__ == "__main__":
    create_base_template()
