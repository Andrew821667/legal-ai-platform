import assert from "node:assert/strict";
import test from "node:test";

import { aiLawComments } from "./aiLawComments.ts";

test("published AI law comments are traceable to official sources", () => {
  assert.ok(aiLawComments.length > 0);

  const slugs = new Set();
  for (const comment of aiLawComments) {
    assert.equal(comment.status, "published");
    assert.ok(!slugs.has(comment.slug), `duplicate slug: ${comment.slug}`);
    slugs.add(comment.slug);

    const source = new URL(comment.officialSource.url);
    assert.equal(source.hostname, "publication.pravo.gov.ru");
    assert.ok(comment.officialSource.publicationId);
    assert.ok(comment.reviewedAt >= comment.lawDate);
    assert.ok(comment.effectiveStages.length > 0);

    const dates = comment.effectiveStages.map((stage) => stage.date);
    assert.deepEqual(dates, [...dates].sort());
  }
});

test("243-FZ comment separates both effective dates and common myths", () => {
  const comment = aiLawComments.find((item) => item.lawNumber === "243-ФЗ");
  assert.ok(comment);
  assert.deepEqual(
    comment.effectiveStages.map((stage) => stage.date),
    ["2026-09-01", "2027-03-01"],
  );

  const myths = comment.misconceptions.map((item) => item.claim).join(" ");
  assert.match(myths, /маркировать/i);
  assert.match(myths, /иностранные модели/i);
});
