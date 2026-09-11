/**
 * Список клиентов — по тому, у кого сейчас ход.
 *
 * Пока клиентов пять, список читается и подряд. На двадцати он превращается
 * в перебор: кто ждёт меня, а кто — своего юриста на той стороне, видно
 * только по пилюлям, и глаз их не собирает. Группы отвечают на один вопрос:
 * что мне делать сейчас. Внутри группы — как отдал сервер, новые первыми.
 */

export type ClientGroupKey = "mine" | "theirs" | "active" | "declined";

export type ClientLike = {
  stage: string;
  waiting_on_me: boolean;
  nda_signed: boolean;
  legal_areas: string[];
  amount_minor: number | null;
};

export const CLIENT_GROUPS: { key: ClientGroupKey; title: string; hint: string }[] = [
  { key: "mine", title: "Нужен ваш ход", hint: "ответить, подготовить условия или отправить договор" },
  { key: "theirs", title: "Ждём клиента", hint: "договор у клиента, решение за ним" },
  { key: "active", title: "В работе", hint: "договор подписан" },
  { key: "declined", title: "Отказались", hint: "" },
];

export function clientGroup(row: ClientLike): ClientGroupKey {
  if (row.waiting_on_me) return "mine";
  if (row.stage === "Договор подписан") return "active";
  if (row.stage === "Клиент отказался") return "declined";
  if (row.stage === "Договор у клиента") return "theirs";
  return "mine";
}

export type ClientFilter = "all" | "waiting" | "no_nda" | "signed";

export const CLIENT_FILTERS: { key: ClientFilter; title: string }[] = [
  { key: "all", title: "Все" },
  { key: "waiting", title: "Ждут ответа" },
  { key: "no_nda", title: "Без NDA" },
  { key: "signed", title: "Подписан" },
];

export function matchesFilter(row: ClientLike, filter: ClientFilter): boolean {
  if (filter === "waiting") return row.waiting_on_me;
  if (filter === "no_nda") return !row.nda_signed;
  if (filter === "signed") return row.stage === "Договор подписан";
  return true;
}

/** Пусто — область не выбрана вовсе, тогда проходят все. */
export function matchesAreas(row: ClientLike, areas: string[]): boolean {
  if (areas.length === 0) return true;
  return row.legal_areas.some((area) => areas.includes(area));
}

/**
 * Области, которые реально встречаются в списке, — самые частые первыми.
 *
 * Кодов — десяток, а у практики обычно два-три направления; статичный
 * список чипов на все области был бы забит лишними.
 */
export function availableAreas(rows: ClientLike[]): string[] {
  const counts = new Map<string, number>();
  for (const row of rows) {
    for (const area of row.legal_areas) counts.set(area, (counts.get(area) || 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([area]) => area);
}

export type ClientSort = "recent" | "amount_desc";

export const CLIENT_SORTS: { key: ClientSort; title: string }[] = [
  { key: "recent", title: "Сначала новые" },
  { key: "amount_desc", title: "Сначала дороже" },
];

/**
 * По сумме — только те, у кого она известна; остальные хвостом, в своём
 * прежнем порядке. Ноль в неизвестной сумме означал бы «копейки», а её
 * там попросту нет — молчание, а не грош.
 */
function sortRows<T extends ClientLike>(rows: T[], sort: ClientSort): T[] {
  if (sort === "recent") return rows;
  const priced = rows.filter((r) => r.amount_minor !== null);
  const unpriced = rows.filter((r) => r.amount_minor === null);
  priced.sort((a, b) => (b.amount_minor as number) - (a.amount_minor as number));
  return [...priced, ...unpriced];
}

export function groupClients<T extends ClientLike>(
  rows: T[],
  filter: ClientFilter = "all",
  options: { areas?: string[]; sort?: ClientSort } = {},
): { key: ClientGroupKey; title: string; hint: string; rows: T[] }[] {
  const areas = options.areas || [];
  const sort = options.sort || "recent";
  const buckets = new Map<ClientGroupKey, T[]>();
  for (const row of rows) {
    if (!matchesFilter(row, filter) || !matchesAreas(row, areas)) continue;
    const key = clientGroup(row);
    buckets.set(key, [...(buckets.get(key) || []), row]);
  }
  return CLIENT_GROUPS.filter((group) => buckets.has(group.key)).map((group) => ({
    ...group,
    rows: sortRows(buckets.get(group.key) || [], sort),
  }));
}
