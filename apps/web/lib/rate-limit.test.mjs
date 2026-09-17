import assert from "node:assert/strict";
import { test } from "node:test";

import { checkSlidingWindow, commitSlidingWindowHit, slidingWindowAllow } from "./rate-limit.ts";

test("slidingWindowAllow пропускает до лимита и блокирует сверх", () => {
  const store = new Map();
  assert.equal(slidingWindowAllow(store, "k", 2, 1000, 100).allowed, true);
  assert.equal(slidingWindowAllow(store, "k", 2, 1000, 200).allowed, true);
  const blocked = slidingWindowAllow(store, "k", 2, 1000, 300);
  assert.equal(blocked.allowed, false);
  assert.ok(blocked.retryAfter > 0);
});

test("slidingWindowAllow забывает попытки старше окна", () => {
  const store = new Map();
  slidingWindowAllow(store, "k", 1, 1000, 0);
  assert.equal(slidingWindowAllow(store, "k", 1, 1000, 500).allowed, false);
  assert.equal(slidingWindowAllow(store, "k", 1, 1000, 1001).allowed, true);
});

test("разные ключи не влияют друг на друга", () => {
  const store = new Map();
  slidingWindowAllow(store, "a", 1, 1000, 0);
  assert.equal(slidingWindowAllow(store, "b", 1, 1000, 0).allowed, true);
});

test("checkSlidingWindow не фиксирует попытку без явного коммита", () => {
  const store = new Map();
  const first = checkSlidingWindow(store, "k", 1, 1000, 0);
  assert.equal(first.allowed, true);
  // Повторная проверка без коммита снова видит лимит свободным.
  const second = checkSlidingWindow(store, "k", 1, 1000, 100);
  assert.equal(second.allowed, true);
});

test("commitSlidingWindowHit фиксирует попытку, дальше лимит расходуется", () => {
  const store = new Map();
  const check = checkSlidingWindow(store, "k", 1, 1000, 0);
  commitSlidingWindowHit(store, "k", check.rows, 0);
  assert.equal(checkSlidingWindow(store, "k", 1, 1000, 100).allowed, false);
});

test("двухфазный check+commit не расходует лимит при отказе второй проверки (сценарий IP+session)", () => {
  const ipStore = new Map();
  const sessionStore = new Map();
  // IP уже на пределе, session — свежий ключ.
  slidingWindowAllow(ipStore, "1.2.3.4", 1, 1000, 0);

  const ipCheck = checkSlidingWindow(ipStore, "1.2.3.4", 1, 1000, 100);
  const sessionCheck = checkSlidingWindow(sessionStore, "sess", 5, 1000, 100);
  assert.equal(ipCheck.allowed, false);
  assert.equal(sessionCheck.allowed, true);
  // Ни один коммит не должен произойти — вызывающая сторона обязана
  // пропустить commit при отказе хотя бы одной из проверок.
  if (ipCheck.allowed && sessionCheck.allowed) {
    commitSlidingWindowHit(ipStore, "1.2.3.4", ipCheck.rows, 100);
    commitSlidingWindowHit(sessionStore, "sess", sessionCheck.rows, 100);
  }
  assert.equal(sessionStore.get("sess"), undefined);
});
