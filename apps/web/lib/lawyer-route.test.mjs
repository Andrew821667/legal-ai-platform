import assert from "node:assert/strict";
import { test } from "node:test";

import { buildWorkspaceSearch, parseWorkspaceRoute } from "./lawyer-route.ts";

const LEAD = "11111111-1111-4111-8111-111111111111";

test("пустой адрес — список клиентов", () => {
  assert.deepEqual(parseWorkspaceRoute(""), { tab: "clients", client: null });
});

test("client= открывает карточку", () => {
  assert.deepEqual(parseWorkspaceRoute(`?client=${LEAD}`), { tab: "clients", client: LEAD });
});

test("идентификатор приводится к нижнему регистру", () => {
  assert.equal(parseWorkspaceRoute(`?client=${LEAD.toUpperCase()}`).client, LEAD);
});

test("мусор вместо идентификатора не открывает ничего", () => {
  // Иначе любая ссылка с опечаткой дёргала бы сервер и показывала ошибку.
  for (const junk of ["abc", "1", "../etc", "<script>", `${LEAD}x`]) {
    assert.equal(parseWorkspaceRoute(`?client=${encodeURIComponent(junk)}`).client, null, junk);
  }
});

test("tab= выбирает вкладку, неизвестная — клиенты", () => {
  assert.equal(parseWorkspaceRoute("?tab=today").tab, "today");
  assert.equal(parseWorkspaceRoute("?tab=finance").tab, "finance");
  assert.equal(parseWorkspaceRoute("?tab=nope").tab, "clients");
});

test("адрес собирается обратно", () => {
  assert.equal(buildWorkspaceSearch({ tab: "clients", client: null }), "");
  assert.equal(buildWorkspaceSearch({ tab: "today", client: null }), "?tab=today");
  assert.equal(buildWorkspaceSearch({ tab: "clients", client: LEAD }), `?client=${LEAD}`);
});

test("карточка важнее вкладки: с client= вкладка в адрес не попадает", () => {
  // Карточка — отдельный экран поверх вкладок; куда вернуться после неё,
  // решает история, а не адрес.
  assert.equal(buildWorkspaceSearch({ tab: "today", client: LEAD }), `?client=${LEAD}`);
});

test("разбор и сборка — обратные друг другу", () => {
  for (const route of [
    { tab: "clients", client: null },
    { tab: "finance", client: null },
    { tab: "clients", client: LEAD },
  ]) {
    assert.deepEqual(parseWorkspaceRoute(buildWorkspaceSearch(route)), route);
  }
});
