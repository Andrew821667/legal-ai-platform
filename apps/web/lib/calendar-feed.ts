/**
 * Сроки практики — подпиской в календарь телефона (ICS, RFC 5545).
 *
 * Календарь забирает ленту сам, без входа, поэтому доступ — секрет в адресе,
 * как у «секретного адреса» Google Календаря. Секрет не хранится: это HMAC
 * от id юриста на секрете сессии рабочего места с отдельной меткой —
 * сменили LAWYER_SESSION_SECRET, и все выданные адреса перестали работать
 * вместе с сессиями.
 *
 * Модуль без Next — чтобы тестировать сборку ICS и проверку подписи.
 */

import { createHmac, timingSafeEqual } from "node:crypto";

export type CalendarEvent = {
  uid: string;
  kind: string;
  /** Дата срока по Москве, YYYY-MM-DD. */
  date: string;
  title: string;
  lead_id: string | null;
};

const LABEL = "calendar-feed:v1:";

export function feedToken(secret: string, lawyerId: number): string {
  return createHmac("sha256", secret).update(`${LABEL}${lawyerId}`).digest("hex").slice(0, 40);
}

export function verifyFeedToken(secret: string, lawyerId: number, token: string): boolean {
  if (!secret || !/^[0-9a-f]{40}$/.test(token)) return false;
  const expected = Buffer.from(feedToken(secret, lawyerId));
  const given = Buffer.from(token);
  return expected.length === given.length && timingSafeEqual(expected, given);
}

export function feedUrls(origin: string, lawyerId: number, secret: string): { https: string; webcal: string } {
  const https = `${origin.replace(/\/$/, "")}/api/lawyer/calendar?u=${lawyerId}&t=${feedToken(secret, lawyerId)}`;
  return { https, webcal: https.replace(/^https?:/, "webcal:") };
}

/** Экранирование текстового значения ICS. */
export function escapeText(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
}

/**
 * Перенос строки длиннее 75 байт: продолжение начинается с пробела. Режем
 * по байтам UTF-8, но не посреди символа — иначе кириллица превратится в
 * мусор в календаре.
 */
export function foldLine(line: string): string {
  const parts: string[] = [];
  let current = "";
  let bytes = 0;
  for (const char of line) {
    const size = Buffer.byteLength(char);
    const limit = parts.length === 0 ? 75 : 74; // у продолжения первый байт — пробел
    if (bytes + size > limit) {
      parts.push(current);
      current = "";
      bytes = 0;
    }
    current += char;
    bytes += size;
  }
  parts.push(current);
  return parts.join("\r\n ");
}

const compactDate = (iso: string) => iso.replace(/-/g, "");

function nextDay(iso: string): string {
  const date = new Date(`${iso}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}

function stamp(now: Date): string {
  return now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

export function buildIcs(events: CalendarEvent[], options: { now: Date; origin: string }): string {
  const origin = options.origin.replace(/\/$/, "");
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//AI Verdict//Сроки практики//RU",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:AI Verdict — сроки",
    "X-WR-TIMEZONE:Europe/Moscow",
    // Как часто календарю перечитывать ленту: срок могли перенести.
    "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
    "X-PUBLISHED-TTL:PT1H",
  ];
  for (const event of events) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(event.date)) continue;
    const url = event.lead_id ? `${origin}/lawyer?client=${encodeURIComponent(event.lead_id)}` : `${origin}/lawyer`;
    const title = escapeText(event.title);
    lines.push(
      "BEGIN:VEVENT",
      `UID:${event.uid}@ai-verdict.ru`,
      `DTSTAMP:${stamp(options.now)}`,
      `DTSTART;VALUE=DATE:${compactDate(event.date)}`,
      `DTEND;VALUE=DATE:${compactDate(nextDay(event.date))}`,
      `SUMMARY:${title}`,
      `DESCRIPTION:${escapeText(`Карточка клиента: ${url}`)}`,
      `URL:${url}`,
      "TRANSP:TRANSPARENT",
      // Напоминания: накануне в 9:00 и в сам день в 9:00 (событие на весь день
      // начинается в полночь).
      "BEGIN:VALARM",
      "ACTION:DISPLAY",
      `DESCRIPTION:Завтра: ${title}`,
      "TRIGGER:-PT15H",
      "END:VALARM",
      "BEGIN:VALARM",
      "ACTION:DISPLAY",
      `DESCRIPTION:Сегодня: ${title}`,
      "TRIGGER:PT9H",
      "END:VALARM",
      "END:VEVENT",
    );
  }
  lines.push("END:VCALENDAR");
  return lines.map(foldLine).join("\r\n") + "\r\n";
}
