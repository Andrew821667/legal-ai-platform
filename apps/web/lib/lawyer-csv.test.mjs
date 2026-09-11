import assert from "node:assert/strict";
import { test } from "node:test";

import { agreementsCsv, agreementsCsvFileName, csvAmount, csvDate } from "./lawyer-csv.ts";

const row = (extra = {}) => ({
  number: "AV-20260909-2EFAB3-R2",
  client: "Александр Рябов",
  subject: "Сопровождение раздела имущества",
  status: "signed",
  amount_minor: 1250050,
  price_text: "12 500,50 ₽",
  created_at: "2026-09-09T10:00:00Z",
  sent_at: "2026-09-09T12:00:00Z",
  signed_at: "2026-09-10T21:30:00Z",
  ...extra,
});

test("файл открывается в русском Excel: BOM, точка с запятой, CRLF", () => {
  const csv = agreementsCsv([row()]);
  assert.ok(csv.startsWith("\uFEFF"));
  const lines = csv.slice(1).split("\r\n");
  assert.equal(lines[0], "Номер;Клиент;Предмет;Статус;Сумма, ₽;Цена в документе;Составлен;Отправлен;Подписан");
  assert.equal(
    lines[1],
    "AV-20260909-2EFAB3-R2;Александр Рябов;Сопровождение раздела имущества;Подписан;12500,50;12 500,50 ₽;09.09.2026;09.09.2026;11.09.2026",
  );
  assert.equal(lines[2], "");
});

test("разделитель, кавычка и перенос внутри значения — в кавычках", () => {
  const csv = agreementsCsv([row({ subject: 'Договор "поставки"; срочно\nдва этапа' })]);
  assert.ok(csv.includes('"Договор ""поставки""; срочно\nдва этапа"'));
});

test("сумма — число с запятой, без суммы — пусто", () => {
  assert.equal(csvAmount(1000000), "10000,00");
  assert.equal(csvAmount(5), "0,05");
  assert.equal(csvAmount(null), "");
  assert.ok(agreementsCsv([row({ amount_minor: null, price_text: null })]).includes(";Подписан;;;09.09.2026"));
});

test("дата — по Москве, без времени; мусор — пусто", () => {
  // 21:30 UTC — это уже следующий день по Москве.
  assert.equal(csvDate("2026-09-10T21:30:00Z"), "11.09.2026");
  assert.equal(csvDate("нет"), "");
  assert.equal(csvDate(null), "");
});

test("неизвестный статус остаётся кодом, а не пустотой", () => {
  assert.ok(agreementsCsv([row({ status: "weird" })]).includes(";weird;"));
});

test("имя файла — с датой выгрузки", () => {
  assert.equal(agreementsCsvFileName(new Date("2026-09-11T12:00:00Z")), "договоры-2026-09-11.csv");
});
