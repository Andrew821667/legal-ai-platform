import assert from "node:assert/strict";
import { test } from "node:test";

import {
  BOOKING_TOKEN,
  groupByDay,
  minutesLeft,
  moscowStarts,
  parseTimes,
  statusText,
  timeLabel,
} from "./consultation.ts";

test("время по Москве и группировка по московским дням", () => {
  // 21:30 UTC 1 октября — в Москве уже 2 октября, 00:30.
  const slots = [
    { slot_id: "b", starts_at: "2026-10-01T21:30:00Z", duration_min: 60 },
    { slot_id: "a", starts_at: "2026-10-01T09:00:00Z", duration_min: 60 },
  ];
  const groups = groupByDay(slots);
  assert.deepEqual(groups.map((g) => [g.day, g.slots.map((s) => s.slot_id)]), [
    ["2026-10-01", ["a"]],
    ["2026-10-02", ["b"]],
  ]);
  assert.equal(timeLabel("2026-10-01T09:00:00Z"), "12:00");
  assert.match(groups[0].label, /^Чт, 1 октября$/);
});

test("юрист вводит время как удобно — получаем порядок без повторов", () => {
  assert.deepEqual(parseTimes("15, 10:00; 11.30  10:00 25:00 9:61 abc"), ["10:00", "11:30", "15:00"]);
  assert.deepEqual(moscowStarts("2026-10-01", ["10:00"]), ["2026-10-01T10:00:00+03:00"]);
  assert.deepEqual(moscowStarts("01.10.2026", ["10:00"]), []);
});

test("статус брони и остаток времени", () => {
  const now = new Date("2026-09-26T10:00:00Z");
  const held = { slot_id: "s", starts_at: "", duration_min: 60, status: "held", price_minor: 490000, code: "K-1",
    held_until: "2026-09-26T10:12:30Z" };
  assert.equal(minutesLeft(held.held_until, now), 13);
  assert.match(statusText(held, now), /ещё 13 мин/);
  assert.match(statusText({ ...held, held_until: "2026-09-26T09:00:00Z" }, now), /истекло/);
  assert.match(statusText({ ...held, status: "claimed" }, now), /сверит поступление/);
  assert.match(statusText({ ...held, status: "confirmed" }, now), /подтверждена/);
  assert.ok(BOOKING_TOKEN.test("a".repeat(32)) && !BOOKING_TOKEN.test("../x"));
});
