"""
Template Comparator - Сравнение черновика договора с эталонным шаблоном

Этап Stage 2.2: Pre-Execution
- Загрузка эталонного шаблона (DOCX/PDF/TXT)
- Посекционное сравнение черновика с шаблоном через LLM
- Выявление отклонений, пропущенных разделов, рисков
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from openai import AsyncOpenAI
import os

logger = logging.getLogger(__name__)


@dataclass
class DeviationItem:
    """Одно отклонение от шаблона"""
    section: str           # Раздел договора
    severity: str          # "critical" | "high" | "medium" | "low"
    deviation_type: str    # "missing" | "modified" | "added" | "weakened" | "contradicts"
    template_text: str     # Текст из шаблона (эталон)
    draft_text: str        # Текст из черновика
    description: str       # Описание отклонения
    risk: str              # Какой риск несёт отклонение
    recommendation: str    # Что рекомендуется сделать


@dataclass
class TemplateComparisonResult:
    """Результат сравнения черновика с шаблоном"""
    # Общая статистика
    total_deviations: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int

    # Детали
    deviations: List[DeviationItem]
    missing_sections: List[str]       # Разделы шаблона, отсутствующие в черновике
    extra_sections: List[str]         # Разделы черновика, отсутствующие в шаблоне

    # Итог
    compliance_score: int             # 0-100, насколько черновик соответствует шаблону
    summary: str                      # Краткий итог сравнения
    verdict: str                      # "approved" | "minor_changes" | "major_changes" | "reject"


class TemplateComparator:
    """Сравнивает черновик договора с эталонным шаблоном через LLM"""

    def __init__(self, model: str = "deepseek-chat", api_key: str = None,
                 base_url: str = None):
        self.model = model
        client_kwargs = {"api_key": api_key or os.getenv("OPENAI_API_KEY")}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**client_kwargs)

    async def compare(
        self,
        draft_text: str,
        template_text: str,
        contract_type: str = "неизвестный"
    ) -> TemplateComparisonResult:
        """
        Сравнивает черновик с шаблоном

        Args:
            draft_text: Текст черновика договора
            template_text: Текст эталонного шаблона
            contract_type: Тип договора (для контекста)

        Returns:
            TemplateComparisonResult с детальным анализом отклонений
        """
        logger.info(f"Starting template comparison: draft={len(draft_text)} chars, template={len(template_text)} chars")

        # Обрезаем текст если слишком длинный (лимит контекста LLM)
        max_chars = 12000
        draft_trimmed = draft_text[:max_chars]
        template_trimmed = template_text[:max_chars]

        prompt = f"""Проведи ДЕТАЛЬНОЕ сравнение черновика договора с эталонным шаблоном компании.

ТИП ДОГОВОРА: {contract_type}

═══════════════════════════════════════
ЭТАЛОННЫЙ ШАБЛОН (как ДОЛЖНО быть):
═══════════════════════════════════════
{template_trimmed}

═══════════════════════════════════════
ЧЕРНОВИК ДОГОВОРА (что прислали / составлен):
═══════════════════════════════════════
{draft_trimmed}

═══════════════════════════════════════

ЗАДАЧА: Сравни черновик с шаблоном и найди ВСЕ отклонения.

ВИДЫ ОТКЛОНЕНИЙ:
- "missing" — раздел/пункт из шаблона отсутствует в черновике
- "modified" — формулировка изменена (ослаблена или усилена)
- "added" — в черновике есть пункт, которого нет в шаблоне (может быть риск)
- "weakened" — условие ослаблено по сравнению с шаблоном (менее выгодное)
- "contradicts" — черновик противоречит шаблону или законодательству РФ

SEVERITY:
- "critical" — нарушает закон или создает серьёзный финансовый/юридический риск
- "high" — существенное отклонение от стандарта компании
- "medium" — заметное отклонение, рекомендуется исправить
- "low" — незначительное отклонение, по усмотрению юриста

Верни JSON:
{{
  "deviations": [
    {{
      "section": "Название раздела",
      "severity": "critical|high|medium|low",
      "deviation_type": "missing|modified|added|weakened|contradicts",
      "template_text": "Текст из шаблона (если есть)",
      "draft_text": "Текст из черновика (если есть)",
      "description": "Описание отклонения",
      "risk": "Какой риск это несёт",
      "recommendation": "Что рекомендуется сделать"
    }}
  ],
  "missing_sections": ["Раздел 1", "Раздел 2"],
  "extra_sections": ["Раздел X"],
  "compliance_score": 75,
  "summary": "Краткий итог сравнения (2-3 предложения)",
  "verdict": "minor_changes|major_changes|approved|reject"
}}

ВАЖНО:
- Анализируй ВСЕ разделы, не пропускай
- Ссылайся на конкретные статьи ГК РФ где применимо
- compliance_score: 100 = полное соответствие, 0 = полное несоответствие
- verdict: "approved" (>90%), "minor_changes" (70-90%), "major_changes" (40-70%), "reject" (<40%)
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты ведущий юрист-эксперт по договорному праву РФ с 15-летним опытом. "
                                   "Проводишь экспертное сравнение договоров с эталонными шаблонами компании. "
                                   "Находишь все отклонения, оцениваешь риски, даёшь конкретные рекомендации."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )

            result = json.loads(response.choices[0].message.content)

            # Парсим отклонения
            deviations = []
            for d in result.get("deviations", []):
                deviations.append(DeviationItem(
                    section=d.get("section", ""),
                    severity=d.get("severity", "medium"),
                    deviation_type=d.get("deviation_type", "modified"),
                    template_text=d.get("template_text", ""),
                    draft_text=d.get("draft_text", ""),
                    description=d.get("description", ""),
                    risk=d.get("risk", ""),
                    recommendation=d.get("recommendation", "")
                ))

            # Считаем статистику
            critical = sum(1 for d in deviations if d.severity == "critical")
            high = sum(1 for d in deviations if d.severity == "high")
            medium = sum(1 for d in deviations if d.severity == "medium")
            low = sum(1 for d in deviations if d.severity == "low")

            comparison_result = TemplateComparisonResult(
                total_deviations=len(deviations),
                critical_count=critical,
                high_count=high,
                medium_count=medium,
                low_count=low,
                deviations=deviations,
                missing_sections=result.get("missing_sections", []),
                extra_sections=result.get("extra_sections", []),
                compliance_score=result.get("compliance_score", 0),
                summary=result.get("summary", ""),
                verdict=result.get("verdict", "major_changes")
            )

            logger.info(f"Template comparison completed: {len(deviations)} deviations, "
                       f"score={comparison_result.compliance_score}%, verdict={comparison_result.verdict}")

            return comparison_result

        except Exception as e:
            logger.error(f"Template comparison failed: {e}")
            return TemplateComparisonResult(
                total_deviations=0,
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                deviations=[],
                missing_sections=[],
                extra_sections=[],
                compliance_score=0,
                summary=f"Ошибка сравнения: {str(e)}",
                verdict="major_changes"
            )
