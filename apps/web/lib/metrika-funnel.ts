/**
 * Сайт в воронке: сколько людей зашло и сколько из них оставили заявку.
 *
 * Воронка ядра начинается с тех, кто уже написал, — посетители, ушедшие
 * молча, в ней не видны. Метрика знает их число и откуда они пришли, и её
 * цели отправки формы (`lead_form_submit`, `starter_offer_submit`) — второй
 * счётчик заявок, с которым можно сверить ядро: расхождение значит, что
 * заявки теряются по дороге (антиспам, сбой ядра).
 *
 * Модуль без Next — чтобы тестировать с подставным fetch. Токен Метрики
 * живёт только на сервере сайта, в браузер не уходит.
 */

export const METRIKA_API = "https://api-metrika.yandex.net";

// Номер счётчика не секрет: он в коде каждой страницы сайта.
export const DEFAULT_COUNTER_ID = "110733908";

/** Цели, которые сайт шлёт при отправке заявки (lib/lead-attribution.ts). */
export const LEAD_GOAL_IDENTIFIERS = ["lead_form_submit", "starter_offer_submit"] as const;

const SOURCE_TITLES: Record<string, string> = {
  organic: "Поиск",
  direct: "Прямые заходы",
  referral: "Ссылки с сайтов",
  social: "Соцсети",
  messenger: "Мессенджеры",
  ad: "Реклама",
  recommend: "Рекомендации",
  email: "Почта",
  internal: "Внутренние",
  saved: "Сохранённые страницы",
  undefined: "Не определён",
};

export type MetrikaConfig = { counterId: string; token: string };

export type SiteSource = { key: string; title: string; visits: number; users: number; formSubmits: number | null };

export type SiteStats =
  | { status: "off" }
  | { status: "error"; detail: string }
  | {
      status: "ok";
      date1: string;
      date2: string;
      visits: number;
      users: number;
      /** Отправки формы по целям Метрики; null — цели в счётчике не настроены. */
      formSubmits: number | null;
      sources: SiteSource[];
    };

export function metrikaConfig(env: Record<string, string | undefined>): MetrikaConfig | null {
  const token = (env.YM_ACCESS_TOKEN || "").trim();
  if (!token) return null;
  const counterId = (env.YM_COUNTER_ID || env.NEXT_PUBLIC_YM_COUNTER_ID || DEFAULT_COUNTER_ID).trim();
  if (!/^\d{1,12}$/.test(counterId)) return null;
  return { counterId, token };
}

/** Даты периода в часовом поясе счётчика (Москва): Метрика считает по нему. */
export function periodDates(now: Date, days: number): { date1: string; date2: string } {
  const moscow = (date: Date) =>
    new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Moscow" }).format(date);
  return { date1: moscow(new Date(now.getTime() - days * 86_400_000)), date2: moscow(now) };
}

/** id целей, срабатывающих на отправку заявки, из ответа management API. */
export function leadGoalIds(goals: unknown): number[] {
  const list = (goals as { goals?: unknown })?.goals;
  if (!Array.isArray(list)) return [];
  const wanted = new Set<string>(LEAD_GOAL_IDENTIFIERS);
  const ids: number[] = [];
  for (const goal of list) {
    const record = goal as { id?: unknown; conditions?: unknown };
    const conditions = Array.isArray(record.conditions) ? record.conditions : [];
    const matches = conditions.some((c) => wanted.has(String((c as { url?: unknown })?.url ?? "")));
    if (matches && typeof record.id === "number" && Number.isSafeInteger(record.id)) ids.push(record.id);
  }
  // Метрика принимает до 20 метрик в запросе; две заняты визитами и людьми.
  return ids.slice(0, 18);
}

