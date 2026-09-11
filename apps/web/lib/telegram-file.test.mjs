import assert from "node:assert/strict";
import { test } from "node:test";

import {
  TelegramFileError,
  contentDisposition,
  getTelegramFilePath,
  sendTelegramDocument,
  showsInline,
  telegramFileUrl,
  uploadTelegramDocument,
} from "./telegram-file.ts";

const TOKEN = "123456:SECRET-TOKEN-VALUE";

test("кириллическое имя уходит и в ASCII-запасе, и в UTF-8", () => {
  const header = contentDisposition("договор поставки.pdf", true);
  assert.match(header, /^inline; filename="document\.pdf"; filename\*=UTF-8''/);
  assert.match(header, /%D0%B4%D0%BE%D0%B3%D0%BE%D0%B2%D0%BE%D1%80%20/);
});

test("латинское имя остаётся как есть", () => {
  assert.equal(
    contentDisposition("scan.jpg", false),
    "attachment; filename=\"scan.jpg\"; filename*=UTF-8''scan.jpg",
  );
});

test("без имени — document, кавычки и переводы строк не ломают заголовок", () => {
  assert.match(contentDisposition(null, false), /filename="document"/);
  const evil = contentDisposition('a"b\r\nc.pdf', false);
  assert.ok(!evil.includes("\n") && !evil.includes('a"b'));
});

test("PDF и картинки показываются в браузере, остальное скачивается", () => {
  assert.equal(showsInline("application/pdf"), true);
  assert.equal(showsInline("image/jpeg"), true);
  assert.equal(showsInline("application/msword"), false);
  assert.equal(showsInline(null), false);
});

test("путь к файлу берётся из getFile", async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, body: JSON.parse(init.body) });
    return new Response(JSON.stringify({ ok: true, result: { file_path: "documents/file_1.pdf" } }));
  };
  const path = await getTelegramFilePath(TOKEN, "FILE_ID", fetchImpl);
  assert.equal(path, "documents/file_1.pdf");
  assert.equal(calls[0].url, `https://api.telegram.org/bot${TOKEN}/getFile`);
  assert.deepEqual(calls[0].body, { file_id: "FILE_ID" });
  assert.equal(telegramFileUrl(TOKEN, path), `https://api.telegram.org/file/bot${TOKEN}/documents/file_1.pdf`);
});

test("ошибка Telegram не выносит токен и говорит по-русски", async () => {
  const fetchImpl = async () =>
    new Response(JSON.stringify({ ok: false, description: "Bad Request: file is too big" }), { status: 400 });
  await assert.rejects(
    getTelegramFilePath(TOKEN, "FILE_ID", fetchImpl),
    (err) => err instanceof TelegramFileError && /20 МБ/.test(err.message) && !err.message.includes("SECRET"),
  );
});

test("сеть упала — тоже без токена", async () => {
  const fetchImpl = async () => { throw new Error(`connect failed for bot${TOKEN}`); };
  await assert.rejects(
    getTelegramFilePath(TOKEN, "FILE_ID", fetchImpl),
    (err) => err instanceof TelegramFileError && !err.message.includes("SECRET"),
  );
});

test("пересылка в чат идёт по идентификатору, без байтов", async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, body: JSON.parse(init.body) });
    return new Response(JSON.stringify({ ok: true, result: { message_id: 1 } }));
  };
  await sendTelegramDocument(TOKEN, 321, "FILE_ID", "договор.pdf", fetchImpl);
  assert.equal(calls[0].url, `https://api.telegram.org/bot${TOKEN}/sendDocument`);
  assert.deepEqual(calls[0].body, { chat_id: 321, document: "FILE_ID", caption: "договор.pdf" });
});

test("выгрузка уходит в чат multipart-формой с именем файла", async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, form: init.body });
    return new Response(JSON.stringify({ ok: true, result: {} }));
  };
  const bytes = new TextEncoder().encode("\uFEFFНомер;Клиент\r\n");
  await uploadTelegramDocument(TOKEN, 42, { name: "договоры-2026-09-11.csv", type: "text/csv", bytes }, "Договоры", fetchImpl);

  assert.equal(calls[0].url, `https://api.telegram.org/bot${TOKEN}/sendDocument`);
  const form = calls[0].form;
  assert.ok(form instanceof FormData);
  assert.equal(form.get("chat_id"), "42");
  assert.equal(form.get("caption"), "Договоры");
  const file = form.get("document");
  assert.equal(file.name, "договоры-2026-09-11.csv");
  // text() по спецификации снимает BOM — сверяем байты: в файле он должен остаться.
  assert.deepEqual(new Uint8Array(await file.arrayBuffer()), bytes);
});

test("отказ Telegram при выгрузке — по-русски и без токена", async () => {
  const fetchImpl = async () => new Response(JSON.stringify({ ok: false, description: "Bad Request" }), { status: 400 });
  await assert.rejects(
    uploadTelegramDocument(TOKEN, 42, { name: "a.csv", type: "text/csv", bytes: new Uint8Array() }, "x", fetchImpl),
    (err) => err instanceof TelegramFileError && !err.message.includes("SECRET"),
  );
});
