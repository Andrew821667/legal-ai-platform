import assert from "node:assert/strict";
import { test } from "node:test";

import { clientContacts, contactHref } from "./lawyer-contacts.ts";

test("письмо, звонок и чат распознаются по виду значения", () => {
  assert.equal(contactHref("ivan@example.ru"), "mailto:ivan@example.ru");
  assert.equal(contactHref("+7 (912) 345-67-89"), "tel:+79123456789");
  assert.equal(contactHref("@ivan_petrov"), "https://t.me/ivan_petrov");
  assert.equal(contactHref("Иван, звонить после 18"), null);
});

test("одно значение в трёх полях показывается один раз", () => {
  const contacts = clientContacts({
    contact: "ivan@example.ru",
    email: "Ivan@Example.ru",
    phone: "+7 912 345-67-89",
    telegram_user_id: null,
  });
  assert.deepEqual(
    contacts.map((c) => c.value),
    ["ivan@example.ru", "+7 912 345-67-89"],
  );
});

test("без @имени чат открывается по идентификатору", () => {
  const contacts = clientContacts({ contact: null, email: null, phone: null, telegram_user_id: 42 });
  assert.deepEqual(contacts, [{ value: "Чат в Telegram", href: "tg://user?id=42" }]);
});

test("с @именем второй ссылки на чат нет", () => {
  const contacts = clientContacts({ contact: "@ivan", email: null, phone: null, telegram_user_id: 42 });
  assert.equal(contacts.length, 1);
  assert.equal(contacts[0].href, "https://t.me/ivan");
});

test("пустые поля не дают пустых строк", () => {
  assert.deepEqual(clientContacts({ contact: "  ", email: "", phone: null, telegram_user_id: null }), []);
});
