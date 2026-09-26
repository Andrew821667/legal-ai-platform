import assert from "node:assert/strict";
import { test } from "node:test";

import { cabinetLeadFields, cabinetNoteTags, cabinetSourceContext } from "./lead-cabinet.ts";

test("cabinetLeadFields — без сессии пустой объект (анонимная форма сайта не меняется)", () => {
  assert.deepEqual(cabinetLeadFields(null), {});
});

test("cabinetLeadFields — с сессией добавляет telegram_user_id из куки, не с клиента", () => {
  assert.deepEqual(cabinetLeadFields({ telegramUserId: 848510279 }), { telegram_user_id: 848510279 });
});

test("cabinetSourceContext — без сессии остаётся исходный fallback (адрес страницы)", () => {
  assert.equal(cabinetSourceContext(null, "/legal-help"), "/legal-help");
});

test("cabinetSourceContext — с сессией всегда 'cabinet' независимо от fallback", () => {
  assert.equal(cabinetSourceContext({ telegramUserId: 1 }, "/legal-help"), "cabinet");
  assert.equal(cabinetSourceContext({ telegramUserId: 1 }, "/"), "cabinet");
});

test("cabinetNoteTags — без сессии пустой список", () => {
  assert.deepEqual(cabinetNoteTags(null), []);
});

test("cabinetNoteTags — с сессией отмечает канал и подтверждённый Telegram", () => {
  assert.deepEqual(cabinetNoteTags({ telegramUserId: 1 }), ["channel=cabinet", "telegram_verified=1"]);
});

test("вход через Яндекс ID — почта учётной записи в email лида и своя отметка", () => {
  const session = { accountEmail: "anna@yandex.ru" };
  assert.deepEqual(cabinetLeadFields(session), { email: "anna@yandex.ru" });
  assert.deepEqual(cabinetNoteTags(session), ["channel=cabinet", "yandex_verified=1"]);
  assert.equal(cabinetSourceContext(session, "/"), "cabinet");
});
