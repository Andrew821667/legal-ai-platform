import assert from "node:assert/strict";
import { test } from "node:test";

import { mintSessionToken, verifySessionToken } from "./session-token.ts";

const SECRET = "shared-secret";
const DAY = 24 * 60 * 60;

test("выпущенный токен проходит проверку тем же секретом", () => {
  const token = mintSessionToken(848510279, SECRET);
  const result = verifySessionToken(token, SECRET, 30 * DAY);
  assert.deepEqual(result && { telegramUserId: result.telegramUserId }, {
    telegramUserId: 848510279,
  });
});

test("другой секрет не проходит", () => {
  const token = mintSessionToken(1, SECRET);
  assert.equal(verifySessionToken(token, "другой-секрет", 30 * DAY), null);
});

test("подделанная подпись не проходит", () => {
  const token = mintSessionToken(1, SECRET);
  const [id, issuedAt] = token.split(".");
  const forged = `${id}.${issuedAt}.${"0".repeat(64)}`;
  assert.equal(verifySessionToken(forged, SECRET, 30 * DAY), null);
});

test("просроченный токен отклоняется", () => {
  const now = 1_700_000_000;
  const token = mintSessionToken(1, SECRET, now - 7 * DAY - 1);
  assert.equal(verifySessionToken(token, SECRET, 7 * DAY, now), null);
});

test("токен ровно на границе срока ещё действителен", () => {
  const now = 1_700_000_000;
  const token = mintSessionToken(1, SECRET, now - 7 * DAY);
  assert.ok(verifySessionToken(token, SECRET, 7 * DAY, now));
});

test("токен из будущего дальше чем на 60с отклоняется", () => {
  const now = 1_700_000_000;
  const token = mintSessionToken(1, SECRET, now + 61);
  assert.equal(verifySessionToken(token, SECRET, 7 * DAY, now), null);
});

test("мусорный ввод не роняет проверку", () => {
  assert.equal(verifySessionToken("", SECRET, DAY), null);
  assert.equal(verifySessionToken("a.b", SECRET, DAY), null);
  assert.equal(verifySessionToken("1.2.not-hex", SECRET, DAY), null);
  assert.equal(verifySessionToken("abc.123.".padEnd(64 + 8, "0"), SECRET, DAY), null);
});

test("два разных roleSecret не взаимозаменяемы (клиент/юрист)", () => {
  const lawyerToken = mintSessionToken(555, "LAWYER_SECRET");
  const clientToken = mintSessionToken(555, "CLIENT_SECRET");
  assert.notEqual(lawyerToken, clientToken);
  assert.equal(verifySessionToken(lawyerToken, "CLIENT_SECRET", DAY), null);
  assert.equal(verifySessionToken(clientToken, "LAWYER_SECRET", DAY), null);
});
