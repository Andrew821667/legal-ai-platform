import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { aiLawCommentSeeds } from "./aiLawComments.ts";
import {
  listAiLawEditorialComments,
  listPublishedAiLawComments,
  saveAiLawComment,
  validateAiLawComment,
} from "./aiLawEditorialStore.ts";

function withStore(run) {
  const dir = mkdtempSync(path.join(os.tmpdir(), "ai-law-editorial-"));
  const previous = process.env.AI_LAW_EDITORIAL_STORE_PATH;
  process.env.AI_LAW_EDITORIAL_STORE_PATH = path.join(dir, "comments.json");
  try {
    run();
  } finally {
    if (previous === undefined) delete process.env.AI_LAW_EDITORIAL_STORE_PATH;
    else process.env.AI_LAW_EDITORIAL_STORE_PATH = previous;
    rmSync(dir, { recursive: true, force: true });
  }
}

test("drafts stay private until verification and publication", () => withStore(() => {
  saveAiLawComment({ slug: "new-ai-rule", title: "Новая норма", status: "draft" });
  assert.ok(listAiLawEditorialComments().some((item) => item.slug === "new-ai-rule"));
  assert.ok(!listPublishedAiLawComments().some((item) => item.slug === "new-ai-rule"));

  const comment = structuredClone(aiLawCommentSeeds[0]);
  comment.slug = "new-ai-rule";
  comment.title = "Новая норма";
  comment.status = "verified";
  saveAiLawComment(comment);
  assert.ok(!listPublishedAiLawComments().some((item) => item.slug === "new-ai-rule"));

  comment.status = "published";
  saveAiLawComment(comment);
  assert.ok(listPublishedAiLawComments().some((item) => item.slug === "new-ai-rule"));
}));

test("runtime records can archive a bundled publication", () => withStore(() => {
  const comment = structuredClone(aiLawCommentSeeds[0]);
  comment.status = "archived";
  saveAiLawComment(comment);
  assert.ok(!listPublishedAiLawComments().some((item) => item.slug === comment.slug));
}));

test("verified materials require an official publication source", () => {
  const comment = structuredClone(aiLawCommentSeeds[0]);
  comment.status = "verified";
  comment.officialSource.url = "https://www.consultant.ru/document/example/";
  assert.match(validateAiLawComment(comment).join(" "), /pravo\.gov\.ru/);
});
