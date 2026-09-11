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

export function groupClients<T extends ClientLike>(
  rows: T[],
  filter: ClientFilter = "all",
): { key: ClientGroupKey; title: string; hint: string; rows: T[] }[] {
  const buckets = new Map<ClientGroupKey, T[]>();
  for (const row of rows) {
    if (!matchesFilter(row, filter)) continue;
    const key = clientGroup(row);
    buckets.set(key, [...(buckets.get(key) || []), row]);
  }
  return CLIENT_GROUPS.filter((group) => buckets.has(group.key)).map((group) => ({
    ...group,
    rows: buckets.get(group.key) || [],
  }));
}
