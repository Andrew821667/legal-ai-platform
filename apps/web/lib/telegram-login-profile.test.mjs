import assert from "node:assert/strict";
import { test } from "node:test";

import { profileFromIdTokenClaims, profileFromWidgetParams, toProfileCookie } from "./telegram-login-profile.ts";

test("profileFromIdTokenClaims — given_name/family_name в приоритете над name", () => {
  const profile = profileFromIdTokenClaims({
    sub: "848510279",
    given_name: "Иван",
    family_name: "Петров",
    name: "Другое Имя",
    preferred_username: "ivan_petrov",
    picture: "https://t.me/i/userpic/x.jpg",
  });
  assert.deepEqual(profile, {
    telegramUserId: 848510279,
    firstName: "Иван",
    lastName: "Петров",
    username: "ivan_petrov",
    photoUrl: "https://t.me/i/userpic/x.jpg",
    phone: undefined,
    phoneVerified: false,
    method: "oidc",
  });
});

test("profileFromIdTokenClaims — без given_name/family_name разбирает name", () => {
  const profile = profileFromIdTokenClaims({ sub: "1", name: "Иван Петров" });
  assert.equal(profile?.firstName, "Иван");
  assert.equal(profile?.lastName, "Петров");
});

test("profileFromIdTokenClaims — name без пробела даёт только firstName", () => {
  const profile = profileFromIdTokenClaims({ sub: "1", name: "Иван" });
  assert.equal(profile?.firstName, "Иван");
  assert.equal(profile?.lastName, undefined);
});

test("profileFromIdTokenClaims — sub в приоритете, id как запасной вариант", () => {
  assert.equal(profileFromIdTokenClaims({ sub: "5" })?.telegramUserId, 5);
  assert.equal(profileFromIdTokenClaims({ id: "7" })?.telegramUserId, 7);
  assert.equal(profileFromIdTokenClaims({ sub: "5", id: "7" })?.telegramUserId, 5);
});

test("profileFromIdTokenClaims — невалидный sub/id отклоняется", () => {
  assert.equal(profileFromIdTokenClaims({ sub: "abc" }), null);
  assert.equal(profileFromIdTokenClaims({ sub: "0" }), null);
  assert.equal(profileFromIdTokenClaims({ sub: "-5" }), null);
  assert.equal(profileFromIdTokenClaims({}), null);
});

test("profileFromIdTokenClaims — телефон нормализуется и считается верифицированным по умолчанию", () => {
  const profile = profileFromIdTokenClaims({ sub: "1", phone_number: "+7 909 233-09-09" });
  assert.equal(profile?.phone, "+79092330909");
  assert.equal(profile?.phoneVerified, true);
});

test("profileFromIdTokenClaims — phone_number_verified: false явно отключает флаг", () => {
  const profile = profileFromIdTokenClaims({
    sub: "1",
    phone_number: "+79092330909",
    phone_number_verified: false,
  });
  assert.equal(profile?.phoneVerified, false);
});

test("profileFromIdTokenClaims — без phone_number флаг phoneVerified не поднимается", () => {
  const profile = profileFromIdTokenClaims({ sub: "1" });
  assert.equal(profile?.phone, undefined);
  assert.equal(profile?.phoneVerified, false);
});

test("profileFromWidgetParams — маппинг полей виджета, phoneVerified всегда false", () => {
  const params = new URLSearchParams({
    id: "848510279",
    first_name: "Иван",
    last_name: "Петров",
    username: "ivan_petrov",
    photo_url: "https://t.me/i/userpic/x.jpg",
    auth_date: "1700000000",
    hash: "deadbeef",
  });
  const profile = profileFromWidgetParams(params);
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

test("toProfileCookie — маскирует телефон, оставляя последние 4 цифры", () => {
  const cookie = toProfileCookie({
    telegramUserId: 1,
    firstName: "Иван",
    lastName: "Петров",
    username: "ivan",
    phone: "+79092330909",
    phoneVerified: true,
    method: "oidc",
  });
  assert.equal(cookie.fn, "Иван");
  assert.equal(cookie.ln, "Петров");
  assert.match(cookie.phoneMasked ?? "", /^\+•+0909$/);
});

test("toProfileCookie — без телефона phoneMasked не заполняется", () => {
  const cookie = toProfileCookie({
    telegramUserId: 1,
    firstName: "Иван",
    phoneVerified: false,
    method: "legacy",
  });
  assert.equal(cookie.phoneMasked, undefined);
});
