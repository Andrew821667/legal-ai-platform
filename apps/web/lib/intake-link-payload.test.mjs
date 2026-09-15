import assert from "node:assert/strict";
import { test } from "node:test";

import { parseIntakeLinkPayload } from "./intake-link-payload.ts";

const LEAD = "11111111-1111-4111-8111-111111111111";
const INTAKE = "22222222-2222-4222-8222-222222222222";

test("клиент и роль — достаточно, конкретное дело необязательно", () => {
  assert.deepEqual(parseIntakeLinkPayload({ linked_lead_id: LEAD, role: "joint" }), {
    ok: true,
    payload: { linked_lead_id: LEAD, role: "joint" },
  });
});

test("конкретное дело уходит в ядро как есть", () => {
  const result = parseIntakeLinkPayload({
    linked_lead_id: LEAD,
    linked_intake_id: INTAKE,
    role: "subordinate",
    note: "  общий спор  ",
  });
  assert.deepEqual(result, {
    ok: true,
    payload: { linked_lead_id: LEAD, linked_intake_id: INTAKE, role: "subordinate", note: "общий спор" },
  });
});

test("пустое дело — то же, что не указано", () => {
  for (const empty of ["", null, undefined]) {
    const result = parseIntakeLinkPayload({ linked_lead_id: LEAD, linked_intake_id: empty, role: "main" });
    assert.equal(result.ok, true);
    assert.equal("linked_intake_id" in result.payload, false, String(empty));
  }
});

test("мусор вместо идентификаторов и роли не проходит", () => {
  assert.equal(parseIntakeLinkPayload({ linked_lead_id: "abc", role: "joint" }).ok, false);
  assert.equal(parseIntakeLinkPayload({ linked_lead_id: LEAD, role: "boss" }).ok, false);
  assert.equal(
    parseIntakeLinkPayload({ linked_lead_id: LEAD, linked_intake_id: "../x", role: "joint" }).ok,
    false,
  );
  assert.equal(parseIntakeLinkPayload(null).ok, false);
});

test("заметка режется до 500 знаков", () => {
  const result = parseIntakeLinkPayload({ linked_lead_id: LEAD, role: "joint", note: "x".repeat(700) });
  assert.equal(result.ok && result.payload.note?.length, 500);
});
