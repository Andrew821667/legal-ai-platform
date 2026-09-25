import assert from "node:assert/strict";
import { test } from "node:test";

import { sanitizeReviews } from "./public-reviews.ts";

test("мусор отбрасывается, имя и оценка приводятся к безопасному виду", () => {
  const out = sanitizeReviews([
    { name: "Анна", score: 5, text: "Всё чётко и быстро", date: "2026-09-20" },
    { name: "", score: 9, text: "  Хорошо  ", date: "вчера" },
    { name: "Пётр", score: 4, text: "" },
    null,
    "строка",
  ]);
  assert.deepEqual(out, [
    { name: "Анна", score: 5, text: "Всё чётко и быстро", date: "2026-09-20" },
    { name: "Клиент", score: null, text: "Хорошо", date: null },
  ]);
});

test("длинный текст обрезается, количество ограничено", () => {
  const long = "а".repeat(1000);
  const out = sanitizeReviews(Array.from({ length: 10 }, () => ({ name: "Ира", score: 5, text: long })), 3);
  assert.equal(out.length, 3);
  assert.equal(out[0].text.length, 598);
  assert.ok(out[0].text.endsWith("…"));
});

test("не массив — пусто", () => {
  assert.deepEqual(sanitizeReviews({ detail: "Invalid API key" }), []);
});
