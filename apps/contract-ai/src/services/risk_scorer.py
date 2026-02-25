# -*- coding: utf-8 -*-
"""
Risk Scorer - Stage 2.3

Rule-based risk scoring for Pre-Execution analysis.
Produces:
- overall risk score (0-100)
- risk level
- section-level risk indicators
- actionable factors
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import re


@dataclass
class RiskFactor:
    """Single risk factor contribution."""

    code: str
    title: str
    severity: str
    points: int
    description: str
    recommendation: str
    source: str


@dataclass
class SectionRisk:
    """Risk score for one contract section."""

    section_number: str
    section_title: str
    score: int
    level: str
    warnings_count: int
    recommendations_count: int


@dataclass
class RiskScoringResult:
    """Final risk scoring result."""

    overall_score: int
    mitigated_score: int
    risk_level: str
    residual_risk_level: str
    critical_factors: int
    high_factors: int
    medium_factors: int
    low_factors: int
    factors: List[RiskFactor]
    section_risks: List[SectionRisk]
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "mitigated_score": self.mitigated_score,
            "risk_level": self.risk_level,
            "residual_risk_level": self.residual_risk_level,
            "critical_factors": self.critical_factors,
            "high_factors": self.high_factors,
            "medium_factors": self.medium_factors,
            "low_factors": self.low_factors,
            "factors": [f.__dict__ for f in self.factors],
            "section_risks": [s.__dict__ for s in self.section_risks],
            "summary": self.summary,
        }


class RiskScorer:
    """
    Stage 2.3 scorer.

    Scoring philosophy:
    - 0 = no detected risk
    - 100 = critical risk concentration
    """

    def score(
        self,
        raw_text: str,
        extracted_data: Optional[Dict[str, Any]] = None,
        validation_result: Optional[Dict[str, Any]] = None,
        template_comparison: Optional[Any] = None,
        section_analysis: Optional[Dict[str, Any]] = None,
        accepted_recommendations: Optional[List[Dict[str, Any]]] = None,
    ) -> RiskScoringResult:
        """Calculate risk score and detailed factors."""

        extracted_data = extracted_data or {}
        validation_result = validation_result or {}
        accepted_recommendations = accepted_recommendations or []

        factors: List[RiskFactor] = []
        section_risks: List[SectionRisk] = []
        score = 0

        # 1) Validation impact
        errors = validation_result.get("errors", []) or []
        warnings = validation_result.get("warnings", []) or []
        if errors:
            points = min(30, len(errors) * 8)
            score += points
            factors.append(
                RiskFactor(
                    code="validation_errors",
                    title="Ошибки валидации",
                    severity="high" if len(errors) < 3 else "critical",
                    points=points,
                    description=f"Обнаружено ошибок валидации: {len(errors)}",
                    recommendation="Исправить обязательные поля и некорректные значения перед согласованием.",
                    source="validation",
                )
            )
        if warnings:
            points = min(16, len(warnings) * 3)
            score += points
            factors.append(
                RiskFactor(
                    code="validation_warnings",
                    title="Предупреждения валидации",
                    severity="medium",
                    points=points,
                    description=f"Обнаружено предупреждений: {len(warnings)}",
                    recommendation="Проверить отмеченные поля и уточнить формулировки.",
                    source="validation",
                )
            )

        # 2) Template deviations impact
        if template_comparison is not None:
            critical = self._safe_get(template_comparison, "critical_count", 0)
            high = self._safe_get(template_comparison, "high_count", 0)
            medium = self._safe_get(template_comparison, "medium_count", 0)
            low = self._safe_get(template_comparison, "low_count", 0)
            missing_sections = self._safe_get(template_comparison, "missing_sections", []) or []

            if critical or high or medium or low:
                points = min(50, critical * 18 + high * 10 + medium * 5 + low * 2)
                score += points
                sev = "critical" if critical > 0 else ("high" if high > 0 else "medium")
                factors.append(
                    RiskFactor(
                        code="template_deviations",
                        title="Отклонения от эталонного шаблона",
                        severity=sev,
                        points=points,
                        description=(
                            f"Критичных: {critical}, высоких: {high}, "
                            f"средних: {medium}, низких: {low}"
                        ),
                        recommendation="Согласовать отклонения с юридической политикой компании и устранить критичные расхождения.",
                        source="template_comparison",
                    )
                )

            if missing_sections:
                points = min(20, len(missing_sections) * 6)
                score += points
                factors.append(
                    RiskFactor(
                        code="missing_sections",
                        title="Пропущенные разделы шаблона",
                        severity="high",
                        points=points,
                        description=f"Отсутствует разделов из шаблона: {len(missing_sections)}",
                        recommendation="Добавить отсутствующие разделы или зафиксировать бизнес-обоснование исключения.",
                        source="template_comparison",
                    )
                )

        # 3) Heuristics by extracted data + text
        text_lower = (raw_text or "").lower()
        financials = extracted_data.get("financials", {}) if isinstance(extracted_data, dict) else {}
        penalties = extracted_data.get("penalties", {}) if isinstance(extracted_data, dict) else {}
        terms = extracted_data.get("terms", {}) if isinstance(extracted_data, dict) else {}

        prepayment_percent = self._extract_percentage(financials, ["prepayment_percent", "advance_percent", "prepayment"])
        if prepayment_percent is None:
            prepayment_percent = self._extract_number_from_text(text_lower, r"(предоплат[аы]|аванс)[^\d]{0,20}(\d{1,3})\s*%")

        if prepayment_percent is not None and prepayment_percent > 50:
            points = min(18, int((prepayment_percent - 50) * 0.6) + 8)
            score += points
            factors.append(
                RiskFactor(
                    code="high_prepayment",
                    title="Высокая предоплата",
                    severity="high",
                    points=points,
                    description=f"Предоплата {prepayment_percent:.0f}% превышает порог 50%",
                    recommendation="Снизить долю предоплаты или добавить гарантии исполнения/возврата.",
                    source="financials",
                )
            )

        payment_days = self._extract_integer(terms, ["payment_days", "payment_term_days", "days_to_pay"])
        if payment_days is None:
            payment_days = self._extract_number_from_text(text_lower, r"(срок оплат[ыа]|оплата в течение)[^\d]{0,20}(\d{1,3})")
        if payment_days is not None and payment_days > 60:
            points = min(15, int((payment_days - 60) * 0.25) + 8)
            score += points
            factors.append(
                RiskFactor(
                    code="long_payment_term",
                    title="Длинный срок оплаты",
                    severity="high",
                    points=points,
                    description=f"Срок оплаты {int(payment_days)} дней превышает 60 дней",
                    recommendation="Сократить срок оплаты или добавить обеспечительные механизмы.",
                    source="terms",
                )
            )

        penalty_percent_day = self._extract_percentage(penalties, ["penalty_percent_per_day", "penalty_rate", "daily_penalty"])
        if penalty_percent_day is None:
            penalty_percent_day = self._extract_number_from_text(
                text_lower,
                r"(неустойк[аеи]|пен[яи])[^\d]{0,25}(\d+(?:[.,]\d+)?)\s*%[^.\n]{0,20}(в день|за день)"
            )
        if penalty_percent_day is not None and penalty_percent_day > 0.5:
            points = min(12, int((penalty_percent_day - 0.5) * 10) + 4)
            score += points
            factors.append(
                RiskFactor(
                    code="aggressive_penalty",
                    title="Повышенная ежедневная неустойка",
                    severity="medium",
                    points=points,
                    description=f"Неустойка {penalty_percent_day:.2f}% в день выше порога 0.5%",
                    recommendation="Согласовать разумный предел неустойки и максимальный cap по сумме.",
                    source="penalties",
                )
            )

        if not self._contains_any(text_lower, ["форс-мажор", "обстоятельств непреодолимой силы"]):
            score += 8
            factors.append(
                RiskFactor(
                    code="missing_force_majeure",
                    title="Нет явного форс-мажора",
                    severity="medium",
                    points=8,
                    description="В тексте не найден раздел/условие о форс-мажоре.",
                    recommendation="Добавить раздел о форс-мажоре с порядком уведомления сторон.",
                    source="text_heuristics",
                )
            )

        if not self._contains_any(text_lower, ["порядок разрешения споров", "подсудн", "арбитражный суд"]):
            score += 7
            factors.append(
                RiskFactor(
                    code="missing_dispute_resolution",
                    title="Неявный порядок разрешения споров",
                    severity="medium",
                    points=7,
                    description="Не найдено явное условие о подсудности/урегулировании споров.",
                    recommendation="Добавить порядок досудебного урегулирования и подсудность.",
                    source="text_heuristics",
                )
            )

        if self._contains_any(
            text_lower,
            [
                "неограниченн",
                "в полном объеме убытков без ограничения",
                "без ограничения ответственности",
            ],
        ):
            score += 20
            factors.append(
                RiskFactor(
                    code="unlimited_liability",
                    title="Неограниченная ответственность",
                    severity="critical",
                    points=20,
                    description="Выявлены признаки неограниченной ответственности стороны.",
                    recommendation="Ограничить ответственность суммой договора или согласованным лимитом.",
                    source="text_heuristics",
                )
            )

        if self._contains_any(
            text_lower,
            [
                "право англии",
                "право штата",
                "london court",
                "icc arbitration",
                "иностранн",
            ],
        ):
            score += 22
            factors.append(
                RiskFactor(
                    code="foreign_jurisdiction",
                    title="Иностранное право/подсудность",
                    severity="critical",
                    points=22,
                    description="Обнаружены признаки иностранной юрисдикции или права.",
                    recommendation="Подтвердить приемлемость юрисдикции; при необходимости перейти на право РФ.",
                    source="text_heuristics",
                )
            )

        # 4) Section analysis impact
        if section_analysis:
            section_risks = self._score_sections(section_analysis)
            risky_sections = [s for s in section_risks if s.level in ("critical", "high")]
            if risky_sections:
                points = min(20, len(risky_sections) * 4)
                score += points
                factors.append(
                    RiskFactor(
                        code="section_risks",
                        title="Повышенный риск по разделам",
                        severity="high" if len(risky_sections) >= 2 else "medium",
                        points=points,
                        description=f"Разделов с высоким/критичным риском: {len(risky_sections)}",
                        recommendation="Приоритизировать доработку наиболее рискованных разделов.",
                        source="section_analysis",
                    )
                )

        # 5) Mitigation by accepted recommendations
        accepted_count = len(accepted_recommendations)
        critical_accepted = 0
        for item in accepted_recommendations:
            priority = (item.get("priority") or "").lower()
            if priority == "critical":
                critical_accepted += 1

        mitigation_points = min(35, accepted_count * 3 + critical_accepted * 4)
        raw_score = min(100, max(0, score))
        mitigated = max(0, raw_score - mitigation_points)

        critical_count = sum(1 for f in factors if f.severity == "critical")
        high_count = sum(1 for f in factors if f.severity == "high")
        medium_count = sum(1 for f in factors if f.severity == "medium")
        low_count = sum(1 for f in factors if f.severity == "low")

        risk_level = self._score_to_level(raw_score)
        residual_level = self._score_to_level(mitigated)

        summary = (
            f"Базовый риск: {raw_score}/100 ({risk_level}). "
            f"После учета принятых правок: {mitigated}/100 ({residual_level})."
        )

        return RiskScoringResult(
            overall_score=raw_score,
            mitigated_score=mitigated,
            risk_level=risk_level,
            residual_risk_level=residual_level,
            critical_factors=critical_count,
            high_factors=high_count,
            medium_factors=medium_count,
            low_factors=low_count,
            factors=factors,
            section_risks=section_risks,
            summary=summary,
        )

    def _score_sections(self, section_analysis: Dict[str, Any]) -> List[SectionRisk]:
        """Score risks by section analysis output."""

        result: List[SectionRisk] = []
        sections = section_analysis.get("sections", []) if isinstance(section_analysis, dict) else []
        analyses = section_analysis.get("section_analyses", []) if isinstance(section_analysis, dict) else []

        for section, analysis in zip(sections, analyses):
            section_number = self._safe_get(section, "number", "")
            section_title = self._safe_get(section, "title", "")
            warnings = self._safe_get(analysis, "warnings", []) or []
            recs = self._safe_get(analysis, "recommendations", []) or []
            comparison = (self._safe_get(analysis, "own_contracts_comparison", "") or "").lower()
            conclusion = (self._safe_get(analysis, "conclusion", "") or "").lower()

            sec_score = 0
            sec_score += min(45, len(warnings) * 10)

            critical_recs = 0
            important_recs = 0
            optional_recs = 0

            for rec in recs:
                priority = (self._safe_get(rec, "priority", "optional") or "optional").lower()
                if priority == "critical":
                    critical_recs += 1
                elif priority == "important":
                    important_recs += 1
                else:
                    optional_recs += 1

            sec_score += min(35, critical_recs * 12 + important_recs * 7 + optional_recs * 3)

            if "не соответствует" in comparison:
                sec_score += 14
            elif "замеч" in comparison:
                sec_score += 8

            if "требует" in conclusion or "доработ" in conclusion:
                sec_score += 7

            sec_score = min(100, sec_score)
            sec_level = self._score_to_level(sec_score)

            result.append(
                SectionRisk(
                    section_number=str(section_number),
                    section_title=str(section_title),
                    score=sec_score,
                    level=sec_level,
                    warnings_count=len(warnings),
                    recommendations_count=len(recs),
                )
            )

        return result

    def _score_to_level(self, score: int) -> str:
        if score >= 75:
            return "critical"
        if score >= 55:
            return "high"
        if score >= 30:
            return "medium"
        return "low"

    def _safe_get(self, obj: Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _contains_any(self, text: str, keywords: List[str]) -> bool:
        for kw in keywords:
            if kw in text:
                return True
        return False

    def _extract_percentage(self, data: Dict[str, Any], keys: List[str]) -> Optional[float]:
        for key in keys:
            value = data.get(key) if isinstance(data, dict) else None
            if value is None:
                continue
            parsed = self._to_float(value)
            if parsed is not None:
                return parsed
        return None

    def _extract_integer(self, data: Dict[str, Any], keys: List[str]) -> Optional[int]:
        for key in keys:
            value = data.get(key) if isinstance(data, dict) else None
            if value is None:
                continue
            parsed = self._to_float(value)
            if parsed is not None:
                return int(parsed)
        return None

    def _extract_number_from_text(self, text: str, pattern: str) -> Optional[float]:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None
        value = match.group(2) if match.lastindex and match.lastindex >= 2 else match.group(1)
        return self._to_float(value)

    def _to_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip().lower()
        if not text:
            return None

        text = text.replace("%", "").replace(",", ".")
        text = re.sub(r"[^\d.]", "", text)
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

