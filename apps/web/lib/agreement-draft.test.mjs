import assert from "node:assert/strict";
import { test } from "node:test";

import { AGREEMENT_FIELDS, checkAgreementDraft } from "./agreement-draft.ts";

/** Заполненный по минимуму черновик — с ним ядро договор создаёт. */
function draft(overrides = {}) {
  const filled = {};
  for (const field of AGREEMENT_FIELDS) {
    filled[field.key] = "х".repeat(Math.max(field.min, 3));
  }
  return { ...filled, ...overrides };
}

test("заполненный черновик проходит", () => {
  const result = checkAgreementDraft(draft());
  assert.equal(result.ok, true);
  assert.deepEqual(Object.keys(result.value).sort(), AGREEMENT_FIELDS.map((f) => f.key).sort());
});

test("пустое поле не проходит и названо по-русски", () => {
  const result = checkAgreementDraft(draft({ price_text: "" }));
  assert.equal(result.ok, false);
  assert.match(result.detail, /Стоимость/);
});

test("слишком короткий предмет не проходит", () => {
  // У ядра здесь min_length=10: без этой проверки юрист получил бы разбор
  // Pydantic на английском вместо подсказки.
  const result = checkAgreementDraft(draft({ subject: "коротко" }));
  assert.equal(result.ok, false);
  assert.match(result.detail, /Предмет/);
});

test("слишком длинная стоимость не проходит", () => {
  const result = checkAgreementDraft(draft({ price_text: "9".repeat(501) }));
  assert.equal(result.ok, false);
  assert.match(result.detail, /не больше 500/);
});

test("пробелы по краям срезаются, а не засчитываются за длину", () => {
  const result = checkAgreementDraft(draft({ subject: `   ${"a".repeat(9)}   ` }));
  assert.equal(result.ok, false);
});

test("значение приходит обрезанным", () => {
  const result = checkAgreementDraft(draft({ price_text: "  10 000 ₽  " }));
  assert.equal(result.ok, true);
  assert.equal(result.value.price_text, "10 000 ₽");
});

test("посторонние поля не пролезают в ядро", () => {
  // Иначе через форму можно было бы дослать в ядро что угодно.
  const result = checkAgreementDraft(draft({ prepared_by_telegram_user_id: 1, expires_in_days: 30 }));
  assert.equal(result.ok, true);
  assert.equal(result.value.prepared_by_telegram_user_id, undefined);
  assert.equal(result.value.expires_in_days, undefined);
});

test("ограничения совпадают с ядром", () => {
  // Если в core-api поменяют схему, тест напомнит поправить и здесь.
  const limits = Object.fromEntries(AGREEMENT_FIELDS.map((f) => [f.key, [f.min, f.max]]));
  assert.deepEqual(limits, {
    subject: [10, 4000],
    scope_text: [10, 6000],
    exclusions_text: [2, 2000],
    schedule_text: [2, 2000],
    price_text: [2, 500],
    payment_terms: [2, 2000],
  });
});
