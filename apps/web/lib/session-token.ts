import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Автономный вход — минуя Telegram, второй фактор к initData.
 *
 * Внутри Telegram подпись initData делает сам клиент Telegram: она есть
 * всегда, пока страница открыта в его WebView или пришла по OAuth-редиректу.
 * Вне Telegram (иконка на экране iPhone, обычная вкладка Safari) initData
 * нет вовсе — эту дверь приходится делать самим.
 *
 * Токен — обычный bearer, подписан HMAC общим секретом ролью (у юриста —
 * LAWYER_SESSION_SECRET, у клиента — CLIENT_SESSION_SECRET, разные и не
 * взаимозаменяемые). Состояние на сервере не хранится: проверка — это
 * пересчитать подпись и сравнить.
 *
 * Отсутствие состояния — это и ограничение: отозвать один-единственный
 * скомпрометированный токен, не трогая остальные, нельзя. Для небольшого
 * числа пользователей это разумный размен — секрет просто перевыпускается
 * (docs/runbook.md), и все токены этой роли разом перестают работать.
 *
 * Модуль общий для lawyer-session-token.ts (roleSecret = LAWYER_SESSION_SECRET,
 * maxAge 30д) и client-session.ts (roleSecret = CLIENT_SESSION_SECRET, maxAge
 * 7д) — сам формат токена <id>.<issuedAt>.<hex-hmac> ничего не знает про роль.
 */

export type SessionTokenResult = { telegramUserId: number; issuedAt: number };

function dataToSign(telegramUserId: number, issuedAt: number): string {
  return `${telegramUserId}.${issuedAt}`;
}

function sign(payload: string, secret: string): string {
  return createHmac("sha256", secret).update(payload).digest("hex");
}

/** Собирает токен. Используется тестами и как образец для боевого mint на стороне бота. */
export function mintSessionToken(
  telegramUserId: number,
  secret: string,
  issuedAt: number = Math.floor(Date.now() / 1000),
): string {
  const payload = dataToSign(telegramUserId, issuedAt);
  return `${payload}.${sign(payload, secret)}`;
}

export function verifySessionToken(
  token: string,
  secret: string,
  maxAgeSeconds: number,
  now: number = Math.floor(Date.now() / 1000),
): SessionTokenResult | null {
  const parts = (token || "").split(".");
  if (parts.length !== 3) return null;
  const [idPart, issuedAtPart, signaturePart] = parts;

  const telegramUserId = Number(idPart);
  const issuedAt = Number(issuedAtPart);
  if (!Number.isFinite(telegramUserId) || telegramUserId <= 0) return null;
  if (!Number.isFinite(issuedAt) || issuedAt <= 0) return null;
  if (!/^[0-9a-f]{64}$/i.test(signaturePart)) return null;

  const expected = sign(dataToSign(telegramUserId, issuedAt), secret);
  const provided = Buffer.from(signaturePart, "hex");
  const expectedBuf = Buffer.from(expected, "hex");
  if (provided.length !== expectedBuf.length || !timingSafeEqual(provided, expectedBuf)) {
    return null;
  }

  if (now - issuedAt > maxAgeSeconds) return null;
  // Токен не должен быть "из будущего" — небольшой допуск на рассинхрон часов.
  if (issuedAt - now > 60) return null;

  return { telegramUserId, issuedAt };
}
