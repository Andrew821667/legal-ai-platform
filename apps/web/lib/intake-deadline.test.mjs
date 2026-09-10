import assert from "node:assert/strict";
import { test } from "node:test";

import { normalizeDeadline } from "./intake-deadline.ts";

test("день превращается в конец этого дня", () => {
  // Не в полночь: иначе весь день, когда срок ещё не нарушен, показывался бы
  // как просроченный.
  const result = normalizeDeadline("2026-09-17");
  assert.equal(result.ok, true);
  assert.equal(result.value, "2026-09-17T23:59:59Z");
});

test("пусто — это снятие срока, а не ошибка", () => {
  for (const empty of ["", null, undefined]) {
    const result = normalizeDeadline(empty);
    assert.equal(result.ok, true, String(empty));
    assert.equal(result.value, null);
  }
});

test("несуществующая дата не проходит", () => {
  // Date молча переносит 31 февраля на март — без проверки срок уехал бы
  // на несколько дней, и никто бы не заметил.
  const result = normalizeDeadline("2026-02-31");
  assert.equal(result.ok, false);
  assert.match(result.detail, /не существует/);
});

test("29 февраля високосного года проходит", () => {
  assert.equal(normalizeDeadline("2028-02-29").ok, true);
});

test("29 февраля невисокосного — нет", () => {
  assert.equal(normalizeDeadline("2027-02-29").ok, false);
});

test("свободный текст не принимается", () => {
  for (const junk of ["к четвергу", "17.09.2026", "2026-9-7", "2026-09-17T10:00:00Z"]) {
    const result = normalizeDeadline(junk);
    assert.equal(result.ok, false, junk);
  }
});
