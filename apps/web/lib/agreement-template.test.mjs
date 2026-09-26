import assert from "node:assert/strict";
import { test } from "node:test";

import { draftToTemplate, templateToDraft, templateWithPackage } from "./agreement-template.ts";

const template = {
  template_id: "t1",
  name: "Проверка договора",
  practice: "legal",
  subject: "Правовой анализ договора",
  scope_text: "Изучить договор",
  exclusions_text: "Переговоры",
  schedule_text: "Три дня",
  price_text: "15 000 ₽",
  amount_minor: 1_500_000,
  payment_terms: "100% вперёд",
  use_count: 0,
};

test("заготовка заполняет все поля формы и сумму в рублях", () => {
  const draft = templateToDraft(template);
  assert.equal(draft.subject, "Правовой анализ договора");
  assert.equal(draft.price_text, "15 000 ₽");
  assert.equal(draft.amount, "15000");
  assert.equal(templateToDraft({ ...template, amount_minor: null }).amount, "");
});

test("из формы — заготовка с суммой в копейках", () => {
  const result = draftToTemplate(templateToDraft(template), "  Проверка  ", "legal");
  assert.equal(result.ok, true);
  assert.equal(result.value.name, "Проверка");
  assert.equal(result.value.amount_minor, 1_500_000);
  assert.equal(result.value.scope_text, "Изучить договор");
});

test("без имени, с пустой формой или неверной суммой — не сохраняем", () => {
  assert.equal(draftToTemplate(templateToDraft(template), " ", "legal").ok, false);
  assert.equal(draftToTemplate({}, "Пустая", null).ok, false);
  assert.equal(draftToTemplate({ subject: "Тема", amount: "много" }, "Имя", null).ok, false);
});

test("заготовка привязывается к пакету сайта, остальное не меняется", () => {
  const body = templateWithPackage(template, "legal_contract_review");
  assert.equal(body.package_id, "legal_contract_review");
  assert.equal(body.subject, "Правовой анализ договора");
  assert.equal(body.amount_minor, 1_500_000);
  assert.equal(templateWithPackage(template, "").package_id, null);
  const saved = draftToTemplate(templateToDraft(template), "Проверка", "legal", "legal_contract_review");
  assert.equal(saved.value.package_id, "legal_contract_review");
  assert.equal(draftToTemplate(templateToDraft(template), "Проверка", "legal").value.package_id, null);
});
