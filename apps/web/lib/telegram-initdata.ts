import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Проверка подписи initData мини-аппа — без Next.
 *
 * Вынесено из telegram-webapp-auth.ts ради тестов: тот модуль тянет
 * next/server, который тест-раннер не поднимает. Здесь только криптография
 * и разбор строки — то, что и нужно проверять.
 */

export const TELEGRAM_INIT_DATA_HEADER = "x-telegram-init-data";

const DEFAULT_MAX_AGE_SECONDS = 60 * 60;

type TelegramWebAppUser = {
  id?: unknown;
};

export type VerificationResult = {
  telegramUserId: number;
};

function buildDataCheckString(params: URLSearchParams): string {
  const rows: string[] = [];
  params.forEach((value, key) => {
    if (key === "hash") {
      return;
    }
    rows.push(`${key}=${value}`);
  });
  rows.sort();
  return rows.join("\n");
}

function getAuthMaxAgeSeconds(): number {
  const parsed = Number(process.env.MINIAPP_TELEGRAM_AUTH_MAX_AGE_SECONDS || DEFAULT_MAX_AGE_SECONDS);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_MAX_AGE_SECONDS;
  }
  return Math.round(parsed);
}

/**
 * Боты, из которых открывают мини-апп.
 *
 * Мини-апп писался для бота-ридера, и подпись проверялась только его
 * токеном. Но кнопка «📱 Мини-апп» на постоянной клавиатуре бота-ассистента
 * тоже ведёт сюда, а Telegram подписывает initData токеном того бота, из
 * которого открыли, — и клиент ассистента получал «Invalid initData»,
 * не сделав ничего плохого. Подпись сходится с одним из токенов — вход есть.
 */
export function getMiniAppBotTokens(): string[] {
  const tokens = [
    process.env.READER_BOT_TOKEN,
    process.env.LEAD_BOT_TOKEN,
    process.env.TELEGRAM_BOT_TOKEN,
  ]
    .map((value) => (value || "").trim())
    .filter(Boolean);
  return Array.from(new Set(tokens));
}

export function allowUnverifiedMiniAppAuth(): boolean {
  return process.env.MINIAPP_ALLOW_UNVERIFIED === "1";
}

export function requireMiniAppTelegramAuth(): boolean {
  const raw = String(process.env.MINIAPP_REQUIRE_TELEGRAM_AUTH || "").trim().toLowerCase();
  if (!raw) {
    return true;
  }
  return raw !== "0" && raw !== "false" && raw !== "no";
}

function parseTelegramUserId(rawUser: string | null): number | null {
  if (!rawUser) {
    return null;
  }
  let parsed: TelegramWebAppUser;
  try {
    parsed = JSON.parse(rawUser) as TelegramWebAppUser;
  } catch {
    return null;
  }
  const value = Number(parsed.id);
  if (!Number.isFinite(value) || value <= 0) {
    return null;
  }
  return value;
}

export function verifyTelegramWebAppInitData(initData: string, botToken: string): VerificationResult | null {
  const params = new URLSearchParams(initData);
  const hash = (params.get("hash") || "").trim().toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(hash)) {
    return null;
  }

  const authDateRaw = Number(params.get("auth_date") || "0");
  if (!Number.isFinite(authDateRaw) || authDateRaw <= 0) {
    return null;
  }

  const now = Math.floor(Date.now() / 1000);
  const maxAgeSeconds = getAuthMaxAgeSeconds();
  if (authDateRaw > now + 60 || now - authDateRaw > maxAgeSeconds) {
    return null;
  }

  const telegramUserId = parseTelegramUserId(params.get("user"));
  if (!telegramUserId) {
    return null;
  }

  const dataCheckString = buildDataCheckString(params);
  const secretKey = createHmac("sha256", "WebAppData").update(botToken).digest();
  const expectedHash = createHmac("sha256", secretKey).update(dataCheckString).digest("hex");

  const expectedBytes = Buffer.from(expectedHash, "hex");
  const providedBytes = Buffer.from(hash, "hex");
  if (expectedBytes.length !== providedBytes.length) {
    return null;
  }
  if (!timingSafeEqual(expectedBytes, providedBytes)) {
    return null;
  }

  return { telegramUserId };
}

/** Подпись должна сойтись хотя бы с одним ботом из тех, что открывают мини-апп. */
export function verifyTelegramWebAppInitDataWithAny(
  initData: string,
  botTokens: string[],
): VerificationResult | null {
  for (const token of botTokens) {
    const result = verifyTelegramWebAppInitData(initData, token);
    if (result) return result;
  }
  return null;
}

