import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Одноразовая ссылка входа в рабочее место юриста.
 *
 * Раньше бот клал в ссылку сам токен сессии: ссылка была пропуском на 30
 * дней, открывалась сколько угодно раз и оседала в истории браузера и
 * журналах прокси. Теперь в ссылке — отдельный токен входа: короткий срок,
 * случайный nonce, своя подпись. /lawyer/login проверяет его здесь, гасит
 * nonce в ядре (второй раз не сработает) и выдаёт свою куку сессии — она в
 * адрес не попадает никогда.
 *
 * Формат: v2.<id>.<issuedAt>.<ttl>.<nonce>.<hex-hmac>, подпись — HMAC-SHA256
 * общим с ботом секретом (LAWYER_SESSION_SECRET) над
 * "lawyer-login.<id>.<issuedAt>.<ttl>.<nonce>". Префикс в подписи не даёт
 * выдать токен сессии за ссылку входа и наоборот. Пара на стороне бота —
 * apps/lead-bot/legacy/lawyer_session_link.py.
 */

/** Ссылка в кнопке Telegram живёт до следующего /admin — не дольше недели. */
export const LOGIN_TOKEN_MAX_TTL_SECONDS = 7 * 24 * 60 * 60;

export type LawyerLoginToken = {
  telegramUserId: number;
  issuedAt: number;
  ttl: number;
  nonce: string;
  expiresAt: number;
};

function sign(payload: string, secret: string): string {
  return createHmac("sha256", secret).update(`lawyer-login.${payload}`).digest("hex");
}

/** Для тестов и как образец для бота. */
export function mintLawyerLoginToken(
  telegramUserId: number,
  secret: string,
  { ttl, nonce, issuedAt = Math.floor(Date.now() / 1000) }: { ttl: number; nonce: string; issuedAt?: number },
): string {
  const payload = `${telegramUserId}.${issuedAt}.${ttl}.${nonce}`;
  return `v2.${payload}.${sign(payload, secret)}`;
}

export function verifyLawyerLoginToken(
  token: string,
  secret: string,
  now: number = Math.floor(Date.now() / 1000),
): LawyerLoginToken | null {
  if (!secret) return null;
  const parts = (token || "").split(".");
  if (parts.length !== 6 || parts[0] !== "v2") return null;
  const [, idPart, issuedPart, ttlPart, nonce, signature] = parts;
  if (!/^\d{1,15}$/.test(idPart) || !/^\d{1,12}$/.test(issuedPart) || !/^\d{1,9}$/.test(ttlPart)) return null;
  if (!/^[0-9a-f]{32}$/.test(nonce) || !/^[0-9a-f]{64}$/.test(signature)) return null;

  const expected = Buffer.from(sign(`${idPart}.${issuedPart}.${ttlPart}.${nonce}`, secret), "hex");
  const provided = Buffer.from(signature, "hex");
  if (provided.length !== expected.length || !timingSafeEqual(provided, expected)) return null;

  const telegramUserId = Number(idPart);
  const issuedAt = Number(issuedPart);
  const ttl = Number(ttlPart);
  if (telegramUserId <= 0 || ttl <= 0 || ttl > LOGIN_TOKEN_MAX_TTL_SECONDS) return null;
  if (issuedAt - now > 60) return null; // «из будущего» — часы бота и сайта на одной машине
  if (now > issuedAt + ttl) return null;
  return { telegramUserId, issuedAt, ttl, nonce, expiresAt: issuedAt + ttl };
}
