import assert from "node:assert/strict";
import { test } from "node:test";

import { availableAreas, clientGroup, groupClients, matchesAreas, matchesFilter } from "./lawyer-clients.ts";

const row = (stage_key, extra = {}) => ({
  stage_key,
  waiting_on_me: false,
  nda_signed: true,
  legal_areas: [],
  amount_minor: null,
  ...extra,
});

test("вопрос клиента без ответа — мой ход, какой бы ни была стадия", () => {
  assert.equal(clientGroup(row("signed", { waiting_on_me: true })), "mine");
  assert.equal(clientGroup(row("with_client", { waiting_on_me: true })), "mine");
});

test("стадии раскладываются по тому, у кого ход", () => {
  assert.equal(clientGroup(row("first_contact")), "mine");
  assert.equal(clientGroup(row("preparing_terms")), "mine");
  assert.equal(clientGroup(row("not_sent")), "mine");
  assert.equal(clientGroup(row("with_client")), "theirs");
  assert.equal(clientGroup(row("signed")), "active");
  assert.equal(clientGroup(row("declined")), "declined");
  // Решили вести без договора — работа идёт, хода от юриста по договору не ждём.
  assert.equal(clientGroup(row("without_agreement")), "active");
});

test("группы идут в порядке срочности, пустые не показываются", () => {
  const groups = groupClients([row("signed"), row("with_client"), row("first_contact")]);
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
  const a = row("first_contact", { name: "a" });
  const b = row("preparing_terms", { name: "b" });
  const [group] = groupClients([a, b]);
  assert.deepEqual(group.rows.map((r) => r.name), ["a", "b"]);
});

test("фильтры", () => {
  assert.ok(matchesFilter(row("signed"), "signed"));
  assert.ok(!matchesFilter(row("with_client"), "signed"));
  assert.ok(matchesFilter(row("first_contact", { nda_signed: false }), "no_nda"));
  assert.ok(matchesFilter(row("first_contact", { waiting_on_me: true }), "waiting"));
  assert.deepEqual(groupClients([row("signed")], "waiting"), []);
});

test("область права — пусто выбрано значит проходят все, иначе пересечение", () => {
  const contracts = row("first_contact", { legal_areas: ["contracts"] });
  const employment = row("first_contact", { legal_areas: ["employment"] });
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
  const a = row("first_contact", { legal_areas: ["contracts"] });
  const b = row("with_client", { legal_areas: ["employment"] });
  const groups = groupClients([a, b], "all", { areas: ["contracts"] });
  assert.deepEqual(
    groups.map((g) => g.key),
    ["mine"],
  );
});

test("сортировка по сумме — внутри группы, без суммы хвостом в прежнем порядке", () => {
  const cheap = row("first_contact", { name: "cheap", amount_minor: 10_000 });
  const pricey = row("first_contact", { name: "pricey", amount_minor: 500_000 });
  const unknownFirst = row("first_contact", { name: "unknownFirst", amount_minor: null });
  const unknownSecond = row("first_contact", { name: "unknownSecond", amount_minor: null });
  const [group] = groupClients([cheap, unknownFirst, pricey, unknownSecond], "all", { sort: "amount_desc" });
  assert.deepEqual(group.rows.map((r) => r.name), ["pricey", "cheap", "unknownFirst", "unknownSecond"]);
});

test("сортировка «сначала новые» — порядок сервера как есть, даже с суммами", () => {
  const a = row("first_contact", { name: "a", amount_minor: 100 });
  const b = row("first_contact", { name: "b", amount_minor: 900 });
  const [group] = groupClients([a, b], "all", { sort: "recent" });
  assert.deepEqual(group.rows.map((r) => r.name), ["a", "b"]);
});

test("свои аккаунты — в группе «Тест» внизу, что бы ни ждало ответа", () => {
  assert.equal(clientGroup(row("signed", { is_test: true, waiting_on_me: true })), "test");
  const groups = groupClients([row("first_contact", { is_test: true }), row("signed")]);
  assert.deepEqual(groups.map((g) => g.key), ["active", "test"]);
});
