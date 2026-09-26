import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildYandexAuthorizeUrl,
  exchangeYandexCode,
  fetchYandexProfile,
  profileFromYandexInfo,
  yandexConfig,
  YandexOauthError,
} from "./yandex-oauth.ts";

const config = { clientId: "app-id", clientSecret: "app-secret", redirectUri: "https://ai-verdict.ru/cabinet/callback/yandex" };

test("настройки: без id или секрета входа нет, адрес возврата по умолчанию от origin", () => {
  assert.equal(yandexConfig({}, "https://ai-verdict.ru"), null);
  assert.equal(yandexConfig({ YANDEX_OAUTH_CLIENT_ID: "a" }, "https://ai-verdict.ru"), null);
  assert.deepEqual(yandexConfig({ YANDEX_OAUTH_CLIENT_ID: "a", YANDEX_OAUTH_CLIENT_SECRET: "b" }, "https://ai-verdict.ru"), {
    clientId: "a",
    clientSecret: "b",
    redirectUri: "https://ai-verdict.ru/cabinet/callback/yandex",
  });
});

test("ссылка авторизации: code + PKCE S256 + state", () => {
  const url = new URL(buildYandexAuthorizeUrl({ ...config, state: "st", codeChallenge: "ch" }));
  assert.equal(url.origin + url.pathname, "https://oauth.yandex.ru/authorize");
  assert.equal(url.searchParams.get("response_type"), "code");
  assert.equal(url.searchParams.get("client_id"), "app-id");
  assert.equal(url.searchParams.get("redirect_uri"), config.redirectUri);
  assert.equal(url.searchParams.get("state"), "st");
  assert.equal(url.searchParams.get("code_challenge"), "ch");
  assert.equal(url.searchParams.get("code_challenge_method"), "S256");
});

test("обмен кода: форма с verifier и секретом; без токена — ошибка exchange", async () => {
  let seen;
  const ok = async (url, init) => {
    seen = { url, body: new URLSearchParams(String(init.body)) };
    return new Response(JSON.stringify({ access_token: "tok" }), { status: 200 });
  };
  assert.equal(await exchangeYandexCode({ code: "c1", codeVerifier: "v1", config }, ok), "tok");
  assert.equal(seen.url, "https://oauth.yandex.ru/token");
  assert.equal(seen.body.get("grant_type"), "authorization_code");
  assert.equal(seen.body.get("code_verifier"), "v1");
  assert.equal(seen.body.get("client_secret"), "app-secret");

  const bad = async () => new Response(JSON.stringify({ error: "invalid_grant" }), { status: 400 });
  await assert.rejects(exchangeYandexCode({ code: "c", codeVerifier: "v", config }, bad), (e) => e instanceof YandexOauthError && e.reason === "exchange");
});

test("профиль: почта по умолчанию, запасная из списка, имя; без почты — ошибка email", () => {
  assert.deepEqual(profileFromYandexInfo({ id: "123", default_email: "Anna@Yandex.ru", first_name: "Анна" }, "app-id"), {
    yandexId: "123",
    email: "anna@yandex.ru",
    displayName: "Анна",
  });
  assert.equal(profileFromYandexInfo({ id: 5, emails: ["b@ya.ru"], login: "bb" }, "app-id").email, "b@ya.ru");
  assert.throws(() => profileFromYandexInfo({ id: "1" }, "app-id"), (e) => e.reason === "email");
  assert.throws(() => profileFromYandexInfo({ default_email: "a@ya.ru" }, "app-id"), (e) => e.reason === "profile");
});

test("токен, выданный чужому приложению, не принимается", () => {
  assert.throws(
    () => profileFromYandexInfo({ id: "1", default_email: "a@ya.ru", client_id: "other" }, "app-id"),
    (e) => e.reason === "profile",
  );
});

test("запрос профиля идёт с заголовком OAuth", async () => {
  let header;
  const fake = async (url, init) => {
    header = init.headers.authorization;
    return new Response(JSON.stringify({ id: "9", default_email: "c@ya.ru" }), { status: 200 });
  };
  const profile = await fetchYandexProfile("tok", "app-id", fake);
  assert.equal(header, "OAuth tok");
  assert.equal(profile.yandexId, "9");
});
