import assert from "node:assert/strict";
import { test } from "node:test";

import { collectTitles, commonDocuments, deliveryNote, MAX_ITEMS, waitingSummary } from "./document-requests.ts";

const row = (status, title = "Паспорт") => ({
  request_id: title + status,
  intake_id: "i",
  title,
  note: null,
  status,
  document_id: null,
  created_at: null,
  received_at: null,
});

test("частые документы — по практике", () => {
  assert.ok(commonDocuments("legal").some((t) => t.startsWith("Паспорт")));
  assert.ok(commonDocuments("engineering").includes("Документация API"));
  assert.ok(commonDocuments("hybrid").length > 4);
});

test("список: отмеченное и своё, без пустых и повторов, с пределом", () => {
  assert.deepEqual(
    collectTitles(["Паспорт", "Договор"], "  договор \nСправка 2-НДФЛ; ;x\nПереписка  в  WhatsApp"),
    ["Паспорт", "Договор", "Справка 2-НДФЛ", "Переписка в WhatsApp"],
  );
  const many = Array.from({ length: 30 }, (_, i) => `Документ ${i}`).join("\n");
  assert.equal(collectTitles([], many).length, MAX_ITEMS);
});

test("итог: сколько ждём, отменённые не в счёт", () => {
  assert.equal(waitingSummary([]), null);
  assert.equal(waitingSummary([row("open"), row("received", "Договор"), row("cancelled", "ЕГРН")]), "ждём 1 из 2");
  assert.equal(waitingSummary([row("received")]), "всё получено");
});

test("после отправки — куда ушло и что делать юристу", () => {
  const requests = [row("open")];
  assert.match(deliveryNote({ requests, delivered_via: "telegram" }), /в Telegram/);
  assert.match(deliveryNote({ requests, delivered_via: "queued" }), /повторится само/);
  assert.match(deliveryNote({ requests, delivered_via: "cabinet", cabinet_email: "a@b.ru" }), /a@b\.ru/);
  assert.match(deliveryNote({ requests, delivered_via: "not_configured" }), /не настроен/);
  assert.match(deliveryNote({ requests, delivered_via: "none" }), /передайте список сами/);
});
