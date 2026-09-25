import assert from "node:assert/strict";
import { test } from "node:test";

import { translateCoreDetail, translateCoreErrorBody } from "./core-errors.ts";

test("известный отказ ядра — по-русски", () => {
  assert.equal(
    translateCoreDetail("Only a signed agreement takes a supplement; change an unsigned one with a new revision"),
    "Допсоглашение — только к подписанному договору. Неподписанный меняется новой редакцией.",
  );
  assert.equal(translateCoreDetail("NDA must be signed first"), "Сначала клиент должен подписать соглашение о конфиденциальности.");
});

test("ошибка отправки с именем исключения — по префиксу", () => {
  assert.match(String(translateCoreDetail("Telegram delivery failed: ConnectTimeout")), /Telegram не принял сообщение/);
});

test("ошибки проверки полей — с русскими названиями полей", () => {
  const detail = [
    { loc: ["body", "price_text"], msg: "String should have at most 500 characters" },
    { loc: ["body", "scope_text"], msg: "too short" },
  ];
  assert.equal(translateCoreDetail(detail), "Проверьте поля: «Стоимость», «Что входит».");
});

test("неизвестное и уже русское — как есть", () => {
  assert.equal(translateCoreDetail("Something new happened"), "Something new happened");
  assert.equal(translateCoreDetail("У клиента несколько обращений: выберите конкретное дело"), "У клиента несколько обращений: выберите конкретное дело");
});

test("тело ответа: detail переведён, остальное на месте; не-JSON не трогаем", () => {
  const body = JSON.parse(translateCoreErrorBody(JSON.stringify({ detail: "Agreement not found", code: 7 })));
  assert.deepEqual(body, { detail: "Договор не найден.", code: 7 });
  assert.equal(translateCoreErrorBody("Internal Server Error"), "Internal Server Error");
});
