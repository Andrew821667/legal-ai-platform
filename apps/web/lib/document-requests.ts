/**
 * Запрос документов у клиента: что предложить юристу одним нажатием, как
 * собрать список и что сказать после отправки.
 *
 * Модуль без React — логику проверяют тесты, а компоненты только рисуют.
 */

export type DocumentRequestStatus = "open" | "received" | "cancelled";

export type DocumentRequestRow = {
  request_id: string;
  intake_id: string;
  title: string;
  note: string | null;
  status: DocumentRequestStatus;
  document_id: string | null;
  created_at: string | null;
  received_at: string | null;
};

export type DocumentRequestResponse = {
  requests: DocumentRequestRow[];
  delivered_via: "telegram" | "queued" | "not_configured" | "cabinet" | "none";
  cabinet_email?: string;
};

export const MAX_ITEMS = 20;

// Частые просьбы по практикам — чтобы юрист отмечал, а не набирал.
const COMMON: Record<string, string[]> = {
  legal: [
    "Паспорт (разворот с фото и регистрация)",
    "Договор и приложения",
    "Переписка со второй стороной",
    "Претензия или ответ на неё",
    "Платёжные документы",
    "Доверенность",
    "Выписка ЕГРН",
    "Выписка ЕГРЮЛ / ЕГРИП",
  ],
  engineering: [
    "Описание текущего процесса",
    "Доступы к тестовой среде",
    "Примеры входных данных",
    "Документация API",
    "Макеты или скриншоты",
  ],
};

export function commonDocuments(practice: string | null | undefined): string[] {
  if (practice === "engineering") return COMMON.engineering;
  if (practice === "hybrid") return [...COMMON.legal.slice(0, 4), ...COMMON.engineering.slice(0, 3)];
  return COMMON.legal;
}

/**
 * Список из отмеченных вариантов и строк «своего»: по строке или через «;».
 * Без пустых, без повторов (без учёта регистра), не больше MAX_ITEMS.
 */
export function collectTitles(selected: string[], custom: string): string[] {
  const seen = new Set<string>();
  const titles: string[] = [];
  for (const raw of [...selected, ...custom.split(/[\n;]+/)]) {
    const title = raw.replace(/\s+/g, " ").trim().slice(0, 200);
    if (title.length < 2 || seen.has(title.toLocaleLowerCase("ru"))) continue;
    seen.add(title.toLocaleLowerCase("ru"));
    titles.push(title);
  }
  return titles.slice(0, MAX_ITEMS);
}

/** «Ждём 2 из 3» — для заголовка блока; отменённые не считаются. */
export function waitingSummary(rows: DocumentRequestRow[]): string | null {
  const active = rows.filter((row) => row.status !== "cancelled");
  if (!active.length) return null;
  const waiting = active.filter((row) => row.status === "open").length;
  return waiting ? `ждём ${waiting} из ${active.length}` : "всё получено";
}

export function deliveryNote(response: DocumentRequestResponse): string {
  const count = response.requests.length;
  const saved = `Запрошено: ${count}.`;
  switch (response.delivered_via) {
    case "telegram":
      return `${saved} Список ушёл клиенту в Telegram и виден ему в «Моих делах».`;
    case "queued":
      return `${saved} Telegram сейчас не ответил — сообщение повторится само; список уже виден клиенту в «Моих делах».`;
    case "not_configured":
      return `${saved} Бот на сервере не настроен — сообщение не ушло, но список виден клиенту в «Моих делах».`;
    case "cabinet":
      return `${saved} Клиент без Telegram увидит список в кабинете (ai-verdict.ru/cabinet, вход с Яндекс ID, почта ${response.cabinet_email}). Сообщите ему об этом.`;
    default:
      return `${saved} У клиента нет ни Telegram, ни почты для кабинета — передайте список сами.`;
  }
}
