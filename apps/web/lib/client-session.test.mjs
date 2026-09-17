import assert from "node:assert/strict";
import { test } from "node:test";

import {
  CLIENT_SESSION_MAX_AGE_SECONDS,
  clientCookieOptions,
  clientSessionSecret,
  mintClientSessionToken,
  verifyClientSessionToken,
} from "./client-session.ts";

const DAY = 24 * 60 * 60;

test("7 дней — согласованный TTL сессии клиента", () => {
  assert.equal(CLIENT_SESSION_MAX_AGE_SECONDS, 7 * DAY);
});

test("токен клиента проходит проверку тем же секретом в пределах 7 дней", () => {
  const token = mintClientSessionToken(848510279, "client-secret");
  const result = verifyClientSessionToken(token, "client-secret");
  assert.equal(result?.telegramUserId, 848510279);
});

test("токен клиента протухает после 7 дней", () => {
  const now = 1_700_000_000;
  const token = mintClientSessionToken(1, "client-secret", now - 7 * DAY - 1);
  assert.equal(verifyClientSessionToken(token, "client-secret", now), null);
});

test("clientCookieOptions — httpOnly/secure/lax по умолчанию на путь /", () => {
  assert.deepEqual(clientCookieOptions(3600), {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 3600,
  });
});

test("clientCookieOptions принимает свой path", () => {
  assert.equal(clientCookieOptions(600, "/cabinet").path, "/cabinet");
});

test("clientSessionSecret пуст, если не задан", () => {
  const savedClient = process.env.CLIENT_SESSION_SECRET;
  const savedLawyer = process.env.LAWYER_SESSION_SECRET;
  delete process.env.CLIENT_SESSION_SECRET;
  delete process.env.LAWYER_SESSION_SECRET;
  try {
    assert.equal(clientSessionSecret(), "");
  } finally {
    if (savedClient === undefined) delete process.env.CLIENT_SESSION_SECRET;
    else process.env.CLIENT_SESSION_SECRET = savedClient;
    if (savedLawyer === undefined) delete process.env.LAWYER_SESSION_SECRET;
    else process.env.LAWYER_SESSION_SECRET = savedLawyer;
  }
});

test("clientSessionSecret отдаёт значение, когда оно отличается от секрета юриста", () => {
  const savedClient = process.env.CLIENT_SESSION_SECRET;
  const savedLawyer = process.env.LAWYER_SESSION_SECRET;
  process.env.CLIENT_SESSION_SECRET = "client-only-secret";
  process.env.LAWYER_SESSION_SECRET = "lawyer-only-secret";
  try {
    assert.equal(clientSessionSecret(), "client-only-secret");
  } finally {
    if (savedClient === undefined) delete process.env.CLIENT_SESSION_SECRET;
    else process.env.CLIENT_SESSION_SECRET = savedClient;
    if (savedLawyer === undefined) delete process.env.LAWYER_SESSION_SECRET;
    else process.env.LAWYER_SESSION_SECRET = savedLawyer;
  }
});

test("clientSessionSecret пуст, если совпадает с секретом юриста (guard от коллизии ролей)", () => {
  const savedClient = process.env.CLIENT_SESSION_SECRET;
  const savedLawyer = process.env.LAWYER_SESSION_SECRET;
  process.env.CLIENT_SESSION_SECRET = "same-secret";
  process.env.LAWYER_SESSION_SECRET = "same-secret";
  try {
    assert.equal(clientSessionSecret(), "");
  } finally {
    if (savedClient === undefined) delete process.env.CLIENT_SESSION_SECRET;
    else process.env.CLIENT_SESSION_SECRET = savedClient;
    if (savedLawyer === undefined) delete process.env.LAWYER_SESSION_SECRET;
    else process.env.LAWYER_SESSION_SECRET = savedLawyer;
  }
});
