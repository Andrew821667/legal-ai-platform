"""Явная подсказка о связи с другим обращением — в собственных словах клиента.

Кейс, из-за которого это появилось: Рябова Алёна написала в своём обращении
прямым текстом «Обращался Рябов АА. Уже есть информация по нашему случаю» —
это НЕ требует сопоставления фамилий по всей базе (см. platform_context.py,
TODO про чужие обращения — та, более рискованная задача сознательно не
делалась). Здесь работа проще и безопаснее: человек сам назвал фамилию в
своём тексте, наша задача — не проглядеть это и явно показать владельцу.

Эвристика простая и объяснимая (не LLM): вытащить из текста слова, похожие
на русские фамилии, и проверить, не совпадает ли какое-то из них с именем
уже существующего лида. Ложные срабатывания не опасны — результат только
подсвечивается владельцу как «проверьте», а не показывается автоматически
другому клиенту и не меняет поведение бота.
"""
from __future__ import annotations

import re

# Слово, похожее на фамилию: с заглавной кириллической буквы, 3+ букв,
# остальные строчные (частично допускаем "Рябов" и т.п.), либо в кавычках.
_SURNAME_TOKEN_RE = re.compile(r"\b[А-ЯЁ][а-яё]{2,}(?:ов|ев|ин|ын|ая|яя|ий|ый|их|ых|а|я)?\b")

# Частые слова, которые попадают под шаблон, но фамилиями не являются —
# начало предложения, обращения, названия организаций и т.п.
_STOPWORDS = {
    "Здравствуйте", "Добрый", "Добрая", "Нужна", "Нужен", "Нужно", "Хочу",
    "Меня", "Мне", "Моя", "Мой", "Моё", "Наш", "Наша", "Наше", "Обращался",
    "Обращалась", "Уже", "Есть", "Информация", "По", "Нашему", "Случаю",
    "Дело", "Вопрос", "Спасибо", "Пожалуйста", "Прошу", "Компания", "ООО",
    "ИП", "АО", "ПАО", "Договор", "Организация", "Ситуация", "Помогите",
    "Помощь", "Юрист", "Юристу", "Консультация", "Здравствуй", "Приветствую",
}

_MIN_SURNAME_LEN = 4


def extract_name_candidates(text: str | None) -> list[str]:
    """Слова из текста клиента, похожие на упомянутую фамилию (без своего имени)."""
    if not text:
        return []
    seen: list[str] = []
    for match in _SURNAME_TOKEN_RE.finditer(text):
        word = match.group(0)
        if len(word) < _MIN_SURNAME_LEN or word in _STOPWORDS:
            continue
        if word not in seen:
            seen.append(word)
    return seen


def _name_matches_candidate(lead_name: str | None, candidate: str) -> bool:
    if not lead_name:
        return False
    candidate_low = candidate.lower()
    for part in lead_name.split():
        part = part.strip(",.")
        if len(part) < _MIN_SURNAME_LEN:
            continue
        # Совпадение по началу слова покрывает падежи и краткую форму
        # фамилии ("Рябов" в тексте против "Рябова Алёна" в имени лида).
        stem_len = _MIN_SURNAME_LEN
        if part.lower()[:stem_len] == candidate_low[:stem_len]:
            return True
    return False


def find_related_lead(
    *,
    text: str | None,
    own_lead_id: int | None,
    own_name: str | None,
    other_leads: list[dict],
) -> dict | None:
    """Первый другой лид, чьё имя совпадает с фамилией из текста этого лида.

    `other_leads` — список словарей с как минимум `id`, `name`, `created_at`
    (формат `database.db.get_all_leads()`). own_name исключён из кандидатов,
    чтобы не сработать на собственной фамилии.
    """
    candidates = [c for c in extract_name_candidates(text) if not _name_matches_candidate(own_name, c)]
    if not candidates:
        return None
    for other in other_leads:
        if other.get("id") == own_lead_id:
            continue
        for candidate in candidates:
            if _name_matches_candidate(other.get("name"), candidate):
                return {"lead": other, "matched_word": candidate}
    return None


def build_relation_flag(match: dict) -> str:
    other = match["lead"]
    created = (other.get("created_at") or "")[:10]
    return (
        f"⚠️ Возможная связь: в обращении упомянута фамилия «{match['matched_word']}», "
        f"похожая на лид №{other.get('id')} «{other.get('name') or '—'}»"
        + (f" от {created}" if created else "")
        + ". Проверьте, не конфликт ли интересов, прежде чем отвечать по существу."
    )
