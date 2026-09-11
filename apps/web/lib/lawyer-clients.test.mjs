import assert from "node:assert/strict";
import { test } from "node:test";

import { availableAreas, clientGroup, groupClients, matchesAreas, matchesFilter } from "./lawyer-clients.ts";

const row = (stage, extra = {}) => ({
  stage,
  waiting_on_me: false,
  nda_signed: true,
  legal_areas: [],
  amount_minor: null,
  ...extra,
});

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

test("область права — пусто выбрано значит проходят все, иначе пересечение", () => {
  const contracts = row("Первичное обращение", { legal_areas: ["contracts"] });
  const employment = row("Первичное обращение", { legal_areas: ["employment"] });
  assert.ok(matchesAreas(contracts, []));
  assert.ok(matchesAreas(contracts, ["contracts", "tax_compliance"]));
  assert.ok(!matchesAreas(employment, ["contracts"]));
});

test("доступные области — самые частые первыми, без повторов", () => {
  const rows = [
    row("x", { legal_areas: ["contracts"] }),
    row("x", { legal_areas: ["employment"] }),
    row("x", { legal_areas: ["contracts"] }),
  ];
  assert.deepEqual(availableAreas(rows), ["contracts", "employment"]);
});

test("groupClients фильтрует по области и держит группировку", () => {
  const a = row("Первичное обращение", { legal_areas: ["contracts"] });
  const b = row("Договор у клиента", { legal_areas: ["employment"] });
  const groups = groupClients([a, b], "all", { areas: ["contracts"] });
  assert.deepEqual(
    groups.map((g) => g.key),
    ["mine"],
  );
});

test("сортировка по сумме — внутри группы, без суммы хвостом в прежнем порядке", () => {
  const cheap = row("Первичное обращение", { name: "cheap", amount_minor: 10_000 });
  const pricey = row("Первичное обращение", { name: "pricey", amount_minor: 500_000 });
  const unknownFirst = row("Первичное обращение", { name: "unknownFirst", amount_minor: null });
  const unknownSecond = row("Первичное обращение", { name: "unknownSecond", amount_minor: null });
  const [group] = groupClients([cheap, unknownFirst, pricey, unknownSecond], "all", { sort: "amount_desc" });
  assert.deepEqual(group.rows.map((r) => r.name), ["pricey", "cheap", "unknownFirst", "unknownSecond"]);
});

test("сортировка «сначала новые» — порядок сервера как есть, даже с суммами", () => {
  const a = row("Первичное обращение", { name: "a", amount_minor: 100 });
  const b = row("Первичное обращение", { name: "b", amount_minor: 900 });
  const [group] = groupClients([a, b], "all", { sort: "recent" });
  assert.deepEqual(group.rows.map((r) => r.name), ["a", "b"]);
});
