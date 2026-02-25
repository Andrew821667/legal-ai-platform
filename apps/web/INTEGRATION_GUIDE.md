# Практический гайд интеграции SEO AI Models в Legal AI

**Дата:** 11 ноября 2025  
**Статус:** Готово к реализации

---

## Быстрый старт (15 минут)

### 1. Установка зависимостей

```bash
# Перейти в директорию проекта
cd /Users/andrew/legal-ai-bot/website

# Создать виртуальное окружение (если еще нет)
python3 -m venv venv
source venv/bin/activate

# Установить зависимости SEO анализатора
pip install requests beautifulsoup4 lxml markdown
pip install numpy scikit-learn
pip install spacy nltk
pip install playwright
pip install google-search-results
pip install tqdm colorlog

# Установить браузеры для Playwright
python -m playwright install chromium
```

### 2. Базовый тест (seo_test.py)

```python
#!/usr/bin/env python3
"""Базовый тест SEO анализа для Legal AI"""

import sys
sys.path.insert(0, '/tmp/seo-ai-models')

from seo_ai_models.models.seo_advisor.advisor import SEOAdvisor

# Инициализация для юридической отрасли
advisor = SEOAdvisor(industry='legal')

# Тестовое содержимое
test_content = """
# Консультация по корпоративному праву

## Введение

Корпоративное право - это область юриспруденции, которая занимается правовыми вопросами, 
связанными с функционированием и управлением корпорациями...

## Основные аспекты

Наша юридическая фирма имеет более 15 лет опыта в консультировании компаний...

## Часто задаваемые вопросы

Какие документы необходимы для регистрации компании?
Сколько времени занимает процедура?

## Контакты

Свяжитесь с нашей командой специалистов для получения квалифицированной консультации.
"""

# Выполнить анализ
try:
    report = advisor.analyze_content(
        content=test_content,
        keywords=['корпоративное право', 'консультация', 'юридическая фирма']
    )
    
    print("✅ Анализ успешно выполнен!")
    print(f"\nПредсказанная позиция: {report.predicted_position}")
    print(f"E-E-A-T Оценка: {report.content_quality}")
    print(f"Рекомендации: {report.recommendations}")
    
except Exception as e:
    print(f"❌ Ошибка анализа: {e}")
    import traceback
    traceback.print_exc()
```

**Запуск:**
```bash
python seo_test.py
```

---

## Интеграция с вашим Next.js сайтом

### 1. Краулинг сайта (site_analyzer.py)

