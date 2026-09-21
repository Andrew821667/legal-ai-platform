import test from "node:test";
import assert from "node:assert/strict";

import {
  buildLeadAttribution,
  trackLeadConversion,
  trackStarterOfferSelection,
} from "./lead-attribution.ts";
import { starterOffers } from "./starter-offers.ts";

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

test("tracks selection and submission by starter offer id", () => {
  const calls = [];
  globalThis.window = {
    gtag: (...args) => calls.push(["gtag", ...args]),
    ym: (...args) => calls.push(["ym", ...args]),
  };

  try {
    trackStarterOfferSelection(starterOffers.engineering_rag_service);
    trackLeadConversion(
      "general",
      { landing_page: "/engineering", utm_source: "google", utm_medium: "organic" },
      "engineering_rag_service",
    );
  } finally {
    delete globalThis.window;
  }

  assert.ok(calls.some((call) =>
    call[0] === "gtag" &&
    call[2] === "starter_offer_select" &&
    call[3].starter_offer_id === "engineering_rag_service"
  ));
  assert.ok(calls.some((call) =>
    call[0] === "gtag" &&
    call[2] === "starter_offer_submit" &&
    call[3].starter_offer_id === "engineering_rag_service"
  ));
  assert.ok(calls.some((call) =>
    call[0] === "ym" &&
    call[3] === "starter_offer_submit" &&
    call[4].starter_offer_id === "engineering_rag_service"
  ));
});
