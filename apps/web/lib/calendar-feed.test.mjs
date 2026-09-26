import assert from "node:assert/strict";
import { test } from "node:test";

import { buildIcs, escapeText, feedToken, feedUrls, foldLine, verifyFeedToken } from "./calendar-feed.ts";

const events = [
  {
    uid: "intake-1",
    kind: "intake_deadline",
    date: "2026-10-01",
    title: "Срок по делу: Договоры и сделки · №ABC",
    lead_id: "11111111-2222-3333-4444-555555555555",
  },
  { uid: "act-2", kind: "act_payment_due", date: "2026-12-31", title: "Срок оплаты: акт AC-1", lead_id: null },
  { uid: "bad", kind: "x", date: "01.10.2026", title: "мусор", lead_id: null },
];

test("подпись адреса: своя для юриста и секрета, чужая и битая — отказ", () => {
  const token = feedToken("secret", 42);
  assert.equal(token.length, 40);
  assert.equal(verifyFeedToken("secret", 42, token), true);
  assert.equal(verifyFeedToken("secret", 43, token), false);
  assert.equal(verifyFeedToken("other", 42, token), false);
  assert.equal(verifyFeedToken("secret", 42, token.slice(0, 39)), false);
  assert.equal(verifyFeedToken("", 42, token), false);
  const urls = feedUrls("https://ai-verdict.ru/", 42, "secret");
  assert.equal(urls.https, `https://ai-verdict.ru/api/lawyer/calendar?u=42&t=${token}`);
  assert.ok(urls.webcal.startsWith("webcal://ai-verdict.ru/api/lawyer/calendar"));
});

test("экранирование и перенос длинных строк без разрыва кириллицы", () => {
  assert.equal(escapeText("a,b;c\\d\ne"), "a\\,b\\;c\\\\d\\ne");
  const line = `SUMMARY:${"Ж".repeat(60)}`;
  const folded = foldLine(line);
  for (const part of folded.split("\r\n")) assert.ok(Buffer.byteLength(part) <= 75, part);
  assert.equal(folded.split("\r\n").map((p, i) => (i ? p.slice(1) : p)).join(""), line);
});

test("лента: события на весь день с напоминаниями и ссылкой на карточку", () => {
  const ics = buildIcs(events, { now: new Date("2026-09-26T10:00:00Z"), origin: "https://ai-verdict.ru" });
  assert.ok(ics.startsWith("BEGIN:VCALENDAR\r\n") && ics.endsWith("END:VCALENDAR\r\n"));
  const unfolded = ics.replace(/\r\n /g, "");
  assert.match(unfolded, /DTSTART;VALUE=DATE:20261001\r\nDTEND;VALUE=DATE:20261002/);
  // Переход через год.
  assert.match(unfolded, /DTSTART;VALUE=DATE:20261231\r\nDTEND;VALUE=DATE:20270101/);
  assert.match(unfolded, /URL:https:\/\/ai-verdict.ru\/lawyer\?client=11111111-2222-3333-4444-555555555555/);
  assert.match(unfolded, /UID:intake-1@ai-verdict.ru/);
  assert.equal((unfolded.match(/BEGIN:VEVENT/g) || []).length, 2, "дата не в формате — событие пропущено");
  assert.equal((unfolded.match(/TRIGGER:-PT15H/g) || []).length, 2);
  assert.match(unfolded, /SUMMARY:Срок по делу: Договоры и сделки · №ABC/);
  assert.match(unfolded, /DTSTAMP:20260926T100000Z/);
});

test("консультация — событие со временем и напоминанием за час", () => {
  const ics = buildIcs(
    [{ uid: "consultation-1", kind: "consultation", date: "2026-10-01", title: "Консультация · код K-ABC123",
       lead_id: null, starts_at: "2026-10-01T12:00:00+00:00", duration_min: 60 }],
    { now: new Date("2026-09-26T10:00:00Z"), origin: "https://ai-verdict.ru" },
  ).replace(/\r\n /g, "");
  assert.match(ics, /DTSTART:20261001T120000Z\r\nDTEND:20261001T130000Z/);
  assert.match(ics, /TRIGGER:-PT1H/);
  assert.doesNotMatch(ics, /VALUE=DATE/);
});
