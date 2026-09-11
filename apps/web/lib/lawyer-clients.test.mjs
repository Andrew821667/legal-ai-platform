import assert from "node:assert/strict";
import { test } from "node:test";

import { clientGroup, groupClients, matchesFilter } from "./lawyer-clients.ts";

const row = (stage, extra = {}) => ({ stage, waiting_on_me: false, nda_signed: true, ...extra });

test("вопрос клиента без ответа — мой ход, какой бы ни была стадия", () => {
  assert.equal(clientGroup(row("Договор подписан", { waiting_on_me: true })), "mine");
  assert.equal(clientGroup(row("Договор у клиента", { waiting_on_me: true })), "mine");
});

test("стадии раскладываются по тому, у кого ход", () => {
  assert.equal(clientGroup(row("Первичное обращение")), "mine");
  assert.equal(clientGroup(row("Готовим условия")), "mine");
  assert.equal(clientGroup(row("Договор не отправлен")), "mine");
  assert.equal(clientGroup(row("Договор у клиента")), "theirs");
  assert.equal(clientGroup(row("Договор подписан")), "active");
  assert.equal(clientGroup(row("Клиент отказался")), "declined");
});

test("группы идут в порядке срочности, пустые не показываются", () => {
  const groups = groupClients([row("Договор подписан"), row("Договор у клиента"), row("Первичное обращение")]);
  assert.deepEqual(
    groups.map((g) => [g.key, g.rows.length]),
    [
      ["mine", 1],
      ["theirs", 1],
      ["active", 1],
    ],
  );
});

test("порядок сервера внутри группы сохраняется", () => {
  const a = row("Первичное обращение", { name: "a" });
  const b = row("Готовим условия", { name: "b" });
  const [group] = groupClients([a, b]);
  assert.deepEqual(group.rows.map((r) => r.name), ["a", "b"]);
});

test("фильтры", () => {
  assert.ok(matchesFilter(row("Договор подписан"), "signed"));
  assert.ok(!matchesFilter(row("Договор у клиента"), "signed"));
  assert.ok(matchesFilter(row("Первичное обращение", { nda_signed: false }), "no_nda"));
  assert.ok(matchesFilter(row("Первичное обращение", { waiting_on_me: true }), "waiting"));
  assert.deepEqual(groupClients([row("Договор подписан")], "waiting"), []);
});
