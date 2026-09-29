import test from "node:test";
import assert from "node:assert/strict";

import {
  buildLeadAttribution,
  trackLeadConversion,
  trackServiceRouteClick,
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

test("tracks each service route with its destination and first-touch source", () => {
  const calls = [];
  globalThis.window = {
    location: { href: "https://ai-verdict.ru/legal-ai/prompts-for-lawyers" },
    sessionStorage: {
      getItem: () => JSON.stringify({
        landing_page: "/legal-ai/prompts-for-lawyers",
        utm_source: "google",
        utm_medium: "organic",
      }),
    },
    ym: (...args) => calls.push(args),
  };

  try {
    trackServiceRouteClick("legal_contract_review", "/legal-help/contracts");
    trackServiceRouteClick("contract_ai", "/contract-ai-system");
    trackServiceRouteClick("engineering_rag_service", "/engineering/ai-rag");
  } finally {
    delete globalThis.window;
  }

  assert.equal(calls.length, 3);
  for (const call of calls) {
    assert.equal(call[1], "reachGoal");
    assert.equal(call[2], "service_route_click");
  }
  assert.deepEqual(calls.map((call) => call[3].route), [
    "legal_contract_review",
    "contract_ai",
    "engineering_rag_service",
  ]);
  assert.deepEqual(calls.map((call) => call[3].destination), [
    "/legal-help/contracts",
    "/contract-ai-system",
    "/engineering/ai-rag",
  ]);
  assert.deepEqual(calls[0][3], {
    route: "legal_contract_review",
    from_page: "/legal-ai/prompts-for-lawyers",
    destination: "/legal-help/contracts",
    landing_page: "/legal-ai/prompts-for-lawyers",
    traffic_source: "google",
    traffic_medium: "organic",
  });
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

  // Google Analytics убран: цели уходят только в Яндекс Метрику.
  assert.ok(!calls.some((call) => call[0] === "gtag"));
  assert.ok(calls.some((call) =>
    call[0] === "ym" &&
    call[3] === "starter_offer_submit" &&
    call[4].starter_offer_id === "engineering_rag_service"
  ));
});
