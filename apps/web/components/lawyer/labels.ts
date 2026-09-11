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

/**
 * Дата, выбранная в календаре, — именно она, а не соседний день.
 *
 * Срок хранится как конец дня по UTC, а `toLocaleDateString` рисует в поясе
 * зрителя: в Москве 23:59Z переезжает на следующие сутки, и юрист, поставивший
 * 17-е, видел на карточке 18-е. Для настоящих моментов времени («когда
 * отправлено») это не так — там местный пояс и нужен.
 */
export function shortDay(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    timeZone: "UTC",
  });
}

export function shortDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

/**
 * Событие журнала — одной строкой, от лица того, кто действовал.
 *
 * Журнал пишет имя API-ключа, а не человека: кто сделал, понятно из самого
 * действия. «Клиент …» и «Вы …» — так лента читается как история дела, а не
 * как лог сервера.
 */
export const HISTORY: Record<string, string> = {
  "legal_intake.create": "Обращение принято",
  "legal_intake.update": "Обращение изменено",
  "legal_intake.outreach": "Бот написал клиенту первым",
  "legal_intake.clarification": "Клиент ответил на уточнение",
  "legal_intake.document": "Клиент прислал документ",
  "nda.sign": "Клиент подписал соглашение о конфиденциальности",
  "service_agreement.create": "Договор составлен",
  "service_agreement.sent": "Договор отправлен клиенту",
  "service_agreement.deliver": "Договор отправлен клиенту",
  "service_agreement.viewed": "Клиент открыл договор",
  "service_agreement.client_details": "Клиент заполнил реквизиты",
  "service_agreement.sign": "Клиент подписал договор",
  "service_agreement.decline": "Клиент отклонил договор",
  "service_agreement.question": "Клиент задал вопрос по договору",
  "service_agreement.reply": "Вы ответили клиенту",
  "service_agreement.amount": "Сумма к учёту изменена",
};
