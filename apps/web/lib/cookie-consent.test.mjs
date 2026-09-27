import assert from "node:assert/strict";
import { test } from "node:test";

import {
  COOKIE_CONSENT_KEY,
  analyticsAllowed,
  cookieConsentMode,
  readCookieConsent,
  writeCookieConsent,
} from "./cookie-consent.ts";

function memoryStorage() {
  const data = new Map();
  return { getItem: (key) => data.get(key) ?? null, setItem: (key, value) => data.set(key, String(value)) };
}

test("без согласия счётчики молчат, в уведомительном режиме — работают до отказа", () => {
  assert.equal(analyticsAllowed("opt_in", null), false);
  assert.equal(analyticsAllowed("opt_in", "accepted"), true);
  assert.equal(analyticsAllowed("opt_in", "declined"), false);
  assert.equal(analyticsAllowed("notice", null), true);
  assert.equal(analyticsAllowed("notice", "declined"), false);
});

test("режим по умолчанию — opt_in", () => {
  assert.equal(cookieConsentMode(undefined), "opt_in");
  assert.equal(cookieConsentMode("NOTICE"), "notice");
  assert.equal(cookieConsentMode("что-то"), "opt_in");
});

test("выбор сохраняется, мусор и сломанное хранилище — как «не выбрано»", () => {
  const storage = memoryStorage();
  assert.equal(readCookieConsent(storage), null);
  writeCookieConsent(storage, "accepted");
  assert.equal(readCookieConsent(storage), "accepted");
  storage.setItem(COOKIE_CONSENT_KEY, "maybe");
  assert.equal(readCookieConsent(storage), null);
  const broken = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };
  assert.equal(readCookieConsent(broken), null);
  assert.doesNotThrow(() => writeCookieConsent(broken, "declined"));
});
