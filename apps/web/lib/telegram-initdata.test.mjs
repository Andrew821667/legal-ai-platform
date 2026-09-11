import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { test } from "node:test";

import {
  getMiniAppBotTokens,
  verifyTelegramWebAppInitData,
  verifyTelegramWebAppInitDataWithAny,
} from "./telegram-initdata.ts";

const READER = "111:READER-TOKEN";
const LEAD = "222:LEAD-TOKEN";

function signed(token, userId = 42) {
  const params = new URLSearchParams({
    auth_date: String(Math.floor(Date.now() / 1000)),
    user: JSON.stringify({ id: userId }),
  });
  const rows = [];
  params.forEach((value, key) => rows.push(`${key}=${value}`));
  rows.sort();
  const secret = createHmac("sha256", "WebAppData").update(token).digest();
  params.set("hash", createHmac("sha256", secret).update(rows.join("\n")).digest("hex"));
  return params.toString();
}

test("подпись бота-ассистента проходит, когда он в списке", () => {
  // Мини-апп писался для ридера; кнопка на клавиатуре ассистента ведёт
  // сюда же — и клиент получал «Invalid initData», не сделав ничего плохого.
  const result = verifyTelegramWebAppInitDataWithAny(signed(LEAD), [READER, LEAD]);
  assert.equal(result?.telegramUserId, 42);
});

test("подпись ридера по-прежнему проходит", () => {
  assert.equal(verifyTelegramWebAppInitDataWithAny(signed(READER), [READER, LEAD])?.telegramUserId, 42);
});

test("чужой бот не проходит ни с одним токеном", () => {
  assert.equal(verifyTelegramWebAppInitDataWithAny(signed("333:STRANGER"), [READER, LEAD]), null);
});

test("одиночная проверка не изменилась", () => {
  assert.equal(verifyTelegramWebAppInitData(signed(LEAD), READER), null);
  assert.equal(verifyTelegramWebAppInitData(signed(LEAD), LEAD)?.telegramUserId, 42);
});

test("список токенов берётся из окружения без пустых и дублей", () => {
  const saved = { ...process.env };
  process.env.READER_BOT_TOKEN = " r ";
  process.env.LEAD_BOT_TOKEN = "l";
  process.env.TELEGRAM_BOT_TOKEN = "l";
  try {
    assert.deepEqual(getMiniAppBotTokens(), ["r", "l"]);
    delete process.env.READER_BOT_TOKEN;
    delete process.env.LEAD_BOT_TOKEN;
    process.env.TELEGRAM_BOT_TOKEN = "";
    assert.deepEqual(getMiniAppBotTokens(), []);
  } finally {
    process.env.READER_BOT_TOKEN = saved.READER_BOT_TOKEN;
    process.env.LEAD_BOT_TOKEN = saved.LEAD_BOT_TOKEN;
    process.env.TELEGRAM_BOT_TOKEN = saved.TELEGRAM_BOT_TOKEN;
  }
});
