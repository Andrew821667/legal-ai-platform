import test from "node:test";
import assert from "node:assert/strict";

import { buildLeadAttribution } from "./lead-attribution.ts";

test("marks a Google visit as organic and keeps the first landing page", () => {
  const data = buildLeadAttribution(
    "https://ai-verdict.ru/legal-ai/contract-review",
    "https://www.google.com/",
  );

  assert.equal(data.utm_source, "google");
  assert.equal(data.utm_medium, "organic");
  assert.equal(data.landing_page, "/legal-ai/contract-review");
});

test("marks a Yandex visit as organic", () => {
  const data = buildLeadAttribution(
    "https://ai-verdict.ru/legal-help/contracts",
    "https://yandex.ru/",
  );

  assert.equal(data.utm_source, "yandex");
  assert.equal(data.utm_medium, "organic");
});

test("keeps an external site as a referral source", () => {
  const data = buildLeadAttribution(
    "https://ai-verdict.ru/contract-ai-system",
    "https://productradar.ru/product/contract-ai",
  );

  assert.equal(data.utm_source, "productradar.ru");
  assert.equal(data.utm_medium, "referral");
});

test("keeps explicit campaign attribution instead of the referrer", () => {
  const data = buildLeadAttribution(
    "https://ai-verdict.ru/?utm_source=telegram&utm_medium=channel&utm_campaign=launch",
    "https://www.google.com/",
  );

  assert.equal(data.utm_source, "telegram");
  assert.equal(data.utm_medium, "channel");
  assert.equal(data.utm_campaign, "launch");
});

test("does not turn an internal navigation into a referral", () => {
  const data = buildLeadAttribution(
    "https://ai-verdict.ru/",
    "https://ai-verdict.ru/legal-help/contracts",
  );

  assert.equal(data.utm_source, undefined);
  assert.equal(data.utm_medium, undefined);
});

test("drops unrelated query parameters from the stored landing page", () => {
  const data = buildLeadAttribution(
    "https://ai-verdict.ru/legal-help?email=person%40example.com&utm_source=yandex",
  );

  assert.equal(data.landing_page, "/legal-help?utm_source=yandex");
});
