import assert from "node:assert/strict";
import { test } from "node:test";

import { checkSupplementDraft } from "./supplement-draft.ts";

const filled = {
  scope_text: "Подготовка и подача иска о взыскании неустойки",
  price_text: "150 000 ₽",
  amount: "150 000",
};

test("работы, новая стоимость и число — достаточно", () => {
  const result = checkSupplementDraft(filled);
  assert.equal(result.ok, true);
  assert.equal(result.value.amount_minor, 15_000_000);
  // Пустые сроки и оплата не уходят в ядро: там они значат «как в договоре».
  assert.equal("schedule_text" in result.value, false);
  assert.equal("payment_terms" in result.value, false);
});

test("без числа допсоглашение не составить — переносить в итоги нечего", () => {
  const result = checkSupplementDraft({ ...filled, amount: "" });
  assert.equal(result.ok, false);
  assert.match(result.detail, /новую общую стоимость/);
});

test("коротко описанные работы не проходят и названы по-русски", () => {
  const result = checkSupplementDraft({ ...filled, scope_text: "иск" });
  assert.equal(result.ok, false);
  assert.match(result.detail, /Дополнительные работы/);
});

test("пустая формулировка стоимости не проходит", () => {
  const result = checkSupplementDraft({ ...filled, price_text: " " });
  assert.equal(result.ok, false);
  assert.match(result.detail, /Новая стоимость/);
});
