/**
 * Запросы сайта к api.telegram.org — через прокси.
 *
 * С прод-хоста Telegram напрямую не открывается (таймаут), и сайт ходил туда
 * встроенным fetch без прокси: документы клиента в рабочем месте не
 * открывались, «в чат» не отправлялось. Прокси тот же, что у ядра и бота
 * (LEGAL_AI_HTTPS_PROXY), и тот же приём, что у входа через Telegram:
 * fetch и ProxyAgent из npm-пакета undici — встроенный fetch с его агентом
 * несовместим (UND_ERR_INVALID_ARG).
 */

import { fetch as undiciFetch, FormData as UndiciFormData, ProxyAgent } from "undici";

let cached: ProxyAgent | null | undefined;

export function telegramProxyUrl(): string {
  return (process.env.LEGAL_AI_HTTPS_PROXY || process.env.LEGAL_AI_HTTP_PROXY || "").trim();
}

function dispatcher(): ProxyAgent | undefined {
  if (cached === undefined) {
    const url = telegramProxyUrl();
    cached = url ? new ProxyAgent(url) : null;
  }
  return cached ?? undefined;
}

/** fetch для api.telegram.org: через прокси, если он задан. */
export const telegramFetch = ((input: string | URL, init?: RequestInit) => {
  const agent = dispatcher();
  return undiciFetch(input, {
    ...(init as Parameters<typeof undiciFetch>[1]),
    ...(agent ? { dispatcher: agent } : {}),
  }) as unknown as Promise<Response>;
}) as typeof fetch;

/**
 * Форма для multipart-запроса к Telegram. Из того же undici, что и fetch:
 * встроенный FormData для npm-undici — чужой класс, и тело ушло бы строкой.
 */
export function telegramFormData(): FormData {
  return new UndiciFormData() as unknown as FormData;
}
