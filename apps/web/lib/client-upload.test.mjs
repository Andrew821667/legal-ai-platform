import assert from "node:assert/strict";
import { test } from "node:test";

import { MAX_UPLOAD_BYTES, checkUpload } from "./client-upload.ts";

test("документы, сканы и архивы — принимаются", () => {
  for (const name of ["Договор аренды.PDF", "скан.jpg", "выписка.xlsx", "архив.zip", "письмо.docx"]) {
    assert.equal(checkUpload({ name, size: 1000 }).ok, true, name);
  }
});

test("исполняемые и без расширения — нет, и объяснено по-русски", () => {
  const exe = checkUpload({ name: "invoice.exe", size: 10 });
  assert.equal(exe.ok, false);
  assert.match(exe.detail, /\.exe не принимаются/);
  assert.equal(checkUpload({ name: "README", size: 10 }).ok, false);
});

test("пустой и больше 20 МБ — нет", () => {
  assert.equal(checkUpload({ name: "a.pdf", size: 0 }).ok, false);
  assert.equal(checkUpload({ name: "a.pdf", size: MAX_UPLOAD_BYTES + 1 }).ok, false);
  assert.equal(checkUpload({ name: "a.pdf", size: MAX_UPLOAD_BYTES }).ok, true);
});

test("имя очищается от переносов и путей", () => {
  const result = checkUpload({ name: "../../etc\\passwd\n.pdf", size: 5 });
  assert.equal(result.ok, true);
  assert.ok(!result.name.includes("/") && !result.name.includes("\n") && !result.name.includes("\\"));
});
