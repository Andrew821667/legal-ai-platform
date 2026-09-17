import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Подписанные значения для кук, которые несут не просто telegramUserId
 * (для этого есть session-token.ts), а произвольный JSON — короткоживущее
 * состояние OAuth-обмена (client_oauth: state/nonce/verifier/next) и
 * отображаемый профиль клиента (client_profile: имя/фото/маска телефона).
 *
 * Обе куки httpOnly, но домен ai-verdict.ru делит браузер с поддоменом
 * contract.ai-verdict.ru — другим приложением. Без подписи это создавало бы
 * почву для cookie tossing: чужое приложение на поддомене не может прочитать
 * httpOnly-куку сайта, но может ЗАПИСАТЬ куку с тем же именем на родительский
 * домен (Set-Cookie без Domain уязвим к этому по спецификации), и наш сервер
 * принял бы её как свою. HMAC поверх значения делает такую подделку
 * бессмысленной: подписи не будет.
 */

function sign(payload: string, secret: string): string {
  return createHmac("sha256", secret).update(payload).digest("hex");
}

export function sealCookieValue(payload: object, secret: string, now: number = Math.floor(Date.now() / 1000)): string {
  const body = Buffer.from(JSON.stringify({ ...payload, iat: now })).toString("base64url");
  return `${body}.${sign(body, secret)}`;
}

export function openCookieValue<T extends Record<string, unknown>>(
  raw: string,
  secret: string,
  maxAgeSeconds: number,
  now: number = Math.floor(Date.now() / 1000),
): (T & { iat: number }) | null {
  const value = (raw || "").trim();
  const dot = value.lastIndexOf(".");
  if (dot <= 0 || dot === value.length - 1) return null;
  const body = value.slice(0, dot);
  const signature = value.slice(dot + 1);
  if (!/^[0-9a-f]{64}$/i.test(signature)) return null;

  const expected = sign(body, secret);
  const provided = Buffer.from(signature, "hex");
  const expectedBuf = Buffer.from(expected, "hex");
  if (provided.length !== expectedBuf.length || !timingSafeEqual(provided, expectedBuf)) {
    return null;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(Buffer.from(body, "base64url").toString("utf8"));
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;
  const iat = (parsed as Record<string, unknown>).iat;
  if (typeof iat !== "number" || !Number.isFinite(iat) || iat <= 0) return null;
  if (now - iat > maxAgeSeconds) return null;
  if (iat - now > 60) return null;

  return parsed as T & { iat: number };
}
