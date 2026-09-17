import assert from "node:assert/strict";
import { createHash, createHmac } from "node:crypto";
import { test } from "node:test";

import { verifyTelegramLoginWidget } from "./telegram-login-legacy.ts";

const BOT_TOKEN = "8124330166:TESTTOKENTESTTOKENTESTTOKEN";

/** Собирает params с корректной подписью — так их формирует telegram-widget.js. */
function signedParams(overrides = {}, { authDate } = {}) {
  const base = {
    id: "848510279",
    first_name: "Иван",
    last_name: "Петров",
    username: "ivan_petrov",
    photo_url: "https://t.me/i/userpic/x.jpg",
    auth_date: String(authDate ?? Math.floor(Date.now() / 1000)),
    ...overrides,
  };
  const params = new URLSearchParams(base);
  const rows = [];
  params.forEach((value, key) => rows.push(`${key}=${value}`));
  rows.sort();
  const key = createHash("sha256").update(BOT_TOKEN).digest();
  const hash = createHmac("sha256", key).update(rows.join("\n")).digest("hex");
  params.set("hash", hash);
  return params;
}

test("корректная подпись проходит и маппится в профиль", () => {
  const profile = verifyTelegramLoginWidget(signedParams(), BOT_TOKEN);
  assert.deepEqual(profile, {
    telegramUserId: 848510279,
    firstName: "Иван",
    lastName: "Петров",
    username: "ivan_petrov",
    photoUrl: "https://t.me/i/userpic/x.jpg",
    phoneVerified: false,
    method: "legacy",
  });
});

test("ключ — SHA256(botToken), а НЕ HMAC('WebAppData', botToken) как у Mini App", () => {
  // Если бы модуль перепутал схему с Mini App, эта подпись (посчитанная
  // правильным для виджета способом) не прошла бы.
  const params = signedParams();
  const wrongKey = createHmac("sha256", "WebAppData").update(BOT_TOKEN).digest();
  const rows = [];
  new URLSearchParams(params).forEach((value, key) => {
    if (key !== "hash") rows.push(`${key}=${value}`);
  });
  rows.sort();
  const wrongHash = createHmac("sha256", wrongKey).update(rows.join("\n")).digest("hex");
  params.set("hash", wrongHash);
  assert.equal(verifyTelegramLoginWidget(params, BOT_TOKEN), null);
});

test("без токена бота на сервере — отказ, а не пропуск", () => {
  assert.equal(verifyTelegramLoginWidget(signedParams(), ""), null);
});

test("подделанная подпись отвергается", () => {
  const params = signedParams();
  params.set("hash", "0".repeat(64));
  assert.equal(verifyTelegramLoginWidget(params, BOT_TOKEN), null);
});

test("подмена поля после подписи ломает совпадение", () => {
  const params = signedParams();
  params.set("first_name", "Другой");
  assert.equal(verifyTelegramLoginWidget(params, BOT_TOKEN), null);
});

test("устаревший auth_date отклоняется (защита от replay)", () => {
  const now = 1_700_000_000;
  const params = signedParams({}, { authDate: now - 601 });
  assert.equal(verifyTelegramLoginWidget(params, BOT_TOKEN, { now }), null);
});

test("auth_date ровно на границе окна ещё принимается", () => {
  const now = 1_700_000_000;
  const params = signedParams({}, { authDate: now - 600 });
  assert.ok(verifyTelegramLoginWidget(params, BOT_TOKEN, { now }));
});

test("auth_date из будущего дальше чем на 60с отклоняется", () => {
  const now = 1_700_000_000;
  const params = signedParams({}, { authDate: now + 61 });
  assert.equal(verifyTelegramLoginWidget(params, BOT_TOKEN, { now }), null);
});

test("дубликат ключа в параметрах отклоняется", () => {
  const params = signedParams();
  const raw = `${params.toString()}&id=999999999`;
  assert.equal(verifyTelegramLoginWidget(new URLSearchParams(raw), BOT_TOKEN), null);
});

test("нечисловой или неположительный id отклоняется несмотря на верную подпись", () => {
  assert.equal(verifyTelegramLoginWidget(signedParams({ id: "0" }), BOT_TOKEN), null);
  assert.equal(verifyTelegramLoginWidget(signedParams({ id: "-5" }), BOT_TOKEN), null);
});

test("hash не в hex-формате отклоняется до вычисления подписи", () => {
  const params = signedParams();
  params.set("hash", "not-hex-value");
  assert.equal(verifyTelegramLoginWidget(params, BOT_TOKEN), null);
});
