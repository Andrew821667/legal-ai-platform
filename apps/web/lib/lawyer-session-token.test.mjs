import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { test } from "node:test";

import { mintLawyerSessionToken, verifyLawyerSessionToken } from "./lawyer-session-token.ts";

const SECRET = "shared-secret";
const DAY = 24 * 60 * 60;

test("выпущенный токен проходит проверку тем же секретом", () => {
  const token = mintLawyerSessionToken(848510279, SECRET);
  const result = verifyLawyerSessionToken(token, SECRET, 30 * DAY);
  assert.deepEqual(result && { telegramUserId: result.telegramUserId }, {
    telegramUserId: 848510279,
  });
});

test("другой секрет не проходит", () => {
  const token = mintLawyerSessionToken(1, SECRET);
  assert.equal(verifyLawyerSessionToken(token, "другой-секрет", 30 * DAY), null);
});

test("подделанная подпись не проходит", () => {
  const token = mintLawyerSessionToken(1, SECRET);
  const [id, issuedAt] = token.split(".");
  const forged = `${id}.${issuedAt}.${"0".repeat(64)}`;
  assert.equal(verifyLawyerSessionToken(forged, SECRET, 30 * DAY), null);
});

test("подмена id в токене ломает подпись", () => {
  // Подпись считается от всей строки id.issuedAt — подмена одного числа не
  // может остаться незамеченной, как бывает с наивной конкатенацией.
  const token = mintLawyerSessionToken(1, SECRET);
  const [, issuedAt, signature] = token.split(".");
  const forged = `999.${issuedAt}.${signature}`;
  assert.equal(verifyLawyerSessionToken(forged, SECRET, 30 * DAY), null);
});

test("просроченный токен отклоняется", () => {
  const monthAgo = Math.floor(Date.now() / 1000) - 31 * DAY;
  const token = mintLawyerSessionToken(1, SECRET, monthAgo);
  assert.equal(verifyLawyerSessionToken(token, SECRET, 30 * DAY), null);
});

test("токен из будущего отклоняется", () => {
  // Небольшой допуск на рассинхрон часов, но не на минуты вперёд.
  const future = Math.floor(Date.now() / 1000) + 10 * 60;
  const token = mintLawyerSessionToken(1, SECRET, future);
  assert.equal(verifyLawyerSessionToken(token, SECRET, 30 * DAY), null);
});

test("токен ровно на границе срока ещё действителен", () => {
  const now = Math.floor(Date.now() / 1000);
  const issuedAt = now - 30 * DAY + 5;
  const token = mintLawyerSessionToken(1, SECRET, issuedAt);
  const result = verifyLawyerSessionToken(token, SECRET, 30 * DAY, now);
  assert.ok(result !== null);
});

test("мусорный ввод не роняет проверку", () => {
  for (const bad of ["", "not-a-token", "1.2", "1.2.3.4", "abc.def.ghi"]) {
    assert.equal(verifyLawyerSessionToken(bad, SECRET, 30 * DAY), null, bad);
  }
});

test("формат совпадает с тем, что проверяет lawyer_session_link.py на стороне бота", () => {
  // Контракт формата, не живой межъязыковой вызов: тот же алгоритм
  // (HMAC-SHA256 от `${id}.${issuedAt}`), собранный вручную, как это делает
  // Python-сторона, должен приниматься тем же verify.
  const issuedAt = Math.floor(Date.now() / 1000);
  const payload = `848510279.${issuedAt}`;
  const signature = createHmac("sha256", SECRET).update(payload).digest("hex");
  const handAssembled = `${payload}.${signature}`;

  const result = verifyLawyerSessionToken(handAssembled, SECRET, 30 * DAY);
  assert.deepEqual(result && result.telegramUserId, 848510279);
});