```python
#!/usr/bin/env python3
"""
Анализ всех страниц Legal AI сайта
Использует Playwright для работы с Next.js
"""

import sys
import json
from pathlib import Path
sys.path.insert(0, '/tmp/seo-ai-models')

from seo_ai_models.parsers.unified.unified_parser import UnifiedParser
from seo_ai_models.models.seo_advisor.advisor import SEOAdvisor
from datetime import datetime

class LegalAIAnalyzer:
    def __init__(self, site_url: str = "https://legal-ai.com"):
        self.site_url = site_url
        
        # Инициализация парсера для Next.js
        self.parser = UnifiedParser(
            force_spa_mode=True,
            auto_detect_spa=True,
            parallel_parsing=True,
            max_workers=3,  # Не нагружать сервер
            
            spa_settings={
                "headless": True,
                "wait_for_idle": 2000,
                "wait_for_timeout": 10000,
                "browser_type": "chromium",
                "intercept_ajax": True
            },
            extract_semantic=True
        )
        
        # Инициализация анализатора для legal сегмента
        self.advisor = SEOAdvisor(industry='legal')
        
    def analyze_site(self, max_pages: int = 20) -> dict:
        """Анализ всего сайта"""
        print(f"Запуск анализа {self.site_url}...")
        print(f"Максимум страниц: {max_pages}\n")
        
        # Краулинг сайта
        print("1. Краулинг сайта...")
        site_analysis = self.parser.crawl_site(
            self.site_url,
            max_pages=max_pages,
            delay=1.5  # Задержка 1.5 сек между запросами
        )
        
        if not site_analysis.get("success"):
            print("❌ Ошибка при краулинге сайта")
            return {"success": False, "error": "Краулинг не успешен"}
        
        pages_data = site_analysis.get("site_data", {}).get("pages", {})
        print(f"✅ Просканировано страниц: {len(pages_data)}\n")
        
        # Анализ каждой страницы
        print("2. Анализ контента...")
        results = []
        
        for idx, (url, page_data) in enumerate(pages_data.items(), 1):
            print(f"   [{idx}/{len(pages_data)}] {url}")
            
            try:
                # Анализ содержимого
                content_text = page_data.get("text", "")
                if not content_text or len(content_text) < 50:
                    print(f"       ⚠️ Недостаточно контента")
                    continue
                
                # Анализ SEO
                analysis = self.advisor.analyze_content(
                    content=content_text,
                    url=url
                )
                
                result = {
                    "url": url,
                    "title": page_data.get("title", ""),
                    "word_count": page_data.get("word_count", 0),
                    "predicted_position": analysis.predicted_position,
                    "eeat_score": analysis.content_quality.eeat_score,
                    "semantic_depth": analysis.feature_scores.get("semantic_depth", 0),
                    "readability": analysis.feature_scores.get("readability_score", 0),
                    "strengths": analysis.content_quality.strengths[:2],
                    "weaknesses": analysis.content_quality.weaknesses[:2],
                    "critical_issues": [r for r in analysis.recommendations.get("critical", [])],
                }
                results.append(result)
                
            except Exception as e:
                print(f"       ❌ Ошибка: {str(e)[:50]}")
                continue
        
        print(f"\n✅ Проанализировано страниц: {len(results)}\n")
        
        # Формирование итогового отчета
        report = {
            "scan_date": datetime.now().isoformat(),
            "site_url": self.site_url,
            "total_pages": len(results),
            "pages": results,
            "summary": self._generate_summary(results)
        }
        
        return report
    
    def _generate_summary(self, results: list) -> dict:
        """Генерация сводной статистики"""
        if not results:
            return {}
        
        positions = [r["predicted_position"] for r in results]
        eeat_scores = [r["eeat_score"] for r in results]
        word_counts = [r["word_count"] for r in results]
        
        return {
            "avg_predicted_position": sum(positions) / len(positions),
            "avg_eeat_score": sum(eeat_scores) / len(eeat_scores),
            "avg_word_count": sum(word_counts) / len(word_counts),
            "pages_in_top_10": len([p for p in positions if p <= 10]),
            "pages_in_top_20": len([p for p in positions if p <= 20]),
            "pages_below_quality": len([e for e in eeat_scores if e < 0.65]),
            "critical_issues_total": sum(len(r.get("critical_issues", [])) for r in results)
        }
    
    def save_report(self, report: dict, filename: str = "seo_report.json"):
        """Сохранение отчета в файл"""
        output_path = Path(filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Отчет сохранен: {output_path}")
    
    def print_summary(self, report: dict):
        """Вывод сводки в консоль"""
        summary = report.get("summary", {})
        
        print("\n" + "="*60)
        print("ИТОГОВАЯ СТАТИСТИКА")
        print("="*60)
        print(f"Проанализировано страниц: {report.get('total_pages', 0)}")
        print(f"Средняя предсказанная позиция: {summary.get('avg_predicted_position', 0):.1f}")
        print(f"Средний E-E-A-T сcore: {summary.get('avg_eeat_score', 0):.2f}")
        print(f"Средний объем контента: {summary.get('avg_word_count', 0):.0f} слов")
        print(f"Страниц в топ-10: {summary.get('pages_in_top_10', 0)}")
        print(f"Страниц в топ-20: {summary.get('pages_in_top_20', 0)}")
        print(f"Страниц ниже качества (E-E-A-T < 0.65): {summary.get('pages_below_quality', 0)}")
        print(f"Критических проблем: {summary.get('critical_issues_total', 0)}")
        print("="*60 + "\n")

def main():
    # Конфигурация
    SITE_URL = "https://legal-ai.com"  # Измените на ваш сайт
    MAX_PAGES = 20  # Для теста - 20 страниц
    
    # Анализ
    analyzer = LegalAIAnalyzer(SITE_URL)
    report = analyzer.analyze_site(max_pages=MAX_PAGES)
    
    # Сохранение и вывод
    if report.get("success", True):
        analyzer.save_report(report, "seo_report_latest.json")
        analyzer.print_summary(report)
        
        # Вывод критических проблем
        print("\nТОП ПРОБЛЕМ ДЛЯ ИСПРАВЛЕНИЯ:")
        print("-" * 60)
        for page in report.get("pages", [])[:5]:  # Первые 5 страниц
            if page["critical_issues"]:
                print(f"\n{page['url']}")
                for issue in page["critical_issues"][:2]:
                    print(f"  • {issue}")

if __name__ == "__main__":
    main()
```

