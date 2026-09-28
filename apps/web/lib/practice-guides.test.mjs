import assert from "node:assert/strict";
import test from "node:test";

import { guides } from "./guidesData.ts";

const planned = [
  ["check-contract-before-signing", "legal", "/legal-help/contracts"],
  ["check-apartment-before-purchase", "legal", "/legal-help/real-estate"],
  ["telegram-bot-development-cost", "engineering", "/engineering/telegram-bots"],
  ["prepare-data-for-rag", "engineering", "/engineering/ai-rag"],
];

test("practice guides have distinct intent and a matching service route", () => {
  assert.equal(new Set(guides.map((guide) => guide.slug)).size, guides.length);
  assert.equal(new Set(guides.map((guide) => guide.seoTitle || guide.title)).size, guides.length);
  assert.ok(guides.every((guide) => ["platform", "legal", "engineering"].includes(guide.practice)));

  for (const [slug, practice, href] of planned) {
    const guide = guides.find((item) => item.slug === slug);
    assert.ok(guide, `${slug} is missing`);
    assert.equal(guide.practice, practice);
    assert.equal(guide.cta?.href, href);
    assert.ok(guide.sections.length >= 4);
    assert.ok(guide.checklist.length >= 5);
    if (practice === "legal") assert.ok(guide.sources?.length);
  }
});

test("general legal guide supports the main legal services page", () => {
  const guide = guides.find((item) => item.slug === "which-legal-help-do-i-need");
  assert.ok(guide);
  assert.equal(guide.practice, "legal");
  assert.equal(guide.cta?.href, "/legal-help");
  assert.ok(guide.sections.length >= 4);
  assert.ok(guide.checklist.length >= 5);
});

test("introductory AI guide leads to process diagnosis", () => {
  const guide = guides.find((item) => item.slug === "how-to-start-ai-adoption");
  assert.ok(guide);
  assert.equal(guide.practice, "engineering");
  assert.equal(guide.cta?.href, "/engineering/automation-diagnostic");
  assert.ok(guide.sections.length >= 4);
  assert.ok(guide.checklist.length >= 5);
  assert.ok(guide.sources?.length);
});
