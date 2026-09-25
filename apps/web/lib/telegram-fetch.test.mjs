import assert from "node:assert/strict";
import { createServer } from "node:http";
import { test } from "node:test";

/**
 * Запрос к Telegram идёт через прокси — проверяем на живом фальшивом прокси:
 * он видит запрос целиком, включая multipart-тело загрузки файла.
 */
test("getFile и загрузка файла уходят через LEGAL_AI_HTTPS_PROXY", async () => {
  const seen = [];
  const proxy = createServer((req, res) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      seen.push({ url: req.url, type: req.headers["content-type"] || "", body: Buffer.concat(chunks).toString("utf8") });
      res.writeHead(200, { "content-type": "application/json" });
      const result = req.url.endsWith("/getFile") ? { file_path: "docs/file.pdf" } : { message_id: 1 };
      res.end(JSON.stringify({ ok: true, result }));
    });
  });
  await new Promise((resolve) => proxy.listen(0, "127.0.0.1", resolve));
  const { port } = proxy.address();
  process.env.LEGAL_AI_HTTPS_PROXY = `http://127.0.0.1:${port}`;
  process.env.TELEGRAM_API_BASE = "http://telegram.test";
  try {
    const files = await import(`./telegram-file.ts?proxy=${port}`);
    const path = await files.getTelegramFilePath("123:TOKEN", "file-id");
    assert.equal(path, "docs/file.pdf");
    await files.uploadTelegramDocument(
      "123:TOKEN",
      42,
      { name: "договор.pdf", type: "application/pdf", bytes: new Uint8Array([37, 80, 68, 70]) },
      "Документ от клиента",
    );
    // Прокси видит абсолютный адрес — значит, запрос шёл через него.
    assert.equal(seen[0].url, "http://telegram.test/bot123:TOKEN/getFile");
    assert.equal(seen[1].url, "http://telegram.test/bot123:TOKEN/sendDocument");
    assert.match(seen[1].type, /^multipart\/form-data; boundary=/);
    assert.match(seen[1].body, /name="chat_id"\r\n\r\n42/);
    assert.match(seen[1].body, /Документ от клиента/);
    assert.match(seen[1].body, /%PDF/);
  } finally {
    await new Promise((resolve) => proxy.close(resolve));
    delete process.env.LEGAL_AI_HTTPS_PROXY;
    delete process.env.TELEGRAM_API_BASE;
  }
});
