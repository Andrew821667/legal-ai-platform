import assert from "node:assert/strict";
import { test } from "node:test";

import { publicOrigin } from "./public-origin.ts";

test("использует X-Forwarded-* от Caddy, а не адрес процесса", () => {
  const headers = new Headers({
    "x-forwarded-proto": "https",
    "x-forwarded-host": "ai-verdict.ru",
    host: "0.0.0.0:3000",
  });
  assert.equal(publicOrigin(headers, "0.0.0.0:3000"), "https://ai-verdict.ru");
});

test("без X-Forwarded-Host падает на обычный Host", () => {
  const headers = new Headers({ "x-forwarded-proto": "https", host: "ai-verdict.ru" });
  assert.equal(publicOrigin(headers, "0.0.0.0:3000"), "https://ai-verdict.ru");
});

test("без X-Forwarded-Proto по умолчанию https, а не адрес процесса", () => {
  const headers = new Headers({ host: "ai-verdict.ru" });
  assert.equal(publicOrigin(headers, "0.0.0.0:3000"), "https://ai-verdict.ru");
});

test("при отсутствии всех заголовков берёт NEXT_PUBLIC_SITE_URL", () => {
  const saved = process.env.NEXT_PUBLIC_SITE_URL;
  process.env.NEXT_PUBLIC_SITE_URL = "https://ai-verdict.ru";
  try {
    const headers = new Headers();
    assert.equal(publicOrigin(headers, "0.0.0.0:3000"), "https://ai-verdict.ru");
  } finally {
    if (saved === undefined) delete process.env.NEXT_PUBLIC_SITE_URL;
    else process.env.NEXT_PUBLIC_SITE_URL = saved;
  }
});

test("совсем без сигналов о домене — запасной адрес процесса, а не падение", () => {
  const saved = process.env.NEXT_PUBLIC_SITE_URL;
  delete process.env.NEXT_PUBLIC_SITE_URL;
  try {
    // Это ровно тот случай, который уронил прод: без заголовков от прокси и
    // без NEXT_PUBLIC_SITE_URL остаётся только адрес самого процесса.
    // Не идеально, но предсказуемо — и не падает с исключением.
    assert.equal(publicOrigin(new Headers(), "0.0.0.0:3000"), "https://0.0.0.0:3000");
  } finally {
    if (saved !== undefined) process.env.NEXT_PUBLIC_SITE_URL = saved;
  }
});
