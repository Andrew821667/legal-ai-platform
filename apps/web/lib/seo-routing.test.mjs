import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const read = (path) => readFileSync(resolve(webRoot, path), "utf8");

test("keeps booking out of search while the service page owns consultation intent", () => {
  const booking = read("app/consultation/page.tsx");
  const sitemap = read("app/sitemap.ts");

  assert.match(booking, /path: "\/legal-help\/online-consultation"/);
  assert.match(booking, /index: false/);
  assert.match(booking, /follow: true/);
  assert.doesNotMatch(sitemap, /path: "\/consultation"/);
});

test("AI discovery files include current commercial and expert pages", () => {
  const concise = read("public/llms.txt");
  const full = read("public/llms-full.txt");
  const requiredPaths = [
    "/engineering/automation-diagnostic",
    "/engineering/telegram-bots",
    "/engineering/ai-rag",
    "/guides/online-lawyer-consultation-price",
    "/guides/business-process-automation-audit",
    "/guides/contract-review-lawyer-price",
    "/guides/response-to-counterparty-claim",
  ];

  for (const path of requiredPaths) {
    assert.match(concise, new RegExp(path));
    assert.match(full, new RegExp(path));
  }
});
