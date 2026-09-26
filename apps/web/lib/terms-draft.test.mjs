import assert from "node:assert/strict";
import { test } from "node:test";

import { mergeTermsDraft, termsDraftSummary } from "./terms-draft.ts";

const draft = {
  fields: {
    subject: "Правовой анализ договора аренды",
    scope_text: "1. Изучить договор.\n2. Подготовить замечания.",
    exclusions_text: "Переговоры",
    schedule_text: "Пять рабочих дней",
    price_text: "15 000 ₽",
    payment_terms: "100% до начала работы",
  },
  amount_minor: 1_500_000,
  template: { template_id: "t1", name: "Проверка договора" },
  notes: [],
};

test("черновик заполняет пустую форму и сумму в рублях", () => {
  const merge = mergeTermsDraft({}, draft);
  assert.equal(merge.values.subject, "Правовой анализ договора аренды");
  assert.equal(merge.values.amount, "15000");
  assert.equal(merge.filled.length, 6);
  assert.match(termsDraftSummary(merge, draft.template), /заготовка «Проверка договора»/);
});

test("набранное юристом не затирается, в том числе сумма", () => {
  const merge = mergeTermsDraft({ subject: "Моя формулировка предмета", amount: "20000" }, draft);
  assert.equal(merge.values.subject, "Моя формулировка предмета");
  assert.equal(merge.values.amount, "20000");
  assert.deepEqual(merge.kept, ["Предмет"]);
  assert.match(termsDraftSummary(merge, null), /Не тронуто набранное: предмет/);
});

test("без заготовки стоимость и оплата остаются юристу", () => {
  const merge = mergeTermsDraft(
    {},
    { ...draft, fields: { ...draft.fields, price_text: "", payment_terms: "" }, amount_minor: null, template: null },
  );
  assert.equal(merge.values.price_text, undefined);
  assert.equal(merge.values.amount, undefined);
  assert.deepEqual(merge.empty, ["Стоимость", "Оплата"]);
  assert.match(termsDraftSummary(merge, null), /Укажите сами: стоимость, оплата/);
});

test("заполненная форма — подсказка, как получить предложение заново", () => {
  const full = Object.fromEntries(Object.keys(draft.fields).map((key) => [key, "уже есть"]));
  const merge = mergeTermsDraft(full, draft);
  assert.equal(merge.filled.length, 0);
  assert.match(termsDraftSummary(merge, null), /очистите/);
});
