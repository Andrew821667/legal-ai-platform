import assert from "node:assert/strict";
import { test } from "node:test";

import { openCookieValue, sealCookieValue } from "./signed-cookie.ts";

const SECRET = "cookie-secret";
const TEN_MIN = 600;

test("запечатанное значение вскрывается тем же секретом", () => {
  const sealed = sealCookieValue({ state: "abc", nonce: "xyz" }, SECRET);
  const opened = openCookieValue(sealed, SECRET, TEN_MIN);
  assert.equal(opened?.state, "abc");
  assert.equal(opened?.nonce, "xyz");
  assert.equal(typeof opened?.iat, "number");
});

test("другой секрет не вскрывает", () => {
  const sealed = sealCookieValue({ state: "abc" }, SECRET);
  assert.equal(openCookieValue(sealed, "другой-секрет", TEN_MIN), null);
});

test("подделанная подпись отклоняется", () => {
  const sealed = sealCookieValue({ state: "abc" }, SECRET);
  const [body] = sealed.split(".");
  const forged = `${body}.${"0".repeat(64)}`;
  assert.equal(openCookieValue(forged, SECRET, TEN_MIN), null);
});

test("подмена тела при старой подписи отклоняется", () => {
  const sealed = sealCookieValue({ state: "abc" }, SECRET);
  const [, signature] = sealed.split(".");
  const tamperedBody = Buffer.from(JSON.stringify({ state: "evil", iat: Math.floor(Date.now() / 1000) })).toString(
    "base64url",
  );
  assert.equal(openCookieValue(`${tamperedBody}.${signature}`, SECRET, TEN_MIN), null);
});

test("протухшее значение отклоняется", () => {
  const now = 1_700_000_000;
  const sealed = sealCookieValue({ state: "abc" }, SECRET, now - TEN_MIN - 1);
  assert.equal(openCookieValue(sealed, SECRET, TEN_MIN, now), null);
});

test("значение ровно на границе срока ещё действительно", () => {
  const now = 1_700_000_000;
  const sealed = sealCookieValue({ state: "abc" }, SECRET, now - TEN_MIN);
  assert.ok(openCookieValue(sealed, SECRET, TEN_MIN, now));
});

test("значение из будущего дальше чем на 60с отклоняется", () => {
  const now = 1_700_000_000;
  const sealed = sealCookieValue({ state: "abc" }, SECRET, now + 61);
  assert.equal(openCookieValue(sealed, SECRET, TEN_MIN, now), null);
});

test("мусорный ввод не роняет проверку", () => {
  assert.equal(openCookieValue("", SECRET, TEN_MIN), null);
  assert.equal(openCookieValue("no-dot-here", SECRET, TEN_MIN), null);
  assert.equal(openCookieValue("body.not-hex-signature", SECRET, TEN_MIN), null);
  assert.equal(openCookieValue(".deadbeef", SECRET, TEN_MIN), null);
});

test("произвольная вложенная структура переживает круг seal/open", () => {
  const payload = { fn: "Иван", ln: "Петров", un: "ivan_petrov", photo: "https://t.me/x.jpg", phoneMasked: "+7•••1234", method: "oidc" };
  const sealed = sealCookieValue(payload, SECRET);
  const opened = openCookieValue(sealed, SECRET, TEN_MIN);
  assert.deepEqual({ ...opened, iat: undefined }, { ...payload, iat: undefined });
});