export function statsUrl(config: MetrikaConfig, dates: { date1: string; date2: string }, goalIds: number[]): string {
  const url = new URL(`${METRIKA_API}/stat/v1/data`);
  const metrics = ["ym:s:visits", "ym:s:users", ...goalIds.map((id) => `ym:s:goal${id}reaches`)];
  url.searchParams.set("ids", config.counterId);
  url.searchParams.set("metrics", metrics.join(","));
  url.searchParams.set("dimensions", "ym:s:lastTrafficSource");
  url.searchParams.set("date1", dates.date1);
  url.searchParams.set("date2", dates.date2);
  // Без выборки: на небольшом трафике сэмплирование дало бы дробные люди.
  url.searchParams.set("accuracy", "full");
  url.searchParams.set("limit", "20");
  return url.toString();
}

const count = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? Math.round(value) : 0);
const sumGoals = (metrics: unknown[], goalCount: number) =>
  goalCount ? metrics.slice(2, 2 + goalCount).reduce<number>((total, value) => total + count(value), 0) : null;

export function parseStats(
  data: unknown,
  goalCount: number,
  dates: { date1: string; date2: string },
): SiteStats {
  const body = data as { totals?: unknown; data?: unknown };
  if (!Array.isArray(body?.totals) || !Array.isArray(body?.data)) {
    return { status: "error", detail: "Метрика ответила без данных." };
  }
  const sources: SiteSource[] = [];
  for (const row of body.data as { dimensions?: { id?: unknown; name?: unknown }[]; metrics?: unknown[] }[]) {
    const dimension = row?.dimensions?.[0] || {};
    const metrics = Array.isArray(row?.metrics) ? row.metrics : [];
    const key = String(dimension.id ?? "undefined");
    sources.push({
      key,
      title: SOURCE_TITLES[key] || String(dimension.name || key),
      visits: count(metrics[0]),
      users: count(metrics[1]),
      formSubmits: sumGoals(metrics, goalCount),
    });
  }
  sources.sort((a, b) => b.visits - a.visits);
  return {
    status: "ok",
    ...dates,
    visits: count(body.totals[0]),
    users: count(body.totals[1]),
    formSubmits: sumGoals(body.totals, goalCount),
    sources,
  };
}

async function getJson(url: string, token: string, fetchImpl: typeof fetch): Promise<unknown> {
  const response = await fetchImpl(url, {
    headers: { Authorization: `OAuth ${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(8_000),
  });
  if (response.status === 401 || response.status === 403) {
    throw new Error("Метрика не приняла токен: выпустите новый с доступом metrika:read.");
  }
  if (!response.ok) throw new Error(`Метрика ответила ${response.status}.`);
  return response.json();
}

export async function loadSiteStats(
  config: MetrikaConfig | null,
  days: number,
  now: Date = new Date(),
  fetchImpl: typeof fetch = fetch,
): Promise<SiteStats> {
  if (!config) return { status: "off" };
  const dates = periodDates(now, days);
  try {
    // Без целей воронка всё равно полезна: визиты и источники останутся.
    const goals = await getJson(
      `${METRIKA_API}/management/v1/counter/${config.counterId}/goals`,
      config.token,
      fetchImpl,
    ).catch(() => null);
    const goalIds = leadGoalIds(goals);
    const data = await getJson(statsUrl(config, dates, goalIds), config.token, fetchImpl);
    return parseStats(data, goalIds.length, dates);
  } catch (error) {
    const timedOut = error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError");
    return {
      status: "error",
      detail: timedOut ? "Метрика не ответила вовремя." : error instanceof Error ? error.message : "Метрика недоступна.",
    };
  }
}

/**
 * Кэш на полчаса: Метрика обновляет данные не мгновенно, а воронку
 * открывают часто. Ошибку помним пять минут — чтобы не долбить API, но и
 * не ждать полчаса после исправления токена.
 */
export function createStatsCache(ttlMs = 30 * 60_000, errorTtlMs = 5 * 60_000) {
  const store = new Map<string, { at: number; value: SiteStats }>();
  return async (key: string, load: () => Promise<SiteStats>, now = Date.now()): Promise<SiteStats> => {
    const hit = store.get(key);
    if (hit && now - hit.at < (hit.value.status === "ok" ? ttlMs : errorTtlMs)) return hit.value;
    const value = await load();
    store.set(key, { at: now, value });
    return value;
  };
}
