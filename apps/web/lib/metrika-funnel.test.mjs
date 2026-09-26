import assert from "node:assert/strict";
import { test } from "node:test";

import {
  createStatsCache,
  leadGoalIds,
  loadSiteStats,
  metrikaConfig,
  parseStats,
  periodDates,
  statsUrl,
} from "./metrika-funnel.ts";

const GOALS = {
  goals: [
    { id: 101, name: "Заявка", type: "action", conditions: [{ type: "exact", url: "lead_form_submit" }] },
    { id: 102, name: "Стартовый пакет", type: "action", conditions: [{ type: "exact", url: "starter_offer_submit" }] },
    { id: 103, name: "Выбор пакета", type: "action", conditions: [{ type: "exact", url: "starter_offer_select" }] },
    { id: 104, name: "Страница", type: "url", conditions: [{ type: "contain", url: "/contacts" }] },
  ],
};

const DATA = {
  totals: [120, 90, 4, 1],
  data: [
    { dimensions: [{ id: "direct", name: "Direct traffic" }], metrics: [30, 25, 1, 0] },
    { dimensions: [{ id: "organic", name: "Search engine traffic" }], metrics: [80, 60, 3, 1] },
    { dimensions: [{ id: "new_kind", name: "Новый вид" }], metrics: [10, 5, 0, 0] },
  ],
};

const config = { counterId: "110733908", token: "test-token" };

test("без токена Метрики — выключено; номер счётчика по умолчанию — сайта", () => {
  assert.equal(metrikaConfig({}), null);
  assert.deepEqual(metrikaConfig({ YM_ACCESS_TOKEN: " t " }), { counterId: "110733908", token: "t" });
  assert.equal(metrikaConfig({ YM_ACCESS_TOKEN: "t", YM_COUNTER_ID: "12;drop" }), null);
});

test("период — по московской дате, как считает Метрика", () => {
  // 21:30 UTC 26.09 — в Москве уже 27.09.
  const dates = periodDates(new Date("2026-09-26T21:30:00Z"), 30);
  assert.deepEqual(dates, { date1: "2026-08-28", date2: "2026-09-27" });
});

test("цели заявки находятся по идентификатору события, остальные — нет", () => {
  assert.deepEqual(leadGoalIds(GOALS), [101, 102]);
  assert.deepEqual(leadGoalIds(null), []);
  assert.deepEqual(leadGoalIds({ goals: [{ id: "x", conditions: [{ url: "lead_form_submit" }] }] }), []);
});

test("запрос — визиты, люди и достижения целей по источникам, без выборки", () => {
  const url = new URL(statsUrl(config, { date1: "2026-08-28", date2: "2026-09-27" }, [101, 102]));
  assert.equal(url.searchParams.get("metrics"), "ym:s:visits,ym:s:users,ym:s:goal101reaches,ym:s:goal102reaches");
  assert.equal(url.searchParams.get("dimensions"), "ym:s:lastTrafficSource");
  assert.equal(url.searchParams.get("accuracy"), "full");
  assert.equal(url.searchParams.get("ids"), "110733908");
});

test("разбор: итоги, источники по визитам, отправки формы — сумма целей", () => {
  const stats = parseStats(DATA, 2, { date1: "a", date2: "b" });
  assert.equal(stats.status, "ok");
  assert.equal(stats.visits, 120);
  assert.equal(stats.users, 90);
  assert.equal(stats.formSubmits, 5);
  assert.deepEqual(
    stats.sources.map((s) => [s.title, s.visits, s.formSubmits]),
    [
      ["Поиск", 80, 4],
      ["Прямые заходы", 30, 1],
      ["Новый вид", 10, 0],
    ],
  );
  // Целей нет — отправки неизвестны, а не ноль.
  assert.equal(parseStats(DATA, 0, { date1: "a", date2: "b" }).formSubmits, null);
  assert.equal(parseStats({}, 0, { date1: "a", date2: "b" }).status, "error");
});

test("загрузка: токен в заголовке, цели, затем данные", async () => {
  const calls = [];
  const fake = async (url, init) => {
    calls.push({ url: String(url), auth: init.headers.Authorization });
    const body = String(url).includes("/goals") ? GOALS : DATA;
    return new Response(JSON.stringify(body), { status: 200 });
  };
  const stats = await loadSiteStats(config, 30, new Date("2026-09-26T10:00:00Z"), fake);
  assert.equal(stats.status, "ok");
  assert.equal(stats.formSubmits, 5);
  assert.equal(calls.length, 2);
  assert.ok(calls.every((c) => c.auth === "OAuth test-token"));
  assert.ok(!calls.some((c) => c.url.includes("test-token")), "токен не в адресе");
});

test("цели недоступны — визиты всё равно есть; токен отклонён — понятная ошибка", async () => {
  const noGoals = async (url) =>
    String(url).includes("/goals")
      ? new Response("{}", { status: 500 })
      : new Response(JSON.stringify(DATA), { status: 200 });
  const stats = await loadSiteStats(config, 30, new Date(), noGoals);
  assert.equal(stats.status, "ok");
  assert.equal(stats.formSubmits, null);

  const denied = async () => new Response("{}", { status: 403 });
  const failed = await loadSiteStats(config, 30, new Date(), denied);
  assert.equal(failed.status, "error");
  assert.match(failed.detail, /metrika:read/);

  assert.deepEqual(await loadSiteStats(null, 30), { status: "off" });
});

test("кэш: удачный ответ полчаса, ошибка — пять минут", async () => {
  const cache = createStatsCache();
  let loads = 0;
  const ok = async () => {
    loads += 1;
    return { status: "ok", date1: "", date2: "", visits: loads, users: 0, formSubmits: null, sources: [] };
  };
  await cache("30", ok, 0);
  await cache("30", ok, 29 * 60_000);
  assert.equal(loads, 1);
  await cache("30", ok, 31 * 60_000);
  assert.equal(loads, 2);

  let errors = 0;
  const bad = async () => {
    errors += 1;
    return { status: "error", detail: "x" };
  };
  await cache("90", bad, 0);
  await cache("90", bad, 4 * 60_000);
  await cache("90", bad, 6 * 60_000);
  assert.equal(errors, 2);
});
