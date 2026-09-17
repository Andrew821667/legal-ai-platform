import { createHash, createHmac, timingSafeEqual } from "node:crypto";

import { profileFromWidgetParams, type TelegramLoginProfile } from "./telegram-login-profile.ts";

/**
 * Проверка legacy iframe-виджета Telegram Login (telegram-widget.js) —
 * запасной режим (TELEGRAM_LOGIN_MODE=legacy) на случай, если Login Widget
 * в @BotFather недоступен для этого бота. Отличие от подписи Mini App
 * (telegram-initdata.ts): там ключ — HMAC("WebAppData", botToken), здесь —
 * прямой SHA256(botToken). Разные механизмы Telegram, разные ключи; спутать
 * их — значит принять данные, для которых подписи вообще не считали так.
 */

const DEFAULT_MAX_AGE_SECONDS = 600;

function dataCheckString(params: URLSearchParams): string {
  const rows: string[] = [];
  params.forEach((value, key) => {
    if (key !== "hash") rows.push(`${key}=${value}`);
  });
  rows.sort();
  return rows.join("\n");
}

export function verifyTelegramLoginWidget(
  params: URLSearchParams,
  botToken: string,
  opts: { maxAgeSeconds?: number; now?: number } = {},
): TelegramLoginProfile | null {
  if (!botToken.trim()) return null;

  const seen = new Set<string>();
  for (const [key] of params) {
    if (seen.has(key)) return null;
    seen.add(key);
  }

  const providedHash = (params.get("hash") || "").trim().toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(providedHash)) return null;

  const key = createHash("sha256").update(botToken).digest();
  const expected = createHmac("sha256", key).update(dataCheckString(params)).digest();
  const provided = Buffer.from(providedHash, "hex");
  if (provided.length !== expected.length || !timingSafeEqual(provided, expected)) {
    return null;
  }

  const maxAgeSeconds = opts.maxAgeSeconds ?? DEFAULT_MAX_AGE_SECONDS;
  const now = opts.now ?? Math.floor(Date.now() / 1000);
  const authDate = Number(params.get("auth_date"));
  if (!Number.isFinite(authDate) || authDate <= 0) return null;
  if (now - authDate > maxAgeSeconds) return null;
  // Допуск на рассинхрон часов — тот же принцип, что у session-token.ts.
  if (authDate - now > 60) return null;

  const telegramUserId = Number(params.get("id"));
  if (!Number.isSafeInteger(telegramUserId) || telegramUserId <= 0) return null;

  return profileFromWidgetParams(params);
}
