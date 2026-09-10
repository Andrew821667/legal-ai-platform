/** Человеческие названия вместо служебных кодов. */

export const AREA: Record<string, string> = {
  contracts: "Договорная работа",
  disputes: "Спор",
  corporate: "Корпоративные отношения",
  employment: "Трудовые отношения",
  tax_compliance: "Налоги",
  real_estate: "Недвижимость",
  it_ip_data: "ИС и данные",
  family_inheritance: "Семья и наследство",
  debt_bankruptcy: "Задолженность",
  other: "Требует уточнения",
};

export const INTAKE_STATUS: Record<string, string> = {
  received: "Принято",
  needs_clarification: "Уточняем",
  conflict_check: "Проверка конфликта",
  scope_preparation: "Готовим условия",
  proposal_sent: "Предложение отправлено",
  accepted: "В работе",
  declined: "Отказ",
  closed: "Закрыто",
};

export const AGREEMENT_STATUS: Record<string, string> = {
  draft: "Черновик",
  sent: "Отправлен",
  viewed: "Просмотрен",
  signed: "Подписан",
  declined: "Отклонён",
  expired: "Истёк",
  superseded: "Заменён",
  cancelled: "Отменён",
};

export const URGENCY: Record<string, string> = {
  urgent: "Срочно",
  high: "Высокая",
  normal: "Обычная",
  no_deadline: "Без срока",
};

/** Проверка конфликта интересов. Ядро не даёт создать договор, пока не «clear». */
export const CONFLICT: Record<string, string> = {
  unchecked: "Конфликт не проверен",
  clear: "Конфликтов нет",
  potential: "Нужна доп. проверка",
  conflict: "Обнаружен конфликт",
};

export const CONFLICT_EXPLAINED: Record<string, string> = {
  unchecked:
    "Проверка на конфликт интересов не проводилась. Пока она не пройдена, договор по этому обращению создать нельзя.",
  potential:
    "Проверка показала возможный конфликт интересов. Пока он не снят, договор по этому обращению создать нельзя.",
  conflict:
    "По этому обращению обнаружен конфликт интересов. Договор заключать нельзя.",
};

export const OUTREACH_REASON: Record<string, string> = {
  no_telegram: "заявка не из Telegram",
  forbidden: "бот заблокирован",
};

export function label(map: Record<string, string>, key: string | null | undefined): string {
  if (!key) return "—";
  return map[key] || key;
}

/** «3 дня», «1 день» — согласование числительного. */
export function days(count: number | null | undefined): string {
  if (count === null || count === undefined) return "";
  const last = count % 10;
  const teen = count % 100 >= 11 && count % 100 <= 14;
  const word = teen || last === 0 || last >= 5 ? "дней" : last === 1 ? "день" : "дня";
  return `${count} ${word}`;
}

export function shortDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "2-digit" });
}
