import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { test } from "node:test";

import { checkLawyerAccess, checkLawyerSessionCookie, parseAllowedIds } from "./lawyer-access.ts";
import { mintLawyerSessionToken } from "./lawyer-session-token.ts";

const BOT_TOKEN = "8124330166:TESTTOKENTESTTOKENTESTTOKEN";
const LAWYER_ID = 848510279;
const STRANGER_ID = 111222333;
const ALLOWED = [LAWYER_ID];

/** Собирает initData с корректной подписью — так его формирует Telegram. */
function signedInitData(userId, { authDate = Math.floor(Date.now() / 1000) } = {}) {
  const params = new URLSearchParams({
    auth_date: String(authDate),
    user: JSON.stringify({ id: userId }),
  });
  const rows = [];
  params.forEach((value, key) => rows.push(`${key}=${value}`));
  rows.sort();
  const secret = createHmac("sha256", "WebAppData").update(BOT_TOKEN).digest();
  const hash = createHmac("sha256", secret).update(rows.join("\n")).digest("hex");
  params.set("hash", hash);
  return params.toString();
}

function check(initData, overrides = {}) {
  return checkLawyerAccess({ initData, botToken: BOT_TOKEN, allowedIds: ALLOWED, ...overrides });
}

test("юрист с корректной подписью проходит", () => {
  const result = check(signedInitData(LAWYER_ID));
  assert.equal(result.ok, true);
  assert.equal(result.telegramUserId, LAWYER_ID);
});

test("без подписи доступа нет", () => {
  const result = check("");
  assert.equal(result.ok, false);
  assert.equal(result.status, 401);
});

test("поддельная подпись отвергается", () => {
  const tampered = signedInitData(LAWYER_ID).replace(/hash=[0-9a-f]+/, `hash=${"0".repeat(64)}`);
  const result = check(tampered);
  assert.equal(result.ok, false);
  assert.equal(result.status, 401);
});

test("подмена пользователя в подписанных данных не проходит", () => {
  // Берём валидную подпись юриста и подставляем чужой id: подпись перестаёт
  // сходиться, потому что считается по всему набору полей.
  const forged = signedInitData(LAWYER_ID).replace(
    encodeURIComponent(JSON.stringify({ id: LAWYER_ID })),
    encodeURIComponent(JSON.stringify({ id: STRANGER_ID })),
  );
  const result = check(forged);
  assert.equal(result.ok, false);
  assert.equal(result.status, 401);
});

test("посторонний с настоящей подписью получает отказ", () => {
  // Подпись честная — человек действительно открыл мини-апп из Telegram.
  // Но данные клиентов практики ему видеть незачем.
  const result = check(signedInitData(STRANGER_ID));
  assert.equal(result.ok, false);
  assert.equal(result.status, 403);
});

test("просроченная подпись не принимается", () => {
  // Перехваченный initData иначе работал бы вечно.
  const old = Math.floor(Date.now() / 1000) - 60 * 60 * 24;
  const result = check(signedInitData(LAWYER_ID, { authDate: old }));
  assert.equal(result.ok, false);
  assert.equal(result.status, 401);
});

test("без токена бота запрос не пропускается", () => {
  // Проверить подпись нечем. Пропустить в таком случае значило бы отдать
  // данные клиентов любому, кто знает адрес.
  const result = check(signedInitData(LAWYER_ID), { botToken: "" });
  assert.equal(result.ok, false);
  assert.equal(result.status, 500);
});

test("пустой список допущенных никого не пропускает", () => {
  const result = check(signedInitData(LAWYER_ID), { allowedIds: [] });
  assert.equal(result.ok, false);
  assert.equal(result.status, 403);
});

test("список допущенных разбирается из строк окружения", () => {
  assert.deepEqual(parseAllowedIds(String(LAWYER_ID), "555, 666", undefined), [
    LAWYER_ID,
    555,
    666,
  ]);
});

test("мусор в списке допущенных отбрасывается", () => {
  // Испорченная переменная не должна превращаться в NaN и тем более никого
  // не пропускать по совпадению с ним.
  assert.deepEqual(parseAllowedIds("", "abc, -5, 0, 777"), [777]);
});

// --- Автономный вход: куки вне Telegram (без initData вовсе) ---

const SESSION_SECRET = "session-shared-secret";

function checkCookie(cookie, overrides = {}) {
  return checkLawyerSessionCookie({
    cookie,
    secret: SESSION_SECRET,
    allowedIds: ALLOWED,
    ...overrides,
  });
}

test("юрист с валидным токеном в куке проходит", () => {
  const token = mintLawyerSessionToken(LAWYER_ID, SESSION_SECRET);
  const result = checkCookie(token);
  assert.equal(result.ok, true);
  assert.equal(result.telegramUserId, LAWYER_ID);
});

test("без куки — как без initData: 401 с просьбой войти", () => {
  const result = checkCookie("");
  assert.equal(result.ok, false);
  assert.equal(result.status, 401);
});

test("посторонний с валидным токеном получает 403, а не доступ", () => {
  const token = mintLawyerSessionToken(STRANGER_ID, SESSION_SECRET);
  const result = checkCookie(token);
  assert.equal(result.ok, false);
  assert.equal(result.status, 403);
});

test("токен, подписанный другим секретом, не проходит", () => {
  const token = mintLawyerSessionToken(LAWYER_ID, "чужой-секрет");
  const result = checkCookie(token);
  assert.equal(result.ok, false);
  assert.equal(result.status, 401);
});

test("без секрета на сервере автономный вход не пропускает никого", () => {
  // Проверить токен нечем — тот же принцип, что и для ботового токена в
  // Telegram-пути: молчаливый пропуск здесь означал бы дыру, а не удобство.
  const token = mintLawyerSessionToken(LAWYER_ID, SESSION_SECRET);
  const result = checkCookie(token, { secret: "" });
  assert.equal(result.ok, false);
  assert.equal(result.status, 500);
});
