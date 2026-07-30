import { createHash } from "node:crypto";

import bcrypt from "bcryptjs";

const BCRYPT_ROUNDS = 12;

export function hashAdminSecret(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

export function hashAdminPassword(password: string): string {
  return bcrypt.hashSync(password.normalize("NFKC"), BCRYPT_ROUNDS);
}

export function verifyAdminPassword(password: string, storedHash: string): boolean {
  if (!storedHash) {
    return false;
  }
  return bcrypt.compareSync(password.normalize("NFKC"), storedHash);
}

/**
 * Достаёт адрес клиента из X-Forwarded-For.
 *
 * Берётся ПОСЛЕДНИЙ элемент списка, а не первый. Заголовок формируется как
 * "<присланное клиентом>, <адрес, добавленный обратным прокси>", то есть всё,
 * кроме последнего элемента, подконтрольно отправителю запроса. Если брать
 * первый элемент, атакующий подставляет произвольное значение на каждом
 * запросе, получает новый ключ троттлинга и обходит лимит попыток входа.
 */
function extractClientIp(headers: Headers): string {
  const forwarded = String(headers.get("x-forwarded-for") || "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  const fromProxy = forwarded.length > 0 ? forwarded[forwarded.length - 1] : "";
  const real = String(headers.get("x-real-ip") || "").trim();
  return (fromProxy || real || "unknown").slice(0, 120);
}

export function resolveAdminClientContext(headers: Headers): {
  clientKey: string;
  ipHash: string;
  userAgentHash: string;
} {
  const ip = extractClientIp(headers);
  const userAgent = String(headers.get("user-agent") || "unknown").slice(0, 500);
  const ipHash = hashAdminSecret(`ip:${ip}`);
  const userAgentHash = hashAdminSecret(`ua:${userAgent}`);
  return {
    // Ключ троттлинга считается только по адресу. User-Agent сюда не входит:
    // он меняется одной строкой в запросе, и любой перебор превращался бы в
    // цепочку "новых" клиентов. Хеш User-Agent остаётся для журнала аудита.
    clientKey: ipHash,
    ipHash,
    userAgentHash,
  };
}
