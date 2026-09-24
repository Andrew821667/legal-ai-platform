import assert from "node:assert/strict";
import { test } from "node:test";

import { matterStage, stageFor, WITHOUT_AGREEMENT_STAGE } from "./lawyer-stage.ts";

test("лестница этапов совпадает с ядром", () => {
  assert.equal(stageFor(false, null), "Первичное обращение");
  assert.equal(stageFor(true, null), "Готовим условия");
  assert.equal(stageFor(true, "draft"), "Договор не отправлен");
  assert.equal(stageFor(true, "sent"), "Договор у клиента");
  assert.equal(stageFor(true, "viewed"), "Договор у клиента");
  assert.equal(stageFor(true, "signed"), "Договор подписан");
  assert.equal(stageFor(true, "declined"), "Клиент отказался");
});

test("этап обращения — по его последнему договору, а не по первому в списке", () => {
  const agreements = [
    { status: "declined", created_at: "2026-08-01T00:00:00Z" },
    { status: "signed", created_at: "2026-09-01T00:00:00Z" },
  ];
  assert.equal(matterStage(agreements, true), "Договор подписан");
  assert.equal(matterStage([], true), "Готовим условия");
});

test("без договора — свой этап, пока договор всё же не составлен", () => {
  assert.equal(stageFor(true, null, true), WITHOUT_AGREEMENT_STAGE);
  assert.equal(matterStage([], true, true), "В работе без договора");
  // Передумали и составили договор — этап снова по нему.
  assert.equal(matterStage([{ status: "sent", created_at: "2026-09-20T00:00:00Z" }], true, true), "Договор у клиента");
});
