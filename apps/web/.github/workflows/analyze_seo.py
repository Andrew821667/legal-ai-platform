#!/usr/bin/env python3
"""SEO Analysis Script for GitHub Actions - Fixed to work with SPA on Vercel"""

import json
import sys
from datetime import datetime
from dataclasses import asdict, is_dataclass
import asyncio

sys.path.insert(0, 'seo-tools')

SITE_URL = 'https://legalaipro.ru'


def dataclass_to_dict(obj):
    """Конвертирует dataclass объекты в словари для JSON сериализации"""
    if obj is None:
        return None
    elif is_dataclass(obj) and not isinstance(obj, type):
        # Конвертируем dataclass в dict, затем рекурсивно обрабатываем значения
        result = {}
        for field_name, field_value in asdict(obj).items():
            result[field_name] = dataclass_to_dict(field_value)
        return result
    elif isinstance(obj, dict):
        return {k: dataclass_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [dataclass_to_dict(item) for item in obj]
    elif isinstance(obj, (int, float, str, bool)):
        return obj
    elif hasattr(obj, '__float__'):
        # Для numpy типов и подобных
        return float(obj)
    elif hasattr(obj, '__int__'):
        return int(obj)
    else:
        # Для всех остальных случаев пытаемся вернуть как есть
        return obj

async def fetch_page_with_playwright(url):
    """Загружает страницу с помощью Playwright для рендеринга SPA"""
    from playwright.async_api import async_playwright

    print('📥 Запускаю браузер для загрузки SPA...')

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox'
            ]
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='ru-RU',
            timezone_id='Europe/Moscow',
            extra_http_headers={
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            }
        )

        # Скрываем признаки автоматизации
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US', 'en']});
        """)

        page = await context.new_page()

        print(f'🌐 Загружаю {url}...')
        response = await page.goto(url, wait_until='networkidle', timeout=60000)
        status_code = response.status

        print(f'⏳ Жду полного рендеринга React...')
        # Ждем рендеринга контента
        await page.wait_for_timeout(3000)

        # Получаем полный HTML после рендеринга
        html_content = await page.content()

        await browser.close()

        return html_content, status_code


def main():
    try:
        print('🔍 Импортирую модули...')
        from seo_ai_models.models.seo_advisor.advisor import SEOAdvisor
        from seo_ai_models.parsers.extractors.content_extractor import ContentExtractor
        from seo_ai_models.parsers.extractors.meta_extractor import MetaExtractor

        print('✅ Модули импортированы успешно')

        # Инициализация (без ParsingPipeline из-за бага)
        advisor = SEOAdvisor()
        content_extractor = ContentExtractor()
        meta_extractor = MetaExtractor()

        print(f'🌐 Анализирую сайт: {SITE_URL}')

        # Парсинг SPA страницы через Playwright
        html_content, status_code = asyncio.run(fetch_page_with_playwright(SITE_URL))

        print(f'\n📊 Результат парсинга:')
        print(f'  Status code: {status_code}')
        print(f'  Content length: {len(html_content)} символов')

        if status_code != 200:
            print(f'  ❌ Неожиданный status code: {status_code}')
            create_error_report({'error': f'HTTP {status_code}'})
            sys.exit(1)

        print(f'  ✅ Страница успешно загружена и отрендерена')

        # Извлечение контента через seo-ai-models экстракторы
        print('🔬 Извлекаю контент и метаданные...')
        content_analysis = content_extractor.extract_content(html_content, SITE_URL)
        meta_analysis = meta_extractor.extract_meta_information(html_content, SITE_URL)

        # Формируем контент для SEO анализа
        content_text = content_analysis.get('content', {}).get('all_text', '')
        title = meta_analysis.get('meta_tags', {}).get('title', '')
        description = meta_analysis.get('meta_tags', {}).get('description', '')

        print(f'\n📝 Найденный контент:')
        print(f'  Title: {title[:80]}...' if len(title) > 80 else f'  Title: {title}')
        print(f'  Description: {description[:80]}...' if len(description) > 80 else f'  Description: {description}')
        print(f'  Content length: {len(content_text)} символов')
        print(f'  Word count: {len(content_text.split())} слов')

        # SEO анализ через advisor
        print(f'\n🔬 Запускаю SEO анализ...')

        # Извлекаем ключевые слова из title и content
        target_keywords = []
        if title:
            # Простая токенизация title
            target_keywords.extend([w.lower() for w in title.split() if len(w) > 3])

        # Если нет ключевых слов, используем общие для юридического AI
        if not target_keywords:
            target_keywords = ['legal', 'ai', 'юридический', 'искусственный интеллект', 'автоматизация']

        print(f'  Целевые ключевые слова: {", ".join(target_keywords[:5])}...')

        # Формируем markdown-контент для advisor
        markdown_content = f"# {title}\n\n{content_text}"
        seo_report = advisor.analyze_content(markdown_content, target_keywords)

        # seo_report это SEOAnalysisReport dataclass, нужно извлечь данные
        predicted_position = float(seo_report.predicted_position) if seo_report.predicted_position else 50.0
        overall_score = max(0, min(100, int((1 - (predicted_position / 100)) * 100)))  # Конвертируем позицию в score

        print(f'  Predicted Position: {predicted_position:.1f}')
        print(f'  SEO Score: {overall_score}/100')

        # Сборка результатов с конвертацией dataclass в dict
        results = {
            'timestamp': datetime.now().isoformat(),
            'site_url': SITE_URL,
            'overall_score': overall_score,
            'predicted_position': predicted_position,
            'page_metadata': {
                'title': title,
                'title_length': len(title),
                'description': description,
                'description_length': len(description),
                'word_count': len(content_text.split()),
                'content_length': len(content_text),
                'h1_count': len(content_analysis.get('headings', {}).get('h1', [])),
                'h2_count': len(content_analysis.get('headings', {}).get('h2', [])),
                'internal_links': len(meta_analysis.get('links', {}).get('internal', [])),
                'external_links': len(meta_analysis.get('links', {}).get('external', []))
            },
            'seo_analysis': {
                'predicted_position': predicted_position,
                'content_metrics': dataclass_to_dict(seo_report.content_metrics),
                'keyword_analysis': dataclass_to_dict(seo_report.keyword_analysis),
                'feature_scores': dataclass_to_dict(seo_report.feature_scores),
                'recommendations': dataclass_to_dict(seo_report.recommendations) if hasattr(seo_report, 'recommendations') else {},
                'priorities': dataclass_to_dict(seo_report.priorities) if hasattr(seo_report, 'priorities') else []
            },
            'raw_page_data': {
                'status_code': status_code,
                'headings': content_analysis.get('headings', {})
            }
        }

        # Сохранение JSON отчета
        report_file = f'seo-reports/report-{datetime.now().strftime("%Y-%m-%d")}.json'

        print(f'\n💾 Сохраняю JSON отчет...')
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f'✅ JSON отчет сохранен: {report_file}')
        except TypeError as e:
            print(f'❌ Ошибка сериализации JSON: {e}')
            print(f'Тип проблемного объекта: {type(e).__name__}')
            # Пытаемся сохранить с default handler
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2, default=str)
            print(f'⚠️ JSON отчет сохранен с конвертацией в строки: {report_file}')

        # Создание Markdown summary
        create_markdown_summary(results)

        print(f'\n✅ Анализ завершен! Общий score: {results["overall_score"]}/100')

    except Exception as e:
        print(f'\n❌ Критическая ошибка: {e}')
        import traceback
        traceback.print_exc()

        # Создаем error report
        create_error_report({'error': str(e), 'traceback': traceback.format_exc()})
        sys.exit(1)


def create_markdown_summary(results):
    """Создание Markdown отчета"""
    with open('seo-reports/SUMMARY.md', 'w', encoding='utf-8') as f:
        f.write('# 🔍 SEO Analysis Report\n\n')
        f.write(f'**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
        f.write(f'**Site:** {results["site_url"]}\n\n')
        f.write(f'**Overall Score:** {results["overall_score"]}/100\n\n')

        # Статус
        score = results["overall_score"]
        if score >= 80:
            f.write('**Status:** ✅ Отлично\n\n')
        elif score >= 60:
            f.write('**Status:** ⚠️ Хорошо, но есть улучшения\n\n')
        else:
            f.write('**Status:** ❌ Требуется оптимизация\n\n')

        # Метаданные страницы
        meta = results.get('page_metadata', {})
        f.write('## 📊 Метаданные страницы\n\n')
        f.write(f'- **Title:** {meta.get("title", "N/A")} ({meta.get("title_length", 0)} символов)\n')
        f.write(f'- **Meta Description:** {"✅ Есть" if meta.get("description") else "❌ Нет"} ({meta.get("description_length", 0)} символов)\n')
        f.write(f'- **H1:** {meta.get("h1_count", 0)} шт\n')
        f.write(f'- **H2:** {meta.get("h2_count", 0)} шт\n')
        f.write(f'- **Слов:** {meta.get("word_count", 0)}\n')
        f.write(f'- **Внутренних ссылок:** {meta.get("internal_links", 0)}\n')
        f.write(f'- **Внешних ссылок:** {meta.get("external_links", 0)}\n\n')

        # Рекомендации
        seo_analysis = results.get('seo_analysis', {})
        if isinstance(seo_analysis, dict):
            recommendations_dict = seo_analysis.get('recommendations', {})

            # recommendations может быть Dict[str, List[str]] по категориям
            all_recommendations = []
            if isinstance(recommendations_dict, dict):
                for category, recs in recommendations_dict.items():
                    if isinstance(recs, list):
                        all_recommendations.extend(recs)

            if all_recommendations:
                f.write('## 🎯 Рекомендации по улучшению\n\n')
                for i, rec in enumerate(all_recommendations[:10], 1):
                    f.write(f'{i}. {rec}\n')
                f.write('\n')

        f.write('\n---\n\n')
        f.write('*Powered by SEO AI Models*\n')

    print(f'📄 Markdown summary создан: seo-reports/SUMMARY.md')


def create_error_report(error_data):
    """Создание error report при ошибке"""
    try:
        with open('seo-reports/ERROR.md', 'w', encoding='utf-8') as f:
            f.write('# ❌ SEO Analysis Error\n\n')
            f.write(f'**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
            f.write(f'**Site:** {SITE_URL}\n\n')
            f.write('## Error Details\n\n')
            f.write(f'```\n{error_data.get("error", "Unknown error")}\n```\n\n')

            if 'traceback' in error_data:
                f.write('## Traceback\n\n')
                f.write(f'```\n{error_data["traceback"]}\n```\n')

        print('📝 Error report создан: seo-reports/ERROR.md')
    except Exception as e:
        print(f'⚠️ Не удалось создать error report: {e}')


if __name__ == "__main__":
    main()