**Запуск:**
```bash
python site_analyzer.py
```

---

## CI/CD интеграция

### GitHub Actions для ежедневного мониторинга

```yaml
# .github/workflows/seo-daily-check.yml
name: Daily SEO Check

on:
  schedule:
    - cron: '0 2 * * *'  # Ежедневно в 2:00 UTC
  workflow_dispatch:     # Ручной запуск

jobs:
  seo-analysis:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python 3.10
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Cache pip packages
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install requests beautifulsoup4 lxml markdown numpy scikit-learn
        pip install spacy nltk gensim playwright google-search-results tqdm colorlog
        python -m playwright install chromium
    
    - name: Clone SEO AI Models
      run: |
        git clone https://github.com/Andrew821667/seo-ai-models.git /tmp/seo-ai-models || true
    
    - name: Run SEO Analysis
      run: |
        python scripts/site_analyzer.py
    
    - name: Check Results
      run: |
        python scripts/check_seo_quality.py --report seo_report_latest.json
    
    - name: Upload Report
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: seo-report-${{ github.run_id }}
        path: seo_report_latest.json
        retention-days: 30
    
    - name: Slack Notification
      if: failure()
      uses: slackapi/slack-github-action@v1
      with:
        webhook-url: ${{ secrets.SLACK_WEBHOOK }}
        payload: |
          {
            "text": "SEO Analysis Failed",
            "details": "Check https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}"
          }
```

### Скрипт проверки качества

```python
#!/usr/bin/env python3
"""check_seo_quality.py - Проверка пороговых значений"""

import json
import sys
from pathlib import Path

# Пороги для Legal AI (YMYL сайт)
THRESHOLDS = {
    "eeat_score": 0.65,           # Минимум для legal
    "predicted_position": 25,     # Целевая позиция <= 25
    "word_count": 800,            # Минимум слов для статьи
    "readability": 50,            # Flesch Reading Ease >= 50
}

def check_report(report_file: str):
    """Проверка отчета против пороговых значений"""
    
    with open(report_file, 'r') as f:
        report = json.load(f)
    
    issues = []
    pages = report.get("pages", [])
    
    print("\nПРОВЕРКА ПОРОГОВЫХ ЗНАЧЕНИЙ")
    print("="*60)
    
    for page in pages:
        url = page.get("url", "unknown")
        
        # Проверка E-E-A-T
        eeat = page.get("eeat_score", 0)
        if eeat < THRESHOLDS["eeat_score"]:
            issues.append(f"⚠️ {url}: E-E-A-T {eeat:.2f} < {THRESHOLDS['eeat_score']}")
        
        # Проверка позиции
        position = page.get("predicted_position", 100)
        if position > THRESHOLDS["predicted_position"]:
            issues.append(f"⚠️ {url}: Позиция {position} > {THRESHOLDS['predicted_position']}")
        
        # Проверка объема
        words = page.get("word_count", 0)
        if words < THRESHOLDS["word_count"]:
            issues.append(f"⚠️ {url}: Слов {words} < {THRESHOLDS['word_count']}")
    
    if issues:
        print(f"\nНайдено проблем: {len(issues)}\n")
        for issue in issues[:10]:  # Показать первые 10
            print(issue)
        print("\n" + "="*60)
        sys.exit(1)
    else:
        print("✅ Все страницы соответствуют требованиям!")
        print("="*60)
        sys.exit(0)

if __name__ == "__main__":
    report_file = sys.argv[1] if len(sys.argv) > 1 else "seo_report_latest.json"
    check_report(report_file)
```

---

## Мониторинг и отслеживание

### Сохранение истории отчетов

