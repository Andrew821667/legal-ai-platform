import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Автономный вход в рабочее место — минуя Telegram.
 *
 * Внутри Telegram подпись initData делает сам клиент Telegram: она есть
 * всегда, пока страница открыта в его WebView. Вне Telegram (иконка на
 * экране iPhone, обычная вкладка Safari) initData нет вовсе — эту дверь
 * приходится делать самим.
 *
 * Токен выдаёт бот: только он знает Telegram-аккаунт владельца, и только
 * через него можно нажать кнопку и получить ссылку. Дальше токен живёт как
 * обычный bearer — подписан HMAC общим секретом (LAWYER_SESSION_SECRET,
 * один и тот же в .env бота и веба), состояние на сервере не хранится:
 * проверка — это пересчитать подпись и сравнить.
 *
 * Отсутствие состояния — это и ограничение: отозвать один-единственный
 * скомпрометированный токен, не трогая остальные, нельзя. Для одного или
 * двух пользователей это разумный размен — при потере телефона секрет
 * просто перевыпускается (docs/runbook.md), и все токены разом перестают
 * работать.
 */

export type SessionTokenResult = { telegramUserId: number; issuedAt: number };

function dataToSign(telegramUserId: number, issuedAt: number): string {
  return `${telegramUserId}.${issuedAt}`;
}

function sign(payload: string, secret: string): string {
  return createHmac("sha256", secret).update(payload).digest("hex");
}

/** Собирает токен. Используется тестами и как образец для боевого mint на стороне бота. */
export function mintLawyerSessionToken(
  telegramUserId: number,
  secret: string,
  issuedAt: number = Math.floor(Date.now() / 1000),
): string {
  const payload = dataToSign(telegramUserId, issuedAt);
  return `${payload}.${sign(payload, secret)}`;
}

export function verifyLawyerSessionToken(
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
