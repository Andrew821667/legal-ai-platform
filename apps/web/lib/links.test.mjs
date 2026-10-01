import assert from "node:assert/strict";
import test from "node:test";

import { contractAIEntryHref } from "./links.ts";

test("кнопки «демо» ведут на страницу заявки Contract AI, а не на несуществующий якорь", () => {
  assert.equal(contractAIEntryHref("demo"), "https://contract.ai-verdict.ru/demo");
});

test("прочие переходы в Contract AI не меняются", () => {
  assert.equal(contractAIEntryHref(), "https://contract.ai-verdict.ru");
  assert.equal(contractAIEntryHref("pricing"), "https://contract.ai-verdict.ru#pricing");
});