```python
#!/usr/bin/env python3
"""Архивирование отчетов для отслеживания прогресса"""

import json
import shutil
from pathlib import Path
from datetime import datetime

def archive_report(report_file: str):
    """Сохранение отчета в архив"""
    
    report_path = Path(report_file)
    if not report_path.exists():
        print(f"Файл не найден: {report_file}")
        return
    
    # Создать директорию для архива
    archive_dir = Path("seo_reports/history")
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Генерировать имя файла с датой
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archive_name = f"seo_report_{timestamp}.json"
    archive_path = archive_dir / archive_name
    
    # Копировать файл
    shutil.copy2(report_path, archive_path)
    
    print(f"✅ Отчет архивирован: {archive_path}")
    
    # Создать также ссылку на последний отчет
    latest_path = Path("seo_reports/latest.json")
    if latest_path.exists():
        latest_path.unlink()
    shutil.copy2(report_path, latest_path)
    print(f"✅ Обновлена ссылка на последний: {latest_path}")

if __name__ == "__main__":
    archive_report("seo_report_latest.json")
```

---

## Полезные команды

```bash
# Анализ одной страницы
python -c "
import sys
sys.path.insert(0, '/tmp/seo-ai-models')
from seo_ai_models.models.seo_advisor.advisor import SEOAdvisor

advisor = SEOAdvisor(industry='legal')
content = 'Ваш контент здесь...'
report = advisor.analyze_content(content)
print(f'Позиция: {report.predicted_position}')
"

# Просмотр последнего отчета
cat seo_report_latest.json | jq '.summary'

# Сравнение с предыдущим отчетом
diff <(jq '.summary' seo_reports/history/seo_report_2025-11-10*.json) \
     <(jq '.summary' seo_report_latest.json)
```

---

## Структура проекта после интеграции

```
legal-ai-bot/website/
├── scripts/
│   ├── site_analyzer.py           # Главный анализатор
│   ├── check_seo_quality.py       # Проверка качества
│   ├── archive_reports.py         # Архивирование
│   └── requirements_seo.txt       # Зависимости SEO
│
├── seo_reports/
│   ├── latest.json                # Последний отчет
│   └── history/
│       ├── seo_report_2025-11-11_02-00-00.json
│       ├── seo_report_2025-11-10_02-00-00.json
│       └── ...
│
├── .github/workflows/
│   └── seo-daily-check.yml        # GitHub Actions
│
├── SEO_AI_MODELS_REPORT.md         # Этот документ
├── INTEGRATION_GUIDE.md            # Гайд интеграции
└── README.md
```

---

## Дополнительные сценарии

### Проверка перед деплоем

```python
#!/usr/bin/env python3
"""Проверка SEO перед деплоем в production"""

import subprocess
import sys

def pre_deploy_seo_check():
    """Выполнить SEO проверку перед деплоем"""
    
    print("🔍 Выполнение SEO проверки перед деплоем...\n")
    
    # 1. Анализ сайта
    print("1️⃣  Анализ сайта...")
    result = subprocess.run([sys.executable, "scripts/site_analyzer.py"], 
                          capture_output=True)
    if result.returncode != 0:
        print("❌ Ошибка анализа")
        sys.exit(1)
    
    # 2. Проверка качества
    print("\n2️⃣  Проверка качества...")
    result = subprocess.run([sys.executable, "scripts/check_seo_quality.py"],
                          capture_output=True)
    if result.returncode != 0:
        print("❌ Сайт не соответствует требованиям качества")
        print(result.stderr.decode())
        sys.exit(1)
    
    # 3. Архивирование
    print("\n3️⃣  Архивирование отчета...")
    subprocess.run([sys.executable, "scripts/archive_reports.py"])
    
    print("\n✅ SEO проверка пройдена успешно!")
    print("Готово к деплою.")
    
    return True

if __name__ == "__main__":
    pre_deploy_seo_check()
```

---

## Поддержка и отладка

### Логирование

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('seo_analysis.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### Обработка ошибок

```python
try:
    result = analyzer.analyze_site(max_pages=20)
except TimeoutError:
    print("⏱️ Тайм-аут при анализе (превышено время ожидания)")
except ConnectionError:
    print("🌐 Ошибка подключения к сайту")
except Exception as e:
    print(f"❌ Непредвиденная ошибка: {e}")
```

