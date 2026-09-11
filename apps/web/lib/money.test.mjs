import assert from "node:assert/strict";
import { test } from "node:test";

import { formatRub, parseRublesInput } from "./money.ts";

test("копейки становятся рублями с разделителем разрядов", () => {
  assert.equal(formatRub(1_000_000), "10 000 ₽");
  assert.equal(formatRub(100_000_000), "1 000 000 ₽");
  assert.equal(formatRub(1_250_050), "12 500,50 ₽");
  assert.equal(formatRub(500), "5 ₽");
});

test("нет суммы — прочерк, а не ноль", () => {
  // Ноль рублей и «не указано» — разные вещи: ноль сложится в итог молча.
  assert.equal(formatRub(null), "—");
  assert.equal(formatRub(undefined), "—");
  assert.equal(formatRub(0), "0 ₽");
});

test("ввод юриста разбирается в копейки", () => {
  assert.deepEqual(parseRublesInput("10 000"), { ok: true, minor: 1_000_000 });
  assert.deepEqual(parseRublesInput("10000"), { ok: true, minor: 1_000_000 });
  assert.deepEqual(parseRublesInput("12 500,50"), { ok: true, minor: 1_250_050 });
  assert.deepEqual(parseRublesInput("12500.5"), { ok: true, minor: 1_250_050 });
  assert.deepEqual(parseRublesInput("10 000 ₽"), { ok: true, minor: 1_000_000 });
  assert.deepEqual(parseRublesInput("10000 руб"), { ok: true, minor: 1_000_000 });
});

test("пусто — это «не указана»", () => {
  assert.deepEqual(parseRublesInput(""), { ok: true, minor: null });
  assert.deepEqual(parseRublesInput(null), { ok: true, minor: null });
});

test("не число — понятная подсказка, а не ноль", () => {
  for (const junk of ["десять тысяч", "10 тысяч", "от 50 000", "10.000.000", "-5"]) {
    const result = parseRublesInput(junk);
    assert.equal(result.ok, false, junk);
  }
});

test("формат и разбор — обратные друг другу", () => {
  for (const minor of [1_000_000, 1_250_050, 500, 100_000_000]) {
    const back = parseRublesInput(formatRub(minor));
    assert.equal(back.ok && back.minor, minor);
  }
});
