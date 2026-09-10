import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Решение о доступе к рабочему месту юриста.
 *
 * Модуль намеренно ничего не знает про Next: проверка подписи и права — это
 * логика, а не транспорт. Пока она была сцеплена с NextResponse, её нельзя было
 * покрыть тестом, а непроверяемая проверка доступа — самое неудачное место для
 * доверия к себе.
 *
 * Обёртка над HTTP живёт в lawyer-auth.ts.
 */

const DEFAULT_MAX_AGE_SECONDS = 60 * 60;

export type AccessOk = { ok: true; telegramUserId: number };
export type AccessDenied = { ok: false; status: 401 | 403 | 500; detail: string };
export type AccessResult = AccessOk | AccessDenied;

export type AccessInput = {
  initData: string;
  botToken: string;
  allowedIds: number[];
  maxAgeSeconds?: number;
  now?: number;
};

function dataCheckString(params: URLSearchParams): string {
  const rows: string[] = [];
  params.forEach((value, key) => {
    if (key !== "hash") {
      rows.push(`${key}=${value}`);
    }
  });
  rows.sort();
  return rows.join("\n");
}

function parseUserId(raw: string | null): number | null {
  if (!raw) return null;
  try {
    const value = Number((JSON.parse(raw) as { id?: unknown }).id);
    return Number.isFinite(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

export function parseAllowedIds(...sources: (string | undefined)[]): number[] {
  return sources
    .join(",")
    .split(",")
    .map((part) => Number(part.trim()))
    .filter((value) => Number.isFinite(value) && value > 0);
}

export function checkLawyerAccess({
  initData,
  botToken,
  allowedIds,
  maxAgeSeconds = DEFAULT_MAX_AGE_SECONDS,
  now = Math.floor(Date.now() / 1000),
}: AccessInput): AccessResult {
  if (!initData.trim()) {
    return { ok: false, status: 401, detail: "Требуется вход через Telegram" };
  }
  if (!botToken.trim()) {
    // Проверить подпись нечем. Пропустить запрос в таком случае значило бы
    // отдать данные клиентов любому, кто знает адрес.
    return {
      ok: false,
      status: 500,
      detail: "Сервер не настроен: нет токена бота для проверки подписи",
    };
  }

  const params = new URLSearchParams(initData);
  const providedHash = params.get("hash") || "";
  if (!/^[0-9a-f]{64}$/i.test(providedHash)) {
    return { ok: false, status: 401, detail: "Подпись Telegram недействительна" };
  }

  const secret = createHmac("sha256", "WebAppData").update(botToken).digest();
  const expected = createHmac("sha256", secret).update(dataCheckString(params)).digest();
  const provided = Buffer.from(providedHash, "hex");
  if (provided.length !== expected.length || !timingSafeEqual(provided, expected)) {
    return { ok: false, status: 401, detail: "Подпись Telegram недействительна" };
  }

  // Устаревшие данные не принимаем: перехваченный initData иначе работал бы
  // вечно.
  const authDate = Number(params.get("auth_date"));
  if (!Number.isFinite(authDate) || authDate <= 0 || now - authDate > maxAgeSeconds) {
    return { ok: false, status: 401, detail: "Данные входа устарели" };
  }

  const telegramUserId = parseUserId(params.get("user"));
  if (telegramUserId === null) {
    return { ok: false, status: 401, detail: "Подпись Telegram недействительна" };
  }

  if (!allowedIds.includes(telegramUserId)) {
    // Подпись честная — человек действительно открыл мини-апп из Telegram.
    // Но данные клиентов практики ему видеть незачем.
    return { ok: false, status: 403, detail: "Раздел доступен только юристу практики" };
  }

  return { ok: true, telegramUserId };
}
