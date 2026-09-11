import assert from "node:assert/strict";
import { test } from "node:test";

import { splitBlocks } from "./lawyer-text.ts";

test("перечень с любым маркером — один список", () => {
  const text = "Нужно:\n• составить договор\n- проверить контрагента\no подписать NDA\n▪ выставить счёт";
  assert.deepEqual(splitBlocks(text), [
    { type: "paragraph", text: "Нужно:" },
    {
      type: "list",
      ordered: false,
      items: ["составить договор", "проверить контрагента", "подписать NDA", "выставить счёт"],
    },
  ]);
});

test("нумерация — упорядоченный список, отдельно от маркированного", () => {
  const blocks = splitBlocks("1. Первое\n2) Второе\n• третье");
  assert.equal(blocks.length, 2);
  assert.deepEqual(blocks[0], { type: "list", ordered: true, items: ["Первое", "Второе"] });
  assert.deepEqual(blocks[1], { type: "list", ordered: false, items: ["третье"] });
});

test("«o» внутри слова и дефис в числе — не маркеры", () => {
  assert.deepEqual(splitBlocks("ooo Ромашка\n-5 градусов"), [
    { type: "paragraph", text: "ooo Ромашка\n-5 градусов" },
  ]);
});

test("пустая строка делит абзацы, пустой текст — ничего", () => {
  assert.deepEqual(splitBlocks("Первый\nещё\n\nВторой"), [
    { type: "paragraph", text: "Первый\nещё" },
    { type: "paragraph", text: "Второй" },
  ]);
  assert.deepEqual(splitBlocks(""), []);
  assert.deepEqual(splitBlocks(null), []);
});
