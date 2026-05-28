# -*- coding: utf-8 -*-
"""
Revision Comparator — side-by-side, perspective-aware comparison of two
contract revisions, producing a structured report that maps 1-to-1 onto
the rows of the Excel template the lawyer team uses (см. образец
"Сравнение_редакций_договора_..._доп_риски.xlsx").

Pipeline:
  1. Take two ContractVersion-shaped inputs (file paths or parsed XML).
  2. Run the existing DocumentDiffService to get raw atomic changes
     (text + XML/XPath diff with heuristic categorization).
  3. Group raw changes into clause-level pairs, keyed by the source
     clause number from the *older* revision (fallback: from the newer
     revision when the clause is brand-new).
  4. For each pair, ask the LLM (gateway) to produce a structured row:
        {block, condition, txt_old, txt_new, change_summary,
         assessment, risk_level, recommendation, source}
     where assessment ∈ {plus, minus, neutral, mixed} and is rendered
     from the perspective of the requesting party (supplier / buyer /
     neutral). risk_level ∈ {low, medium, high}.
  5. Build a summary block (general verdict, key pros, key risks,
     pre-signature edits) for the second sheet of the xlsx report.

The LLM is invoked through `llm_gateway.LLMGateway` so the whole pipeline
honours the same retries / cost tracking / model selection as the rest of
Contract AI. When `llm_gateway` cannot be imported (e.g. unit tests
running with mocked dependencies), the comparator falls back to a
"stub" mode where assessments come from simple heuristics — enough to
exercise the xlsx exporter end-to-end in CI without burning tokens.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Optional

from loguru import logger


class Perspective(str, Enum):
    """Whose side the assessment is rendered for."""

    SUPPLIER = "supplier"
    BUYER = "buyer"
    NEUTRAL = "neutral"


class Assessment(str, Enum):
    PLUS = "plus"           # Изменение выгодно стороне
    MINUS = "minus"         # Невыгодно
    NEUTRAL = "neutral"     # Не меняет позицию
    MIXED = "mixed"         # Есть и плюс, и минус


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Russian labels used directly in the rendered xlsx — kept here so the
# exporter doesn't need its own translation map.
ASSESSMENT_LABELS_RU: dict[Assessment, str] = {
    Assessment.PLUS: "Плюс",
    Assessment.MINUS: "Минус",
    Assessment.NEUTRAL: "Нейтрально",
    Assessment.MIXED: "Смешанно",
}
RISK_LABELS_RU: dict[RiskLevel, str] = {
    RiskLevel.LOW: "Низкий",
    RiskLevel.MEDIUM: "Средний",
    RiskLevel.HIGH: "Высокий",
}
PERSPECTIVE_LABELS_RU: dict[Perspective, str] = {
    Perspective.SUPPLIER: "Поставщик",
    Perspective.BUYER: "Покупатель",
    Perspective.NEUTRAL: "Нейтральная позиция",
}


@dataclass
class RevisionDiffRow:
    """One row of the 'Сравнение условий' sheet.

    Each row represents a single clause of the contract — same business
    intent in both revisions. `clause_pair_label` puts the matched
    clause numbers right next to '№' so the lawyer immediately sees
    'п.2.1 ↔ п.2.1' (or 'п.5.2 ↔ п.5.3' after renumbering).
    """

    number: int
    clause_pair_label: str          # "п.5.2 ↔ п.5.3" / "п.5.2 ↔ — (удалён)" / "— ↔ п.7.1 (новый)"
    block: str                      # "Предмет / терминология", "Базис поставки", ...
    condition: str                  # короткое название условия
    old_text: Optional[str]         # текст из старой редакции
    new_text: Optional[str]         # текст из новой редакции
    change_summary: str             # 1-2 предложения о сути изменения
    assessment: Assessment          # Плюс / Минус / Нейтрально / Смешанно
    risk_level: RiskLevel           # Низкий / Средний / Высокий
    complex_impact: str             # ⟵ NEW: как пункт влияет на договор и другие пункты
    recommendation: str             # что делать
    source: str                     # "2025: п.2.1; 2026: п.2.1"

    def as_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "clause_pair_label": self.clause_pair_label,
            "block": self.block,
            "condition": self.condition,
            "old_text": self.old_text or "",
            "new_text": self.new_text or "",
            "change_summary": self.change_summary,
            "assessment": self.assessment.value,
            "risk_level": self.risk_level.value,
            "complex_impact": self.complex_impact,
            "recommendation": self.recommendation,
            "source": self.source,
        }


@dataclass
class RevisionDiffSummary:
    """Second-sheet 'Краткие выводы' content."""

    title: str
    prepared_at: datetime
    documents_compared: str         # человекочитаемое описание обоих файлов
    overall_verdict: str            # развёрнутый общий вывод (несколько предложений)
    key_pros: list[str] = field(default_factory=list)
    key_risks: list[str] = field(default_factory=list)
    pre_signature_edits: list[str] = field(default_factory=list)
    source_files: dict[str, str] = field(default_factory=dict)  # {"Редакция 2025": "name.pdf", ...}

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "prepared_at": self.prepared_at.isoformat(),
            "documents_compared": self.documents_compared,
            "overall_verdict": self.overall_verdict,
            "key_pros": list(self.key_pros),
            "key_risks": list(self.key_risks),
            "pre_signature_edits": list(self.pre_signature_edits),
            "source_files": dict(self.source_files),
        }


@dataclass
class RevisionDiffReport:
    """Top-level container returned by RevisionComparator.compare."""

    rows: list[RevisionDiffRow]
    summary: RevisionDiffSummary
    perspective: Perspective

    def as_dict(self) -> dict[str, Any]:
        return {
            "perspective": self.perspective.value,
            "rows": [r.as_dict() for r in self.rows],
            "summary": self.summary.as_dict(),
        }


# --- Comparator implementation ---------------------------------------------

# Closed set of "Блок" labels used in the existing template. The LLM is
# asked to pick the best match from this list (so reports stay
# consistent across runs). The "fallback to clause number" knob below
# is used when the LLM can't confidently classify or when LLM is
# unavailable.
DEFAULT_BLOCKS_RU: tuple[str, ...] = (
    "Предмет / терминология",
    "Базис поставки",
    "Количество",
    "Качество",
    "Документы",
    "Цена / расчёты",
    "Оплата",
    "Право собственности / риск",
    "Хранение",
    "Приёмка",
    "Гарантии",
    "Ответственность / неустойка",
    "Форс-мажор",
    "Конфиденциальность",
    "Срок и расторжение",
    "Применимое право и споры",
    "Прочее",
)


@dataclass
class _ClausePair:
    """Internal: one matched clause from old + new revisions."""

    clause_number_old: Optional[str]
    clause_number_new: Optional[str]
    old_text: Optional[str]
    new_text: Optional[str]
    section_hint_old: Optional[str] = None   # if document_parser supplied a heading
    section_hint_new: Optional[str] = None


class RevisionComparator:
    """Produce a RevisionDiffReport from two contract revisions.

    The constructor takes optional gateways so tests can inject mocks:
      - diff_service: instance with .compare_documents(old, new, mode='combined')
      - llm_gateway:  object with .complete(prompt: str, system: str) -> str
      - parser:       object with .extract_clauses(xml_or_text) -> list[dict]

    All three are optional. If a real gateway is None the comparator
    falls back to heuristics so the pipeline still runs (useful in
    CI and for the very first xlsx wiring before the LLM prompt is
    tuned).
    """

    def __init__(
        self,
        diff_service: Any = None,
        llm_gateway: Any = None,
        parser: Any = None,
        old_revision_label: str = "Редакция 1",
        new_revision_label: str = "Редакция 2",
    ) -> None:
        self.diff_service = diff_service
        self.llm = llm_gateway
        self.parser = parser
        self.old_label = old_revision_label
        self.new_label = new_revision_label

    # ----- public ----------------------------------------------------

    def compare(
        self,
        old_content: str,
        new_content: str,
        *,
        perspective: Perspective = Perspective.NEUTRAL,
        title: Optional[str] = None,
        old_file_name: Optional[str] = None,
        new_file_name: Optional[str] = None,
    ) -> RevisionDiffReport:
        """Compare two revision contents (XML or plain text).

        Returns a RevisionDiffReport ready for the xlsx/pdf exporter.
        """
        pairs = self._match_clauses(old_content, new_content)
        rows = self._classify_pairs(pairs, perspective=perspective)
        summary = self._build_summary(
            rows,
            perspective=perspective,
            title=title or "Сравнение редакций договора",
            old_file_name=old_file_name,
            new_file_name=new_file_name,
        )
        return RevisionDiffReport(rows=rows, summary=summary, perspective=perspective)

    # ----- step 1: pair clauses --------------------------------------

    def _match_clauses(self, old_content: str, new_content: str) -> list[_ClausePair]:
        """Pair clauses across revisions.

        Strategy (in order):
          a) If a document parser is available, use parsed clause numbers
             (e.g. "2.1", "4.3.2") as natural keys.
          b) Otherwise fall back to DocumentDiffService line/XPath diff
             output, grouped by `extract_clause_number(...)`.
          c) If everything fails, return one giant "documents differ"
             pair so the user at least sees the report shell.
        """
        if self.parser is not None:
            try:
                return self._match_via_parser(old_content, new_content)
            except Exception:
                logger.exception("clause matching via parser failed, falling back to diff")

        if self.diff_service is not None:
            try:
                return self._match_via_diff(old_content, new_content)
            except Exception:
                logger.exception("clause matching via diff service failed, falling back to single-pair")

        return [_ClausePair(
            clause_number_old="—",
            clause_number_new="—",
            old_text=old_content[:5000],
            new_text=new_content[:5000],
        )]

    def _match_via_parser(self, old_content: str, new_content: str) -> list[_ClausePair]:
        """Use document_parser to get a structured list of clauses, then
        align on clause number with a best-effort fuzzy join for
        renumbered clauses.
        """
        old_clauses = self.parser.extract_clauses(old_content)  # list[{number, title, text}]
        new_clauses = self.parser.extract_clauses(new_content)
        by_number_new = {c.get("number"): c for c in new_clauses if c.get("number")}

        pairs: list[_ClausePair] = []
        consumed_new: set[str] = set()

        for old_c in old_clauses:
            num = old_c.get("number")
            new_c = by_number_new.get(num)
            if new_c is not None:
                consumed_new.add(num)
                pairs.append(_ClausePair(
                    clause_number_old=num,
                    clause_number_new=num,
                    old_text=old_c.get("text"),
                    new_text=new_c.get("text"),
                    section_hint_old=old_c.get("title"),
                    section_hint_new=new_c.get("title"),
                ))
            else:
                # Deleted clause (only in old)
                pairs.append(_ClausePair(
                    clause_number_old=num,
                    clause_number_new=None,
                    old_text=old_c.get("text"),
                    new_text=None,
                    section_hint_old=old_c.get("title"),
                ))

        for new_c in new_clauses:
            num = new_c.get("number")
            if num and num not in consumed_new:
                # Added clause (only in new)
                pairs.append(_ClausePair(
                    clause_number_old=None,
                    clause_number_new=num,
                    old_text=None,
                    new_text=new_c.get("text"),
                    section_hint_new=new_c.get("title"),
                ))

        return pairs

    def _match_via_diff(self, old_content: str, new_content: str) -> list[_ClausePair]:
        """Use the existing DocumentDiffService and group by detected
        clause number. This is a coarser match than parser-based, but
        still gives row-level granularity for the report.
        """
        raw_changes = self.diff_service.compare_documents(old_content, new_content, mode="combined")
        # Group by clause number (best effort)
        bucket: dict[str, _ClausePair] = {}
        for ch in raw_changes:
            num = (
                self.diff_service.extract_clause_number(
                    (ch.get("old_content") or ch.get("new_content") or ""),
                    ch.get("xpath_location"),
                )
                or ch.get("section_name")
                or f"change-{len(bucket)+1}"
            )
            if num not in bucket:
                bucket[num] = _ClausePair(
                    clause_number_old=num if ch.get("old_content") else None,
                    clause_number_new=num if ch.get("new_content") else None,
                    old_text=ch.get("old_content"),
                    new_text=ch.get("new_content"),
                    section_hint_old=ch.get("section_name"),
                    section_hint_new=ch.get("section_name"),
                )
            else:
                p = bucket[num]
                if ch.get("old_content") and not p.old_text:
                    p.old_text = ch["old_content"]
                    p.clause_number_old = num
                if ch.get("new_content") and not p.new_text:
                    p.new_text = ch["new_content"]
                    p.clause_number_new = num
        return list(bucket.values())

    # ----- step 2: classify ------------------------------------------

    def _classify_pairs(
        self,
        pairs: Iterable[_ClausePair],
        *,
        perspective: Perspective,
    ) -> list[RevisionDiffRow]:
        """Convert raw clause pairs into report rows. Uses LLM when
        available; otherwise applies a deterministic heuristic so the
        exporter and API can still produce a populated report.
        """
        rows: list[RevisionDiffRow] = []
        for idx, pair in enumerate(pairs, start=1):
            if self.llm is not None:
                try:
                    row = self._classify_via_llm(pair, idx, perspective=perspective)
                except Exception:
                    logger.exception("LLM classification failed on pair %d, using heuristic", idx)
                    row = self._classify_heuristic(pair, idx, perspective=perspective)
            else:
                row = self._classify_heuristic(pair, idx, perspective=perspective)
            rows.append(row)
        return rows

    def _classify_via_llm(
        self,
        pair: _ClausePair,
        idx: int,
        *,
        perspective: Perspective,
    ) -> RevisionDiffRow:
        """LLM call: produce a structured row.

        Uses `LLMGateway.call(..., response_format='json')` which already
        handles JSON parsing, markdown-fence stripping, caching and
        retries. Falls back to a raw `.complete(prompt, system)` interface
        for adapters that don't speak the gateway API (used in tests).
        """
        prompt = self._build_llm_prompt(pair, perspective=perspective)
        system = self._llm_system_prompt(perspective)

        if hasattr(self.llm, "call"):
            data = self.llm.call(
                prompt=prompt,
                system_prompt=system,
                response_format="json",
            )
            if isinstance(data, str):
                # Provider returned raw text despite response_format='json'
                # — parse defensively so we don't crash the whole report.
                import json
                data = json.loads(data)
        else:
            import json
            raw = self.llm.complete(prompt=prompt, system=system)
            data = json.loads(raw)

        return RevisionDiffRow(
            number=idx,
            clause_pair_label=self._format_clause_pair_label(pair),
            block=str(data.get("block") or "Прочее"),
            condition=str(data.get("condition") or self._infer_condition(pair)),
            old_text=pair.old_text,
            new_text=pair.new_text,
            change_summary=str(data.get("change_summary") or "Изменение в формулировке."),
            assessment=Assessment(data.get("assessment", Assessment.NEUTRAL.value)),
            risk_level=RiskLevel(data.get("risk_level", RiskLevel.LOW.value)),
            complex_impact=str(data.get("complex_impact") or "Прямого влияния на другие пункты не выявлено."),
            recommendation=str(data.get("recommendation") or "Согласовать с юристом."),
            source=self._format_source(pair),
        )

    def _classify_heuristic(
        self,
        pair: _ClausePair,
        idx: int,
        *,
        perspective: Perspective,
    ) -> RevisionDiffRow:
        """Deterministic fallback used in tests and before the LLM prompt
        is wired in. Produces a *plausible* row so the xlsx exporter can
        be exercised end-to-end without API calls.
        """
        if pair.old_text is None:
            change_summary = "Пункт добавлен в новой редакции."
            assessment = Assessment.MIXED
            recommendation = "Проанализировать добавленное условие на предмет рисков."
            complex_impact = (
                "Новый пункт — возможно влияет на другие разделы; "
                "проверить связи с предметом, ценой и ответственностью."
            )
        elif pair.new_text is None:
            change_summary = "Пункт исключён в новой редакции."
            assessment = Assessment.MIXED
            recommendation = "Уточнить, переехало ли условие в спецификацию или удалено полностью."
            complex_impact = (
                "Удаление пункта может ослабить защиту по связанным разделам "
                "(приёмка, оплата, ответственность) — проверить отдельно."
            )
        else:
            change_summary = "Изменены формулировки пункта."
            assessment = Assessment.NEUTRAL
            recommendation = "Сравнить дословно, согласовать с юристом перед подписанием."
            complex_impact = (
                "Изменение формулировок может косвенно повлиять на смежные пункты "
                "(приёмка/оплата/ответственность) — оценить совместно."
            )

        block = pair.section_hint_old or pair.section_hint_new or "Прочее"
        condition = self._infer_condition(pair)
        return RevisionDiffRow(
            number=idx,
            clause_pair_label=self._format_clause_pair_label(pair),
            block=block,
            condition=condition,
            old_text=pair.old_text,
            new_text=pair.new_text,
            change_summary=change_summary,
            assessment=assessment,
            risk_level=RiskLevel.MEDIUM,
            complex_impact=complex_impact,
            recommendation=recommendation,
            source=self._format_source(pair),
        )

    # ----- step 3: summary -------------------------------------------

    def _build_summary(
        self,
        rows: list[RevisionDiffRow],
        *,
        perspective: Perspective,
        title: str,
        old_file_name: Optional[str],
        new_file_name: Optional[str],
    ) -> RevisionDiffSummary:
        plus = [r for r in rows if r.assessment is Assessment.PLUS]
        minus = [r for r in rows if r.assessment is Assessment.MINUS]
        high_risk = [r for r in rows if r.risk_level is RiskLevel.HIGH]

        verdict_parts: list[str] = []
        verdict_parts.append(
            f"Сравнение с позиции «{PERSPECTIVE_LABELS_RU[perspective]}»."
        )
        verdict_parts.append(
            f"Всего сопоставлено пунктов: {len(rows)}, "
            f"в пользу стороны: {len(plus)}, против: {len(minus)}, "
            f"высокий риск: {len(high_risk)}."
        )

        return RevisionDiffSummary(
            title=title,
            prepared_at=datetime.now(timezone.utc),
            documents_compared=self._documents_compared_label(old_file_name, new_file_name),
            overall_verdict=" ".join(verdict_parts),
            key_pros=[f"{r.block}: {r.change_summary}" for r in plus[:5]],
            key_risks=[f"{r.block}: {r.change_summary}" for r in high_risk[:5]],
            pre_signature_edits=[r.recommendation for r in (high_risk + minus)[:5]],
            source_files={
                self.old_label: old_file_name or "",
                self.new_label: new_file_name or "",
            },
        )

    # ----- helpers ---------------------------------------------------

    def _format_source(self, pair: _ClausePair) -> str:
        bits: list[str] = []
        if pair.clause_number_old:
            bits.append(f"{self.old_label}: п.{pair.clause_number_old}")
        if pair.clause_number_new:
            bits.append(f"{self.new_label}: п.{pair.clause_number_new}")
        return "; ".join(bits) if bits else "—"

    def _format_clause_pair_label(self, pair: _ClausePair) -> str:
        """Compact label shown right next to '№' so it's obvious which
        clauses are being compared in this row."""
        if pair.clause_number_old and pair.clause_number_new:
            return f"п.{pair.clause_number_old} ↔ п.{pair.clause_number_new}"
        if pair.clause_number_old and not pair.clause_number_new:
            return f"п.{pair.clause_number_old} ↔ — (удалён)"
        if pair.clause_number_new and not pair.clause_number_old:
            return f"— ↔ п.{pair.clause_number_new} (новый)"
        return "—"

    def _infer_condition(self, pair: _ClausePair) -> str:
        text = pair.old_text or pair.new_text or ""
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if not first_line:
            return "Изменение пункта"
        # Take up to ~90 chars, end at a word boundary
        return first_line[:90].rstrip() + ("…" if len(first_line) > 90 else "")

    def _documents_compared_label(
        self,
        old_file_name: Optional[str],
        new_file_name: Optional[str],
    ) -> str:
        old = old_file_name or self.old_label
        new = new_file_name or self.new_label
        return f"{old}  ↔  {new}"

    def _llm_system_prompt(self, perspective: Perspective) -> str:
        return (
            "Ты юрист, оценивающий изменения в редакции коммерческого договора. "
            f"Точка зрения: {PERSPECTIVE_LABELS_RU[perspective]}. "
            "Отвечай ТОЛЬКО валидным JSON со схемой: "
            "{block, condition, change_summary, assessment, risk_level, complex_impact, recommendation}. "
            f"assessment ∈ {{plus, minus, neutral, mixed}}. "
            f"risk_level ∈ {{low, medium, high}}. "
            "complex_impact — 1-3 предложения о том, как изменение этого пункта "
            "влияет на договор в целом и на смежные пункты (например: "
            "усиливает обязанности по приёмке, ослабляет защиту в части оплаты, "
            "конфликтует с разделом «Ответственность» и т.п.). "
            f"block желательно выбрать из закрытого списка: {', '.join(DEFAULT_BLOCKS_RU)}."
        )

    def _build_llm_prompt(self, pair: _ClausePair, *, perspective: Perspective) -> str:
        parts: list[str] = []
        parts.append(f"Перспектива: {PERSPECTIVE_LABELS_RU[perspective]}.")
        parts.append("---")
        parts.append(f"Старая редакция (пункт {pair.clause_number_old or 'отсутствует'}):")
        parts.append(pair.old_text or "(пункт отсутствует)")
        parts.append("---")
        parts.append(f"Новая редакция (пункт {pair.clause_number_new or 'отсутствует'}):")
        parts.append(pair.new_text or "(пункт удалён)")
        parts.append("---")
        parts.append(
            "Сформируй JSON: block, condition, change_summary (1-2 предложения), "
            "assessment (plus/minus/neutral/mixed), risk_level (low/medium/high), "
            "complex_impact (как этот пункт влияет на договор и смежные пункты, "
            "1-3 предложения), recommendation (что делать)."
        )
        return "\n".join(parts)


__all__ = [
    "Perspective",
    "Assessment",
    "RiskLevel",
    "RevisionDiffRow",
    "RevisionDiffSummary",
    "RevisionDiffReport",
    "RevisionComparator",
    "ASSESSMENT_LABELS_RU",
    "RISK_LABELS_RU",
    "PERSPECTIVE_LABELS_RU",
    "DEFAULT_BLOCKS_RU",
]
