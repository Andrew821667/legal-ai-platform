/**
 * Адрес экрана рабочего места.
 *
 * Карточка клиента и вкладка живут в строке запроса: `?client=<id>` и
 * `?tab=today`. Без этого карточку нельзя было открыть ни из уведомления
 * бота, ни по закладке, а «назад» в Telegram закрывал мини-апп целиком —
 * экран был чистым состоянием React без имени.
 */

export const TABS = ["clients", "today", "finance"] as const;
export type Tab = (typeof TABS)[number];

export type WorkspaceRoute = { tab: Tab; client: string | null };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function parseWorkspaceRoute(search: string): WorkspaceRoute {
  const params = new URLSearchParams(search);
  const tab = params.get("tab");
  const client = params.get("client");
  return {
    tab: (TABS as readonly string[]).includes(tab || "") ? (tab as Tab) : "clients",
    // Мусор в адресе — не повод дёргать сервер: карточка открывается только
    // по настоящему идентификатору.
    client: client && UUID.test(client) ? client.toLowerCase() : null,
  };
}

export function buildWorkspaceSearch(route: WorkspaceRoute): string {
  const params = new URLSearchParams();
  if (route.client) params.set("client", route.client);
  else if (route.tab !== "clients") params.set("tab", route.tab);
  const query = params.toString();
  return query ? `?${query}` : "";
}
