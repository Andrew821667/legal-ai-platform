import { openClientAccount, verifyClientSessionToken } from "./client-session.ts";

/**
 * Объединение входа через Яндекс ID с Telegram — правила сайта (без Next).
 *
 * Два способа доказать, что оба входа — одного человека:
 *  • код из бота (/link): его видит только владелец Telegram, вводит сам в
 *    кабинете — проверяет ядро;
 *  • обе сессии в одном браузере. Но кука живёт 7 дней, и на общем
 *    компьютере в браузере может остаться чужой вход. Поэтому объединяем по
 *    сессиям, только если ОБА входа свежие — сделаны за последние 15 минут:
 *    человек только что подтвердил и Telegram, и Яндекс ID.
 */

export const LINK_FRESH_SECONDS = 15 * 60;

export type BothSessions = {
  telegramUserId: number;
  accountId: string;
  email: string | null;
  telegramFresh: boolean;
  accountFresh: boolean;
};

export function readBothSessions({
  sessionCookie,
  accountCookie,
  secret,
  now = Math.floor(Date.now() / 1000),
}: {
  sessionCookie: string;
  accountCookie: string;
  secret: string;
  now?: number;
}): BothSessions | null {
  if (!secret.trim()) return null;
  const telegram = verifyClientSessionToken(sessionCookie, secret, now);
  const account = openClientAccount(accountCookie, secret, now);
  if (!telegram || !account) return null;
  return {
    telegramUserId: telegram.telegramUserId,
    accountId: account.accountId,
    email: account.email,
    telegramFresh: now - telegram.issuedAt <= LINK_FRESH_SECONDS,
    accountFresh: now - account.issuedAt <= LINK_FRESH_SECONDS,
  };
}

/** Код из бота: как ввёл человек — ядро само уберёт пробелы, дефис и регистр. */
export function cleanLinkCode(raw: unknown): string {
  return typeof raw === "string" ? raw.trim().slice(0, 32) : "";
}

export function maskEmail(email: string | null | undefined): string {
  const [local, domain] = String(email || "").split("@");
  return domain ? `${local.slice(0, 1)}***@${domain}` : "";
}
